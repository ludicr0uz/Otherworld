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
             point is out of the speed's reach, or is the sky), the view's,
             tipped up Held.ThrowArcDegrees: a lob

THE AIMED PITCH
---------------
From the start, AimPoint is d away over the ground and h up. A throw at speed
v under gravity g passes through it when

    tan(pitch) = (v^2 - sqrt(v^4 - g (g d^2 + 2 h v^2))) / (g d)

the flatter of the two answers. Under the root is negative when the point is
out of reach (and at the sky, AIM_TRACE_RANGE out): the throw then falls
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

from combat.graph import _at, _connect, _node, _pin, _set, _vec
from combat.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ADD_VV, FN_AND, FN_BREAK_ROT, FN_BREAK_VECTOR,
    FN_CLAMP, FN_DEG_ATAN2, FN_DOT_VV, FN_FORWARD, FN_GE_FF, FN_GET_CONTROL_ROT,
    FN_MAKE_ROT, FN_MAKE_VECTOR, FN_MAX_FF, FN_MUL_FF, FN_MUL_VF,
    FN_NORMALIZE_AXIS, FN_SELECT_FF, FN_SQRT, FN_SUB_FF, FN_SUB_VV,
    FN_VEC_TO_ROT, FN_VSIZE_XY,
)
from combat.throw_tuning import (
    THROW_AIM_MIN_AHEAD, THROW_GRAVITY_Z, THROW_MAX_PITCH_DEG,
    THROW_PITCH_VAR, THROW_SPEED_VAR, THROW_START_FORWARD, THROW_START_UP,
)
from combat.weapon_component.common import _prop

AIM_POINT_VAR = "AimPoint"


def _out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def _math(ed, fn, a, b, x, y):
    """fn(a, b), where b is a pin or a literal (a math node's A holds none)."""
    n = _at(_node(ed, fn), x, y)
    _connect(a, _pin(n, "A"))
    if isinstance(b, (int, float)):
        _set(n, "B", float(b))
    else:
        _connect(b, _pin(n, "B"))
    return _out(n)


def _pick(ed, a, b, pick_a, x, y):
    n = _at(_node(ed, FN_SELECT_FF), x, y)
    _connect(a, _pin(n, "A"))
    _connect(b, _pin(n, "B"))
    _connect(pick_a, _pin(n, "bPickA"))
    return _out(n)


def _author_start(ed, owner_out, yaw, x0, y0):
    """(start, ahead_dir): the launch point, and the level direction the view
    faces, which it is set forward along."""
    flat = _at(_node(ed, FN_MAKE_ROT), x0, y0)
    _connect(yaw, _pin(flat, "Yaw"))
    ahead_dir = _at(_node(ed, FN_FORWARD), x0 + 240, y0)
    _connect(_out(flat), _pin(ahead_dir, "InRot"))
    ahead = _at(_node(ed, FN_MUL_VF), x0 + 480, y0)
    _connect(_out(ahead_dir), _pin(ahead, "A"))
    f = THROW_START_FORWARD
    _connect(_vec(ed, f, f, f, x0 + 240, y0 + 140), _pin(ahead, "B"))
    here = _at(_node(ed, FN_ACTOR_LOC), x0 + 480, y0 + 260)
    _connect(owner_out, _pin(here, "self"))
    raised = _at(_node(ed, FN_ADD_VV), x0 + 720, y0 + 260)
    _connect(_out(here), _pin(raised, "A"))
    _connect(_vec(ed, 0.0, 0.0, THROW_START_UP, x0 + 480, y0 + 400), _pin(raised, "B"))
    start = _at(_node(ed, FN_ADD_VV), x0 + 960, y0)
    _connect(_out(raised), _pin(start, "A"))
    _connect(_out(ahead), _pin(start, "B"))
    return _out(start), _out(ahead_dir)


def _author_through(ed, to, speed, x0, y0):
    """(pitch, reaches): the flatter pitch of a throw at ``speed`` whose curve
    passes through the point ``to`` away from its start, and whether there is
    one. See the module docstring."""
    g = -THROW_GRAVITY_Z
    d = _at(_node(ed, FN_VSIZE_XY), x0, y0)
    _connect(to, _pin(d, "A"))
    parts = _at(_node(ed, FN_BREAK_VECTOR), x0, y0 + 140)
    _connect(to, _pin(parts, "InVec"))
    v2 = _math(ed, FN_MUL_FF, speed, speed, x0, y0 + 300)
    v4 = _math(ed, FN_MUL_FF, v2, v2, x0 + 240, y0 + 300)
    gd2 = _math(ed, FN_MUL_FF, _math(ed, FN_MUL_FF, _out(d), _out(d), x0 + 240, y0),
                g, x0 + 480, y0)
    hv2 = _math(ed, FN_MUL_FF, _math(ed, FN_MUL_FF, _out(parts, "Z"), v2,
                                     x0 + 240, y0 + 140), 2.0, x0 + 480, y0 + 140)
    drop = _math(ed, FN_MUL_FF, _math(ed, FN_ADD_FF, gd2, hv2, x0 + 720, y0),
                 g, x0 + 960, y0)
    under = _math(ed, FN_SUB_FF, v4, drop, x0 + 1200, y0 + 300)
    reaches = _math(ed, FN_GE_FF, under, 0.0, x0 + 1440, y0 + 440)
    root = _at(_node(ed, FN_SQRT), x0 + 1680, y0 + 300)
    _connect(_math(ed, FN_MAX_FF, under, 0.0, x0 + 1440, y0 + 300), _pin(root, "A"))
    pitch = _at(_node(ed, FN_DEG_ATAN2), x0 + 2160, y0)
    _connect(_math(ed, FN_SUB_FF, v2, _out(root), x0 + 1920, y0 + 300), _pin(pitch, "Y"))
    _connect(_math(ed, FN_MUL_FF, _out(d), g, x0 + 1920, y0), _pin(pitch, "X"))
    return _out(pitch), reaches


