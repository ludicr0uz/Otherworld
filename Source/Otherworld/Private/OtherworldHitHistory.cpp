#include "OtherworldHitHistory.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/BodySetup.h"

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
	for (TActorIterator<ACharacter> It(GetWorld()); It; ++It)
	{
		ACharacter* Character = *It;
		if (!IsValid(Character))
		{
			continue;
		}
		const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
		const USkeletalMeshComponent* Mesh = Character->GetMesh();
		if (!Capsule || !Mesh)
		{
			continue;
		}
		FOtherworldCharacterHistory* History = Histories.FindByPredicate(
			[Character](const FOtherworldCharacterHistory& H) { return H.Character.Get() == Character; });
		if (!History)
		{
			History = &Histories.AddDefaulted_GetRef();
			History->Character = Character;
		}

		FOtherworldBodySample Sample;
		Sample.Time = Now;
		const bool bCapsuleBody = Capsule->BodyInstance.IsValidBodyInstance();
		Sample.bShootable = bCapsuleBody && Capsule->IsQueryCollisionEnabled()
			&& Capsule->GetCollisionResponseToChannel(ECC_Visibility) == ECR_Block;
		Sample.Capsule = bCapsuleBody ? Capsule->BodyInstance.GetUnrealWorldTransform()
									  : Capsule->GetComponentTransform();
		Sample.Bodies.Reserve(Mesh->Bodies.Num());
		for (const FBodyInstance* Body : Mesh->Bodies)
		{
			Sample.Bodies.Add(Body && Body->IsValidBodyInstance() ? Body->GetUnrealWorldTransform()
																  : FTransform::Identity);
		}
		History->Samples.Add(MoveTemp(Sample));

		int32 Stale = 0;
		while (Stale + 1 < History->Samples.Num() && History->Samples[Stale + 1].Time <= Now - HistorySeconds)
		{
			++Stale;
		}
		if (Stale > 0)
		{
			History->Samples.RemoveAt(0, Stale, EAllowShrinking::No);
		}
	}
	Histories.RemoveAll([](const FOtherworldCharacterHistory& H) { return !H.Character.IsValid(); });
}

void UOtherworldHitHistory::CharactersRecorded(TArray<AActor*>& Out) const
{
	for (const FOtherworldCharacterHistory& H : Histories)
	{
		if (ACharacter* Character = H.Character.Get())
		{
			Out.Add(Character);
		}
	}
}

const FOtherworldCharacterHistory* UOtherworldHitHistory::HistoryOf(const AActor* Character) const
{
	return Histories.FindByPredicate(
		[Character](const FOtherworldCharacterHistory& H) { return H.Character.Get() == Character; });
}

int32 UOtherworldHitHistory::SampleCount(const AActor* Character) const
{
	const FOtherworldCharacterHistory* History = HistoryOf(Character);
	return History ? History->Samples.Num() : 0;
}

bool UOtherworldHitHistory::SampleAt(const FOtherworldCharacterHistory& History, double At, FOtherworldBodySample& Out)
{
	const TArray<FOtherworldBodySample>& S = History.Samples;
	if (S.Num() == 0)
	{
		return false;
	}
	// Older than the history: the oldest sample, the cap. Newer than the
	// newest: now.
	if (At <= S[0].Time)
	{
		Out = S[0];
		return true;
	}
	if (At >= S.Last().Time)
	{
		Out = S.Last();
		return true;
	}
	int32 i = 0;
	while (i + 1 < S.Num() && S[i + 1].Time < At)
	{
		++i;
	}
	const FOtherworldBodySample& A = S[i];
	const FOtherworldBodySample& B = S[i + 1];
	const double Span = B.Time - A.Time;
	const float Alpha = Span > 0.0 ? static_cast<float>((At - A.Time) / Span) : 1.f;
	if (A.Bodies.Num() != B.Bodies.Num())
	{
		Out = Alpha < 0.5f ? A : B;
		return true;
	}
	Out.Time = At;
	Out.bShootable = (Alpha < 0.5f ? A : B).bShootable;
	Out.Capsule.Blend(A.Capsule, B.Capsule, Alpha);
	Out.Bodies.SetNum(A.Bodies.Num());
	for (int32 b = 0; b < A.Bodies.Num(); ++b)
	{
		Out.Bodies[b].Blend(A.Bodies[b], B.Bodies[b], Alpha);
	}
	return true;
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

bool UOtherworldHitHistory::TraceRewound(ACharacter* Character, double At, const FVector& Start, const FVector& End,
	FHitResult& OutCapsule, bool& bOutBody, FName& OutBone, FVector& OutBodyPoint) const
{
	bOutBody = false;
	OutBone = NAME_None;
	OutBodyPoint = FVector::ZeroVector;
	const FOtherworldCharacterHistory* History = HistoryOf(Character);
	if (!History)
	{
		return false;
	}
	FOtherworldBodySample Sample;
	if (!SampleAt(*History, At, Sample) || !Sample.bShootable)
	{
		return false;
	}
	UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
	if (!Capsule || !Capsule->BodyInstance.IsValidBodyInstance()
		|| !TraceBodyThen(Capsule->BodyInstance, Sample.Capsule, Start, End, OutCapsule))
	{
		return false;
	}
	OutCapsule.bBlockingHit = true;
	OutCapsule.HitObjectHandle = FActorInstanceHandle(Character);
	OutCapsule.Component = Capsule;

	USkeletalMeshComponent* Mesh = Character->GetMesh();
	if (!Mesh || Mesh->Bodies.Num() != Sample.Bodies.Num())
	{
		return true;
	}
	float Best = TNumericLimits<float>::Max();
	for (int32 b = 0; b < Mesh->Bodies.Num(); ++b)
	{
		const FBodyInstance* Body = Mesh->Bodies[b];
		if (!Body || !Body->IsValidBodyInstance())
		{
			continue;
		}
		FHitResult Hit;
		if (TraceBodyThen(*Body, Sample.Bodies[b], Start, End, Hit) && Hit.Time < Best)
		{
			Best = Hit.Time;
			bOutBody = true;
			OutBone = Hit.BoneName.IsNone() && Body->BodySetup.IsValid() ? Body->BodySetup->BoneName : Hit.BoneName;
			OutBodyPoint = Hit.Location;
		}
	}
	return true;
}
