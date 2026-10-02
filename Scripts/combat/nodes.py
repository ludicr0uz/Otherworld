"""Function paths (FN_*), palette node names (NODE_*) and macros used when
authoring graphs. Constants only.
"""



# ─── Graph node paths ────────────────────────────────────────────────────────

FN_GET_OWNER = "/Script/Engine.ActorComponent.GetOwner"
FN_GET_PC = "/Script/Engine.GameplayStatics.GetPlayerController"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
# Held, not tapped: sprint is a state for as long as the key is down, so it is
# the one polled key in this file that cannot use WasInputKeyJustPressed.
FN_IS_KEY_DOWN = "/Script/Engine.PlayerController.IsInputKeyDown"
FN_GET_CAM = "/Script/Engine.GameplayStatics.GetPlayerCameraManager"
FN_CAM_LOC = "/Script/Engine.PlayerCameraManager.GetCameraLocation"
FN_CAM_ROT = "/Script/Engine.PlayerCameraManager.GetCameraRotation"
FN_FORWARD = "/Script/Engine.KismetMathLibrary.GetForwardVector"
FN_RAND_CONE = "/Script/Engine.KismetMathLibrary.RandomUnitVectorInConeInRadians"
FN_TRACE = "/Script/Engine.KismetSystemLibrary.LineTraceSingle"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
# A class reference is a different pin category from an object reference, so
# IsValid refuses to connect to one; IsValidClass is the class-pin twin.
FN_IS_VALID_CLASS = "/Script/Engine.KismetSystemLibrary.IsValidClass"
FN_TRANSFORM_LOC = "/Script/Engine.KismetMathLibrary.TransformLocation"
FN_GET_TRANSFORM = "/Script/Engine.Actor.GetTransform"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_MAKE_TRANSFORM = "/Script/Engine.KismetMathLibrary.MakeTransform"
FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
FN_BREAK_VECTOR = "/Script/Engine.KismetMathLibrary.BreakVector"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_PRINT = "/Script/Engine.KismetSystemLibrary.PrintString"
FN_WARN = "/Script/Engine.KismetSystemLibrary.PrintWarning"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_VEC_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_VectorToString"
FN_NORMAL = "/Script/Engine.KismetMathLibrary.Normal"
FN_DEG2RAD = "/Script/Engine.KismetMathLibrary.DegreesToRadians"
FN_PLAY_SOUND = "/Script/Engine.GameplayStatics.PlaySoundAtLocation"
FN_OBJECT_CLASS = "/Script/Engine.GameplayStatics.GetObjectClass"
FN_ATTACH = "/Script/Engine.Actor.K2_AttachToComponent"
FN_DETACH = "/Script/Engine.Actor.K2_DetachFromActor"
FN_SET_HIDDEN = "/Script/Engine.Actor.SetActorHiddenInGame"
FN_SET_OWNER_NO_SEE = "/Script/Engine.PrimitiveComponent.SetOwnerNoSee"
FN_HIDE_BONE = "/Script/Engine.SkinnedMeshComponent.HideBoneByName"
FN_UNHIDE_BONE = "/Script/Engine.SkinnedMeshComponent.UnHideBoneByName"
FN_SET_ACTOR_LOC = "/Script/Engine.Actor.K2_SetActorLocation"
FN_SET_REL_LOC = "/Script/Engine.Actor.K2_SetActorRelativeLocation"
FN_SET_REL_ROT = "/Script/Engine.Actor.K2_SetActorRelativeRotation"
FN_SET_SCALE = "/Script/Engine.Actor.SetActorScale3D"
FN_DESTROY = "/Script/Engine.Actor.K2_DestroyActor"
FN_LIFESPAN = "/Script/Engine.Actor.SetLifeSpan"
FN_ALL_ACTORS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"
FN_ANIM_INSTANCE = "/Script/Engine.SkeletalMeshComponent.GetAnimInstance"
FN_PLAY_SLOT = "/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage"
FN_STOP_SLOT = "/Script/Engine.AnimInstance.StopSlotAnimation"
FN_RANDOM_NAV = ("/Script/NavigationSystem.NavigationSystemV1"
                 ".K2_GetRandomLocationInNavigableRadius")
FN_PROJECT_NAV = ("/Script/NavigationSystem.NavigationSystemV1"
                  ".K2_ProjectPointToNavigation")

FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_ARR_REMOVE = "/Script/Engine.KismetArrayLibrary.Array_Remove"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"

