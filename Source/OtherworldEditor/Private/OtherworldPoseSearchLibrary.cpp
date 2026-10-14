#include "OtherworldPoseSearchLibrary.h"

#include "PoseSearch/PoseSearchDatabase.h"

int32 UOtherworldPoseSearchLibrary::ReplaceDatabaseAnimation(UPoseSearchDatabase* Database, UObject* From, UObject* To)
{
	if (!Database || !From || !To)
	{
		return 0;
	}
	int32 Replaced = 0;
	for (int32 Index = 0; Index < Database->GetNumAnimationAssets(); ++Index)
	{
		const FPoseSearchDatabaseAnimationAsset* Entry = Database->GetDatabaseAnimationAsset(Index);
		if (!Entry || Entry->AnimAsset != From)
		{
			continue;
		}
		if (Replaced == 0)
		{
			Database->Modify();
		}
		FPoseSearchDatabaseAnimationAsset Changed = *Entry;
		Changed.AnimAsset = To;
		Database->SetAnimationAssetAt(Changed, Index);
		++Replaced;
	}
	if (Replaced > 0)
	{
		Database->MarkPackageDirty();
	}
	return Replaced;
}

bool UOtherworldPoseSearchLibrary::GetDatabaseEntry(const UPoseSearchDatabase* Database, int32 Index, UObject*& Asset,
	bool& bEnabled, bool& bDisableReselection, int32& MirrorOption, FVector2D& SamplingRange)
{
	const FPoseSearchDatabaseAnimationAsset* Entry = Database ? Database->GetDatabaseAnimationAsset(Index) : nullptr;
	if (!Entry)
	{
		return false;
	}
	Asset = Entry->AnimAsset;
	bEnabled = Entry->bEnabled;
	bDisableReselection = Entry->bDisableReselection;
	MirrorOption = static_cast<int32>(Entry->MirrorOption);
	SamplingRange = FVector2D(Entry->SamplingRange.Min, Entry->SamplingRange.Max);
	return true;
}
