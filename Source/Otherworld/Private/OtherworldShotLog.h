// The shot log: a developer's record of every shot the authority judged, to
// troubleshoot one that hit or missed when it should not have. Off unless one
// of three asks for it:
//
//     the console variable   Otherworld.ShotLog 1      (any machine, live)
//     the command line       -ShotLog                  (a dedicated server)
//     the GameState's        DebugShotLog              (the menu's DEBUG
//                                                       SETTINGS "Shot log")
//
// Each shot is one SHOT-LOG block in the log (LogOtherworldShotLog): the ask
// (the shooter, its place, its view, the aim point, or why it was refused),
// then a line set per pellet: the line traced (muzzle, direction, end, the
// angle off the aim point, the rewind), what stopped it (actor, component,
// location, impact point and normal, distance), the body struck (bone and
// point), the target (actor, mesh and capsule, now and, rewound, the bone's
// box then), and the outcome (zone, damage, health before and after). A
// pellet that struck no body names the character nearest its line and how
// far it passed. Only the machine with authority judges a shot, so a
// server's log has its clients' shots and a client's has none.
#pragma once

#include "CoreMinimal.h"

class AActor;
class UWorld;
class UOtherworldHealthComponent;
struct FHitResult;

namespace OtherworldShotLog
{
	/** Whether this world logs its shots (above). */
	bool IsOn(const UWorld* World);

	/** A shot asked for: a new shot number, and its ask logged. */
	void Asked(const AActor* Shooter, const FVector& AimPoint);

	/** The ask refused, and why. */
	void Refused(const AActor* Shooter, const FString& Why);

	/** What one pellet of the current shot did. */
	struct FPellet
	{
		const AActor* Shooter = nullptr;
		const AActor* Gun = nullptr;
		int32 Index = 0;
		int32 Count = 0;
		FVector Muzzle = FVector::ZeroVector;
		FVector Direction = FVector::ZeroVector;
		FVector End = FVector::ZeroVector;
		float SpreadDegrees = 0.f;
		float RewindSeconds = 0.f;
		bool bStopped = false;
		const FHitResult* Hit = nullptr;
		bool bBodyHit = false;
		FName BodyBone = NAME_None;
		FVector BodyPoint = FVector::ZeroVector;
		bool bHurt = false;
		bool bScenery = false;
		bool bHead = false;
		bool bLimb = false;
		float Worth = 1.f;
		float Damage = 0.f;
		double HealthBefore = 0.0;
		const UOtherworldHealthComponent* Health = nullptr;
	};
	void Pellet(const FPellet& P);

	/** For the probes: the lines written in this process, and the last block. */
	int32 Lines();
	const FString& Last();
}
