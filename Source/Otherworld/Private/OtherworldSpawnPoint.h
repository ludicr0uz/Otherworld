// Where a new wanderer may appear, shared by the server's population budget
// (OtherworldPopulation.cpp, M29) and the horde level's director
// (OtherworldHordeDirector.cpp): a random bearing in a band round one player,
// projected onto the navmesh and seated on the ground, no nearer any player
// than the band's near edge, and refused where a player could see it.
#pragma once

#include "CoreMinimal.h"

class APawn;
class UWorld;

namespace OtherworldSpawnPoint
{
	/** Bearings tried for one spawn before the caller waits for its next pass. */
	constexpr int32 Attempts = 8;

	/** A pawn that is there and not dead (one with no health component lives). */
	bool Lives(const APawn* Pawn);

	/**
	 * A standing point for a Class in the band [SpawnMin, SpawnMax] cm round
	 * Origin, tried Attempts times. OutNearest is that point's distance from the
	 * nearest of Players, in cm; SeenRefused counts the points refused because
	 * a player could see them.
	 */
	bool Find(UWorld* World, TSubclassOf<APawn> Class, const FVector& Origin, float SpawnMin,
		float SpawnMax, const TArray<APawn*>& Players, FVector& OutStand, double& OutNearest,
		int32& SeenRefused);
}
