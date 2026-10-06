// The player's movement component: sprint, prone and the aim-walk as predicted
// movement states, and the stamina a sprint spends.
//
// A state written onto the stock component from a Blueprint (MaxWalkSpeed, the
// crouched height) exists on one machine only, so under lag the owning client
// and the server move the character at different speeds and the server pulls
// the client back. Here the three states travel with every move as saved-move
// flags, and both machines run the same rules on them, in the same step of the
// movement, with that move's own delta time:
//
//   sprint    FLAG_Custom_0, the key. Whether it is a sprint is decided here:
//             the stamina latch and the forward cone (SprintConeMinDot).
//   prone     FLAG_Custom_1. A crouch (the engine's own flag) to ProneHalfHeight.
//   aim-walk  FLAG_Custom_2. AimWalkAlpha eases towards it; the walk slows by it.
//
// Stamina is simulated with the moves, so the client predicts it; the client
// reports its own with each move, and a correction carries the server's.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/CharacterMovementReplication.h"
#include "OtherworldCharacterMovement.generated.h"

class UOtherworldCharacterMovement;

/** What a move adds to the engine's: the wants, and the state the move started from and ended with. */
class FOtherworldSavedMove : public FSavedMove_Character
{
public:
	typedef FSavedMove_Character Super;

	uint8 bWantsToSprint : 1;
	uint8 bWantsProne : 1;
	uint8 bWantsAimWalk : 1;
	uint8 bStartSprintSpent : 1;
	float StartStamina = 0.f;
	float StartAimWalkAlpha = 0.f;
	/** After the move: what the server is told, to compare with its own. */
	float EndStamina = 0.f;

	virtual void Clear() override;
	virtual void SetMoveFor(ACharacter* C, float InDeltaTime, FVector const& NewAccel, FNetworkPredictionData_Client_Character& ClientData) override;
	virtual void PostUpdate(ACharacter* C, EPostUpdateMode PostUpdateMode) override;
	virtual bool CanCombineWith(const FSavedMovePtr& NewMove, ACharacter* InCharacter, float MaxDelta) const override;
	virtual void CombineWith(const FSavedMove_Character* OldMove, ACharacter* InCharacter, APlayerController* PC, const FVector& OldStartLocation) override;
	virtual uint8 GetCompressedFlags() const override;
};

class FOtherworldPredictionData_Client : public FNetworkPredictionData_Client_Character
{
public:
	explicit FOtherworldPredictionData_Client(const UCharacterMovementComponent& ClientMovement);
	virtual FSavedMovePtr AllocateNewMove() override;
};

/** A move as sent to the server: the engine's, and the client's stamina after it. */
struct FOtherworldNetworkMoveData : public FCharacterNetworkMoveData
{
	/** Sent as a byte: a 255th of the bar, well inside StaminaErrorTolerance. */
	float Stamina = 0.f;

	virtual void ClientFillNetworkMoveData(const FSavedMove_Character& ClientMove, ENetworkMoveType MoveType) override;
	virtual bool Serialize(UCharacterMovementComponent& CharacterMovement, FArchive& Ar, UPackageMap* PackageMap, ENetworkMoveType MoveType) override;
};

struct FOtherworldNetworkMoveDataContainer : public FCharacterNetworkMoveDataContainer
{
	FOtherworldNetworkMoveDataContainer();

private:
	FOtherworldNetworkMoveData Moves[3];
};

/** The server's answer: a correction also carries the stamina, the latch and the aim's ease. */
struct FOtherworldMoveResponseDataContainer : public FCharacterMoveResponseDataContainer
{
	float Stamina = 0.f;
	float AimWalkAlpha = 0.f;
	bool bSprintSpent = false;

	virtual void ServerFillResponseData(const UCharacterMovementComponent& CharacterMovement, const FClientAdjustment& PendingAdjustment) override;
	virtual bool Serialize(UCharacterMovementComponent& CharacterMovement, FArchive& Ar, UPackageMap* PackageMap) override;
};

UCLASS()
class OTHERWORLD_API UOtherworldCharacterMovement : public UCharacterMovementComponent
{
	GENERATED_BODY()

public:
	UOtherworldCharacterMovement();

	// --- the numbers: the builders write them onto the character's template
	// (combat/player_move.py) from the tuning tables. The jog is MaxWalkSpeed.

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace", meta = (ForceUnits = "cm/s"))
	float SprintSpeed = 600.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace")
	float MaxStamina = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace")
	float StaminaDrainPerSecond = 12.5f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace")
	float StaminaRegenPerSecond = 12.f;

	/** A sprint needs the steering within the cone ahead: the cosine of its half angle. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace")
	float SprintConeMinDot = 0.5f;

	/** The walk's share of the jog at a full aim. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace")
	float AimWalkSpeedScale = 0.5f;

	/** FInterpTo's speed for AimWalkAlpha: the same as the camera's zoom. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace")
	float AimWalkInterpSpeed = 12.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Stance")
	float CrouchSpeedScale = 0.45f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Stance")
	float ProneSpeedScale = 0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Stance", meta = (ForceUnits = "cm"))
	float CrouchHalfHeight = 60.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Stance", meta = (ForceUnits = "cm"))
	float ProneHalfHeight = 40.f;

	/** How far the client's stamina may be from the server's before the server corrects it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Otherworld|Pace")
	float StaminaErrorTolerance = 2.f;

	// --- what the player wants: written by the owning machine, sent as flags.

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bWantsToSprint = false;

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bWantsProne = false;

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bWantsAimWalk = false;

	// --- what the movement made of it: the same on the owning client and the server.

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	float Stamina = 100.f;

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bSprinting = false;

	/** A held sprint ran the stamina out: no sprint until the key is let go. */
	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bSprintSpent = false;

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	bool bSprintAhead = false;

	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	float AimWalkAlpha = 0.f;

	/** Corrections this client has taken from the server since it began. Each is also a log line. */
	UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Otherworld|State")
	int32 CorrectionCount = 0;

	/** The server's stamina, changed outside a move (a blocked blow, a loaded profile). */
	void SetStaminaAuthoritative(float NewStamina);

	virtual void BeginPlay() override;
	virtual float GetMaxSpeed() const override;
	virtual void UpdateCharacterStateBeforeMovement(float DeltaSeconds) override;
	virtual void UpdateFromCompressedFlags(uint8 Flags) override;
	virtual FNetworkPredictionData_Client* GetPredictionData_Client() const override;
	virtual bool ClientUpdatePositionAfterServerUpdate() override;

protected:
	using Super::ServerCheckClientError;
	virtual bool ServerCheckClientError(float ClientTimeStamp, float DeltaTime, const FVector& Accel, const FVector& ClientWorldLocation, const FVector& RelativeClientLocation, FMovementBaseInterfaceData* ClientMovementBaseInterfaceData, FName ClientBaseBoneName, uint8 ClientMovementMode) override;

	using Super::OnClientCorrectionReceived;
	virtual void OnClientCorrectionReceived(FNetworkPredictionData_Client_Character& ClientData, float TimeStamp, FVector NewLocation, FVector NewVelocity, FMovementBaseInterfaceData* NewMovementBaseInterfaceData, FName NewBaseBoneName, bool bHasBase, bool bBaseRelativePosition, uint8 ServerMovementMode, FVector ServerGravityDirection) override;

private:
	/** The way the player faces, for the sprint's cone: the view's yaw. */
	FVector FacingDirection() const;
	float GroundSpeed() const;

	FOtherworldNetworkMoveDataContainer MoveDataContainer;
	FOtherworldMoveResponseDataContainer MoveResponseContainer;
};
