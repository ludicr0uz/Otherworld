#include "OtherworldShotLibrary.h"

#include "CollisionQueryParams.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/NetConnection.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "OtherworldHitHistory.h"

DEFINE_LOG_CATEGORY_STATIC(LogOtherworldShot, Log, All);

namespace
{
	UOtherworldHitHistory* HistoryOf(const UObject* WorldContextObject)
	{
		const UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
		return World ? World->GetSubsystem<UOtherworldHitHistory>() : nullptr;
	}

	/** The second trace of a present-day hit: the struck character's bodies, as K2_LineTraceComponent did it. */
	void BodyOfNow(const FHitResult& Hit, const FVector& Start, const FVector& End,
		bool& bBodyHit, FName& BodyBone, FVector& BodyPoint)
	{
		const ACharacter* Character = Cast<ACharacter>(Hit.GetActor());
		USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
		if (!Mesh)
		{
			return;
		}
		FCollisionQueryParams Params(SCENE_QUERY_STAT(OtherworldShotBody), /*bTraceComplex*/ false);
		FHitResult BodyHit;
		if (Mesh->LineTraceComponent(BodyHit, Start, End, Params))
		{
			bBodyHit = true;
			BodyBone = BodyHit.BoneName;
			BodyPoint = BodyHit.Location;
		}
	}
}

float UOtherworldShotLibrary::RewindSecondsFor(const AActor* Shooter, float MaxRewindSeconds, float ExtraRewindSeconds)
{
	const APawn* Pawn = Cast<APawn>(Shooter);
	const APlayerController* PC = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	// Single player, a listen host's own player, an AI: the present.
	if (!PC || PC->IsLocalController())
	{
		return 0.f;
	}
	const UNetConnection* Connection = PC->GetNetConnection();
	if (!Connection)
	{
		return 0.f;
	}
	float Ping = Connection->AvgLag;
	if (Ping <= 0.f && PC->PlayerState)
	{
		Ping = PC->PlayerState->GetPingInMilliseconds() / 1000.f;
	}
	return FMath::Clamp(Ping + ExtraRewindSeconds, 0.f, FMath::Max(MaxRewindSeconds, 0.f));
}

bool UOtherworldShotLibrary::ShotTrace(AActor* Shooter, FVector Start, FVector End, float MaxRewindSeconds,
	float ExtraRewindSeconds, FHitResult& OutHit, bool& bBodyHit, FName& BodyBone, FVector& BodyPoint)
{
	OutHit = FHitResult(Start, End);
	bBodyHit = false;
	BodyBone = NAME_None;
	BodyPoint = FVector::ZeroVector;
	UWorld* World = Shooter ? Shooter->GetWorld() : nullptr;
	if (!World)
	{
		return false;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(OtherworldShot), /*bTraceComplex*/ false);
	Params.bReturnPhysicalMaterial = true;
	Params.AddIgnoredActor(Shooter);

	UOtherworldHitHistory* History = World->GetSubsystem<UOtherworldHitHistory>();
	const float Rewind = RewindSecondsFor(Shooter, MaxRewindSeconds, ExtraRewindSeconds);
	if (History)
	{
		History->LastRewindSeconds = Rewind;
		History->LastStart = Start;
		History->LastEnd = End;
	}
	if (Rewind <= 0.f || !History || !History->IsRecording())
	{
		// The present: LineTraceSingle, then K2_LineTraceComponent, as the graph had them.
		const bool bHit = World->LineTraceSingleByChannel(OutHit, Start, End, ECC_Visibility, Params);
		if (bHit)
		{
			BodyOfNow(OutHit, Start, End, bBodyHit, BodyBone, BodyPoint);
		}
		return bHit;
	}

	// The past: the world without the characters, then every character where
	// it stood (the history tries the capsules, and the bodies of the one
	// struck); the nearest wins.
	++History->RewoundShots;
	const double At = World->GetTimeSeconds() - Rewind;
	Params.AddIgnoredActors(History->Recorded());
	FHitResult WorldHit(Start, End);
	const bool bWorld = World->LineTraceSingleByChannel(WorldHit, Start, End, ECC_Visibility, Params);
	const float Reach = bWorld ? WorldHit.Distance : static_cast<float>(FVector::Dist(Start, End));

	if (History->TraceRewound(Shooter, At, Start, End, Reach, OutHit, bBodyHit, BodyBone, BodyPoint))
	{
		if (bBodyHit)
		{
			++History->RewoundHits;
		}
		UE_LOG(LogOtherworldShot, Verbose, TEXT("SHOT-REWIND %.0f ms: %s %s"), Rewind * 1000.f,
			*GetNameSafe(OutHit.GetActor()), *BodyBone.ToString());
		return true;
	}
	OutHit = WorldHit;
	return bWorld;
}

bool UOtherworldShotLibrary::IsRecordingHitHistory(const UObject* WorldContextObject)
{
	const UOtherworldHitHistory* History = HistoryOf(WorldContextObject);
	return History && History->IsRecording();
}

int32 UOtherworldShotLibrary::HitHistoryPoses(const AActor* Character)
{
	const UOtherworldHitHistory* History = HistoryOf(Character);
	return History ? History->PoseCount(Character) : 0;
}

int32 UOtherworldShotLibrary::HitHistorySamples(const AActor* Character)
{
	const UOtherworldHitHistory* History = HistoryOf(Character);
	return History ? History->SampleCount(Character) : 0;
}

FVector UOtherworldShotLibrary::HitBoxThen(const AActor* Character, FName Bone, float SecondsAgo)
{
	FVector Location = FVector::ZeroVector;
	const UWorld* World = Character ? Character->GetWorld() : nullptr;
	if (const UOtherworldHitHistory* History = HistoryOf(Character))
	{
		History->BodyThen(Character, Bone, World->GetTimeSeconds() - SecondsAgo, Location);
	}
	return Location;
}

void UOtherworldShotLibrary::LastShotLine(const UObject* WorldContextObject, FVector& Start, FVector& End)
{
	const UOtherworldHitHistory* History = HistoryOf(WorldContextObject);
	Start = History ? History->LastStart : FVector::ZeroVector;
	End = History ? History->LastEnd : FVector::ZeroVector;
}

float UOtherworldShotLibrary::LastRewindSeconds(const UObject* WorldContextObject)
{
	const UOtherworldHitHistory* History = HistoryOf(WorldContextObject);
	return History ? History->LastRewindSeconds : 0.f;
}

int32 UOtherworldShotLibrary::RewoundShots(const UObject* WorldContextObject)
{
	const UOtherworldHitHistory* History = HistoryOf(WorldContextObject);
	return History ? History->RewoundShots : 0;
}

int32 UOtherworldShotLibrary::RewoundHits(const UObject* WorldContextObject)
{
	const UOtherworldHitHistory* History = HistoryOf(WorldContextObject);
	return History ? History->RewoundHits : 0;
}
