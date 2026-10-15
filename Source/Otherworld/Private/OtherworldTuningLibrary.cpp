#include "OtherworldTuningLibrary.h"

#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"

bool UOtherworldTuningLibrary::CanRunPython()
{
	return FModuleManager::Get().IsModuleLoaded(TEXT("PythonScriptPlugin"));
}

FString UOtherworldTuningLibrary::TuningCsvPath(const FString& FileName)
{
	return FPaths::ConvertRelativePathToFull(
		FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Tuning"), FileName));
}

FString UOtherworldTuningLibrary::FormatCell(double Value)
{
	// Python's f"{round(v, 6):g}": six significant digits, no trailing zeros.
	const double Rounded = FMath::RoundToDouble(Value * 1e6) / 1e6;
	FString Text = FString::Printf(TEXT("%g"), Rounded);
	return Text == TEXT("-0") ? FString(TEXT("0")) : Text;
}

bool UOtherworldTuningLibrary::SaveTuningCsv(const FString& FileName, const FString& Header,
	const TArray<FString>& Subjects, const TArray<double>& Values,
	const TArray<bool>& Live, int32 Stride)
{
	TArray<FString> Columns;
	Header.ParseIntoArray(Columns, TEXT(","), false);
	const int32 Cells = Columns.Num() - 1;
	const FString Path = TuningCsvPath(FileName);
	if (Cells < 1 || Stride < Cells || Values.Num() != Subjects.Num() * Stride
		|| (Live.Num() && Live.Num() != Values.Num()))
	{
		UE_LOG(LogTemp, Warning, TEXT("[TUNE] %s: %d values, %d live for %d rows of %d (%d columns)"),
			*Path, Values.Num(), Live.Num(), Subjects.Num(), Stride, Cells);
		return false;
	}
	FString Text = Header + TEXT("\n");
	for (int32 Row = 0; Row < Subjects.Num(); ++Row)
	{
		Text += Subjects[Row];
		for (int32 Cell = 0; Cell < Cells; ++Cell)
		{
			const int32 At = Row * Stride + Cell;
			Text += TEXT(",");
			if (!Live.Num() || Live[At])
			{
				Text += FormatCell(Values[At]);
			}
		}
		Text += TEXT("\n");
	}
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
	const bool bWrote = FFileHelper::SaveStringToFile(
		Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	if (bWrote)
	{
		UE_LOG(LogTemp, Warning, TEXT("[TUNE] saved %d rows to %s"), Subjects.Num(), *Path);
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("[TUNE] could not write %s"), *Path);
	}
	return bWrote;
}
