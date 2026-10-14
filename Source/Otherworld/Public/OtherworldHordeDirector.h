// The Horde Survival level's difficulty (Scripts/forest_generator/npc_horde.py):
// how many monsters the level holds, rising a level every StepSeconds of play.
// Level L (1 from the start, at most MaxLevel) holds FirstCount + PerLevel x (L - 1)
// wanderers, of which L / WendigoEveryLevels are wendigos and the rest zombies:
// 4 zombies at level 1, 6 at 2, 8 at 3, 9 and a wendigo at 4, 16 and 2 at 8.
//
// One is placed in the level (Scripts/forest_import/fort.py), its numbers
// written there from npc_horde.py. Once a second, wherever the world is not a
// client's, and per creature:
//   - more living than the level holds (the level's own placed cast, at the
//     start): the furthest from the players are removed;
//   - fewer, for Delay seconds (none at the first pass): one is spawned, in the
//     band round a living player, on the navmesh and out of sight
//     (OtherworldSpawnPoint, as the server's population budget places one);
//   - every one kept has its BP_HealthComponent's replacement switched off
//     (the variable named ReplacementVar, emptied by name): the director owns
//     the count, so a kill is replaced by it, not by the single-player
//     replacement as well.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OtherworldHordeDirector.generated.h"

class APawn;

UCLASS()
class OTHERWORLD_API AOtherworldHordeDirector : public AActor
{
	GENERATED_BODY()

public:
	AOtherworldHordeDirector();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	TSubclassOf<APawn> ZombieClass;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	TSubclassOf<APawn> WendigoClass;

	/** Seconds of play from one level to the next. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	float StepSeconds = 180.f;

	/** Monsters at level 1, and how many more each level holds. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	int32 FirstCount = 4;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	int32 PerLevel = 2;

	/** One wendigo for every this many levels. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	int32 WendigoEveryLevels = 4;

	/** The level stops rising here. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	int32 MaxLevel = 20;

	/** Where a new one appears: this far from the player it is for, in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	float SpawnMin = 7500.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	float SpawnMax = 10000.f;

	/** How long the level stays one short before one more comes, in seconds. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	float Delay = 10.f;

	/** The health component's variable holding what a dead wanderer is replaced by. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Horde")
	FName ReplacementVar = TEXT("RespawnClass");

	/** The level now (0 before the first pass), and for the probes what was spawned and removed. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Horde")
	int32 Level = 0;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Horde")
	int32 Spawned = 0;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Horde")
	int32 Removed = 0;

	/** Living wanderers whose replacement it switched off. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Horde")
	int32 ReplacementsOff = 0;

	/** The level after Seconds of play. */
	UFUNCTION(BlueprintPure, Category = "Horde")
	int32 LevelAt(float Seconds) const;

	/** How many monsters, and of them wendigos and zombies, a level holds. */
	UFUNCTION(BlueprintPure, Category = "Horde")
	int32 TotalAt(int32 AtLevel) const;

	UFUNCTION(BlueprintPure, Category = "Horde")
	int32 WendigosAt(int32 AtLevel) const;

	UFUNCTION(BlueprintPure, Category = "Horde")
	int32 ZombiesAt(int32 AtLevel) const;

	/** Seconds of play the level is counted from. */
	UFUNCTION(BlueprintPure, Category = "Horde")
	float PlaySeconds() const;

	/** For the probes: the living wanderers of a class (and its children). */
	UFUNCTION(BlueprintCallable, Category = "Horde")
	int32 LivingOf(TSubclassOf<APawn> Class) const;

	/** For the probes: count the level from now, as if play had just begun. */
	UFUNCTION(BlueprintCallable, Category = "Horde")
	void Restart();

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

private:
	void Pass();
	void Hold(TSubclassOf<APawn> Class, int32 Want, double& DueAt, const TArray<APawn*>& Players);
	void Living(TSubclassOf<APawn> Class, TArray<APawn*>& Out) const;
	void ReplacementOff(APawn* Wanderer);

	double StartedAt = 0.0;
	double ZombieDueAt = -1.0;
	double WendigoDueAt = -1.0;
	bool bFirstPass = true;
};
