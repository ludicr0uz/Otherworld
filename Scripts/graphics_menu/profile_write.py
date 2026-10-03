"""Writing the profile: the player's stats and inventory into BP_Profile.

Run once, when the save-and-exit countdown runs out (save_exit.py). A fresh
BP_Profile every time rather than an edit of the loaded one, so a field that
was dropped from the character (an item eaten) cannot survive in the save.

    CreateSaveGameObject(BP_Profile) -> Cast
      -> Health, Stamina, Hunger, Thirst, Temperature, Kills, EquippedIndex
      -> for each Inventory item: ItemClasses += its class,
                                  ItemLoaded += Loaded, ItemReserve += Reserve
      -> SaveGameToSlot(PROFILE_SLOT)
"""

from combat.game_state import KILL_COUNT_VAR
from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import MACRO_FOR_EACH
from combat.paths import GAME_MODE_CLASS_PATH, ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.player_parts import MODE
from graphics_menu.profile_consts import (
    ITEM_FIELDS, EQUIPPED_FIELD, ITEM_CLASSES_FIELD, KILLS_FIELD,
    NODE_CAST_PROFILE, PROFILE_CLASS_PATH, PROFILE_SLOT, PROFILE_USER_INDEX,
    STAT_FIELDS,
)

FN_CREATE_SAVE = "/Script/Engine.GameplayStatics.CreateSaveGameObject"
FN_WRITE_SAVE = "/Script/Engine.GameplayStatics.SaveGameToSlot"
FN_OBJECT_CLASS = "/Script/Engine.GameplayStatics.GetObjectClass"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"


def copy_var(ed, src_out, src_class, src_var, dst_out, dst_class, dst_var, flow, made):
    """dst.dst_var = src.src_var; returns the exec that follows."""
    get = ed.add_get_member_variable_node(src_var, src_class)
    _connect(src_out, _pin(get, "self"))
    put = ed.add_set_member_variable_node(dst_var, dst_class)
    _connect(dst_out, _pin(put, "self"))
    _connect(_pin(get, src_var, is_input=False), _pin(put, dst_var))
    _connect(flow, _pin(put, "execute"))
    made += [get, put]
    return BEL.find_then_pin(put)


def author_write_profile(ed, in_exec, parts, made):
    """Fill a new BP_Profile from ``parts`` (player_parts) and save it.

    Returns the exec pins that continue: saved, or the profile cast failed.
    """
    fresh = _node(ed, FN_CREATE_SAVE)
    _pin(fresh, "SaveGameClass").set_pin_value(PROFILE_CLASS_PATH)
    _connect(in_exec, _pin(fresh, "execute"))
    cast = _palette(ed, NODE_CAST_PROFILE)
    _connect(_pin(fresh, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(fresh), _pin(cast, "execute"))
    made += [fresh, cast]
    prof = _loose_pin(cast, "AsBPProfile", is_input=False)
    flow = BEL.find_then_pin(cast)

    copies = [(parts[owner], owner, var, field) for field, owner, var in STAT_FIELDS]
    copies += [(parts[MODE], GAME_MODE_CLASS_PATH, KILL_COUNT_VAR, KILLS_FIELD),
               (parts[WEAPON_COMP_CLASS_PATH], WEAPON_COMP_CLASS_PATH,
                "EquippedIndex", EQUIPPED_FIELD)]
    for src_out, src_class, src_var, field in copies:
        flow = copy_var(ed, src_out, src_class, src_var, prof, PROFILE_CLASS_PATH,
                     field, flow, made)

    # --- the inventory, one entry per slot in every array -------------------
    inv = ed.add_get_member_variable_node("Inventory", WEAPON_COMP_CLASS_PATH)
    _connect(parts[WEAPON_COMP_CLASS_PATH], _pin(inv, "self"))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    loop
    _connect(_pin(inv, "Inventory", is_input=False), _loose_pin(loop, "Array"))
    _connect(flow, _loose_pin(loop, "Exec"))
    made += [inv, loop]
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    body = _loose_pin(loop, "LoopBody", is_input=False)
    kind = _node(ed, FN_OBJECT_CLASS)
    _connect(item, _pin(kind, "Object"))
    made.append(kind)
    sources = [(ITEM_CLASSES_FIELD, _pin(kind, "ReturnValue", is_input=False))]
    for field, item_var in ITEM_FIELDS:
        got = ed.add_get_member_variable_node(item_var, ITEM_CLASS_PATH)
        _connect(item, _pin(got, "self"))
        made.append(got)
        sources.append((field, _pin(got, item_var, is_input=False)))
    for field, value_out in sources:
        arr = ed.add_get_member_variable_node(field, PROFILE_CLASS_PATH)
        _connect(prof, _pin(arr, "self"))
        add = _node(ed, FN_ARR_ADD)
        _connect(_pin(arr, field, is_input=False), _loose_pin(add, "TargetArray"))
        _connect(value_out, _loose_pin(add, "NewItem"))
        _connect(body, _pin(add, "execute"))
        made += [arr, add]
        body = BEL.find_then_pin(add)

    save = _node(ed, FN_WRITE_SAVE)
    _connect(prof, _pin(save, "SaveGameObject"))
    _set(save, "SlotName", PROFILE_SLOT)
    _set(save, "UserIndex", PROFILE_USER_INDEX)
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(save, "execute"))
    made.append(save)
    ed.add_comment_to_nodes(
        f"The profile: the player's stats and inventory into a fresh BP_Profile, "
        f"saved to slot {PROFILE_SLOT!r}. Not where the player stands: a loaded "
        f"character starts wherever the level puts it.",
        [fresh, cast, loop, save])
    return [BEL.find_then_pin(save), _pin(cast, "CastFailed", is_input=False)]
