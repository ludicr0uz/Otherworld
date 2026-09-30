"""Reading the profile: BP_Profile back onto the player who just started.

Run once per level, from save_exit.py, the first Tick of a started game on
which the weapon component has spawned its loadout -- so the issued guns are
there to be replaced, rather than spawned after the saved ones and added twice.

    LoadGameFromSlot(PROFILE_SLOT) -> Cast
      -> the stats and the kill count back onto their owners
      -> destroy every item carried now, clear Inventory
      -> for each saved class: spawn it at the pawn, Dropped = false,
                               Loaded/Reserve from the save, Inventory += it
      -> EquippedIndex from the save, NeedsRefresh = true

NeedsRefresh hands the equipping to the weapon component's own Tick, the one
place attaching is authored. Location is never read: a loaded character
starts wherever the level puts it.
"""

from combat.game_state import KILL_COUNT_VAR
from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import MACRO_FOR_EACH, NODE_SPAWN
from combat.paths import GAME_MODE_CLASS_PATH, ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.player_parts import MODE, PAWN
from graphics_menu.profile_consts import (
    AMMO_FIELDS, EQUIPPED_FIELD, ITEM_CLASSES_FIELD, KILLS_FIELD,
    NODE_CAST_PROFILE, PROFILE_CLASS_PATH, PROFILE_SLOT, PROFILE_USER_INDEX,
    STAT_FIELDS,
)
from graphics_menu.profile_write import copy_var

FN_LOAD_SAVE = "/Script/Engine.GameplayStatics.LoadGameFromSlot"
FN_DESTROY = "/Script/Engine.Actor.K2_DestroyActor"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_ARR_CLEAR = "/Script/Engine.KismetArrayLibrary.Array_Clear"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_GET_TRANSFORM = "/Script/Engine.Actor.GetTransform"


def _for_each(ed, array_out, exec_in, x, y, made):
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(loop, x, y)
    _connect(array_out, _loose_pin(loop, "Array"))
    _connect(exec_in, _loose_pin(loop, "Exec"))
    made.append(loop)
    return loop


def _author_respawn_items(ed, prof, wc, pawn_out, exec_in, x0, y0, made):
    """The saved items, spawned and carried. Returns the loop's Completed."""
    classes = _at(ed.add_get_member_variable_node(ITEM_CLASSES_FIELD, PROFILE_CLASS_PATH),
                  x0, y0 + 240)
    _connect(prof, _pin(classes, "self"))
    made.append(classes)
    loop = _for_each(ed, _pin(classes, ITEM_CLASSES_FIELD, is_input=False), exec_in,
                     x0 + 260, y0, made)
    index = _loose_pin(loop, "ArrayIndex", is_input=False)

    where = _at(_node(ed, FN_GET_TRANSFORM), x0 + 560, y0 + 300)
    _connect(pawn_out, _pin(where, "self"))
    spawn = _at(_palette(ed, NODE_SPAWN), x0 + 800, y0)
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(spawn, "execute"))
    made += [where, spawn]
    item = _pin(spawn, "ReturnValue", is_input=False)

    # Carried, not lying in the world: a consumable defaults to Dropped.
    held = _at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
               x0 + 1100, y0)
    _connect(item, _pin(held, "self"))
    _set(held, "Dropped", "false")
    _connect(BEL.find_then_pin(spawn), _pin(held, "execute"))
    made.append(held)
    flow = BEL.find_then_pin(held)

    x = x0 + 1360
    for field, item_var in AMMO_FIELDS:
        arr = _at(ed.add_get_member_variable_node(field, PROFILE_CLASS_PATH),
                  x, y0 + 300)
        _connect(prof, _pin(arr, "self"))
        at = _at(_node(ed, FN_ARR_GET), x + 240, y0 + 300)
        _connect(_pin(arr, field, is_input=False), _loose_pin(at, "TargetArray"))
        _connect(index, _pin(at, "Index"))
        put = _at(ed.add_set_member_variable_node(item_var, ITEM_CLASS_PATH),
                  x + 480, y0)
        _connect(item, _pin(put, "self"))
        _connect(_loose_pin(at, "Item", is_input=False), _pin(put, item_var))
        _connect(flow, _pin(put, "execute"))
        made += [arr, at, put]
        flow = BEL.find_then_pin(put)
        x += 740

    inv = _at(ed.add_get_member_variable_node("Inventory", WEAPON_COMP_CLASS_PATH),
              x, y0 + 300)
    _connect(wc, _pin(inv, "self"))
    add = _at(_node(ed, FN_ARR_ADD), x + 240, y0)
    _connect(_pin(inv, "Inventory", is_input=False), _loose_pin(add, "TargetArray"))
    _connect(item, _loose_pin(add, "NewItem"))
    _connect(flow, _pin(add, "execute"))
    made += [inv, add]
    return _loose_pin(loop, "Completed", is_input=False)


