"""The two widgets the screens are built from: WBP_MenuRow (one line of any
menu: caret, label, value) and WBP_InventorySlot (one cell of the strip, of
the bag or of the worn grid), and the grid of slots the HUD lays them in.

A menu row carries its own label. Each instance's LabelText, LabelWidth and
LabelColor are set in the parent screen's designer and applied by the row's
PreConstruct, so the labels show in the UMG editor and the HUD never writes
them. What the HUD does write per frame is the caret's opacity (the selected
row) and the value column (a slider's number, a key's name, ON/OFF).
"""

import unreal

from combat.graph import (
    BEL, BGE, _apply_defaults, _at, _connect, _declare, _float_type, _must_load, _node,
    _palette, _pin,
)
from graphics_menu import umg_author as U
from graphics_menu.umg_consts import (
    COL_CARET, COL_GHOST, COL_KILL, COL_ROW, ROW_CARET, ROW_CARET_W, ROW_COLOR_VAR, ROW_FONT,
    ROW_ICON, ROW_ICON_H, ROW_ICON_W, ROW_LABEL, ROW_LABEL_BOX, ROW_LABEL_W,
    ROW_TEXT_VAR, ROW_VALUE, ROW_WIDTH_VAR,
    SLOT_ACTIVE, SLOT_AMMO, SLOT_AMMO_BOTTOM, SLOT_AMMO_FONT, SLOT_AMMO_RIGHT, SLOT_BACK,
    SLOT_FRAME, SLOT_GAP, SLOT_GHOST, SLOT_GHOST_VAR, SLOT_H, SLOT_ICON, SLOT_ICON_H,
    SLOT_ICON_TOP, SLOT_ICON_W, SLOT_W, UI_ART_DIR, WBP_INVENTORY_SLOT, WBP_MENU_ROW,
)
from item_icons.items import icon_name

NODE_PRE_CONSTRUCT = "AddEvent|UserInterface|EventPreConstruct"
FN_STR_TO_TEXT = "/Script/Engine.KismetTextLibrary.Conv_StringToText"
FN_SET_TEXT = "/Script/UMG.TextBlock.SetText"
FN_SET_TEXT_COLOUR = "/Script/UMG.TextBlock.SetColorAndOpacity"
FN_SET_WIDTH = "/Script/UMG.SizeBox.SetWidthOverride"
FN_SET_BRUSH = "/Script/UMG.Image.SetBrushFromTexture"


def _author_pre_construct(bp):
    """PreConstruct: Label = LabelText in LabelColor, LabelBox = LabelWidth wide."""
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    ed.remove_nodes(ed.list_all_nodes())
    pre = _palette(ed, NODE_PRE_CONSTRUCT)

    def get(var, x, y):
        return _pin(_at(ed.add_get_member_variable_node(var), x, y), var, is_input=False)

    as_text = _at(_node(ed, FN_STR_TO_TEXT), 300, 200)
    _connect(get(ROW_TEXT_VAR, 60, 200), _pin(as_text, "InString"))
    put = _at(_node(ed, FN_SET_TEXT), 560, 0)
    _connect(get(ROW_LABEL, 300, 80), _pin(put, "self"))
    _connect(_pin(as_text, "ReturnValue", is_input=False), _pin(put, "InText"))
    _connect(BEL.find_then_pin(pre), _pin(put, "execute"))

    tint = _at(_node(ed, FN_SET_TEXT_COLOUR), 860, 0)
    _connect(get(ROW_LABEL, 600, 240), _pin(tint, "self"))
    _connect(get(ROW_COLOR_VAR, 600, 320), _pin(tint, "InColorAndOpacity"))
    _connect(BEL.find_then_pin(put), _pin(tint, "execute"))

    width = _at(_node(ed, FN_SET_WIDTH), 1160, 0)
    _connect(get(ROW_LABEL_BOX, 900, 240), _pin(width, "self"))
    _connect(get(ROW_WIDTH_VAR, 900, 320), _pin(width, "InWidthOverride"))
    _connect(BEL.find_then_pin(tint), _pin(width, "execute"))


