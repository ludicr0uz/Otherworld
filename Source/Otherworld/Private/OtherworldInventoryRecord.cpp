#include "OtherworldInventoryRecord.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "Net/Core/PushModel/PushModel.h"
#include "Net/UnrealNetwork.h"
#include "UObject/CoreNet.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogOtherworldInventory, Log, All);

static TAutoConsoleVariable<int32> CVarInventoryRecordAudit(
	TEXT("Otherworld.InventoryRecord.Audit"), 0,
	TEXT("1: every frame, compare each unmarked inventory record with the item actors and log ")
	TEXT("INVENTORY-RECORD-STALE where they differ (a change site that did not mark)."));

namespace
{
	// A signed count as a small unsigned one: -1 is 1, 1 is 2.
	uint32 ZigZag(int32 Value)
	{
		return (static_cast<uint32>(Value) << 1) ^ static_cast<uint32>(Value >> 31);
	}

	int32 UnZigZag(uint32 Value)
	{
		return static_cast<int32>(Value >> 1) ^ -static_cast<int32>(Value & 1);
	}

	void SerializeInt(FArchive& Ar, int32& Value)
	{
		uint32 Packed = ZigZag(Value);
		Ar.SerializeIntPacked(Packed);
		if (Ar.IsLoading())
		{
			Value = UnZigZag(Packed);
		}
	}

	void SerializeClass(FArchive& Ar, UPackageMap* Map, TSubclassOf<AActor>& Class)
	{
		UObject* Object = Class.Get();
		if (Map)
		{
			// A class this machine has not loaded yet reads as none, and the
			// engine gives the record again once it has.
			Map->SerializeObject(Ar, UClass::StaticClass(), Object);
		}
		else
		{
			Ar << Object;
		}
		if (Ar.IsLoading())
		{
			Class = Cast<UClass>(Object);
		}
	}

	FString ClassName(const UClass* Class)
	{
		return Class ? Class->GetName() : FString(TEXT("-"));
	}

	const FArrayProperty* ArrayOf(const UObject* Object, FName Name)
	{
		return Object && !Name.IsNone() ? FindFProperty<FArrayProperty>(Object->GetClass(), Name) : nullptr;
	}

	/** The objects of an object array variable, null for a slot with none. */
	void ReadObjects(const UObject* Object, FName Name, TArray<UObject*>& Out)
	{
		Out.Reset();
		const FArrayProperty* Array = ArrayOf(Object, Name);
		const FObjectPropertyBase* Inner = Array ? CastField<FObjectPropertyBase>(Array->Inner) : nullptr;
		if (!Inner)
		{
			return;
		}
		FScriptArrayHelper Helper(Array, Array->ContainerPtrToValuePtr<void>(Object));
		for (int32 Index = 0; Index < Helper.Num(); ++Index)
		{
			UObject* Value = Inner->GetObjectPropertyValue(Helper.GetRawPtr(Index));
			Out.Add(IsValid(Value) ? Value : nullptr);
		}
	}

	int32 ReadInt(const UObject* Object, FName Name)
	{
		const FIntProperty* Property = FindFProperty<FIntProperty>(Object->GetClass(), Name);
		return Property ? Property->GetPropertyValue_InContainer(Object) : 0;
	}

	bool ReadBool(const UObject* Object, FName Name)
	{
		const FBoolProperty* Property = FindFProperty<FBoolProperty>(Object->GetClass(), Name);
		return Property && Property->GetPropertyValue_InContainer(Object);
	}
}

// ─── The record ──────────────────────────────────────────────────────────────

bool FOtherworldInventoryRecord::NetSerialize(FArchive& Ar, UPackageMap* Map, bool& bOutSuccess)
{
	bOutSuccess = true;

	uint32 Rows = Items.Num();
	Ar.SerializeIntPacked(Rows);
	uint32 Slots = Worn.Num();
	Ar.SerializeIntPacked(Slots);
	if (Ar.IsLoading())
	{
		if (Rows > MaxRows || Slots > MaxRows)
		{
			Ar.SetError();
			bOutSuccess = false;
			return false;
		}
		Items.SetNum(Rows);
		Worn.SetNum(Slots);
	}
	for (FOtherworldItemRow& Row : Items)
	{
		SerializeClass(Ar, Map, Row.Class);
		SerializeInt(Ar, Row.Slot);
		SerializeInt(Ar, Row.Loaded);
		SerializeInt(Ar, Row.Reserve);
		uint8 Flags = (Row.bLit ? 1 : 0) | (Row.bHot ? 2 : 0);
		Ar.SerializeBits(&Flags, 2);
		if (Ar.IsLoading())
		{
			Row.bLit = (Flags & 1) != 0;
			Row.bHot = (Flags & 2) != 0;
		}
	}
	for (TSubclassOf<AActor>& Garment : Worn)
	{
		SerializeClass(Ar, Map, Garment);
	}
	return true;
}

