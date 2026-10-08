#include "OtherworldHitHistory.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/BodySetup.h"

namespace
{
	/** Whether this frame posed the mesh anew: false on a frame its update rate skipped (OtherworldServerPose.h). */
	bool PosedThisFrame(const USkeletalMeshComponent& Mesh)
	{
		const FAnimUpdateRateParameters* Rate = Mesh.AnimUpdateRateParams;
		return !Rate || !Mesh.ShouldUseUpdateRateOptimizations() || !Rate->DoEvaluationRateOptimizations()
			|| !Rate->ShouldSkipEvaluation();
	}

	/** Drops the oldest entries of a ring while the one after them is already HistorySeconds old. */
	void DropStale(const double* Times, int32& Start, int32& Num, double Horizon)
	{
		constexpr int32 Capacity = FOtherworldCharacterHistory::Capacity;
		while (Num > 1 && Times[(Start + 1) % Capacity] <= Horizon)
		{
			Start = (Start + 1) % Capacity;
			--Num;
		}
	}

	/** The slot the next entry of a ring is written to: the one past the newest, or the oldest's when full. */
	int32 Push(int32& Start, int32& Num)
	{
		constexpr int32 Capacity = FOtherworldCharacterHistory::Capacity;
		if (Num == Capacity)
		{
			const int32 Slot = Start;
			Start = (Start + 1) % Capacity;
			return Slot;
		}
		return (Start + Num++) % Capacity;
	}
}

void UOtherworldHitHistory::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	// After every actor has ticked: the animation has posed the bones and the
	// kinematic bodies follow them, so this is where the frame's bodies are.
	TickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(this, &UOtherworldHitHistory::OnPostActorTick);
}

void UOtherworldHitHistory::Deinitialize()
{
	FWorldDelegates::OnWorldPostActorTick.Remove(TickHandle);
	Histories.Empty();
	RecordedActors.Empty();
	Super::Deinitialize();
}

bool UOtherworldHitHistory::IsRecording() const
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}
	const ENetMode Mode = World->GetNetMode();
	return Mode == NM_DedicatedServer || Mode == NM_ListenServer;
}

void UOtherworldHitHistory::OnPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
	if (World != GetWorld() || TickType == LEVELTICK_PauseTick || !IsRecording())
	{
		return;
	}
	Record(World->GetTimeSeconds());
}

void UOtherworldHitHistory::Record(double Now)
{
	constexpr int32 Capacity = FOtherworldCharacterHistory::Capacity;
	// A frame sooner than this after the last is not kept: a second always fits the ring.
	const double MinInterval = 0.9 / FramesPerSecond;
	const double Horizon = Now - HistorySeconds;

	for (TActorIterator<ACharacter> It(GetWorld()); It; ++It)
	{
		ACharacter* Character = *It;
		const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
		const USkeletalMeshComponent* Mesh = Character->GetMesh();
		if (!IsValid(Character) || !Capsule || !Mesh)
		{
			continue;
		}
		TUniquePtr<FOtherworldCharacterHistory>& Held = Histories.FindOrAdd(FObjectKey(Character));
		if (!Held)
		{
			Held = MakeUnique<FOtherworldCharacterHistory>();
			Held->Character = Character;
		}
		FOtherworldCharacterHistory& H = *Held;
		if (H.FrameNum > 0 && Now - H.FrameTimes[H.Frame(H.FrameNum - 1)] < MinInterval)
		{
			continue;
		}

		const bool bCapsuleBody = Capsule->BodyInstance.IsValidBodyInstance();
		const bool bShootable = bCapsuleBody && Capsule->IsQueryCollisionEnabled()
			&& Capsule->GetCollisionResponseToChannel(ECC_Visibility) == ECR_Block;
		const FTransform& MeshWorld = Mesh->GetComponentTransform();
		const FTransform MeshFrame(MeshWorld.GetRotation(), MeshWorld.GetLocation());

		const int32 f = Push(H.FrameStart, H.FrameNum);
		H.FrameTimes[f] = Now;
		H.bShootable[f] = bShootable;
		H.Capsules[f] = bCapsuleBody ? Capsule->BodyInstance.GetUnrealWorldTransform()
									 : Capsule->GetComponentTransform();
		H.MeshFrames[f] = MeshFrame;
		DropStale(H.FrameTimes, H.FrameStart, H.FrameNum, Horizon);

		// The bodies: only of a character a pellet can stop on (a corpse's
		// capsule stops none), and only when the mesh was posed anew.
		const int32 Bodies = Mesh->Bodies.Num();
		if (Bodies != H.BodyCount)
		{
			// Collision toggled, or the first frame: the poses kept no longer fit.
			H.BodyCount = Bodies;
			H.PoseBodies.SetNumUninitialized(Capacity * Bodies, EAllowShrinking::No);
			H.PoseStart = H.PoseNum = 0;
		}
		if (bShootable && Bodies > 0 && (H.PoseNum == 0 || PosedThisFrame(*Mesh)))
		{
			const int32 p = Push(H.PoseStart, H.PoseNum);
			H.PoseTimes[p] = Now;
			FTransform* Out = &H.PoseBodies[p * Bodies];
			for (int32 b = 0; b < Bodies; ++b)
			{
				const FBodyInstance* Body = Mesh->Bodies[b];
				Out[b] = Body && Body->IsValidBodyInstance()
					? Body->GetUnrealWorldTransform().GetRelativeTransform(MeshFrame)
					: FTransform::Identity;
			}
		}
		DropStale(H.PoseTimes, H.PoseStart, H.PoseNum, Horizon);
	}

	RecordedActors.Reset();
	for (auto It = Histories.CreateIterator(); It; ++It)
	{
		const ACharacter* Character = It.Value()->Character.Get();
		if (!Character)
		{
			It.RemoveCurrent();
			continue;
		}
		RecordedActors.Add(Character);
	}
}

