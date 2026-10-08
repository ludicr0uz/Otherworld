"""The use key's one kind so far: a stick that Burns (stick.py).

    Using --> Held.Lit --> FireWard = true          the fire is held out
              not Lit  --> FireWard = false
                           UsePressed AND Held.Burns --> Server_Kindle()
    not Using --> FireWard = false

    Server_Kindle, a reliable Server event (task M25, combat/fire_vars.py; in
    single player a plain call). Alive, this machine's Held Burns, not Lit:
        NearFire = any CampfireClass actor within STICK_LIGHT_RADIUS_CM of
                   this machine's copy of the player
        NearFire: Held.BurnOutTime = now + burn, Held.Lit = true

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

from net.guard import author_guard
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.fire_vars import SERVER_KINDLE
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.paths import FIRE_WARD_VAR, ITEM_CLASS_PATH
from combat.torch_tuning import (
    BURN_OUT_VAR, BURNS_VAR, LIT_VAR, NEAR_FIRE_VAR, STICK_BURN_S,
    STICK_LIGHT_RADIUS_CM, USE_POSE_VAR, WARD_CARRY_VAR, WARD_ITEM_VAR,
)
from combat.use_tuning import USE_PRESSED_VAR, USING_VAR
from combat.weapon_component.common import _prop
from combat.weapon_component.shot import _author_alive
from combat.weapon_component.slot_nodes import for_each, not_, op, valid
from uebp import net
from uebp.g import _G
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_OWNER
from uebp.nodes.math import FN_ADD_FF, FN_AND, FN_DISTANCE, FN_LE_FF, FN_NE_OO, FN_NOT, FN_OR
from uebp.nodes.system import FN_ALL_ACTORS, FN_IS_VALID, FN_TIME_SECONDS
from combat import item_vars as IV
from combat.weapon_component import vars as WV


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

    # --- not burning: a press asks the server to light it at a campfire -------
    wants = branch(gate2(FN_AND, get(USE_PRESSED_VAR), held_prop(BURNS_VAR)), (then(unlit),))
    ask = keep(_node(ed, SERVER_KINDLE))
    _connect(then(wants), _pin(ask, "execute"))

    settled = (then(out_), then(idle), else_(wants), then(ask))

    # --- the pose follows: lower the stick that is up, then raise ----------------
    ward = get(FIRE_WARD_VAR)
    item = get(WARD_ITEM_VAR)
    up = keep(_node(ed, FN_IS_VALID))
    _connect(item, _pin(up, "Object"))
    other = keep(_node(ed, FN_NE_OO))
    _connect(item, _pin(other, "A"))
    _connect(held, _pin(other, "B"))
    stale = gate2(FN_OR, negate(ward), out(other))
    lower = branch(gate2(FN_AND, out(up), stale), settled)
    back = keep(ed.add_set_member_variable_node(IV.AimPose, ITEM_CLASS_PATH))
    _connect(item, _pin(back, "self"))
    _connect(get(WARD_CARRY_VAR), _pin(back, IV.AimPose))
    _connect(then(lower), _pin(back, "execute"))
    # Set with its input unconnected: None.
    clear = put(WARD_ITEM_VAR, None)
    _connect(then(back), _pin(clear, "execute"))
    down = put(WV.NeedsRefresh, "true")
    _connect(then(clear), _pin(down, "execute"))

    # Pure, and read after the lowering above: it sees WardItem cleared.
    raise_ = branch(gate2(FN_AND, ward, negate(out(up))), (then(down), else_(lower)))
    whose = put(WARD_ITEM_VAR, None)
    _connect(held, _pin(whose, WARD_ITEM_VAR))
    _connect(then(raise_), _pin(whose, "execute"))
    carry = put(WARD_CARRY_VAR, None)
    _connect(held_prop(IV.AimPose), _pin(carry, WARD_CARRY_VAR))
    _connect(then(whose), _pin(carry, "execute"))
    swap = keep(ed.add_set_member_variable_node(IV.AimPose, ITEM_CLASS_PATH))
    _connect(held, _pin(swap, "self"))
    _connect(held_prop(USE_POSE_VAR), _pin(swap, IV.AimPose))
    _connect(then(carry), _pin(swap, "execute"))
    rise = put(WV.NeedsRefresh, "true")
    _connect(then(swap), _pin(rise, "execute"))

    ed.add_comment_to_nodes(
        "The use key on a stick (torch.py). A burning one is held out while "
        f"the key is held: {FIRE_WARD_VAR}, written on every arm so it is never "
        "left up. A press with one that is not burning asks the server to "
        f"light it ({SERVER_KINDLE}). "
        f"Held out, the stick's AimPose is its {USE_POSE_VAR} "
        f"({WARD_ITEM_VAR} is the stick, {WARD_CARRY_VAR} what to put back), "
        "and each change re-equips, which blends the arm up or down.",
        made)
    return (then(rise), else_(raise_))


def author_kindle_event(ed):
    """Server_Kindle(): the press that lights a stick, on the machine that
    owns it. Refused unless the owner is alive, its own Held Burns and is not
    Lit, and a campfire stands within STICK_LIGHT_RADIUS_CM of this machine's
    copy of the owner. Before the Tick, which calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, SERVER_KINDLE))
    go, _refused = author_guard(g, SERVER_KINDLE, [then(event)])
    alive = _author_alive(g, [go])
    held = g.get(WV.Held)
    armed, _bare = g.branch(valid(g, held), alive)
    unlit = op(g, FN_AND, g.iget(held, BURNS_VAR), not_(g, g.iget(held, LIT_VAR)))
    wants, _no = g.branch(unlit, [armed])

    forget = g.put(NEAR_FIRE_VAR, "false", [wants])
    every = g.call(FN_ALL_ACTORS, [forget], ActorClass=g.get(CAMPFIRE_CLASS_VAR))
    fire, _i, body, done = for_each(g, out(every, "OutActors"), [then(every)])
    here = g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER)))
    gap = g.call(FN_DISTANCE, V1=out(g.call(FN_ACTOR_LOC, self=fire)), V2=out(here))
    close = g.call(FN_LE_FF, A=out(gap))
    _set(close, "B", STICK_LIGHT_RADIUS_CM)
    near, _far = g.branch(out(close), [body])
    g.put(NEAR_FIRE_VAR, "true", [near])

    at_fire, _none = g.branch(g.get(NEAR_FIRE_VAR), [done])
    until = g.call(FN_ADD_FF, A=out(g.call(FN_TIME_SECONDS)))
    _set(until, "B", STICK_BURN_S)
    burn = g.iput(held, BURN_OUT_VAR, out(until), [at_fire])
    g.iput(held, LIT_VAR, "true", [burn])
    ed.add_comment_to_nodes(
        f"{SERVER_KINDLE} (torch.py): the owning client's use key on a stick. "
        "Refused unless the owner is alive, this machine's Held Burns and is "
        f"not burning, and a campfire stands within {STICK_LIGHT_RADIUS_CM:g} cm "
        f"of this machine's copy of the owner; then it is Lit for {STICK_BURN_S:g} s, "
        "on the item's own clock (stick.py). The owner's copy is told by the "
        "record, everyone else by HandLit (record.py).", g.made)
