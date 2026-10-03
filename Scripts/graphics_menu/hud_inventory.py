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

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from combat.slot_tuning import HAND, SLOT_COUNT, SLOT_ITEMS_VAR
from graphics_menu.inv_consts import BAG_PANEL, DRAG_FROM_VAR, SEL_TO_CODE, SLOT_BOXES
from graphics_menu.ui_graph import member, part, set_shown, set_text, show_if
from graphics_menu.umg_consts import (
    EQUIPPED_NAME, SLOT_ACTIVE, SLOT_AMMO, SLOT_FRAME, SLOT_GHOST, SLOT_GHOST_VAR,
    SLOT_ICON, WBP_HUD, WBP_INVENTORY_SLOT,
)
from graphics_menu.wear_consts import WEAR_OPEN_VAR, WEAR_PORTRAIT, WEAR_SEL_VAR
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.array import FN_ARR_GET, FN_ARR_VALID
from uebp.nodes.math import (
    FN_AND, FN_EQ_II, FN_LESS_II, FN_NOT, FN_OR, FN_SELECT_OBJ, FN_SELECT_STR, FN_SUB_II)
from uebp.nodes.palette import MACRO_FOR_LOOP, NODE_CAST_SLOT, NODE_CAST_WEAPON
from uebp.nodes.system import FN_CONCAT, FN_GET_PLAYER_PAWN, FN_INT_TO_STR, FN_IS_VALID
from uebp.nodes.umg import FN_CHILD_AT, FN_SET_BRUSH, FN_SET_TINT
from combat import item_vars as IV
from graphics_menu import hud_vars as MV
from combat.weapon_component import vars as WV

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
ITEM_CLASS_PATH = "/Game/Weapons/BP_WeaponItem.BP_WeaponItem_C"

# What an InfiniteReserve weapon (the pistol) shows for its reserve.
INFINITE_RESERVE_TEXT = "\u221e"


def _item(ed, inv, index):
    """(IsValidIndex(inv, index), inv[index]) -- read the item only behind the
    first, or an empty slot is an Accessed None per frame."""
    valid = _node(ed, FN_ARR_VALID)
    _connect(inv, _loose_pin(valid, "TargetArray"))
    _connect(index, _pin(valid, "IndexToTest"))
    got = _node(ed, FN_ARR_GET)
    _connect(inv, _loose_pin(got, "TargetArray"))
    _connect(index, _pin(got, "Index"))
    return (out(valid), _loose_pin(got, "Item", is_input=False))


def _get(ed, item, var):
    n = ed.add_get_member_variable_node(var, ITEM_CLASS_PATH)
    _connect(item, _pin(n, "self"))
    return out(n, var)


def _author_equipped_name(ed, inv, equipped, exec_in):
    valid, item = _item(ed, inv, equipped)
    br = ed.add_branch_node()
    _connect(valid, _pin(br, "Condition"))
    _connect(exec_in, _pin(br, "execute"))
    name = part(ed, WBP_HUD, EQUIPPED_NAME)
    said = set_text(ed, name, _get(ed, item, IV.DisplayName), [then(br)])
    return (set_shown(ed, name, True, [said]), set_shown(ed, name, False, [else_(br)]))


