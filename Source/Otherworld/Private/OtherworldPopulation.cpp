#include "OtherworldPopulation.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "OtherworldSpawnPoint.h"

namespace
{
	using OtherworldSpawnPoint::Lives;

	UOtherworldPopulation* PopulationOf(const UObject* WorldContextObject)
	{
		const UWorld* World = GEngine
			? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull)
			: nullptr;
		return World ? World->GetSubsystem<UOtherworldPopulation>() : nullptr;
	}
}

bool UOtherworldPopulation::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UOtherworldPopulation::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UOtherworldPopulation, STATGROUP_Tickables);
}

bool UOtherworldPopulation::IsBudget() const
{
	const UWorld* World = GetWorld();
	return World && World->GetAuthGameMode() && World->GetNetMode() != NM_Standalone;
}

FOtherworldPopulationEntry& UOtherworldPopulation::EntryOf(TSubclassOf<APawn> Class)
{
	for (FOtherworldPopulationEntry& Entry : Entries)
	{
		if (Entry.Class == Class)
		{
			return Entry;
		}
	}
	FOtherworldPopulationEntry& Entry = Entries.AddDefaulted_GetRef();
	Entry.Class = Class;
	return Entry;
}

void UOtherworldPopulation::Register(APawn* Wanderer, int32 PerPlayer, int32 ServerCap, float Range,
	float SpawnMin, float SpawnMax, float Delay)
{
	if (!IsBudget() || !IsValid(Wanderer))
	{
		return;
	}
	FOtherworldPopulationEntry& Entry = EntryOf(Wanderer->GetClass());
	if (!Entry.bOverridden)
	{
		Entry.PerPlayer = PerPlayer;
		Entry.ServerCap = ServerCap;
		Entry.Range = Range;
		Entry.SpawnMin = SpawnMin;
		Entry.SpawnMax = SpawnMax;
		Entry.Delay = Delay;
	}
	if (!Entry.Living.Contains(Wanderer))
	{
		Entry.Living.Add(Wanderer);
		Entry.Placed += Wanderer->IsNetStartupActor() ? 1 : 0;
	}
}

void UOtherworldPopulation::SetBudget(TSubclassOf<APawn> Class, int32 PerPlayer, int32 ServerCap,
	float Range, float SpawnMin, float SpawnMax, float Delay)
{
	if (!IsBudget() || !Class)
	{
		return;
	}
	FOtherworldPopulationEntry& Entry = EntryOf(Class);
	Entry.PerPlayer = PerPlayer;
	Entry.ServerCap = ServerCap;
	Entry.Range = Range;
	Entry.SpawnMin = SpawnMin;
	Entry.SpawnMax = SpawnMax;
	Entry.Delay = Delay;
	Entry.bOverridden = true;
	Entry.DueAt.Reset();
}

int32 UOtherworldPopulation::Count(TSubclassOf<APawn> Class)
{
	int32 Total = 0;
	for (const FOtherworldPopulationEntry& Entry : Entries)
	{
		if (!Class || (Entry.Class && Entry.Class->IsChildOf(Class)))
		{
			for (const TWeakObjectPtr<APawn>& Pawn : Entry.Living)
			{
				Total += Lives(Pawn.Get()) ? 1 : 0;
			}
		}
	}
	return Total;
}

void UOtherworldPopulation::Tick(float DeltaTime)
{
	SincePass += DeltaTime;
	if (SincePass < PassSeconds)
	{
		return;
	}
	SincePass = 0.f;
	if (IsBudget())
	{
		Pass();
	}
}

void UOtherworldPopulation::Pass()
{
	UWorld* World = GetWorld();
	TArray<APawn*> Players;
	for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
	{
		const APlayerController* Controller = It->Get();
		if (Controller && IsValid(Controller->GetPawn()))
		{
			Players.Add(Controller->GetPawn());
		}
	}
	// With no one in the world nothing is near anyone: the wanderers stand as
	// they are (a server boots before its first player joins) and none is added.
	if (Players.IsEmpty())
	{
		return;
	}
	const double Now = World->GetTimeSeconds();
	for (FOtherworldPopulationEntry& Entry : Entries)
	{
		// The dead leave the count; their bodies are the corpse's own business.
		Entry.Living.RemoveAllSwap([](const TWeakObjectPtr<APawn>& Pawn) { return !Lives(Pawn.Get()); });

		const double RangeSq = FMath::Square(double(Entry.Range));
		for (int32 Index = Entry.Living.Num() - 1; Index >= 0; --Index)
		{
			APawn* Wanderer = Entry.Living[Index].Get();
			const FVector At = Wanderer->GetActorLocation();
			const bool bNear = Players.ContainsByPredicate([&At, RangeSq](const APawn* Player)
			{
				return FVector::DistSquared(Player->GetActorLocation(), At) <= RangeSq;
			});
			if (!bNear)
			{
				Entry.Living.RemoveAtSwap(Index);
				Wanderer->Destroy();
				++Removed;
			}
		}

		for (const APawn* Player : Players)
		{
			TWeakObjectPtr<AController> Key = Player->GetController();
			const FVector At = Player->GetActorLocation();
			int32 Near = 0;
			for (const TWeakObjectPtr<APawn>& Wanderer : Entry.Living)
			{
				Near += FVector::DistSquared(Wanderer->GetActorLocation(), At) <= RangeSq ? 1 : 0;
			}
			if (!Lives(Player) || Near >= Entry.Budget() || Entry.Living.Num() >= Entry.ServerCap)
			{
				Entry.DueAt.Remove(Key);
				continue;
			}
			double* Due = Entry.DueAt.Find(Key);
			if (!Due)
			{
				Entry.DueAt.Add(Key, Now + Entry.Delay);
			}
			else if (Now >= *Due && SpawnFor(Entry, Player, Players))
			{
				Entry.DueAt.Remove(Key);
			}
		}
		for (auto It = Entry.DueAt.CreateIterator(); It; ++It)
		{
			if (!It.Key().IsValid())
			{
				It.RemoveCurrent();
			}
		}
	}
}

