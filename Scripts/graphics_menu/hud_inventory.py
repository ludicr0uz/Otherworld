"""DrawHUD: the inventory grid -- WBP_HUD's ten WBP_InventorySlots and the
equipped weapon's name above them -- filled from the weapon component.

Everything shown comes off the carried item itself (Icon, SlotColor,
DisplayName, UsesAmmo, Loaded, Reserve, InfiniteReserve), so the HUD keeps no table of weapons
and no idea which of them has a magazine. Slot i shows Inventory[i]; a slot
past the end of the inventory is emptied, every frame, so a dropped weapon
leaves no ghost behind.

The equipped slot gets a lit background AND a lit frame over its icon -- a
lit edge alone was reported as not reading -- and its name, once, above the
grid rather than in every slot.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.tuning import INVENTORY_SIZE
from graphics_menu.ui_graph import (
    FN_CHILD_AT, MACRO_FOR_LOOP, member, part, set_shown, set_text, show_if,
)
from graphics_menu.umg_consts import (
    EQUIPPED_NAME, SLOT_ACTIVE, SLOT_AMMO, SLOT_FRAME, SLOT_ICON, SLOTS,
    WBP_HUD, WBP_INVENTORY_SLOT,
)

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
ITEM_CLASS_PATH = "/Game/Weapons/BP_WeaponItem.BP_WeaponItem_C"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"
NODE_CAST_SLOT = "Utilities|Casting|CastToWBP_InventorySlot"

FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_ARR_VALID = "/Script/Engine.KismetArrayLibrary.Array_IsValidIndex"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_SELECT_STR = "/Script/Engine.KismetMathLibrary.SelectString"
# What an InfiniteReserve weapon (the pistol) shows for its reserve.
INFINITE_RESERVE_TEXT = "\u221e"
FN_SET_BRUSH = "/Script/UMG.Image.SetBrushFromTexture"
FN_SET_TINT = "/Script/UMG.Image.SetColorAndOpacity"


def _item(ed, inv, index, x, y):
    """(IsValidIndex(inv, index), inv[index]) -- read the item only behind the
    first, or an empty slot is an Accessed None per frame."""
    valid = _at(_node(ed, FN_ARR_VALID), x, y)
    _connect(inv, _loose_pin(valid, "TargetArray"))
    _connect(index, _pin(valid, "IndexToTest"))
    got = _at(_node(ed, FN_ARR_GET), x, y + 160)
    _connect(inv, _loose_pin(got, "TargetArray"))
    _connect(index, _pin(got, "Index"))
    return (_pin(valid, "ReturnValue", is_input=False),
            _loose_pin(got, "Item", is_input=False))


def _get(ed, item, var, x, y):
    n = _at(ed.add_get_member_variable_node(var, ITEM_CLASS_PATH), x, y)
    _connect(item, _pin(n, "self"))
    return _pin(n, var, is_input=False)


def _author_equipped_name(ed, inv, equipped, exec_in, x0, y0):
    valid, item = _item(ed, inv, equipped, x0, y0 + 300)
    br = _at(ed.add_branch_node(), x0 + 260, y0)
    _connect(valid, _pin(br, "Condition"))
    _connect(exec_in, _pin(br, "execute"))
    name = part(ed, WBP_HUD, EQUIPPED_NAME, x0 + 260, y0 + 500)
    said = set_text(ed, name, _get(ed, item, "DisplayName", x0 + 520, y0 + 300),
                    [BEL.find_then_pin(br)], x0 + 780, y0)
    return (set_shown(ed, name, True, [said], x0 + 1040, y0),
            set_shown(ed, name, False, [BEL.find_else_pin(br)], x0 + 1040, y0 + 200))


def _author_filled_slot(ed, slot, item, is_equipped, exec_in, x0, y0):
    """Icon in the item's colour, its ammunition if it counts any, and the
    equipped slot's lit layers. Returns the exec tails."""
    def w(name, py):
        return member(ed, slot, WBP_INVENTORY_SLOT, name, x0, py)

    icon = w(SLOT_ICON, y0 + 300)
    brush = _at(_node(ed, FN_SET_BRUSH), x0 + 260, y0)
    _connect(icon, _pin(brush, "self"))
    _connect(_get(ed, item, "Icon", x0, y0 + 440), _pin(brush, "Texture"))
    _connect(exec_in, _pin(brush, "execute"))
    tint = _at(_node(ed, FN_SET_TINT), x0 + 520, y0)
    _connect(icon, _pin(tint, "self"))
    _connect(_get(ed, item, "SlotColor", x0 + 260, y0 + 440), _pin(tint, "InColorAndOpacity"))
    _connect(BEL.find_then_pin(brush), _pin(tint, "execute"))
    flow = set_shown(ed, icon, True, [BEL.find_then_pin(tint)], x0 + 780, y0)

    # "3 / 15": rounds in the gun, rounds in reserve. Only for a weapon that
    # uses ammunition. The pistol reloads every eight shots over an endless
    # reserve, so it reads "5 / ∞": the magazine is the part to manage.
    loaded = _at(_node(ed, FN_INT_TO_STR), x0 + 1040, y0 + 440)
    _connect(_get(ed, item, "Loaded", x0 + 780, y0 + 440), _pin(loaded, "InInt"))
    reserve = _at(_node(ed, FN_INT_TO_STR), x0 + 1040, y0 + 580)
    _connect(_get(ed, item, "Reserve", x0 + 780, y0 + 580), _pin(reserve, "InInt"))
    spare = _at(_node(ed, FN_SELECT_STR), x0 + 1280, y0 + 700)
    _set(spare, "A", INFINITE_RESERVE_TEXT)
    _connect(_pin(reserve, "ReturnValue", is_input=False), _pin(spare, "B"))
    _connect(_get(ed, item, "InfiniteReserve", x0 + 1040, y0 + 720), _pin(spare, "bPickA"))
    sep = _at(_node(ed, FN_CONCAT), x0 + 1280, y0 + 580)
    _set(sep, "A", " / ")
    _connect(_pin(spare, "ReturnValue", is_input=False), _pin(sep, "B"))
    count = _at(_node(ed, FN_CONCAT), x0 + 1520, y0 + 440)
    _connect(_pin(loaded, "ReturnValue", is_input=False), _pin(count, "A"))
    _connect(_pin(sep, "ReturnValue", is_input=False), _pin(count, "B"))

    ammo = w(SLOT_AMMO, y0 + 700)
    counted = _at(ed.add_branch_node(), x0 + 1040, y0)
    _connect(_get(ed, item, "UsesAmmo", x0 + 780, y0 + 300), _pin(counted, "Condition"))
    _connect(flow, _pin(counted, "execute"))
    wrote = set_text(ed, ammo, _pin(count, "ReturnValue", is_input=False),
                     [BEL.find_then_pin(counted)], x0 + 1780, y0)
    tails = (set_shown(ed, ammo, True, [wrote], x0 + 2040, y0),
             set_shown(ed, ammo, False, [BEL.find_else_pin(counted)], x0 + 2040, y0 + 200))

    active, frame = w(SLOT_ACTIVE, y0 + 900), w(SLOT_FRAME, y0 + 1000)
    lit = show_if(ed, active, is_equipped, tails, x0 + 2300, y0)
    return show_if(ed, frame, is_equipped, lit, x0 + 2820, y0)


