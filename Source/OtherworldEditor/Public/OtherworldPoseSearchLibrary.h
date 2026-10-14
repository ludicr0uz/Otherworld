#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldPoseSearchLibrary.generated.h"

class UPoseSearchDatabase;

/**
 * A pose search database's entries for the Python builders (Scripts/combat/gas_sprint.py):
 * DatabaseAnimationAssets is a plain UPROPERTY() and Python can read only the asset of an
 * entry, not its settings, and write nothing. The caller saves the database.
 */
UCLASS()
class OTHERWORLDEDITOR_API UOtherworldPoseSearchLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Puts To in place of From in every entry of the database that plays From, keeping each
	 * entry's other settings (enabled, reselection, mirroring, sampling range). Returns how
	 * many entries changed; 0 when none plays From.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|PoseSearch")
	static int32 ReplaceDatabaseAnimation(UPoseSearchDatabase* Database, UObject* From, UObject* To);

	/**
	 * One entry's asset and settings. MirrorOption is EPoseSearchMirrorOption as a number
	 * (0 original only, 1 mirrored only, 2 both), which Python cannot name. False past the end.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|PoseSearch")
	static bool GetDatabaseEntry(const UPoseSearchDatabase* Database, int32 Index, UObject*& Asset,
		bool& bEnabled, bool& bDisableReselection, int32& MirrorOption, FVector2D& SamplingRange);
};
