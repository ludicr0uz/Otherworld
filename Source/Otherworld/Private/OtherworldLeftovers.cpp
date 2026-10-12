#include "OtherworldLeftovers.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(OtherworldLeftovers)

namespace
{
	UOtherworldLeftovers* LeftoversOf(const UWorld* World)
	{
		return World ? World->GetSubsystem<UOtherworldLeftovers>() : nullptr;
	}

	UOtherworldLeftovers* LeftoversAt(const UObject* WorldContextObject)
	{
		return LeftoversOf(GEngine
			? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull)
			: nullptr);
	}
}

bool UOtherworldLeftovers::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

bool UOtherworldLeftovers::Leave(AActor* Actor, FName Kind, float LifetimeSeconds, int32 Cap)
{
	UWorld* World = GetWorld();
	if (!World || !IsValid(Actor))
	{
		return false;
	}
	// A server's alone: single player keeps what is left until it is taken,
	// and a client's copies are the server's to destroy.
	const ENetMode Mode = World->GetNetMode();
	if (Mode == NM_Standalone || Mode == NM_Client)
	{
		return false;
	}
	// An item lying where the level put it was left by no one, and gets no
	// lifetime: once carried it is a player's to leave. A kind with no lifetime
	// of ours (a body, a fire) is going by its own, and is only counted.
	if (LifetimeSeconds > 0.f && Actor->IsNetStartupActor() && !Carried.Contains(Actor))
	{
		return false;
	}
	const double Now = World->GetTimeSeconds();
	FLeft* Own = List.FindByPredicate([Actor](const FLeft& Left) { return Left.Actor == Actor; });
	if (!Own)
	{
		Own = &List.AddDefaulted_GetRef();
		Own->Actor = Actor;
	}
	Own->Kind = Kind;
	Own->Since = Now;
	Own->Lifetime = LifetimeSeconds;

	// The cap: the oldest of the kind go until it holds. Never the one just
	// noted, which is the newest.
	while (Cap > 0 && Count(Kind) > Cap)
	{
		int32 Oldest = INDEX_NONE;
		for (int32 i = 0; i < List.Num(); ++i)
		{
			const FLeft& Left = List[i];
			if (Left.Kind == Kind && Left.Actor.IsValid() && Left.Actor != Actor
				&& (Oldest == INDEX_NONE || Left.Since < List[Oldest].Since))
			{
				Oldest = i;
			}
		}
		if (Oldest == INDEX_NONE)
		{
			break;
		}
		AActor* Gone = List[Oldest].Actor.Get();
		List.RemoveAtSwap(Oldest);
		Gone->Destroy();
		++Evicted;
	}

	if (!SweepTimer.IsValid())
	{
		World->GetTimerManager().SetTimer(SweepTimer, this, &UOtherworldLeftovers::Sweep, SweepSeconds, true);
	}
	return true;
}

void UOtherworldLeftovers::Take(const AActor* Actor)
{
	List.RemoveAllSwap([Actor](const FLeft& Left) { return Left.Actor == Actor; });
	if (Actor && Actor->IsNetStartupActor())
	{
		Carried.Add(Actor);
	}
}

int32 UOtherworldLeftovers::Count(FName Kind) const
{
	int32 Found = 0;
	for (const FLeft& Left : List)
	{
		Found += Left.Kind == Kind && Left.Actor.IsValid();
	}
	return Found;
}

float UOtherworldLeftovers::LifetimeOf(const AActor* Actor) const
{
	const FLeft* Own = List.FindByPredicate([Actor](const FLeft& Left) { return Left.Actor == Actor; });
	return Own && Own->Actor.IsValid() ? Own->Lifetime : -1.f;
}

void UOtherworldLeftovers::Sweep()
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();
	// What is due, gathered first: a destroy may run a graph that notes or takes.
	TArray<AActor*> Due;
	List.RemoveAllSwap([Now, &Due](const FLeft& Left)
	{
		AActor* Actor = Left.Actor.Get();
		if (!Actor)
		{
			return true;   // gone by its own lifespan, or destroyed by a graph
		}
		if (Left.Lifetime > 0.f && Now - Left.Since >= Left.Lifetime)
		{
			Due.Add(Actor);
			return true;
		}
		return false;
	});
	for (AActor* Actor : Due)
	{
		if (IsValid(Actor))
		{
			Actor->Destroy();
			++Expired;
		}
	}
}

void UOtherworldLeftoverLibrary::LeftInWorld(AActor* Actor, FName Kind, float LifetimeSeconds, int32 Cap)
{
	if (UOtherworldLeftovers* Leftovers = LeftoversOf(Actor ? Actor->GetWorld() : nullptr))
	{
		Leftovers->Leave(Actor, Kind, LifetimeSeconds, Cap);
	}
}

void UOtherworldLeftoverLibrary::TakenFromWorld(AActor* Actor)
{
	if (UOtherworldLeftovers* Leftovers = LeftoversOf(Actor ? Actor->GetWorld() : nullptr))
	{
		Leftovers->Take(Actor);
	}
}

int32 UOtherworldLeftoverLibrary::LeftCount(const UObject* WorldContextObject, FName Kind)
{
	const UOtherworldLeftovers* Leftovers = LeftoversAt(WorldContextObject);
	return Leftovers ? Leftovers->Count(Kind) : 0;
}

float UOtherworldLeftoverLibrary::LeftLifetime(const AActor* Actor)
{
	const UOtherworldLeftovers* Leftovers = LeftoversOf(Actor ? Actor->GetWorld() : nullptr);
	return Leftovers ? Leftovers->LifetimeOf(Actor) : -1.f;
}

int32 UOtherworldLeftoverLibrary::LeftExpired(const UObject* WorldContextObject)
{
	const UOtherworldLeftovers* Leftovers = LeftoversAt(WorldContextObject);
	return Leftovers ? Leftovers->Expired : 0;
}

int32 UOtherworldLeftoverLibrary::LeftEvicted(const UObject* WorldContextObject)
{
	const UOtherworldLeftovers* Leftovers = LeftoversAt(WorldContextObject);
	return Leftovers ? Leftovers->Evicted : 0;
}