def _author_empty_slot(ed, slot, exec_in, x0, y0):
    flow = (exec_in,)
    for i, name in enumerate((SLOT_ICON, SLOT_AMMO, SLOT_ACTIVE, SLOT_FRAME)):
        target = member(ed, slot, WBP_INVENTORY_SLOT, name, x0 + i * 260, y0 + 240)
        flow = (set_shown(ed, target, False, flow, x0 + i * 260, y0),)
    return flow


def author_inventory(ed, x0, y0, in_execs):
    """Returns the exec pins to go on from; a pawn with no weapon component
    still reaches the rest of the HUD."""
    pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 300)
    _set(pawn, "PlayerIndex", 0)
    comp = _at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 300)
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 500, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    inv = _at(ed.add_get_member_variable_node("Inventory", WEAPON_COMP_CLASS_PATH),
              x0 + 760, y0 + 300)
    _connect(as_weapon, _pin(inv, "self"))
    inv = _pin(inv, "Inventory", is_input=False)
    equipped = _at(ed.add_get_member_variable_node("EquippedIndex", WEAPON_COMP_CLASS_PATH),
                   x0 + 760, y0 + 420)
    _connect(as_weapon, _pin(equipped, "self"))
    equipped = _pin(equipped, "EquippedIndex", is_input=False)

    named = _author_equipped_name(ed, inv, equipped, BEL.find_then_pin(cast),
                                  x0 + 1000, y0)

    # Slot i of the grid, i over every slot the component allows.
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    _at(loop, x0 + 2300, y0)
    _set(loop, "FirstIndex", 0)
    _set(loop, "LastIndex", INVENTORY_SIZE - 1)
    for e in named:
        _connect(e, _pin(loop, "execute"))
    index = _loose_pin(loop, "Index", is_input=False)
    child = _at(_node(ed, FN_CHILD_AT), x0 + 2600, y0 + 300)
    _connect(part(ed, WBP_HUD, SLOTS, x0 + 2300, y0 + 500), _pin(child, "self"))
    _connect(index, _pin(child, "Index"))
    as_slot = _at(_palette(ed, NODE_CAST_SLOT), x0 + 2860, y0)
    _connect(_pin(child, "ReturnValue", is_input=False), _pin(as_slot, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(as_slot, "execute"))
    slot = _loose_pin(as_slot, "AsWBPInventorySlot", is_input=False)

    valid, item = _item(ed, inv, index, x0 + 2860, y0 + 400)
    carried = _at(ed.add_branch_node(), x0 + 3120, y0)
    _connect(valid, _pin(carried, "Condition"))
    _connect(BEL.find_then_pin(as_slot), _pin(carried, "execute"))
    is_equipped = _at(_node(ed, FN_EQ_II), x0 + 3120, y0 + 400)
    _connect(index, _pin(is_equipped, "A"))
    _connect(equipped, _pin(is_equipped, "B"))
    _author_filled_slot(ed, slot, item, _pin(is_equipped, "ReturnValue", is_input=False),
                        BEL.find_then_pin(carried), x0 + 3400, y0)
    _author_empty_slot(ed, slot, BEL.find_else_pin(carried), x0 + 3400, y0 + 1400)

    ed.add_comment_to_nodes(
        "The inventory grid: slot i shows Inventory[i] -- its own icon in its "
        "own SlotColor, rounds-in-gun / rounds-in-reserve if it uses ammunition, "
        "and a lit background and frame if it is the equipped one. Slots past "
        "the end are emptied.", [cast, loop, as_slot, carried])
    return (_loose_pin(loop, "Completed", is_input=False),
            _pin(cast, "CastFailed", is_input=False))
