// What a player carries, as one record (task A3a). The server's item actors
// are still what its graphs work on (the weapon component's Inventory, Worn
// and SlotItems, each item's Slot, Loaded, Reserve, Lit and Hot); the record
// is those written down as plain data: a row per carried item and a class
// per worn slot. It travels to the owning client as one value
// (FOtherworldInventoryRecord::NetSerialize), so a client never holds half of
// one, and it is written when what is carried changes, not every Tick:
//
//   a graph changes what is carried  -->  MarkDirty()  (Scripts/uebp/nodes/
//                                         inventory.py; the server's alone)
//   after the actors ticked, that frame  -->  the record written once, off
//                                         the item actors as they then stand
//
// Everyone but the owner is told what the hand holds: HandClass, HandLit and
// HandHot.
//
// Until the client's view reads the record (task A3b) the component also
// writes the weapon component's own Inv* arrays, WornClass and Hand*
// variables from it, in the same frame: those still replicate, and
// Scripts/combat/weapon_component/view.py still reads them.
//
// In single player the component holds the record and nothing travels.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/EngineBaseTypes.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "Templates/SubclassOf.h"
#include "OtherworldInventoryRecord.generated.h"

/** One carried item. */
USTRUCT(BlueprintType)
struct OTHERWORLD_API FOtherworldItemRow
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	TSubclassOf<AActor> Class;

	/** Its slot code (Scripts/combat/slot_tuning.py): the hand, a weapon slot, a bag slot. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	int32 Slot = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	int32 Loaded = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	int32 Reserve = 0;

	/** It is burning (a stick lit at a fire). */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	bool bLit = false;

	/** It is hot (a blade heated at one). */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	bool bHot = false;

	bool operator==(const FOtherworldItemRow& Other) const
	{
		return Class == Other.Class && Slot == Other.Slot && Loaded == Other.Loaded && Reserve == Other.Reserve
			&& bLit == Other.bLit && bHot == Other.bHot;
	}
};

/** What a player carries and wears. Sent whole, never a member at a time. */
USTRUCT(BlueprintType)
struct OTHERWORLD_API FOtherworldInventoryRecord
{
	GENERATED_BODY()

	/** A row per carried item, in the order of the server's Inventory. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	TArray<FOtherworldItemRow> Items;

	/** A row per worn slot (Scripts/combat/wear_tuning.py): the garment's class, or none. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	TArray<TSubclassOf<AActor>> Worn;

	/** More rows than this in a record received is a broken one. */
	static constexpr uint32 MaxRows = 256;

	bool operator==(const FOtherworldInventoryRecord& Other) const
	{
		return Items == Other.Items && Worn == Other.Worn;
	}
	bool operator!=(const FOtherworldInventoryRecord& Other) const { return !(*this == Other); }

	bool NetSerialize(FArchive& Ar, UPackageMap* Map, bool& bOutSuccess);

	/** For the log and the probes: "Class@slot loaded/reserve[ lit][ hot], ... | worn, ...". */
	FString Describe() const;
};

template<>
struct TStructOpsTypeTraits<FOtherworldInventoryRecord> : public TStructOpsTypeTraitsBase2<FOtherworldInventoryRecord>
{
	enum
	{
		WithNetSerializer = true,
		WithIdenticalViaEquality = true,
	};
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOtherworldRecordChanged);

/**
 * Holds one player's record, on the character beside the weapon component
 * (Scripts/combat/install.py adds it and writes the names below from the
 * builders' own tables).
 */
