#include "OtherworldServerPose.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "OtherworldCharacter.h"

void UOtherworldServerPose::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	TickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(this, &UOtherworldServerPose::OnPostActorTick);
}

void UOtherworldServerPose::Deinitialize()
{
	FWorldDelegates::OnWorldPostActorTick.Remove(TickHandle);
	Bodies.Empty();
	Super::Deinitialize();
}

void UOtherworldServerPose::Throttle(ACharacter* Body, float FullWithinCm, float FarHz, float NobodyBeyondCm,
	float NobodyHz)
{
	USkeletalMeshComponent* Mesh = Body ? Body->GetMesh() : nullptr;
	const UWorld* World = GetWorld();
	if (!Mesh || !World || World->GetNetMode() != NM_DedicatedServer)
	{
		return;
	}
	// The mesh the game runs on: posed though never drawn, at a rate of its own.
	Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Mesh->bEnableUpdateRateOptimizations = true;
	// Everything else skinned on the actor is only ever drawn.
	TInlineComponentArray<USkinnedMeshComponent*> Skinned(Body);
	for (USkinnedMeshComponent* Other : Skinned)
	{
		if (Other != Mesh)
		{
			Other->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
			Other->SetComponentTickEnabled(false);
		}
	}

	FOtherworldPosedBody* Entry = Bodies.FindByPredicate(
		[Body](const FOtherworldPosedBody& B) { return B.Character.Get() == Body; });
	if (!Entry)
	{
		Entry = &Bodies.AddDefaulted_GetRef();
		Entry->Character = Body;
	}
	Entry->FullWithinCm = FullWithinCm;
	Entry->FarHz = FarHz;
	Entry->NobodyBeyondCm = NobodyBeyondCm;
	Entry->NobodyHz = NobodyHz;
	// Decided at the next review; until then the engine's default stands.
	NextReview = 0.0;
}

int32 UOtherworldServerPose::EveryFrames(const AActor* Body) const
{
	const FOtherworldPosedBody* Entry = Bodies.FindByPredicate(
		[Body](const FOtherworldPosedBody& B) { return B.Character.Get() == Body; });
	return Entry ? Entry->EveryFrames : 0;
}

void UOtherworldServerPose::OnPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
	if (World != GetWorld() || Bodies.Num() == 0)
	{
		return;
	}
	FrameSeconds = FMath::Lerp(FrameSeconds, FMath::Clamp(DeltaSeconds, 1.f / 240.f, 0.5f), 0.1f);
	const double Now = World->GetRealTimeSeconds();
	if (Now >= NextReview)
	{
		NextReview = Now + ReviewSeconds;
		Review();
	}
}

void UOtherworldServerPose::Review()
{
	Bodies.RemoveAllSwap([](const FOtherworldPosedBody& B) { return !B.Character.IsValid(); },
		EAllowShrinking::No);

	// Where the players stand: the bodies a player is (or a load test's bot
	// stands in for), alive. A ragdoll is nobody.
	Players.Reset();
	PlayerBodies.Reset();
	for (const FOtherworldPosedBody& B : Bodies)
	{
		const ACharacter* Character = B.Character.Get();
		const USkeletalMeshComponent* Mesh = Character->GetMesh();
		if (Character->IsA<AOtherworldCharacter>() && Mesh && !Mesh->IsAnySimulatingPhysics())
		{
			Players.Add(Character->GetActorLocation());
			PlayerBodies.Add(Character);
		}
	}

	for (FOtherworldPosedBody& B : Bodies)
	{
		const ACharacter* Character = B.Character.Get();
		USkeletalMeshComponent* Mesh = Character->GetMesh();
		if (!Mesh)
		{
			continue;
		}
		float Hz = B.NobodyHz;
		if (!Mesh->IsAnySimulatingPhysics())
		{
			// The nearest player other than the body itself.
			const FVector Here = Character->GetActorLocation();
			float NearestSq = TNumericLimits<float>::Max();
			for (int32 i = 0; i < Players.Num(); ++i)
			{
				if (PlayerBodies[i] != Character)
				{
					NearestSq = FMath::Min(NearestSq, static_cast<float>(FVector::DistSquared(Here, Players[i])));
				}
			}
			if (NearestSq <= FMath::Square(B.FullWithinCm))
			{
				Hz = 0.f;
			}
			else if (NearestSq <= FMath::Square(B.NobodyBeyondCm))
			{
				Hz = B.FarHz;
			}
		}
		B.EveryFrames = Hz > 0.f ? FMath::Max(1, FMath::RoundToInt(1.f / (Hz * FrameSeconds))) : 1;
		if (Mesh->AnimUpdateRateParams)
		{
			Mesh->AnimUpdateRateParams->BaseNonRenderedUpdateRate = B.EveryFrames;
		}
	}
}

void UOtherworldPoseLibrary::ThrottleServerPose(ACharacter* Body, float FullWithinCm, float FarHz,
	float NobodyBeyondCm, float NobodyHz)
{
	UWorld* World = Body ? Body->GetWorld() : nullptr;
	if (UOtherworldServerPose* Pose = World ? World->GetSubsystem<UOtherworldServerPose>() : nullptr)
	{
		Pose->Throttle(Body, FullWithinCm, FarHz, NobodyBeyondCm, NobodyHz);
	}
}

int32 UOtherworldPoseLibrary::ServerPoseEveryFrames(const AActor* Body)
{
	const UWorld* World = Body ? Body->GetWorld() : nullptr;
	const UOtherworldServerPose* Pose = World ? World->GetSubsystem<UOtherworldServerPose>() : nullptr;
	return Pose ? Pose->EveryFrames(Body) : 0;
}

int32 UOtherworldPoseLibrary::TickingSkinnedMeshes(const AActor* Body)
{
	int32 Ticking = 0;
	if (Body)
	{
		TInlineComponentArray<USkinnedMeshComponent*> Skinned(Body);
		for (const USkinnedMeshComponent* Mesh : Skinned)
		{
			Ticking += Mesh->IsComponentTickEnabled() ? 1 : 0;
		}
	}
	return Ticking;
}
