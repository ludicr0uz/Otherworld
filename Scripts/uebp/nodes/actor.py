"""uebp.nodes.actor -- member functions of engine classes: actors, components,
controllers, the HUD, anim instances.
"""

FN_ACTOR_FORWARD = "/Script/Engine.Actor.GetActorForwardVector"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_ACTOR_RIGHT = "/Script/Engine.Actor.GetActorRightVector"
FN_ACTOR_TICK_PAUSED = "/Script/Engine.Actor.SetTickableWhenPaused"
FN_ADD_LOCAL_ROT = "/Script/Engine.Actor.K2_AddActorLocalRotation"
FN_ADD_WORLD_ROT = "/Script/Engine.Actor.K2_AddActorWorldRotation"
FN_ATTACH = "/Script/Engine.Actor.K2_AttachToComponent"
FN_DESTROY = "/Script/Engine.Actor.K2_DestroyActor"
FN_DETACH = "/Script/Engine.Actor.K2_DetachFromActor"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_COMPONENTS = "/Script/Engine.Actor.K2_GetComponentsByClass"
FN_GET_TRANSFORM = "/Script/Engine.Actor.GetTransform"
FN_HAS_TAG = "/Script/Engine.Actor.ActorHasTag"
FN_LIFESPAN = "/Script/Engine.Actor.SetLifeSpan"
FN_ROOT = "/Script/Engine.Actor.K2_GetRootComponent"
FN_SET_ACTOR_LOC = "/Script/Engine.Actor.K2_SetActorLocation"
FN_SET_ACTOR_ROT = "/Script/Engine.Actor.K2_SetActorRotation"
FN_SET_HIDDEN = "/Script/Engine.Actor.SetActorHiddenInGame"
FN_SET_LOC_ROT = "/Script/Engine.Actor.K2_SetActorLocationAndRotation"
FN_SET_REL_LOC = "/Script/Engine.Actor.K2_SetActorRelativeLocation"
FN_SET_REL_ROT = "/Script/Engine.Actor.K2_SetActorRelativeRotation"
FN_SET_SCALE = "/Script/Engine.Actor.SetActorScale3D"
FN_VELOCITY = "/Script/Engine.Actor.GetVelocity"

FN_ADD_TICK_PREREQ = "/Script/Engine.ActorComponent.AddTickPrerequisiteComponent"
FN_COMP_TICK_PAUSED = "/Script/Engine.ActorComponent.SetTickableWhenPaused"
FN_GET_OWNER = "/Script/Engine.ActorComponent.GetOwner"

FN_IS_PLAYING_SLOT = "/Script/Engine.AnimInstance.IsPlayingSlotAnimation"
# "Is anything playing in this slot right now?" -- pure, one Name in, one bool
# out. It is what lets the ready pose notice that a hit reaction took the
# montage group off it, and put itself back the frame the flinch ends.
FN_IS_SLOT_ACTIVE = "/Script/Engine.AnimInstance.IsSlotActive"
FN_PLAY_SLOT = "/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage"
FN_STOP_SLOT = "/Script/Engine.AnimInstance.StopSlotAnimation"

FN_SET_FOV = "/Script/Engine.CameraComponent.SetFieldOfView"

FN_CAPSULE_HALF_HEIGHT = "/Script/Engine.CapsuleComponent.GetUnscaledCapsuleHalfHeight"

# Crouch and prone (weapon_component/stance.py). Crouch/UnCrouch only set the
# movement component's wish; it resizes the capsule on its own next tick.
FN_CROUCH = "/Script/Engine.Character.Crouch"
FN_UNCROUCH = "/Script/Engine.Character.UnCrouch"

FN_DISABLE_MOVEMENT = "/Script/Engine.CharacterMovementComponent.DisableMovement"
FN_SET_MOVEMENT_MODE = "/Script/Engine.CharacterMovementComponent.SetMovementMode"

