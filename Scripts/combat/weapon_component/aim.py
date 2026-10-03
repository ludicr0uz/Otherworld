"""Aim: resolving the aim point every frame (camera trace, then muzzle trace).

The two ways of aiming -- the zoom they share, the look and walk slowdowns --
are ads.py; where the camera sits while aiming down the sights is sights.py.
"""

from combat.camera import AIM_TRACE_RANGE, BLOCKED_SLACK
from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from combat.nodes import (
    FN_ADD_VV, FN_CAM_LOC, FN_CAM_ROT, FN_DISTANCE, FN_FORWARD, FN_GET_CAM,
    FN_GREATER_FF, FN_IS_VALID, FN_MUL_VF, FN_TRACE, NODE_BREAK_HIT,
)
from combat.weapon_component.carry import _author_shot_origin
from combat.weapon_component.common import _trace_defaults


def _author_resolve_aim(ed, held, exec_ins):
    """Work out where this frame's shot lands. The hybrid of the two obvious wrongs.

    Aiming purely from the muzzle is honest and unplayable: the barrel sits below
    and to the side of the camera, so the shot lands a little off wherever the
    crosshair is, and a player standing beside a wall shoots the wall while their
    crosshair is on an enemy in the open. Aiming purely from the camera is
    playable and looks broken: the camera is on a boom behind the shoulder, so
    the pellets visibly fan out from behind the player -- which is exactly what
    was reported here.

    So: the camera decides *what* is being aimed at, and the muzzle decides
    whether the gun can actually reach it.

      1. Trace from the camera along its forward vector. Whatever it hits is the
         aim point; if it hits nothing, the aim point is a point a kilometre out,
         which is the standard stand-in for "the sky".
      2. Trace from the muzzle to that aim point. If something stops that second
         line well short, *that* is where the shot lands -- the wall in front of
         the barrel -- and AimBlocked says so, which is what turns the reticle
         red.

    Step 2 is not a separate safety check bolted on: it is the same line the
    pellets themselves fly down, so the reticle cannot promise a hit the shot
    will not make. The pellet loop then only has to spread a cone around
    (AimPoint - muzzle).

    Runs before the fire gate and unconditionally, because the reticle has to be
    right on frames where the trigger is not pulled -- which is most of them.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cam = keep(_node(ed, FN_GET_CAM))
    _set(cam, "PlayerIndex", 0)
    cam_out = _pin(cam, "ReturnValue", is_input=False)
    cam_loc = keep(_node(ed, FN_CAM_LOC))
    _connect(cam_out, _pin(cam_loc, "self"))
    cam_loc_out = _pin(cam_loc, "ReturnValue", is_input=False)
    cam_rot = keep(_node(ed, FN_CAM_ROT))
    _connect(cam_out, _pin(cam_rot, "self"))
    fwd = keep(_node(ed, FN_FORWARD))
    _connect(_pin(cam_rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))
    reach = keep(_node(ed, FN_MUL_VF))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(reach, "A"))
    # The length goes in as a *vector* literal, not a float one. UE 5 promotes
    # Multiply_VectorFloat to a wildcard operator, and with nothing connected
    # its B pin is a vector -- which is a struct pin, which rejects every
    # literal format there is. Multiplying component-wise by (R, R, R) is the
    # same arithmetic and actually survives the save.
    _connect(_vec(ed, AIM_TRACE_RANGE, AIM_TRACE_RANGE, AIM_TRACE_RANGE), _pin(reach, "B"))
    sky = keep(_node(ed, FN_ADD_VV))
    _connect(cam_loc_out, _pin(sky, "A"))
    _connect(_pin(reach, "ReturnValue", is_input=False), _pin(sky, "B"))
    sky_out = _pin(sky, "ReturnValue", is_input=False)

    look = keep(_node(ed, FN_TRACE))
    _connect(cam_loc_out, _pin(look, "Start"))
    _connect(sky_out, _pin(look, "End"))
    # Never drawn: this line runs from the camera through the player's own head
    # every frame, so drawing it would fill the screen. Only the pellets are
    # drawn, and only when they are actually fired.
    _trace_defaults(look)
    for e in exec_ins:
        _connect(e, _pin(look, "execute"))

    look_brk = keep(_palette(ed, NODE_BREAK_HIT))
    _connect(_pin(look, "OutHit", is_input=False), _loose_pin(look_brk, "Hit"))
    saw = keep(ed.add_branch_node())
    _connect(_pin(look, "ReturnValue", is_input=False), _pin(saw, "Condition"))
    _connect(BEL.find_then_pin(look), _pin(saw, "execute"))

    on_surface = keep(ed.add_set_member_variable_node("AimPoint"))
    _connect(_loose_pin(look_brk, "Location", is_input=False), _pin(on_surface, "AimPoint"))
    _connect(BEL.find_then_pin(saw), _pin(on_surface, "execute"))
    at_sky = keep(ed.add_set_member_variable_node("AimPoint"))
    _connect(sky_out, _pin(at_sky, "AimPoint"))
    _connect(BEL.find_else_pin(saw), _pin(at_sky, "execute"))

    armed = keep(_node(ed, FN_IS_VALID))
    _connect(held, _pin(armed, "Object"))
    holding = keep(ed.add_branch_node())
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(holding, "Condition"))
    _connect(BEL.find_then_pin(on_surface), _pin(holding, "execute"))
    _connect(BEL.find_then_pin(at_sky), _pin(holding, "execute"))

    # Empty-handed: there is nothing to draw a reticle for, and no muzzle to
    # trace from -- reading one off a null weapon is how Accessed None happens.
    unarmed = keep(ed.add_set_member_variable_node("AimValid"))
    _set(unarmed, "AimValid", "false")
    _connect(BEL.find_else_pin(holding), _pin(unarmed, "execute"))

    aim_get = keep(ed.add_get_member_variable_node("AimPoint"))
    aim_out = _pin(aim_get, "AimPoint", is_input=False)

    # The muzzle, or while the gun is lowered where it is about to be (carry.py).
    muzzle = _author_shot_origin(ed, held)

    clear = keep(_node(ed, FN_TRACE))
    _connect(muzzle, _pin(clear, "Start"))
    _connect(aim_out, _pin(clear, "End"))
    _trace_defaults(clear)
    _connect(BEL.find_then_pin(holding), _pin(clear, "execute"))

    clear_brk = keep(_palette(ed, NODE_BREAK_HIT))
    _connect(_pin(clear, "OutHit", is_input=False), _loose_pin(clear_brk, "Hit"))
    stopped = keep(ed.add_branch_node())
    _connect(_pin(clear, "ReturnValue", is_input=False), _pin(stopped, "Condition"))
    _connect(BEL.find_then_pin(clear), _pin(stopped, "execute"))

    short_by = keep(_node(ed, FN_DISTANCE))
    _connect(_loose_pin(clear_brk, "Location", is_input=False), _pin(short_by, "V1"))
    _connect(aim_out, _pin(short_by, "V2"))
    far_short = keep(_node(ed, FN_GREATER_FF))
    _connect(_pin(short_by, "ReturnValue", is_input=False), _pin(far_short, "A"))
    _set(far_short, "B", BLOCKED_SLACK)

    mark = keep(ed.add_set_member_variable_node("AimBlocked"))
    _connect(_pin(far_short, "ReturnValue", is_input=False), _pin(mark, "AimBlocked"))
    _connect(BEL.find_then_pin(stopped), _pin(mark, "execute"))
    # The aim point moves to where the barrel's own line actually ends, so the
    # reticle sits on the near wall rather than on the enemy behind it.
    reality = keep(ed.add_set_member_variable_node("AimPoint"))
    _connect(_loose_pin(clear_brk, "Location", is_input=False), _pin(reality, "AimPoint"))
    _connect(BEL.find_then_pin(mark), _pin(reality, "execute"))

    open_shot = keep(ed.add_set_member_variable_node("AimBlocked"))
    _set(open_shot, "AimBlocked", "false")
    _connect(BEL.find_else_pin(stopped), _pin(open_shot, "execute"))

    ready = keep(ed.add_set_member_variable_node("AimValid"))
    _set(ready, "AimValid", "true")
    _connect(BEL.find_then_pin(reality), _pin(ready, "execute"))
    _connect(BEL.find_then_pin(open_shot), _pin(ready, "execute"))

    ed.add_comment_to_nodes(
        "Resolve aim: the camera picks the target, the muzzle decides whether "
        "the gun can reach it. AimPoint ends up at the first surface on the "
        "line the pellets will actually fly down, which is what makes the "
        "reticle honest -- including when the barrel is against a tree and the "
        "camera can see straight past it.",
        made)
    return [BEL.find_then_pin(ready), BEL.find_then_pin(unarmed)], muzzle
