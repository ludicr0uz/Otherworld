#include "OtherworldShotLog.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/Controller.h"
#include "GameFramework/GameStateBase.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "OtherworldHealthComponent.h"
#include "OtherworldHitHistory.h"
#include "PhysicalMaterials/PhysicalMaterial.h"

DEFINE_LOG_CATEGORY_STATIC(LogOtherworldShotLog, Log, All);

static TAutoConsoleVariable<int32> CVarShotLog(
	TEXT("Otherworld.ShotLog"), 0,
	TEXT("1: log every shot the authority judges (SHOT-LOG): the shooter, the aim point, each ")
	TEXT("pellet's line, what stopped it, the body and bone struck, the target's place and the ")
	TEXT("damage. Also on with -ShotLog, or the GameState's DebugShotLog (the menu's Shot log)."));

namespace
{
	// The GameState's switch, a Blueprint variable read by name
	// (Scripts/net/state_consts.py, DebugShotLog).
	const FName GameStateSwitch(TEXT("DebugShotLog"));

	int32 ShotNumber = 0;
	int32 LineCount = 0;
	FString LastBlock;

	FString V(const FVector& At)
	{
		return FString::Printf(TEXT("(%.1f, %.1f, %.1f)"), At.X, At.Y, At.Z);
	}

	// A direction, fine enough to see a tenth of a degree.
	FString D(const FVector& Dir)
	{
		return FString::Printf(TEXT("(%.4f, %.4f, %.4f)"), Dir.X, Dir.Y, Dir.Z);
	}

	FString R(const FRotator& Rot)
	{
		return FString::Printf(TEXT("(P=%.1f Y=%.1f R=%.1f)"), Rot.Pitch, Rot.Yaw, Rot.Roll);
	}

	const TCHAR* NetModeName(const UWorld* World)
	{
		switch (World ? World->GetNetMode() : NM_Standalone)
		{
		case NM_DedicatedServer: return TEXT("server");
		case NM_ListenServer: return TEXT("listen");
		case NM_Client: return TEXT("client");
		default: return TEXT("standalone");
		}
	}

	/** Who an actor is: its name, a player's or an AI's. */
	FString Who(const AActor* Actor)
	{
		const APawn* Pawn = Cast<APawn>(Actor);
		const AController* Controller = Pawn ? Pawn->GetController() : nullptr;
		const TCHAR* Kind = !Controller ? TEXT("no controller")
			: Cast<APlayerController>(Controller) ? (Controller->IsLocalController() ? TEXT("local player") : TEXT("remote player"))
			: TEXT("AI");
		return FString::Printf(TEXT("%s [%s]"), *GetNameSafe(Actor), Kind);
	}

	/** An actor's place: its root, and a character's mesh and capsule. */
	FString Place(const AActor* Actor)
	{
		if (!Actor)
		{
			return TEXT("none");
		}
		FString Out = FString::Printf(TEXT("actor=%s yaw=%.1f"), *V(Actor->GetActorLocation()), Actor->GetActorRotation().Yaw);
		if (const ACharacter* Character = Cast<ACharacter>(Actor))
		{
			if (const USkeletalMeshComponent* Mesh = Character->GetMesh())
			{
				Out += FString::Printf(TEXT(" mesh=%s"), *V(Mesh->GetComponentLocation()));
			}
			if (const UCapsuleComponent* Capsule = Character->GetCapsuleComponent())
			{
				Out += FString::Printf(TEXT(" capsule r=%.1f hh=%.1f"),
					Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight());
			}
		}
		return Out;
	}

	/** One block: every line logged and counted, the block kept for the probes. */
	void Write(const TArray<FString>& Lines)
	{
		for (const FString& Line : Lines)
		{
			UE_LOG(LogOtherworldShotLog, Log, TEXT("SHOT-LOG %s"), *Line);
		}
		LineCount += Lines.Num();
		LastBlock = FString::Join(Lines, TEXT("\n"));
	}

