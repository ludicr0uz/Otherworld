#include "OtherworldCharacter.h"

#include "OtherworldCharacterMovement.h"
#include "Components/CapsuleComponent.h"
#include "Net/UnrealNetwork.h"

AOtherworldCharacter::AOtherworldCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UOtherworldCharacterMovement>(ACharacter::CharacterMovementComponentName))
{
}

void AOtherworldCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION(AOtherworldCharacter, bProne, COND_SimulatedOnly);
}

void AOtherworldCharacter::OnRep_IsCrouched()
{
	if (Cast<UOtherworldCharacterMovement>(GetCharacterMovement()))
	{
		ApplySimulatedStance();
		return;
	}
	Super::OnRep_IsCrouched();
}

void AOtherworldCharacter::OnRep_Prone()
{
	ApplySimulatedStance();
}

void AOtherworldCharacter::ApplySimulatedStance()
{
	UOtherworldCharacterMovement* Movement = Cast<UOtherworldCharacterMovement>(GetCharacterMovement());
	if (!Movement || !GetCapsuleComponent())
	{
		return;
	}
	Movement->bWantsToCrouch = bIsCrouched;
	Movement->bWantsProne = bProne;

	// The two flags arrive in either order, and often together, so this is
	// written to be run twice: it acts only on a capsule that is not yet the
	// stance's. (The engine's own notify crouches again whatever the capsule
	// is, and a second crouch to the height it already has puts the mesh back
	// at its standing offset.) A proxy's capsule is a hair under its nominal
	// size (p.NetProxyShrinkHalfHeight), hence the slack.
	const float Slack = 1.f;
	const float Standing = GetDefault<ACharacter>(GetClass())->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
	const float Wanted = !bIsCrouched ? Standing : (bProne ? Movement->ProneHalfHeight : Movement->CrouchHalfHeight);
	const float Now = GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
	if (!FMath::IsNearlyEqual(Now, Wanted, Slack))
	{
		// Between the two low stances it stands first: the engine sizes the
		// capsule, and offsets the mesh, only from the standing one.
		if (!FMath::IsNearlyEqual(Now, Standing, Slack))
		{
			Movement->UnCrouch(true);
		}
		if (bIsCrouched)
		{
			Movement->SetCrouchedHalfHeight(Wanted);
			Movement->Crouch(true);
		}
	}
	Movement->bNetworkUpdateReceived = true;
}
