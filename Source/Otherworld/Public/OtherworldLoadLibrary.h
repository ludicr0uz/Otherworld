// What a load test reads off a running server (task A1): each connection's
// traffic and channels, the frame and world-tick times, and the hit history's
// size. UNetConnection's counters are plain members, not properties, so
// Python (Scripts/probes/probe_net_load.py) cannot read them without this.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldLoadLibrary.generated.h"

/** One connection's totals since it opened. */
USTRUCT(BlueprintType)
struct FOtherworldConnectionStats
{
	GENERATED_BODY()

	/** The remote address with its port: unique per connection on one machine. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	FString Name;

	/** The player's name, empty for a connection with no PlayerState yet. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	FString Player;

	/** UNetConnection::InTotalBytes / OutTotalBytes: every byte in and out. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	int32 InBytes = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	int32 OutBytes = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	int32 InPackets = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	int32 OutPackets = 0;

	/** Open actor channels: the actors replicated to this connection just now. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	int32 ActorChannels = 0;

	/** UNetConnection::AvgLag, in milliseconds. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Load")
	float AvgLagMs = 0.f;
};

UCLASS()
class OTHERWORLD_API UOtherworldLoadLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Every connection of this world's net driver: on a server its clients,
	 * on a client the one to the server. Empty with no net driver.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Load", meta = (WorldContext = "WorldContextObject"))
	static TArray<FOtherworldConnectionStats> ConnectionStats(const UObject* WorldContextObject);

	/**
	 * Start (or restart) sampling every frame: the wall time from one
	 * FCoreDelegates::OnBeginFrame to the next, and the game world's
	 * UWorld::Tick (FWorldDelegates::OnWorldTickStart to OnWorldTickEnd). On a
	 * dedicated server the frame holds the tick-rate sleep and the world tick
	 * does not, so the world tick is the work and the frame the rate.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Load")
	static void StartFrameTiming();

	/** The frame times sampled since the start, in milliseconds, oldest first. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Load")
	static TArray<float> FrameTimesMs();

	/** The world-tick times sampled since the start, in milliseconds, oldest first. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Load")
	static TArray<float> WorldTickTimesMs();

	/** Stop sampling and forget the samples. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Load")
	static void StopFrameTiming();

	/** How many characters the hit history (OtherworldHitHistory.h) holds samples of. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Load", meta = (WorldContext = "WorldContextObject"))
	static int32 HitHistoryCharacters(const UObject* WorldContextObject);

	/** Every character's samples in the hit history, added up. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Load", meta = (WorldContext = "WorldContextObject"))
	static int32 HitHistoryTotalSamples(const UObject* WorldContextObject);
};