	/** The character other than Shooter whose capsule's axis passes nearest the segment. */
	const ACharacter* NearestTo(const UWorld* World, const AActor* Shooter, const FVector& A, const FVector& B,
		float& OutMiss, FVector& OutOnLine)
	{
		const ACharacter* Best = nullptr;
		OutMiss = TNumericLimits<float>::Max();
		for (TActorIterator<ACharacter> It(const_cast<UWorld*>(World)); It; ++It)
		{
			const ACharacter* Character = *It;
			if (Character == Shooter)
			{
				continue;
			}
			const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
			const FVector Center = Character->GetActorLocation();
			const float Half = Capsule ? Capsule->GetScaledCapsuleHalfHeight_WithoutHemisphere() : 0.f;
			const FVector Up = Character->GetActorUpVector();
			FVector OnLine, OnAxis;
			FMath::SegmentDistToSegmentSafe(A, B, Center - Up * Half, Center + Up * Half, OnLine, OnAxis);
			const float Miss = static_cast<float>(FVector::Dist(OnLine, OnAxis));
			if (Miss < OutMiss)
			{
				OutMiss = Miss;
				OutOnLine = OnLine;
				Best = Character;
			}
		}
		return Best;
	}
}

bool OtherworldShotLog::IsOn(const UWorld* World)
{
	if (CVarShotLog.GetValueOnGameThread() > 0)
	{
		return true;
	}
	static const bool bCommandLine = FParse::Param(FCommandLine::Get(), TEXT("ShotLog"));
	if (bCommandLine)
	{
		return true;
	}
	const AGameStateBase* State = World ? World->GetGameState() : nullptr;
	const FBoolProperty* Switch = State ? FindFProperty<FBoolProperty>(State->GetClass(), GameStateSwitch) : nullptr;
	return Switch && Switch->GetPropertyValue_InContainer(State);
}

void OtherworldShotLog::Asked(const AActor* Shooter, const FVector& AimPoint)
{
	++ShotNumber;
	const UWorld* World = Shooter ? Shooter->GetWorld() : nullptr;
	TArray<FString> Lines;
	Lines.Add(FString::Printf(TEXT("#%d asked on the %s at %.3f s by %s"), ShotNumber, NetModeName(World),
		World ? World->GetTimeSeconds() : 0.0, *Who(Shooter)));
	Lines.Add(FString::Printf(TEXT("#%d   shooter %s"), ShotNumber, *Place(Shooter)));
	if (const APawn* Pawn = Cast<APawn>(Shooter))
	{
		const FVector Eye = Pawn->GetPawnViewLocation();
		const FRotator View = Pawn->GetBaseAimRotation();
		const FVector ToAim = AimPoint - Eye;
		const double Off = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
			FVector::DotProduct(View.Vector(), ToAim.GetSafeNormal()), -1.0, 1.0)));
		Lines.Add(FString::Printf(TEXT("#%d   view eye=%s aim rotation=%s; aim point=%s, %.1f cm off, %.2f deg off the view"),
			ShotNumber, *V(Eye), *R(View), *V(AimPoint), ToAim.Size(), Off));
	}
	else
	{
		Lines.Add(FString::Printf(TEXT("#%d   aim point=%s"), ShotNumber, *V(AimPoint)));
	}
	Write(Lines);
}

void OtherworldShotLog::Refused(const AActor* Shooter, const FString& Why)
{
	Write({FString::Printf(TEXT("#%d   REFUSED (%s): %s"), ShotNumber, *Why, *GetNameSafe(Shooter))});
}

