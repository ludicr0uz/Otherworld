#include "OtherworldHordeDirector.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "OtherworldHealthComponent.h"
#include "OtherworldSpawnPoint.h"
#include "UObject/UnrealType.h"

namespace
{
	/** Seconds between two passes. */
	constexpr float HordePassSeconds = 1.f;
}

AOtherworldHordeDirector::AOtherworldHordeDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = HordePassSeconds;
	SetHidden(true);
	bReplicates = false;
}

int32 AOtherworldHordeDirector::LevelAt(float Seconds) const
{
	const int32 Steps = StepSeconds > 0.f ? FMath::FloorToInt32(FMath::Max(Seconds, 0.f) / StepSeconds) : 0;
	return FMath::Clamp(1 + Steps, 1, FMath::Max(MaxLevel, 1));
}

int32 AOtherworldHordeDirector::TotalAt(int32 AtLevel) const
{
	return FMath::Max(FirstCount + PerLevel * (AtLevel - 1), 0);
}

int32 AOtherworldHordeDirector::WendigosAt(int32 AtLevel) const
{
	const int32 Wendigos = WendigoEveryLevels > 0 ? AtLevel / WendigoEveryLevels : 0;
	return FMath::Clamp(Wendigos, 0, TotalAt(AtLevel));
}

int32 AOtherworldHordeDirector::ZombiesAt(int32 AtLevel) const
{
	return TotalAt(AtLevel) - WendigosAt(AtLevel);
}

float AOtherworldHordeDirector::PlaySeconds() const
{
	const UWorld* World = GetWorld();
	return World ? float(World->GetTimeSeconds() - StartedAt) : 0.f;
}

void AOtherworldHordeDirector::BeginPlay()
{
	Super::BeginPlay();
	StartedAt = GetWorld()->GetTimeSeconds();
}

void AOtherworldHordeDirector::Restart()
{
	StartedAt = GetWorld()->GetTimeSeconds();
	Level = 0;
	ZombieDueAt = WendigoDueAt = -1.0;
	bFirstPass = true;
}

void AOtherworldHordeDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	// A client's copy of the level has one too; the count is the authority's.
	if (GetWorld()->GetNetMode() != NM_Client)
	{
		Pass();
	}
}

void AOtherworldHordeDirector::Living(TSubclassOf<APawn> Class, TArray<APawn*>& Out) const
{
	Out.Reset();
	if (!Class)
	{
		return;
	}
	for (TActorIterator<APawn> It(GetWorld(), Class); It; ++It)
	{
		if (OtherworldSpawnPoint::Lives(*It))
		{
			Out.Add(*It);
		}
	}
}

int32 AOtherworldHordeDirector::LivingOf(TSubclassOf<APawn> Class) const
{
	TArray<APawn*> Found;
	Living(Class, Found);
	return Found.Num();
}

void AOtherworldHordeDirector::ReplacementOff(APawn* Wanderer)
{
	UActorComponent* Health = Wanderer->FindComponentByClass<UOtherworldHealthComponent>();
	if (!Health)
	{
		return;
	}
	FObjectPropertyBase* Prop = FindFProperty<FObjectPropertyBase>(Health->GetClass(), ReplacementVar);
	if (!Prop)
	{
		return;
	}
	if (Prop->GetObjectPropertyValue_InContainer(Health))
	{
		Prop->SetObjectPropertyValue_InContainer(Health, nullptr);
		++ReplacementsOff;
	}
}

void AOtherworldHordeDirector::Pass()
{
	UWorld* World = GetWorld();
	TArray<APawn*> Players;
	for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
	{
		const APlayerController* Controller = It->Get();
		if (Controller && OtherworldSpawnPoint::Lives(Controller->GetPawn()))
		{
			Players.Add(Controller->GetPawn());
		}
	}
	// No one alive to meet them: the horde stands as it is.
	if (Players.IsEmpty())
	{
		return;
	}
	const int32 Now = LevelAt(PlaySeconds());
	if (Now != Level)
	{
		Level = Now;
		UE_LOG(LogTemp, Log, TEXT("[HORDE] level %d: %d zombies, %d wendigos"), Level, ZombiesAt(Level),
			WendigosAt(Level));
	}
	Hold(ZombieClass, ZombiesAt(Level), ZombieDueAt, Players);
	Hold(WendigoClass, WendigosAt(Level), WendigoDueAt, Players);
	bFirstPass = false;
}

void AOtherworldHordeDirector::Hold(TSubclassOf<APawn> Class, int32 Want, double& DueAt,
	const TArray<APawn*>& Players)
{
	if (!Class)
	{
		return;
	}
	UWorld* World = GetWorld();
	TArray<APawn*> Found;
	Living(Class, Found);
	for (APawn* Wanderer : Found)
	{
		ReplacementOff(Wanderer);
	}

	auto FromPlayers = [&Players](const APawn* Wanderer)
	{
		double Least = TNumericLimits<double>::Max();
		for (const APawn* Player : Players)
		{
			Least = FMath::Min(Least, FVector::DistSquared(Player->GetActorLocation(), Wanderer->GetActorLocation()));
		}
		return Least;
	};
	if (Found.Num() > Want)
	{
		Found.Sort([&FromPlayers](const APawn& A, const APawn& B) { return FromPlayers(&A) > FromPlayers(&B); });
		for (int32 Index = 0; Index < Found.Num() - Want; ++Index)
		{
			Found[Index]->Destroy();
			++Removed;
		}
		UE_LOG(LogTemp, Log, TEXT("[HORDE] removed %d of %s; %d alive"), Found.Num() - Want,
			*Class->GetName(), Want);
		DueAt = -1.0;
		return;
	}
	if (Found.Num() == Want)
	{
		DueAt = -1.0;
		return;
	}
	const double Now = World->GetTimeSeconds();
	if (DueAt < 0.0)
	{
		DueAt = bFirstPass ? Now : Now + Delay;
	}
	if (Now < DueAt)
	{
		return;
	}
	const APawn* For = Players[FMath::RandHelper(Players.Num())];
	FVector Stand;
	double Nearest = 0.0;
	int32 SeenRefused = 0;
	if (!OtherworldSpawnPoint::Find(World, Class, For->GetActorLocation(), SpawnMin, SpawnMax, Players,
		Stand, Nearest, SeenRefused))
	{
		return;
	}
	FActorSpawnParameters Spawn;
	Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
	const FRotator Facing(0.0, FMath::FRandRange(0.0, 360.0), 0.0);
	APawn* Made = World->SpawnActor<APawn>(Class, Stand, Facing, Spawn);
	if (!Made)
	{
		return;
	}
	// Its BeginPlay has run (the world has begun play), and named itself as its own replacement.
	ReplacementOff(Made);
	++Spawned;
	UE_LOG(LogTemp, Log, TEXT("[HORDE] %s at %s, %.0f cm from the nearest player; level %d, %d of %d"),
		*Made->GetName(), *Stand.ToCompactString(), Nearest, Level, Found.Num() + 1, Want);
}
