"""The I panel's HUD Tick fragment: its keys, a take-off, and the held walk.

    with the player's weapon component:
        the player dead -> WearOpen = false, WearTakeOffRequested = false
        menu shut (NOT MenuOpen):
            [I]          WearOpen = NOT WearOpen, WearSel = 0
            open, and the loot window shut:
                Up/Down  WearSel -/+ 1, kept to the worn rows and the bag's
                         slots after them
                Enter    WearTakeOffRequested = true
        WearTakeOffRequested AND WearOpen -> lower it;
            WearSel a worn row -> the weapon component's AskTakeOff(WearSel,
                                  into the bag)
            WearSel a bag slot -> its AskSlot(that slot) (to hand)
    then, on every path: WearOpen != WearStill -> WearStill = WearOpen,
        controller.SetIgnoreMoveInput(WearOpen)

The HUD only asks (ask.py): the weapon component takes the garment off on its
own Tick (combat/weapon_component/wear.py), where the bag's room is known. Tick,
not DrawHUD, so a -nullrhi probe can open the panel and take off without a
keyboard (probes/probe_clothing.py). The walk is held as the menu holds it
(menu_still.py): the stock mapping walks on the arrows too. SetIgnoreMoveInput
counts its calls, so it is made on WearOpen's edges only; WearStill is that
edge's memory.
"""

import unreal

from uebp.graph import BEL, _connect, _declare, _loose_pin, _palette, _pin, out, then
from combat.ask_consts import ASK_SLOT, ASK_TAKE_OFF
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.wear_tuning import NOT_CLOTHING
from combat.weapon_component.dead import OWNER_DEAD_VAR
from graphics_menu.ask import ask
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.loot_consts import LOOT_OPEN_VAR
from graphics_menu.loot_find import put
from graphics_menu.inv_consts import SEL_ROWS, SEL_TO_CODE
from graphics_menu.wear_consts import (
    WEAR_DOWN, WEAR_KEY, WEAR_OPEN_VAR, WEAR_ROWS, WEAR_SEL_VAR, WEAR_TAKE_KEY,
    WEAR_TAKE_VAR, WEAR_UP,
)
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN, FN_IGNORE_MOVE, FN_WAS_PRESSED
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_LESS_II, FN_MAX_II, FN_MIN_II, FN_NEQ_BB, FN_NOT, FN_SUB_II)
from uebp.nodes.palette import NODE_CAST_WEAPON
from graphics_menu import hud_vars as MV

WEAR_STILL_VAR = "WearStill"

_BOOLS = (WEAR_OPEN_VAR, WEAR_TAKE_VAR, WEAR_STILL_VAR)


def declare_wear_vars(ed):
    """The HUD's I panel variables. Defaults: wear_defaults()."""
    _declare(ed, WEAR_SEL_VAR, BEL.get_basic_type_by_name("int"))
    for name in _BOOLS:
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))


def wear_defaults():
    return {WEAR_SEL_VAR: 0, **{b: False for b in _BOOLS}}


def _pressed(ed, pc_out, key, made):
    return out(_call(ed, FN_WAS_PRESSED, made, self=pc_out, Key=key))


