"""uebp.nodes.locomotion -- what the player's motion-matching anim blueprint
reads its character through (combat/gas_locomotion.py): the movement
component's state, and the Game Animation Sample's own structs and enums.
"""

# The anim instance's pawn: None in an editor preview.
FN_TRY_GET_PAWN_OWNER = "/Script/Engine.AnimInstance.TryGetPawnOwner"
FN_ACTOR_ROT = "/Script/Engine.Actor.K2_GetActorRotation"

# The character's movement component.
FN_CURRENT_ACCELERATION = "/Script/Engine.CharacterMovementComponent.GetCurrentAcceleration"
FN_MAX_ACCELERATION = "/Script/Engine.CharacterMovementComponent.GetMaxAcceleration"
FN_MAX_SPEED = "/Script/Engine.MovementComponent.GetMaxSpeed"
FN_IS_FALLING = "/Script/Engine.NavMovementComponent.IsFalling"

# A number chosen by a bool, and that number as the byte an enum is made of.
FN_SELECT_INT = "/Script/Engine.KismetMathLibrary.SelectInt"
FN_INT_TO_BYTE = "/Script/Engine.KismetMathLibrary.Conv_IntToByte"

NODE_BREAK_FLOOR = "Utilities|Struct|BreakFindFloorResult"
NODE_EVENT_INIT_ANIM = "AddEvent|EventBlueprintInitializeAnimation"
NODE_EVENT_UPDATE_ANIM = "AddEvent|EventBlueprintUpdateAnimation"

# The sample's own (/Game/GAS/Blueprints/Data): in the palette while loaded.
NODE_MAKE_CHARACTER_PROPERTIES = "Utilities|Struct|MakeSCharacterPropertiesforAnimation"
NODE_MAKE_INPUT_STATE = "Utilities|Struct|MakeSPlayerInputState"
# A byte as one of the sample's enums: an enum pin takes no variable, and a
# graph that must choose a value at run time chooses a number and casts it.
NODE_BYTE_TO_GAIT = "Utilities|Enum|BytetoEnumE_Gait"
NODE_BYTE_TO_MOVEMENT_MODE = "Utilities|Enum|BytetoEnumE_MovementMode"
NODE_BYTE_TO_ROTATION_MODE = "Utilities|Enum|BytetoEnumE_RotationMode"
