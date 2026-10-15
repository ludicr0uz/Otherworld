// The tuning tabs' save where there is no Python (a packaged build). The editor,
// PIE and a -game run of the editor binary save a tab through the Python plugin
// (Scripts/graphics_menu/tune_save.py), straight into the tracked CSV under
// Scripts/. A packaged build has no Python plugin (it is UncookedOnly) and no
// Scripts/, so its save writes the same CSV here instead, into the build's own
// Saved/Tuning/, from where Scripts/combat/gun_tuning_take.py takes it back
// into the project as the new defaults (python3 Scripts/take_gun_tuning.py).
//
// The format is Scripts/combat/gun_tuning.py's write_table: a header, then one
// row per subject, a cell per column, empty where the column is not the
// subject's own, numbers as gun_tuning.format_value writes them.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldTuningLibrary.generated.h"

UCLASS()
class OTHERWORLD_API UOtherworldTuningLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Is the Python plugin running here (the editor binary), so a tab's save runs through it? */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Tuning")
	static bool CanRunPython();

	/**
	 * A tab's table as a CSV in Saved/Tuning/FileName. Header is the CSV's
	 * first line ("weapon,damage,..."); each of Subjects is a row, and its
	 * cells are the first (columns of Header - 1) of its Stride cells of
	 * Values, empty where Live says the cell is not the subject's own (Live
	 * may be empty: every cell is). False when the table does not fit or the
	 * file could not be written.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Tuning")
	static bool SaveTuningCsv(const FString& FileName, const FString& Header,
		const TArray<FString>& Subjects, const TArray<double>& Values,
		const TArray<bool>& Live, int32 Stride);

	/** Where SaveTuningCsv writes FileName: the build's Saved/Tuning/, in full. */
	UFUNCTION(BlueprintPure, Category = "Otherworld|Tuning")
	static FString TuningCsvPath(const FString& FileName);

	/** A number as the CSV holds it: rounded to six decimals, then %g (no float noise, ints bare). */
	static FString FormatCell(double Value);
};
