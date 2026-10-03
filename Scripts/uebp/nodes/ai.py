"""uebp.nodes.ai -- AIModule and the navigation system."""

FN_GET_BLACKBOARD = "/Script/AIModule.AIBlueprintHelperLibrary.GetBlackboard"
# A move order with no acceptance radius and no strafe options: a stroll. It
# is also NOT a second MoveToActor/MoveToLocation, which the level verifier
# counts to prove the chase has exactly one of each.
FN_SIMPLE_MOVE = "/Script/AIModule.AIBlueprintHelperLibrary.SimpleMoveToLocation"

FN_CLEAR_FOCUS = "/Script/AIModule.AIController.K2_ClearFocus"
# Function paths for the graph nodes
FN_MOVE_TO_ACTOR = "/Script/AIModule.AIController.MoveToActor"
# The same move order with pathfinding switched off: path following still runs,
# it just follows a straight line to the point instead of a Recast path. This
# is what lets a wanderer chase a player who is standing on ground the navmesh
# does not cover.
FN_MOVE_TO_LOCATION = "/Script/AIModule.AIController.MoveToLocation"
# The behaviour tree (npc/controller.py, steps.py, step_task.py, agro.py).
FN_RUN_BT = "/Script/AIModule.AIController.RunBehaviorTree"
# A focus set from a graph has Gameplay priority, above the Move priority
# path following sets on every move, so it holds while the wanderer walks.
FN_SET_FOCUS = "/Script/AIModule.AIController.K2_SetFocus"

FN_FINISH_EXECUTE = "/Script/AIModule.BTTask_BlueprintBase.FinishExecute"

FN_BB_SET_BOOL = "/Script/AIModule.BlackboardComponent.SetValueAsBool"
FN_BB_SET_STRING = "/Script/AIModule.BlackboardComponent.SetValueAsString"

FN_STOP_LOGIC = "/Script/AIModule.BrainComponent.StopLogic"

FN_PROJECT_NAV = "/Script/NavigationSystem.NavigationSystemV1.K2_ProjectPointToNavigation"
FN_RANDOM_NAV = "/Script/NavigationSystem.NavigationSystemV1.K2_GetRandomLocationInNavigableRadius"
# Patrol and senses (npc/patrol.py, senses.py, agro.py).
# K2_GetRandomReachablePointInRadius is PURE: it re-runs its query once per
# output pin read, so only RandomLocation is ever read, straight into a Set.
FN_RANDOM_REACHABLE = ("/Script/NavigationSystem.NavigationSystemV1"
                       ".K2_GetRandomReachablePointInRadius")