FN_ADD_VV = "/Script/Engine.KismetMathLibrary.Add_VectorVector"
FN_SUB_VV = "/Script/Engine.KismetMathLibrary.Subtract_VectorVector"
FN_MUL_VF = "/Script/Engine.KismetMathLibrary.Multiply_VectorFloat"
FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_MOD_II = "/Script/Engine.KismetMathLibrary.Percent_IntInt"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_LESS_II = "/Script/Engine.KismetMathLibrary.Less_IntInt"
FN_GREATER_II = "/Script/Engine.KismetMathLibrary.Greater_IntInt"
FN_MIN_II = "/Script/Engine.KismetMathLibrary.Min"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_ADD_FF = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_SUB_FF = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_LE_FF = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_LESS_FF = "/Script/Engine.KismetMathLibrary.Less_DoubleDouble"
FN_GREATER_FF = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_GE_FF = "/Script/Engine.KismetMathLibrary.GreaterEqual_DoubleDouble"
# The ground test. UCharacterMovementComponent's own IsMovingOnGround is not
# BlueprintCallable, but UNavMovementComponent's -- the same virtual, one class
# up -- is. It replaced Character::CanJump, which was a proxy for "feet on the
# ground" until crouching arrived: CanJump is false while crouched, and every
# crouched or prone step would have been silent. The self pin is the movement
# component, not the character.
FN_ON_GROUND = "/Script/Engine.NavMovementComponent.IsMovingOnGround"
FN_GET_VELOCITY = "/Script/Engine.Actor.GetVelocity"
FN_VSIZE_XY = "/Script/Engine.KismetMathLibrary.VSizeXY"
FN_CLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_DISTANCE = "/Script/Engine.KismetMathLibrary.Vector_Distance"
FN_RANDOM_FLOAT = "/Script/Engine.KismetMathLibrary.RandomFloatInRange"
FN_RAND_INT = "/Script/Engine.KismetMathLibrary.RandomIntegerInRange"
# FRandomStream draws. Pure, and they advance the stream they read (its Seed is
# mutable), so each must be pulled by exactly one exec consumer. The seeders
# take the stream by reference and write the variable they are wired to.
FN_STREAM_FLOAT = "/Script/Engine.KismetMathLibrary.RandomFloatFromStream"
FN_STREAM_INT = "/Script/Engine.KismetMathLibrary.RandomIntegerFromStream"
FN_SEED_STREAM = "/Script/Engine.KismetMathLibrary.SeedRandomStream"
FN_SET_STREAM_SEED = "/Script/Engine.KismetMathLibrary.SetRandomStreamSeed"
FN_NEQ_BB = "/Script/Engine.KismetMathLibrary.NotEqual_BoolBool"
FN_MAKE_ROT = "/Script/Engine.KismetMathLibrary.MakeRotator"
FN_MUL_FF = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_SELECT_FF = "/Script/Engine.KismetMathLibrary.SelectFloat"
FN_DIV_FF = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_INTERP_FF = "/Script/Engine.KismetMathLibrary.FInterpTo"
FN_NOT_B = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_SET_FOV = "/Script/Engine.CameraComponent.SetFieldOfView"
FN_GET_YAW_SCALE = "/Script/Engine.PlayerController.GetDeprecatedInputYawScale"
FN_GET_PITCH_SCALE = "/Script/Engine.PlayerController.GetDeprecatedInputPitchScale"
FN_SET_YAW_SCALE = "/Script/Engine.PlayerController.SetDeprecatedInputYawScale"
FN_SET_PITCH_SCALE = "/Script/Engine.PlayerController.SetDeprecatedInputPitchScale"
FN_LERP = "/Script/Engine.KismetMathLibrary.Lerp"
# Recoil moves the view through the CONTROLLER's rotation, not through
# AddPitchInput: see COMBAT's recoil block for why routing it through
# RotationInput would make the kick scale with the sensitivity slider.
FN_GET_CONTROL_ROT = "/Script/Engine.Controller.GetControlRotation"
FN_SET_CONTROL_ROT = "/Script/Engine.Controller.SetControlRotation"
FN_BREAK_ROT = "/Script/Engine.KismetMathLibrary.BreakRotator"
# The control rotation keeps pitch in 0..360; this makes looking down negative.
FN_NORMALIZE_AXIS = "/Script/Engine.KismetMathLibrary.NormalizeAxis"
FN_ABS = "/Script/Engine.KismetMathLibrary.Abs"
# "Is anything playing in this slot right now?" -- pure, one Name in, one bool
# out. It is what lets the ready pose notice that a hit reaction took the
# montage group off it, and put itself back the frame the flinch ends.
FN_IS_SLOT_ACTIVE = "/Script/Engine.AnimInstance.IsSlotActive"
# The hit-direction pick. Dot_VectorVector against the owner's own forward and
# right is what turns "where the round came from" into one of four clips
# without a single angle or a single trigonometric function.
FN_DOT_VV = "/Script/Engine.KismetMathLibrary.Dot_VectorVector"
FN_ACTOR_RIGHT = "/Script/Engine.Actor.GetActorRightVector"
# Integer clamp, not FClamp: the reaction index is an array index, and an array
# shorter than HIT_REACTION_CLIPS (a checkout whose retarget has not run) must
# clip to the last entry rather than read off the end.
FN_CLAMP_II = "/Script/Engine.KismetMathLibrary.Clamp"
# Crouch and prone (weapon_component/stance.py). Crouch/UnCrouch only set the
# movement component's wish; it resizes the capsule on its own next tick.
FN_CROUCH = "/Script/Engine.Character.Crouch"
FN_UNCROUCH = "/Script/Engine.Character.UnCrouch"
FN_IS_CROUCHING = "/Script/Engine.NavMovementComponent.IsCrouching"
FN_CAPSULE_HALF_HEIGHT = "/Script/Engine.CapsuleComponent.GetUnscaledCapsuleHalfHeight"
FN_SELECT_II = "/Script/Engine.KismetMathLibrary.SelectInt"
CAMERA_CLASS_PATH = "/Script/Engine.CameraComponent"
MOVEMENT_CLASS_PATH = "/Script/Engine.CharacterMovementComponent"
# Aiming down the sights (weapon_component/sights.py): the camera leaves the
# boom's end for the weapon's eye point. USpringArmComponent names its one
# socket SpringEndpoint; the camera hangs off it with no offset of its own.
SPRING_ARM_CLASS_PATH = "/Script/Engine.SpringArmComponent"
SPRING_ARM_SOCKET = "SpringEndpoint"
FN_SOCKET_LOC = "/Script/Engine.SceneComponent.GetSocketLocation"
FN_COMP_SET_WORLD_LOC = "/Script/Engine.SceneComponent.K2_SetWorldLocation"
FN_VLERP = "/Script/Engine.KismetMathLibrary.VLerp"
# The sight camera's rotation (weapon_component/sights.py): from the boom's
# to the look down the held weapon's sight line.
FN_SOCKET_ROT = "/Script/Engine.SceneComponent.GetSocketRotation"
FN_COMP_SET_WORLD_ROT = "/Script/Engine.SceneComponent.K2_SetWorldRotation"
FN_RLERP = "/Script/Engine.KismetMathLibrary.RLerp"
FN_VSIZE = "/Script/Engine.KismetMathLibrary.VSize"
FN_BOOL_TO_FLOAT = "/Script/Engine.KismetMathLibrary.Conv_BoolToDouble"
FN_ADD_TICK_PREREQ = "/Script/Engine.ActorComponent.AddTickPrerequisiteComponent"
FN_SET_LISTENER_ATTENUATION = (
    "/Script/Engine.PlayerController.SetAudioListenerAttenuationOverride")
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
# The reticle's size (weapon_component/accuracy.py): the cloud's angle as a
# fraction of the half-width the field of view spans.
FN_DEG_TAN = "/Script/Engine.KismetMathLibrary.DegTan"
# The noise record (combat/noise.py): the louder of two reaches, and whether a
# footstep belongs to the player rather than to one of the wanderers who share
# the footstep component.
FN_MAX_FF = "/Script/Engine.KismetMathLibrary.FMax"
FN_IS_PLAYER_CONTROLLED = "/Script/Engine.Pawn.IsPlayerControlled"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"
FN_DISABLE_MOVEMENT = "/Script/Engine.CharacterMovementComponent.DisableMovement"
FN_SET_COLLISION = "/Script/Engine.PrimitiveComponent.SetCollisionEnabled"
FN_GET_CONTROLLER = "/Script/Engine.Pawn.GetController"
FN_SET_PROFILE = "/Script/Engine.PrimitiveComponent.SetCollisionProfileName"
# Every body in the physics asset, not the component's one root body --
# see RAGDOLL_PROFILE. SkeletalMeshComponent has no SetSimulatePhysics
# UFunction at all, so there is no node to reach for by mistake.
FN_SIMULATE_ALL = ("/Script/Engine.SkeletalMeshComponent"
                   ".SetAllBodiesSimulatePhysics")
