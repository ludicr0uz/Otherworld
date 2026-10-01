"""The dev-all-guns cheat: the HUD Tick fragment behind the M panel's dev-all-guns row.

    the row taken (PauseClick) -> DevAllGunsRequested = true
    DevAllGunsRequested        -> false, then for each gun class, in order:
        DevHasGun = false
        ForEach Inventory: GetObjectClass(item) == gun -> DevHasGun = true
        not DevHasGun AND Inventory has room
            -> spawn the gun at the pawn, cast, Dropped = false, Inventory += it
    then NeedsRefresh, so the weapon component re-equips what it holds and
    hides the rest -- the held item stays held, as with a pick-up.

A gun already carried is skipped, so pressing it twice adds nothing, and the
INVENTORY_SIZE slots the HUD draws are never overflowed. The key only raises
the request, which is what lets a probe ask for the guns without a key press
(probes/probe_dev_all_guns.py).
"""

import unreal

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import FN_OBJECT_CLASS, MACRO_FOR_EACH, NODE_CAST_ITEM, NODE_SPAWN
from combat.paths import ITEM_BP_PATH, ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import INVENTORY_SIZE
from graphics_menu.dev_consts import (
    DEV_GUN_CLASS_PATHS, DEV_GUNS_ACTION, DEV_GUNS_REQUEST_VAR, DEV_HAS_GUN_VAR,
)
from graphics_menu.menu_nav import pause_row_taken
from graphics_menu.player_parts import PAWN

FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_LESS_II = "/Script/Engine.KismetMathLibrary.Less_IntInt"
FN_CLASS_EQ = "/Script/Engine.KismetMathLibrary.EqualEqual_ClassClass"
FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_GET_TRANSFORM = "/Script/Engine.Actor.GetTransform"

_VARS = (DEV_GUNS_REQUEST_VAR, DEV_HAS_GUN_VAR)


def declare_dev_guns_vars(ed):
    """The HUD's two bools. Defaults: dev_guns_defaults()."""
    for name in _VARS:
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name("bool")):
            raise RuntimeError(f"could not declare member variable {name}")


def dev_guns_defaults():
    return {n: False for n in _VARS}


def _class_literal(node, pin_name, class_path):
    """A class pin's literal. _set compares strings, and a class pin reads back
    as the object path, so check it landed by the path instead."""
    pin = _pin(node, pin_name)
    pin.set_pin_value(class_path)
    got = str(pin.get_pin_value())
    if class_path.rsplit(".", 1)[1] not in got:
        raise RuntimeError(f"class pin {pin_name!r} would not take {class_path!r}: {got!r}")


def _setter(ed, var, value, in_execs, x, y, made, owner=None, self_out=None):
    n = _at(ed.add_set_member_variable_node(var, owner) if owner
            else ed.add_set_member_variable_node(var), x, y)
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    _set(n, var, value)
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    made.append(n)
    return BEL.find_then_pin(n)


def _get(ed, var, x, y, made, owner=None, self_out=None):
    n = _at(ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var), x, y)
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    made.append(n)
    return _pin(n, var, is_input=False)


def _call(ed, fn, x, y, made, **inputs):
    n = _at(_node(ed, fn), x, y)
    for name, v in inputs.items():
        if isinstance(v, (str, int, float)):
            _set(n, name, v)
        else:
            _connect(v, _pin(n, name))
    made.append(n)
    return n


def _out(n):
    return _pin(n, "ReturnValue", is_input=False)


