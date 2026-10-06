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

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, else_, out, then
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.wear_tuning import WORN_VAR
from graphics_menu.cursor import author_widget_click
from graphics_menu.hud_inventory import _author_empty_slot, _author_filled_slot
from graphics_menu.inv_consts import DRAG_FROM_VAR, WORN_CODE_FIRST
from graphics_menu.inv_carry import author_carry_end, author_carry_icon
from graphics_menu.inv_drag import author_inv_drag
from graphics_menu.ui_graph import part, set_shown
from graphics_menu.umg_consts import WBP_HUD
from graphics_menu.wear_consts import (
    WEAR_CLOSE, WEAR_OPEN_VAR, WEAR_PANEL, WEAR_ROWS, WEAR_SEL_VAR, WEAR_SLOTS_BOX,
)
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN
from uebp.nodes.array import FN_ARR_GET, FN_ARR_VALID
from uebp.nodes.math import FN_ADD_II, FN_AND, FN_EQ_II, FN_NOT, FN_OR
from uebp.nodes.palette import MACRO_FOR_LOOP, NODE_CAST_SLOT, NODE_CAST_WEAPON
from uebp.nodes.system import FN_IS_VALID
from uebp.nodes.umg import FN_CHILD_AT
from graphics_menu import hud_vars as MV


def _get(ed, var, owner=None, self_out=None):
    n = (ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var))
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    return out(n, var)


def _call(ed, fn, **inputs):
    n = _node(ed, fn)
    for name, pin in inputs.items():
        if isinstance(pin, int):
            _pin(n, name).set_pin_value(str(pin))
        else:
            _connect(pin, _loose_pin(n, name))
    return n


def _branch(ed, cond, execs):
    br = ed.add_branch_node()
    _connect(cond, _pin(br, "Condition"))
    for e in execs:
        _connect(e, _pin(br, "execute"))
    return then(br), else_(br)


def _author_slots(ed, worn, box, in_execs):
    """Cell i of the worn grid shows Worn[i] as any inventory slot shows its
    item (hud_inventory's two fragments): its icon, lit under the open
    panel's caret and at a drag's start; nothing worn, the slot's silhouette.
    Returns Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    loop
    _pin(loop, "FirstIndex").set_pin_value("0")
    _pin(loop, "LastIndex").set_pin_value(str(WEAR_ROWS - 1))
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = out(loop, "Index")
    cast = _palette(ed, NODE_CAST_SLOT)
    _connect(out(_call(ed, FN_CHILD_AT, self=box, Index=i)), _pin(cast, "Object"))
    _connect(out(loop, "LoopBody"), _pin(cast, "execute"))
    slot = _loose_pin(cast, "AsWBPInventorySlot", is_input=False)
    there, past = _branch(ed, out(_call(ed, FN_ARR_VALID,
                                         TargetArray=worn, IndexToTest=i)),
                          [then(cast)])
    item = _loose_pin(_call(ed, FN_ARR_GET, TargetArray=worn, Index=i), "Item", is_input=False)
    worn_one, bare = _branch(ed, out(_call(ed, FN_IS_VALID, Object=item)), [there])
    caret = _call(ed, FN_AND,
                  A=_get(ed, WEAR_OPEN_VAR),
                  B=out(_call(ed, FN_EQ_II, A=i,
                               B=_get(ed, WEAR_SEL_VAR))))
    code = _call(ed, FN_ADD_II, A=i, B=WORN_CODE_FIRST)
    dragged = _call(ed, FN_EQ_II, A=out(code), B=_get(ed, DRAG_FROM_VAR))
    lit = _call(ed, FN_OR, A=out(caret), B=out(dragged))
    _author_filled_slot(ed, slot, item, out(lit), worn_one, ammo=False)
    _author_empty_slot(ed, slot, (bare, past))
    return out(loop, "Completed")


def author_wear_panel(ed, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    panel = part(ed, WBP_HUD, WEAR_PANEL)
    not_menu = _call(ed, FN_NOT, A=_get(ed, MV.MenuOpen))
    shown, shut = _branch(ed, out(not_menu), in_execs)
    closed = set_shown(ed, panel, False, [shut])
    flow = set_shown(ed, panel, True, [shown])

    pawn = out(_call(ed, FN_GET_OWNING_PAWN))
    comp = _call(ed, FN_GET_COMP, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _palette(ed, NODE_CAST_WEAPON)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(flow, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    worn = _get(ed, WORN_VAR, WEAPON_COMP_CLASS_PATH, wc)

    # The mouse only with the panel open: shut, the cursor is hidden and a
    # click is a shot. Before the slots are drawn, so the caret it moves and
    # the drag it starts are lit this frame.
    opened, idle = _branch(ed, _get(ed, WEAR_OPEN_VAR), [then(cast)])
    # The close button: a click on it lowers WearOpen, as I does.
    flow = author_widget_click(ed, part(ed, WBP_HUD, WEAR_CLOSE),
                               (WEAR_OPEN_VAR, "false"), [opened])
    flow = author_inv_drag(ed, wc, flow)
    flow = author_carry_icon(ed, wc, worn, flow)
    box = part(ed, WBP_HUD, WEAR_SLOTS_BOX)
    done = _author_slots(ed, worn, box, flow + [idle])
    # A drag's end with the panel shut, and the look held while one is on.
    return author_carry_end(ed, [closed, done, out(cast, "CastFailed")])