# Recoil moves the view through the CONTROLLER's rotation, not through
# AddPitchInput: see COMBAT's recoil block for why routing it through
# RotationInput would make the kick scale with the sensitivity slider.
FN_GET_CONTROL_ROT = "/Script/Engine.Controller.GetControlRotation"
FN_GET_PAWN = "/Script/Engine.Controller.K2_GetPawn"
FN_IGNORE_LOOK = "/Script/Engine.Controller.SetIgnoreLookInput"
FN_IGNORE_MOVE = "/Script/Engine.Controller.SetIgnoreMoveInput"
FN_LINE_OF_SIGHT = "/Script/Engine.Controller.LineOfSightTo"
FN_SET_CONTROL_ROT = "/Script/Engine.Controller.SetControlRotation"
FN_STOP_MOVEMENT = "/Script/Engine.Controller.StopMovement"

FN_FOG_COLOR = "/Script/Engine.ExponentialHeightFogComponent.SetFogInscatteringColor"
FN_FOG_DENSITY = "/Script/Engine.ExponentialHeightFogComponent.SetFogDensity"

FN_DRAW_HUD_LINE = "/Script/Engine.HUD.DrawLine"
FN_DRAW_RECT = "/Script/Engine.HUD.DrawRect"
FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"
FN_DRAW_TEXTURE = "/Script/Engine.HUD.DrawTexture"
FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_PROJECT = "/Script/Engine.HUD.Project"

FN_GET_CULLS = "/Script/Engine.InstancedStaticMeshComponent.GetCullDistances"
# Pure (it is const): read the bool, branch, then read the transform.
FN_INSTANCE_TRANSFORM = "/Script/Engine.InstancedStaticMeshComponent.GetInstanceTransform"
FN_SET_CULLS = "/Script/Engine.InstancedStaticMeshComponent.SetCullDistances"

FN_LIGHT_INTENSITY = "/Script/Engine.LightComponent.SetIntensity"

FN_MID_SCALAR = "/Script/Engine.MaterialInstanceDynamic.SetScalarParameterValue"
FN_MID_VECTOR = "/Script/Engine.MaterialInstanceDynamic.SetVectorParameterValue"

FN_SET_OVERLAY = "/Script/Engine.MeshComponent.SetOverlayMaterial"

FN_IS_CROUCHING = "/Script/Engine.NavMovementComponent.IsCrouching"
# The ground test. UCharacterMovementComponent's own IsMovingOnGround is not
# BlueprintCallable, but UNavMovementComponent's -- the same virtual, one class
# up -- is. It replaced Character::CanJump, which was a proxy for "feet on the
# ground" until crouching arrived: CanJump is false while crouched, and every
# crouched or prone step would have been silent. The self pin is the movement
# component, not the character.
FN_ON_GROUND = "/Script/Engine.NavMovementComponent.IsMovingOnGround"

FN_GET_CONTROLLER = "/Script/Engine.Pawn.GetController"
FN_IS_PLAYER_CONTROLLED = "/Script/Engine.Pawn.IsPlayerControlled"
# The way the player steered this frame, as the movement component consumed it:
# the intent, not the velocity, which lags it and outlives it.
FN_LAST_MOVE_INPUT = "/Script/Engine.Pawn.GetLastMovementInputVector"
# What the pawn stands on: the terrain, which the sweep for a tree ignores.
FN_MOVEMENT_BASE = "/Script/Engine.Pawn.GetMovementBaseActor"

FN_CAM_LOC = "/Script/Engine.PlayerCameraManager.GetCameraLocation"
FN_CAM_ROT = "/Script/Engine.PlayerCameraManager.GetCameraRotation"

