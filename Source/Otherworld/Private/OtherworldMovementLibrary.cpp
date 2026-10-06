#include "OtherworldMovementLibrary.h"

#include "GameFramework/Character.h"
#include "OtherworldCharacterMovement.h"

namespace
{
	UOtherworldCharacterMovement* MovementOf(const AActor* Actor)
	{
		const ACharacter* Character = Cast<ACharacter>(Actor);
		return Character ? Cast<UOtherworldCharacterMovement>(Character->GetCharacterMovement()) : nullptr;
	}

	/** The component, on the machine that decides: the server, or single player. */
	UOtherworldCharacterMovement* AuthorityMovementOf(const AActor* Actor)
	{
		return (Actor && Actor->HasAuthority()) ? MovementOf(Actor) : nullptr;
	}
}

UOtherworldCharacterMovement* UOtherworldMovementLibrary::GetOtherworldMovement(const AActor* Character)
{
	return MovementOf(Character);
}

void UOtherworldMovementLibrary::SetSprintHeld(AActor* Character, bool bHeld)
{
	if (UOtherworldCharacterMovement* Movement = MovementOf(Character))
	{
		Movement->bWantsToSprint = bHeld;
	}
}

void UOtherworldMovementLibrary::SetStance(AActor* Character, int32 Stance)
{
	UOtherworldCharacterMovement* Movement = MovementOf(Character);
	if (!Movement)
	{
		return;
	}
	// Prone is the engine's crouch to a lower height, so the engine's own
	// predicted flag carries the crouch and ours only says how low.
	Movement->bWantsProne = Stance == 2;
	ACharacter* Body = CastChecked<ACharacter>(Character);
	if (Stance == 0)
	{
		Body->UnCrouch();
	}
	else
	{
		Body->Crouch();
	}
}

int32 UOtherworldMovementLibrary::GetStance(const AActor* Character)
{
	const UOtherworldCharacterMovement* Movement = MovementOf(Character);
	if (!Movement || !Movement->IsCrouching())
	{
		return 0;
	}
	// On a simulated copy bWantsProne is the character's replicated bProne.
	return Movement->bWantsProne ? 2 : 1;
}

void UOtherworldMovementLibrary::SetAimWalk(AActor* Character, bool bAiming)
{
	if (UOtherworldCharacterMovement* Movement = MovementOf(Character))
	{
		Movement->bWantsAimWalk = bAiming;
	}
}

float UOtherworldMovementLibrary::GetStamina(const AActor* Character)
{
	const UOtherworldCharacterMovement* Movement = MovementOf(Character);
	return Movement ? Movement->Stamina : 0.f;
}

bool UOtherworldMovementLibrary::IsSprinting(const AActor* Character)
{
	const UOtherworldCharacterMovement* Movement = MovementOf(Character);
	return Movement && Movement->bSprinting;
}

bool UOtherworldMovementLibrary::IsSprintSpent(const AActor* Character)
{
	const UOtherworldCharacterMovement* Movement = MovementOf(Character);
	return Movement && Movement->bSprintSpent;
}

bool UOtherworldMovementLibrary::IsSprintAhead(const AActor* Character)
{
	const UOtherworldCharacterMovement* Movement = MovementOf(Character);
	return Movement && Movement->bSprintAhead;
}

void UOtherworldMovementLibrary::SetStamina(AActor* Character, float NewStamina)
{
	if (UOtherworldCharacterMovement* Movement = AuthorityMovementOf(Character))
	{
		Movement->SetStaminaAuthoritative(NewStamina);
	}
}

void UOtherworldMovementLibrary::SpendStamina(AActor* Character, float Amount)
{
	if (UOtherworldCharacterMovement* Movement = AuthorityMovementOf(Character))
	{
		Movement->SetStaminaAuthoritative(Movement->Stamina - Amount);
	}
}

void UOtherworldMovementLibrary::SetPace(AActor* Character, float JogSpeed, float SprintSpeed, float StaminaDrainPerSecond, float StaminaRegenPerSecond)
{
	if (UOtherworldCharacterMovement* Movement = AuthorityMovementOf(Character))
	{
		Movement->MaxWalkSpeed = JogSpeed;
		Movement->SprintSpeed = SprintSpeed;
		Movement->StaminaDrainPerSecond = StaminaDrainPerSecond;
		Movement->StaminaRegenPerSecond = StaminaRegenPerSecond;
	}
}
