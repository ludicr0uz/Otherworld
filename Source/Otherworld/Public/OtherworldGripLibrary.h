// The grip nudges (H2): a table of per-item position and rotation nudges, laid
// over the place an item's Grip component gives it in the hand, and read by the
// running game, so a number is a restart and not a build.
//
// The table is a CSV, Content/Tuning/grip_nudges.csv (staged loose with a
// packaged build), one row per held item's class: item,x,y,z,pitch,yaw,roll,
// centimetres and degrees in the grip socket's frame. Every machine reads it
// once, the first time anything asks, so the server, the clients and the menu
// seat an item alike. Scripts/combat/grip_nudges.py is the same format in
// Python (the unit tests hold the two together through the probe).
//
// An item's seat under the socket is inverse(Grip) * nudge: the nudge turns it
// about the socket (the hand) and then moves it. A row of zeros, or no row, is
// the identity, and the seat is the Grip's alone.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldGripLibrary.generated.h"

class AActor;
class APawn;

UCLASS()
class OTHERWORLD_API UOtherworldGripLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** How many numbers a row has: x y z pitch yaw roll. */
	static constexpr int32 CellCount = 6;

	/** An item's row: its class's name without the _C (BP_Knife). None for null. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Grip")
	static FName GripRowOf(const AActor* Item);

	/** A row as a transform; the identity for a row the table lacks. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Grip")
	static FTransform GripNudge(FName Row);

	/**
	 * Where the item sits under the grip socket: the inverse of its Grip
	 * component's relative transform, then its row. The identity for an item
	 * with no Grip. The equip sets the item's relative transform to this.
	 */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Grip")
	static FTransform GripSeat(const AActor* Item);

	/** The item the pawn's weapon component holds (its Held), or null. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Grip")
	static AActor* HeldItemOf(const APawn* Pawn);

	/**
	 * The item's row into six cells of a tuning page's table, from First on.
	 * Zeros for null. Nothing where the table is too short.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Grip")
	static void ReadGripCells(const AActor* Item, UPARAM(ref) TArray<double>& Table, int32 First);

	/**
	 * Six cells of a tuning page's table as the item's row. Where they are not
	 * the row already: the row takes them, the item is seated anew if it is
	 * attached, and the table is written to its file. True when it moved.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Grip")
	static bool WriteGripCells(AActor* Item, const TArray<double>& Table, int32 First);

	/** A row in memory alone: no file is written and nothing is seated. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Grip")
	static void SetGripNudge(FName Row, FVector Location, FRotator Rotation);

	/** The table to its file. False when the file could not be written. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Grip")
	static bool SaveGripNudges();

	/** Read the file again, as a launch does. Returns its rows. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Grip")
	static int32 ReloadGripNudges();

	/** The file the table is read from and written to. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Grip")
	static FString GripNudgeFile();

	/**
	 * For the probes: another file ("" = the game's own), read at once, so a
	 * probe never writes the tracked table.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Grip")
	static void SetGripNudgeFile(const FString& Path);
};
