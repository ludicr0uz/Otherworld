#include "OtherworldCharacter.h"

#include "OtherworldCharacterMovement.h"
#include "OtherworldWeaponComponentBase.h"
#include "Components/CapsuleComponent.h"
#include "Engine/LocalPlayer.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "Net/UnrealNetwork.h"

AOtherworldCharacter::AOtherworldCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UOtherworldCharacterMovement>(ACharacter::CharacterMovementComponentName))
{
}

UEnhancedInputLocalPlayerSubsystem* AOtherworldCharacter::InputSubsystem() const
{
	const APlayerController* PC = Cast<APlayerController>(GetController());
	const ULocalPlayer* Player = PC ? PC->GetLocalPlayer() : nullptr;
	return Player ? Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
}

void AOtherworldCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	UEnhancedInputLocalPlayerSubsystem* Subsystem = InputSubsystem();
	if (Subsystem && InputContext && !Subsystem->HasMappingContext(InputContext))
	{
		Subsystem->AddMappingContext(InputContext, 0);
	}
	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (Input && FireAction)
	{
		Input->BindAction(FireAction, ETriggerEvent::Started, this, &AOtherworldCharacter::FireStarted);
		Input->BindAction(FireAction, ETriggerEvent::Completed, this, &AOtherworldCharacter::FireStopped);
		Input->BindAction(FireAction, ETriggerEvent::Canceled, this, &AOtherworldCharacter::FireStopped);
	}
}

void AOtherworldCharacter::FireStarted()
{
	if (UOtherworldWeaponComponentBase* Weapon = FindComponentByClass<UOtherworldWeaponComponentBase>())
	{
		Weapon->FireInput(true);
	}
}

void AOtherworldCharacter::FireStopped()
{
	if (UOtherworldWeaponComponentBase* Weapon = FindComponentByClass<UOtherworldWeaponComponentBase>())
	{
		Weapon->FireInput(false);
	}
}

void AOtherworldCharacter::SetFireKey(FKey Key)
{
	if (!InputContext || !FireAction || !Key.IsValid())
	{
		return;
	}
	bool bMapped = false;
	int32 Others = 0;
	for (const FEnhancedActionKeyMapping& Mapping : InputContext->GetMappings())
	{
		if (Mapping.Action == FireAction)
		{
			if (Mapping.Key == Key)
			{
				bMapped = true;
			}
			else
			{
				++Others;
			}
		}
	}
	if (bMapped && Others == 0)
	{
		return;
	}
	InputContext->UnmapAllKeysFromAction(FireAction);
	InputContext->MapKey(FireAction, Key);
	if (UEnhancedInputLocalPlayerSubsystem* Subsystem = InputSubsystem())
	{
		Subsystem->RequestRebuildControlMappings();
	}
}

void AOtherworldCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION(AOtherworldCharacter, bProne, COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(AOtherworldCharacter, bSliding, COND_SimulatedOnly);
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