def _author_keys(ed, pc_out, in_execs, made):
    """I, and with the panel open Up/Down/Enter. Returns the exec tails."""
    free, busy = _branch(ed, out(_call(ed, FN_NOT, made,
                                        A=_get(ed, MV.MenuOpen, made))),
                         in_execs, made)
    key, no_key = _branch(ed, _pressed(ed, pc_out, WEAR_KEY, made), [free], made)
    flip = _call(ed, FN_NOT, made, A=_get(ed, WEAR_OPEN_VAR, made))
    flow = put(ed, WEAR_OPEN_VAR, out(flip), [key], made)
    flow = _setter(ed, WEAR_SEL_VAR, 0, [flow], made)

    # The loot window's keys are the same three: open over it, they are its.
    looting = _call(ed, FN_NOT, made, A=_get(ed, LOOT_OPEN_VAR, made))
    ours = _call(ed, FN_AND, made, A=_get(ed, WEAR_OPEN_VAR, made), B=out(looting))
    shown, shut = _branch(ed, out(ours), [flow, no_key], made)
    flow = [shown]
    for k, step, limit, bound in ((WEAR_UP, FN_SUB_II, FN_MAX_II, 0),
                                  (WEAR_DOWN, FN_ADD_II, FN_MIN_II, SEL_ROWS - 1)):
        hit, miss = _branch(ed, _pressed(ed, pc_out, k, made), flow, made)
        moved = _call(ed, step, made, A=_get(ed, WEAR_SEL_VAR, made), B=1)
        kept = _call(ed, limit, made, A=out(moved), B=bound)
        flow = [put(ed, WEAR_SEL_VAR, out(kept), [hit], made), miss]
    ask, no_ask = _branch(ed, _pressed(ed, pc_out, WEAR_TAKE_KEY, made), flow, made)
    asked = _setter(ed, WEAR_TAKE_VAR, "true", [ask], made)
    return [asked, no_ask, shut, busy]


def _author_still(ed, pc_out, in_execs, made):
    """The walk held on WearOpen's edges. Returns the exec tails."""
    changed = _call(ed, FN_NEQ_BB, made,
                    A=_get(ed, WEAR_OPEN_VAR, made),
                    B=_get(ed, WEAR_STILL_VAR, made))
    edge, same = _branch(ed, out(changed), in_execs, made)
    flow = put(ed, WEAR_STILL_VAR, _get(ed, WEAR_OPEN_VAR, made), [edge], made)
    still = _call(ed, FN_IGNORE_MOVE, made, self=pc_out,
                  bNewMoveInput=_get(ed, WEAR_OPEN_VAR, made))
    _connect(flow, _pin(still, "execute"))
    return [then(still), same]


def author_wear_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the tails."""
    made = []
    pawn = out(_call(ed, FN_GET_OWNING_PAWN, made))
    comp = _call(ed, FN_GET_COMP, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _palette(ed, NODE_CAST_WEAPON)
    made.append(cast)
    _connect(out(comp), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    # The dead wear nothing new: no I, no take-off, and an open panel shuts.
    dead, alive = _branch(ed, _get(ed, OWNER_DEAD_VAR, made,
                                   WEAPON_COMP_CLASS_PATH, wc),
                          [then(cast)], made)
    shut = _setter(ed, WEAR_OPEN_VAR, "false", [dead], made)
    shut = _setter(ed, WEAR_TAKE_VAR, "false", [shut], made)

    keyed = _author_keys(ed, pc_out, [alive], made)
    wanted = _call(ed, FN_AND, made,
                   A=_get(ed, WEAR_TAKE_VAR, made),
                   B=_get(ed, WEAR_OPEN_VAR, made))
    serve, idle = _branch(ed, out(wanted), keyed, made)
    flow = _setter(ed, WEAR_TAKE_VAR, "false", [serve], made)
    # The caret on a worn row takes it off; on a bag slot (past the rows) it
    # asks for that slot's item in hand.
    worn_row = _call(ed, FN_LESS_II, made, A=_get(ed, WEAR_SEL_VAR, made), B=WEAR_ROWS)
    row, bag = _branch(ed, out(worn_row), [flow], made)
    # Into the bag: no slot named (a drag names one, inv_drag.py).
    asked = ask(ed, wc, ASK_TAKE_OFF, [row], made,
                Slot=_get(ed, WEAR_SEL_VAR, made), To=NOT_CLOTHING)
    code = _call(ed, FN_SUB_II, made, A=_get(ed, WEAR_SEL_VAR, made), B=SEL_TO_CODE)
    brought = ask(ed, wc, ASK_SLOT, [bag], made, Slot=out(code))
    tails = [asked, brought, idle, shut, out(cast, "CastFailed")]
    tails = _author_still(ed, pc_out, tails, made)
    ed.add_comment_to_nodes(
        f"The I panel: [{WEAR_KEY}] opens what the player wears, Up/Down pick a "
        "slot, Enter asks the weapon component to take that garment off "
        "(AskTakeOff). While it is open the walk is held.", made[:1])
    return tails
