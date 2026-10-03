"""DrawHUD: the worn panel, from wear_tick's variables and the player's Worn.

    the menu shut   the panel, always (bottom right, over the bag): cell i
                    is an inventory slot showing the weapon component's
                    Worn[i] by its own icon, or the slot's silhouette where
                    nothing is worn (Worn is read only behind IsValidIndex,
                    then IsValid); with the I panel open (WearOpen) the slot
                    under the caret (WearSel) is lit, as a drag's start is
    the menu open   collapsed

Only reads; wear_tick.py decides. The one thing it writes is the mouse's
(cursor.py), with the I panel open only, because only DrawHUD knows where a
cell is: a click on the WearClose line lowers WearOpen, as I does; and the
slots, the worn ones among them (inv_drag.py: the cell under the cursor ->
WearSel, a click on it raises WearTakeOffRequested, which Tick serves
exactly as it serves Enter, and a drag wears or takes off).
"""

import unreal

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin
from combat.nodes import (
    FN_ADD_II, FN_AND, FN_ARR_GET, FN_ARR_VALID, FN_EQ_II, FN_GET_COMP, FN_GET_PLAYER_PAWN,
    FN_IS_VALID, FN_NOT, FN_OR, MACRO_FOR_LOOP,
)
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.wear_tuning import WORN_VAR
from graphics_menu.cursor import author_widget_click
from graphics_menu.hud_inventory import (
    NODE_CAST_SLOT, _author_empty_slot, _author_filled_slot,
)
from graphics_menu.inv_consts import DRAG_FROM_VAR, WORN_CODE_FIRST
from graphics_menu.inv_drag import author_inv_drag
from graphics_menu.ui_graph import FN_CHILD_AT, part, set_shown
from graphics_menu.umg_consts import WBP_HUD
from graphics_menu.wear_consts import (
    WEAR_CLOSE, WEAR_OPEN_VAR, WEAR_PANEL, WEAR_ROWS, WEAR_SEL_VAR, WEAR_SLOTS_BOX,
)

NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"


def _get(ed, var, x, y, owner=None, self_out=None):
    n = _at(ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var), x, y)
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    return _pin(n, var, is_input=False)


def _call(ed, fn, x, y, **inputs):
    n = _at(_node(ed, fn), x, y)
    for name, pin in inputs.items():
        if isinstance(pin, int):
            _pin(n, name).set_pin_value(str(pin))
        else:
            _connect(pin, _loose_pin(n, name))
    return n


def _out(n):
    return _pin(n, "ReturnValue", is_input=False)


def _branch(ed, cond, execs, x, y):
    br = _at(ed.add_branch_node(), x, y)
    _connect(cond, _pin(br, "Condition"))
    for e in execs:
        _connect(e, _pin(br, "execute"))
    return BEL.find_then_pin(br), BEL.find_else_pin(br)


def _author_slots(ed, worn, box, in_execs, x0, y0):
    """Cell i of the worn grid shows Worn[i] as any inventory slot shows its
    item (hud_inventory's two fragments): its icon, lit under the open
    panel's caret and at a drag's start; nothing worn, the slot's silhouette.
    Returns Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    _at(loop, x0, y0)
    _pin(loop, "FirstIndex").set_pin_value("0")
    _pin(loop, "LastIndex").set_pin_value(str(WEAR_ROWS - 1))
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)
    cast = _at(_palette(ed, NODE_CAST_SLOT), x0 + 560, y0)
    _connect(_out(_call(ed, FN_CHILD_AT, x0 + 300, y0 + 240, self=box, Index=i)),
             _pin(cast, "Object"))
    _connect(_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    slot = _loose_pin(cast, "AsWBPInventorySlot", is_input=False)
    there, past = _branch(ed, _out(_call(ed, FN_ARR_VALID, x0 + 600, y0 + 500,
                                         TargetArray=worn, IndexToTest=i)),
                          [BEL.find_then_pin(cast)], x0 + 860, y0)
    item = _loose_pin(_call(ed, FN_ARR_GET, x0 + 860, y0 + 500, TargetArray=worn, Index=i),
                      "Item", is_input=False)
    worn_one, bare = _branch(ed, _out(_call(ed, FN_IS_VALID, x0 + 1120, y0 + 500,
                                            Object=item)), [there], x0 + 1120, y0)
    caret = _call(ed, FN_AND, x0 + 1120, y0 + 900,
                  A=_get(ed, WEAR_OPEN_VAR, x0 + 600, y0 + 900),
                  B=_out(_call(ed, FN_EQ_II, x0 + 860, y0 + 1040, A=i,
                               B=_get(ed, WEAR_SEL_VAR, x0 + 600, y0 + 1040))))
    code = _call(ed, FN_ADD_II, x0 + 600, y0 + 1200, A=i, B=WORN_CODE_FIRST)
    dragged = _call(ed, FN_EQ_II, x0 + 860, y0 + 1200, A=_out(code),
                    B=_get(ed, DRAG_FROM_VAR, x0 + 600, y0 + 1340))
    lit = _call(ed, FN_OR, x0 + 1120, y0 + 1200, A=_out(caret), B=_out(dragged))
    _author_filled_slot(ed, slot, item, _out(lit), worn_one, x0 + 1400, y0, ammo=False)
    _author_empty_slot(ed, slot, (bare, past), x0 + 1400, y0 + 1600)
    return _pin(loop, "Completed", is_input=False)


def author_wear_panel(ed, x0, y0, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    panel = part(ed, WBP_HUD, WEAR_PANEL, x0, y0 + 1000)
    not_menu = _call(ed, FN_NOT, x0, y0 + 440, A=_get(ed, "MenuOpen", x0 - 240, y0 + 440))
    shown, shut = _branch(ed, _out(not_menu), in_execs, x0 + 480, y0)
    closed = set_shown(ed, panel, False, [shut], x0 + 740, y0 + 700)
    flow = set_shown(ed, panel, True, [shown], x0 + 740, y0)

    pawn = _out(_call(ed, FN_GET_PLAYER_PAWN, x0 + 740, y0 + 440))
    comp = _call(ed, FN_GET_COMP, x0 + 1000, y0 + 440, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 1000, y0)
    _connect(_out(comp), _pin(cast, "Object"))
    _connect(flow, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    worn = _get(ed, WORN_VAR, x0 + 1300, y0 + 300, WEAPON_COMP_CLASS_PATH, wc)

    # The mouse only with the panel open: shut, the cursor is hidden and a
    # click is a shot. Before the slots are drawn, so the caret it moves and
    # the drag it starts are lit this frame.
    opened, idle = _branch(ed, _get(ed, WEAR_OPEN_VAR, x0 + 1300, y0 + 600),
                           [BEL.find_then_pin(cast)], x0 + 1560, y0)
    # The close button: a click on it lowers WearOpen, as I does.
    flow = author_widget_click(ed, part(ed, WBP_HUD, WEAR_CLOSE, x0 + 1820, y0 - 2100),
                               (WEAR_OPEN_VAR, "false"), [opened], x0 + 2340, y0 - 2600)
    flow = author_inv_drag(ed, wc, flow, x0 + 1820, y0 + 4000)
    box = part(ed, WBP_HUD, WEAR_SLOTS_BOX, x0 + 1820, y0 + 500)
    done = _author_slots(ed, worn, box, flow + [idle], x0 + 2300, y0)
    return [closed, done, _pin(cast, "CastFailed", is_input=False)]
