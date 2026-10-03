"""The dev-all-guns cheat: the HUD Tick fragment behind the M panel's dev-all-guns row.

    the row taken (PauseClick) -> DevAllGunsRequested = true
    DevAllGunsRequested        -> false, then for each gun class, in order:
        DevHasGun = false
        ForEach Inventory: GetObjectClass(item) == gun -> DevHasGun = true
        not DevHasGun AND Inventory has room
            -> spawn the gun at the pawn, cast, Dropped = false, Inventory += it
    then NeedsRefresh, so the weapon component re-equips what it holds and
    hides the rest -- the held item stays held, as with a pick-up.

A gun already carried is skipped, so pressing it twice adds nothing, and no
more items are carried than there are SLOT_COUNT slots: the weapon
component's slot sync puts each new one in a free bag slot, the hand, or
the weapon slot it fits. The key only raises
the request, which is what lets a probe ask for the guns without a key press
(probes/probe_dev_all_guns.py).
"""

import unreal

from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set
from uebp.graph import out
from combat.nodes import FN_OBJECT_CLASS, MACRO_FOR_EACH, NODE_CAST_ITEM, NODE_SPAWN
from combat.paths import ITEM_BP_PATH, ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import SLOT_COUNT
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


def _setter(ed, var, value, in_execs, made, owner=None, self_out=None):
    n = (ed.add_set_member_variable_node(var, owner) if owner
            else ed.add_set_member_variable_node(var))
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    _set(n, var, value)
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    made.append(n)
    return BEL.find_then_pin(n)


def _get(ed, var, made, owner=None, self_out=None):
    n = (ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var))
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    made.append(n)
    return _pin(n, var, is_input=False)


def _call(ed, fn, made, **inputs):
    n = _node(ed, fn)
    for name, v in inputs.items():
        if isinstance(v, (str, int, float)):
            _set(n, name, v)
        else:
            _connect(v, _pin(n, name))
    made.append(n)
    return n


def _branch(ed, cond, in_execs, made):
    br = ed.add_branch_node()
    _connect(cond, _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    made.append(br)
    return BEL.find_then_pin(br), BEL.find_else_pin(br)


def _author_give_one(ed, gun, wc, pawn_out, in_execs, made):
    """One gun class: skipped if carried or the bag is full, else spawned and
    carried. Returns the exec tails."""
    flow = _setter(ed, DEV_HAS_GUN_VAR, "false", in_execs, made)
    inv = _get(ed, "Inventory", made, WEAPON_COMP_CLASS_PATH, wc)
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(inv, _loose_pin(loop, "Array"))
    _connect(flow, _loose_pin(loop, "Exec"))
    cls = _call(ed, FN_OBJECT_CLASS, made, Object=_loose_pin(loop, "ArrayElement", is_input=False))
    same = _call(ed, FN_CLASS_EQ, made, A=out(cls))
    _class_literal(same, "B", gun)
    held, _other = _branch(ed, out(same), [_loose_pin(loop, "LoopBody", is_input=False)], made)
    _setter(ed, DEV_HAS_GUN_VAR, "true", [held], made)

    # After the scan: a gun not carried, while there is room for it.
    count = _call(ed, FN_ARR_LEN, made,
                  TargetArray=_get(ed, "Inventory", made,
                                   WEAPON_COMP_CLASS_PATH, wc))
    room = _call(ed, FN_LESS_II, made, A=out(count), B=SLOT_COUNT)
    new = _call(ed, FN_NOT, made, A=_get(ed, DEV_HAS_GUN_VAR, made))
    want = _call(ed, FN_AND, made, A=out(room), B=out(new))
    give, skip = _branch(ed, out(want), [_loose_pin(loop, "Completed", is_input=False)], made)

    where = _call(ed, FN_GET_TRANSFORM, made, self=pawn_out)
    spawn = _palette(ed, NODE_SPAWN)
    made.append(spawn)
    _class_literal(spawn, "Class", gun)
    _connect(out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(give, _pin(spawn, "execute"))
    cast = _palette(ed, NODE_CAST_ITEM)
    made.append(cast)
    _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(spawn), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    # Carried, not lying in the world.
    flow = _setter(ed, "Dropped", "false", [BEL.find_then_pin(cast)], made, ITEM_CLASS_PATH, item)
    add = _call(ed, FN_ARR_ADD, made,
                TargetArray=_get(ed, "Inventory", made,
                                 WEAPON_COMP_CLASS_PATH, wc))
    _connect(item, _loose_pin(add, "NewItem"))
    _connect(flow, _pin(add, "execute"))
    return [BEL.find_then_pin(add), skip, _pin(cast, "CastFailed", is_input=False)]


def author_dev_guns(ed, pc_out, parts, in_execs, made):
    """The whole fragment (see the module docstring). ``parts`` is
    player_parts'. Returns the exec tails."""
    unreal.load_asset(ITEM_BP_PATH)     # the cast node exists only for a loaded class
    raise_it, no_key = _branch(ed, pause_row_taken(ed, DEV_GUNS_ACTION, made), in_execs, made)
    raised = _setter(ed, DEV_GUNS_REQUEST_VAR, "true", [raise_it], made)

    serve, idle = _branch(ed, _get(ed, DEV_GUNS_REQUEST_VAR, made), [raised, no_key], made)
    flow = [_setter(ed, DEV_GUNS_REQUEST_VAR, "false", [serve], made)]
    wc = parts[WEAPON_COMP_CLASS_PATH]
    for gun in DEV_GUN_CLASS_PATHS:
        flow = _author_give_one(ed, gun, wc, parts[PAWN], flow, made)
    dirty = _setter(ed, "NeedsRefresh", "true", flow, made, WEAPON_COMP_CLASS_PATH, wc)
    ed.add_comment_to_nodes(
        f"dev-all-guns (its row in the M panel): one of every gun not "
        f"already carried, while fewer than {SLOT_COUNT} items are. "
        f"NeedsRefresh re-equips; the held item stays held.", made[-1:])
    return [dirty, idle]
