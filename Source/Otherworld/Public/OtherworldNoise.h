// The noises the wanderers can hear (task M28): a short list of recent ones,
// each with its place, its reach, when it was made and who made it. The
// server's alone: only the wanderers' AI reads it, and that runs there. Before
// M28 it was one record on the GameMode, so of two players firing far apart
// the wanderers heard only the louder.
//
// Written by Scripts/combat/noise.py's node (the shot, the player's footstep),
// asked by Scripts/npc/senses.py's (the sound sense). The nodes are
// Scripts/uebp/nodes/noise.py.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "OtherworldNoise.generated.h"

class APawn;

/** One noise: how far it carries belongs to what made it, the listener only scales it. */
USTRUCT(BlueprintType)
struct FOtherworldNoise
{
	GENERATED_BODY()

	/** Who made it: a player's pawn. Null once that body is gone. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Noise")
	TObjectPtr<AActor> Maker = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Noise")
	FVector Location = FVector::ZeroVector;

	/** How far it is heard all round, in cm. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Noise")
	float Reach = 0.f;

	/** A gunshot's louder cone: its line, its reach and the cosine of its half-angle. A reach of 0 is no cone. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Noise")
	FVector Direction = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Noise")
	float ConeReach = 0.f;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Noise")
	float ConeCos = 1.f;

	/** The world's time when it was made, in seconds. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Noise")
	float Time = 0.f;

	/** The larger of the two reaches. */
	float Loudness() const { return FMath::Max(Reach, ConeReach); }
};

/** The list itself, one per game world. Empty for ever on a client: nothing writes it there. */
UCLASS()
class OTHERWORLD_API UOtherworldNoiseList : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** A bound on the list whatever writes it: one noise a maker, and 64 players. */
	static constexpr int32 MaxNoises = 128;

	/**
	 * Add a noise, on a machine with authority. Each maker has one entry: a
	 * new noise replaces that maker's own only if it is older than
	 * HoldSeconds or the new one is at least as loud, so a footstep right
	 * after a gunshot does not erase the shot before the wanderers have asked.
	 * Another maker's noise is never touched. False when it did not land.
	 */
	bool Make(AActor* Maker, const FVector& Location, float Reach, const FVector& Direction,
		float ConeReach, float ConeCos, float HoldSeconds);

	/**
	 * The nearest noise of the last HoldSeconds that reaches a listener at
	 * Listener, each reach scaled by HearingScale. Null when none does.
	 */
	const FOtherworldNoise* Hear(const FVector& Listener, float HearingScale, float HoldSeconds) const;

	const TArray<FOtherworldNoise>& Noises() const { return List; }

	/** Noises that landed and noises refused (a quieter one over its maker's fresh one), for the probes. */
	int32 Made = 0;
	int32 Refused = 0;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	UPROPERTY()
	TArray<FOtherworldNoise> List;
};

UCLASS()
class OTHERWORLD_API UOtherworldNoiseLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** UOtherworldNoiseList::Make on this world's list. Does nothing on a client. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Noise", meta = (WorldContext = "WorldContextObject"))
	static void MakeNoise(const UObject* WorldContextObject, AActor* Maker, FVector Location, float Reach,
		FVector Direction, float ConeReach, float ConeCos, float HoldSeconds);

	/**
	 * Does a listener at Listener hear a noise of the last HoldSeconds? The
	 * nearest one that reaches it: who made it (null if not a pawn, or gone)
	 * and where. An exec node, so one pass of a sense asks once.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Noise", meta = (WorldContext = "WorldContextObject"))
	static bool HearNoise(const UObject* WorldContextObject, FVector Listener, float HearingScale,
		float HoldSeconds, APawn*& Maker, FVector& Location);

	/** For the probes: every noise held, stale ones included until the next write prunes them. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Noise", meta = (WorldContext = "WorldContextObject"))
	static TArray<FOtherworldNoise> NoisesHeld(const UObject* WorldContextObject);

	/** For the probes: how many noises have landed in this world, and how many were refused. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Noise", meta = (WorldContext = "WorldContextObject"))
	static int32 NoisesMade(const UObject* WorldContextObject);

	UFUNCTION(BlueprintCallable, Category = "Otherworld|Noise", meta = (WorldContext = "WorldContextObject"))
	static int32 NoisesRefused(const UObject* WorldContextObject);
};