FN_GET_PITCH_SCALE = "/Script/Engine.PlayerController.GetDeprecatedInputPitchScale"
FN_GET_YAW_SCALE = "/Script/Engine.PlayerController.GetDeprecatedInputYawScale"
# Held, not tapped: sprint is a state for as long as the key is down, so it is
# the one polled key in this file that cannot use WasInputKeyJustPressed.
FN_IS_KEY_DOWN = "/Script/Engine.PlayerController.IsInputKeyDown"
FN_RELEASED = "/Script/Engine.PlayerController.WasInputKeyJustReleased"
FN_SET_LISTENER_ATTENUATION = "/Script/Engine.PlayerController.SetAudioListenerAttenuationOverride"
FN_SET_PITCH_SCALE = "/Script/Engine.PlayerController.SetDeprecatedInputPitchScale"
FN_SET_YAW_SCALE = "/Script/Engine.PlayerController.SetDeprecatedInputYawScale"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"

FN_CREATE_MID = "/Script/Engine.PrimitiveComponent.CreateDynamicMaterialInstance"
FN_SET_COLLISION = "/Script/Engine.PrimitiveComponent.SetCollisionEnabled"
FN_SET_MAX_DRAW = "/Script/Engine.PrimitiveComponent.SetCullDistance"
FN_SET_OWNER_NO_SEE = "/Script/Engine.PrimitiveComponent.SetOwnerNoSee"
FN_SET_PROFILE = "/Script/Engine.PrimitiveComponent.SetCollisionProfileName"
FN_TRACE_COMPONENT = "/Script/Engine.PrimitiveComponent.K2_LineTraceComponent"

FN_COMP_LOC = "/Script/Engine.SceneComponent.K2_GetComponentLocation"
# Component-space, not the Actor.* pair above it: the droplets move relative to
# the burst, and the actor itself never moves after the frame it spawns.
FN_COMP_REL_XFORM = "/Script/Engine.SceneComponent.GetRelativeTransform"
FN_COMP_SET_REL_LOC = "/Script/Engine.SceneComponent.K2_SetRelativeLocation"
FN_COMP_SET_SCALE = "/Script/Engine.SceneComponent.SetRelativeScale3D"
FN_COMP_SET_WORLD_LOC = "/Script/Engine.SceneComponent.K2_SetWorldLocation"
FN_COMP_SET_WORLD_ROT = "/Script/Engine.SceneComponent.K2_SetWorldRotation"
FN_FORWARD_OF = "/Script/Engine.SceneComponent.GetForwardVector"
FN_SET_VISIBILITY = "/Script/Engine.SceneComponent.SetVisibility"
FN_SOCKET_LOC = "/Script/Engine.SceneComponent.GetSocketLocation"
# The sight camera's rotation (weapon_component/sights.py): from the boom's
# to the look down the held weapon's sight line.
FN_SOCKET_ROT = "/Script/Engine.SceneComponent.GetSocketRotation"

FN_ANIM_INSTANCE = "/Script/Engine.SkeletalMeshComponent.GetAnimInstance"
# Every body in the physics asset, not the component's one root body --
# see RAGDOLL_PROFILE. SkeletalMeshComponent has no SetSimulatePhysics
# UFunction at all, so there is no node to reach for by mistake.
FN_SIMULATE_ALL = "/Script/Engine.SkeletalMeshComponent.SetAllBodiesSimulatePhysics"

FN_CLOSEST_BONE = "/Script/Engine.SkinnedMeshComponent.FindClosestBone_K2"
FN_HIDE_BONE = "/Script/Engine.SkinnedMeshComponent.HideBoneByName"
FN_UNHIDE_BONE = "/Script/Engine.SkinnedMeshComponent.UnHideBoneByName"

FN_SKY_INTENSITY = "/Script/Engine.SkyLightComponent.SetIntensity"

FN_SET_WPO = "/Script/Engine.StaticMeshComponent.SetEvaluateWorldPositionOffset"
FN_SET_WPO_DISTANCE = "/Script/Engine.StaticMeshComponent.SetWorldPositionOffsetDisableDistance"