FString FOtherworldInventoryRecord::Describe() const
{
	TArray<FString> Rows;
	for (const FOtherworldItemRow& Row : Items)
	{
		Rows.Add(FString::Printf(TEXT("%s@%d %d/%d%s%s"), *ClassName(Row.Class), Row.Slot, Row.Loaded,
			Row.Reserve, Row.bLit ? TEXT(" lit") : TEXT(""), Row.bHot ? TEXT(" hot") : TEXT("")));
	}
	TArray<FString> Garments;
	for (const TSubclassOf<AActor>& Garment : Worn)
	{
		Garments.Add(ClassName(Garment));
	}
	return FString::Join(Rows, TEXT(", ")) + TEXT(" | ") + FString::Join(Garments, TEXT(", "));
}

// ─── The component ───────────────────────────────────────────────────────────

UOtherworldInventoryRecordComponent::UOtherworldInventoryRecordComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	SetIsReplicatedByDefault(true);
}

void UOtherworldInventoryRecordComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	FDoRepLifetimeParams Owner;
	Owner.bIsPushBased = true;
	Owner.Condition = COND_OwnerOnly;
	DOREPLIFETIME_WITH_PARAMS_FAST(UOtherworldInventoryRecordComponent, Record, Owner);

	FDoRepLifetimeParams Others;
	Others.bIsPushBased = true;
	Others.Condition = COND_SkipOwner;
	DOREPLIFETIME_WITH_PARAMS_FAST(UOtherworldInventoryRecordComponent, HandClass, Others);
	DOREPLIFETIME_WITH_PARAMS_FAST(UOtherworldInventoryRecordComponent, HandLit, Others);
	DOREPLIFETIME_WITH_PARAMS_FAST(UOtherworldInventoryRecordComponent, HandHot, Others);
}

void UOtherworldInventoryRecordComponent::BeginPlay()
{
	Super::BeginPlay();
	if (UWorld* World = GetWorld())
	{
		if (UOtherworldInventoryRecords* Records = World->GetSubsystem<UOtherworldInventoryRecords>())
		{
			Records->Add(this);
		}
	}
	// Whatever the owner was given before anything marked.
	MarkDirty();
}

void UOtherworldInventoryRecordComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		if (UOtherworldInventoryRecords* Records = World->GetSubsystem<UOtherworldInventoryRecords>())
		{
			Records->Remove(this);
		}
	}
	Super::EndPlay(EndPlayReason);
}

void UOtherworldInventoryRecordComponent::MarkDirty()
{
	const AActor* Owner = GetOwner();
	if (Owner && Owner->HasAuthority())
	{
		bDirty = true;
	}
}

UOtherworldInventoryRecordComponent* UOtherworldInventoryRecordComponent::Of(const UObject* Carrier)
{
	const UActorComponent* Part = Cast<UActorComponent>(Carrier);
	const AActor* Actor = Part ? Part->GetOwner() : Cast<AActor>(Carrier);
	return Actor ? Actor->FindComponentByClass<UOtherworldInventoryRecordComponent>() : nullptr;
}

UActorComponent* UOtherworldInventoryRecordComponent::Source()
{
	if (UActorComponent* Known = CachedSource.Get())
	{
		return Known;
	}
	if (const AActor* Owner = GetOwner())
	{
		for (UActorComponent* Component : Owner->GetComponents())
		{
			if (Component && Component != this && ArrayOf(Component, InventoryVar))
			{
				CachedSource = Component;
				return Component;
			}
		}
	}
	return nullptr;
}

void UOtherworldInventoryRecordComponent::Read(UActorComponent* From, FOtherworldInventoryRecord& OutRecord,
	TSubclassOf<AActor>& OutHand, bool& bOutLit, bool& bOutHot) const
{
	TArray<UObject*> Objects;
	ReadObjects(From, InventoryVar, Objects);
	OutRecord.Items.Reset(Objects.Num());
	for (const UObject* Item : Objects)
	{
		// An item destroyed and not yet taken out of Inventory has no row.
		if (!Item)
		{
			continue;
		}
		FOtherworldItemRow& Row = OutRecord.Items.AddDefaulted_GetRef();
		Row.Class = Item->GetClass();
		Row.Slot = ReadInt(Item, ItemSlotVar);
		Row.Loaded = ReadInt(Item, ItemLoadedVar);
		Row.Reserve = ReadInt(Item, ItemReserveVar);
		Row.bLit = ReadBool(Item, ItemLitVar);
		Row.bHot = ReadBool(Item, ItemHotVar);
	}

	ReadObjects(From, WornVar, Objects);
	OutRecord.Worn.Reset(Objects.Num());
	for (const UObject* Garment : Objects)
	{
		OutRecord.Worn.Add(Garment ? Garment->GetClass() : nullptr);
	}

	ReadObjects(From, SlotItemsVar, Objects);
	const UObject* Held = Objects.IsValidIndex(HandSlot) ? Objects[HandSlot] : nullptr;
	OutHand = Held ? Held->GetClass() : nullptr;
	bOutLit = Held && ReadBool(Held, ItemLitVar);
	bOutHot = Held && ReadBool(Held, ItemHotVar);
}

