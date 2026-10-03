"""The carry: writes Lowered once a frame, which is whether the ready pose is
off (ready_pose.py and the equip in inventory.py read it).

    Lowered = Sprinting
              OR (Held is a gun AND NOT Stance == PRONE
                  AND NOT (Aiming OR Blocking OR RaiseForced
                           OR SightSeat > SEAT_HOLD
                           OR now < Held.NextFireTime + hold))

A gun is an item that is neither Melee nor Consumable, and does not Burn: the
knife, the food and the stick keep their hold poses, which point nothing
forward (the stick's is a torch held up: lowered, its fire would hang at the
knee). Aiming is either aim key
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
from uebp.graph import _connect, _node, _pin, _set, _vec, else_, out, then
from combat.seat_tuning import SEAT_HOLD, SEAT_VAR
from combat.torch_tuning import BURNS_VAR
from combat.weapon_component.common import _muzzle_location, _prop
from combat.weapon_component.stance import PRONE, STANCE_VAR
from uebp.nodes.actor import FN_GET_OWNER, FN_GET_TRANSFORM
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_VV, FN_AND, FN_EQ_II, FN_GREATER_FF, FN_LESS_FF, FN_NOT, FN_OR,
    FN_SELECT_VECTOR, FN_TRANSFORM_LOC)
from uebp.nodes.system import FN_TIME_SECONDS


def _author_shot_origin(ed, held):
    """Where a shot starts, as a pure sub-graph: the muzzle, or while Lowered
    the place the raised muzzle will be. Shared by the aim resolve and the
    pellets, as the muzzle was, so the two cannot disagree."""
    real = _muzzle_location(ed, held)
    owner = _node(ed, FN_GET_OWNER)
    body = _node(ed, FN_GET_TRANSFORM)
    _connect(out(owner), _pin(body, "self"))
    off_pin, _off = _prop(ed, "MuzzleOffset", held)
    grip = _vec(ed, *CARRY_GRIP)
    ahead = _node(ed, FN_ADD_VV)
    _connect(off_pin, _pin(ahead, "A"))
    _connect(grip, _pin(ahead, "B"))
    raised = _node(ed, FN_TRANSFORM_LOC)
    _connect(out(body), _pin(raised, "T"))
    _connect(out(ahead), _pin(raised, "Location"))
    down = ed.add_get_member_variable_node(LOWERED_VAR)
    pick = _node(ed, FN_SELECT_VECTOR)
    _connect(out(raised), _pin(pick, "A"))
    _connect(real, _pin(pick, "B"))
    _connect(out(down, LOWERED_VAR), _pin(pick, "bPickA"))
    return out(pick)


def _author_carry(ed, held, armed_out, exec_ins):
    """Write Lowered behind an IsValid(Held) Branch; returns the exits."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(name):
        n = keep(ed.add_get_member_variable_node(name))
        return out(n, name)

    def gate2(fn, a, b):
        n = keep(_node(ed, fn))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return out(n)

    def negate(a):
        n = keep(_node(ed, FN_NOT))
        _connect(a, _pin(n, "A"))
        return out(n)

    gate = keep(ed.add_branch_node())
    _connect(armed_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    # --- is it a gun? ---------------------------------------------------------
    melee, melee_n = _prop(ed, "Melee", held)
    food, food_n = _prop(ed, "Consumable", held)
    burns, burns_n = _prop(ed, BURNS_VAR, held)
    keep(melee_n)
    keep(food_n)
    keep(burns_n)
    held_up = gate2(FN_OR, gate2(FN_OR, melee, food), burns)
    gun = negate(held_up)

    # --- is anything holding it up? -------------------------------------------
    hands = gate2(FN_OR, get("Aiming"), get("Blocking"))
    hands = gate2(FN_OR, hands, get(RAISE_FORCED_VAR))
    # ...or the camera, still on the gun's sights (seat.py). Literal on B.
    on_gun = keep(_node(ed, FN_GREATER_FF))
    _connect(get(SEAT_VAR), _pin(on_gun, "A"))
    _set(on_gun, "B", SEAT_HOLD)
    hands = gate2(FN_OR, hands, out(on_gun))
    ready, ready_n = _prop(ed, "NextFireTime", held)
    keep(ready_n)
    until = keep(_node(ed, FN_ADD_FF))
    _connect(ready, _pin(until, "A"))
    _set(until, "B", CARRY_RAISE_HOLD_S)
    now = keep(_node(ed, FN_TIME_SECONDS))
    fresh = gate2(FN_LESS_FF, out(now), out(until))
    raised = gate2(FN_OR, hands, fresh)

    gun_down = gate2(FN_AND, gun, negate(raised))
    # Not while prone: the literal is on B, the pin that holds one.
    lying = keep(_node(ed, FN_EQ_II))
    _connect(get(STANCE_VAR), _pin(lying, "A"))
    _set(lying, "B", PRONE)
    upright = negate(out(lying))
    gun_down = gate2(FN_AND, gun_down, upright)
    down = gate2(FN_OR, get("Sprinting"), gun_down)

    mark = keep(ed.add_set_member_variable_node(LOWERED_VAR))
    _connect(down, _pin(mark, LOWERED_VAR))
    _connect(then(gate), _pin(mark, "execute"))

    # --- empty hands: the pose follows the sprint alone -----------------------
    running = keep(ed.add_get_member_variable_node("Sprinting"))
    plain = keep(ed.add_set_member_variable_node(LOWERED_VAR))
    _connect(out(running, "Sprinting"), _pin(plain, LOWERED_VAR))
    _connect(else_(gate), _pin(plain, "execute"))

    ed.add_comment_to_nodes(
        f"The carry. {LOWERED_VAR} is whether the ready pose is off: sprinting, "
        "or a gun (not Melee, not Consumable, not the stick; not while prone) that no aim key, "
        f"guard, shot or reload is holding up, and that the sight camera has "
        f"left (SightSeat under {SEAT_HOLD:g}). A shot or a reload holds it up until "
        f"{CARRY_RAISE_HOLD_S:g} s after NextFireTime. Lowered, the locomotion "
        "comes through and the gun rides in the hand, off the horizon.",
        made)
    return (then(mark), then(plain))
