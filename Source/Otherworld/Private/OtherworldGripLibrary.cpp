#include "OtherworldGripLibrary.h"

#include "Components/SceneComponent.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "OtherworldWeaponComponentBase.h"
#include "UObject/UnrealType.h"

namespace
{
	const FName GripTag(TEXT("Grip"));
	const FName HeldVar(TEXT("Held"));
	const TCHAR* CsvHeader = TEXT("item,x,y,z,pitch,yaw,roll");
	// Two numbers nearer than this are one: a cell stepped by 0.1 three times
	// is not 0.3 to the last bit.
	const double Same = 1e-6;

	using FCells = TStaticArray<double, UOtherworldGripLibrary::CellCount>;

	struct FGripTable
	{
		bool bLoaded = false;
		FString File;                   // "" = the game's own
		TArray<FName> Order;            // the rows as the file lists them
		TMap<FName, FCells> Rows;
	};

	FGripTable& Table()
	{
		static FGripTable T;
		return T;
	}

	FString FileOf(const FGripTable& T)
	{
		return T.File.IsEmpty()
			? FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Tuning"), TEXT("grip_nudges.csv"))
			: T.File;
	}

	void Load(FGripTable& T)
	{
		T.bLoaded = true;
		T.Order.Reset();
		T.Rows.Reset();
		TArray<FString> Lines;
		if (!FFileHelper::LoadFileToStringArray(Lines, *FileOf(T)))
		{
			return;
		}
		for (int32 L = 1; L < Lines.Num(); ++L)
		{
			TArray<FString> Parts;
			Lines[L].ParseIntoArray(Parts, TEXT(","), false);
			const FString Name = Parts.Num() ? Parts[0].TrimStartAndEnd() : FString();
			if (Name.IsEmpty())
			{
				continue;
			}
			FCells Cells(InPlace, 0.0);
			for (int32 C = 0; C < UOtherworldGripLibrary::CellCount; ++C)
			{
				// An empty cell, or one the row is too short for, is zero.
				Cells[C] = Parts.IsValidIndex(C + 1) ? FCString::Atod(*Parts[C + 1]) : 0.0;
			}
			const FName Row(*Name);
			if (!T.Rows.Contains(Row))
			{
				T.Order.Add(Row);
			}
			T.Rows.Add(Row, Cells);
		}
	}

	FGripTable& Loaded()
	{
		FGripTable& T = Table();
		if (!T.bLoaded)
		{
			Load(T);
		}
		return T;
	}

	/** A number as the file holds it: no float noise, no trailing zeros. */
	FString Written(double Value)
	{
		FString S = FString::Printf(TEXT("%.6f"), Value);
		while (S.EndsWith(TEXT("0")))
		{
			S.LeftChopInline(1);
		}
		if (S.EndsWith(TEXT(".")))
		{
			S.LeftChopInline(1);
		}
		return (S == TEXT("-0") || S.IsEmpty()) ? TEXT("0") : S;
	}

	FTransform AsTransform(const FCells& C)
	{
		return FTransform(FRotator(C[3], C[4], C[5]), FVector(C[0], C[1], C[2]));
	}

	const USceneComponent* GripOf(const AActor* Item)
	{
		return Item ? Cast<USceneComponent>(
			Item->FindComponentByTag(USceneComponent::StaticClass(), GripTag)) : nullptr;
	}
}

FName UOtherworldGripLibrary::GripRowOf(const AActor* Item)
{
	if (!Item)
	{
		return NAME_None;
	}
	FString Name = Item->GetClass()->GetName();
	Name.RemoveFromEnd(TEXT("_C"));
	return FName(*Name);
}

FTransform UOtherworldGripLibrary::GripNudge(FName Row)
{
	const FCells* Cells = Loaded().Rows.Find(Row);
	return Cells ? AsTransform(*Cells) : FTransform::Identity;
}

