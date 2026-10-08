// What a graph asks about an actor's place on the network and Python cannot
// reach otherwise (task A2): whether it was placed in the level. The engine
// tells a late joiner of a destroyed level actor, so the take destroys such
// an item (combat/weapon_component/pickup.py) where it would hide a spawned
// one.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldNetLibrary.generated.h"

UCLASS()
class OTHERWORLD_API UOtherworldNetLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Was this actor placed in the level (a net startup actor, loaded by
	 * every machine), rather than spawned? False for nothing.
	 */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Net")
	static bool IsLevelActor(const AActor* Actor);
};