def _branch(ed, cond, in_execs, x, y, made):
    br = _at(ed.add_branch_node(), x, y)
    _connect(cond, _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    made.append(br)
    return BEL.find_then_pin(br), BEL.find_else_pin(br)


def _author_give_one(ed, gun, wc, pawn_out, in_execs, x0, y0, made):
    """One gun class: skipped if carried or the bag is full, else spawned and
    carried. Returns the exec tails."""
    flow = _setter(ed, DEV_HAS_GUN_VAR, "false", in_execs, x0, y0, made)
    inv = _get(ed, "Inventory", x0, y0 + 300, made, WEAPON_COMP_CLASS_PATH, wc)
    loop = _at(ed.add_macro_node(MACRO_FOR_EACH), x0 + 260, y0)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(inv, _loose_pin(loop, "Array"))
    _connect(flow, _loose_pin(loop, "Exec"))
    cls = _call(ed, FN_OBJECT_CLASS, x0 + 560, y0 + 300, made,
                Object=_loose_pin(loop, "ArrayElement", is_input=False))
    same = _call(ed, FN_CLASS_EQ, x0 + 800, y0 + 300, made, A=_out(cls))
    _class_literal(same, "B", gun)
    held, _other = _branch(ed, _out(same),
                           [_loose_pin(loop, "LoopBody", is_input=False)],
                           x0 + 1040, y0, made)
    _setter(ed, DEV_HAS_GUN_VAR, "true", [held], x0 + 1300, y0, made)

    # After the scan: a gun not carried, while there is room for it.
    y1 = y0 + 700
    count = _call(ed, FN_ARR_LEN, x0 + 260, y1 + 300, made,
                  TargetArray=_get(ed, "Inventory", x0, y1 + 300, made,
                                   WEAPON_COMP_CLASS_PATH, wc))
    room = _call(ed, FN_LESS_II, x0 + 500, y1 + 300, made, A=_out(count),
                 B=INVENTORY_SIZE)
    new = _call(ed, FN_NOT, x0 + 500, y1 + 440, made,
                A=_get(ed, DEV_HAS_GUN_VAR, x0 + 260, y1 + 440, made))
    want = _call(ed, FN_AND, x0 + 740, y1 + 300, made, A=_out(room), B=_out(new))
    give, skip = _branch(ed, _out(want),
                         [_loose_pin(loop, "Completed", is_input=False)],
                         x0 + 980, y1, made)

    where = _call(ed, FN_GET_TRANSFORM, x0 + 1000, y1 + 300, made, self=pawn_out)
    spawn = _at(_palette(ed, NODE_SPAWN), x0 + 1240, y1)
    made.append(spawn)
    _class_literal(spawn, "Class", gun)
    _connect(_out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(give, _pin(spawn, "execute"))
    cast = _at(_palette(ed, NODE_CAST_ITEM), x0 + 1540, y1)
    made.append(cast)
    _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(spawn), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    # Carried, not lying in the world.
    flow = _setter(ed, "Dropped", "false", [BEL.find_then_pin(cast)], x0 + 1840, y1,
                   made, ITEM_CLASS_PATH, item)
    add = _call(ed, FN_ARR_ADD, x0 + 2100, y1, made,
                TargetArray=_get(ed, "Inventory", x0 + 1840, y1 + 300, made,
                                 WEAPON_COMP_CLASS_PATH, wc))
    _connect(item, _loose_pin(add, "NewItem"))
    _connect(flow, _pin(add, "execute"))
    return [BEL.find_then_pin(add), skip, _pin(cast, "CastFailed", is_input=False)]


def author_dev_guns(ed, pc_out, parts, in_execs, x0, y0, made):
    """The whole fragment (see the module docstring). ``parts`` is
    player_parts'. Returns the exec tails."""
    unreal.load_asset(ITEM_BP_PATH)     # the cast node exists only for a loaded class
    raise_it, no_key = _branch(ed, pause_row_taken(ed, DEV_GUNS_ACTION, x0,
                                                   y0 + 300, made),
                               in_execs, x0 + 480, y0, made)
    raised = _setter(ed, DEV_GUNS_REQUEST_VAR, "true", [raise_it], x0 + 740, y0 - 300,
                     made)

    serve, idle = _branch(ed, _get(ed, DEV_GUNS_REQUEST_VAR, x0 + 740, y0 + 300, made),
                          [raised, no_key], x0 + 1000, y0, made)
    flow = [_setter(ed, DEV_GUNS_REQUEST_VAR, "false", [serve], x0 + 1260, y0, made)]
    wc = parts[WEAPON_COMP_CLASS_PATH]
    x = x0 + 1520
    for gun in DEV_GUN_CLASS_PATHS:
        flow = _author_give_one(ed, gun, wc, parts[PAWN], flow, x, y0, made)
        x += 2600
    dirty = _setter(ed, "NeedsRefresh", "true", flow, x, y0, made,
                    WEAPON_COMP_CLASS_PATH, wc)
    ed.add_comment_to_nodes(
        f"dev-all-guns (its row in the M panel): one of every gun not "
        f"already carried, while fewer than {INVENTORY_SIZE} items are. "
        f"NeedsRefresh re-equips; the held item stays held.", made[-1:])
    return [dirty, idle]
