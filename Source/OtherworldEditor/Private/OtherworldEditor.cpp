#include "Modules/ModuleManager.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "UObject/ObjectSaveContext.h"
#include "UObject/UObjectGlobals.h"

DEFINE_LOG_CATEGORY_STATIC(LogOtherworldEditor, Log, All);

// UE 5.8's UBlueprintGraphEditor::AddCommentNode (the Python add_comment_to_nodes) never calls
// CreateNewGuid, so every scripted comment saved with no NodeGuid and the cook warned about each.
// Python cannot write NodeGuid, so any Blueprint about to save gets a GUID on every node without one.
class FOtherworldEditorModule : public FDefaultModuleImpl
{
public:
	virtual void StartupModule() override
	{
		PreSaveHandle = FCoreUObjectDelegates::OnObjectPreSave.AddStatic(&FOtherworldEditorModule::OnPreSave);
	}

	virtual void ShutdownModule() override
	{
		FCoreUObjectDelegates::OnObjectPreSave.Remove(PreSaveHandle);
	}

private:
	static void OnPreSave(UObject* Object, FObjectPreSaveContext Context)
	{
		UBlueprint* Blueprint = Cast<UBlueprint>(Object);
		if (!Blueprint || Context.IsProceduralSave())
		{
			return;
		}
		TArray<UEdGraph*> Graphs;
		Blueprint->GetAllGraphs(Graphs);
		int32 Fixed = 0;
		for (UEdGraph* Graph : Graphs)
		{
			if (!Graph)
			{
				continue;
			}
			for (UEdGraphNode* Node : Graph->Nodes)
			{
				if (Node && !Node->NodeGuid.IsValid())
				{
					Node->CreateNewGuid();
					++Fixed;
				}
			}
		}
		if (Fixed > 0)
		{
			UE_LOG(LogOtherworldEditor, Log, TEXT("Gave %d node(s) a NodeGuid before saving %s"), Fixed, *Blueprint->GetPathName());
		}
	}

	FDelegateHandle PreSaveHandle;
};

IMPLEMENT_MODULE(FOtherworldEditorModule, OtherworldEditor);
