// The record as a save holds it (FOtherworldInventoryRecord::ToBytes,
// FromBytes; OtherworldInventoryRecord.h says what the record is):
//
//   uint32  SaveVersion
//   uint16  rows;   each: class path, int32 slot, loaded, reserve, uint8 flags (1 lit, 2 hot)
//   uint16  worn slots;   each: class path (empty: nothing worn there)
//
// Little-endian; a class path is its UTF-8 length (uint16) and bytes.
#include "OtherworldInventoryRecord.h"

#include "GameFramework/Actor.h"
#include "UObject/Class.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	void PutU16(TArray<uint8>& Bytes, uint16 Value)
	{
		Bytes.Add(static_cast<uint8>(Value));
		Bytes.Add(static_cast<uint8>(Value >> 8));
	}

	void PutU32(TArray<uint8>& Bytes, uint32 Value)
	{
		PutU16(Bytes, static_cast<uint16>(Value));
		PutU16(Bytes, static_cast<uint16>(Value >> 16));
	}

	void PutClass(TArray<uint8>& Bytes, const UClass* Class)
	{
		const FTCHARToUTF8 Path(Class ? *Class->GetPathName() : TEXT(""));
		const uint16 Length = static_cast<uint16>(FMath::Min(Path.Length(), 0xFFFF));
		PutU16(Bytes, Length);
		Bytes.Append(reinterpret_cast<const uint8*>(Path.Get()), Length);
	}

	/** Reads past the end are zeros, and bOk false from then on. */
	struct FSavedBytes
	{
		const TArray<uint8>& Bytes;
		int32 At = 0;
		bool bOk = true;

		explicit FSavedBytes(const TArray<uint8>& InBytes) : Bytes(InBytes) {}

		bool Has(int32 Count)
		{
			bOk = bOk && Count >= 0 && At + Count <= Bytes.Num();
			return bOk;
		}

		uint8 U8()
		{
			return Has(1) ? Bytes[At++] : 0;
		}

		uint16 U16()
		{
			const uint16 Low = U8();
			return Low | static_cast<uint16>(U8() << 8);
		}

		uint32 U32()
		{
			const uint32 Low = U16();
			return Low | (static_cast<uint32>(U16()) << 16);
		}

		/** The class at a path, loaded if it is not; null for no path, or one nothing answers to. */
		UClass* Class()
		{
			const int32 Length = U16();
			if (Length == 0 || !Has(Length))
			{
				return nullptr;
			}
			const FUTF8ToTCHAR Path(reinterpret_cast<const ANSICHAR*>(Bytes.GetData() + At), Length);
			At += Length;
			const FString Name(Path.Length(), Path.Get());
			UClass* Found = FindObject<UClass>(nullptr, *Name);
			if (!Found)
			{
				Found = StaticLoadClass(AActor::StaticClass(), nullptr, *Name, nullptr, LOAD_NoWarn | LOAD_Quiet);
			}
			return Found && Found->IsChildOf(AActor::StaticClass()) ? Found : nullptr;
		}
	};
}

void FOtherworldInventoryRecord::ToBytes(TArray<uint8>& OutBytes) const
{
	OutBytes.Reset();
	PutU32(OutBytes, SaveVersion);
	PutU16(OutBytes, static_cast<uint16>(Items.Num()));
	for (const FOtherworldItemRow& Row : Items)
	{
		PutClass(OutBytes, Row.Class.Get());
		PutU32(OutBytes, static_cast<uint32>(Row.Slot));
		PutU32(OutBytes, static_cast<uint32>(Row.Loaded));
		PutU32(OutBytes, static_cast<uint32>(Row.Reserve));
		OutBytes.Add((Row.bLit ? 1 : 0) | (Row.bHot ? 2 : 0));
	}
	PutU16(OutBytes, static_cast<uint16>(Worn.Num()));
	for (const TSubclassOf<AActor>& Garment : Worn)
	{
		PutClass(OutBytes, Garment.Get());
	}
}

bool FOtherworldInventoryRecord::FromBytes(const TArray<uint8>& Bytes)
{
	FSavedBytes In(Bytes);
	if (In.U32() != SaveVersion || !In.bOk)
	{
		return false;
	}
	FOtherworldInventoryRecord Read;
	const uint32 Rows = In.U16();
	if (Rows > MaxRows)
	{
		return false;
	}
	for (uint32 Index = 0; Index < Rows && In.bOk; ++Index)
	{
		FOtherworldItemRow Row;
		Row.Class = In.Class();
		Row.Slot = static_cast<int32>(In.U32());
		Row.Loaded = static_cast<int32>(In.U32());
		Row.Reserve = static_cast<int32>(In.U32());
		const uint8 Flags = In.U8();
		Row.bLit = (Flags & 1) != 0;
		Row.bHot = (Flags & 2) != 0;
		// An item this build no longer has is not carried.
		if (Row.Class)
		{
			Read.Items.Add(Row);
		}
	}
	const uint32 Slots = In.U16();
	if (Slots > MaxRows)
	{
		return false;
	}
	for (uint32 Index = 0; Index < Slots && In.bOk; ++Index)
	{
		Read.Worn.Add(In.Class());
	}
	if (!In.bOk || In.At != Bytes.Num())
	{
		return false;
	}
	*this = MoveTemp(Read);
	return true;
}
