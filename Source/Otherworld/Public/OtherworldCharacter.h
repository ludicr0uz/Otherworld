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
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "OtherworldCharacter.generated.h"

UCLASS()
class OTHERWORLD_API AOtherworldCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	explicit AOtherworldCharacter(const FObjectInitializer& ObjectInitializer);

	/** Crouched to the prone height. The server writes it with each move; only simulated copies receive it. */
	UPROPERTY(Transient, ReplicatedUsing = OnRep_Prone, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bProne = false;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void OnRep_IsCrouched() override;

protected:
	UFUNCTION()
	void OnRep_Prone();

private:
	/** On a simulated copy: the capsule and the mesh's offset for bIsCrouched and bProne as they now are. */
	void ApplySimulatedStance();
};