void OtherworldShotLog::Pellet(const FPellet& P)
{
	const UWorld* World = P.Shooter ? P.Shooter->GetWorld() : nullptr;
	const FString Tag = FString::Printf(TEXT("#%d pellet %d/%d"), ShotNumber, P.Index + 1, P.Count);
	TArray<FString> Lines;
	Lines.Add(FString::Printf(TEXT("%s gun=%s muzzle=%s dir=%s end=%s range=%.0f spread=%.2f deg rewind=%.0f ms"),
		*Tag, *GetNameSafe(P.Gun), *V(P.Muzzle), *D(P.Direction), *V(P.End),
		FVector::Dist(P.Muzzle, P.End), P.SpreadDegrees, P.RewindSeconds * 1000.f));

	const FHitResult* Hit = P.Hit;
	const AActor* Struck = (P.bStopped && Hit) ? Hit->GetActor() : nullptr;
	if (P.bStopped && Hit)
	{
		const UPhysicalMaterial* Material = Hit->PhysMaterial.Get();
		Lines.Add(FString::Printf(TEXT("%s   stopped by %s component=%s at %s impact=%s normal=%s dist=%.1f physmat=%s"),
			*Tag, *GetNameSafe(Struck), *GetNameSafe(Hit->GetComponent()), *V(Hit->Location),
			*V(Hit->ImpactPoint), *V(Hit->ImpactNormal), Hit->Distance, *GetNameSafe(Material)));
	}
	else
	{
		Lines.Add(FString::Printf(TEXT("%s   stopped by nothing: flew its whole range"), *Tag));
	}

	if (const ACharacter* Target = Cast<ACharacter>(Struck))
	{
		Lines.Add(FString::Printf(TEXT("%s   target %s %s"), *Tag, *Who(Target), *Place(Target)));
		if (P.bBodyHit)
		{
			Lines.Add(FString::Printf(TEXT("%s   body struck: bone=%s point=%s, %.1f cm past the capsule"),
				*Tag, *P.BodyBone.ToString(), *V(P.BodyPoint), FVector::Dist(Hit->Location, P.BodyPoint)));
			const UOtherworldHitHistory* History = World ? World->GetSubsystem<UOtherworldHitHistory>() : nullptr;
			FVector Then;
			if (P.RewindSeconds > 0.f && History
				&& History->BodyThen(Target, P.BodyBone, World->GetTimeSeconds() - P.RewindSeconds, Then))
			{
				const USkeletalMeshComponent* Mesh = Target->GetMesh();
				const FVector Now = Mesh ? Mesh->GetBoneLocation(P.BodyBone) : FVector::ZeroVector;
				Lines.Add(FString::Printf(TEXT("%s   rewound: %s's box stood at %s then, its bone is at %s now (%.1f cm apart)"),
					*Tag, *P.BodyBone.ToString(), *V(Then), *V(Now), FVector::Dist(Then, Now)));
			}
		}
		else
		{
			Lines.Add(FString::Printf(TEXT("%s   body MISSED: the line crossed the capsule and struck none of its bodies"), *Tag));
		}
	}

	if (P.bHurt)
	{
		const double After = P.Health ? P.Health->Health : 0.0;
		Lines.Add(FString::Printf(TEXT("%s   HIT %s zone=%s worth=x%.2f damage=%.1f health %.1f -> %.1f%s"),
			*Tag, *GetNameSafe(Struck), P.bHead ? TEXT("head") : (P.bLimb ? TEXT("limb") : TEXT("body")),
			P.Worth, P.Damage * P.Worth, P.HealthBefore, After,
			(P.Health && !P.Health->IsAlive()) ? TEXT(" (dead)") : TEXT("")));
	}
	else
	{
		const FVector Stop = (P.bStopped && Hit) ? FVector(Hit->Location) : P.End;
		float Miss = 0.f;
		FVector OnLine = FVector::ZeroVector;
		const ACharacter* Nearest = World ? NearestTo(World, P.Shooter, P.Muzzle, Stop, Miss, OnLine) : nullptr;
		Lines.Add(FString::Printf(TEXT("%s   no damage (%s)"), *Tag,
			P.bScenery ? TEXT("scenery") : (Struck ? TEXT("a character's capsule, no body") : TEXT("nothing struck"))));
		if (Nearest)
		{
			const UCapsuleComponent* Capsule = Nearest->GetCapsuleComponent();
			const float Radius = Capsule ? Capsule->GetScaledCapsuleRadius() : 0.f;
			Lines.Add(FString::Printf(TEXT("%s   nearest character %s: its axis %.1f cm from the line (%.1f cm outside its capsule) at %s; %s"),
				*Tag, *Who(Nearest), Miss, Miss - Radius, *V(OnLine), *Place(Nearest)));
		}
	}
	Write(Lines);
}

int32 OtherworldShotLog::Lines()
{
	return LineCount;
}

const FString& OtherworldShotLog::Last()
{
	return LastBlock;
}
