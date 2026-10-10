// The native parent of BP_HealthComponent (task W3): the health of a body,
// the player's or a wanderer's, and the one way a blow takes it off.
//
//     any machine                        server (and single player)
//     a blow: TakeHit(Amount, From,  -->  HitCount + 1 where it takes health
//             InstigatedBy, Cause)        Health = max(Health - Amount, 0)
//       (absorbed without authority)      LastDamageTime, LastHitFrom,
//                                         LastInstigator, LastCause,
//                                         DamagedByPlayer
//                                         the graph's Tick sees Health at 0:
//                                         Die()  ->  Dead, OnDied()   (graph)
//     a client
//     Health arrives: OnHealthChanged()                               (graph)
//       a blow or a drain, told by HitCount; the bar, the flinch
//     Dead arrives:   OnDied(), at the component's next tick          (graph)
//       the cry, the collapse, the menu
//
// The graph keeps what dying is (the corpse, the kill, the replacement, the
// player's respawn: Scripts/combat/death.py, player_respawn.py), the drain,
// the world-floor net, the voice and the flinch. They read and write these
// properties as they did the Blueprint's variables of the same names; a
// Blueprint Set of one calls no notify (the engine's Set node calls only a
// Blueprint's own), so OnHealthChanged is a client's alone.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OtherworldHealthComponent.generated.h"

class AController;

UCLASS(Abstract, Blueprintable, ClassGroup = (Otherworld))
class OTHERWORLD_API UOtherworldHealthComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UOtherworldHealthComponent();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

	/**
	 * A blow: Amount off Health, floored at zero, stamped with when, which
	 * way it came (From), who struck it (the controller a kill is credited
	 * to) and with what. HitCount rises where it takes health (Health and
	 * Amount above zero): what a client tells a blow from a drain by.
	 * Nothing without authority.
	 */
	UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category = "Otherworld|Health")
	void TakeHit(double Amount, FVector From, AController* InstigatedBy, AActor* Cause);

	/**
	 * The body has died: Dead, which replicates, and OnDied here. Once, and
	 * nothing without authority. The graph's Tick calls it on the frame it
	 * sees Health at zero, after the drain and the world-floor net.
	 */
	UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category = "Otherworld|Health")
	void Die();

	/** On a client, a Health that arrived. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Otherworld|Health")
	void OnHealthChanged();

	/**
	 * Once on each machine: on the server from Die, on a client on the
	 * component's first tick after Dead arrived (after the graph's Tick).
	 * Never from inside the notify: that runs mid-bunch, before the body's
	 * replicated place is applied, and a body moved and killed in one frame
	 * would fall where it no longer is.
	 */
	UFUNCTION(BlueprintImplementableEvent, Category = "Otherworld|Health")
	void OnDied();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, ReplicatedUsing = OnRep_Health, Category = "Otherworld|Health")
	double Health = 100.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, ReplicatedUsing = OnRep_Dead, Category = "Otherworld|Health")
	bool Dead = false;

	// How many blows have taken health off this body.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Replicated, Category = "Otherworld|Health")
	int32 HitCount = 0;

	// The way the last blow came: the flinch's direction.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Replicated, Category = "Otherworld|Health")
	FVector LastHitFrom = FVector::ZeroVector;

	// When the last blow landed, by this machine's clock (a client stamps
	// its own in the graph): far in the past until one does.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Otherworld|Health")
	double LastDamageTime = -1000.0;

	// A player has struck this body.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Otherworld|Health")
	bool DamagedByPlayer = false;

	// Who struck the last blow, and with what. The server's alone.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Otherworld|Health")
	TObjectPtr<AController> LastInstigator;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Otherworld|Health")
	TObjectPtr<AActor> LastCause;

	/** Whether the body lives: not Dead, and Health above zero. */
	bool IsAlive() const { return !Dead && Health > 0.0; }

protected:
	UFUNCTION()
	void OnRep_Health();

	UFUNCTION()
	void OnRep_Dead();

private:
	bool HasAuthority() const;

	/** OnDied, once on this machine. */
	void TellDied();

	bool bDiedTold = false;

	// Dead arrived on this client and OnDied is owed at the next tick.
	bool bDiedPending = false;
};
