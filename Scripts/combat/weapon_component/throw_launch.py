"""Where a throw leaves from and how fast: (start, velocity), as pure pins the
arc is predicted from and the release stores (throw.py).

    start    in front of the chest: THROW_START_FORWARD ahead of the capsule's
             centre along the view's yaw, THROW_START_UP above it
    yaw      towards AimPoint, the point the reticle rests on (aim.py), so the
             curve lies in the upright plane through that point and stands
             under the reticle on screen. The launch point is off to one side
             of the camera's line: along the view's own yaw the arc ran
             beside the reticle and never met it
    pitch    the one whose curve passes through AimPoint at Held.ThrowSpeed,
             so the item goes where the reticle is. With no such pitch (the
             point is aim_rot of the speed's reach, or is the sky), the view's,
             tipped up Held.ThrowArcDegrees: a lob

THE AIMED PITCH
---------------
From the start, AimPoint is d away over the ground and h up. A throw at speed
v under gravity g passes through it when

    tan(pitch) = (v^2 - sqrt(v^4 - g (g d^2 + 2 h v^2))) / (g d)

the flatter of the two answers. Under the root is negative when the point is
aim_rot of reach (and at the sky, AIM_TRACE_RANGE aim_rot): the throw then falls
back on the tipped view, which is what ThrowArcDegrees is for. The default
speed reaches about 12 m over level ground, a melee weapon's 33 m. Taken with DegAtan2, so a point straight above or below (d = 0)
is a throw straight up or down, capped like any other.

AimPoint is only used THROW_AIM_MIN_AHEAD or more ahead of the start, along
the view's yaw: a wall at the shoulder or a trunk between the camera and the
player would turn the throw sideways or back. Nearer than that the yaw is the
view's and the pitch the tipped view's.

Everything here is pure and reads Held: pull these pins only where it is
valid. AimPoint is this frame's, resolved at the head of Tick.
"""

from uebp.graph import _connect, _node, _pin, _set, _vec, out
from combat.throw_tuning import (
    THROW_AIM_MIN_AHEAD, THROW_GRAVITY_Z, THROW_MAX_PITCH_DEG,
    THROW_PITCH_VAR, THROW_SPEED_VAR, THROW_START_FORWARD, THROW_START_UP,
)
from combat.weapon_component.common import _prop
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_CONTROL_ROT
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_VV, FN_AND, FN_BREAK_ROT, FN_BREAK_VECTOR, FN_CLAMP, FN_DEG_ATAN2,
    FN_DOT_VV, FN_FORWARD, FN_GE_FF, FN_MAKE_ROT, FN_MAKE_VECTOR, FN_MAX_FF, FN_MUL_FF,
    FN_MUL_VF, FN_NORMALIZE_AXIS, FN_SELECT_FF, FN_SQRT, FN_SUB_FF, FN_SUB_VV, FN_VEC_TO_ROT,
    FN_VSIZE_XY)
from combat.weapon_component import vars as WV

AIM_POINT_VAR = WV.AimPoint


def _math(ed, fn, a, b):
    """fn(a, b), where b is a pin or a literal (a math node's A holds none)."""
    n = _node(ed, fn)
    _connect(a, _pin(n, "A"))
    if isinstance(b, (int, float)):
        _set(n, "B", float(b))
    else:
        _connect(b, _pin(n, "B"))
    return out(n)


def _pick(ed, a, b, pick_a):
    n = _node(ed, FN_SELECT_FF)
    _connect(a, _pin(n, "A"))
    _connect(b, _pin(n, "B"))
    _connect(pick_a, _pin(n, "bPickA"))
    return out(n)


def _author_start(ed, owner_out, yaw):
    """(start, ahead_dir): the launch point, and the level direction the view
    faces, which it is set forward along."""
    flat = _node(ed, FN_MAKE_ROT)
    _connect(yaw, _pin(flat, "Yaw"))
    ahead_dir = _node(ed, FN_FORWARD)
    _connect(out(flat), _pin(ahead_dir, "InRot"))
    ahead = _node(ed, FN_MUL_VF)
    _connect(out(ahead_dir), _pin(ahead, "A"))
    f = THROW_START_FORWARD
    _connect(_vec(ed, f, f, f), _pin(ahead, "B"))
    here = _node(ed, FN_ACTOR_LOC)
    _connect(owner_out, _pin(here, "self"))
    raised = _node(ed, FN_ADD_VV)
    _connect(out(here), _pin(raised, "A"))
    _connect(_vec(ed, 0.0, 0.0, THROW_START_UP), _pin(raised, "B"))
    start = _node(ed, FN_ADD_VV)
    _connect(out(raised), _pin(start, "A"))
    _connect(out(ahead), _pin(start, "B"))
    return out(start), out(ahead_dir)


