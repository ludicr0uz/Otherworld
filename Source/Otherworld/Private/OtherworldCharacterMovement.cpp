#include "OtherworldCharacterMovement.h"

#include "GameFramework/Character.h"
#include "GameFramework/Controller.h"

DEFINE_LOG_CATEGORY_STATIC(LogOtherworldMove, Log, All);

namespace
{
	const uint8 FLAG_Sprint = FSavedMove_Character::FLAG_Custom_0;
	const uint8 FLAG_Prone = FSavedMove_Character::FLAG_Custom_1;
	const uint8 FLAG_AimWalk = FSavedMove_Character::FLAG_Custom_2;

	// The capsule is the height it was asked for; this is float slack only.
	const float HeightSlack = 0.5f;

	UOtherworldCharacterMovement* MovementOf(const ACharacter* Character)
	{
		return Character ? Cast<UOtherworldCharacterMovement>(Character->GetCharacterMovement()) : nullptr;
	}
}

// --- the saved move ----------------------------------------------------------

void FOtherworldSavedMove::Clear()
{
	Super::Clear();
	bWantsToSprint = false;
	bWantsProne = false;
	bWantsAimWalk = false;
	bStartSprintSpent = false;
	StartStamina = 0.f;
	StartAimWalkAlpha = 0.f;
	EndStamina = 0.f;
}

void FOtherworldSavedMove::SetMoveFor(ACharacter* C, float InDeltaTime, FVector const& NewAccel, FNetworkPredictionData_Client_Character& ClientData)
{
	Super::SetMoveFor(C, InDeltaTime, NewAccel, ClientData);
	if (const UOtherworldCharacterMovement* Movement = MovementOf(C))
	{
		bWantsToSprint = Movement->bWantsToSprint;
		bWantsProne = Movement->bWantsProne;
		bWantsAimWalk = Movement->bWantsAimWalk;
		bStartSprintSpent = Movement->bSprintSpent;
		StartStamina = Movement->Stamina;
		StartAimWalkAlpha = Movement->AimWalkAlpha;
	}
}

void FOtherworldSavedMove::PostUpdate(ACharacter* C, EPostUpdateMode PostUpdateMode)
{
	Super::PostUpdate(C, PostUpdateMode);
	if (PostUpdateMode == PostUpdate_Record)
	{
		if (const UOtherworldCharacterMovement* Movement = MovementOf(C))
		{
			EndStamina = Movement->Stamina;
		}
	}
}

bool FOtherworldSavedMove::CanCombineWith(const FSavedMovePtr& NewMove, ACharacter* InCharacter, float MaxDelta) const
{
	const FOtherworldSavedMove* Other = static_cast<const FOtherworldSavedMove*>(NewMove.Get());
	if (bWantsToSprint != Other->bWantsToSprint || bWantsProne != Other->bWantsProne || bWantsAimWalk != Other->bWantsAimWalk)
	{
		return false;
	}
	return Super::CanCombineWith(NewMove, InCharacter, MaxDelta);
}

void FOtherworldSavedMove::CombineWith(const FSavedMove_Character* OldMove, ACharacter* InCharacter, APlayerController* PC, const FVector& OldStartLocation)
{
	Super::CombineWith(OldMove, InCharacter, PC, OldStartLocation);
	// The engine has put the character back where the old move started and
	// will run both as one move, so the stamina goes back there with it:
	// otherwise the old move's time is spent twice.
	const FOtherworldSavedMove* Old = static_cast<const FOtherworldSavedMove*>(OldMove);
	bStartSprintSpent = Old->bStartSprintSpent;
	StartStamina = Old->StartStamina;
	StartAimWalkAlpha = Old->StartAimWalkAlpha;
	if (UOtherworldCharacterMovement* Movement = MovementOf(InCharacter))
	{
		Movement->bSprintSpent = bStartSprintSpent;
		Movement->Stamina = StartStamina;
		Movement->AimWalkAlpha = StartAimWalkAlpha;
	}
}

uint8 FOtherworldSavedMove::GetCompressedFlags() const
{
	uint8 Flags = Super::GetCompressedFlags();
	if (bWantsToSprint)
	{
		Flags |= FLAG_Sprint;
	}
	if (bWantsProne)
	{
		Flags |= FLAG_Prone;
	}
	if (bWantsAimWalk)
	{
		Flags |= FLAG_AimWalk;
	}
	return Flags;
}

FOtherworldPredictionData_Client::FOtherworldPredictionData_Client(const UCharacterMovementComponent& ClientMovement)
	: FNetworkPredictionData_Client_Character(ClientMovement)
{
}

FSavedMovePtr FOtherworldPredictionData_Client::AllocateNewMove()
{
	return FSavedMovePtr(new FOtherworldSavedMove());
}

// --- what goes over the wire -------------------------------------------------

void FOtherworldNetworkMoveData::ClientFillNetworkMoveData(const FSavedMove_Character& ClientMove, ENetworkMoveType MoveType)
{
	FCharacterNetworkMoveData::ClientFillNetworkMoveData(ClientMove, MoveType);
	Stamina = static_cast<const FOtherworldSavedMove&>(ClientMove).EndStamina;
}

