#include "OtherworldReplicationGraph.h"

#include "Engine/ChildConnection.h"
#include "Engine/NetConnection.h"
#include "GameFramework/Controller.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "UObject/UObjectIterator.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(OtherworldReplicationGraph)

void UOtherworldReplicationGraphNode_ForConnection::GatherActorListsForConnection(const FConnectionGatherActorListParameters& Params)
{
	Super::GatherActorListsForConnection(Params);

#if WITH_SERVER_CODE
	// The engine's list holds the viewer (the controller) and its view target
	// (the pawn). The player's own PlayerState is always relevant to them
	// too, whatever the AlwaysRelevantNode does with the others.
	OwnStateList.Reset();
	for (const FNetViewer& Viewer : Params.Viewers)
	{
		const APlayerController* PC = Cast<APlayerController>(Viewer.InViewer);
		if (PC && PC->PlayerState)
		{
			OwnStateList.Add(PC->PlayerState);
		}
	}
	if (OwnStateList.Num() > 0)
	{
		Params.OutGatheredReplicationLists.AddReplicationActorList(OwnStateList);
	}
#endif
}

bool FOtherworldConnectionNodePair::operator==(UNetConnection* InConnection) const
{
	// A child connection (split screen) looks at its parent's node.
	if (InConnection && InConnection->GetUChildConnection() != nullptr)
	{
		InConnection = static_cast<UChildConnection*>(InConnection)->Parent;
	}
	return InConnection == NetConnection;
}

UOtherworldReplicationGraph::UOtherworldReplicationGraph()
{
}

UOtherworldReplicationGraphNode_ForConnection* UOtherworldReplicationGraph::NodeForConnection(UNetConnection* Connection) const
{
	if (const FOtherworldConnectionNodePair* Pair = Connection ? ConnectionNodes.FindByKey(Connection) : nullptr)
	{
		return Pair->Node;
	}
	return nullptr;
}

bool UOtherworldReplicationGraph::IsNotRouted(const AActor* Actor)
{
	// A controller replicates to its own connection only, which the engine
	// does through the connection's owner, not a node.
	return Actor->IsA<AController>();
}

void UOtherworldReplicationGraph::InitGlobalActorClassSettings()
{
	Super::InitGlobalActorClassSettings();

	// One FClassReplicationInfo per replicated actor class, from the class
	// defaults: NetUpdateFrequency becomes a period in server frames, and
	// NetCullDistanceSquared the grid's cull distance. The Python builders
	// write both (Scripts/net/relevancy_consts.py).
	for (TObjectIterator<UClass> It; It; ++It)
	{
		UClass* Class = *It;
		AActor* ActorCDO = Cast<AActor>(Class->GetDefaultObject());
		if (!ActorCDO || !ActorCDO->GetIsReplicated())
		{
			continue;
		}
		if (Class->GetName().StartsWith(TEXT("SKEL_")) || Class->GetName().StartsWith(TEXT("REINST_")))
		{
			continue;
		}

		FClassReplicationInfo ClassInfo;
		ClassInfo.ReplicationPeriodFrame = GetReplicationPeriodFrameForFrequency(ActorCDO->GetNetUpdateFrequency());
		if (ActorCDO->bAlwaysRelevant || ActorCDO->bOnlyRelevantToOwner)
		{
			ClassInfo.SetCullDistanceSquared(0.f);
		}
		else
		{
			ClassInfo.SetCullDistanceSquared(ActorCDO->GetNetCullDistanceSquared());
		}
		GlobalActorReplicationInfoMap.SetClassInfo(Class, ClassInfo);
	}
}

void UOtherworldReplicationGraph::InitGlobalGraphNodes()
{
	GridNode = CreateNewNode<UReplicationGraphNode_GridSpatialization2D>();
	GridNode->CellSize = CellSizeCm;
	GridNode->SpatialBias = FVector2D(-UE_OLD_WORLD_MAX, -UE_OLD_WORLD_MAX);
	AddGlobalGraphNode(GridNode);

	AlwaysRelevantNode = CreateNewNode<UReplicationGraphNode_ActorList>();
	AddGlobalGraphNode(AlwaysRelevantNode);
}

void UOtherworldReplicationGraph::InitConnectionGraphNodes(UNetReplicationGraphConnection* RepGraphConnection)
{
	Super::InitConnectionGraphNodes(RepGraphConnection);

	UOtherworldReplicationGraphNode_ForConnection* Own = CreateNewNode<UOtherworldReplicationGraphNode_ForConnection>();
	AddConnectionGraphNode(Own, RepGraphConnection);
	ConnectionNodes.Emplace(RepGraphConnection->NetConnection, Own);
}

void UOtherworldReplicationGraph::RouteAddNetworkActorToNodes(const FNewReplicatedActorInfo& ActorInfo, FGlobalActorReplicationInfo& GlobalInfo)
{
	AActor* Actor = ActorInfo.Actor;
	if (IsNotRouted(Actor))
	{
		return;
	}
	if (Actor->bAlwaysRelevant)
	{
		AlwaysRelevantNode->NotifyAddNetworkActor(ActorInfo);
		return;
	}
	if (Actor->bOnlyRelevantToOwner)
	{
		// Its owner's node, once the owner has a connection (ServerReplicateActors).
		ActorsWithoutNetConnection.Add(Actor);
		return;
	}
	// Everything else has a place in the world. The dormancy variant treats
	// the actor as moving while awake and as standing still once dormant,
	// which is what an item lying on the ground becomes (item_world.py).
	GridNode->AddActor_Dormancy(ActorInfo, GlobalInfo);
}

void UOtherworldReplicationGraph::RouteRemoveNetworkActorToNodes(const FNewReplicatedActorInfo& ActorInfo)
{
	AActor* Actor = ActorInfo.Actor;
	if (IsNotRouted(Actor))
	{
		return;
	}
	if (Actor->bAlwaysRelevant)
	{
		AlwaysRelevantNode->NotifyRemoveNetworkActor(ActorInfo);
		SetActorDestructionInfoToIgnoreDistanceCulling(ActorInfo.GetActor());
		return;
	}
	if (Actor->bOnlyRelevantToOwner)
	{
		ActorsWithoutNetConnection.Remove(Actor);
		if (UReplicationGraphNode* Node = NodeForConnection(Actor->GetNetConnection()))
		{
			Node->NotifyRemoveNetworkActor(ActorInfo, false);
		}
		return;
	}
	GridNode->RemoveActor_Dormancy(ActorInfo);
}

int32 UOtherworldReplicationGraph::ServerReplicateActors(float DeltaSeconds)
{
	for (int32 Index = ActorsWithoutNetConnection.Num() - 1; Index >= 0; --Index)
	{
		AActor* Actor = ActorsWithoutNetConnection[Index];
		bool bRemove = (Actor == nullptr);
		if (Actor)
		{
			if (UReplicationGraphNode* Node = NodeForConnection(Actor->GetNetConnection()))
			{
				Node->NotifyAddNetworkActor(FNewReplicatedActorInfo(Actor));
				bRemove = true;
			}
		}
		if (bRemove)
		{
			ActorsWithoutNetConnection.RemoveAtSwap(Index, EAllowShrinking::No);
		}
	}
	return Super::ServerReplicateActors(DeltaSeconds);
}