void UOtherworldInventoryRecordComponent::Write()
{
	bDirty = false;
	UActorComponent* From = Source();
	if (!From)
	{
		return;
	}
	FOtherworldInventoryRecord Now;
	TSubclassOf<AActor> Hand;
	bool bLit = false;
	bool bHot = false;
	Read(From, Now, Hand, bLit, bHot);

	++Writes;
	if (Now != Record)
	{
		Record = MoveTemp(Now);
		MARK_PROPERTY_DIRTY_FROM_NAME(UOtherworldInventoryRecordComponent, Record, this);
	}
	if (Hand != HandClass)
	{
		HandClass = Hand;
		MARK_PROPERTY_DIRTY_FROM_NAME(UOtherworldInventoryRecordComponent, HandClass, this);
	}
	if (bLit != HandLit)
	{
		HandLit = bLit;
		MARK_PROPERTY_DIRTY_FROM_NAME(UOtherworldInventoryRecordComponent, HandLit, this);
	}
	if (bHot != HandHot)
	{
		HandHot = bHot;
		MARK_PROPERTY_DIRTY_FROM_NAME(UOtherworldInventoryRecordComponent, HandHot, this);
	}
}

void UOtherworldInventoryRecordComponent::Audit()
{
	const AActor* Owner = GetOwner();
	UActorComponent* From = Source();
	if (!Owner || !Owner->HasAuthority() || !From)
	{
		return;
	}
	FOtherworldInventoryRecord Now;
	TSubclassOf<AActor> Hand;
	bool bLit = false;
	bool bHot = false;
	Read(From, Now, Hand, bLit, bHot);
	if (Now == Record && Hand == HandClass && bLit == HandLit && bHot == HandHot)
	{
		return;
	}
	++Stale;
	UE_LOG(LogOtherworldInventory, Warning,
		TEXT("INVENTORY-RECORD-STALE: %s changed with no MarkDirty. Record: [%s] hand %s%s%s. Items: [%s] hand %s%s%s"),
		*Owner->GetName(), *Record.Describe(), *ClassName(HandClass), HandLit ? TEXT(" lit") : TEXT(""),
		HandHot ? TEXT(" hot") : TEXT(""), *Now.Describe(), *ClassName(Hand), bLit ? TEXT(" lit") : TEXT(""),
		bHot ? TEXT(" hot") : TEXT(""));
	Write();
}

bool UOtherworldInventoryRecordComponent::Carries(const AActor* Item) const
{
	UActorComponent* From = const_cast<UOtherworldInventoryRecordComponent*>(this)->Source();
	TArray<UObject*> Objects;
	ReadObjects(From, InventoryVar, Objects);
	if (Objects.Contains(Item))
	{
		return true;
	}
	ReadObjects(From, WornVar, Objects);
	return Objects.Contains(Item);
}

void UOtherworldInventoryRecordComponent::OnRep_Record()
{
	++Writes;
	RaiseViewDirty();
	OnRecordChanged.Broadcast();
}

void UOtherworldInventoryRecordComponent::OnRep_Hand()
{
	RaiseViewDirty();
}

void UOtherworldInventoryRecordComponent::RaiseViewDirty()
{
	UActorComponent* View = Source();
	const FBoolProperty* Property = View && !ViewDirtyVar.IsNone()
		? FindFProperty<FBoolProperty>(View->GetClass(), ViewDirtyVar) : nullptr;
	if (Property)
	{
		Property->SetPropertyValue_InContainer(View, true);
	}
}

// ─── The frame's one write ───────────────────────────────────────────────────

void UOtherworldInventoryRecords::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	// After the actors ticked: the slots are placed and every graph that
	// changes what is carried has run. Replication is later in the frame.
	TickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(this, &UOtherworldInventoryRecords::OnPostActorTick);
}

void UOtherworldInventoryRecords::Deinitialize()
{
	FWorldDelegates::OnWorldPostActorTick.Remove(TickHandle);
	Super::Deinitialize();
}

void UOtherworldInventoryRecords::Add(UOtherworldInventoryRecordComponent* Component)
{
	Components.AddUnique(Component);
}

void UOtherworldInventoryRecords::Remove(UOtherworldInventoryRecordComponent* Component)
{
	Components.RemoveSwap(Component);
}

void UOtherworldInventoryRecords::MarkCarrierOf(const AActor* Item)
{
	for (const TWeakObjectPtr<UOtherworldInventoryRecordComponent>& Weak : Components)
	{
		UOtherworldInventoryRecordComponent* Component = Weak.Get();
		if (Component && Component->Carries(Item))
		{
			Component->MarkDirty();
		}
	}
}

void UOtherworldInventoryRecords::OnPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
	if (World != GetWorld())
	{
		return;
	}
	const bool bAudit = CVarInventoryRecordAudit.GetValueOnGameThread() != 0;
	for (int32 Index = Components.Num() - 1; Index >= 0; --Index)
	{
		UOtherworldInventoryRecordComponent* Component = Components[Index].Get();
		if (!Component)
		{
			Components.RemoveAtSwap(Index);
		}
		else if (Component->IsDirty())
		{
			Component->Write();
		}
		else if (bAudit)
		{
			Component->Audit();
		}
	}
}