void UOtherworldHitHistory::CharactersRecorded(TArray<AActor*>& Out) const
{
	for (const auto& Pair : Histories)
	{
		if (ACharacter* Character = Pair.Value->Character.Get())
		{
			Out.Add(Character);
		}
	}
}

const FOtherworldCharacterHistory* UOtherworldHitHistory::HistoryOf(const AActor* Character) const
{
	const TUniquePtr<FOtherworldCharacterHistory>* Held = Histories.Find(FObjectKey(Character));
	return Held ? Held->Get() : nullptr;
}

int32 UOtherworldHitHistory::SampleCount(const AActor* Character) const
{
	const FOtherworldCharacterHistory* History = HistoryOf(Character);
	return History ? History->FrameNum : 0;
}

int32 UOtherworldHitHistory::PoseCount(const AActor* Character) const
{
	const FOtherworldCharacterHistory* History = HistoryOf(Character);
	return History ? History->PoseNum : 0;
}

void UOtherworldHitHistory::Either(const double* Times, int32 Start, int32 Num, double At,
	int32& OutA, int32& OutB, float& OutAlpha)
{
	constexpr int32 Capacity = FOtherworldCharacterHistory::Capacity;
	const int32 Oldest = Start;
	const int32 Newest = (Start + Num - 1) % Capacity;
	OutAlpha = 0.f;
	// Older than the ring: its oldest entry, the cap. Newer than the newest: now.
	if (At <= Times[Oldest])
	{
		OutA = OutB = Oldest;
		return;
	}
	if (At >= Times[Newest])
	{
		OutA = OutB = Newest;
		return;
	}
	int32 i = 0;
	while (i + 2 < Num && Times[(Start + i + 1) % Capacity] < At)
	{
		++i;
	}
	OutA = (Start + i) % Capacity;
	OutB = (Start + i + 1) % Capacity;
	const double Span = Times[OutB] - Times[OutA];
	OutAlpha = Span > 0.0 ? static_cast<float>((At - Times[OutA]) / Span) : 1.f;
}

bool UOtherworldHitHistory::TraceBodyThen(const FBodyInstance& Body, const FTransform& Then,
	const FVector& Start, const FVector& End, FHitResult& OutHit)
{
	// X in the world as it was -> X in the body's own frame -> where that
	// point of the body is now; and the hit the other way round.
	const FTransform Now = Body.GetUnrealWorldTransform();
	const FTransform ThenToNow = Then.Inverse() * Now;
	const FTransform NowToThen = Now.Inverse() * Then;
	FHitResult Hit;
	if (!Body.LineTrace(Hit, ThenToNow.TransformPosition(Start), ThenToNow.TransformPosition(End),
			/*bTraceComplex*/ false, /*bReturnPhysicalMaterial*/ true))
	{
		return false;
	}
	OutHit = Hit;
	OutHit.Location = NowToThen.TransformPosition(Hit.Location);
	OutHit.ImpactPoint = NowToThen.TransformPosition(Hit.ImpactPoint);
	OutHit.Normal = NowToThen.TransformVectorNoScale(Hit.Normal);
	OutHit.ImpactNormal = NowToThen.TransformVectorNoScale(Hit.ImpactNormal);
	OutHit.TraceStart = Start;
	OutHit.TraceEnd = End;
	return true;
}