def author_read_profile(ed, in_exec, parts, x0, y0, made):
    """Load the profile slot onto ``parts`` (player_parts). Returns the exec
    pins that continue: applied, or the save would not cast."""
    load = _at(_node(ed, FN_LOAD_SAVE), x0, y0)
    _set(load, "SlotName", PROFILE_SLOT)
    _set(load, "UserIndex", PROFILE_USER_INDEX)
    _connect(in_exec, _pin(load, "execute"))
    cast = _at(_palette(ed, NODE_CAST_PROFILE), x0 + 260, y0)
    _connect(_pin(load, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(load), _pin(cast, "execute"))
    made += [load, cast]
    prof = _loose_pin(cast, "AsBPProfile", is_input=False)
    flow = BEL.find_then_pin(cast)
    wc = parts[WEAPON_COMP_CLASS_PATH]

    x = x0 + 520
    copies = [(parts[owner], owner, var, field) for field, owner, var in STAT_FIELDS]
    copies += [(parts[MODE], GAME_MODE_CLASS_PATH, KILL_COUNT_VAR, KILLS_FIELD)]
    for dst_out, dst_class, dst_var, field in copies:
        flow = copy_var(ed, prof, PROFILE_CLASS_PATH, field, dst_out, dst_class,
                     dst_var, flow, x, y0, made)
        x += 520

    # --- out with the issued loadout ----------------------------------------
    old = _at(ed.add_get_member_variable_node("Inventory", WEAPON_COMP_CLASS_PATH),
              x, y0 + 240)
    _connect(wc, _pin(old, "self"))
    made.append(old)
    old_out = _pin(old, "Inventory", is_input=False)
    drop_all = _for_each(ed, old_out, flow, x + 260, y0, made)
    gone = _at(_node(ed, FN_DESTROY), x + 560, y0)
    _connect(_loose_pin(drop_all, "ArrayElement", is_input=False), _pin(gone, "self"))
    _connect(_loose_pin(drop_all, "LoopBody", is_input=False), _pin(gone, "execute"))
    wipe = _at(_node(ed, FN_ARR_CLEAR), x + 820, y0 - 300)
    _connect(old_out, _loose_pin(wipe, "TargetArray"))
    _connect(_loose_pin(drop_all, "Completed", is_input=False), _pin(wipe, "execute"))
    made += [gone, wipe]

    # --- in with the saved one ----------------------------------------------
    done = _author_respawn_items(ed, prof, wc, parts[PAWN], BEL.find_then_pin(wipe),
                                 x + 1080, y0, made)
    x += 1080 + 3200
    flow = copy_var(ed, prof, PROFILE_CLASS_PATH, EQUIPPED_FIELD, wc,
                 WEAPON_COMP_CLASS_PATH, "EquippedIndex", done, x, y0, made)
    dirty = _at(ed.add_set_member_variable_node("NeedsRefresh", WEAPON_COMP_CLASS_PATH),
                x + 520, y0)
    _connect(wc, _pin(dirty, "self"))
    _set(dirty, "NeedsRefresh", "true")
    _connect(flow, _pin(dirty, "execute"))
    made.append(dirty)
    ed.add_comment_to_nodes(
        f"The saved profile ({PROFILE_SLOT!r}) back onto the player: stats, kill "
        f"count, and the inventory -- the issued loadout destroyed and the saved "
        f"items spawned in its place. NeedsRefresh makes the weapon component "
        f"equip, so attaching stays authored once. Position is never restored.",
        [load, cast, drop_all, wipe, dirty])
    return [BEL.find_then_pin(dirty), _pin(cast, "CastFailed", is_input=False)]
