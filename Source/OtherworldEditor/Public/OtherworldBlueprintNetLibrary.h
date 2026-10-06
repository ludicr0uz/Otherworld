#pragma once

#include "CoreMinimal.h"
#include "EdGraph/EdGraphPin.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OtherworldBlueprintNetLibrary.generated.h"

class UBlueprint;
class UEdGraphNode;

/** Who runs a custom event: the "Replicates" choice of its details panel. */
UENUM(BlueprintType)
enum class EOtherworldRpc : uint8
{
	NotReplicated,
	Multicast,
	Server,
	Client,
};

/** A member variable's "Replication" choice. */
UENUM(BlueprintType)
enum class EOtherworldVarReplication : uint8
{
	None,
	Replicated,
	RepNotify,
};

/**
 * What the Blueprint editor's details panel writes for networked code, for the Python
 * builders (Scripts/uebp/net.py): K2Node_Event's FunctionFlags and a variable's property
 * flags are not reachable from Python. Every setter leaves the Blueprint structurally
 * modified and uncompiled; the caller compiles.
 */
UCLASS()
class OTHERWORLDEDITOR_API UOtherworldBlueprintNetLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Sets a custom event's net flags. False if the node is not a custom event, or overrides a parent's. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool SetCustomEventRpc(UEdGraphNode* EventNode, EOtherworldRpc Rpc, bool bReliable);

	/** Reads back what SetCustomEventRpc wrote on the node. False if the node is not a custom event. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool GetCustomEventRpc(const UEdGraphNode* EventNode, EOtherworldRpc& Rpc, bool& bReliable);

	/** Adds a parameter (an output pin) to a custom event. False if it could not be added. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool AddCustomEventParameter(UEdGraphNode* EventNode, FName ParameterName, const FEdGraphPinType& PinType);

	/** Reads a compiled function's net flags off a class. False if the class has no such function. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool GetCompiledFunctionRpc(const UClass* Class, FName FunctionName, EOtherworldRpc& Rpc, bool& bReliable);

	/**
	 * Sets a member variable's replication. RepNotify creates the OnRep_<Variable> function
	 * graph when the Blueprint has none. False if the Blueprint declares no such variable.
	 */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool SetVariableReplication(UBlueprint* Blueprint, FName VariableName, EOtherworldVarReplication Replication, ELifetimeCondition Condition = COND_None);

	/** Reads back what SetVariableReplication wrote. False if the Blueprint declares no such variable. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool GetVariableReplication(const UBlueprint* Blueprint, FName VariableName, EOtherworldVarReplication& Replication, FName& RepNotifyFunction, TEnumAsByte<ELifetimeCondition>& Condition);

	/** Reads a compiled property's replication off a class. False if the class has no such property. */
	UFUNCTION(BlueprintCallable, Category = "Otherworld|Net")
	static bool GetCompiledPropertyReplication(const UClass* Class, FName PropertyName, EOtherworldVarReplication& Replication, FName& RepNotifyFunction);
};