bool UOtherworldHitHistory::TraceRewound(const AActor* Shooter, double At, const FVector& Start, const FVector& End,
	float Reach, FHitResult& OutCapsule, bool& bOutBody, FName& OutBone, FVector& OutBodyPoint) const
{
	bOutBody = false;
	OutBone = NAME_None;
	OutBodyPoint = FVector::ZeroVector;

	// Every capsule where it was, from the frames alone; the nearest wins.
	const FOtherworldCharacterHistory* Struck = nullptr;
	FTransform StruckFrame;
	for (const auto& Pair : Histories)
	{
		const FOtherworldCharacterHistory& H = *Pair.Value;
		ACharacter* Character = H.Character.Get();
		if (!Character || Character == Shooter || H.FrameNum == 0)
		{
			continue;
		}
		int32 A, B;
		float Alpha;
		Either(H.FrameTimes, H.FrameStart, H.FrameNum, At, A, B, Alpha);
		if (!H.bShootable[Alpha < 0.5f ? A : B])
		{
			continue;
		}
		FTransform CapsuleThen = H.Capsules[A];
		if (A != B)
		{
			CapsuleThen.Blend(H.Capsules[A], H.Capsules[B], Alpha);
		}
		// Far off the line: no trace at all. The bound is the capsule's own sphere.
		const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
		if (!Capsule || !Capsule->BodyInstance.IsValidBodyInstance())
		{
			continue;
		}
		const float Bound = Capsule->GetScaledCapsuleHalfHeight() + Capsule->GetScaledCapsuleRadius();
		if (FMath::PointDistToSegmentSquared(CapsuleThen.GetLocation(), Start, End) > FMath::Square(Bound))
		{
			continue;
		}
		FHitResult Hit;
		if (!TraceBodyThen(Capsule->BodyInstance, CapsuleThen, Start, End, Hit) || Hit.Distance >= Reach)
		{
			continue;
		}
		Reach = Hit.Distance;
		Struck = &H;
		OutCapsule = Hit;
		OutCapsule.bBlockingHit = true;
		OutCapsule.HitObjectHandle = FActorInstanceHandle(Character);
		OutCapsule.Component = Character->GetCapsuleComponent();
		StruckFrame = H.MeshFrames[A];
		if (A != B)
		{
			StruckFrame.Blend(H.MeshFrames[A], H.MeshFrames[B], Alpha);
		}
	}
	if (!Struck)
	{
		return false;
	}
	// Only now the bodies, and only the struck character's.
	if (USkeletalMeshComponent* Mesh = Struck->Character->GetMesh())
	{
		BodiesThen(*Struck, *Mesh, At, StruckFrame, Start, End, bOutBody, OutBone, OutBodyPoint);
	}
	return true;
}

void UOtherworldHitHistory::BodiesThen(const FOtherworldCharacterHistory& History, USkeletalMeshComponent& Mesh,
	double At, const FTransform& MeshFrame, const FVector& Start, const FVector& End,
	bool& bOutBody, FName& OutBone, FVector& OutBodyPoint) const
{
	// A mesh whose bodies are not the poses' (collision toggled since) is
	// judged by its capsule alone.
	const int32 Bodies = History.BodyCount;
	if (History.PoseNum == 0 || Mesh.Bodies.Num() != Bodies)
	{
		return;
	}
	int32 A, B;
	float Alpha;
	Either(History.PoseTimes, History.PoseStart, History.PoseNum, At, A, B, Alpha);
	const FTransform* PoseA = &History.PoseBodies[A * Bodies];
	const FTransform* PoseB = &History.PoseBodies[B * Bodies];
	float Best = TNumericLimits<float>::Max();
	for (int32 b = 0; b < Bodies; ++b)
	{
		const FBodyInstance* Body = Mesh.Bodies[b];
		if (!Body || !Body->IsValidBodyInstance())
		{
			continue;
		}
		FTransform InMesh = PoseA[b];
		if (A != B)
		{
			InMesh.Blend(PoseA[b], PoseB[b], Alpha);
		}
		FHitResult Hit;
		if (TraceBodyThen(*Body, InMesh * MeshFrame, Start, End, Hit) && Hit.Time < Best)
		{
			Best = Hit.Time;
			bOutBody = true;
			OutBone = Hit.BoneName.IsNone() && Body->BodySetup.IsValid() ? Body->BodySetup->BoneName : Hit.BoneName;
			OutBodyPoint = Hit.Location;
		}
	}
}

bool UOtherworldHitHistory::BodyThen(const AActor* Character, FName Bone, double At, FVector& OutLocation) const
{
	const FOtherworldCharacterHistory* History = HistoryOf(Character);
	const ACharacter* Body = History ? History->Character.Get() : nullptr;
	const USkeletalMeshComponent* Mesh = Body ? Body->GetMesh() : nullptr;
	if (!Mesh || History->FrameNum == 0 || History->PoseNum == 0 || Mesh->Bodies.Num() != History->BodyCount)
	{
		return false;
	}
	int32 Index = INDEX_NONE;
	for (int32 b = 0; b < Mesh->Bodies.Num(); ++b)
	{
		const FBodyInstance* Instance = Mesh->Bodies[b];
		if (Instance && Instance->BodySetup.IsValid() && Instance->BodySetup->BoneName == Bone)
		{
			Index = b;
			break;
		}
	}
	if (Index == INDEX_NONE)
	{
		return false;
	}
	int32 A, B;
	float Alpha;
	Either(History->FrameTimes, History->FrameStart, History->FrameNum, At, A, B, Alpha);
	FTransform MeshFrame = History->MeshFrames[A];
	if (A != B)
	{
		MeshFrame.Blend(History->MeshFrames[A], History->MeshFrames[B], Alpha);
	}
	Either(History->PoseTimes, History->PoseStart, History->PoseNum, At, A, B, Alpha);
	FTransform InMesh = History->PoseBodies[A * History->BodyCount + Index];
	if (A != B)
	{
		InMesh.Blend(History->PoseBodies[A * History->BodyCount + Index],
			History->PoseBodies[B * History->BodyCount + Index], Alpha);
	}
	OutLocation = (InMesh * MeshFrame).GetLocation();
	return true;
}
