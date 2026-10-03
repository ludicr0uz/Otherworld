"""The use key's one kind so far: a stick that Burns (stick.py).

    Using --> Held.Lit --> FireWard = true          the fire is held out
              not Lit  --> FireWard = false
                           UsePressed AND Held.Burns
                             --> NearFire = any CampfireClass actor within
                                 STICK_LIGHT_RADIUS_CM of the player
                             --> NearFire: Held.BurnOutTime = now + burn,
                                           Held.Lit = true
    not Using --> FireWard = false

    WardItem valid AND (NOT FireWard OR WardItem != Held)
        --> WardItem.AimPose = WardCarryPose; WardItem = None; re-equip
    FireWard AND WardItem not valid
        --> WardItem = Held; WardCarryPose = Held.AimPose;
            Held.AimPose = Held.UsePose; re-equip

FireWard is written on every arm, every frame, so nothing has to remember to
lower it: the key let go, a sprint, the stick burning out (stick.py's own
Tick clears Lit), dropped, thrown or switched away from all read as "not
held out" on the next frame. A creature afraid of fire reads it
(npc/ward.py). The dead gate lets it go too (dead.py).

The press that lights the stick does not raise it: Lit is read before the
light, and the next frame of the held key finds it burning.

THE RAISED POSE
---------------
The ready pose an item is held in is its AimPose, which the equip plays and
the keep-alive restarts (inventory.py, ready_pose.py). Raising the stick
swaps that variable on the stick itself for its UsePose and re-equips, so
both of those readers follow with no branch of their own, and the equip's
blend carries the arm up and down. WardItem is the stick that is raised and
WardCarryPose what to put back; the lowering is tested first, so a stick
swapped for another lit one is lowered and the new one raised on one frame.
Both poses close the fist as the pistol pose does (hold_pose.py), so the grip
solved against the one holds in the other.

The loop over the campfires only remembers (NearFire); the stick is lit once,
off Completed, as the matches' strike and the pick-up are. With no
CampfireClass (survival not built) the walk is over nothing. Held's flags are
read behind the Branch on Using or UsePressed, which are false with empty
hands. Numbers and names: torch_tuning.py.
"""

from uebp.graph import _connect, _loose_pin, _node, _pin, _set, else_, out, then
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ALL_ACTORS, FN_AND, FN_DISTANCE, FN_IS_VALID,
    FN_LE_FF, FN_NOT, FN_OR, FN_TIME_SECONDS, MACRO_FOR_EACH,
)
from combat.paths import FIRE_WARD_VAR, ITEM_CLASS_PATH
from combat.torch_tuning import (
    BURN_OUT_VAR, BURNS_VAR, LIT_VAR, NEAR_FIRE_VAR, STICK_BURN_S,
    STICK_LIGHT_RADIUS_CM, USE_POSE_VAR, WARD_CARRY_VAR, WARD_ITEM_VAR,
)
from combat.use_tuning import USE_PRESSED_VAR, USING_VAR
from combat.weapon_component.common import _prop

FN_NEQ_OBJECTS = "/Script/Engine.KismetMathLibrary.NotEqual_ObjectObject"


