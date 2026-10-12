#include "OtherworldNoise.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"

namespace
{
	UOtherworldNoiseList* ListOf(const UObject* WorldContextObject)
	{
		const UWorld* World = GEngine
			? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull)
			: nullptr;
		return World ? World->GetSubsystem<UOtherworldNoiseList>() : nullptr;
	}
}

bool UOtherworldNoiseList::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

bool UOtherworldNoiseList::Make(AActor* Maker, const FVector& Location, float Reach,
	const FVector& Direction, float ConeReach, float ConeCos, float HoldSeconds)
{
	const UWorld* World = GetWorld();
	// The server's alone: a client has no GameMode, and nothing there listens.
	if (!World || !World->GetAuthGameMode())
	{
		return false;
	}
	const float Now = World->GetTimeSeconds();
	// What no listener can hear any more goes, so the list is the recent noises.
	List.RemoveAllSwap([Now, HoldSeconds](const FOtherworldNoise& Noise)
	{
		return Now - Noise.Time > HoldSeconds;
	});

	FOtherworldNoise New;
	New.Maker = Maker;
	New.Location = Location;
	New.Reach = Reach;
	New.Direction = Direction;
	New.ConeReach = ConeReach;
	New.ConeCos = ConeCos;
	New.Time = Now;

	FOtherworldNoise* Own = List.FindByPredicate([Maker](const FOtherworldNoise& Noise)
	{
		return Noise.Maker == Maker;
	});
	if (Own)
	{
		const bool bStale = Now - Own->Time >= HoldSeconds;
		if (!bStale && New.Loudness() < Own->Loudness())
		{
			++Refused;
			return false;
		}
		*Own = New;
	}
	else
	{
		if (List.Num() >= MaxNoises)
		{
			// Never in play (one a maker): the oldest makes room.
			int32 Oldest = 0;
			for (int32 i = 1; i < List.Num(); ++i)
			{
				if (List[i].Time < List[Oldest].Time)
				{
					Oldest = i;
				}
			}
			List.RemoveAtSwap(Oldest);
		}
		List.Add(New);
	}
	++Made;
	return true;
}

const FOtherworldNoise* UOtherworldNoiseList::Hear(const FVector& Listener, float HearingScale,
	float HoldSeconds) const
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return nullptr;
	}
	const float Now = World->GetTimeSeconds();
	const FOtherworldNoise* Best = nullptr;
	double BestGap = 0.0;
	for (const FOtherworldNoise& Noise : List)
	{
		// A wanderer that strolls into the reach of an old shot does not hear it now.
		if (Now - Noise.Time > HoldSeconds)
		{
			continue;
		}
		const FVector Away = Listener - Noise.Location;
		const double Gap = Away.Size();
		const bool bAllRound = Gap <= Noise.Reach * HearingScale;
		const bool bInCone = Gap <= Noise.ConeReach * HearingScale
			&& FVector::DotProduct(Noise.Direction, Away.GetSafeNormal()) >= Noise.ConeCos;
		if ((bAllRound || bInCone) && (!Best || Gap < BestGap))
		{
			Best = &Noise;
			BestGap = Gap;
		}
	}
	return Best;
}

void UOtherworldNoiseLibrary::MakeNoise(const UObject* WorldContextObject, AActor* Maker,
	FVector Location, float Reach, FVector Direction, float ConeReach, float ConeCos, float HoldSeconds)
{
	if (UOtherworldNoiseList* List = ListOf(WorldContextObject))
	{
		List->Make(Maker, Location, Reach, Direction, ConeReach, ConeCos, HoldSeconds);
	}
}

bool UOtherworldNoiseLibrary::HearNoise(const UObject* WorldContextObject, FVector Listener,
	float HearingScale, float HoldSeconds, APawn*& Maker, FVector& Location)
{
	Maker = nullptr;
	Location = FVector::ZeroVector;
	const UOtherworldNoiseList* List = ListOf(WorldContextObject);
	const FOtherworldNoise* Heard = List ? List->Hear(Listener, HearingScale, HoldSeconds) : nullptr;
	if (!Heard)
	{
		return false;
	}
	Maker = Cast<APawn>(Heard->Maker.Get());
	Location = Heard->Location;
	return true;
}

TArray<FOtherworldNoise> UOtherworldNoiseLibrary::NoisesHeld(const UObject* WorldContextObject)
{
	const UOtherworldNoiseList* List = ListOf(WorldContextObject);
	return List ? List->Noises() : TArray<FOtherworldNoise>();
}

int32 UOtherworldNoiseLibrary::NoisesMade(const UObject* WorldContextObject)
{
	const UOtherworldNoiseList* List = ListOf(WorldContextObject);
	return List ? List->Made : 0;
}

int32 UOtherworldNoiseLibrary::NoisesRefused(const UObject* WorldContextObject)
{
	const UOtherworldNoiseList* List = ListOf(WorldContextObject);
	return List ? List->Refused : 0;
}
