// What players leave in the world, and how a server keeps it from piling up
// (task M31): an item set down, thrown or lodged, wood cut from a tree, a
// corpse, a campfire. A server runs for days, so each kind has a lifetime
// and a cap on how many exist; the oldest of a kind makes room for a new
// one.
//
// The server's alone, and a dedicated or listen server's only: in single
// player nothing is noted and nothing is cleaned up, where a session ends
// long before it matters (serversupportsysdesign.md 4.8, the mode table). An
// item lying where the level put it gets no lifetime either: it is the
// level's, left by no one, until someone has carried it.
//
// The numbers are not here: each call brings its kind's lifetime and cap,
// pin literals from Scripts/net/leftover_consts.py. The nodes are
// Scripts/uebp/nodes/leftover.py, authored by Scripts/net/leftover.py.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "OtherworldLeftovers.generated.h"

/** The list itself, one per game world. Empty for ever in single player and on a client. */
UCLASS()
class OTHERWORLD_API UOtherworldLeftovers : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** How often the lifetimes are looked at, in seconds. */
	static constexpr float SweepSeconds = 1.f;

	/**
	 * Actor is left in the world from now, one of Kind. It is destroyed
	 * LifetimeSeconds on (0: it has a lifespan of its own, and only the cap
	 * is kept), and while more than Cap of the kind are left (0: no cap) the
	 * oldest is destroyed. Noting an actor again starts its lifetime again.
	 * False when it was not noted: not a server, or a level's item never carried.
	 */
	bool Leave(AActor* Actor, FName Kind, float LifetimeSeconds, int32 Cap);

	/** Actor is no longer left (taken into an inventory). */
	void Take(const AActor* Actor);

	/** How many of Kind are left now. */
	int32 Count(FName Kind) const;

	/** The lifetime Actor was noted with, or -1 when it is not noted. */
	float LifetimeOf(const AActor* Actor) const;

	/** Actors destroyed at the end of their lifetime, and to keep a cap, for the probes. */
	int32 Expired = 0;
	int32 Evicted = 0;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	struct FLeft
	{
		TWeakObjectPtr<AActor> Actor;
		FName Kind;
		double Since = 0.0;
		float Lifetime = 0.f;
	};

	void Sweep();

	TArray<FLeft> List;
	/** The level's own actors that have been carried since: set down again, they are left like any other. */
	TSet<TWeakObjectPtr<const AActor>> Carried;
	FTimerHandle SweepTimer;
};

UCLASS()
class OTHERWORLD_API UOtherworldLeftoverLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * UOtherworldLeftovers::Leave on Actor's world. Does nothing in single
	 * player, on a client, or for a level's item never carried. Actor is the graph's own
	 * actor when the pin is left empty.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Leftovers", meta = (DefaultToSelf = "Actor"))
	static void LeftInWorld(AActor* Actor, FName Kind, float LifetimeSeconds, int32 Cap);

	/** UOtherworldLeftovers::Take on Actor's world. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Leftovers", meta = (DefaultToSelf = "Actor"))
	static void TakenFromWorld(AActor* Actor);

	/** For the probes: how many of Kind are left in this world. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Leftovers", meta = (WorldContext = "WorldContextObject"))
	static int32 LeftCount(const UObject* WorldContextObject, FName Kind);

	/** For the probes: the lifetime Actor was noted with, or -1 when it is not noted. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Leftovers")
	static float LeftLifetime(const AActor* Actor);

	/** For the probes: actors destroyed at the end of their lifetime in this world, and to keep a cap. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Leftovers", meta = (WorldContext = "WorldContextObject"))
	static int32 LeftExpired(const UObject* WorldContextObject);

	UFUNCTION(BlueprintCallable, Category = "Otherworld|Leftovers", meta = (WorldContext = "WorldContextObject"))
	static int32 LeftEvicted(const UObject* WorldContextObject);
};
