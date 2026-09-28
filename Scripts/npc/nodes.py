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
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_WARN = "/Script/Engine.KismetSystemLibrary.PrintWarning"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_DISPLAY_NAME = "/Script/Engine.KismetSystemLibrary.GetDisplayName"

NODE_CAST_CHARACTER = "Utilities|Casting|CastToCharacter"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"
