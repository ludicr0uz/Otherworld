"""The node shapes the slot fragments share (slot_sync.py, slot_moves.py):
loops, SlotItems[code], and the rule for what fits where. Pure helpers on
common._G; no fragment of its own.
"""

from combat.graph import BEL, _connect, _loose_pin, _pin, _set
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


def out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def then(n):
    return BEL.find_then_pin(n)


def op(g, fn, a, b, x, y):
    """A two-input pure node (A, B); returns its ReturnValue."""
    return out(g.call(fn, x, y, A=a, B=b))


def not_(g, a, x, y):
    return out(g.call(FN_NOT, x, y, A=a))


def valid(g, obj, x, y):
    return out(g.call(FN_IS_VALID, x, y, Object=obj))


def for_each(g, array, execs, x, y):
    """ForEachLoop over ``array``: (element, index, body, completed)."""
    loop = g.ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    g.keep(loop, x, y)
    _connect(array, _loose_pin(loop, "Array"))
    for e in execs:
        _connect(e, _loose_pin(loop, "Exec"))
    return (_loose_pin(loop, "ArrayElement", is_input=False),
            _loose_pin(loop, "ArrayIndex", is_input=False),
            _loose_pin(loop, "LoopBody", is_input=False),
            _loose_pin(loop, "Completed", is_input=False))


def for_loop(g, first, last, execs, x, y):
    """ForLoop first..last (literals): (index, body, completed)."""
    loop = g.ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    g.keep(loop, x, y)
    _set(loop, "FirstIndex", first)
    _set(loop, "LastIndex", last)
    for e in execs:
        _connect(e, _pin(loop, "execute"))
    return (_loose_pin(loop, "Index", is_input=False),
            _loose_pin(loop, "LoopBody", is_input=False),
            _loose_pin(loop, "Completed", is_input=False))


def slot_at(g, slot, x, y):
    """SlotItems[slot] (an int pin or a literal). Read only with ``slot`` in
    0 .. SLOT_COUNT-1: the sync keeps the array that long."""
    n = g.call(FN_ARR_GET, x, y, TargetArray=g.get(SLOT_ITEMS_VAR, x - 240, y), Index=slot)
    return _loose_pin(n, "Item", is_input=False)


def fits(g, item, slot, x, y):
    """Pure: ``item`` may go in slot ``slot`` (an int pin). The hand and the
    bag take anything; a weapon slot only the weapon whose WeaponKind it is,
    and the secondary a long gun too (slot_tuning.fits is the same rule).
    Reads item.WeaponKind: only call it on a valid item."""
    kind = g.iget(item, WEAPON_KIND_VAR, x, y + 300)
    weapon_slot = op(g, FN_AND, op(g, FN_GE_II, slot, PRIMARY, x + 260, y),
                     op(g, FN_LE_II, slot, MELEE_SLOT, x + 260, y + 140), x + 520, y)
    own = op(g, FN_EQ_II, kind, slot, x + 260, y + 300)
    second = op(g, FN_AND, op(g, FN_EQ_II, kind, LONG_GUN, x + 260, y + 440),
                op(g, FN_EQ_II, slot, SECONDARY, x + 260, y + 580), x + 520, y + 440)
    weapon_ok = op(g, FN_OR, own, second, x + 780, y + 300)
    allowed = op(g, FN_OR, not_(g, weapon_slot, x + 780, y), weapon_ok, x + 1040, y)
    in_range = op(g, FN_AND, op(g, FN_GE_II, slot, 0, x + 780, y + 600),
                  op(g, FN_LESS_II, slot, SLOT_COUNT, x + 780, y + 740), x + 1040, y + 600)
    return op(g, FN_AND, in_range, allowed, x + 1300, y)