def _author_filled_slot(ed, slot, item, is_equipped, exec_in, ammo=True):
    """Icon in the item's colour (the empty slot's silhouette put away), its
    ammunition if it counts any (``ammo`` False: a worn slot, which counts
    none), and the equipped slot's lit layers. Returns the exec tails."""
    def w(name):
        return member(ed, slot, WBP_INVENTORY_SLOT, name)

    icon = w(SLOT_ICON)
    no_ghost = set_shown(ed, w(SLOT_GHOST), False, [exec_in])
    brush = _node(ed, FN_SET_BRUSH)
    _connect(icon, _pin(brush, "self"))
    _connect(_get(ed, item, IV.Icon), _pin(brush, "Texture"))
    _connect(no_ghost, _pin(brush, "execute"))
    tint = _node(ed, FN_SET_TINT)
    _connect(icon, _pin(tint, "self"))
    _connect(_get(ed, item, IV.SlotColor), _pin(tint, "InColorAndOpacity"))
    _connect(then(brush), _pin(tint, "execute"))
    flow = set_shown(ed, icon, True, [then(tint)])
    active, frame = w(SLOT_ACTIVE), w(SLOT_FRAME)
    if not ammo:
        tails = (set_shown(ed, w(SLOT_AMMO), False, [flow]),)
        lit = show_if(ed, active, is_equipped, tails)
        return show_if(ed, frame, is_equipped, lit)

    # "3 / 15": rounds in the gun, rounds in reserve. Only for a weapon that
    # uses ammunition. The pistol reloads every eight shots over an endless
    # reserve, so it reads "5 / ∞": the magazine is the part to manage.
    loaded = _node(ed, FN_INT_TO_STR)
    _connect(_get(ed, item, IV.Loaded), _pin(loaded, "InInt"))
    reserve = _node(ed, FN_INT_TO_STR)
    _connect(_get(ed, item, IV.Reserve), _pin(reserve, "InInt"))
    spare = _node(ed, FN_SELECT_STR)
    _set(spare, "A", INFINITE_RESERVE_TEXT)
    _connect(out(reserve), _pin(spare, "B"))
    _connect(_get(ed, item, IV.InfiniteReserve), _pin(spare, "bPickA"))
    sep = _node(ed, FN_CONCAT)
    _set(sep, "A", " / ")
    _connect(out(spare), _pin(sep, "B"))
    count = _node(ed, FN_CONCAT)
    _connect(out(loaded), _pin(count, "A"))
    _connect(out(sep), _pin(count, "B"))

    ammo = w(SLOT_AMMO)
    counted = ed.add_branch_node()
    _connect(_get(ed, item, IV.UsesAmmo), _pin(counted, "Condition"))
    _connect(flow, _pin(counted, "execute"))
    wrote = set_text(ed, ammo, out(count), [then(counted)])
    tails = (set_shown(ed, ammo, True, [wrote]), set_shown(ed, ammo, False, [else_(counted)]))

    lit = show_if(ed, active, is_equipped, tails)
    return show_if(ed, frame, is_equipped, lit)


def _author_empty_slot(ed, slot, execs):
    """Every carried-item layer collapsed, and the slot's silhouette shown
    if it has one. Returns the exec tails."""
    flow = tuple(execs)
    for name in (SLOT_ICON, SLOT_AMMO, SLOT_ACTIVE, SLOT_FRAME):
        target = member(ed, slot, WBP_INVENTORY_SLOT, name)
        flow = (set_shown(ed, target, False, flow),)
    has = _node(ed, FN_IS_VALID)
    _connect(member(ed, slot, WBP_INVENTORY_SLOT, SLOT_GHOST_VAR), _pin(has, "Object"))
    return show_if(ed, member(ed, slot, WBP_INVENTORY_SLOT, SLOT_GHOST), out(has), flow)


def _slot_widget(ed, code):
    """Code ``code``'s WBP_InventorySlot (as a UObject): the hand's cell, a
    weapon cell or a bag cell. GetChildAt past a grid's end is None, never
    an error, so all three are read and the code picks one."""
    (hand_box, _h, _n), (weapon_box, first_weapon, _w), (bag_box, first_bag, _b) = SLOT_BOXES
    kids = []
    for box, first in ((hand_box, 0), (weapon_box, first_weapon), (bag_box, first_bag)):
        at = _node(ed, FN_SUB_II)
        _connect(code, _pin(at, "A"))
        _set(at, "B", first)
        child = _node(ed, FN_CHILD_AT)
        _connect(part(ed, WBP_HUD, box), _pin(child, "self"))
        _connect(out(at), _pin(child, "Index"))
        kids.append(out(child))
    in_bag = _node(ed, FN_LESS_II)
    _connect(code, _pin(in_bag, "A"))
    _set(in_bag, "B", first_bag)
    near = _node(ed, FN_SELECT_OBJ)
    _connect(kids[1], _pin(near, "A"))
    _connect(kids[2], _pin(near, "B"))
    _connect(out(in_bag), _pin(near, "bSelectA"))
    is_hand = _node(ed, FN_EQ_II)
    _connect(code, _pin(is_hand, "A"))
    _set(is_hand, "B", HAND)
    pick = _node(ed, FN_SELECT_OBJ)
    _connect(kids[0], _pin(pick, "A"))
    _connect(out(near), _pin(pick, "B"))
    _connect(out(is_hand), _pin(pick, "bSelectA"))
    return out(pick), out(is_hand)


