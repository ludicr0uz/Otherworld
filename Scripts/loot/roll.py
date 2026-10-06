"""BP_HealthComponent's side of corpse loot: its loot variables, and the roll
that fills a body's Loot when a wanderer is killed.

    ForLoop i over LootTable:
        RandomFloat < LootChances[i]  ->  Loot += LootTable[i]
                                          LootNames += LootTableNames[i]
                                          LootIcons += LootTableIcons[i]
                                          LootTints += LootTableTints[i]

Spliced after the gun drop on the DamagedByPlayer arm (combat/death.py), so
only a counted kill fills a body: the world-floor net kills the same way, and
a wanderer the terrain swallowed was not killed. The items stay classes until
the player takes one (combat/weapon_component/loot_take.py spawns it), so a body holds
no hidden actors and nothing is left over when its lifespan ends.
"""

import unreal

from uebp.graph import (
    BEL, _connect, _declare, _float_type, _node, _pin, _struct_type, out, then)
from loot.consts import (
    LOOT_ARRAYS, LOOT_CHANCES_VAR, LOOT_ICONS_VAR, LOOT_NAMES_VAR, LOOT_TABLE_ICONS_VAR,
    LOOT_TABLE_NAMES_VAR, LOOT_TABLE_TINTS_VAR, LOOT_TABLE_VAR, LOOT_TINTS_VAR, LOOT_VAR,
)
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_GET, FN_ARR_LEN
from uebp.nodes.math import FN_LESS_FF, FN_RANDOM_UNIT, FN_SUB_II
from uebp.nodes.palette import MACRO_FOR_LOOP


def declare_loot_vars(ed):
    """The table (filled by loot/install.py) and the body's contents. The
    classes are class-of-Actor, for DropClasses' reason: this component
    compiles before any item it names exists."""
    item = BEL.get_class_reference_type(unreal.Actor.static_class())
    text = BEL.get_basic_type_by_name("string")
    icon = BEL.get_object_reference_type(unreal.Texture2D.static_class())
    tint = _struct_type(unreal.LinearColor.static_struct())
    for name, kind in ((LOOT_TABLE_VAR, item), (LOOT_CHANCES_VAR, _float_type()),
                       (LOOT_TABLE_NAMES_VAR, text), (LOOT_VAR, item),
                       (LOOT_NAMES_VAR, text), (LOOT_TABLE_ICONS_VAR, icon),
                       (LOOT_ICONS_VAR, icon), (LOOT_TABLE_TINTS_VAR, tint),
                       (LOOT_TINTS_VAR, tint)):
        _declare(ed, name, BEL.get_array_type(kind))


def _get(ed, var, made):
    n = ed.add_get_member_variable_node(var)
    made.append(n)
    return out(n, var)


def _element(ed, var, index, made):
    n = _node(ed, FN_ARR_GET)
    made.append(n)
    _connect(_get(ed, var, made), _pin(n, "TargetArray"))
    _connect(index, _pin(n, "Index"))
    return out(n, "Item")


def _append(ed, var, item, exec_in, made):
    n = _node(ed, FN_ARR_ADD)
    made.append(n)
    _connect(_get(ed, var, made), _pin(n, "TargetArray"))
    _connect(item, _pin(n, "NewItem"))
    _connect(exec_in, _pin(n, "execute"))
    return then(n)


def author_loot_roll(ed, exec_ins):
    """The roll (see the module docstring). Returns the exec pin after it.

    RandomFloat is pure, so the Branch pulls exactly one draw per entry. An
    empty table (a build where install.py has not run) loops zero times.
    """
    made = []
    size = _node(ed, FN_ARR_LEN)
    made.append(size)
    _connect(_get(ed, LOOT_TABLE_VAR, made), _pin(size, "TargetArray"))
    last = _node(ed, FN_SUB_II)
    made.append(last)
    _connect(out(size), _pin(last, "A"))
    _pin(last, "B").set_pin_value("1")

    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    loop
    made.append(loop)
    _pin(loop, "FirstIndex").set_pin_value("0")
    _connect(out(last), _pin(loop, "LastIndex"))
    for e in exec_ins:
        _connect(e, _pin(loop, "execute"))
    i = out(loop, "Index")

    draw = _node(ed, FN_RANDOM_UNIT)
    lucky = _node(ed, FN_LESS_FF)
    made += [draw, lucky]
    _connect(out(draw), _pin(lucky, "A"))
    _connect(_element(ed, LOOT_CHANCES_VAR, i, made), _pin(lucky, "B"))
    carried = ed.add_branch_node()
    made.append(carried)
    _connect(out(lucky), _pin(carried, "Condition"))
    _connect(out(loop, "LoopBody"), _pin(carried, "execute"))

    flow = then(carried)
    for table, body in LOOT_ARRAYS:
        flow = _append(ed, body, _element(ed, table, i, made), flow, made)
    ed.add_comment_to_nodes(
        "Corpse loot: each LootTable entry is rolled once per counted kill "
        "(RandomFloat < LootChances[i]) and, on a hit, goes into Loot (with its "
        "name, icon and tint), which the HUD's loot window shows. Filled by "
        "loot/install.py.", made)
    return out(loop, "Completed")
