#include "OtherworldRpcGuard.h"

#include "Engine/NetConnection.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Net/Core/Connection/NetCloseResult.h"

DEFINE_LOG_CATEGORY_STATIC(LogOtherworldRpcGuard, Log, All);

namespace
{
	// The close reason the kicked client is sent, and the server logs.
	const TCHAR* ClosedByRpcGuard = TEXT("ClosedByRpcGuard");

	struct FBucket
	{
		double Tokens = 0.0;
		double At = 0.0;
	};

	// One connection's state. It outlives a character: a player who dies is
	// given a new one, and its buckets and refusals are still these.
	struct FConnectionState
	{
		TMap<FName, FBucket> Buckets;
		TArray<double> RefusedAt;
		bool bKicked = false;
	};

	TMap<TWeakObjectPtr<UNetConnection>, FConnectionState>& States()
	{
		static TMap<TWeakObjectPtr<UNetConnection>, FConnectionState> Map;
		return Map;
	}

	FConnectionState& StateOf(UNetConnection* Connection)
	{
		TMap<TWeakObjectPtr<UNetConnection>, FConnectionState>& Map = States();
		if (!Map.Contains(Connection))
		{
			// A new connection: forget the ones that have gone.
			for (auto It = Map.CreateIterator(); It; ++It)
			{
				if (!It.Key().IsValid())
				{
					It.RemoveCurrent();
				}
			}
		}
		return Map.FindOrAdd(Connection);
	}
}

UOtherworldRpcGuard::UOtherworldRpcGuard()
{
	PrimaryComponentTick.bCanEverTick = false;
}

UNetConnection* UOtherworldRpcGuard::RemoteConnection() const
{
	const APawn* Pawn = Cast<APawn>(GetOwner());
	const APlayerController* Player = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	if (!Player || !Pawn->HasAuthority() || Player->IsLocalController())
	{
		return nullptr;
	}
	return Player->GetNetConnection();
}

bool UOtherworldRpcGuard::Allow(FName Name)
{
	UNetConnection* Connection = RemoteConnection();
	const UWorld* World = GetWorld();
	if (!Connection || !World)
	{
		return true;
	}
	FConnectionState& State = StateOf(Connection);
	if (State.bKicked)
	{
		// What was already on the wire when the connection was closed.
		return false;
	}
	const double Now = World->GetTimeSeconds();
	const float* Row = Rates.Find(Name);
	const double Rate = FMath::Max(Row ? *Row : DefaultRate, 0.f);
	const double Most = FMath::Max(1.0, Rate * BurstSeconds);
	FBucket* Bucket = State.Buckets.Find(Name);
	if (!Bucket)
	{
		Bucket = &State.Buckets.Add(Name);
		Bucket->Tokens = Most;
		Bucket->At = Now;
	}
	Bucket->Tokens = FMath::Min(Most, Bucket->Tokens + (Now - Bucket->At) * Rate);
	Bucket->At = Now;
	++Counted;
	if (Bucket->Tokens >= 1.0)
	{
		Bucket->Tokens -= 1.0;
		return true;
	}

	++Refused;
	UE_LOG(LogOtherworldRpcGuard, Warning, TEXT("RPC-REFUSED %s (%s)"), *Name.ToString(),
	       *GetNameSafe(GetOwner()));
	State.RefusedAt.RemoveAll([&](double At) { return Now - At > KickSeconds; });
	State.RefusedAt.Add(Now);
	if (State.RefusedAt.Num() > KickRefusals)
	{
		State.bKicked = true;
		bKicked = true;
		UE_LOG(LogOtherworldRpcGuard, Warning,
		       TEXT("RPC-KICKED %s: %d refusals in %.0f s, the last %s (%s)"), ClosedByRpcGuard,
		       State.RefusedAt.Num(), KickSeconds, *Name.ToString(), *GetNameSafe(GetOwner()));
		Connection->Close(UE::Net::FNetCloseResult(ENetCloseResult::Extended, ClosedByRpcGuard));
	}
	return false;
}

bool UOtherworldRpcGuard::AimAllowed(FVector AimPoint)
{
	if (!RemoteConnection())
	{
		return true;
	}
	const APawn* Pawn = CastChecked<APawn>(GetOwner());
	const FVector Look = Pawn->GetBaseAimRotation().Vector();
	const FVector Eyes = Pawn->GetPawnViewLocation();
	const FVector To = AimPoint - (Eyes - Look * AimBackCm);
	const double Along = FVector::DotProduct(To, Look);
	const double Aside = (To - Look * Along).Size();
	const bool bNear = !AimPoint.ContainsNaN() && FVector::DistSquared(AimPoint, Eyes) <= FMath::Square(AimMaxCm);
	const bool bAhead = bNear && Along >= 0.0
		&& Aside <= AimSideCm + Along * FMath::Tan(FMath::DegreesToRadians(AimConeDegrees));
	if (!bAhead)
	{
		++AimRefused;
		UE_LOG(LogOtherworldRpcGuard, Warning, TEXT("RPC-REFUSED AimPoint (%s)"), *GetNameSafe(GetOwner()));
	}
	return bAhead;
}
