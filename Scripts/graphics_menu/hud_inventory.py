"""DrawHUD: the inventory's slots -- WBP_HUD's hand slot, four weapon slots
and ten bag slots (WBP_InventorySlot each) and the held item's name above
the hand -- filled from the weapon component.

Everything shown comes off the carried item itself (Icon, SlotColor,
DisplayName, UsesAmmo, Loaded, Reserve, InfiniteReserve), so the HUD keeps no table of weapons
and no idea which of them has a magazine. One loop over the fifteen slot
codes (combat/slot_tuning.py): code c's widget is the hand's cell, a weapon
cell or a bag cell (inv_consts.SLOT_BOXES), and it shows the component's
SlotItems[c], read behind IsValidIndex and then IsValid; an empty slot is
emptied, every frame, so a dropped weapon leaves nothing behind; an empty
slot that has a silhouette (its GhostTexture: the weapon slots, the worn
ones) shows it. All three grids are always shown, but the bag's hides under
the menu. wear_draw.py fills the worn grid's slots with the same two
fragments.

A lit slot gets a lit background AND a lit frame over its icon -- a lit
edge alone was reported as not reading: the hand's, the bag slot under the
I panel's caret, and the slot a drag started on.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import FN_AND, FN_IS_VALID, FN_LESS_II, FN_NOT, FN_OR, FN_SUB_II
from combat.slot_tuning import HAND, SLOT_COUNT, SLOT_ITEMS_VAR
from graphics_menu.inv_consts import BAG_PANEL, DRAG_FROM_VAR, SEL_TO_CODE, SLOT_BOXES
from graphics_menu.ui_graph import (
    FN_CHILD_AT, MACRO_FOR_LOOP, member, part, set_shown, set_text, show_if,
)
from graphics_menu.umg_consts import (
    EQUIPPED_NAME, SLOT_ACTIVE, SLOT_AMMO, SLOT_FRAME, SLOT_GHOST, SLOT_GHOST_VAR,
    SLOT_ICON, WBP_HUD, WBP_INVENTORY_SLOT,
)
from graphics_menu.wear_consts import WEAR_OPEN_VAR, WEAR_PORTRAIT, WEAR_SEL_VAR

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
FN_SELECT_OBJ = "/Script/Engine.KismetMathLibrary.SelectObject"
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


def _author_filled_slot(ed, slot, item, is_equipped, exec_in, x0, y0, ammo=True):
    """Icon in the item's colour (the empty slot's silhouette put away), its
    ammunition if it counts any (``ammo`` False: a worn slot, which counts
    none), and the equipped slot's lit layers. Returns the exec tails."""
    def w(name, py):
        return member(ed, slot, WBP_INVENTORY_SLOT, name, x0, py)

    icon = w(SLOT_ICON, y0 + 300)
    no_ghost = set_shown(ed, w(SLOT_GHOST, y0 - 200), False, [exec_in], x0, y0 - 300)
    brush = _at(_node(ed, FN_SET_BRUSH), x0 + 260, y0)
    _connect(icon, _pin(brush, "self"))
    _connect(_get(ed, item, "Icon", x0, y0 + 440), _pin(brush, "Texture"))
    _connect(no_ghost, _pin(brush, "execute"))
    tint = _at(_node(ed, FN_SET_TINT), x0 + 520, y0)
    _connect(icon, _pin(tint, "self"))
    _connect(_get(ed, item, "SlotColor", x0 + 260, y0 + 440), _pin(tint, "InColorAndOpacity"))
    _connect(BEL.find_then_pin(brush), _pin(tint, "execute"))
    flow = set_shown(ed, icon, True, [BEL.find_then_pin(tint)], x0 + 780, y0)
    active, frame = w(SLOT_ACTIVE, y0 + 900), w(SLOT_FRAME, y0 + 1000)
    if not ammo:
        tails = (set_shown(ed, w(SLOT_AMMO, y0 + 700), False, [flow], x0 + 1040, y0),)
        lit = show_if(ed, active, is_equipped, tails, x0 + 1300, y0)
        return show_if(ed, frame, is_equipped, lit, x0 + 1820, y0)

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

    lit = show_if(ed, active, is_equipped, tails, x0 + 2300, y0)
    return show_if(ed, frame, is_equipped, lit, x0 + 2820, y0)


