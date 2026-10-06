// What the Blueprint graphs (and the probes, from Python) say to and read off
// the player's movement component. Every function takes the character's actor
// and does nothing, or answers the default, for one without the component, so
// a graph needs no cast.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldMovementLibrary.generated.h"

class AActor;
class UOtherworldCharacterMovement;

UCLASS()
class OTHERWORLD_API UOtherworldMovementLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** The component, or null: for Python. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Movement")
	static UOtherworldCharacterMovement* GetOtherworldMovement(const AActor* Character);

	// --- the wants: called on the machine whose player controls the character.

	/** The sprint key, held or not. Whether that is a sprint the movement decides. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Movement")
	static void SetSprintHeld(AActor* Character, bool bHeld);

	/** 0 stand, 1 crouch, 2 prone. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Movement")
	static void SetStance(AActor* Character, int32 Stance);

	UFUNCTION(BlueprintCallable, Category = "Otherworld|Movement")
	static void SetAimWalk(AActor* Character, bool bAiming);

	// --- the state, for the graphs that show or gate on it.

	UFUNCTION(BlueprintPure, Category = "Otherworld|Movement")
	static float GetStamina(const AActor* Character);

	UFUNCTION(BlueprintPure, Category = "Otherworld|Movement")
	static bool IsSprinting(const AActor* Character);

	UFUNCTION(BlueprintPure, Category = "Otherworld|Movement")
	static bool IsSprintSpent(const AActor* Character);

	UFUNCTION(BlueprintPure, Category = "Otherworld|Movement")
	static bool IsSprintAhead(const AActor* Character);

	// --- the server's alone: each does nothing on a machine without authority.

	UFUNCTION(BlueprintCallable, Category = "Otherworld|Movement")
	static void SetStamina(AActor* Character, float NewStamina);

	/** Take Amount off the stamina, floored at zero (a blocked blow). */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Movement")
	static void SpendStamina(AActor* Character, float Amount);

	/** The PLAYER SETTINGS tab's numbers, cm/s and stamina a second. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Movement")
	static void SetPace(AActor* Character, float JogSpeed, float SprintSpeed, float StaminaDrainPerSecond, float StaminaRegenPerSecond);
};
