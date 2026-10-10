// The native parent of BP_WeaponComponent (task W1): the weapon component
// moved out of its graph a slice at a time. It holds the shot's server half:
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
// and the reload (task W2):
//
//     owning client                      server
//     R: ReloadNow (its prediction)
//        Server_Reload       -------->   the guard's Allow, AsksServed + 1
//                                        ReloadNow
//                                          a gun in a living hand?
//                                          ReloadTake, worked out ONCE
//                                          Loaded, Reserve, the deadline,
//                                          the record
//                                          Reloaded()               (graph)
//                                            the clack, told or predicted
//
// The graph keeps what is for the eye and the ear, the keys, the muzzle (the
// aim's own sub-graph) and the draw inside the accuracy cloud. In single
// player the one machine has authority and each request is a plain call.
//
// What is carried stays where it was: Held is the component's Blueprint
// variable, and Loaded, Reserve and NextFireTime are the item's (one magazine
// and one deadline per gun, and the item is a Blueprint actor still). They
// are read and written here by name, as the inventory's record reads them,
// and a round spent marks that record. A struck body's TakeHit is its
// UOtherworldHealthComponent's (W3); its zone tables are that Blueprint's
// variables, read by name.
// The names are properties of the class defaults, written by
// Scripts/combat/weapon_component/native.py from the builders' constants.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OtherworldWeaponComponentBase.generated.h"

class AController;
class UOtherworldHealthComponent;

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

	/**
	 * The owning client's R. Asks the guard, counts the ask served whatever
	 * it said (a refused reload is answered like any other the server did
	 * not do), then ReloadNow.
	 */
	UFUNCTION(Server, Reliable, BlueprintCallable, Category = "Otherworld|Shot")
	void Server_Reload();

	/**
	 * The reload, on this machine's copy of the held gun: the server's from
	 * Server_Reload, and the owning client's own call, its prediction.
	 * Nothing without a gun in a living hand, or when no round would move
	 * (no pause either). Otherwise the magazine, the reserve, the deadline
	 * (the gun's ReloadSeconds from now, on the one NextFireTime the
	 * interval between shots uses), the record's mark, and Reloaded.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Shot")
	void ReloadNow();

	/** A reload that moved rounds: the graph's clack, told or predicted. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Otherworld|Shot")
	void Reloaded();

	/**
	 * How many rounds a reload of Gun moves now: the magazine's gap, and no
	 * more than the reserve holds. A gun with an endless reserve (the
	 * pistol) fills the whole gap, even from a count below zero. 0 for a
	 * thing without ammunition. Not a Blueprint node: a pure one read again
	 * after Loaded rose charged the reserve less than the magazine gained.
	 */
	int32 ReloadTake(const AActor* Gun) const;

	// How early, by the server's clock, a shot may arrive and still be fired
	// (Scripts/combat/shot_vars.py, FIRE_GRACE_S).
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot")
	float FireGraceSeconds = 0.1f;

	// The guard's name for the shot (Scripts/net/guard_consts.py's row).
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot")
	FName FireEventName = TEXT("Server_Fire");

	// The guard's name for the reload.
	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot")
	FName ReloadEventName = TEXT("Server_Reload");

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

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemMagazineSizeVar = TEXT("MagazineSize");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemReserveVar = TEXT("Reserve");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemInfiniteReserveVar = TEXT("InfiniteReserve");

	UPROPERTY(EditAnywhere, Category = "Otherworld|Shot|Names")
	FName ItemReloadSecondsVar = TEXT("ReloadSeconds");

	// The struck body's health component (UOtherworldHealthComponent, W3):
	// its zone tables are its Blueprint's variables still.
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

	// ...and reloads that moved rounds on this machine (a client's are its
	// predictions).
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Shot")
	int32 Reloads = 0;

private:
	/** The actor's component that takes hits, or none. */
	UOtherworldHealthComponent* HealthOf(const AActor* Actor) const;

	/** Whether the owner lives: an owner with no health component does. */
	bool OwnerAlive() const;

	/** Whether the shot may be fired now: a gun in a living hand, a round in it, cooled. */
	bool MayFire(AActor* Gun) const;
};
