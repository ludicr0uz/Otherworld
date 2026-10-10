#include "OtherworldWeaponComponentBase.h"

#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "OtherworldInventoryRecord.h"
#include "OtherworldRpcGuard.h"
#include "OtherworldShotLibrary.h"

namespace
{
	// A Blueprint variable by name (Source/CLAUDE.md, "A Blueprint variable
	// read or written from C++ is found by name"). A missing one reads as
	// nothing: false, 0, none.
	bool ReadBool(const UObject* Object, FName Name)
	{
		const FBoolProperty* Property = Object ? FindFProperty<FBoolProperty>(Object->GetClass(), Name) : nullptr;
		return Property && Property->GetPropertyValue_InContainer(Object);
	}

	const FNumericProperty* NumberOf(const UObject* Object, FName Name)
	{
		return Object ? FindFProperty<FNumericProperty>(Object->GetClass(), Name) : nullptr;
	}

	int32 ReadInt(const UObject* Object, FName Name)
	{
		const FNumericProperty* Property = NumberOf(Object, Name);
		return Property && Property->IsInteger()
			? static_cast<int32>(Property->GetSignedIntPropertyValue(Property->ContainerPtrToValuePtr<void>(Object))) : 0;
	}

	void WriteInt(UObject* Object, FName Name, int32 Value)
	{
		const FNumericProperty* Property = NumberOf(Object, Name);
		if (Property && Property->IsInteger())
		{
			Property->SetIntPropertyValue(Property->ContainerPtrToValuePtr<void>(Object), static_cast<int64>(Value));
		}
	}

	// A Blueprint float is a double; either is read.
	double ReadReal(const UObject* Object, FName Name)
	{
		const FNumericProperty* Property = NumberOf(Object, Name);
		return Property && Property->IsFloatingPoint()
			? Property->GetFloatingPointPropertyValue(Property->ContainerPtrToValuePtr<void>(Object)) : 0.0;
	}

	void WriteReal(UObject* Object, FName Name, double Value)
	{
		const FNumericProperty* Property = NumberOf(Object, Name);
		if (Property && Property->IsFloatingPoint())
		{
			Property->SetFloatingPointPropertyValue(Property->ContainerPtrToValuePtr<void>(Object), Value);
		}
	}

	UObject* ReadObject(const UObject* Object, FName Name)
	{
		const FObjectPropertyBase* Property = Object ? FindFProperty<FObjectPropertyBase>(Object->GetClass(), Name) : nullptr;
		return Property ? Property->GetObjectPropertyValue_InContainer(Object) : nullptr;
	}

	bool NamesHold(const UObject* Object, FName Name, FName Wanted)
	{
		const FArrayProperty* Array = Object ? FindFProperty<FArrayProperty>(Object->GetClass(), Name) : nullptr;
		const FNameProperty* Inner = Array ? CastField<FNameProperty>(Array->Inner) : nullptr;
		if (!Inner)
		{
			return false;
		}
		FScriptArrayHelper Helper(Array, Array->ContainerPtrToValuePtr<void>(Object));
		for (int32 Index = 0; Index < Helper.Num(); ++Index)
		{
			if (Inner->GetPropertyValue(Helper.GetRawPtr(Index)) == Wanted)
			{
				return true;
			}
		}
		return false;
	}
}

UActorComponent* UOtherworldWeaponComponentBase::HealthOf(const AActor* Actor) const
{
	return Actor && HealthClass ? Actor->FindComponentByClass(HealthClass) : nullptr;
}

bool UOtherworldWeaponComponentBase::OwnerAlive() const
{
	// A request can arrive after the blow that killed: the health itself is
	// asked. An owner with no health component is alive.
	const UActorComponent* Health = HealthOf(GetOwner());
	return !Health || !(ReadBool(Health, HealthDeadVar) || ReadReal(Health, HealthVar) <= 0.0);
}

bool UOtherworldWeaponComponentBase::MayFire(AActor* Gun) const
{
	const UWorld* World = GetWorld();
	if (!IsValid(Gun) || !World)
	{
		return false;
	}
	if (!OwnerAlive())
	{
		return false;
	}
	// Only a gun is fired: the knife, food and the matches have the fire
	// key's other arms, which are not this request.
	if (ReadBool(Gun, ItemMeleeVar) || ReadBool(Gun, ItemConsumableVar) || ReadBool(Gun, ItemLightsVar))
	{
		return false;
	}
	if (ReadBool(Gun, ItemUsesAmmoVar) && ReadInt(Gun, ItemLoadedVar) <= 0)
	{
		return false;
	}
	// A client fires on its own clock and its packets do not arrive evenly.
	return World->GetTimeSeconds() + FireGraceSeconds >= ReadReal(Gun, ItemNextFireTimeVar);
}

