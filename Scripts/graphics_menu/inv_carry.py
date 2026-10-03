"""DrawHUD: the item a drag carries, on the mouse cursor, and the view held
still while it is carried (inv_drag.py starts and ends the drag).

    with the I panel open (author_carry_icon, after the drag's fragment):
        InvDragFrom a slot's code, and the item there valid (SlotItems[code],
        or Worn[code - WORN_CODE_FIRST]) ->
            DragIcon's picture := the item's Icon, DragIcon moved onto the
            cursor (CursorPos in the Body's own space) and shown
        otherwise DragIcon collapsed
    on every path of the panel's draw (author_carry_end):
        the panel not open (I shut it, the menu is up, the player died) ->
            InvDragFrom := NO_SLOT, DragIcon collapsed: a drag is called off
        (InvDragFrom >= 0) != InvLookHeld ->
            InvLookHeld := it, controller.SetIgnoreLookInput(InvLookHeld)

The icon is one Image on WBP_HUD's root, over everything, its centre on the
canvas's corner: its render translation is the cursor's place. The look is
held because the game still has the mouse with the cursor shown (Game-and-UI:
the left button held captures it, and the view turned with the drag).
SetIgnoreLookInput counts its calls, as SetIgnoreMoveInput does, so it is
made on the drag's edges only; InvLookHeld is that edge's memory.
"""

from uebp.graph import BEL, _connect, _declare, _pin, out, then
from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import SLOT_ITEMS_VAR
from combat import item_vars as IV
from graphics_menu.cursor import _pc
from graphics_menu.cursor_consts import CURSOR_POS_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.inv_consts import (
    DRAG_FROM_VAR, DRAG_ICON, LOOK_HELD_VAR, NO_SLOT, WORN_CODE_FIRST,
)
from graphics_menu.loot_find import put
from graphics_menu.ui_graph import part, set_shown
from graphics_menu.umg_consts import HUD_BODY, WBP_HUD
from graphics_menu.wear_consts import WEAR_OPEN_VAR
from uebp.nodes.actor import FN_IGNORE_LOOK
from uebp.nodes.array import FN_ARR_GET, FN_ARR_VALID
from uebp.nodes.math import FN_AND, FN_GE_II, FN_LESS_II, FN_NEQ_BB, FN_NOT, FN_SUB_II
from uebp.nodes.system import FN_IS_VALID
from uebp.nodes.umg import FN_ABS_TO_LOCAL, FN_GEOMETRY, FN_SET_BRUSH, FN_SET_TRANSLATION
from graphics_menu import hud_vars as MV


def declare_carry_vars(ed):
    """The HUD's look-held memory. Default: carry_defaults()."""
    _declare(ed, LOOK_HELD_VAR, BEL.get_basic_type_by_name("bool"))


def carry_defaults():
    return {LOOK_HELD_VAR: False}


def _dragging(ed, made):
    return out(_call(ed, FN_GE_II, made, A=_get(ed, DRAG_FROM_VAR, made), B=0))


def _pictured(ed, icon, array, index, in_execs, made):
    """DragIcon's picture := array[index]'s Icon, behind IsValidIndex and
    IsValid. Returns (the exec after the brush, the tails that drew none)."""
    known, wild = _branch(ed, out(_call(ed, FN_ARR_VALID, made, TargetArray=array,
                                        IndexToTest=index)), in_execs, made)
    item = out(_call(ed, FN_ARR_GET, made, TargetArray=array, Index=index), "Item")
    there, gone = _branch(ed, out(_call(ed, FN_IS_VALID, made, Object=item)), [known], made)
    brush = _call(ed, FN_SET_BRUSH, made, self=icon,
                  Texture=_get(ed, IV.Icon, made, ITEM_CLASS_PATH, item))
    _connect(there, _pin(brush, "execute"))
    return then(brush), [wild, gone]


def author_carry_icon(ed, wc, worn, in_execs):
    """The carried item's icon on the cursor (see the module docstring).
    ``wc``: the cast weapon component's pin; ``worn``: its Worn. Returns the
    exec tails."""
    made = []
    icon = part(ed, WBP_HUD, DRAG_ICON)
    start = _get(ed, DRAG_FROM_VAR, made)
    on, off = _branch(ed, _dragging(ed, made), in_execs, made)
    slot, garment = _branch(ed, out(_call(ed, FN_LESS_II, made, A=start, B=WORN_CODE_FIRST)),
                            [on], made)
    items = _get(ed, SLOT_ITEMS_VAR, made, WEAPON_COMP_CLASS_PATH, wc)
    carried, none = _pictured(ed, icon, items, start, [slot], made)
    at = out(_call(ed, FN_SUB_II, made, A=start, B=WORN_CODE_FIRST))
    dressed, bare = _pictured(ed, icon, worn, at, [garment], made)
    # Onto the cursor: its place in the Body's space, the canvas the icon is on.
    geo = _call(ed, FN_GEOMETRY, made, self=part(ed, WBP_HUD, HUD_BODY))
    local = _call(ed, FN_ABS_TO_LOCAL, made, Geometry=out(geo),
                  AbsoluteCoordinate=_get(ed, CURSOR_POS_VAR, made))
    move = _call(ed, FN_SET_TRANSLATION, made, self=icon, Translation=out(local))
    for e in (carried, dressed):
        _connect(e, _pin(move, "execute"))
    shown = set_shown(ed, icon, True, [then(move)])
    hidden = set_shown(ed, icon, False, [off] + none + bare)
    ed.add_comment_to_nodes(
        "A drag in the I panel carries the item's icon on the mouse cursor: "
        "DragIcon shows InvDragFrom's item (a slot's, or a worn garment), moved "
        "to the cursor every frame (inv_carry.py).", made[:4])
    return [shown, hidden]


def author_carry_end(ed, in_execs):
    """On every path of the panel's draw: a drag is called off with the panel
    not open, and the look is held while one is on. Returns the exec tails."""
    made = []
    up = _call(ed, FN_AND, made, A=_get(ed, WEAR_OPEN_VAR, made),
               B=out(_call(ed, FN_NOT, made, A=_get(ed, MV.MenuOpen, made))))
    stay, shut = _branch(ed, out(up), in_execs, made)
    flow = _setter(ed, DRAG_FROM_VAR, NO_SLOT, [shut], made)
    flow = set_shown(ed, part(ed, WBP_HUD, DRAG_ICON), False, [flow])
    changed = _call(ed, FN_NEQ_BB, made, A=_dragging(ed, made),
                    B=_get(ed, LOOK_HELD_VAR, made))
    edge, same = _branch(ed, out(changed), [stay, flow], made)
    flow = put(ed, LOOK_HELD_VAR, _dragging(ed, made), [edge], made)
    hold = _call(ed, FN_IGNORE_LOOK, made, self=_pc(ed, made),
                 bNewLookInput=_get(ed, LOOK_HELD_VAR, made))
    _connect(flow, _pin(hold, "execute"))
    ed.add_comment_to_nodes(
        "While a drag carries an item the mouse does not turn the view: "
        "SetIgnoreLookInput on the drag's edges only (it counts its calls). A "
        "drag is called off when the panel is not open (inv_carry.py).", made[:4])
    return [then(hold), same]
