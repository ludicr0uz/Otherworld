// What a graph asks about an actor's place on the network and Python cannot
// reach otherwise (task A2): whether it was placed in the level. The engine
// tells a late joiner of a destroyed level actor, so the take destroys such
// an item (combat/weapon_component/pickup.py) where it would hide a spawned
// one.
//
// And what a probe needs to play a client that does not keep the rules
// (task A5): SendServerEvent, a Blueprint Server event sent as the wire
// carries it, with whatever arguments and as often as the caller likes.
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

	/**
	 * For the probes: send a Blueprint Server event of Target (an actor or a
	 * component this machine owns) to the server, each parameter from its
	 * text ("3", "(X=1,Y=2,Z=3)"). Python's call_method runs such an event
	 * where it is called: only the Blueprint VM routes one, and this does
	 * what the VM does. False, and nothing sent, unless Event is a Server
	 * event, this machine is not the authority, every argument reads and a
	 * net driver took it.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool SendServerEvent(UObject* Target, FName Event, const TArray<FString>& Arguments);
};