def _lit(ed, code, is_hand):
    """The hand's slot, the bag slot under the open panel's caret, and the
    slot a drag started on (a pure bool)."""
    def var(name):
        return out(ed.add_get_member_variable_node(name), name)

    def node(fn, a, b):
        n = _node(ed, fn)
        _connect(a, _pin(n, "A"))
        if isinstance(b, int):
            _set(n, "B", b)
        else:
            _connect(b, _pin(n, "B"))
        return out(n)

    sel_code = node(FN_SUB_II, var(WEAR_SEL_VAR), SEL_TO_CODE)
    caret = node(FN_AND, var(WEAR_OPEN_VAR), node(FN_EQ_II, code, sel_code))
    dragged = node(FN_EQ_II, code, var(DRAG_FROM_VAR))
    return node(FN_OR, node(FN_OR, is_hand, caret), dragged)


def author_inventory(ed, in_execs):
    """Returns the exec pins to go on from; a pawn with no weapon component
    still reaches the rest of the HUD."""
    pawn = _node(ed, FN_GET_PLAYER_PAWN)
    _set(pawn, "PlayerIndex", 0)
    comp = _node(ed, FN_GET_COMP)
    _connect(out(pawn), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = _palette(ed, NODE_CAST_WEAPON)
    _connect(out(comp), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    inv = ed.add_get_member_variable_node(WV.Inventory, WEAPON_COMP_CLASS_PATH)
    _connect(as_weapon, _pin(inv, "self"))
    inv = out(inv, WV.Inventory)
    equipped = ed.add_get_member_variable_node(WV.EquippedIndex, WEAPON_COMP_CLASS_PATH)
    _connect(as_weapon, _pin(equipped, "self"))
    equipped = out(equipped, WV.EquippedIndex)

    named = _author_equipped_name(ed, inv, equipped, then(cast))

    items = ed.add_get_member_variable_node(SLOT_ITEMS_VAR, WEAPON_COMP_CLASS_PATH)
    _connect(as_weapon, _pin(items, "self"))
    items = out(items, SLOT_ITEMS_VAR)

    # The bag's grid always, but never under the menu.
    open_ = ed.add_get_member_variable_node(WEAR_OPEN_VAR)
    menu = ed.add_get_member_variable_node(MV.MenuOpen)
    no_menu = _node(ed, FN_NOT)
    _connect(out(menu, MV.MenuOpen), _pin(no_menu, "A"))
    bag_up = _node(ed, FN_AND)
    _connect(out(open_, WEAR_OPEN_VAR), _pin(bag_up, "A"))
    _connect(out(no_menu), _pin(bag_up, "B"))
    shown = show_if(ed, part(ed, WBP_HUD, BAG_PANEL), out(no_menu), named)
    # The character's portrait with the I panel open.
    shown = show_if(ed, part(ed, WBP_HUD, WEAR_PORTRAIT), out(bag_up), list(shown))

    # Slot code c, over every code.
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    loop
    _set(loop, "FirstIndex", 0)
    _set(loop, "LastIndex", SLOT_COUNT - 1)
    for e in shown:
        _connect(e, _pin(loop, "execute"))
    index = _loose_pin(loop, "Index", is_input=False)
    widget, is_hand = _slot_widget(ed, index)
    as_slot = _palette(ed, NODE_CAST_SLOT)
    _connect(widget, _pin(as_slot, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(as_slot, "execute"))
    slot = _loose_pin(as_slot, "AsWBPInventorySlot", is_input=False)

    valid, item = _item(ed, items, index)
    carried = ed.add_branch_node()
    _connect(valid, _pin(carried, "Condition"))
    _connect(then(as_slot), _pin(carried, "execute"))
    there = _node(ed, FN_IS_VALID)
    _connect(item, _pin(there, "Object"))
    filled = ed.add_branch_node()
    _connect(out(there), _pin(filled, "Condition"))
    _connect(then(carried), _pin(filled, "execute"))
    _author_filled_slot(ed, slot, item, _lit(ed, index, is_hand), then(filled))
    _author_empty_slot(ed, slot, (else_(carried), else_(filled)))
    ed.add_comment_to_nodes(
        "The inventory's slots: code c's widget (the hand, a weapon slot, a bag "
        "slot) shows SlotItems[c] -- its own icon in its own SlotColor, "
        "rounds-in-gun / rounds-in-reserve if it uses ammunition, and a lit "
        "background and frame on the hand, the caret and a drag's start. Empty "
        "slots are emptied, down to their silhouette.", [cast, loop, as_slot, carried])
    return (_loose_pin(loop, "Completed", is_input=False), out(cast, "CastFailed"))