bool UOtherworldPopulation::SpawnFor(FOtherworldPopulationEntry& Entry, const APawn* Player,
	const TArray<APawn*>& Players)
{
	UWorld* World = GetWorld();
	FVector Stand;
	double Nearest = 0.0;
	if (!OtherworldSpawnPoint::Find(World, Entry.Class, Player->GetActorLocation(), Entry.SpawnMin,
		Entry.SpawnMax, Players, Stand, Nearest, SeenRefused))
	{
		return false;
	}
	FActorSpawnParameters Spawn;
	Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
	const FRotator Facing(0.0, FMath::FRandRange(0.0, 360.0), 0.0);
	APawn* Made = World->SpawnActor<APawn>(Entry.Class, Stand, Facing, Spawn);
	if (!Made)
	{
		return false;
	}
	// Its controller registers it on possession; one that has none is still counted.
	if (!Entry.Living.Contains(Made))
	{
		Entry.Living.Add(Made);
	}
	++Spawned;
	NearestSpawn = FMath::Min(NearestSpawn, float(Nearest));
	UE_LOG(LogTemp, Log, TEXT("[NPC-POP] %s for %s at %s, %.0f cm from the nearest player; %d alive"),
		*Made->GetName(), *Player->GetName(), *Stand.ToCompactString(), Nearest,
		Entry.Living.Num());
	return true;
}

void UOtherworldPopulationLibrary::RegisterWanderer(const UObject* WorldContextObject, APawn* Wanderer,
	float PerPlayer, float ServerCap, float Range, float SpawnMin, float SpawnMax, float Delay)
{
	if (UOtherworldPopulation* Population = PopulationOf(WorldContextObject))
	{
		Population->Register(Wanderer, FMath::RoundToInt(PerPlayer), FMath::RoundToInt(ServerCap), Range,
			SpawnMin, SpawnMax, Delay);
	}
}

void UOtherworldPopulationLibrary::SetPopulationBudget(const UObject* WorldContextObject,
	TSubclassOf<APawn> Class, int32 PerPlayer, int32 ServerCap, float Range, float SpawnMin,
	float SpawnMax, float Delay)
{
	if (UOtherworldPopulation* Population = PopulationOf(WorldContextObject))
	{
		Population->SetBudget(Class, PerPlayer, ServerCap, Range, SpawnMin, SpawnMax, Delay);
	}
}

bool UOtherworldPopulationLibrary::PopulationIsBudget(const UObject* WorldContextObject)
{
	const UOtherworldPopulation* Population = PopulationOf(WorldContextObject);
	return Population && Population->IsBudget();
}

int32 UOtherworldPopulationLibrary::PopulationCount(const UObject* WorldContextObject, TSubclassOf<APawn> Class)
{
	UOtherworldPopulation* Population = PopulationOf(WorldContextObject);
	return Population ? Population->Count(Class) : 0;
}

int32 UOtherworldPopulationLibrary::PopulationSpawned(const UObject* WorldContextObject)
{
	const UOtherworldPopulation* Population = PopulationOf(WorldContextObject);
	return Population ? Population->Spawned : 0;
}

int32 UOtherworldPopulationLibrary::PopulationRemoved(const UObject* WorldContextObject)
{
	const UOtherworldPopulation* Population = PopulationOf(WorldContextObject);
	return Population ? Population->Removed : 0;
}

float UOtherworldPopulationLibrary::PopulationNearestSpawn(const UObject* WorldContextObject)
{
	const UOtherworldPopulation* Population = PopulationOf(WorldContextObject);
	return Population && Population->Spawned > 0 ? Population->NearestSpawn : 0.f;
}
