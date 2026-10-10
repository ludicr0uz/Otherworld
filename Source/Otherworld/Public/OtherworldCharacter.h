// The player character's native parent. It exists for one thing: a Character's
// movement component is a native subobject, so only a native class can choose
// its class. BP_ThirdPersonCharacter is reparented onto this by
// Scripts/combat/player_move.py; everything else about the player stays in
// the Blueprint the builders author.
//
// And for what another player's copy of the character (a simulated proxy)
// needs to stand as the server has it: the engine replicates its crouch to
// those copies and nothing of prone, which is our own flag on the owning
// client's moves. bProne is that flag, sent to the simulated copies alone,
// and both notifies size the capsule to the stance the two flags make.
//
// And for the keys that are Enhanced Input actions rather than polled (I1:
// the fire key alone). The mapping context and the action are assets
// Scripts/combat/input_assets.py authors and names on the class defaults;
// the local player's copy adds the context and hands the action's press and
// release to the weapon component's native base, whose graph takes it from
// there. The settings page rebinds by SetFireKey: the context's one key for
// the action.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputCoreTypes.h"
#include "OtherworldCharacter.generated.h"

class UInputAction;
class UInputMappingContext;
class UEnhancedInputLocalPlayerSubsystem;

UCLASS()
class OTHERWORLD_API AOtherworldCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	explicit AOtherworldCharacter(const FObjectInitializer& ObjectInitializer);

	/** Crouched to the prone height. The server writes it with each move; only simulated copies receive it. */
	UPROPERTY(Transient, ReplicatedUsing = OnRep_Prone, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bProne = false;

	/** In a slide (G5). The server writes it with each move; only simulated copies receive it, to pose by. */
	UPROPERTY(Transient, Replicated, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bSliding = false;

	/** The game's own mapping context, added for the local player (input_assets.py writes it). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Otherworld|Input")
	TObjectPtr<UInputMappingContext> InputContext;

	/** The trigger: its press and release go to the weapon component (FireInput). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Otherworld|Input")
	TObjectPtr<UInputAction> FireAction;

	/**
	 * Rebinds the trigger: Key becomes the context's one key for FireAction.
	 * Nothing when it already is, so the settings may hand it over every frame.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Input")
	void SetFireKey(FKey Key);

	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void OnRep_IsCrouched() override;

protected:
	UFUNCTION()
	void OnRep_Prone();

private:
	void FireStarted();
	void FireStopped();

	/** The local player's Enhanced Input subsystem, or null on a copy that is not a local player's. */
	UEnhancedInputLocalPlayerSubsystem* InputSubsystem() const;

	/** On a simulated copy: the capsule and the mesh's offset for bIsCrouched and bProne as they now are. */
	void ApplySimulatedStance();
};
