// How often a dedicated server poses a body it never draws (task A4). It
// judges every shot against the bones (OtherworldHitHistory.h) and fires from
// the gun in the hand, so a body cannot simply stand unposed; but it needs
// the pose at the rate a shot is judged, not the rate a screen is drawn:
//
//   within FullWithinCm of another player's body   every frame
//   further than that from every one               FarHz, a few times a second
//   further than NobodyBeyondCm, or a ragdoll      NobodyHz
//
// The engine's Update Rate Optimization does the skipping
// (USkinnedMeshComponent::bEnableUpdateRateOptimizations): what it never
// renders it evaluates every BaseNonRenderedUpdateRate frames, which this
// subsystem rewrites per body a few times a second. A skipped frame keeps the
// last pose and still carries the bodies with the capsule; the hit history
// blends between the poses it was given. Every other skinned mesh on the
// character (a MetaHuman's body, face and clothes, hung under the mesh the
// game runs on) is drawn only, so on a server it does not tick at all.
//
// Nothing here runs in single player, on a client or on a listen server: a
// machine with a screen poses what it draws.
#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "OtherworldServerPose.generated.h"

class ACharacter;

struct FOtherworldPosedBody
{
	TWeakObjectPtr<ACharacter> Character;
	float FullWithinCm = 0.f;
	float FarHz = 0.f;
	float NobodyBeyondCm = 0.f;
	float NobodyHz = 0.f;
	/** Frames between two poses, as last written: 1 is every frame. */
	int32 EveryFrames = 1;
};

UCLASS()
class OTHERWORLD_API UOtherworldServerPose : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** How often every body's rate is decided again. */
	static constexpr double ReviewSeconds = 0.25;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	void Throttle(ACharacter* Body, float FullWithinCm, float FarHz, float NobodyBeyondCm, float NobodyHz);
	int32 EveryFrames(const AActor* Body) const;

private:
	void OnPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	void Review();

	FDelegateHandle TickHandle;
	TArray<FOtherworldPosedBody> Bodies;
	/** The players' bodies standing, rebuilt in place each review. */
	TArray<FVector> Players;
	TArray<const ACharacter*> PlayerBodies;
	double NextReview = 0.0;
	/** The server's frame, smoothed: what turns a rate in Hz into frames. */
	float FrameSeconds = 1.f / 30.f;
};

UCLASS()
class OTHERWORLD_API UOtherworldPoseLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * On a dedicated server, pose Body's mesh by how near a player is (the
	 * table at the top of this file) and stop every other skinned mesh on it
	 * from ticking. Anywhere else it does nothing. Called once, at the body's
	 * BeginPlay (Scripts/combat/server_pose.py; the numbers are
	 * Scripts/combat/pose_tuning.py).
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Pose")
	static void ThrottleServerPose(ACharacter* Body, float FullWithinCm, float FarHz, float NobodyBeyondCm,
		float NobodyHz);

	/** For the probes: the frames between two poses of this body's mesh (1: every frame; 0: not throttled). */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Pose")
	static int32 ServerPoseEveryFrames(const AActor* Body);

	/** For the probes: how many skinned meshes on this actor still tick. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Pose")
	static int32 TickingSkinnedMeshes(const AActor* Body);
};
