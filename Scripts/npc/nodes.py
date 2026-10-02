"""FN_* function paths and NODE_* palette names used by the NPC graphs."""


# Function paths for the graph nodes
FN_MOVE_TO_ACTOR = "/Script/AIModule.AIController.MoveToActor"
# The same move order with pathfinding switched off: path following still runs,
# it just follows a straight line to the point instead of a Recast path. This
# is what lets a wanderer chase a player who is standing on ground the navmesh
# does not cover.
FN_MOVE_TO_LOCATION = "/Script/AIModule.AIController.MoveToLocation"
FN_PROJECT_NAV = ("/Script/NavigationSystem.NavigationSystemV1"
                  ".K2_ProjectPointToNavigation")
FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
FN_AND_B = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"
FN_GET_PAWN = "/Script/Engine.Controller.K2_GetPawn"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_DISTANCE = "/Script/Engine.KismetMathLibrary.Vector_Distance"
FN_LE_FF = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_GE_FF = "/Script/Engine.KismetMathLibrary.GreaterEqual_DoubleDouble"
FN_EQ_FF = "/Script/Engine.KismetMathLibrary.EqualEqual_DoubleDouble"
FN_GT_FF = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_ADD_FF = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_SUB_FF = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_CLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_ANIM_INSTANCE = "/Script/Engine.SkeletalMeshComponent.GetAnimInstance"
FN_PLAY_SLOT = "/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage"
FN_PLAY_SOUND = "/Script/Engine.GameplayStatics.PlaySoundAtLocation"
FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_RAND_INT = "/Script/Engine.KismetMathLibrary.RandomIntegerInRange"
FN_RANDOM_FLOAT = "/Script/Engine.KismetMathLibrary.RandomFloatInRange"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_GREATER_II = "/Script/Engine.KismetMathLibrary.Greater_IntInt"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_SUB_VV = "/Script/Engine.KismetMathLibrary.Subtract_VectorVector"
FN_NORMAL = "/Script/Engine.KismetMathLibrary.Normal"

# Patrol and senses (npc/patrol.py, senses.py, agro.py).
# K2_GetRandomReachablePointInRadius is PURE: it re-runs its query once per
# output pin read, so only RandomLocation is ever read, straight into a Set.
FN_RANDOM_REACHABLE = ("/Script/NavigationSystem.NavigationSystemV1"
                       ".K2_GetRandomReachablePointInRadius")
# A move order with no acceptance radius and no strafe options: a stroll. It
# is also NOT a second MoveToActor/MoveToLocation, which the level verifier
# counts to prove the chase has exactly one of each.
FN_SIMPLE_MOVE = "/Script/AIModule.AIBlueprintHelperLibrary.SimpleMoveToLocation"
FN_GET_CONTROLLER = "/Script/Engine.Pawn.GetController"
FN_LINE_OF_SIGHT = "/Script/Engine.Controller.LineOfSightTo"
FN_FORWARD = "/Script/Engine.Actor.GetActorForwardVector"
FN_DOT_VV = "/Script/Engine.KismetMathLibrary.Dot_VectorVector"
FN_MUL_FF = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_DEG_COS = "/Script/Engine.KismetMathLibrary.DegCos"
FN_DIV_FF = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_NE_FF = "/Script/Engine.KismetMathLibrary.NotEqual_DoubleDouble"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_WARN = "/Script/Engine.KismetSystemLibrary.PrintWarning"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_DISPLAY_NAME = "/Script/Engine.KismetSystemLibrary.GetDisplayName"

# The combat trace (npc/combat_trace.py) and the corpse state (npc/corpse.py).
FN_PRINT = "/Script/Engine.KismetSystemLibrary.PrintString"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_VEC_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_VectorToString"
FN_FLOAT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_DoubleToString"
FN_BOOL_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_BoolToString"
FN_STOP_MOVEMENT = "/Script/Engine.Controller.StopMovement"

NODE_CAST_CHARACTER = "Utilities|Casting|CastToCharacter"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"

