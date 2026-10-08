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
// A client's item actors are a picture of the record (task A3b): the one
// RepNotify raises the weapon component's ViewDirty, and its view
// (Scripts/combat/weapon_component/view.py) reads the rows through
// UOtherworldInventoryLibrary: InventoryRow, WornRow, HandRow. No Blueprint
// variable holds a copy.
//
// The record is also what a save writes: ToBytes and FromBytes, a version
// first, classes by path, into a USaveGame's byte array
// (UOtherworldRecordSave is the one the probe round-trips through).
//
// In single player the component holds the record and nothing travels.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/EngineBaseTypes.h"
#include "GameFramework/SaveGame.h"
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

	/** The first field of the saved form. A change to the layout below it is a new number, and a reader of the old one. */
	static constexpr uint32 SaveVersion = 1;

	/**
	 * The record as a save holds it: SaveVersion, then the rows and the worn
	 * slots, each class by its path (a save outlives the session that knew
	 * the class by a net id). Little-endian, whatever the machine.
	 */
	void ToBytes(TArray<uint8>& OutBytes) const;

	/**
	 * The record read back. False, and the record left as it was, for bytes
	 * of a version this build does not read, cut short, or with anything
	 * after their end. A row whose class no longer exists is dropped, and a
	 * worn slot whose class does not is empty: a save outlives an item.
	 */
	bool FromBytes(const TArray<uint8>& Bytes);

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
	UPROPERTY(ReplicatedUsing = OnRep_Hand, BlueprintReadOnly, Category = "Otherworld|Inventory")
	TSubclassOf<AActor> HandClass;

	UPROPERTY(ReplicatedUsing = OnRep_Hand, BlueprintReadOnly, Category = "Otherworld|Inventory")
	bool HandLit = false;

	UPROPERTY(ReplicatedUsing = OnRep_Hand, BlueprintReadOnly, Category = "Otherworld|Inventory")
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

	/**
	 * A client's: the bool variable of that same component raised when a
	 * record, or what another player's hand holds, arrives: its view remakes
	 * the item actors on its next Tick. None raises nothing.
	 */
	UPROPERTY(EditAnywhere, Category = "Otherworld|Inventory|View")
	FName ViewDirtyVar = TEXT("ViewDirty");

	/** The record component of Carrier: the character, or one of its components. */
	static UOtherworldInventoryRecordComponent* Of(const UObject* Carrier);

	bool IsDirty() const { return bDirty; }
	/** The record written off the item actors. */
	void Write();
	/** With nothing marked: is the record what the item actors say? If not, logged, counted and written. */
	void Audit();
	/** This component's Inventory or Worn holds Item. */
	bool Carries(const AActor* Item) const;

private:
	UFUNCTION()
	void OnRep_Record();

	/** What another player's hand holds arrived (each of the three calls it). */
	UFUNCTION()
	void OnRep_Hand();

	/** ViewDirtyVar raised on the weapon component. */
	void RaiseViewDirty();

	/** The component on the same actor whose class has InventoryVar. */
	UActorComponent* Source();
	void Read(UActorComponent* From, FOtherworldInventoryRecord& OutRecord, TSubclassOf<AActor>& OutHand,
		bool& bOutLit, bool& bOutHot) const;

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

	// The view's reads (Scripts/combat/weapon_component/view.py), each off
	// the record as this machine holds it. Carrier is the character or one
	// of its components. Kind types the Class pin for the graph: the class
	// every carried item is a child of. Pure: read again at every use.

	/** The rows of Carrier's record: its own player's on the owning client, none on anyone else's. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static int32 InventoryRowCount(const UObject* Carrier);

	/** Row Index of Carrier's record. No such row: no class, slot -1. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory",
		meta = (DeterminesOutputType = "Kind", DynamicOutputParam = "Class"))
	static void InventoryRow(const UObject* Carrier, int32 Index, TSubclassOf<AActor> Kind,
		TSubclassOf<AActor>& Class, int32& Slot, int32& Loaded, int32& Reserve, bool& Lit, bool& Hot);

	/** The worn slots of Carrier's record. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static int32 WornRowCount(const UObject* Carrier);

	/** The class worn in Slot, or none. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory",
		meta = (DeterminesOutputType = "Kind", DynamicOutputParam = "Class"))
	static void WornRow(const UObject* Carrier, int32 Slot, TSubclassOf<AActor> Kind, TSubclassOf<AActor>& Class);

	/** What Carrier's hand holds, as everyone but its owner is told it. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory",
		meta = (DeterminesOutputType = "Kind", DynamicOutputParam = "Class"))
	static void HandRow(const UObject* Carrier, TSubclassOf<AActor> Kind, TSubclassOf<AActor>& Class, bool& Lit,
		bool& Hot);

	// The save's (task M35 writes them into the profile), and the probes'.

	/** Carrier's record as this machine holds it. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static FOtherworldInventoryRecord InventoryRecordOf(const UObject* Carrier);

	/** Record as a save holds it (FOtherworldInventoryRecord::ToBytes). */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static TArray<uint8> InventoryRecordToBytes(const FOtherworldInventoryRecord& Record);

	/** The record a save held. False for bytes this build does not read (FromBytes). */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Inventory")
	static bool InventoryRecordFromBytes(const TArray<uint8>& Bytes, FOtherworldInventoryRecord& Record);

	/** The version ToBytes writes first. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static int32 InventoryRecordSaveVersion();

	/** A record as text: "Class@slot loaded/reserve[ lit][ hot], ... | worn, ...". */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Inventory")
	static FString DescribeRecord(const FOtherworldInventoryRecord& Record);

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

/**
 * A save that holds one record as bytes: the shape the character's save
 * takes in task M35, and what the probe round-trips through a slot
 * (Scripts/probes/probe_record_bytes.py).
 */
UCLASS()
class OTHERWORLD_API UOtherworldRecordSave : public USaveGame
{
	GENERATED_BODY()

public:
	/** FOtherworldInventoryRecord::ToBytes. */
	UPROPERTY(BlueprintReadWrite, Category = "Otherworld|Inventory")
	TArray<uint8> Record;
};
