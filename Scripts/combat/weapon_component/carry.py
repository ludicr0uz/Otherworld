"""The carry: writes Lowered once a frame, which is whether the ready pose is
off (ready_pose.py and the equip in inventory.py read it).

    Lowered = Sprinting
              OR (Held is a gun AND NOT Stance == PRONE
                  AND NOT (Aiming OR Blocking OR RaiseForced
                           OR SightSeat > SEAT_HOLD
                           OR now < Held.NextFireTime + hold))

A gun is an item that is neither Melee nor Consumable: the knife and the food
keep their hold poses, which point nothing forward. Aiming is either aim key
(over the shoulder or down the sights). NextFireTime is written by a shot and
by a reload, so both raise the gun and keep it up for CARRY_RAISE_HOLD_S after
it could fire again. RaiseForced is a probe's stand-in for an aim key.
SightSeat (seat.py) is how far the camera is onto the gun's sights: the gun
stays up until the camera has left it, or the view, easing home after the
sights key is let go, would dip with the gun on its way down.

Prone, the gun stays up: the crawl's own arms pull along the ground, where a
gun in the fist would be dragged through it, and the chest propped behind a
level gun is what lying down with one looks like.

The shot itself is not delayed: it leaves on the frame of the click and the
gun comes up behind it with the ready pose's own blend. So it cannot start at
the muzzle, which is at the knee and pointing at the ground: while Lowered,
_author_shot_origin gives the aim resolve and the pellets the place the raised
muzzle is about to be (CARRY_GRIP in the body's frame + Held.MuzzleOffset),
and the real muzzle otherwise.

Held is read behind an IsValid Branch: with empty hands Lowered is Sprinting,
which is what the pose followed before there was a carry.
"""

from combat.carry_tuning import (
    CARRY_GRIP, CARRY_RAISE_HOLD_S, LOWERED_VAR, RAISE_FORCED_VAR,
)
from combat.graph import BEL, _at, _connect, _node, _pin, _set, _vec
from combat.nodes import (
    FN_ADD_FF, FN_ADD_VV, FN_AND, FN_EQ_II, FN_GET_OWNER, FN_GET_TRANSFORM,
    FN_GREATER_FF, FN_LESS_FF, FN_NOT, FN_OR, FN_SELECT_VECTOR, FN_TIME_SECONDS,
    FN_TRANSFORM_LOC,
)
from combat.seat_tuning import SEAT_HOLD, SEAT_VAR
from combat.weapon_component.common import _muzzle_location, _prop
from combat.weapon_component.stance import PRONE, STANCE_VAR


def _author_shot_origin(ed, held, x, y):
    """Where a shot starts, as a pure sub-graph: the muzzle, or while Lowered
    the place the raised muzzle will be. Shared by the aim resolve and the
    pellets, as the muzzle was, so the two cannot disagree."""
    real = _muzzle_location(ed, held, x, y)
    owner = _at(_node(ed, FN_GET_OWNER), x, y + 320)
    body = _at(_node(ed, FN_GET_TRANSFORM), x + 240, y + 320)
    _connect(_pin(owner, "ReturnValue", is_input=False), _pin(body, "self"))
    off_pin, _off = _prop(ed, "MuzzleOffset", held, x, y + 460)
    grip = _vec(ed, *CARRY_GRIP, x, y + 600)
    ahead = _at(_node(ed, FN_ADD_VV), x + 240, y + 500)
    _connect(off_pin, _pin(ahead, "A"))
    _connect(grip, _pin(ahead, "B"))
    raised = _at(_node(ed, FN_TRANSFORM_LOC), x + 500, y + 400)
    _connect(_pin(body, "ReturnValue", is_input=False), _pin(raised, "T"))
    _connect(_pin(ahead, "ReturnValue", is_input=False), _pin(raised, "Location"))
    down = _at(ed.add_get_member_variable_node(LOWERED_VAR), x + 500, y + 600)
    pick = _at(_node(ed, FN_SELECT_VECTOR), x + 760, y + 200)
    _connect(_pin(raised, "ReturnValue", is_input=False), _pin(pick, "A"))
    _connect(real, _pin(pick, "B"))
    _connect(_pin(down, LOWERED_VAR, is_input=False), _pin(pick, "bPickA"))
    return _pin(pick, "ReturnValue", is_input=False)


