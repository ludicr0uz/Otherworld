// UOtherworldInventoryLibrary: what the graphs, the save and the probes say
// to a player's record and read off it (OtherworldInventoryRecord.h).
#include "OtherworldInventoryRecord.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "Net/Core/PushModel/PushModel.h"

namespace
{
	FString ClassName(const UClass* Class)
	{
		return Class ? Class->GetName() : FString(TEXT("-"));
	}
}

void UOtherworldInventoryLibrary::MarkInventoryDirty(UObject* Carrier)
{
	if (UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier))
	{
		Component->MarkDirty();
	}
}

int32 UOtherworldInventoryLibrary::InventoryRowCount(const UObject* Carrier)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	return Component ? Component->Record.Items.Num() : 0;
}

void UOtherworldInventoryLibrary::InventoryRow(const UObject* Carrier, int32 Index, TSubclassOf<AActor> Kind,
	TSubclassOf<AActor>& Class, int32& Slot, int32& Loaded, int32& Reserve, bool& Lit, bool& Hot)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	const FOtherworldItemRow Row = Component && Component->Record.Items.IsValidIndex(Index)
		? Component->Record.Items[Index] : FOtherworldItemRow();
	Class = Row.Class;
	Slot = Row.Slot;
	Loaded = Row.Loaded;
	Reserve = Row.Reserve;
	Lit = Row.bLit;
	Hot = Row.bHot;
}

int32 UOtherworldInventoryLibrary::WornRowCount(const UObject* Carrier)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	return Component ? Component->Record.Worn.Num() : 0;
}

void UOtherworldInventoryLibrary::WornRow(const UObject* Carrier, int32 Slot, TSubclassOf<AActor> Kind,
	TSubclassOf<AActor>& Class)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	Class = Component && Component->Record.Worn.IsValidIndex(Slot) ? Component->Record.Worn[Slot] : nullptr;
}

void UOtherworldInventoryLibrary::HandRow(const UObject* Carrier, TSubclassOf<AActor> Kind,
	TSubclassOf<AActor>& Class, bool& Lit, bool& Hot)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	Class = Component ? Component->HandClass : nullptr;
	Lit = Component && Component->HandLit;
	Hot = Component && Component->HandHot;
}

FOtherworldInventoryRecord UOtherworldInventoryLibrary::InventoryRecordOf(const UObject* Carrier)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	return Component ? Component->Record : FOtherworldInventoryRecord();
}

TArray<uint8> UOtherworldInventoryLibrary::InventoryRecordToBytes(const FOtherworldInventoryRecord& Record)
{
	TArray<uint8> Bytes;
	Record.ToBytes(Bytes);
	return Bytes;
}

bool UOtherworldInventoryLibrary::InventoryRecordFromBytes(const TArray<uint8>& Bytes, FOtherworldInventoryRecord& Record)
{
	Record = FOtherworldInventoryRecord();
	return Record.FromBytes(Bytes);
}

int32 UOtherworldInventoryLibrary::InventoryRecordSaveVersion()
{
	return static_cast<int32>(FOtherworldInventoryRecord::SaveVersion);
}

FString UOtherworldInventoryLibrary::DescribeRecord(const FOtherworldInventoryRecord& Record)
{
	return Record.Describe();
}

void UOtherworldInventoryLibrary::MarkCarriedItemDirty(AActor* Item)
{
	UWorld* World = Item ? Item->GetWorld() : nullptr;
	if (!World || !Item->HasAuthority())
	{
		return;
	}
	if (UOtherworldInventoryRecords* Records = World->GetSubsystem<UOtherworldInventoryRecords>())
	{
		Records->MarkCarrierOf(Item);
	}
}

FString UOtherworldInventoryLibrary::DescribeInventoryRecord(const AActor* Carrier)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	if (!Component)
	{
		return FString();
	}
	return FString::Printf(TEXT("%s || hand %s%s%s"), *Component->Record.Describe(), *ClassName(Component->HandClass),
		Component->HandLit ? TEXT(" lit") : TEXT(""), Component->HandHot ? TEXT(" hot") : TEXT(""));
}

int32 UOtherworldInventoryLibrary::InventoryRecordWrites(const AActor* Carrier)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	return Component ? Component->Writes : -1;
}

int32 UOtherworldInventoryLibrary::InventoryRecordStale(const AActor* Carrier)
{
	const UOtherworldInventoryRecordComponent* Component = UOtherworldInventoryRecordComponent::Of(Carrier);
	return Component ? Component->Stale : -1;
}

void UOtherworldInventoryLibrary::SetInventoryRecordAudit(bool bOn)
{
	if (IConsoleVariable* Audit = IConsoleManager::Get().FindConsoleVariable(TEXT("Otherworld.InventoryRecord.Audit")))
	{
		Audit->Set(bOn ? 1 : 0, ECVF_SetByCode);
	}
}

bool UOtherworldInventoryLibrary::IsPushModelOn()
{
	return IS_PUSH_MODEL_ENABLED();
}