bool UOtherworldWeaponComponentBase::Server_Fire_Validate(FVector AimPoint)
{
	return !AimPoint.ContainsNaN();
}

void UOtherworldWeaponComponentBase::Server_Fire_Implementation(FVector AimPoint)
{
	const AActor* Owner = GetOwner();
	const UWorld* World = GetWorld();
	if (!Owner || !World)
	{
		return;
	}
	UOtherworldRpcGuard* Guard = Owner->FindComponentByClass<UOtherworldRpcGuard>();
	// Asked first, and counted served whatever it said: a refused shot's
	// round is handed back like any other the server did not fire.
	const bool bAllowed = !Guard || Guard->Allow(FireEventName);
	WriteInt(this, AsksServedVar, ReadInt(this, AsksServedVar) + 1);
	AActor* Gun = Cast<AActor>(ReadObject(this, HeldVar));
	if (!bAllowed || (Guard && !Guard->AimAllowed(AimPoint)) || !MayFire(Gun))
	{
		++ShotsRefused;
		return;
	}
	// The round and the deadline before a single pellet is traced, so
	// nothing downstream can leave the gun having fired for free. Every gun
	// counts down: Loaded is only read behind UsesAmmo. The deadline runs
	// from the later of now and the old one, so a shot let in early does
	// not raise the rate.
	WriteInt(Gun, ItemLoadedVar, ReadInt(Gun, ItemLoadedVar) - 1);
	const double From = FMath::Max<double>(World->GetTimeSeconds(), ReadReal(Gun, ItemNextFireTimeVar));
	WriteReal(Gun, ItemNextFireTimeVar, From + ReadReal(Gun, ItemFireIntervalVar));
	// By the carrier, as the graph's own marks are: by the item, every
	// carrier's inventory is searched for it (55 us a shot at 64 characters).
	UOtherworldInventoryLibrary::MarkInventoryDirty(this);
	++ShotsFired;
	ShotFired(AimPoint);
}

void UOtherworldWeaponComponentBase::Server_Reload_Implementation()
{
	const AActor* Owner = GetOwner();
	if (!Owner)
	{
		return;
	}
	UOtherworldRpcGuard* Guard = Owner->FindComponentByClass<UOtherworldRpcGuard>();
	// Counted served between the ask and its answer, as the shot is: a
	// refused reload hands the client's predicted rounds back.
	const bool bAllowed = !Guard || Guard->Allow(ReloadEventName);
	WriteInt(this, AsksServedVar, ReadInt(this, AsksServedVar) + 1);
	if (bAllowed)
	{
		ReloadNow();
	}
}

int32 UOtherworldWeaponComponentBase::ReloadTake(const AActor* Gun) const
{
	if (!IsValid(Gun) || !ReadBool(Gun, ItemUsesAmmoVar))
	{
		return 0;
	}
	const int32 Gap = ReadInt(Gun, ItemMagazineSizeVar) - ReadInt(Gun, ItemLoadedVar);
	// Min, so a reserve of one tops a magazine that is four short up by one,
	// and the reserve is never driven below zero. An endless reserve stands
	// the whole gap in for itself.
	const int32 Source = ReadBool(Gun, ItemInfiniteReserveVar) ? Gap : ReadInt(Gun, ItemReserveVar);
	return FMath::Max(FMath::Min(Gap, Source), 0);
}

void UOtherworldWeaponComponentBase::ReloadNow()
{
	const UWorld* World = GetWorld();
	AActor* Gun = Cast<AActor>(ReadObject(this, HeldVar));
	if (!World || !IsValid(Gun) || !OwnerAlive())
	{
		return;
	}
	// Once, before anything is written: every line below reads this number.
	const int32 Take = ReloadTake(Gun);
	if (Take <= 0)
	{
		// A full magazine, an empty reserve, a thing without ammunition: no
		// pause and no sound for a key that did not apply.
		return;
	}
	WriteInt(Gun, ItemLoadedVar, ReadInt(Gun, ItemLoadedVar) + Take);
	if (!ReadBool(Gun, ItemInfiniteReserveVar))
	{
		WriteInt(Gun, ItemReserveVar, ReadInt(Gun, ItemReserveVar) - Take);
	}
	// There is no reloading state: the cost is the one deadline the interval
	// between shots uses.
	WriteReal(Gun, ItemNextFireTimeVar, World->GetTimeSeconds() + ReadReal(Gun, ItemReloadSecondsVar));
	// Nothing on a client, whose copy is its prediction.
	UOtherworldInventoryLibrary::MarkInventoryDirty(this);
	++Reloads;
	Reloaded();
}