def _author_carry(ed, held, armed_out, exec_ins, x0, y0):
    """Write Lowered behind an IsValid(Held) Branch; returns the exits."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(name, y):
        n = keep(_at(ed.add_get_member_variable_node(name), x0 + 240, y))
        return _pin(n, name, is_input=False)

    def gate2(fn, a, b, x, y):
        n = keep(_at(_node(ed, fn), x, y))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return _pin(n, "ReturnValue", is_input=False)

    def negate(a, x, y):
        n = keep(_at(_node(ed, FN_NOT), x, y))
        _connect(a, _pin(n, "A"))
        return _pin(n, "ReturnValue", is_input=False)

    gate = keep(_at(ed.add_branch_node(), x0, y0))
    _connect(armed_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    # --- is it a gun? ---------------------------------------------------------
    melee, melee_n = _prop(ed, "Melee", held, x0 + 240, y0 + 200)
    food, food_n = _prop(ed, "Consumable", held, x0 + 240, y0 + 320)
    keep(melee_n)
    keep(food_n)
    gun = negate(gate2(FN_OR, melee, food, x0 + 500, y0 + 260), x0 + 740, y0 + 260)

    # --- is anything holding it up? -------------------------------------------
    hands = gate2(FN_OR, get("Aiming", y0 + 460), get("Blocking", y0 + 560),
                  x0 + 500, y0 + 500)
    hands = gate2(FN_OR, hands, get(RAISE_FORCED_VAR, y0 + 620), x0 + 740, y0 + 540)
    # ...or the camera, still on the gun's sights (seat.py). Literal on B.
    on_gun = keep(_at(_node(ed, FN_GREATER_FF), x0 + 500, y0 + 1100))
    _connect(get(SEAT_VAR, y0 + 1100), _pin(on_gun, "A"))
    _set(on_gun, "B", SEAT_HOLD)
    hands = gate2(FN_OR, hands, _pin(on_gun, "ReturnValue", is_input=False),
                  x0 + 980, y0 + 480)
    ready, ready_n = _prop(ed, "NextFireTime", held, x0 + 240, y0 + 700)
    keep(ready_n)
    until = keep(_at(_node(ed, FN_ADD_FF), x0 + 500, y0 + 700))
    _connect(ready, _pin(until, "A"))
    _set(until, "B", CARRY_RAISE_HOLD_S)
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 500, y0 + 840))
    fresh = gate2(FN_LESS_FF, _pin(now, "ReturnValue", is_input=False),
                  _pin(until, "ReturnValue", is_input=False), x0 + 740, y0 + 760)
    raised = gate2(FN_OR, hands, fresh, x0 + 980, y0 + 600)

    gun_down = gate2(FN_AND, gun, negate(raised, x0 + 1220, y0 + 600),
                     x0 + 1460, y0 + 400)
    # Not while prone: the literal is on B, the pin that holds one.
    lying = keep(_at(_node(ed, FN_EQ_II), x0 + 1220, y0 + 760))
    _connect(get(STANCE_VAR, y0 + 900), _pin(lying, "A"))
    _set(lying, "B", PRONE)
    upright = negate(_pin(lying, "ReturnValue", is_input=False), x0 + 1460, y0 + 760)
    gun_down = gate2(FN_AND, gun_down, upright, x0 + 1700, y0 + 500)
    down = gate2(FN_OR, get("Sprinting", y0 + 100), gun_down, x0 + 1940, y0 + 200)

    mark = keep(_at(ed.add_set_member_variable_node(LOWERED_VAR), x0 + 2200, y0))
    _connect(down, _pin(mark, LOWERED_VAR))
    _connect(BEL.find_then_pin(gate), _pin(mark, "execute"))

    # --- empty hands: the pose follows the sprint alone -----------------------
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"),
                       x0 + 240, y0 + 1000))
    plain = keep(_at(ed.add_set_member_variable_node(LOWERED_VAR), x0 + 500, y0 + 960))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(plain, LOWERED_VAR))
    _connect(BEL.find_else_pin(gate), _pin(plain, "execute"))

    ed.add_comment_to_nodes(
        f"The carry. {LOWERED_VAR} is whether the ready pose is off: sprinting, "
        "or a gun (not Melee, not Consumable; not while prone) that no aim key, "
        f"guard, shot or reload is holding up, and that the sight camera has "
        f"left (SightSeat under {SEAT_HOLD:g}). A shot or a reload holds it up until "
        f"{CARRY_RAISE_HOLD_S:g} s after NextFireTime. Lowered, the locomotion "
        "comes through and the gun rides in the hand, off the horizon.",
        made)
    return (BEL.find_then_pin(mark), BEL.find_then_pin(plain))
