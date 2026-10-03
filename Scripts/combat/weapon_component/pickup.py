"""The pick-up: what the interact key does to an item lying on the ground.

One of interact.py's kinds, in two halves. _author_item_candidates walks the
level's items and offers the Dropped ones; interact.py keeps the one in reach
nearest AimPoint as InteractTarget. _author_take_item casts that target to an
item and takes it, once, after the search. Standing on a pile, the player
picks the item they are looking at, and a second press takes the next.

A pick-up is not always lying loose: a thrown blade is left attached to the
body it struck (throw_strike.py). The take detaches what it takes, so an item
that goes into the bag unseen does not ride on with the body.
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from combat.paths import ITEM_CLASS_PATH
from combat.slot_tuning import HAS_ROOM_VAR, SLOT_VAR, UNPLACED
from combat.weapon_component.common import _prop
from uebp.nodes.actor import FN_DETACH
from uebp.nodes.array import FN_ARR_ADD
from uebp.nodes.palette import MACRO_FOR_EACH
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
    """Take the interact target into the bag, if it is an item and there is room.

    Returns (taken, idle, not_mine): the exec pins a take leaves by, the ones
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
    # the bag full and something in hand, nothing is picked up.
    fits = keep(ed.add_get_member_variable_node(HAS_ROOM_VAR))
    room = keep(ed.add_branch_node())
    _connect(out(fits, HAS_ROOM_VAR), _pin(room, "Condition"))
    _connect(then(cast), _pin(room, "execute"))

    clear = keep(ed.add_set_member_variable_node(IV.Dropped, ITEM_CLASS_PATH))
    _connect(best, _pin(clear, "self"))
    _set(clear, IV.Dropped, False)
    _connect(then(room), _pin(clear, "execute"))
    # Off whatever it was left attached to (a blade thrown into a body),
    # staying where it is: the equip puts it in the hand, or hides it.
    loose = keep(_node(ed, FN_DETACH))
    _connect(best, _pin(loose, "self"))
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(loose, rule, "KeepWorld")
    _connect(then(clear), _pin(loose, "execute"))

    inv2 = keep(ed.add_get_member_variable_node(WV.Inventory))
    add = keep(_node(ed, FN_ARR_ADD))
    _connect(out(inv2, WV.Inventory), _pin(add, "TargetArray"))
    _connect(best, _pin(add, "NewItem"))
    _connect(then(loose), _pin(add, "execute"))

    # Where it goes is the slot sync's (slot_sync.py): UNPLACED, it takes
    # the first free bag slot, or the hand if the bag is full. Whatever is
    # in hand stays there.
    place = keep(ed.add_set_member_variable_node(SLOT_VAR, ITEM_CLASS_PATH))
    _connect(best, _pin(place, "self"))
    _set(place, SLOT_VAR, UNPLACED)
    _connect(then(add), _pin(place, "execute"))

    ed.add_comment_to_nodes(
        "An interact target that is an item is picked up: taken once, after "
        "the search, while a bag slot or the hand is free (HasRoom), and "
        "detached from whatever it was left in. It goes in UNPLACED: the slot "
        "sync puts it in the bag, or in empty hands when the bag is full.",
        made)
    taken = (then(place),)
    idle = (else_(room),)
    return taken, idle, out(cast, "CastFailed")