void UOtherworldWeaponComponentBase::HandHit(UActorComponent* Health, float Amount, const FVector& From,
	AController* By, AActor* Cause) const
{
	UFunction* Function = Health->FindFunction(TakeHitEvent);
	if (!Function)
	{
		return;
	}
	TArray<uint8> Storage;
	Storage.SetNumZeroed(FMath::Max<int32>(Function->ParmsSize, 1));
	uint8* Parms = Storage.GetData();
	// By position and kind: the amount, the way it came, who, with what.
	int32 Objects = 0;
	for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
	{
		It->InitializeValue_InContainer(Parms);
		void* Value = It->ContainerPtrToValuePtr<void>(Parms);
		if (const FNumericProperty* Number = CastField<FNumericProperty>(*It))
		{
			Number->SetFloatingPointPropertyValue(Value, Amount);
		}
		else if (const FStructProperty* Struct = CastField<FStructProperty>(*It))
		{
			if (Struct->Struct == TBaseStructure<FVector>::Get())
			{
				*static_cast<FVector*>(Value) = From;
			}
		}
		else if (const FObjectPropertyBase* Object = CastField<FObjectPropertyBase>(*It))
		{
			Object->SetObjectPropertyValue(Value, Objects++ == 0 ? static_cast<UObject*>(By) : static_cast<UObject*>(Cause));
		}
	}
	Health->ProcessEvent(Function, Parms);
	for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
	{
		It->DestroyValue_InContainer(Parms);
	}
}

void UOtherworldWeaponComponentBase::FirePellets(AActor* Gun, FVector Muzzle, FVector Direction, int32 Pellets,
	float SpreadDegrees, float Range, float Damage, float MaxRewindSeconds, float ExtraRewindSeconds)
{
	AActor* Owner = GetOwner();
	if (!Owner || !Owner->HasAuthority())
	{
		return;
	}
	AController* By = Owner->GetInstigatorController();
	const float Spread = FMath::DegreesToRadians(SpreadDegrees);
	for (int32 Pellet = 0; Pellet < Pellets; ++Pellet)
	{
		// The gun's own pattern around the shot's direction: nothing on a
		// single-round gun, whose round flies down the draw.
		const FVector End = Muzzle + FMath::VRandCone(Direction, Spread) * Range;
		FHitResult Hit;
		bool bBodyHit = false;
		FName BodyBone = NAME_None;
		FVector BodyPoint = FVector::ZeroVector;
		const bool bStopped = UOtherworldShotLibrary::ShotTrace(Owner, Muzzle, End, MaxRewindSeconds,
			ExtraRewindSeconds, Hit, bBodyHit, BodyBone, BodyPoint);

		FVector Point = Hit.Location;
		FName Bone = NAME_None;
		bool bHurt = false;
		bool bScenery = false;
		bool bHead = false;
		float Worth = 1.f;
		if (bStopped)
		{
			AActor* Struck = Hit.GetActor();
			UActorComponent* Health = HealthOf(Struck);
			if (!Health)
			{
				bScenery = true;
			}
			else if (!Cast<ACharacter>(Struck))
			{
				// Health and no body to trace: the hit at 1x, where the trace landed.
				bHurt = true;
			}
			else if (bBodyHit)
			{
				// The capsule says whether a character was struck and its
				// bodies where: a pellet that strikes none passed the model by.
				bHurt = true;
				Bone = BodyBone;
				Point = BodyPoint;
			}
			if (bHurt)
			{
				// The zone off the TARGET's own tables; the head wins.
				bHead = NamesHold(Health, HeadBonesVar, Bone);
				if (bHead)
				{
					Worth = static_cast<float>(ReadReal(Health, HeadMultiplierVar));
				}
				else if (NamesHold(Health, LimbBonesVar, Bone))
				{
					Worth = static_cast<float>(ReadReal(Health, LimbMultiplierVar));
				}
				// Which way it came from is the impact normal: it points
				// back out of the surface toward the muzzle.
				HandHit(Health, Damage * Worth, Hit.ImpactNormal, By, Gun);
			}
		}
		PelletFlew(Muzzle, bStopped ? Hit.Location : End, bStopped, Point, Hit.ImpactNormal,
			bHurt, bScenery, Bone, bHead, Damage * Worth, Worth);
	}
}
