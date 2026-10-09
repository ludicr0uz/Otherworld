// The native parent of BP_WeaponComponent (task W1): the first slice of the
// weapon component moved out of its graph. It holds the shot's server half:
//
//     owning client                      server
//     Server_Fire(AimPoint)  -------->   _Validate: a point that is a number
//                                        the guard's Allow, AsksServed + 1,
//                                        its AimAllowed; a gun in a living
//                                        hand, a round in it, cooled?
//                                        the round, the deadline, the record
//                                        ShotFired(AimPoint)        (graph)
//                                          the sound told, the muzzle, the
//                                          draw in the cloud, then
//                                          FirePellets(...)         (C++)
//                                            ShotTrace, the zone, TakeHit
//                                            PelletFlew(...)        (graph)
//                                              tracer, blood or chips
//                                          the batch told, the noise
//
// The graph keeps what is for the eye and the ear, the muzzle (the aim's own
// sub-graph) and the draw inside the accuracy cloud. In single player the one
// machine has authority and Server_Fire is a plain call.
//
// What is carried stays where it was: Held is the component's Blueprint
// variable, and Loaded, Reserve and NextFireTime are the item's (one magazine
// and one deadline per gun, and the item is a Blueprint actor still). They
// are read and written here by name, as the inventory's record reads them,
// and a round spent marks that record. The health component is a Blueprint
// too (until W3): its tables are read by name and TakeHit called by name.
// The names are properties of the class defaults, written by
// Scripts/combat/weapon_component/native.py from the builders' constants.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OtherworldWeaponComponentBase.generated.h"

class AController;

UCLASS(Abstract, Blueprintable, ClassGroup = (Otherworld))
class OTHERWORLD_API UOtherworldWeaponComponentBase : public UActorComponent
{
	GENERATED_BODY()

public:
	/**
	 * The owning client's trigger, with where its reticle rests. Refused by
	 * _Validate (the connection is closed) only for a point that is not a
	 * number; every other refusal is quiet and counted served, which hands
	 * the client's predicted round back.
	 */
	UFUNCTION(Server, Reliable, WithValidation, BlueprintCallable, Category = "Otherworld|Shot")
	void Server_Fire(FVector AimPoint);

	/**
	 * A shot the server let through, its round spent and its deadline
	 * stamped: the graph tells the sound, finds the muzzle, draws the shot's
	 * direction and calls FirePellets.
	 */
	UFUNCTION(BlueprintImplementableEvent, Category = "Otherworld|Shot")
	void ShotFired(FVector AimPoint);

	/**
	 * The shot's pellets, each inside SpreadDegrees of Direction and traced
	 * Range from Muzzle (UOtherworldShotLibrary::ShotTrace, so a remote
	 * shooter's are judged where the others stood when it fired). One that
	 * strikes a body hands Damage times the body's zone to its TakeHit.
	 * Every pellet is then told to the graph as PelletFlew. Nothing without
	 * authority.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Shot")
	void FirePellets(AActor* Gun, FVector Muzzle, FVector Direction, int32 Pellets, float SpreadDegrees,
		float Range, float Damage, float MaxRewindSeconds, float ExtraRewindSeconds);

	/**
	 * One pellet, for the eye: the line it flew (Start to Stop, bStopped if
	 * it ended on something), and what it did there. bHurt: a body took
	 * Damage (its zone's Worth already in it; Bone the bone struck, bHead if
	 * one of the head's). bScenery: a thing without health. Neither: it
	 * crossed a character's capsule and passed the body by. Point and Normal
	 * are where a burst goes.
	 */
	UFUNCTION(BlueprintImplementableEvent, Category = "Otherworld|Shot")
	void PelletFlew(FVector Start, FVector Stop, bool bStopped, FVector Point, FVector Normal, bool bHurt,
		bool bScenery, FName Bone, bool bHead, float Damage, float Worth);

	// How early, by the server's clock, a shot may arrive and still be fired
	// (Scripts/combat/shot_vars.py, FIRE_GRACE_S).
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot")
	float FireGraceSeconds = 0.1f;

	// The guard's name for the shot (Scripts/net/guard_consts.py's row).
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot")
	FName FireEventName = TEXT("Server_Fire");

	// The component's own Blueprint variables.
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName HeldVar = TEXT("Held");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName AsksServedVar = TEXT("AsksServed");

	// The held item's.
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemMeleeVar = TEXT("Melee");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemConsumableVar = TEXT("Consumable");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemLightsVar = TEXT("Lights");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemUsesAmmoVar = TEXT("UsesAmmo");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemLoadedVar = TEXT("Loaded");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemNextFireTimeVar = TEXT("NextFireTime");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemFireIntervalVar = TEXT("FireInterval");

	// The health component (the shooter's own, and a struck body's): its
	// class, which a body is asked for as the graph asked
	// (GetComponentByClass), and its event and variables.
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	TSubclassOf<UActorComponent> HealthClass;

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName TakeHitEvent = TEXT("TakeHit");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName HealthVar = TEXT("Health");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName HealthDeadVar = TEXT("Dead");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName HeadBonesVar = TEXT("HeadBones");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName LimbBonesVar = TEXT("LimbBones");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName HeadMultiplierVar = TEXT("HeadMultiplier");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName LimbMultiplierVar = TEXT("LimbMultiplier");

	// For the probes: shots this component fired, and requests it refused,
	// on the machine with authority.
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Shot")
	int32 ShotsFired = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Shot")
	int32 ShotsRefused = 0;

private:
	/** The actor's component that takes hits (its HealthClass one), or none. */
	UActorComponent* HealthOf(const AActor* Actor) const;

	/** Whether the shot may be fired now: a gun in a living hand, a round in it, cooled. */
	bool MayFire(AActor* Gun) const;

	/** TakeHit(Amount, From, InstigatedBy, Cause) on a health component, by name. */
	void HandHit(UActorComponent* Health, float Amount, const FVector& From, AController* By, AActor* Cause) const;
};
