#include "OtherworldLoadLibrary.h"

#include "Engine/Engine.h"
#include "Engine/NetConnection.h"
#include "Engine/NetDriver.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "HAL/PlatformTime.h"
#include "Misc/CoreDelegates.h"
#include "OtherworldHitHistory.h"

namespace
{
	/** The sampler: one set of delegates, alive between Start and Stop. */
	struct FOtherworldFrameTiming
	{
		FDelegateHandle BeginFrame, TickStart, TickEnd;
		double LastBeginFrame = 0.0;
		double WorldTickBegan = 0.0;
		TArray<float> FrameMs;
		TArray<float> WorldTickMs;

		bool IsRunning() const { return BeginFrame.IsValid(); }

		void Start()
		{
			Stop();
			BeginFrame = FCoreDelegates::OnBeginFrame.AddLambda([this]()
			{
				const double Now = FPlatformTime::Seconds();
				if (LastBeginFrame > 0.0)
				{
					FrameMs.Add(static_cast<float>((Now - LastBeginFrame) * 1000.0));
				}
				LastBeginFrame = Now;
			});
			TickStart = FWorldDelegates::OnWorldTickStart.AddLambda(
				[this](UWorld* World, ELevelTick, float)
			{
				if (World && World->IsGameWorld())
				{
					WorldTickBegan = FPlatformTime::Seconds();
				}
			});
			TickEnd = FWorldDelegates::OnWorldTickEnd.AddLambda(
				[this](UWorld* World, ELevelTick, float)
			{
				if (World && World->IsGameWorld() && WorldTickBegan > 0.0)
				{
					WorldTickMs.Add(static_cast<float>(
						(FPlatformTime::Seconds() - WorldTickBegan) * 1000.0));
					WorldTickBegan = 0.0;
				}
			});
		}

		void Stop()
		{
			if (BeginFrame.IsValid())
			{
				FCoreDelegates::OnBeginFrame.Remove(BeginFrame);
				FWorldDelegates::OnWorldTickStart.Remove(TickStart);
				FWorldDelegates::OnWorldTickEnd.Remove(TickEnd);
			}
			BeginFrame.Reset();
			TickStart.Reset();
			TickEnd.Reset();
			LastBeginFrame = WorldTickBegan = 0.0;
			FrameMs.Reset();
			WorldTickMs.Reset();
		}
	};

	FOtherworldFrameTiming GTiming;

	UWorld* WorldOf(const UObject* WorldContextObject)
	{
		return GEngine ? GEngine->GetWorldFromContextObject(
			WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	}

	FOtherworldConnectionStats StatsOf(const UNetConnection* Connection)
	{
		FOtherworldConnectionStats Stats;
		const APlayerState* State = Connection->PlayerController
			? Connection->PlayerController->GetPlayerState<APlayerState>() : nullptr;
		Stats.Name = const_cast<UNetConnection*>(Connection)->LowLevelGetRemoteAddress(true);
		Stats.Player = State ? State->GetPlayerName() : FString();
		Stats.InBytes = Connection->InTotalBytes;
		Stats.OutBytes = Connection->OutTotalBytes;
		Stats.InPackets = Connection->InTotalPackets;
		Stats.OutPackets = Connection->OutTotalPackets;
		Stats.ActorChannels = Connection->ActorChannelsNum();
		Stats.AvgLagMs = Connection->AvgLag * 1000.f;
		return Stats;
	}
}

TArray<FOtherworldConnectionStats> UOtherworldLoadLibrary::ConnectionStats(const UObject* WorldContextObject)
{
	TArray<FOtherworldConnectionStats> Out;
	const UWorld* World = WorldOf(WorldContextObject);
	const UNetDriver* Driver = World ? World->GetNetDriver() : nullptr;
	if (!Driver)
	{
		return Out;
	}
	for (const UNetConnection* Connection : Driver->ClientConnections)
	{
		if (Connection)
		{
			Out.Add(StatsOf(Connection));
		}
	}
	if (Driver->ServerConnection)
	{
		Out.Add(StatsOf(Driver->ServerConnection));
	}
	return Out;
}

void UOtherworldLoadLibrary::StartFrameTiming()
{
	GTiming.Start();
}

TArray<float> UOtherworldLoadLibrary::FrameTimesMs()
{
	return GTiming.FrameMs;
}

TArray<float> UOtherworldLoadLibrary::WorldTickTimesMs()
{
	return GTiming.WorldTickMs;
}

void UOtherworldLoadLibrary::StopFrameTiming()
{
	GTiming.Stop();
}

int32 UOtherworldLoadLibrary::HitHistoryCharacters(const UObject* WorldContextObject)
{
	const UWorld* World = WorldOf(WorldContextObject);
	const UOtherworldHitHistory* History = World ? World->GetSubsystem<UOtherworldHitHistory>() : nullptr;
	if (!History)
	{
		return 0;
	}
	TArray<AActor*> Characters;
	History->CharactersRecorded(Characters);
	return Characters.Num();
}

int32 UOtherworldLoadLibrary::HitHistoryTotalSamples(const UObject* WorldContextObject)
{
	const UWorld* World = WorldOf(WorldContextObject);
	const UOtherworldHitHistory* History = World ? World->GetSubsystem<UOtherworldHitHistory>() : nullptr;
	if (!History)
	{
		return 0;
	}
	TArray<AActor*> Characters;
	History->CharactersRecorded(Characters);
	int32 Total = 0;
	for (const AActor* Character : Characters)
	{
		Total += History->SampleCount(Character);
	}
	return Total;
}

AActor* UOtherworldLoadLibrary::SpawnActorAt(const UObject* WorldContextObject, TSubclassOf<AActor> ActorClass, const FTransform& Transform)
{
	UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	if (!World || !ActorClass || World->GetNetMode() == NM_Client)
	{
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	return World->SpawnActor<AActor>(ActorClass, Transform, Params);
}
