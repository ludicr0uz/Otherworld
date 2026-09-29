"""The over-the-shoulder camera: boom length and offset, the aim-trace
range, and the two character patches (face the camera, aim the camera).
"""

import unreal

from combat.graph import BEL, _component_object, _handles, _log


# --- the shooting camera -----------------------------------------------------
# A centred third-person camera puts the character's own back where the reticle
# is, so the crosshair sits on the thing you are least interested in shooting.
# The standard fix is to move the boom over the shoulder: shorter, right, and
# up, which frames the player in the lower-left and leaves the centre of the
# screen clear. The boom shortens as well as offsets -- pushing a 400 cm arm
# sideways swings the camera wide enough that the player's own shoulder crosses
# the centre again when they turn.
CAMERA_ARM = 260.0                  # cm, was 400
CAMERA_SHOULDER = (0.0, 55.0, 60.0) # right and up, in the boom's own space

# How far the camera's aiming ray reaches when it finds nothing: the "point
# arbitrarily far away" the shot is then aimed at. 1 km is past anything in a
# 200 m level, so the ray effectively never runs out before the world does.
AIM_TRACE_RANGE = 100000.0

# The reticle turns red when the muzzle's own line to the aim point stops this
# much short of it -- i.e. something is in front of the barrel that the camera
# cannot see past the player's shoulder. Slack, not zero: the muzzle and the
# camera converge on the same surface from different angles, so their hits are
# never at exactly the same millimetre.
BLOCKED_SLACK = 75.0


def face_the_camera(bp):
    """Turn the body with the camera instead of with the movement input.

    This is what aims the gun, and it is the standard arrangement for a
    third-person shooter: the character always faces where the camera looks and
    strafes around that, so the ready pose -- and therefore the barrel -- stays
    lined up with the crosshair no matter which way the player is running.

    The template ships the opposite (`orient_rotation_to_movement`), which turns
    the whole body to face the movement input. With a weapon in hand that means
    running left points the gun left while the crosshair stays dead ahead.

    The honest cost: the legs still play the *unarmed* forward gait, because a
    strafe set needs blend spaces and those cannot be authored from Python, so
    sideways movement reads as running forward while sliding. That is the same
    limitation the ready pose already documents, not a new one.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    cdo.set_editor_property("use_controller_rotation_yaw", True)
    movement = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.CharacterMovementComponent):
            movement = obj
            break
    if movement is None:
        raise RuntimeError(f"{bp.get_name()} has no CharacterMovementComponent")
    movement.set_editor_property("orient_rotation_to_movement", False)
    if movement.get_editor_property("orient_rotation_to_movement"):
        raise RuntimeError("the character still turns to face its movement — "
                           "the body would fight the camera for where to aim")
    _log("player: body follows the camera's yaw (gun stays on the crosshair)")


def aim_camera(bp):
    """Move the camera boom over the player's right shoulder.

    Belongs with the weapons rather than with the level or the HUD: it exists
    because there is now a reticle in the middle of the screen, and a centred
    boom points that reticle straight at the player's own back.
    """
    arm = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SpringArmComponent):
            arm = obj
            break
    if arm is None:
        _log(f"note: {bp.get_name()} has no SpringArmComponent — camera left alone")
        return
    arm.set_editor_property("target_arm_length", CAMERA_ARM)
    arm.set_editor_property("socket_offset", unreal.Vector(*CAMERA_SHOULDER))
    got = arm.get_editor_property("socket_offset")
    if abs(got.y - CAMERA_SHOULDER[1]) > 1e-3:
        raise RuntimeError(f"the camera boom kept its old offset ({got})")
    # Aiming down the sights puts the camera back at the boom's socket when it
    # lets go (weapon_component/sights.py), which is only "where it was" if
    # the camera sits on that socket with no offset of its own.
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.CameraComponent):
            off = obj.get_editor_property("relative_location")
            if max(abs(off.x), abs(off.y), abs(off.z)) > 1e-3:
                raise RuntimeError(f"the camera is offset from the boom's end "
                                   f"({off}); the sights would not return it there")
    _log(f"camera: boom {CAMERA_ARM:.0f} cm, over the shoulder by "
         f"{CAMERA_SHOULDER[1]:.0f} cm right / {CAMERA_SHOULDER[2]:.0f} cm up")