def _author_torch(ed, held, owner, exec_ins):
    """See the module docstring. Returns the exits."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(name):
        return out(keep(ed.add_get_member_variable_node(name)), name)

    def put(name, value):
        n = keep(ed.add_set_member_variable_node(name))
        if value is not None:
            _set(n, name, value)
        return n

    def held_prop(name):
        pin, n = _prop(ed, name, held)
        keep(n)
        return pin

    def gate2(fn, a, b):
        n = keep(_node(ed, fn))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return out(n)

    def negate(a):
        n = keep(_node(ed, FN_NOT))
        _connect(a, _pin(n, "A"))
        return out(n)

    def branch(cond, exec_in):
        n = keep(ed.add_branch_node())
        _connect(cond, _pin(n, "Condition"))
        for e in exec_in:
            _connect(e, _pin(n, "execute"))
        return n

    # --- is the fire held out? -------------------------------------------------
    using = branch(get(USING_VAR), exec_ins)
    lit = branch(held_prop(LIT_VAR), (then(using),))
    out_ = put(FIRE_WARD_VAR, "true")
    _connect(then(lit), _pin(out_, "execute"))
    idle = put(FIRE_WARD_VAR, "false")
    _connect(else_(using), _pin(idle, "execute"))
    unlit = put(FIRE_WARD_VAR, "false")
    _connect(else_(lit), _pin(unlit, "execute"))

    # --- not burning: a press at a campfire lights it ---------------------------
    wants = branch(gate2(FN_AND, get(USE_PRESSED_VAR), held_prop(BURNS_VAR)), (then(unlit),))
    forget = put(NEAR_FIRE_VAR, "false")
    _connect(then(wants), _pin(forget, "execute"))
    every = keep(_node(ed, FN_ALL_ACTORS))
    _connect(get(CAMPFIRE_CLASS_VAR), _pin(every, "ActorClass"))
    _connect(then(forget), _pin(every, "execute"))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(loop)
    _connect(out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(then(every), _loose_pin(loop, "Exec"))
    there = keep(_node(ed, FN_ACTOR_LOC))
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(there, "self"))
    here = keep(_node(ed, FN_ACTOR_LOC))
    _connect(owner, _pin(here, "self"))
    gap = keep(_node(ed, FN_DISTANCE))
    _connect(out(there), _pin(gap, "V1"))
    _connect(out(here), _pin(gap, "V2"))
    close = keep(_node(ed, FN_LE_FF))
    _connect(out(gap), _pin(close, "A"))
    _set(close, "B", STICK_LIGHT_RADIUS_CM)
    near = branch(out(close), (_loose_pin(loop, "LoopBody", is_input=False),))
    found = put(NEAR_FIRE_VAR, "true")
    _connect(then(near), _pin(found, "execute"))

    at_fire = branch(get(NEAR_FIRE_VAR), (_loose_pin(loop, "Completed", is_input=False),))
    now = keep(_node(ed, FN_TIME_SECONDS))
    until = keep(_node(ed, FN_ADD_FF))
    _connect(out(now), _pin(until, "A"))
    _set(until, "B", STICK_BURN_S)
    burn = keep(ed.add_set_member_variable_node(BURN_OUT_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(burn, "self"))
    _connect(out(until), _pin(burn, BURN_OUT_VAR))
    _connect(then(at_fire), _pin(burn, "execute"))
    light = keep(ed.add_set_member_variable_node(LIT_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(light, "self"))
    _set(light, LIT_VAR, "true")
    _connect(then(burn), _pin(light, "execute"))

    settled = (then(out_), then(idle), else_(wants), else_(at_fire), then(light))

    # --- the pose follows: lower the stick that is up, then raise ----------------
    ward = get(FIRE_WARD_VAR)
    item = get(WARD_ITEM_VAR)
    up = keep(_node(ed, FN_IS_VALID))
    _connect(item, _pin(up, "Object"))
    other = keep(_node(ed, FN_NEQ_OBJECTS))
    _connect(item, _pin(other, "A"))
    _connect(held, _pin(other, "B"))
    stale = gate2(FN_OR, negate(ward), out(other))
    lower = branch(gate2(FN_AND, out(up), stale), settled)
    back = keep(ed.add_set_member_variable_node("AimPose", ITEM_CLASS_PATH))
    _connect(item, _pin(back, "self"))
    _connect(get(WARD_CARRY_VAR), _pin(back, "AimPose"))
    _connect(then(lower), _pin(back, "execute"))
    # Set with its input unconnected: None.
    clear = put(WARD_ITEM_VAR, None)
    _connect(then(back), _pin(clear, "execute"))
    down = put("NeedsRefresh", "true")
    _connect(then(clear), _pin(down, "execute"))

    # Pure, and read after the lowering above: it sees WardItem cleared.
    raise_ = branch(gate2(FN_AND, ward, negate(out(up))), (then(down), else_(lower)))
    whose = put(WARD_ITEM_VAR, None)
    _connect(held, _pin(whose, WARD_ITEM_VAR))
    _connect(then(raise_), _pin(whose, "execute"))
    carry = put(WARD_CARRY_VAR, None)
    _connect(held_prop("AimPose"), _pin(carry, WARD_CARRY_VAR))
    _connect(then(whose), _pin(carry, "execute"))
    swap = keep(ed.add_set_member_variable_node("AimPose", ITEM_CLASS_PATH))
    _connect(held, _pin(swap, "self"))
    _connect(held_prop(USE_POSE_VAR), _pin(swap, "AimPose"))
    _connect(then(carry), _pin(swap, "execute"))
    rise = put("NeedsRefresh", "true")
    _connect(then(swap), _pin(rise, "execute"))

    ed.add_comment_to_nodes(
        "The use key on a stick (torch.py). A burning one is held out while "
        f"the key is held: {FIRE_WARD_VAR}, written on every arm so it is never "
        "left up. One that is not burning is lit by a press within "
        f"{STICK_LIGHT_RADIUS_CM:g} cm of a campfire, for {STICK_BURN_S:g} s. "
        f"Held out, the stick's AimPose is its {USE_POSE_VAR} "
        f"({WARD_ITEM_VAR} is the stick, {WARD_CARRY_VAR} what to put back), "
        "and each change re-equips, which blends the arm up or down.",
        made)
    return (then(rise), else_(raise_))
