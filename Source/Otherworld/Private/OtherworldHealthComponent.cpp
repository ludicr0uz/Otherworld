#include "OtherworldHealthComponent.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "Net/UnrealNetwork.h"

UOtherworldHealthComponent::UOtherworldHealthComponent()
{
	SetIsReplicatedByDefault(true);
}

void UOtherworldHealthComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	// To everyone: the bar over a wanderer, and another player's flinch and
	// collapse, are drawn on every machine.
	DOREPLIFETIME(UOtherworldHealthComponent, Health);
	DOREPLIFETIME(UOtherworldHealthComponent, Dead);
	DOREPLIFETIME(UOtherworldHealthComponent, HitCount);
	DOREPLIFETIME(UOtherworldHealthComponent, LastHitFrom);
}

bool UOtherworldHealthComponent::HasAuthority() const
{
	const AActor* Owner = GetOwner();
	return Owner && Owner->HasAuthority();
}

void UOtherworldHealthComponent::TickComponent(float DeltaTime, ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	// The graph's Tick first: the death comes where its own death branch
	// stood, after what the frame does to a body that still lived.
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (bDiedPending)
	{
		bDiedPending = false;
		TellDied();
	}
}

void UOtherworldHealthComponent::TakeHit(double Amount, FVector From, AController* InstigatedBy, AActor* Cause)
{
	const UWorld* World = GetWorld();
	if (!HasAuthority() || !World)
	{
		return;
	}
	if (Health > 0.0 && Amount > 0.0)
	{
		++HitCount;
	}
	Health = FMath::Max(Health - Amount, 0.0);
	LastDamageTime = World->GetTimeSeconds();
	LastHitFrom = From;
	LastInstigator = InstigatedBy;
	LastCause = Cause;
	// A wanderer's blow blames no player.
	if (Cast<APlayerController>(InstigatedBy))
	{
		DamagedByPlayer = true;
	}
}

void UOtherworldHealthComponent::Die()
{
	if (!HasAuthority() || Dead)
	{
		return;
	}
	Dead = true;
	TellDied();
}

void UOtherworldHealthComponent::TellDied()
{
	if (bDiedTold)
	{
		return;
	}
	bDiedTold = true;
	OnDied();
}

void UOtherworldHealthComponent::OnRep_Health()
{
	OnHealthChanged();
}

void UOtherworldHealthComponent::OnRep_Dead()
{
	// Told from the tick, not from here (the header says why). A body that
	// arrives dead has not begun play yet: its first tick comes after.
	if (Dead && !bDiedTold)
	{
		bDiedPending = true;
	}
}