def _author_empty_slot(ed, slot, execs, x0, y0):
    """Every carried-item layer collapsed, and the slot's silhouette shown
    if it has one. Returns the exec tails."""
    flow = tuple(execs)
    for i, name in enumerate((SLOT_ICON, SLOT_AMMO, SLOT_ACTIVE, SLOT_FRAME)):
        target = member(ed, slot, WBP_INVENTORY_SLOT, name, x0 + i * 260, y0 + 240)
        flow = (set_shown(ed, target, False, flow, x0 + i * 260, y0),)
    has = _at(_node(ed, FN_IS_VALID), x0 + 1040, y0 + 400)
    _connect(member(ed, slot, WBP_INVENTORY_SLOT, SLOT_GHOST_VAR, x0 + 1040, y0 + 540),
             _pin(has, "Object"))
    return show_if(ed, member(ed, slot, WBP_INVENTORY_SLOT, SLOT_GHOST, x0 + 1040, y0 + 240),
                   _pin(has, "ReturnValue", is_input=False), flow, x0 + 1300, y0)


def _slot_widget(ed, code, x0, y0):
    """Code ``code``'s WBP_InventorySlot (as a UObject): the hand's cell, a
    weapon cell or a bag cell. GetChildAt past a grid's end is None, never
    an error, so all three are read and the code picks one."""
    (hand_box, _h, _n), (weapon_box, first_weapon, _w), (bag_box, first_bag, _b) = SLOT_BOXES
    kids = []
    for i, (box, first) in enumerate(((hand_box, 0), (weapon_box, first_weapon),
                                      (bag_box, first_bag))):
        at = _at(_node(ed, FN_SUB_II), x0, y0 + i * 300)
        _connect(code, _pin(at, "A"))
        _set(at, "B", first)
        child = _at(_node(ed, FN_CHILD_AT), x0 + 260, y0 + i * 300)
        _connect(part(ed, WBP_HUD, box, x0, y0 + i * 300 + 140), _pin(child, "self"))
        _connect(_pin(at, "ReturnValue", is_input=False), _pin(child, "Index"))
        kids.append(_pin(child, "ReturnValue", is_input=False))
    in_bag = _at(_node(ed, FN_LESS_II), x0 + 520, y0 + 900)
    _connect(code, _pin(in_bag, "A"))
    _set(in_bag, "B", first_bag)
    near = _at(_node(ed, FN_SELECT_OBJ), x0 + 780, y0 + 300)
    _connect(kids[1], _pin(near, "A"))
    _connect(kids[2], _pin(near, "B"))
    _connect(_pin(in_bag, "ReturnValue", is_input=False), _pin(near, "bSelectA"))
    is_hand = _at(_node(ed, FN_EQ_II), x0 + 780, y0 + 900)
    _connect(code, _pin(is_hand, "A"))
    _set(is_hand, "B", HAND)
    pick = _at(_node(ed, FN_SELECT_OBJ), x0 + 1040, y0)
    _connect(kids[0], _pin(pick, "A"))
    _connect(_pin(near, "ReturnValue", is_input=False), _pin(pick, "B"))
    _connect(_pin(is_hand, "ReturnValue", is_input=False), _pin(pick, "bSelectA"))
    return _pin(pick, "ReturnValue", is_input=False), _pin(is_hand, "ReturnValue",
                                                         is_input=False)