FN_SIN = "/Script/Engine.KismetMathLibrary.Sin"
FN_ROT_FROM_X = "/Script/Engine.KismetMathLibrary.MakeRotFromX"
FN_EXP = "/Script/Engine.KismetMathLibrary.Exp"
FN_INV_XFORM_DIR = "/Script/Engine.KismetMathLibrary.InverseTransformDirection"
FN_BREAK_TRANSFORM = "/Script/Engine.KismetMathLibrary.BreakTransform"
FN_GET_COMPONENTS = "/Script/Engine.Actor.K2_GetComponentsByClass"
# Component-space, not the Actor.* pair above it: the droplets move relative to
# the burst, and the actor itself never moves after the frame it spawns.
FN_COMP_REL_XFORM = "/Script/Engine.SceneComponent.GetRelativeTransform"
FN_COMP_SET_REL_LOC = "/Script/Engine.SceneComponent.K2_SetRelativeLocation"
FN_COMP_SET_SCALE = "/Script/Engine.SceneComponent.SetRelativeScale3D"
FN_SET_ACTOR_ROT = "/Script/Engine.Actor.K2_SetActorRotation"
FN_ACTOR_FORWARD = "/Script/Engine.Actor.GetActorForwardVector"
# The way the player steered this frame, as the movement component consumed it:
# the intent, not the velocity, which lags it and outlives it.
FN_LAST_MOVE_INPUT = "/Script/Engine.Pawn.GetLastMovementInputVector"
FN_DRAW_LINE = "/Script/Engine.KismetSystemLibrary.DrawDebugLine"
FN_DRAW_POINT = "/Script/Engine.KismetSystemLibrary.DrawDebugPoint"
FN_SELECT_VECTOR = "/Script/Engine.KismetMathLibrary.SelectVector"
FN_SELECT_COLOR = "/Script/Engine.KismetMathLibrary.SelectColor"
FN_ADD_LOCAL_ROT = "/Script/Engine.Actor.K2_AddActorLocalRotation"
FN_DRAW_STRING = "/Script/Engine.KismetSystemLibrary.DrawDebugString"
FN_FLOAT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_DoubleToString"
# Only the temporary hit-reaction probe uses this; see HIT_REACT_PROBE.
FN_DISPLAY_NAME = "/Script/Engine.KismetSystemLibrary.GetDisplayName"
FN_TRACE_COMPONENT = "/Script/Engine.PrimitiveComponent.K2_LineTraceComponent"
FN_ARR_CONTAINS = "/Script/Engine.KismetArrayLibrary.Array_Contains"

