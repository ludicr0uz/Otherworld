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

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from uebp.graph import out
from combat.nodes import FN_ALL_ACTORS, FN_ARR_ADD, FN_DETACH, MACRO_FOR_EACH
from combat.paths import ITEM_CLASS_PATH
from combat.slot_tuning import HAS_ROOM_VAR, SLOT_VAR, UNPLACED
from combat.weapon_component.common import _prop

ITEM_CAST = "Utilities|Casting|CastToBP_WeaponItem"


def _author_item_candidates(ed, exec_in, x0, y0):
    """Walk every item in the level, offering the ones flagged Dropped.

    Returns (candidate, offered, body, completed): the item of this turn of
    the loop, whether it is offered, and the exec pins each turn and the end
    of the walk leave by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cls = keep(_at(ed.add_get_member_variable_node("ItemClass"), x0 + 780, y0 + 240))
    every = keep(_at(_node(ed, FN_ALL_ACTORS), x0 + 1040, y0))
    _connect(out(cls, "ItemClass"), _pin(every, "ActorClass"))
    _connect(exec_in, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 1320, y0))
    _connect(out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(every), _loose_pin(loop, "Exec"))
    element = _loose_pin(loop, "ArrayElement", is_input=False)

    cast = keep(_at(_palette(ed, ITEM_CAST), x0 + 1620, y0))
    _connect(element, _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    dropped_pin, dropped_n = _prop(ed, "Dropped", item, x0 + 1900, y0 + 260)
    keep(dropped_n)

    ed.add_comment_to_nodes(
        "The items the interact key may pick up: every item in the level "
        "flagged Dropped.",
        made)
    return (item, dropped_pin, BEL.find_then_pin(cast),
            _loose_pin(loop, "Completed", is_input=False))


def _author_take_item(ed, target, exec_in, x0, y1):
    """Take the interact target into the bag, if it is an item and there is room.

    Returns (taken, idle, not_mine): the exec pins a take leaves by, the ones
    a full bag leaves by, and the one a target that is no item leaves by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cast = keep(_at(_palette(ed, ITEM_CAST), x0 + 2080, y1))
    _connect(target, _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    best = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    # Room is a free bag slot or empty hands (the slot sync's HasRoom): with
    # the bag full and something in hand, nothing is picked up.
    fits = keep(_at(ed.add_get_member_variable_node(HAS_ROOM_VAR), x0 + 2340, y1 + 420))
    room = keep(_at(ed.add_branch_node(), x0 + 2580, y1))
    _connect(out(fits, HAS_ROOM_VAR), _pin(room, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(room, "execute"))

    clear = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
                     x0 + 2840, y1))
    _connect(best, _pin(clear, "self"))
    _set(clear, "Dropped", "false")
    _connect(BEL.find_then_pin(room), _pin(clear, "execute"))
    # Off whatever it was left attached to (a blade thrown into a body),
    # staying where it is: the equip puts it in the hand, or hides it.
    loose = keep(_at(_node(ed, FN_DETACH), x0 + 2840, y1 - 200))
    _connect(best, _pin(loose, "self"))
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(loose, rule, "KeepWorld")
    _connect(BEL.find_then_pin(clear), _pin(loose, "execute"))

    inv2 = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 2840, y1 + 300))
    add = keep(_at(_node(ed, FN_ARR_ADD), x0 + 3100, y1))
    _connect(out(inv2, "Inventory"), _pin(add, "TargetArray"))
    _connect(best, _pin(add, "NewItem"))
    _connect(BEL.find_then_pin(loose), _pin(add, "execute"))

    # Where it goes is the slot sync's (slot_sync.py): UNPLACED, it takes
    # the first free bag slot, or the hand if the bag is full. Whatever is
    # in hand stays there.
    place = keep(_at(ed.add_set_member_variable_node(SLOT_VAR, ITEM_CLASS_PATH),
                     x0 + 3360, y1))
    _connect(best, _pin(place, "self"))
    _set(place, SLOT_VAR, UNPLACED)
    _connect(BEL.find_then_pin(add), _pin(place, "execute"))

    ed.add_comment_to_nodes(
        "An interact target that is an item is picked up: taken once, after "
        "the search, while a bag slot or the hand is free (HasRoom), and "
        "detached from whatever it was left in. It goes in UNPLACED: the slot "
        "sync puts it in the bag, or in empty hands when the bag is full.",
        made)
    taken = (BEL.find_then_pin(place),)
    idle = (BEL.find_else_pin(room),)
    return taken, idle, _pin(cast, "CastFailed", is_input=False)