def _lit(ed, code, is_hand, x0, y0):
    """The hand's slot, the bag slot under the open panel's caret, and the
    slot a drag started on (a pure bool)."""
    def var(name, y):
        return _pin(_at(ed.add_get_member_variable_node(name), x0, y), name, is_input=False)

    def node(fn, a, b, y):
        n = _at(_node(ed, fn), x0 + 260, y)
        _connect(a, _pin(n, "A"))
        if isinstance(b, int):
            _set(n, "B", b)
        else:
            _connect(b, _pin(n, "B"))
        return _pin(n, "ReturnValue", is_input=False)

    sel_code = node(FN_SUB_II, var(WEAR_SEL_VAR, y0), SEL_TO_CODE, y0)
    caret = node(FN_AND, var(WEAR_OPEN_VAR, y0 + 140),
                 node(FN_EQ_II, code, sel_code, y0 + 140), y0 + 280)
    dragged = node(FN_EQ_II, code, var(DRAG_FROM_VAR, y0 + 420), y0 + 420)
    return node(FN_OR, node(FN_OR, is_hand, caret, y0 + 560), dragged, y0 + 700)


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

    items = _at(ed.add_get_member_variable_node(SLOT_ITEMS_VAR, WEAPON_COMP_CLASS_PATH),
                x0 + 760, y0 + 540)
    _connect(as_weapon, _pin(items, "self"))
    items = _pin(items, SLOT_ITEMS_VAR, is_input=False)

    # The bag's grid always, but never under the menu.
    open_ = _at(ed.add_get_member_variable_node(WEAR_OPEN_VAR), x0 + 1760, y0 + 700)
    menu = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 1760, y0 + 840)
    no_menu = _at(_node(ed, FN_NOT), x0 + 2000, y0 + 840)
    _connect(_pin(menu, "MenuOpen", is_input=False), _pin(no_menu, "A"))
    bag_up = _at(_node(ed, FN_AND), x0 + 2240, y0 + 700)
    _connect(_pin(open_, WEAR_OPEN_VAR, is_input=False), _pin(bag_up, "A"))
    _connect(_pin(no_menu, "ReturnValue", is_input=False), _pin(bag_up, "B"))
    shown = show_if(ed, part(ed, WBP_HUD, BAG_PANEL, x0 + 1760, y0 + 1000),
                    _pin(no_menu, "ReturnValue", is_input=False), named, x0 + 2000, y0)
    # The character's portrait with the I panel open.
    shown = show_if(ed, part(ed, WBP_HUD, WEAR_PORTRAIT, x0 + 1760, y0 - 700),
                    _pin(bag_up, "ReturnValue", is_input=False), list(shown),
                    x0 + 2000, y0 - 600)

    # Slot code c, over every code.
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    _at(loop, x0 + 2600, y0)
    _set(loop, "FirstIndex", 0)
    _set(loop, "LastIndex", SLOT_COUNT - 1)
    for e in shown:
        _connect(e, _pin(loop, "execute"))
    index = _loose_pin(loop, "Index", is_input=False)
    widget, is_hand = _slot_widget(ed, index, x0 + 2600, y0 + 400)
    as_slot = _at(_palette(ed, NODE_CAST_SLOT), x0 + 3900, y0)
    _connect(widget, _pin(as_slot, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(as_slot, "execute"))
    slot = _loose_pin(as_slot, "AsWBPInventorySlot", is_input=False)

    valid, item = _item(ed, items, index, x0 + 3900, y0 + 400)
    carried = _at(ed.add_branch_node(), x0 + 4160, y0)
    _connect(valid, _pin(carried, "Condition"))
    _connect(BEL.find_then_pin(as_slot), _pin(carried, "execute"))
    there = _at(_node(ed, FN_IS_VALID), x0 + 4160, y0 + 400)
    _connect(item, _pin(there, "Object"))
    filled = _at(ed.add_branch_node(), x0 + 4420, y0)
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(filled, "Condition"))
    _connect(BEL.find_then_pin(carried), _pin(filled, "execute"))
    _author_filled_slot(ed, slot, item, _lit(ed, index, is_hand, x0 + 4420, y0 + 600),
                        BEL.find_then_pin(filled), x0 + 4700, y0)
    _author_empty_slot(ed, slot, (BEL.find_else_pin(carried), BEL.find_else_pin(filled)),
                       x0 + 4700, y0 + 1400)
    ed.add_comment_to_nodes(
        "The inventory's slots: code c's widget (the hand, a weapon slot, a bag "
        "slot) shows SlotItems[c] -- its own icon in its own SlotColor, "
        "rounds-in-gun / rounds-in-reserve if it uses ammunition, and a lit "
        "background and frame on the hand, the caret and a drag's start. Empty "
        "slots are emptied, down to their silhouette.", [cast, loop, as_slot, carried])
    return (_loose_pin(loop, "Completed", is_input=False),
            _pin(cast, "CastFailed", is_input=False))
