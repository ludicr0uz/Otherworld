// The server's short history of where every character's hit boxes were (task
// M22, lag compensation). One sample per frame of the capsule's and each
// physics body's transform, kept HistorySeconds back, recorded only on a
// server with clients (single player records nothing), so a shot can be judged
// against where the target stood when the shooter saw it
// (UOtherworldShotLibrary::ShotTrace).
//
// A rewound trace moves no body: the engine traces a body where it is now, so
// the pellet's line is carried from where the body was to where it is, traced
// there, and the hit carried back. Rigid transforms both ways, so distances
// and bone names are the engine's own.
#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "Engine/HitResult.h"
#include "Subsystems/WorldSubsystem.h"
#include "OtherworldHitHistory.generated.h"

class ACharacter;
struct FBodyInstance;

/** Where one character's hit boxes were at one moment. */
struct FOtherworldBodySample
{
	double Time = 0.0;
	/** The capsule blocked Visibility then: a pellet could stop on it. */
	bool bShootable = false;
	FTransform Capsule;
	/** The mesh's physics bodies, by index into USkeletalMeshComponent::Bodies. */
	TArray<FTransform> Bodies;
};

struct FOtherworldCharacterHistory
{
	TWeakObjectPtr<ACharacter> Character;
	/** Oldest first. */
	TArray<FOtherworldBodySample> Samples;
};

UCLASS()
class OTHERWORLD_API UOtherworldHitHistory : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** How far back a sample is kept. A rewind is capped below this by its caller. */
	static constexpr double HistorySeconds = 1.0;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** A server with clients records; standalone (single player) does not. */
	bool IsRecording() const;

	/** Every character that has a history: what a world trace leaves to the rewound test. */
	void CharactersRecorded(TArray<AActor*>& Out) const;
	int32 SampleCount(const AActor* Character) const;

	/**
	 * The pellet's line against Character as it stood at time At (world
	 * seconds): false unless its capsule, where it was then, stops the line.
	 * Then OutCapsule is that hit, and the mesh's bodies are tried the same
	 * way: bOutBody says whether one was struck, OutBone which, OutBodyPoint
	 * where (both in today's world).
	 */
	bool TraceRewound(ACharacter* Character, double At, const FVector& Start, const FVector& End,
		FHitResult& OutCapsule, bool& bOutBody, FName& OutBone, FVector& OutBodyPoint) const;

	// What the last ShotTrace did, for the probes.
	float LastRewindSeconds = 0.f;
	int32 RewoundShots = 0;
	int32 RewoundHits = 0;

private:
	void OnPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	void Record(double Now);
	const FOtherworldCharacterHistory* HistoryOf(const AActor* Character) const;
	static bool SampleAt(const FOtherworldCharacterHistory& History, double At, FOtherworldBodySample& Out);
	static bool TraceBodyThen(const FBodyInstance& Body, const FTransform& Then,
		const FVector& Start, const FVector& End, FHitResult& OutHit);

	FDelegateHandle TickHandle;
	TArray<FOtherworldCharacterHistory> Histories;
};
