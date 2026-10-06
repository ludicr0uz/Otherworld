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
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from net.state_consts import PLAYER_STATE_CLASS_PATH
from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.player_parts import STATE, PAWN
from graphics_menu.profile_consts import (
    ITEM_FIELDS, EQUIPPED_FIELD, ITEM_CLASSES_FIELD, KILLS_FIELD, PROFILE_CLASS_PATH,
    PROFILE_SLOT, PROFILE_USER_INDEX, STAT_FIELDS)
from graphics_menu.profile_write import copy_var
from uebp.nodes.actor import FN_DESTROY, FN_GET_TRANSFORM
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_CLEAR, FN_ARR_GET
from uebp.nodes.move import FN_SET_STAMINA
from uebp.nodes.palette import MACRO_FOR_EACH, NODE_CAST_PROFILE, NODE_SPAWN
from uebp.nodes.system import FN_LOAD_SAVE
from combat import item_vars as IV
from combat.weapon_component import vars as WV


def _for_each(ed, array_out, exec_in, made):
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    loop
    _connect(array_out, _loose_pin(loop, "Array"))
    _connect(exec_in, _loose_pin(loop, "Exec"))
    made.append(loop)
    return loop


def _author_respawn_items(ed, prof, wc, pawn_out, exec_in, made):
    """The saved items, spawned and carried. Returns the loop's Completed."""
    classes = ed.add_get_member_variable_node(ITEM_CLASSES_FIELD, PROFILE_CLASS_PATH)
    _connect(prof, _pin(classes, "self"))
    made.append(classes)
    loop = _for_each(ed, out(classes, ITEM_CLASSES_FIELD), exec_in, made)
    index = _loose_pin(loop, "ArrayIndex", is_input=False)

    where = _node(ed, FN_GET_TRANSFORM)
    _connect(pawn_out, _pin(where, "self"))
    spawn = _palette(ed, NODE_SPAWN)
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(spawn, "Class"))
    _connect(out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(spawn, "execute"))
    made += [where, spawn]
    item = out(spawn)

    # Carried, not lying in the world: a consumable defaults to Dropped.
    held = ed.add_set_member_variable_node(IV.Dropped, ITEM_CLASS_PATH)
    _connect(item, _pin(held, "self"))
    _set(held, IV.Dropped, False)
    _connect(then(spawn), _pin(held, "execute"))
    made.append(held)
    flow = then(held)

    for field, item_var in ITEM_FIELDS:
        arr = ed.add_get_member_variable_node(field, PROFILE_CLASS_PATH)
        _connect(prof, _pin(arr, "self"))
        at = _node(ed, FN_ARR_GET)
        _connect(out(arr, field), _loose_pin(at, "TargetArray"))
        _connect(index, _pin(at, "Index"))
        put = ed.add_set_member_variable_node(item_var, ITEM_CLASS_PATH)
        _connect(item, _pin(put, "self"))
        _connect(_loose_pin(at, "Item", is_input=False), _pin(put, item_var))
        _connect(flow, _pin(put, "execute"))
        made += [arr, at, put]
        flow = then(put)

    inv = ed.add_get_member_variable_node(WV.Inventory, WEAPON_COMP_CLASS_PATH)
    _connect(wc, _pin(inv, "self"))
    add = _node(ed, FN_ARR_ADD)
    _connect(out(inv, WV.Inventory), _loose_pin(add, "TargetArray"))
    _connect(item, _loose_pin(add, "NewItem"))
    _connect(flow, _pin(add, "execute"))
    made += [inv, add]
    return _loose_pin(loop, "Completed", is_input=False)


def author_read_profile(ed, in_exec, parts, made):
    """Load the profile slot onto ``parts`` (player_parts). Returns the exec
    pins that continue: applied, or the save would not cast."""
    load = _node(ed, FN_LOAD_SAVE)
    _set(load, "SlotName", PROFILE_SLOT)
    _set(load, "UserIndex", PROFILE_USER_INDEX)
    _connect(in_exec, _pin(load, "execute"))
    cast = _palette(ed, NODE_CAST_PROFILE)
    _connect(out(load), _pin(cast, "Object"))
    _connect(then(load), _pin(cast, "execute"))
    made += [load, cast]
    prof = _loose_pin(cast, "AsBPProfile", is_input=False)
    flow = then(cast)
    wc = parts[WEAPON_COMP_CLASS_PATH]

    copies = [(parts[owner], owner, var, field) for field, owner, var in STAT_FIELDS]
    copies += [(parts[STATE], PLAYER_STATE_CLASS_PATH, KILL_COUNT_VAR, KILLS_FIELD)]
    for dst_out, dst_class, dst_var, field in copies:
        flow = copy_var(ed, prof, PROFILE_CLASS_PATH, field, dst_out, dst_class,
                     dst_var, flow, made)
    # The stamina is the movement component's (combat/player_move.py); the
    # weapon component's is a copy of it, so the saved one goes there too.
    saved = ed.add_get_member_variable_node(WV.Stamina, WEAPON_COMP_CLASS_PATH)
    _connect(wc, _pin(saved, "self"))
    hand = _node(ed, FN_SET_STAMINA)
    _connect(parts[PAWN], _pin(hand, "Character"))
    _connect(out(saved, WV.Stamina), _pin(hand, "NewStamina"))
    _connect(flow, _pin(hand, "execute"))
    made += [saved, hand]
    flow = then(hand)

    # --- out with the issued loadout ----------------------------------------
    old = ed.add_get_member_variable_node(WV.Inventory, WEAPON_COMP_CLASS_PATH)
    _connect(wc, _pin(old, "self"))
    made.append(old)
    old_out = out(old, WV.Inventory)
    drop_all = _for_each(ed, old_out, flow, made)
    gone = _node(ed, FN_DESTROY)
    _connect(_loose_pin(drop_all, "ArrayElement", is_input=False), _pin(gone, "self"))
    _connect(_loose_pin(drop_all, "LoopBody", is_input=False), _pin(gone, "execute"))
    wipe = _node(ed, FN_ARR_CLEAR)
    _connect(old_out, _loose_pin(wipe, "TargetArray"))
    _connect(_loose_pin(drop_all, "Completed", is_input=False), _pin(wipe, "execute"))
    made += [gone, wipe]

    # --- in with the saved one ----------------------------------------------
    done = _author_respawn_items(ed, prof, wc, parts[PAWN], then(wipe), made)
    flow = copy_var(ed, prof, PROFILE_CLASS_PATH, EQUIPPED_FIELD, wc,
                 WEAPON_COMP_CLASS_PATH, "EquippedIndex", done, made)
    dirty = ed.add_set_member_variable_node(WV.NeedsRefresh, WEAPON_COMP_CLASS_PATH)
    _connect(wc, _pin(dirty, "self"))
    _set(dirty, WV.NeedsRefresh, True)
    _connect(flow, _pin(dirty, "execute"))
    made.append(dirty)
    ed.add_comment_to_nodes(
        f"The saved profile ({PROFILE_SLOT!r}) back onto the player: stats, kill "
        f"count, and the inventory -- the issued loadout destroyed and the saved "
        f"items spawned in its place. NeedsRefresh makes the weapon component "
        f"equip, so attaching stays authored once. Position is never restored.",
        [load, cast, drop_all, wipe, dirty])
    return [then(dirty), out(cast, "CastFailed")]