# The Gameplay Ability System (plugin GameplayAbilities). The C++ class is
# AbilitySystemBlueprintLibrary even though Python calls it AbilitySystemLibrary.
GAS = "/Script/GameplayAbilities"
FN_GET_ASC = f"{GAS}.AbilitySystemBlueprintLibrary.GetAbilitySystemComponent"
FN_SEND_GAMEPLAY_EVENT = f"{GAS}.AbilitySystemBlueprintLibrary.SendGameplayEventToActor"
FN_ADD_GRANTED_TAG = f"{GAS}.AbilitySystemBlueprintLibrary.AddGrantedTag"
FN_TAG_COUNT = f"{GAS}.AbilitySystemComponent.GetGameplayTagCount"
FN_EFFECT_COUNT = f"{GAS}.AbilitySystemComponent.GetGameplayEffectCount"
FN_GIVE_ABILITY = f"{GAS}.AbilitySystemComponent.K2_GiveAbility"
FN_MAKE_SPEC = f"{GAS}.AbilitySystemComponent.MakeOutgoingSpec"
FN_MAKE_CONTEXT = f"{GAS}.AbilitySystemComponent.MakeEffectContext"
FN_APPLY_SPEC_TO_SELF = f"{GAS}.AbilitySystemComponent.BP_ApplyGameplayEffectSpecToSelf"
FN_REMOVE_EFFECT = f"{GAS}.AbilitySystemComponent.RemoveActiveGameplayEffectBySourceEffect"
FN_END_ABILITY = f"{GAS}.GameplayAbility.K2_EndAbility"
FN_AVATAR = f"{GAS}.GameplayAbility.GetAvatarActorFromActorInfo"
NODE_MAKE_EVENT_DATA = "Utilities|Struct|MakeGameplayEventData"
NODE_BREAK_EVENT_DATA = "Utilities|Struct|BreakGameplayEventData"
NODE_ABILITY_FROM_EVENT = "AddEvent|Ability|EventActivateAbilityFromEvent"

NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
NODE_BREAK_HIT = "Collision|BreakHitResult"
NODE_SPAWN = "Game|SpawnActorfromClass"
NODE_CAST_CHAR = "Utilities|Casting|CastToBP_ThirdPersonCharacter"
NODE_CAST_CHARACTER = "Utilities|Casting|CastToCharacter"
NODE_CAST_PAWN = "Utilities|Casting|CastToPawn"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"
NODE_CAST_ITEM = "Utilities|Casting|CastToBP_WeaponItem"
MACRO_FOR_LOOP = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForLoop"
MACRO_FOR_EACH = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop"

INF = 1.0e9