def build_menu_row():
    bp = U.widget_blueprint(WBP_MENU_ROW)
    root = U.add(bp, unreal.HorizontalBox, "Row")
    caret_box = U.sized(bp, root, "CaretBox", w=ROW_CARET_W)
    caret = U.text(bp, caret_box, ROW_CARET, ">", ROW_FONT, COL_CARET, variable=True)
    # Unselected by default; the HUD lifts the selected row's to 1 each frame.
    caret.set_editor_property("render_opacity", 0.0)
    label_box = U.sized(bp, root, ROW_LABEL_BOX, w=ROW_LABEL_W, variable=True)
    U.text(bp, label_box, ROW_LABEL, "LABEL", ROW_FONT, COL_ROW, variable=True)
    value = U.text(bp, root, ROW_VALUE, "", ROW_FONT, COL_CARET, variable=True)
    # The loot window's rows show an item's icon here (loot_draw.py).
    icon = U.image(bp, root, ROW_ICON, "T_UI_Slot", (ROW_ICON_W, ROW_ICON_H),
                   variable=True)
    U.pad(icon, v="Center")
    U.hide(icon)
    for w in (caret_box, label_box, value):
        U.pad(w, v="Center")
    U.compile_and_save(bp)   # the widget variables exist once compiled

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    _declare(ed, ROW_TEXT_VAR, BEL.get_basic_type_by_name("string"))
    _declare(ed, ROW_WIDTH_VAR, _float_type())
    _declare(ed, ROW_COLOR_VAR, BEL.get_struct_type(unreal.SlateColor.static_struct()))
    for var in (ROW_TEXT_VAR, ROW_WIDTH_VAR, ROW_COLOR_VAR):
        BEL.set_blueprint_variable_instance_editable(bp, var, True)
    _author_pre_construct(bp)
    U.compile_and_save(bp)
    # The colour is written alongside and compared as text: _same() walks a
    # struct's to_tuple(), and a SlateColor's nests a LinearColor in it.
    unreal.get_default_object(BEL.generated_class(bp)).set_editor_property(
        ROW_COLOR_VAR, U.slate_colour(COL_ROW))
    _apply_defaults(bp, {ROW_TEXT_VAR: "", ROW_WIDTH_VAR: ROW_LABEL_W})
    got = unreal.get_default_object(BEL.generated_class(bp)).get_editor_property(ROW_COLOR_VAR)
    if got.export_text() != U.slate_colour(COL_ROW).export_text():
        raise RuntimeError(f"{ROW_COLOR_VAR} default did not stick: {got.export_text()}")
    return U.compile_and_save(bp)


def build_inventory_slot():
    """An empty slot, with the carried-item layers collapsed until the HUD
    fills them: the lit background and frame of the equipped slot, the
    weapon's icon, and its rounds-in-gun / rounds-in-reserve; and the Ghost,
    the instance's GhostTexture drawn translucent (PreConstruct sets it),
    which the HUD shows in an empty slot that has one."""
    bp = U.widget_blueprint(WBP_INVENTORY_SLOT)
    root = U.sized(bp, None, "Cell", w=SLOT_W, h=SLOT_H)
    stack = U.add(bp, unreal.Overlay, "Stack", root)
    back = U.image(bp, stack, SLOT_BACK, "T_UI_Slot")
    U.pad(back, h="Fill", v="Fill")
    active = U.image(bp, stack, SLOT_ACTIVE, "T_UI_SlotActive", variable=True)
    U.pad(active, h="Fill", v="Fill")
    ghost = U.image(bp, stack, SLOT_GHOST, "T_UI_Slot", (SLOT_ICON_W, SLOT_ICON_H),
                    variable=True, tint=COL_GHOST)
    icon = U.image(bp, stack, SLOT_ICON, "T_UI_Slot", (SLOT_ICON_W, SLOT_ICON_H),
                   variable=True)
    for w in (ghost, icon):
        U.pad(w, top=SLOT_ICON_TOP, h="Center", v="Top")
    ammo = U.text(bp, stack, SLOT_AMMO, "", SLOT_AMMO_FONT, COL_KILL, variable=True)
    U.pad(ammo, right=SLOT_AMMO_RIGHT, bottom=SLOT_AMMO_BOTTOM, h="Right", v="Bottom")
    frame = U.image(bp, stack, SLOT_FRAME, "T_UI_SlotFrame", variable=True)
    U.pad(frame, h="Fill", v="Fill")
    for w in (active, ghost, icon, ammo, frame):
        U.hide(w)
    U.compile_and_save(bp)   # the widget variables exist once compiled

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    _declare(ed, SLOT_GHOST_VAR,
             BEL.get_object_reference_type(unreal.Texture2D.static_class()))
    BEL.set_blueprint_variable_instance_editable(bp, SLOT_GHOST_VAR, True)
    ed.remove_nodes(ed.list_all_nodes())
    pre = _palette(ed, NODE_PRE_CONSTRUCT)
    put = _at(_node(ed, FN_SET_BRUSH), 560, 0)
    for var, pin, y in ((SLOT_GHOST, "self", 80), (SLOT_GHOST_VAR, "Texture", 200)):
        got = _at(ed.add_get_member_variable_node(var), 300, y)
        _connect(_pin(got, var, is_input=False), _pin(put, pin))
    _connect(BEL.find_then_pin(pre), _pin(put, "execute"))
    return U.compile_and_save(bp)


def slot_grid(bp, parent, name, cells, columns, prefix, ghosts=None):
    """A UniformGridPanel of ``cells`` WBP_InventorySlots, a gap apart.
    ``ghosts``: per cell, the item whose icon is its empty silhouette."""
    grid = U.add(bp, unreal.UniformGridPanel, name, parent, variable=True)
    half = SLOT_GAP / 2.0
    grid.set_editor_property("slot_padding", unreal.Margin(half, half, half, half))
    slot_class = BEL.generated_class(_must_load(WBP_INVENTORY_SLOT))
    for i in range(cells):
        cell = U.add(bp, slot_class, f"{prefix}{i}", grid)
        if ghosts:
            cell.set_editor_property(
                SLOT_GHOST_VAR, _must_load(f"{UI_ART_DIR}/{icon_name(ghosts[i])}"))
        U.cell(cell, i // columns, i % columns)
    return grid