def _author_launch(ed, pc_out, owner_out, held, x0, y0):
    """(start, velocity) of a throw of Held, as pure pins."""
    view = _at(_node(ed, FN_GET_CONTROL_ROT), x0, y0)
    _connect(pc_out, _pin(view, "self"))
    parts = _at(_node(ed, FN_BREAK_ROT), x0 + 240, y0)
    _connect(_out(view), _pin(parts, "InRot"))
    # The controller's pitch comes back 0..360; 350 is ten degrees down.
    signed = _at(_node(ed, FN_NORMALIZE_AXIS), x0 + 480, y0)
    _connect(_out(parts, "Pitch"), _pin(signed, "Angle"))
    tip, _tip_n = _prop(ed, THROW_PITCH_VAR, held, x0 + 480, y0 + 140)
    tipped = _math(ed, FN_ADD_FF, _out(signed), tip, x0 + 720, y0)
    speed, _speed_n = _prop(ed, THROW_SPEED_VAR, held, x0 + 480, y0 + 280)

    start, ahead_dir = _author_start(ed, owner_out, _out(parts, "Yaw"),
                                     x0 + 720, y0 + 500)

    # --- the point the reticle rests on, as seen from the start ---------------
    aim = _at(ed.add_get_member_variable_node(AIM_POINT_VAR), x0 + 1680, y0 + 760)
    to = _at(_node(ed, FN_SUB_VV), x0 + 1920, y0 + 700)
    _connect(_out(aim, AIM_POINT_VAR), _pin(to, "A"))
    _connect(start, _pin(to, "B"))
    ahead_cm = _at(_node(ed, FN_DOT_VV), x0 + 2160, y0 + 560)
    _connect(_out(to), _pin(ahead_cm, "A"))
    _connect(ahead_dir, _pin(ahead_cm, "B"))
    clear = _math(ed, FN_GE_FF, _out(ahead_cm), THROW_AIM_MIN_AHEAD, x0 + 2400, y0 + 560)
    towards = _at(_node(ed, FN_VEC_TO_ROT), x0 + 2160, y0 + 700)
    _connect(_out(to), _pin(towards, "InVec"))
    bearing = _at(_node(ed, FN_BREAK_ROT), x0 + 2400, y0 + 700)
    _connect(_out(towards), _pin(bearing, "InRot"))
    yaw = _pick(ed, _out(bearing, "Yaw"), _out(parts, "Yaw"), clear, x0 + 2640, y0 + 600)

    through, reaches = _author_through(ed, _out(to), speed, x0 + 2160, y0 + 900)
    aimed = _math(ed, FN_AND, clear, reaches, x0 + 4320, y0 + 440)
    pitch = _pick(ed, through, tipped, aimed, x0 + 4800, y0)
    # Capped either way: a throw straight up would land on the thrower.
    capped = _at(_node(ed, FN_CLAMP), x0 + 5040, y0)
    _connect(pitch, _pin(capped, "Value"))
    _set(capped, "Min", -89.0)
    _set(capped, "Max", THROW_MAX_PITCH_DEG)

    out = _at(_node(ed, FN_MAKE_ROT), x0 + 5280, y0)
    _connect(_out(capped), _pin(out, "Pitch"))
    _connect(yaw, _pin(out, "Yaw"))
    along = _at(_node(ed, FN_FORWARD), x0 + 5520, y0)
    _connect(_out(out), _pin(along, "InRot"))
    velocity = _at(_node(ed, FN_MUL_VF), x0 + 5760, y0)
    _connect(_out(along), _pin(velocity, "A"))
    # Vector x float is a wildcard whose B is a vector: the speed, three times.
    speeds = _at(_node(ed, FN_MAKE_VECTOR), x0 + 5520, y0 + 140)
    for axis in ("X", "Y", "Z"):
        _connect(speed, _pin(speeds, axis))
    _connect(_out(speeds), _pin(velocity, "B"))
    return start, _out(velocity)
