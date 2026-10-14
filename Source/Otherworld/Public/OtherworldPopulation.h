// How many wanderers a server keeps, and where (task M29): a budget that
// follows the players. Single player keeps the level's fixed count and the
// dead wanderer's own replacement (Scripts/combat/replacement.py); none of
// this runs there.
//
// On a server, once a second and per creature:
//   - a living wanderer with no player within its Range is removed;
//   - a player with fewer of the creature within Range than the budget, for
//     Delay seconds, is given one more: in the band round them, at least the
//     band's near edge from every player and where none can see it.
// The budget per player is the smaller of the table's cap and the number the
// level placed, so a level's cast is what one player meets; the creature's
// living total never passes the server's cap.
//
// A creature is known once one of it has registered: its controller does, on
// possession (Scripts/npc/population.py), with the numbers of the monster
// tuning table. The nodes are Scripts/uebp/nodes/population.py.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "OtherworldPopulation.generated.h"

class AController;
class APawn;

/** One creature's budget and its living wanderers. */
USTRUCT()
struct FOtherworldPopulationEntry
{
	GENERATED_BODY()

	UPROPERTY()
	TSubclassOf<APawn> Class;

	/** At most this many within Range of one player, and this many alive on the server. */
	int32 PerPlayer = 0;
	int32 ServerCap = 0;

	/** A wanderer further than this from every player is removed; a player's count is taken within it. cm. */
	float Range = 0.f;

	/** Where a new one appears: this far from the player it is for, in cm. */
	float SpawnMin = 0.f;
	float SpawnMax = 0.f;

	/** How long a player stays one short before one more comes, in seconds. */
	float Delay = 0.f;

	/** How many of this creature the level placed. */
	int32 Placed = 0;

	/** Set by SetPopulationBudget: PerPlayer stands as given, whatever the level placed. */
	bool bOverridden = false;

	TArray<TWeakObjectPtr<APawn>> Living;

	/** When each short player's next one is due, in world seconds. */
	TMap<TWeakObjectPtr<AController>, double> DueAt;

	int32 Budget() const { return bOverridden ? PerPlayer : FMath::Min(PerPlayer, Placed); }
};

UCLASS()
class OTHERWORLD_API UOtherworldPopulation : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	/** Seconds between two passes. */
	static constexpr float PassSeconds = 1.f;

	/** True where the count is a budget: a server. False in single player and on a client. */
	bool IsBudget() const;

	void Register(APawn* Wanderer, int32 PerPlayer, int32 ServerCap, float Range, float SpawnMin,
		float SpawnMax, float Delay);

	void SetBudget(TSubclassOf<APawn> Class, int32 PerPlayer, int32 ServerCap, float Range,
		float SpawnMin, float SpawnMax, float Delay);

	/** The living wanderers of a class (and its children). */
	int32 Count(TSubclassOf<APawn> Class);

	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	/** For the probes: wanderers spawned and removed, band points refused because a player could see them. */
	int32 Spawned = 0;
	int32 Removed = 0;
	int32 SeenRefused = 0;
	/** The least distance from any player of any spawn so far, in cm. */
	float NearestSpawn = TNumericLimits<float>::Max();

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	FOtherworldPopulationEntry& EntryOf(TSubclassOf<APawn> Class);
	void Pass();
	bool SpawnFor(FOtherworldPopulationEntry& Entry, const APawn* Player, const TArray<APawn*>& Players);

	UPROPERTY()
	TArray<FOtherworldPopulationEntry> Entries;

	float SincePass = 0.f;
};

UCLASS()
class OTHERWORLD_API UOtherworldPopulationLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * A wanderer has come into the world: its creature's budget (the monster
	 * tuning table's numbers) and itself, to be counted. Does nothing in
	 * single player or on a client.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Population", meta = (WorldContext = "WorldContextObject"))
	static void RegisterWanderer(const UObject* WorldContextObject, APawn* Wanderer, float PerPlayer,
		float ServerCap, float Range, float SpawnMin, float SpawnMax, float Delay);

	/** For the probes and a server's settings: a creature's budget as given, whatever the level placed. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Population", meta = (WorldContext = "WorldContextObject"))
	static void SetPopulationBudget(const UObject* WorldContextObject, TSubclassOf<APawn> Class,
		int32 PerPlayer, int32 ServerCap, float Range, float SpawnMin, float SpawnMax, float Delay);

	/** True on a server, where the count is a budget. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Population", meta = (WorldContext = "WorldContextObject"))
	static bool PopulationIsBudget(const UObject* WorldContextObject);

	/** For the probes: the living, registered wanderers of a class. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Population", meta = (WorldContext = "WorldContextObject"))
	static int32 PopulationCount(const UObject* WorldContextObject, TSubclassOf<APawn> Class);

	UFUNCTION(BlueprintCallable, Category = "Otherworld|Population", meta = (WorldContext = "WorldContextObject"))
	static int32 PopulationSpawned(const UObject* WorldContextObject);

	UFUNCTION(BlueprintCallable, Category = "Otherworld|Population", meta = (WorldContext = "WorldContextObject"))
	static int32 PopulationRemoved(const UObject* WorldContextObject);

	/** For the probes: the least distance from any player of any spawn so far, in cm; 0 before the first. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Population", meta = (WorldContext = "WorldContextObject"))
	static float PopulationNearestSpawn(const UObject* WorldContextObject);
};
