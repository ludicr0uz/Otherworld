"""uebp.nodes.palette -- palette nodes (events, casts, break/make) and the
standard macros, and the
actor and component macros (the authority switch).
"""

# Switch Has Authority: exec outs "Authority" and "Remote". An actor graph takes
# the first, a component graph the second (it asks its owner).
MACRO_SWITCH_AUTHORITY = "/Engine/EditorBlueprintResources/ActorMacros.ActorMacros:Switch Has Authority"
MACRO_SWITCH_AUTHORITY_COMP = (
    "/Engine/EditorBlueprintResources/ActorComponentMacros.ActorComponentMacros:Switch Has Authority")

MACRO_FOR_EACH = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop"
MACRO_FOR_LOOP = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForLoop"

NODE_ABILITY_FROM_EVENT = "AddEvent|Ability|EventActivateAbilityFromEvent"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
# The DrawHUD event is not one of the placeholder nodes a fresh Blueprint ships
# with (BeginPlay and Tick are), so it has to be created from the palette.
NODE_DRAW_HUD = "AddEvent|EventReceiveDrawHUD"
NODE_EVENT_EXECUTE_AI = "AddEvent|AI|EventReceiveExecuteAI"
NODE_EVENT_POSSESS = "AddEvent|EventOnPossess"
NODE_PRE_CONSTRUCT = "AddEvent|UserInterface|EventPreConstruct"
# Debug mode's sight cone (npc/sight_cone.py): a Tick of the controller's own,
# because the tree's steps run on its beat and a cone has to follow the head.
NODE_TICK = "AddEvent|EventTick"

NODE_MODIFY_BONE = "Animation|SkeletalControls|Transform(Modify)Bone"
NODE_TO_COMPONENT = "Animation|ConvertSpaces|LocalToComponent"
NODE_TO_LOCAL = "Animation|ConvertSpaces|ComponentToLocal"
NODE_TWO_BONE_IK = "Animation|SkeletalControls|TwoBoneIK"

NODE_BREAK_HIT = "Collision|BreakHitResult"

NODE_SPAWN = "Game|SpawnActorfromClass"

NODE_CREATE_WIDGET = "UserInterface|CreateWidget"

NODE_BREAK_EVENT_DATA = "Utilities|Struct|BreakGameplayEventData"
NODE_CAST_CHAR = "Utilities|Casting|CastToBP_ThirdPersonCharacter"
NODE_CAST_CHARACTER = "Utilities|Casting|CastToCharacter"
NODE_CAST_CONSUMABLE = "Utilities|Casting|CastToBP_ConsumableItem"
NODE_CAST_CYCLE = "Utilities|Casting|CastToBP_DayNightCycle"
NODE_CAST_FOOTSTEP = "Utilities|Casting|CastToBP_FootstepComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"
NODE_CAST_GFX_SAVE = "Utilities|Casting|CastToBP_GraphicsSave"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_INSTANCED = "Utilities|Casting|CastToInstancedStaticMeshComponent"
NODE_CAST_ITEM = "Utilities|Casting|CastToBP_WeaponItem"
NODE_CAST_PAWN = "Utilities|Casting|CastToPawn"
NODE_CAST_PROFILE = "Utilities|Casting|CastToBP_Profile"
NODE_CAST_ROW = "Utilities|Casting|CastToWBP_MenuRow"
NODE_CAST_SETTINGS = "Utilities|Casting|CastToBP_Settings"
NODE_CAST_SLOT = "Utilities|Casting|CastToWBP_InventorySlot"
NODE_CAST_SURVIVAL = "Utilities|Casting|CastToBP_SurvivalComponent"
NODE_CAST_TUNE_SAVE = "Utilities|Casting|CastToBP_TuneSave"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"
NODE_MAKE_EVENT_DATA = "Utilities|Struct|MakeGameplayEventData"
