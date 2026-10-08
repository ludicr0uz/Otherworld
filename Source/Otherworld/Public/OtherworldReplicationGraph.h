// The server's replication graph (task A2): which actors each connection is
// sent. Grid spatialisation for everything with a place in the world
// (characters, items, campfires), the always-relevant list for what every
// client needs (the GameState, the PlayerStates), and a node per connection
// for its own player controller, pawn and PlayerState. Nothing here is game
// logic: the distances and rates are the class defaults the Python builders
// write from Scripts/net/relevancy_consts.py, read off each class's CDO.
// Named for the IpNetDriver in Config/DefaultEngine.ini.
#pragma once

#include "CoreMinimal.h"
#include "ReplicationGraph.h"
#include "OtherworldReplicationGraph.generated.h"

/** The per-connection node: the engine's adds the viewer's controller and
 *  view target; this one adds the viewer's PlayerState too. */
UCLASS()
class OTHERWORLD_API UOtherworldReplicationGraphNode_ForConnection : public UReplicationGraphNode_AlwaysRelevant_ForConnection
{
	GENERATED_BODY()

public:
	virtual void GatherActorListsForConnection(const FConnectionGatherActorListParameters& Params) override;

private:
	/** Rebuilt every gather: the viewer's PlayerState. */
	FActorRepListRefView OwnStateList;
};

/** A connection and its own node, for the actors relevant to their owner alone. */
USTRUCT()
struct FOtherworldConnectionNodePair
{
	GENERATED_BODY()
	FOtherworldConnectionNodePair() {}
	FOtherworldConnectionNodePair(UNetConnection* InConnection, UOtherworldReplicationGraphNode_ForConnection* InNode)
		: NetConnection(InConnection), Node(InNode) {}
	bool operator==(UNetConnection* InConnection) const;

	UPROPERTY()
	TObjectPtr<UNetConnection> NetConnection = nullptr;

	UPROPERTY()
	TObjectPtr<UOtherworldReplicationGraphNode_ForConnection> Node = nullptr;
};

UCLASS(transient, config = Engine)
class OTHERWORLD_API UOtherworldReplicationGraph : public UReplicationGraph
{
	GENERATED_BODY()

public:
	UOtherworldReplicationGraph();

	virtual void InitGlobalActorClassSettings() override;
	virtual void InitGlobalGraphNodes() override;
	virtual void InitConnectionGraphNodes(UNetReplicationGraphConnection* RepGraphConnection) override;
	virtual void RouteAddNetworkActorToNodes(const FNewReplicatedActorInfo& ActorInfo, FGlobalActorReplicationInfo& GlobalInfo) override;
	virtual void RouteRemoveNetworkActorToNodes(const FNewReplicatedActorInfo& ActorInfo) override;
	virtual int32 ServerReplicateActors(float DeltaSeconds) override;

	/** Everything with a place in the world: sent to the connections whose
	 *  viewers are within the class's NetCullDistance of it. Dormant actors
	 *  (an item lying still) sit in a cell as static ones. */
	UPROPERTY()
	TObjectPtr<UReplicationGraphNode_GridSpatialization2D> GridNode;

	/** bAlwaysRelevant actors: the GameState and the PlayerStates. */
	UPROPERTY()
	TObjectPtr<UReplicationGraphNode_ActorList> AlwaysRelevantNode;

	/** The size of a grid cell, cm: 100 m, so a 150 m cull distance spans
	 *  two to three cells. */
	UPROPERTY(Config)
	float CellSizeCm = 10000.f;

	/** Each connection's own node. */
	UPROPERTY()
	TArray<FOtherworldConnectionNodePair> ConnectionNodes;

	/** bOnlyRelevantToOwner actors spawned before their owner had a
	 *  connection (the engine's gameplay debugger is one): routed to the
	 *  owner's node once it has one. */
	UPROPERTY()
	TArray<TObjectPtr<AActor>> ActorsWithoutNetConnection;

	UOtherworldReplicationGraphNode_ForConnection* NodeForConnection(UNetConnection* Connection) const;

private:
	/** Actors with no place in the world and no viewer of their own: the
	 *  controllers (each is the connection's own) and anything else the
	 *  engine replicates by other means. Not routed to any node. */
	static bool IsNotRouted(const AActor* Actor);
};
