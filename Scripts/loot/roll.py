"""BP_HealthComponent's side of corpse loot: its loot variables, and the roll
that fills a body's Loot when a wanderer is killed.

    ForLoop i over LootTable:
        RandomFloat < LootChances[i]  ->  Loot += LootTable[i]
                                          LootNames += LootTableNames[i]

Spliced after the gun drop on the DamagedByPlayer arm (combat/death.py), so
only a counted kill fills a body: the world-floor net kills the same way, and
a wanderer the terrain swallowed was not killed. The items stay classes until
the player takes one (graphics_menu/loot_take.py spawns it), so a body holds
no hidden actors and nothing is left over when its lifespan ends.
"""

import unreal

from combat.graph import BEL, _at, _connect, _declare, _float_type, _node, _pin
from combat.nodes import (
    FN_ARR_ADD, FN_ARR_GET, FN_ARR_LEN, FN_LESS_FF, FN_SUB_II, MACRO_FOR_LOOP,
)
from loot.consts import (
    LOOT_CHANCES_VAR, LOOT_NAMES_VAR, LOOT_TABLE_NAMES_VAR, LOOT_TABLE_VAR, LOOT_VAR,
)

FN_RANDOM_UNIT = "/Script/Engine.KismetMathLibrary.RandomFloat"


def declare_loot_vars(ed):
    """The table (filled by loot/install.py) and the body's contents. The
    classes are class-of-Actor, for DropClasses' reason: this component
    compiles before any item it names exists."""
    item = BEL.get_class_reference_type(unreal.Actor.static_class())
    text = BEL.get_basic_type_by_name("string")
    for name, kind in ((LOOT_TABLE_VAR, item), (LOOT_CHANCES_VAR, _float_type()),
                       (LOOT_TABLE_NAMES_VAR, text), (LOOT_VAR, item),
                       (LOOT_NAMES_VAR, text)):
        _declare(ed, name, BEL.get_array_type(kind))


def _get(ed, var, x, y, made):
    n = _at(ed.add_get_member_variable_node(var), x, y)
    made.append(n)
    return _pin(n, var, is_input=False)


def _element(ed, var, index, x, y, made):
    n = _at(_node(ed, FN_ARR_GET), x, y)
    made.append(n)
    _connect(_get(ed, var, x - 240, y, made), _pin(n, "TargetArray"))
    _connect(index, _pin(n, "Index"))
    return _pin(n, "Item", is_input=False)


def _append(ed, var, item, exec_in, x, y, made):
    n = _at(_node(ed, FN_ARR_ADD), x, y)
    made.append(n)
    _connect(_get(ed, var, x - 240, y + 200, made), _pin(n, "TargetArray"))
    _connect(item, _pin(n, "NewItem"))
    _connect(exec_in, _pin(n, "execute"))
    return BEL.find_then_pin(n)


def author_loot_roll(ed, exec_ins, x0, y0):
    """The roll (see the module docstring). Returns the exec pin after it.

    RandomFloat is pure, so the Branch pulls exactly one draw per entry. An
    empty table (a build where install.py has not run) loops zero times.
    """
    made = []
    size = _at(_node(ed, FN_ARR_LEN), x0, y0 + 300)
    made.append(size)
    _connect(_get(ed, LOOT_TABLE_VAR, x0 - 240, y0 + 300, made), _pin(size, "TargetArray"))
    last = _at(_node(ed, FN_SUB_II), x0 + 240, y0 + 300)
    made.append(last)
    _connect(_pin(size, "ReturnValue", is_input=False), _pin(last, "A"))
    _pin(last, "B").set_pin_value("1")

    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    _at(loop, x0 + 480, y0)
    made.append(loop)
    _pin(loop, "FirstIndex").set_pin_value("0")
    _connect(_pin(last, "ReturnValue", is_input=False), _pin(loop, "LastIndex"))
    for e in exec_ins:
        _connect(e, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)

    draw = _at(_node(ed, FN_RANDOM_UNIT), x0 + 760, y0 + 300)
    lucky = _at(_node(ed, FN_LESS_FF), x0 + 1000, y0 + 300)
    made += [draw, lucky]
    _connect(_pin(draw, "ReturnValue", is_input=False), _pin(lucky, "A"))
    _connect(_element(ed, LOOT_CHANCES_VAR, i, x0 + 760, y0 + 460, made), _pin(lucky, "B"))
    carried = _at(ed.add_branch_node(), x0 + 1240, y0)
    made.append(carried)
    _connect(_pin(lucky, "ReturnValue", is_input=False), _pin(carried, "Condition"))
    _connect(_pin(loop, "LoopBody", is_input=False), _pin(carried, "execute"))

    flow = _append(ed, LOOT_VAR, _element(ed, LOOT_TABLE_VAR, i, x0 + 1240, y0 + 460, made),
                   BEL.find_then_pin(carried), x0 + 1500, y0, made)
    _append(ed, LOOT_NAMES_VAR,
            _element(ed, LOOT_TABLE_NAMES_VAR, i, x0 + 1500, y0 + 660, made),
            flow, x0 + 1760, y0, made)
    ed.add_comment_to_nodes(
        "Corpse loot: each LootTable entry is rolled once per counted kill "
        "(RandomFloat < LootChances[i]) and, on a hit, goes into Loot/LootNames, "
        "which the HUD's loot window lists. Filled by loot/install.py.", made)
    return _pin(loop, "Completed", is_input=False)
