// The server's short history of where every character's hit boxes were (task
// M22, lag compensation; A4 made it a ring). Recorded only on a server with
// clients (single player records nothing), so a shot can be judged against
// where the target stood when the shooter saw it
// (UOtherworldShotLibrary::ShotTrace).
//
// Two rings of fixed capacity per character, so a frame allocates nothing:
//
//   frames  the capsule and the mesh's own frame, at most FramesPerSecond
//           a second: where the character was
//   poses   each physics body in the mesh's frame, written only on a frame
//           that posed the mesh anew: how it stood. A body the server poses
//           at 10 Hz (OtherworldServerPose.h) has ten of these a second, and
//           a rewound trace blends the two either side of its time
//
// A rewound trace moves no body: the engine traces a body where it is now, so
// the pellet's line is carried from where the body was to where it is, traced
// there, and the hit carried back. Rigid transforms both ways, so distances
// and bone names are the engine's own. The capsule is tried first, from the
// frames alone; a body's transform is blended only for a character whose
// capsule the line struck.
#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "Engine/HitResult.h"
#include "Subsystems/WorldSubsystem.h"
#include "UObject/ObjectKey.h"
#include "OtherworldHitHistory.generated.h"

class ACharacter;
class USkeletalMeshComponent;
struct FBodyInstance;

/** Where one character's hit boxes were, a second back: two rings. */
struct FOtherworldCharacterHistory
{
	/** Entries per ring: a second of frames at FramesPerSecond, and two spare. */
	static constexpr int32 Capacity = 32;

	TWeakObjectPtr<ACharacter> Character;

	// --- the frames, oldest at FrameStart.
	double FrameTimes[Capacity];
	/** The capsule blocked Visibility then: a pellet could stop on it. */
	bool bShootable[Capacity];
	FTransform Capsules[Capacity];
	/** The mesh component's place, without its scale: what the poses are kept in. */
	FTransform MeshFrames[Capacity];
	int32 FrameStart = 0;
	int32 FrameNum = 0;

	// --- the poses, oldest at PoseStart.
	double PoseTimes[Capacity];
	int32 PoseStart = 0;
	int32 PoseNum = 0;
	/** Bodies per pose, by index into USkeletalMeshComponent::Bodies. */
	int32 BodyCount = 0;
	/** Capacity x BodyCount transforms, allocated once per character. */
	TArray<FTransform> PoseBodies;

	int32 Frame(int32 i) const { return (FrameStart + i) % Capacity; }
	int32 Pose(int32 i) const { return (PoseStart + i) % Capacity; }
};

UCLASS()
class OTHERWORLD_API UOtherworldHitHistory : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** How far back a sample is kept. A rewind is capped below this by its caller. */
	static constexpr double HistorySeconds = 1.0;
	/** The most frames kept of a second: the rate a shot is judged at, not a screen's. */
	static constexpr double FramesPerSecond = 30.0;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** A server with clients records; standalone (single player) does not. */
	bool IsRecording() const;

	/** Every character that has a history: what a world trace leaves to the rewound test. */
	const TArray<TWeakObjectPtr<const AActor>>& Recorded() const { return RecordedActors; }
	void CharactersRecorded(TArray<AActor*>& Out) const;
	/** The frames held of this character, and the poses among them. */
	int32 SampleCount(const AActor* Character) const;
	int32 PoseCount(const AActor* Character) const;

	/**
	 * The pellet's line against every recorded character but Shooter, each as
	 * it stood at time At (world seconds), nearer than Reach: false unless a
	 * capsule, where it was then, stops the line. Then OutCapsule is the
	 * nearest such hit, and that character's bodies have been tried the same
	 * way: bOutBody says whether one was struck, OutBone which, OutBodyPoint
	 * where (both in today's world).
	 */
	bool TraceRewound(const AActor* Shooter, double At, const FVector& Start, const FVector& End, float Reach,
		FHitResult& OutCapsule, bool& bOutBody, FName& OutBone, FVector& OutBodyPoint) const;

	/**
	 * For the probes: where the body of Character's bone Bone stood at time
	 * At, as a rewound trace would place it. False with no such body or no pose.
	 */
	bool BodyThen(const AActor* Character, FName Bone, double At, FVector& OutLocation) const;

	// What the last ShotTrace did, for the probes.
	float LastRewindSeconds = 0.f;
	FVector LastStart = FVector::ZeroVector;
	FVector LastEnd = FVector::ZeroVector;
	int32 RewoundShots = 0;
	int32 RewoundHits = 0;

private:
	void OnPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	void Record(double Now);
	const FOtherworldCharacterHistory* HistoryOf(const AActor* Character) const;
	/** The two entries of a ring either side of At (the same one twice at an end) and the weight of the second. */
	static void Either(const double* Times, int32 Start, int32 Num, double At, int32& OutA, int32& OutB, float& OutAlpha);
	void BodiesThen(const FOtherworldCharacterHistory& History, USkeletalMeshComponent& Mesh, double At,
		const FTransform& MeshFrame, const FVector& Start, const FVector& End,
		bool& bOutBody, FName& OutBone, FVector& OutBodyPoint) const;
	static bool TraceBodyThen(const FBodyInstance& Body, const FTransform& Then,
		const FVector& Start, const FVector& End, FHitResult& OutHit);

	FDelegateHandle TickHandle;
	TMap<FObjectKey, TUniquePtr<FOtherworldCharacterHistory>> Histories;
	/** The characters of Histories, rebuilt in place each recorded frame. */
	TArray<TWeakObjectPtr<const AActor>> RecordedActors;
};
