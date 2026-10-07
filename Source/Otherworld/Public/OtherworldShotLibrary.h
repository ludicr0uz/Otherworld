// The pellet's trace, for the fire graph (task M22). One node in place of the
// two it had (LineTraceSingle on Visibility, then K2_LineTraceComponent on
// the struck character's mesh): the same two traces where the shooter is
// local, and on a server, for a remote shooter, both against where every
// character stood when the shooter fired, by its ping (UOtherworldHitHistory).
#pragma once

#include "CoreMinimal.h"
#include "Engine/HitResult.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldShotLibrary.generated.h"

class AActor;

UCLASS()
class OTHERWORLD_API UOtherworldShotLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * The pellet from Start to End, ignoring the shooter. True and OutHit when
	 * it stopped on something (Visibility, simple collision). If that is a
	 * character, bBodyHit says whether the same line strikes one of its mesh's
	 * physics bodies, BodyBone which and BodyPoint where: a pellet inside the
	 * capsule that strikes none is a miss. A remote shooter's shot is judged
	 * against where every character stood RewindSecondsFor() ago.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Shot")
	static bool ShotTrace(AActor* Shooter, FVector Start, FVector End, float MaxRewindSeconds,
		float ExtraRewindSeconds, FHitResult& OutHit, bool& bBodyHit, FName& BodyBone, FVector& BodyPoint);

	/**
	 * How far back this shooter's shot is judged: its connection's round trip
	 * plus ExtraRewindSeconds (what its view of the others lags by), at most
	 * MaxRewindSeconds; 0 for a local player (single player, a listen host) or
	 * an AI.
	 */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Shot")
	static float RewindSecondsFor(const AActor* Shooter, float MaxRewindSeconds, float ExtraRewindSeconds);

	// --- what the history did, for the probes.

	/** Whether this world records hit boxes: a server with clients. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Shot", meta = (WorldContext = "WorldContextObject"))
	static bool IsRecordingHitHistory(const UObject* WorldContextObject);

	/** How many samples of this character's hit boxes the history holds. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Shot")
	static int32 HitHistorySamples(const AActor* Character);

	/** The rewind the last ShotTrace used, in seconds (0 when it traced the present). */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Shot", meta = (WorldContext = "WorldContextObject"))
	static float LastRewindSeconds(const UObject* WorldContextObject);

	/** Shots judged against the history, and those of them that struck a rewound body. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Shot", meta = (WorldContext = "WorldContextObject"))
	static int32 RewoundShots(const UObject* WorldContextObject);

	UFUNCTION(BlueprintPure, Category = "Otherworld|Shot", meta = (WorldContext = "WorldContextObject"))
	static int32 RewoundHits(const UObject* WorldContextObject);
};
