"""The pick-up: what the interact key does to an item lying on the ground.

One of interact.py's kinds, in two halves. _author_item_candidates walks the
level's items and offers the Dropped ones; interact.py keeps the one in reach
nearest AimPoint as InteractTarget. _author_take_item casts that target to an
item and asks for it, once, after the search. Standing on a pile, the player
picks the item they are looking at, and a second press takes the next.

The take itself is a server request (task M20, combat/strike_vars.py):
Server_Take(Item), which checks the item is still Dropped and in reach of the
server's copy of the taker. The item has to be one the server can be told
of, and every item in the world is: thrown, set down, placed in the level
or left by a kill, it is a replicated actor (item_world.py; task M23). A
client's own picture of what it carries arrives as nothing on a server and
is refused. In single player the event is a plain call.

A pick-up is not always lying loose: a thrown blade is left attached to the
body it struck (throw_strike.py). The take detaches what it takes, so an item
that goes into the bag unseen does not ride on with the body.

Where a taken item goes is the slot sync's (UNPLACED: a weapon to a free
weapon slot of its kind, anything else to the bag), but for one case: a blade
taken back out of what it was thrown into (the item is Lodged), with empty
hands, goes to the hand (_author_to_hand).
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from combat.paths import ITEM_CLASS_PATH
from combat.slot_tuning import HAND, HAND_FROM_VAR, HAS_ROOM_VAR, SLOT_VAR, UNPLACED, WEAPON_KIND_VAR
from combat.weapon_component.common import _prop
from combat.item_world import author_out_of_world
from combat.strike_vars import ITEM_PARAM, SERVER_TAKE, TAKE_PARAMS, TAKE_REACH_CM
from combat.weapon_component.shot import _author_alive
from combat.weapon_component.slot_nodes import op, valid
from uebp import net
from uebp.nodes.actor import FN_ACTOR_LOC, FN_DETACH, FN_GET_OWNER
from uebp.nodes.array import FN_ARR_ADD
from uebp.g import _G
from uebp.nodes.math import FN_AND, FN_DISTANCE, FN_LE_FF, FN_NOT
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import FN_IS_VALID
from uebp.nodes.system import FN_ALL_ACTORS
from combat import item_vars as IV
from combat.weapon_component import vars as WV

ITEM_CAST = "Utilities|Casting|CastToBP_WeaponItem"


def _author_item_candidates(ed, exec_in):
    """Walk every item in the level, offering the ones flagged Dropped.

    Returns (candidate, offered, body, completed): the item of this turn of
    the loop, whether it is offered, and the exec pins each turn and the end
    of the walk leave by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cls = keep(ed.add_get_member_variable_node(WV.ItemClass))
    every = keep(_node(ed, FN_ALL_ACTORS))
    _connect(out(cls, WV.ItemClass), _pin(every, "ActorClass"))
    _connect(exec_in, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(loop)
    _connect(out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(then(every), _loose_pin(loop, "Exec"))
    element = _loose_pin(loop, "ArrayElement", is_input=False)

    cast = keep(_palette(ed, ITEM_CAST))
    _connect(element, _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    dropped_pin, dropped_n = _prop(ed, IV.Dropped, item)
    keep(dropped_n)

    ed.add_comment_to_nodes(
        "The items the interact key may pick up: every item in the level "
        "flagged Dropped.",
        made)
    return (item, dropped_pin, then(cast), _loose_pin(loop, "Completed", is_input=False))


def _author_take_item(ed, target, exec_in):
    """E on an item, where the keys are: ask the server to take the interact
    target, if it is an item and this copy has room for one.

    Returns (asked, idle, not_mine): the exec pins an ask leaves by, the ones
    a full bag leaves by, and the one a target that is no item leaves by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cast = keep(_palette(ed, ITEM_CAST))
    _connect(target, _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    best = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    # Room is a free bag slot or empty hands (the slot sync's HasRoom): with
    # the bag full and something in hand, nothing is asked for.
    fits = keep(ed.add_get_member_variable_node(HAS_ROOM_VAR))
    room = keep(ed.add_branch_node())
    _connect(out(fits, HAS_ROOM_VAR), _pin(room, "Condition"))
    _connect(then(cast), _pin(room, "execute"))
    ask = keep(_node(ed, SERVER_TAKE))
    _connect(best, _pin(ask, ITEM_PARAM))
    _connect(then(room), _pin(ask, "execute"))
    ed.add_comment_to_nodes(
        "An interact target that is an item is asked for, once, after the "
        f"search, while this copy has room ({SERVER_TAKE}, pickup.py). The take "
        "is the server's; with authority (single player) the event is the take.",
        made)
    return (then(ask),), (else_(room),), out(cast, "CastFailed")


def author_take_event(ed):
    """Server_Take(Item): the take, on the machine that owns the inventory.
    Refused unless the item is there, the taker alive, the item Dropped and
    within TAKE_REACH_CM of this machine's copy of the taker, and a bag slot
    or the hand free. Two players reaching for one item: the first ask finds
    it Dropped, the second does not. Before the Tick, which calls it by
    name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, SERVER_TAKE, TAKE_PARAMS))
    best = out(event, ITEM_PARAM)
    there, _gone = g.branch(valid(g, best), [then(event)])
    alive = _author_alive(g, [there])
    here = g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER)))
    near = op(g, FN_LE_FF,
              out(g.call(FN_DISTANCE, V1=out(g.call(FN_ACTOR_LOC, self=best)), V2=out(here))),
              str(TAKE_REACH_CM))
    free = op(g, FN_AND, op(g, FN_AND, g.iget(best, IV.Dropped), near), g.get(HAS_ROOM_VAR))
    take, _refused = g.branch(free, alive)

    flow = g.iput(best, IV.Dropped, "false", [take])
    # Out of the world: each client's copy of it goes (item_world.py).
    flow = author_out_of_world(ed, best, [flow])
    # Off whatever it was left attached to (a blade thrown into a body),
    # staying where it is: the equip puts it in the hand, or hides it.
    loose = g.call(FN_DETACH, [flow], self=best)
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(loose, rule, "KeepWorld")
    add = g.call(FN_ARR_ADD, [then(loose)], TargetArray=g.get(WV.Inventory), NewItem=best)
    # Where it goes is the slot sync's (slot_sync.py): UNPLACED, it takes
    # the first free bag slot, or the hand if the bag is full. Whatever is
    # in hand stays there.
    flow = g.iput(best, SLOT_VAR, str(UNPLACED), [then(add)])
    taken, hand_nodes = _author_to_hand(ed, best, flow)
    g.put(WV.NeedsRefresh, "true", taken)
    ed.add_comment_to_nodes(
        f"{SERVER_TAKE} (pickup.py): the owning client's E on an item. Refused "
        "unless the item is there and Dropped, the taker alive and within "
        f"{TAKE_REACH_CM:g} cm of it on this machine, and a bag slot or the hand "
        "free. Then it is taken: detached from whatever it was left in, into "
        "Inventory UNPLACED (the slot sync puts a weapon in a free weapon slot "
        "of its kind, anything else in the bag, or in empty hands when the bag "
        "is full). A blade taken back out of what it was thrown into (Lodged) "
        "with empty hands goes to the hand instead.",
        g.made + hand_nodes)


def _author_to_hand(ed, item, exec_in):
    """A Lodged item (a blade thrown into a tree or a body) taken with empty
    hands goes to the hand: Slot = HAND, over the UNPLACED the take wrote.
    HandFrom is its WeaponKind, so the melee slot's key puts it away as if
    it had come from there. Lodged is lowered either way.

    Held is last frame's equip: a clash with something that reached the
    hand this frame is the slot sync's (the later claim goes UNPLACED).
    Returns (tails, nodes).
    """
    g = _G(ed, ITEM_CLASS_PATH)
    stuck, loose = g.branch(g.iget(item, IV.Lodged), [exec_in])
    flow = g.iput(item, IV.Lodged, "false", [stuck])
    bare = out(g.call(FN_NOT, A=out(g.call(FN_IS_VALID, Object=g.get(WV.Held)))))
    empty, busy = g.branch(bare, [flow])
    flow = g.iput(item, SLOT_VAR, str(HAND), [empty])
    flow = g.put(HAND_FROM_VAR, g.iget(item, WEAPON_KIND_VAR), [flow])
    return (loose, busy, flow), g.made
