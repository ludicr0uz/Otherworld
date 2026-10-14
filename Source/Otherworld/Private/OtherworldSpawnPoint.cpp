#include "OtherworldSpawnPoint.h"

#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "NavigationSystem.h"
#include "OtherworldHealthComponent.h"

namespace
{
	// As the single-player replacement seats one (Scripts/combat/respawn.py):
	// the navmesh search box, the trace onto the real ground, the capsule's lift.
	const FVector ProjectExtent(3000.0, 3000.0, 10000.0);
	constexpr double TraceUp = 200.0;
	constexpr double TraceDown = 500.0;
	constexpr double EyeHeight = 150.0;
	// A player sees what is in front of them, this wide each side, with nothing between.
	const double SeenCos = FMath::Cos(FMath::DegreesToRadians(75.0));

	bool Sees(const UWorld* World, const APawn* Player, const FVector& Point)
	{
		const FVector Eye = Player->GetPawnViewLocation();
		const FVector To = (Point - Eye).GetSafeNormal();
		const FVector Look = Player->GetController()
			? Player->GetController()->GetControlRotation().Vector()
			: Player->GetActorForwardVector();
		if (FVector::DotProduct(To, Look) < SeenCos)
		{
			return false;
		}
		FCollisionQueryParams Params(SCENE_QUERY_STAT(OtherworldPopulationSees), false, Player);
		return !World->LineTraceTestByChannel(Eye, Point, ECC_Visibility, Params);
	}
}

bool OtherworldSpawnPoint::Lives(const APawn* Pawn)
{
	if (!IsValid(Pawn))
	{
		return false;
	}
	const UOtherworldHealthComponent* Health = Pawn->FindComponentByClass<UOtherworldHealthComponent>();
	return !Health || Health->IsAlive();
}

bool OtherworldSpawnPoint::Find(UWorld* World, TSubclassOf<APawn> Class, const FVector& Origin,
	float SpawnMin, float SpawnMax, const TArray<APawn*>& Players, FVector& OutStand,
	double& OutNearest, int32& SeenRefused)
{
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	if (!Nav || !Class)
	{
		return false;
	}
	const double MinSq = FMath::Square(double(SpawnMin));
	for (int32 Attempt = 0; Attempt < Attempts; ++Attempt)
	{
		const double Bearing = FMath::FRandRange(0.0, 2.0 * UE_DOUBLE_PI);
		const double Reach = FMath::FRandRange(double(SpawnMin), double(SpawnMax));
		const FVector Request = Origin + FVector(FMath::Cos(Bearing), FMath::Sin(Bearing), 0.0) * Reach;
		FNavLocation OnNav;
		if (!Nav->ProjectPointToNavigation(Request, OnNav, ProjectExtent))
		{
			continue;
		}
		// The navmesh is not reliably the ground: keep its XY, trace for the Z.
		FVector Ground = OnNav.Location;
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(OtherworldPopulationSeat), true);
		if (World->LineTraceSingleByChannel(Hit, Ground + FVector(0.0, 0.0, TraceUp),
			Ground - FVector(0.0, 0.0, TraceDown), ECC_Visibility, Params))
		{
			Ground = Hit.Location;
		}
		const APawn* Default = Class->GetDefaultObject<APawn>();
		const FVector Stand = Ground + FVector(0.0, 0.0, Default->GetDefaultHalfHeight());
		const FVector Head = Ground + FVector(0.0, 0.0, EyeHeight);

		// The projection may have pulled the point in: no nearer any player than the band's near edge.
		double NearestSq = TNumericLimits<double>::Max();
		bool bSeen = false;
		for (const APawn* Other : Players)
		{
			NearestSq = FMath::Min(NearestSq, FVector::DistSquared(Other->GetActorLocation(), Stand));
			bSeen = bSeen || Sees(World, Other, Head);
		}
		if (NearestSq < MinSq)
		{
			continue;
		}
		if (bSeen)
		{
			++SeenRefused;
			continue;
		}
		OutStand = Stand;
		OutNearest = FMath::Sqrt(NearestSq);
		return true;
	}
	return false;
}
