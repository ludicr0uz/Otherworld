"""The pick-up: what the interact key does to an item lying on the ground.

One of interact.py's kinds, in two halves. _author_item_candidates walks the
level's items and offers the Dropped ones; interact.py keeps the one in reach
nearest AimPoint as InteractTarget. _author_take_item casts that target to an
item and takes it, once, after the search. Standing on a pile, the player
picks the item they are looking at, and a second press takes the next.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import (
    FN_ALL_ACTORS, FN_ARR_ADD, FN_ARR_LEN, FN_IS_VALID, FN_LESS_II, MACRO_FOR_EACH,
)
from combat.paths import ITEM_CLASS_PATH
from combat.tuning import INVENTORY_SIZE
from combat.weapon_component.common import _prop

ITEM_CAST = "Utilities|Casting|CastToBP_WeaponItem"


def _out(node, name):
    return _pin(node, name, is_input=False)


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
    _connect(_out(cls, "ItemClass"), _pin(every, "ActorClass"))
    _connect(exec_in, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 1320, y0))
    _connect(_out(every, "OutActors"), _loose_pin(loop, "Array"))
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

    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 1840, y1 + 420))
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 2100, y1 + 420))
    _connect(_out(inv, "Inventory"), _pin(count, "TargetArray"))
    fits = keep(_at(_node(ed, FN_LESS_II), x0 + 2340, y1 + 420))
    _connect(_out(count, "ReturnValue"), _pin(fits, "A"))
    _set(fits, "B", INVENTORY_SIZE)
    room = keep(_at(ed.add_branch_node(), x0 + 2580, y1))
    _connect(_out(fits, "ReturnValue"), _pin(room, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(room, "execute"))

    clear = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
                     x0 + 2840, y1))
    _connect(best, _pin(clear, "self"))
    _set(clear, "Dropped", "false")
    _connect(BEL.find_then_pin(room), _pin(clear, "execute"))

    inv2 = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 2840, y1 + 300))
    add = keep(_at(_node(ed, FN_ARR_ADD), x0 + 3100, y1))
    _connect(_out(inv2, "Inventory"), _pin(add, "TargetArray"))
    _connect(best, _pin(add, "NewItem"))
    _connect(BEL.find_then_pin(clear), _pin(add, "execute"))

    # A pick-up goes into the bag and whatever is in the hand stays there.
    # Only empty hands take it up: after dropping or eating the last item,
    # Held is None and EquippedIndex may be -1, so nothing would be shown.
    # Array_Add's ReturnValue is the new item's index (an exec node's output,
    # read once).
    held = keep(_at(ed.add_get_member_variable_node("Held"), x0 + 3100, y1 + 300))
    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 3360, y1 + 300))
    _connect(_out(held, "Held"), _pin(armed, "Object"))
    empty = keep(_at(ed.add_branch_node(), x0 + 3360, y1))
    _connect(_out(armed, "ReturnValue"), _pin(empty, "Condition"))
    _connect(BEL.find_then_pin(add), _pin(empty, "execute"))
    at = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 3620, y1 + 120))
    _connect(_out(add, "ReturnValue"), _pin(at, "EquippedIndex"))
    _connect(BEL.find_else_pin(empty), _pin(at, "execute"))

    ed.add_comment_to_nodes(
        "An interact target that is an item is picked up: taken once, after "
        f"the search, while fewer than {INVENTORY_SIZE} are carried. It goes "
        "into the inventory without switching to it: the held item stays "
        "held. Only empty hands (Held is None) take it up.",
        made)
    taken = (BEL.find_then_pin(empty), BEL.find_then_pin(at))
    idle = (BEL.find_else_pin(room),)
    return taken, idle, _pin(cast, "CastFailed", is_input=False)