def _author_through(ed, to, speed):
    """(pitch, reaches): the flatter pitch of a throw at ``speed`` whose curve
    passes through the point ``to`` away from its start, and whether there is
    one. See the module docstring."""
    g = -THROW_GRAVITY_Z
    d = _node(ed, FN_VSIZE_XY)
    _connect(to, _pin(d, "A"))
    parts = _node(ed, FN_BREAK_VECTOR)
    _connect(to, _pin(parts, "InVec"))
    v2 = _math(ed, FN_MUL_FF, speed, speed)
    v4 = _math(ed, FN_MUL_FF, v2, v2)
    gd2 = _math(ed, FN_MUL_FF, _math(ed, FN_MUL_FF, out(d), out(d)), g)
    hv2 = _math(ed, FN_MUL_FF, _math(ed, FN_MUL_FF, out(parts, "Z"), v2), 2.0)
    drop = _math(ed, FN_MUL_FF, _math(ed, FN_ADD_FF, gd2, hv2), g)
    under = _math(ed, FN_SUB_FF, v4, drop)
    reaches = _math(ed, FN_GE_FF, under, 0.0)
    root = _node(ed, FN_SQRT)
    _connect(_math(ed, FN_MAX_FF, under, 0.0), _pin(root, "A"))
    pitch = _node(ed, FN_DEG_ATAN2)
    _connect(_math(ed, FN_SUB_FF, v2, out(root)), _pin(pitch, "Y"))
    _connect(_math(ed, FN_MUL_FF, out(d), g), _pin(pitch, "X"))
    return out(pitch), reaches


def _author_launch(ed, pc_out, owner_out, held):
    """(start, velocity) of a throw of Held, as pure pins."""
    view = _node(ed, FN_GET_CONTROL_ROT)
    _connect(pc_out, _pin(view, "self"))
    parts = _node(ed, FN_BREAK_ROT)
    _connect(out(view), _pin(parts, "InRot"))
    # The controller's pitch comes back 0..360; 350 is ten degrees down.
    signed = _node(ed, FN_NORMALIZE_AXIS)
    _connect(out(parts, "Pitch"), _pin(signed, "Angle"))
    tip, _tip_n = _prop(ed, THROW_PITCH_VAR, held)
    tipped = _math(ed, FN_ADD_FF, out(signed), tip)
    speed, _speed_n = _prop(ed, THROW_SPEED_VAR, held)

    start, ahead_dir = _author_start(ed, owner_out, out(parts, "Yaw"))

    # --- the point the reticle rests on, as seen from the start ---------------
    aim = ed.add_get_member_variable_node(AIM_POINT_VAR)
    to = _node(ed, FN_SUB_VV)
    _connect(out(aim, AIM_POINT_VAR), _pin(to, "A"))
    _connect(start, _pin(to, "B"))
    ahead_cm = _node(ed, FN_DOT_VV)
    _connect(out(to), _pin(ahead_cm, "A"))
    _connect(ahead_dir, _pin(ahead_cm, "B"))
    clear = _math(ed, FN_GE_FF, out(ahead_cm), THROW_AIM_MIN_AHEAD)
    towards = _node(ed, FN_VEC_TO_ROT)
    _connect(out(to), _pin(towards, "InVec"))
    bearing = _node(ed, FN_BREAK_ROT)
    _connect(out(towards), _pin(bearing, "InRot"))
    yaw = _pick(ed, out(bearing, "Yaw"), out(parts, "Yaw"), clear)

    through, reaches = _author_through(ed, out(to), speed)
    aimed = _math(ed, FN_AND, clear, reaches)
    pitch = _pick(ed, through, tipped, aimed)
    # Capped either way: a throw straight up would land on the thrower.
    capped = _node(ed, FN_CLAMP)
    _connect(pitch, _pin(capped, "Value"))
    _set(capped, "Min", -89.0)
    _set(capped, "Max", THROW_MAX_PITCH_DEG)

    aim_rot = _node(ed, FN_MAKE_ROT)
    _connect(out(capped), _pin(aim_rot, "Pitch"))
    _connect(yaw, _pin(aim_rot, "Yaw"))
    along = _node(ed, FN_FORWARD)
    _connect(out(aim_rot), _pin(along, "InRot"))
    velocity = _node(ed, FN_MUL_VF)
    _connect(out(along), _pin(velocity, "A"))
    # Vector x float is a wildcard whose B is a vector: the speed, three times.
    speeds = _node(ed, FN_MAKE_VECTOR)
    for axis in ("X", "Y", "Z"):
        _connect(speed, _pin(speeds, axis))
    _connect(out(speeds), _pin(velocity, "B"))
    return start, out(velocity)