UCLASS(ClassGroup = (Otherworld), meta = (BlueprintSpawnableComponent))
class OTHERWORLD_API UOtherworldInventoryRecordComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UOtherworldInventoryRecordComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/**
	 * What is carried changed: the record is written after this frame's
	 * actors have ticked. The server's (and single player's); nothing on a
	 * client. Any number of calls in a frame is one write.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Inventory")
	void MarkDirty();

	/** To the owning client alone. */
	UPROPERTY(ReplicatedUsing = OnRep_Record, BlueprintReadOnly, Category = "Otherworld|Inventory")
	FOtherworldInventoryRecord Record;

	/** To everyone but the owner: what the hand holds, or none; whether it burns; whether it glows. */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Otherworld|Inventory")
	TSubclassOf<AActor> HandClass;

	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Otherworld|Inventory")
	bool HandLit = false;

	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Otherworld|Inventory")
	bool HandHot = false;

	/** A client's: a record arrived. */
	UPROPERTY(BlueprintAssignable, Category = "Otherworld|Inventory")
	FOtherworldRecordChanged OnRecordChanged;

	/** For the probes: the times the record was written (with authority) or arrived (a client). */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	int32 Writes = 0;

	/** For the probes: the times the audit found the record behind the item actors with nothing marked. */
	UPROPERTY(BlueprintReadOnly, Category = "Otherworld|Inventory")
	int32 Stale = 0;

	// Where the record is read from: variables of the component on the same
	// actor that has InventoryVar (the weapon component), and of each item.
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName InventoryVar = TEXT("Inventory");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName WornVar = TEXT("Worn");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName SlotItemsVar = TEXT("SlotItems");
	/** The hand's index in SlotItemsVar. */
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	int32 HandSlot = 0;
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName ItemSlotVar = TEXT("Slot");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName ItemLoadedVar = TEXT("Loaded");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName ItemReserveVar = TEXT("Reserve");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName ItemLitVar = TEXT("Lit");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Source")
	FName ItemHotVar = TEXT("Hot");

	// Where it is also written until task A3b: the same component's
	// variables the old view reads. A name of None is not written.
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorClassVar = TEXT("InvClass");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorSlotVar = TEXT("InvSlot");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorLoadedVar = TEXT("InvLoaded");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorReserveVar = TEXT("InvReserve");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorLitVar = TEXT("InvLit");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorHotVar = TEXT("InvHot");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorWornVar = TEXT("WornClass");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorHandClassVar = TEXT("HandClass");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorHandLitVar = TEXT("HandLit");
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|Mirror")
	FName MirrorHandHotVar = TEXT("HandHot");

	bool IsDirty() const { return bDirty; }
	/** The record written off the item actors, the mirror with it. */
	void Write();
	/** With nothing marked: is the record what the item actors say? If not, logged, counted and written. */
	void Audit();
	/** This component's Inventory or Worn holds Item. */
	bool Carries(const AActor* Item) const;

private:
	UFUNCTION()
	void OnRep_Record();

	/** The component on the same actor whose class has InventoryVar. */
	UActorComponent* Source();
	void Read(UActorComponent* From, FOtherworldInventoryRecord& OutRecord, TSubclassOf<AActor>& OutHand,
		bool& bOutLit, bool& bOutHot) const;
	void WriteMirror(UActorComponent* To) const;

	TWeakObjectPtr<UActorComponent> CachedSource;
	bool bDirty = false;
};

/** Writes each marked record once a frame, after the actors ticked. */
UCLASS()
class OTHERWORLD_API UOtherworldInventoryRecords : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	void Add(UOtherworldInventoryRecordComponent* Component);
	void Remove(UOtherworldInventoryRecordComponent* Component);
	/** Whoever carries Item is marked. */
	void MarkCarrierOf(const AActor* Item);

private:
	void OnPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);

	FDelegateHandle TickHandle;
	TArray<TWeakObjectPtr<UOtherworldInventoryRecordComponent>> Components;
};

UCLASS()
class OTHERWORLD_API UOtherworldInventoryLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * What Carrier carries changed (an item gained, lost, moved, spent, lit):
	 * its record is written at the end of this frame. Carrier is the
	 * character, or one of its components (the weapon component, as another
	 * Blueprint holds it). The server's alone, and single player's.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Inventory")
	static void MarkInventoryDirty(UObject* Carrier);

	/**
	 * The same by the item: whoever carries Item is marked (nobody, for one
	 * lying in the world). Item left unconnected is the calling graph's own
	 * actor: an item's own Tick, whose fire burnt out or whose heat is gone.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Inventory", meta = (DefaultToSelf = "Item"))
	static void MarkCarriedItemDirty(AActor* Item);

	/** For the probes: the record as text, and what the hand holds as everyone else is told it. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static FString DescribeInventoryRecord(const AActor* Carrier);

	/** For the probes: the times Carrier's record was written here, or arrived. -1 with no record component. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static int32 InventoryRecordWrites(const AActor* Carrier);

	/** For the probes: the times the audit found Carrier's record stale. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static int32 InventoryRecordStale(const AActor* Carrier);

	/**
	 * For the probes: every frame, compare each unmarked record with the
	 * item actors (Otherworld.InventoryRecord.Audit). A difference is a
	 * change site that did not mark: an INVENTORY-RECORD-STALE log line.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Inventory")
	static void SetInventoryRecordAudit(bool bOn);

	/** For the probes: the engine's Push Model is compiled in and switched on. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static bool IsPushModelOn();
};