FTransform UOtherworldGripLibrary::GripSeat(const AActor* Item)
{
	const USceneComponent* Grip = GripOf(Item);
	if (!Grip)
	{
		return FTransform::Identity;
	}
	const FTransform Seat = Grip->GetRelativeTransform().Inverse();
	const FCells* Cells = Loaded().Rows.Find(GripRowOf(Item));
	// A row of zeros is not multiplied in: the seat is the Grip's to the bit.
	return Cells && !AsTransform(*Cells).Equals(FTransform::Identity, 0.0)
		? Seat * AsTransform(*Cells) : Seat;
}

AActor* UOtherworldGripLibrary::HeldItemOf(const APawn* Pawn)
{
	const UActorComponent* Weapons =
		Pawn ? Pawn->FindComponentByClass<UOtherworldWeaponComponentBase>() : nullptr;
	const FObjectProperty* Held =
		Weapons ? FindFProperty<FObjectProperty>(Weapons->GetClass(), HeldVar) : nullptr;
	return Held ? Cast<AActor>(Held->GetObjectPropertyValue_InContainer(Weapons)) : nullptr;
}

void UOtherworldGripLibrary::ReadGripCells(const AActor* Item, TArray<double>& InTable, int32 First)
{
	if (First < 0 || First + CellCount > InTable.Num())
	{
		return;
	}
	const FCells* Cells = Item ? Loaded().Rows.Find(GripRowOf(Item)) : nullptr;
	for (int32 C = 0; C < CellCount; ++C)
	{
		InTable[First + C] = Cells ? (*Cells)[C] : 0.0;
	}
}

bool UOtherworldGripLibrary::WriteGripCells(AActor* Item, const TArray<double>& InTable, int32 First)
{
	if (!Item || First < 0 || First + CellCount > InTable.Num())
	{
		return false;
	}
	FGripTable& T = Loaded();
	const FName Row = GripRowOf(Item);
	const FCells* Old = T.Rows.Find(Row);
	FCells New(InPlace, 0.0);
	bool bMoved = false;
	for (int32 C = 0; C < CellCount; ++C)
	{
		New[C] = InTable[First + C];
		bMoved |= FMath::Abs(New[C] - (Old ? (*Old)[C] : 0.0)) > Same;
	}
	if (!bMoved)
	{
		return false;
	}
	if (!Old)
	{
		T.Order.Add(Row);
	}
	T.Rows.Add(Row, New);
	if (Item->GetAttachParentActor() && GripOf(Item))
	{
		Item->SetActorRelativeTransform(GripSeat(Item));
	}
	SaveGripNudges();
	return true;
}

void UOtherworldGripLibrary::SetGripNudge(FName Row, FVector Location, FRotator Rotation)
{
	FGripTable& T = Loaded();
	if (!T.Rows.Contains(Row))
	{
		T.Order.Add(Row);
	}
	FCells Cells(InPlace, 0.0);
	Cells[0] = Location.X; Cells[1] = Location.Y; Cells[2] = Location.Z;
	Cells[3] = Rotation.Pitch; Cells[4] = Rotation.Yaw; Cells[5] = Rotation.Roll;
	T.Rows.Add(Row, Cells);
}

bool UOtherworldGripLibrary::SaveGripNudges()
{
	const FGripTable& T = Loaded();
	FString Text = FString(CsvHeader) + TEXT("\n");
	for (const FName& Row : T.Order)
	{
		Text += Row.ToString();
		for (double Cell : T.Rows[Row])
		{
			Text += TEXT(",") + Written(Cell);
		}
		Text += TEXT("\n");
	}
	const bool bWrote = FFileHelper::SaveStringToFile(
		Text, *FileOf(T), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	if (!bWrote)
	{
		UE_LOG(LogTemp, Warning, TEXT("[GRIP] could not write %s"), *FileOf(T));
	}
	return bWrote;
}

int32 UOtherworldGripLibrary::ReloadGripNudges()
{
	FGripTable& T = Table();
	Load(T);
	return T.Order.Num();
}

FString UOtherworldGripLibrary::GripNudgeFile()
{
	return FileOf(Table());
}

void UOtherworldGripLibrary::SetGripNudgeFile(const FString& Path)
{
	FGripTable& T = Table();
	T.File = Path;
	Load(T);
}