# The behaviour tree (npc/controller.py, steps.py, step_task.py, agro.py).
FN_RUN_BT = "/Script/AIModule.AIController.RunBehaviorTree"
FN_STOP_LOGIC = "/Script/AIModule.BrainComponent.StopLogic"
FN_GET_BLACKBOARD = "/Script/AIModule.AIBlueprintHelperLibrary.GetBlackboard"
FN_BB_SET_BOOL = "/Script/AIModule.BlackboardComponent.SetValueAsBool"
FN_BB_SET_STRING = "/Script/AIModule.BlackboardComponent.SetValueAsString"
FN_FINISH_EXECUTE = "/Script/AIModule.BTTask_BlueprintBase.FinishExecute"
FN_EQ_NAME = "/Script/Engine.KismetMathLibrary.EqualEqual_NameName"
NODE_EVENT_POSSESS = "AddEvent|EventOnPossess"
NODE_EVENT_EXECUTE_AI = "AddEvent|AI|EventReceiveExecuteAI"
# A Name pin passed by reference (the Blackboard's KeyName) takes no literal,
# and EqualEqual_NameName is a wildcard until wired: both are fed from this.
FN_LITERAL_NAME = "/Script/Engine.KismetSystemLibrary.MakeLiteralName"

# Debug mode's sight cone (npc/sight_cone.py): a Tick of the controller's own,
# because the tree's steps run on its beat and a cone has to follow the head.
NODE_EVENT_TICK = "AddEvent|EventTick"
FN_DRAW_CONE = "/Script/Engine.KismetSystemLibrary.DrawDebugConeInDegrees"
FN_SELECT_COLOR = "/Script/Engine.KismetMathLibrary.SelectColor"

# The step between two swings (npc/strafe.py).
FN_LT_FF = "/Script/Engine.KismetMathLibrary.Less_DoubleDouble"
FN_RANDOM_BOOL = "/Script/Engine.KismetMathLibrary.RandomBool"
FN_SELECT_FLOAT = "/Script/Engine.KismetMathLibrary.SelectFloat"
FN_NORMAL_2D = "/Script/Engine.KismetMathLibrary.Vector_Normal2D"
FN_ROTATE_AXIS = "/Script/Engine.KismetMathLibrary.RotateAngleAxis"
FN_ADD_VV = "/Script/Engine.KismetMathLibrary.Add_VectorVector"
FN_MUL_VV = "/Script/Engine.KismetMathLibrary.Multiply_VectorVector"
# A focus set from a graph has Gameplay priority, above the Move priority
# path following sets on every move, so it holds while the wanderer walks.
FN_SET_FOCUS = "/Script/AIModule.AIController.K2_SetFocus"
FN_CLEAR_FOCUS = "/Script/AIModule.AIController.K2_ClearFocus"

# The wendigo's hunt (npc/stalk.py, stalk_cover.py).
FN_SPHERE_TRACE = "/Script/Engine.KismetSystemLibrary.SphereTraceSingle"
FN_LINE_TRACE = "/Script/Engine.KismetSystemLibrary.LineTraceSingle"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_ARR_CLEAR = "/Script/Engine.KismetArrayLibrary.Array_Clear"
# What the pawn stands on: the terrain, which the sweep for a tree ignores.
FN_MOVEMENT_BASE = "/Script/Engine.Pawn.GetMovementBaseActor"
# Pure (it is const): read the bool, branch, then read the transform.
FN_INSTANCE_TRANSFORM = ("/Script/Engine.InstancedStaticMeshComponent"
                         ".GetInstanceTransform")
FN_BREAK_TRANSFORM = "/Script/Engine.KismetMathLibrary.BreakTransform"
FN_BREAK_VECTOR = "/Script/Engine.KismetMathLibrary.BreakVector"
FN_DISTANCE_2D = "/Script/Engine.KismetMathLibrary.Vector_Distance2D"
FN_FMAX = "/Script/Engine.KismetMathLibrary.FMax"
FN_IN_RANGE = "/Script/Engine.KismetMathLibrary.InRange_FloatFloat"
FN_VELOCITY = "/Script/Engine.Actor.GetVelocity"
FN_VSIZE_XY = "/Script/Engine.KismetMathLibrary.VSizeXY"
FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_EQ_OO = "/Script/Engine.KismetMathLibrary.EqualEqual_ObjectObject"
# An object pin of EqualEqual_ObjectObject takes no asset literal, so a mesh
# is told by its name (npc/stalk_cover.py).
FN_OBJECT_NAME = "/Script/Engine.KismetSystemLibrary.GetObjectName"
FN_EQ_SS = "/Script/Engine.KismetStringLibrary.EqualEqual_StrStr"
NODE_BREAK_HIT = "Collision|BreakHitResult"
NODE_CAST_INSTANCED = "Utilities|Casting|CastToInstancedStaticMeshComponent"
