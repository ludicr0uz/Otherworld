"""The node shapes the slot fragments share (slot_sync.py, slot_moves.py):
loops, SlotItems[code], and the rule for what fits where. Pure helpers on
common._G; no fragment of its own.
"""

from combat.graph import BEL, _connect, _loose_pin, _pin, _set
from uebp.graph import out
from combat.nodes import (
    FN_AND, FN_ARR_GET, FN_EQ_II, FN_IS_VALID, FN_LESS_II, FN_NOT, FN_OR,
    MACRO_FOR_EACH, MACRO_FOR_LOOP,
)
from combat.slot_tuning import (
    LONG_GUN, MELEE_SLOT, PRIMARY, SECONDARY, SLOT_COUNT, SLOT_ITEMS_VAR,
    WEAPON_KIND_VAR,
)

FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_LE_II = "/Script/Engine.KismetMathLibrary.LessEqual_IntInt"
FN_NE_II = "/Script/Engine.KismetMathLibrary.NotEqual_IntInt"
FN_NE_OO = "/Script/Engine.KismetMathLibrary.NotEqual_ObjectObject"
FN_ARR_CLEAR = "/Script/Engine.KismetArrayLibrary.Array_Clear"
FN_ARR_RESIZE = "/Script/Engine.KismetArrayLibrary.Array_Resize"
FN_ARR_FIND = "/Script/Engine.KismetArrayLibrary.Array_Find"


def op(g, fn, a, b):
    """A two-input pure node (A, B); returns its ReturnValue."""
    return out(g.call(fn, A=a, B=b))


def not_(g, a):
    return out(g.call(FN_NOT, A=a))


def valid(g, obj):
    return out(g.call(FN_IS_VALID, Object=obj))


def for_each(g, array, execs):
    """ForEachLoop over ``array``: (element, index, body, completed)."""
    loop = g.ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    g.keep(loop)
    _connect(array, _loose_pin(loop, "Array"))
    for e in execs:
        _connect(e, _loose_pin(loop, "Exec"))
    return (_loose_pin(loop, "ArrayElement", is_input=False),
            _loose_pin(loop, "ArrayIndex", is_input=False),
            _loose_pin(loop, "LoopBody", is_input=False),
            _loose_pin(loop, "Completed", is_input=False))


def for_loop(g, first, last, execs):
    """ForLoop first..last (literals): (index, body, completed)."""
    loop = g.ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    g.keep(loop)
    _set(loop, "FirstIndex", first)
    _set(loop, "LastIndex", last)
    for e in execs:
        _connect(e, _pin(loop, "execute"))
    return (_loose_pin(loop, "Index", is_input=False),
            _loose_pin(loop, "LoopBody", is_input=False),
            _loose_pin(loop, "Completed", is_input=False))


def slot_at(g, slot):
    """SlotItems[slot] (an int pin or a literal). Read only with ``slot`` in
    0 .. SLOT_COUNT-1: the sync keeps the array that long."""
    n = g.call(FN_ARR_GET, TargetArray=g.get(SLOT_ITEMS_VAR), Index=slot)
    return _loose_pin(n, "Item", is_input=False)


def fits(g, item, slot):
    """Pure: ``item`` may go in slot ``slot`` (an int pin). The hand and the
    bag take anything; a weapon slot only the weapon whose WeaponKind it is,
    and the secondary a long gun too (slot_tuning.fits is the same rule).
    Reads item.WeaponKind: only call it on a valid item."""
    kind = g.iget(item, WEAPON_KIND_VAR)
    weapon_slot = op(g, FN_AND, op(g, FN_GE_II, slot, PRIMARY), op(g, FN_LE_II, slot, MELEE_SLOT))
    own = op(g, FN_EQ_II, kind, slot)
    second = op(g, FN_AND, op(g, FN_EQ_II, kind, LONG_GUN), op(g, FN_EQ_II, slot, SECONDARY))
    weapon_ok = op(g, FN_OR, own, second)
    allowed = op(g, FN_OR, not_(g, weapon_slot), weapon_ok)
    in_range = op(g, FN_AND, op(g, FN_GE_II, slot, 0), op(g, FN_LESS_II, slot, SLOT_COUNT))
    return op(g, FN_AND, in_range, allowed)