bool FOtherworldNetworkMoveData::Serialize(UCharacterMovementComponent& CharacterMovement, FArchive& Ar, UPackageMap* PackageMap, ENetworkMoveType MoveType)
{
	const bool bOk = FCharacterNetworkMoveData::Serialize(CharacterMovement, Ar, PackageMap, MoveType);
	const float Full = FMath::Max(CastChecked<UOtherworldCharacterMovement>(&CharacterMovement)->MaxStamina, UE_KINDA_SMALL_NUMBER);
	uint8 Byte = Ar.IsSaving() ? static_cast<uint8>(FMath::RoundToInt(FMath::Clamp(Stamina / Full, 0.f, 1.f) * 255.f)) : 0;
	Ar << Byte;
	if (Ar.IsLoading())
	{
		Stamina = Byte / 255.f * Full;
	}
	return bOk && !Ar.IsError();
}

FOtherworldNetworkMoveDataContainer::FOtherworldNetworkMoveDataContainer()
{
	NewMoveData = &Moves[0];
	PendingMoveData = &Moves[1];
	OldMoveData = &Moves[2];
}

void FOtherworldMoveResponseDataContainer::ServerFillResponseData(const UCharacterMovementComponent& CharacterMovement, const FClientAdjustment& PendingAdjustment)
{
	FCharacterMoveResponseDataContainer::ServerFillResponseData(CharacterMovement, PendingAdjustment);
	const UOtherworldCharacterMovement* Movement = CastChecked<UOtherworldCharacterMovement>(&CharacterMovement);
	Stamina = Movement->Stamina;
	AimWalkAlpha = Movement->AimWalkAlpha;
	bSprintSpent = Movement->bSprintSpent;
}

bool FOtherworldMoveResponseDataContainer::Serialize(UCharacterMovementComponent& CharacterMovement, FArchive& Ar, UPackageMap* PackageMap)
{
	const bool bOk = FCharacterMoveResponseDataContainer::Serialize(CharacterMovement, Ar, PackageMap);
	if (IsCorrection())
	{
		Ar << Stamina;
		Ar << AimWalkAlpha;
		Ar.SerializeBits(&bSprintSpent, 1);
	}
	return bOk && !Ar.IsError();
}

// --- the component -----------------------------------------------------------

UOtherworldCharacterMovement::UOtherworldCharacterMovement()
{
	SetNetworkMoveDataContainer(MoveDataContainer);
	SetMoveResponseDataContainer(MoveResponseContainer);
}

void UOtherworldCharacterMovement::BeginPlay()
{
	Super::BeginPlay();
	Stamina = MaxStamina;
}

void UOtherworldCharacterMovement::SetStaminaAuthoritative(float NewStamina)
{
	Stamina = FMath::Clamp(NewStamina, 0.f, MaxStamina);
}

FVector UOtherworldCharacterMovement::FacingDirection() const
{
	// The character turns with the view, and the view is what a move carries
	// to the server, so both machines ask the controller.
	if (CharacterOwner)
	{
		if (const AController* Controller = CharacterOwner->GetController())
		{
			return FRotator(0., Controller->GetControlRotation().Yaw, 0.).Vector();
		}
		return CharacterOwner->GetActorForwardVector().GetSafeNormal2D();
	}
	return FVector::ForwardVector;
}

float UOtherworldCharacterMovement::GroundSpeed() const
{
	if (IsCrouching())
	{
		return MaxWalkSpeed * (bWantsProne ? ProneSpeedScale : CrouchSpeedScale);
	}
	if (bSprinting)
	{
		return SprintSpeed;
	}
	return MaxWalkSpeed * FMath::Lerp(1.f, AimWalkSpeedScale, AimWalkAlpha);
}

float UOtherworldCharacterMovement::GetMaxSpeed() const
{
	switch (MovementMode)
	{
	case MOVE_Walking:
	case MOVE_NavWalking:
	case MOVE_Falling:
		return GroundSpeed();
	default:
		return Super::GetMaxSpeed();
	}
}

