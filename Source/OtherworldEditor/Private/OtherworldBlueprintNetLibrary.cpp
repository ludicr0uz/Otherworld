#include "OtherworldBlueprintNetLibrary.h"

#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "K2Node_CustomEvent.h"
#include "Kismet2/BlueprintEditorUtils.h"

namespace
{
	const uint32 RpcFlags = FUNC_Net | FUNC_NetMulticast | FUNC_NetServer | FUNC_NetClient;

	uint32 FlagsOfRpc(const EOtherworldRpc Rpc)
	{
		switch (Rpc)
		{
		case EOtherworldRpc::Multicast: return FUNC_Net | FUNC_NetMulticast;
		case EOtherworldRpc::Server: return FUNC_Net | FUNC_NetServer;
		case EOtherworldRpc::Client: return FUNC_Net | FUNC_NetClient;
		default: return 0;
		}
	}

	void RpcOfFlags(const uint32 Flags, EOtherworldRpc& Rpc, bool& bReliable)
	{
		Rpc = EOtherworldRpc::NotReplicated;
		if (Flags & FUNC_Net)
		{
			if (Flags & FUNC_NetMulticast)
			{
				Rpc = EOtherworldRpc::Multicast;
			}
			else if (Flags & FUNC_NetServer)
			{
				Rpc = EOtherworldRpc::Server;
			}
			else if (Flags & FUNC_NetClient)
			{
				Rpc = EOtherworldRpc::Client;
			}
		}
		bReliable = Rpc != EOtherworldRpc::NotReplicated && (Flags & FUNC_NetReliable) != 0;
	}

	void ReplicationOfFlags(const uint64 Flags, EOtherworldVarReplication& Replication)
	{
		Replication = !(Flags & CPF_Net) ? EOtherworldVarReplication::None
			: (Flags & CPF_RepNotify) ? EOtherworldVarReplication::RepNotify
			: EOtherworldVarReplication::Replicated;
	}
}

// As FBaseBlueprintGraphActionDetails::SetNetFlags and OnIsReliableReplicationFunctionModified.
bool UOtherworldBlueprintNetLibrary::SetCustomEventRpc(UEdGraphNode* EventNode, const EOtherworldRpc Rpc, const bool bReliable)
{
	UK2Node_CustomEvent* Event = Cast<UK2Node_CustomEvent>(EventNode);
	if (!Event || Event->IsOverride())
	{
		return false;
	}

	Event->Modify();
	Event->FunctionFlags &= ~(RpcFlags | FUNC_NetReliable);
	Event->FunctionFlags |= FlagsOfRpc(Rpc);
	if (bReliable && Rpc != EOtherworldRpc::NotReplicated)
	{
		Event->FunctionFlags |= FUNC_NetReliable;
	}

	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForNode(Event))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	}
	return true;
}

bool UOtherworldBlueprintNetLibrary::GetCustomEventRpc(const UEdGraphNode* EventNode, EOtherworldRpc& Rpc, bool& bReliable)
{
	Rpc = EOtherworldRpc::NotReplicated;
	bReliable = false;
	const UK2Node_CustomEvent* Event = Cast<UK2Node_CustomEvent>(EventNode);
	if (!Event)
	{
		return false;
	}
	RpcOfFlags(Event->FunctionFlags, Rpc, bReliable);
	return true;
}

bool UOtherworldBlueprintNetLibrary::AddCustomEventParameter(UEdGraphNode* EventNode, const FName ParameterName, const FEdGraphPinType& PinType)
{
	UK2Node_CustomEvent* Event = Cast<UK2Node_CustomEvent>(EventNode);
	if (!Event || Event->IsOverride() || ParameterName.IsNone() || Event->FindPin(ParameterName))
	{
		return false;
	}

	Event->Modify();
	if (!Event->CreateUserDefinedPin(ParameterName, PinType, EGPD_Output))
	{
		return false;
	}

	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForNode(Event))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	}
	return true;
}

bool UOtherworldBlueprintNetLibrary::GetCompiledFunctionRpc(const UClass* Class, const FName FunctionName, EOtherworldRpc& Rpc, bool& bReliable)
{
	Rpc = EOtherworldRpc::NotReplicated;
	bReliable = false;
	const UFunction* Function = Class ? Class->FindFunctionByName(FunctionName) : nullptr;
	if (!Function)
	{
		return false;
	}
	RpcOfFlags(Function->FunctionFlags, Rpc, bReliable);
	return true;
}

// As FBlueprintVarActionDetails::OnChangeReplication and ReplicationOnRepFuncChanged.
bool UOtherworldBlueprintNetLibrary::SetVariableReplication(UBlueprint* Blueprint, const FName VariableName, const EOtherworldVarReplication Replication, const ELifetimeCondition Condition)
{
	const int32 VarIndex = Blueprint ? FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VariableName) : INDEX_NONE;
	if (VarIndex == INDEX_NONE)
	{
		return false;
	}

	Blueprint->Modify();
	FBPVariableDescription& Variable = Blueprint->NewVariables[VarIndex];
	FName RepNotifyFunction = NAME_None;
	if (Replication == EOtherworldVarReplication::None)
	{
		Variable.PropertyFlags &= ~(CPF_Net | CPF_RepNotify);
		Variable.ReplicationCondition = COND_None;
	}
	else
	{
		Variable.PropertyFlags |= CPF_Net;
		Variable.ReplicationCondition = Condition;
		if (Replication == EOtherworldVarReplication::RepNotify)
		{
			RepNotifyFunction = FName(*FString::Printf(TEXT("OnRep_%s"), *VariableName.ToString()));
			if (!FindObject<UEdGraph>(Blueprint, *RepNotifyFunction.ToString()))
			{
				UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(Blueprint, RepNotifyFunction, UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
				FBlueprintEditorUtils::AddFunctionGraph<UClass>(Blueprint, Graph, false, nullptr);
			}
			Variable.PropertyFlags |= CPF_RepNotify;
		}
		else
		{
			Variable.PropertyFlags &= ~CPF_RepNotify;
		}
	}
	Variable.RepNotifyFunc = RepNotifyFunction;

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	return true;
}

bool UOtherworldBlueprintNetLibrary::GetVariableReplication(const UBlueprint* Blueprint, const FName VariableName, EOtherworldVarReplication& Replication, FName& RepNotifyFunction, TEnumAsByte<ELifetimeCondition>& Condition)
{
	Replication = EOtherworldVarReplication::None;
	RepNotifyFunction = NAME_None;
	Condition = COND_None;
	const int32 VarIndex = Blueprint ? FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VariableName) : INDEX_NONE;
	if (VarIndex == INDEX_NONE)
	{
		return false;
	}

	const FBPVariableDescription& Variable = Blueprint->NewVariables[VarIndex];
	ReplicationOfFlags(Variable.PropertyFlags, Replication);
	RepNotifyFunction = Variable.RepNotifyFunc;
	Condition = Variable.ReplicationCondition;
	return true;
}

bool UOtherworldBlueprintNetLibrary::GetCompiledPropertyReplication(const UClass* Class, const FName PropertyName, EOtherworldVarReplication& Replication, FName& RepNotifyFunction)
{
	Replication = EOtherworldVarReplication::None;
	RepNotifyFunction = NAME_None;
	const FProperty* Property = Class ? Class->FindPropertyByName(PropertyName) : nullptr;
	if (!Property)
	{
		return false;
	}
	ReplicationOfFlags(Property->PropertyFlags, Replication);
	RepNotifyFunction = Property->RepNotifyFunc;
	return true;
}