void UOtherworldCharacterMovement::UpdateCharacterStateBeforeMovement(float DeltaSeconds)
{
	if (!CharacterOwner || CharacterOwner->GetLocalRole() == ROLE_SimulatedProxy)
	{
		Super::UpdateCharacterStateBeforeMovement(DeltaSeconds);
		return;
	}

	// The engine sizes the capsule only as a crouch starts, so going between
	// crouch and prone stands up first; Super crouches again, to the new
	// height, in this same step.
	const float WantedHeight = bWantsProne ? ProneHalfHeight : CrouchHalfHeight;
	if (IsCrouching() && !FMath::IsNearlyEqual(GetCrouchedHalfHeight(), WantedHeight, HeightSlack))
	{
		UnCrouch(false);
	}
	if (!IsCrouching())
	{
		SetCrouchedHalfHeight(WantedHeight);
	}
	Super::UpdateCharacterStateBeforeMovement(DeltaSeconds);

	// The sprint. The latch first, off the stamina this move starts with: a
	// sprint that ran it out stays off until the key is let go, or a held key
	// would stop, refill a sliver and start again every move.
	const FVector Steer = Acceleration.GetSafeNormal2D();
	bSprintAhead = (Steer | FacingDirection()) >= SprintConeMinDot;
	bSprintSpent = bWantsToSprint && (bSprintSpent || Stamina <= 0.f);
	bSprinting = bWantsToSprint && !bSprintSpent && bSprintAhead;
	const float Rate = bSprinting ? -StaminaDrainPerSecond : StaminaRegenPerSecond;
	Stamina = FMath::Clamp(Stamina + Rate * DeltaSeconds, 0.f, MaxStamina);

	const float AimTarget = (bWantsAimWalk && !bSprinting) ? 1.f : 0.f;
	AimWalkAlpha = FMath::FInterpTo(AimWalkAlpha, AimTarget, DeltaSeconds, AimWalkInterpSpeed);
}

void UOtherworldCharacterMovement::UpdateFromCompressedFlags(uint8 Flags)
{
	Super::UpdateFromCompressedFlags(Flags);
	bWantsToSprint = (Flags & FLAG_Sprint) != 0;
	bWantsProne = (Flags & FLAG_Prone) != 0;
	bWantsAimWalk = (Flags & FLAG_AimWalk) != 0;
}

FNetworkPredictionData_Client* UOtherworldCharacterMovement::GetPredictionData_Client() const
{
	if (ClientPredictionData == nullptr)
	{
		UOtherworldCharacterMovement* MutableThis = const_cast<UOtherworldCharacterMovement*>(this);
		MutableThis->ClientPredictionData = new FOtherworldPredictionData_Client(*this);
	}
	return ClientPredictionData;
}

bool UOtherworldCharacterMovement::ClientUpdatePositionAfterServerUpdate()
{
	// Replaying the saved moves sets the wants to each move's in turn. What
	// the player wants now is what they were before the replay.
	const bool bRealSprint = bWantsToSprint;
	const bool bRealProne = bWantsProne;
	const bool bRealAimWalk = bWantsAimWalk;
	const bool bReplayed = Super::ClientUpdatePositionAfterServerUpdate();
	bWantsToSprint = bRealSprint;
	bWantsProne = bRealProne;
	bWantsAimWalk = bRealAimWalk;
	return bReplayed;
}

bool UOtherworldCharacterMovement::ServerCheckClientError(float ClientTimeStamp, float DeltaTime, const FVector& Accel, const FVector& ClientWorldLocation, const FVector& RelativeClientLocation, FMovementBaseInterfaceData* ClientMovementBaseInterfaceData, FName ClientBaseBoneName, uint8 ClientMovementMode)
{
	if (Super::ServerCheckClientError(ClientTimeStamp, DeltaTime, Accel, ClientWorldLocation, RelativeClientLocation, ClientMovementBaseInterfaceData, ClientBaseBoneName, ClientMovementMode))
	{
		return true;
	}
	// The position agrees; the stamina has to as well, or a bar the server
	// changed (a blocked blow) would stay wrong on the client until it moved
	// it far enough to miss a step.
	if (const FOtherworldNetworkMoveData* Move = static_cast<const FOtherworldNetworkMoveData*>(GetCurrentNetworkMoveData()))
	{
		return FMath::Abs(Move->Stamina - Stamina) > StaminaErrorTolerance;
	}
	return false;
}

void UOtherworldCharacterMovement::OnClientCorrectionReceived(FNetworkPredictionData_Client_Character& ClientData, float TimeStamp, FVector NewLocation, FVector NewVelocity, FMovementBaseInterfaceData* NewMovementBaseInterfaceData, FName NewBaseBoneName, bool bHasBase, bool bBaseRelativePosition, uint8 ServerMovementMode, FVector ServerGravityDirection)
{
	Super::OnClientCorrectionReceived(ClientData, TimeStamp, NewLocation, NewVelocity, NewMovementBaseInterfaceData, NewBaseBoneName, bHasBase, bBaseRelativePosition, ServerMovementMode, ServerGravityDirection);

	const FVector Predicted = ClientData.LastAckedMove.IsValid() ? ClientData.LastAckedMove->SavedLocation : UpdatedComponent->GetComponentLocation();
	++CorrectionCount;
	// One line per correction: the --net check counts them (uepylib/net.py).
	UE_LOG(LogOtherworldMove, Log, TEXT("MOVE-CORRECTION %d %s: %.1f cm off at %.3f, stamina %.1f -> %.1f"),
		CorrectionCount, *GetNameSafe(CharacterOwner), FVector::Dist(Predicted, NewLocation), TimeStamp,
		Stamina, MoveResponseContainer.Stamina);

	// The saved moves after this one are replayed from here, so they start
	// from the server's stamina as they start from its position.
	Stamina = MoveResponseContainer.Stamina;
	AimWalkAlpha = MoveResponseContainer.AimWalkAlpha;
	bSprintSpent = MoveResponseContainer.bSprintSpent;
}
