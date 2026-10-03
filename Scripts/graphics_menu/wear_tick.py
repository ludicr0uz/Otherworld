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
            WearSel a worn row -> the weapon component's TakeOffSlot = WearSel
            WearSel a bag slot -> its SlotRequest = that slot (to hand)
    then, on every path: WearOpen != WearStill -> WearStill = WearOpen,
        controller.SetIgnoreMoveInput(WearOpen)

The HUD only asks: the weapon component takes the garment off on its own
Tick (combat/weapon_component/wear.py), where the bag's room is known. Tick,
not DrawHUD, so a -nullrhi probe can open the panel and take off without a
keyboard (probes/probe_clothing.py). The walk is held as the menu holds it
(menu_still.py): the stock mapping walks on the arrows too. SetIgnoreMoveInput
counts its calls, so it is made on WearOpen's edges only; WearStill is that
edge's memory.
"""

import unreal

from combat.graph import BEL, _at, _connect, _declare, _loose_pin, _palette, _pin
from combat.nodes import (
    FN_ADD_II, FN_AND, FN_GET_COMP, FN_GET_PLAYER_PAWN, FN_LESS_II, FN_MIN_II, FN_NEQ_BB,
    FN_NOT, FN_SUB_II, FN_WAS_PRESSED,
)
from combat.slot_tuning import SLOT_REQUEST_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.wear_tuning import TAKE_OFF_VAR
from combat.weapon_component.dead import OWNER_DEAD_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.loot_consts import LOOT_OPEN_VAR
from graphics_menu.loot_find import put
from graphics_menu.inv_consts import SEL_ROWS, SEL_TO_CODE
from graphics_menu.loot_kneel import FN_IGNORE_MOVE
from graphics_menu.wear_consts import (
    WEAR_DOWN, WEAR_KEY, WEAR_OPEN_VAR, WEAR_ROWS, WEAR_SEL_VAR, WEAR_TAKE_KEY,
    WEAR_TAKE_VAR, WEAR_UP,
)

FN_MAX_II = "/Script/Engine.KismetMathLibrary.Max"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"
WEAR_STILL_VAR = "WearStill"

_BOOLS = (WEAR_OPEN_VAR, WEAR_TAKE_VAR, WEAR_STILL_VAR)


def declare_wear_vars(ed):
    """The HUD's I panel variables. Defaults: wear_defaults()."""
    _declare(ed, WEAR_SEL_VAR, BEL.get_basic_type_by_name("int"))
    for name in _BOOLS:
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))


def wear_defaults():
    return {WEAR_SEL_VAR: 0, **{b: False for b in _BOOLS}}


def _pressed(ed, pc_out, key, x, y, made):
    return _out(_call(ed, FN_WAS_PRESSED, x, y, made, self=pc_out, Key=key))


def _author_keys(ed, pc_out, in_execs, x0, y0, made):
    """I, and with the panel open Up/Down/Enter. Returns the exec tails."""
    free, busy = _branch(ed, _out(_call(ed, FN_NOT, x0, y0 + 300, made,
                                        A=_get(ed, "MenuOpen", x0 - 240, y0 + 300, made))),
                         in_execs, x0 + 240, y0, made)
    key, no_key = _branch(ed, _pressed(ed, pc_out, WEAR_KEY, x0 + 240, y0 + 440, made),
                          [free], x0 + 500, y0, made)
    flip = _call(ed, FN_NOT, x0 + 500, y0 + 440, made,
                 A=_get(ed, WEAR_OPEN_VAR, x0 + 260, y0 + 580, made))
    flow = put(ed, WEAR_OPEN_VAR, _out(flip), [key], x0 + 760, y0 - 200, made)
    flow = _setter(ed, WEAR_SEL_VAR, 0, [flow], x0 + 1020, y0 - 200, made)

    x = x0 + 1300
    # The loot window's keys are the same three: open over it, they are its.
    looting = _call(ed, FN_NOT, x - 240, y0 + 440, made,
                    A=_get(ed, LOOT_OPEN_VAR, x - 480, y0 + 440, made))
    ours = _call(ed, FN_AND, x, y0 + 300, made,
                 A=_get(ed, WEAR_OPEN_VAR, x - 240, y0 + 300, made), B=_out(looting))
    shown, shut = _branch(ed, _out(ours), [flow, no_key], x + 240, y0, made)
    flow = [shown]
    x += 300
    for k, step, limit, bound in ((WEAR_UP, FN_SUB_II, FN_MAX_II, 0),
                                  (WEAR_DOWN, FN_ADD_II, FN_MIN_II, SEL_ROWS - 1)):
        hit, miss = _branch(ed, _pressed(ed, pc_out, k, x, y0 + 440, made), flow,
                            x + 240, y0, made)
        moved = _call(ed, step, x + 300, y0 + 300, made,
                      A=_get(ed, WEAR_SEL_VAR, x + 60, y0 + 300, made), B=1)
        kept = _call(ed, limit, x + 540, y0 + 300, made, A=_out(moved), B=bound)
        flow = [put(ed, WEAR_SEL_VAR, _out(kept), [hit], x + 540, y0, made), miss]
        x += 900
    ask, no_ask = _branch(ed, _pressed(ed, pc_out, WEAR_TAKE_KEY, x, y0 + 440, made),
                          flow, x + 240, y0, made)
    asked = _setter(ed, WEAR_TAKE_VAR, "true", [ask], x + 500, y0, made)
    return [asked, no_ask, shut, busy]


def _author_still(ed, pc_out, in_execs, x0, y0, made):
    """The walk held on WearOpen's edges. Returns the exec tails."""
    changed = _call(ed, FN_NEQ_BB, x0 + 240, y0 + 300, made,
                    A=_get(ed, WEAR_OPEN_VAR, x0, y0 + 300, made),
                    B=_get(ed, WEAR_STILL_VAR, x0, y0 + 440, made))
    edge, same = _branch(ed, _out(changed), in_execs, x0 + 500, y0, made)
    flow = put(ed, WEAR_STILL_VAR, _get(ed, WEAR_OPEN_VAR, x0 + 520, y0 + 300, made),
               [edge], x0 + 760, y0, made)
    still = _call(ed, FN_IGNORE_MOVE, x0 + 1020, y0, made, self=pc_out,
                  bNewMoveInput=_get(ed, WEAR_OPEN_VAR, x0 + 780, y0 + 300, made))
    _connect(flow, _pin(still, "execute"))
    return [BEL.find_then_pin(still), same]


def author_wear_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the tails."""
    made = []
    pawn = _out(_call(ed, FN_GET_PLAYER_PAWN, x0, y0 + 440, made, PlayerIndex=0))
    comp = _call(ed, FN_GET_COMP, x0 + 260, y0 + 440, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 520, y0)
    made.append(cast)
    _connect(_out(comp), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    # The dead wear nothing new: no I, no take-off, and an open panel shuts.
    dead, alive = _branch(ed, _get(ed, OWNER_DEAD_VAR, x0 + 520, y0 + 600, made,
                                   WEAPON_COMP_CLASS_PATH, wc),
                          [BEL.find_then_pin(cast)], x0 + 800, y0 + 600, made)
    shut = _setter(ed, WEAR_OPEN_VAR, "false", [dead], x0 + 1060, y0 + 800, made)
    shut = _setter(ed, WEAR_TAKE_VAR, "false", [shut], x0 + 1320, y0 + 800, made)

    keyed = _author_keys(ed, pc_out, [alive], x0 + 1300, y0, made)
    x0 += 6000
    wanted = _call(ed, FN_AND, x0, y0 + 300, made,
                   A=_get(ed, WEAR_TAKE_VAR, x0 - 240, y0 + 300, made),
                   B=_get(ed, WEAR_OPEN_VAR, x0 - 240, y0 + 440, made))
    serve, idle = _branch(ed, _out(wanted), keyed, x0 + 240, y0, made)
    flow = _setter(ed, WEAR_TAKE_VAR, "false", [serve], x0 + 500, y0, made)
    # The caret on a worn row takes it off; on a bag slot (past the rows) it
    # asks for that slot's item in hand.
    worn_row = _call(ed, FN_LESS_II, x0 + 500, y0 + 300, made,
                     A=_get(ed, WEAR_SEL_VAR, x0 + 260, y0 + 300, made), B=WEAR_ROWS)
    row, bag = _branch(ed, _out(worn_row), [flow], x0 + 760, y0 + 200, made)
    asked = _at(ed.add_set_member_variable_node(TAKE_OFF_VAR, WEAPON_COMP_CLASS_PATH),
                x0 + 1020, y0)
    made.append(asked)
    _connect(wc, _pin(asked, "self"))
    _connect(_get(ed, WEAR_SEL_VAR, x0 + 780, y0 + 300, made), _pin(asked, TAKE_OFF_VAR))
    _connect(row, _pin(asked, "execute"))
    code = _call(ed, FN_SUB_II, x0 + 1020, y0 + 700, made,
                 A=_get(ed, WEAR_SEL_VAR, x0 + 780, y0 + 700, made), B=SEL_TO_CODE)
    brought = _at(ed.add_set_member_variable_node(SLOT_REQUEST_VAR, WEAPON_COMP_CLASS_PATH),
                  x0 + 1280, y0 + 500)
    made.append(brought)
    _connect(wc, _pin(brought, "self"))
    _connect(_out(code), _pin(brought, SLOT_REQUEST_VAR))
    _connect(bag, _pin(brought, "execute"))
    tails = [BEL.find_then_pin(asked), BEL.find_then_pin(brought), idle, shut,
             _pin(cast, "CastFailed", is_input=False)]
    tails = _author_still(ed, pc_out, tails, x0 + 1600, y0, made)
    ed.add_comment_to_nodes(
        f"The I panel: [{WEAR_KEY}] opens what the player wears, Up/Down pick a "
        "slot, Enter asks the weapon component to take that garment off "
        "(TakeOffSlot). While it is open the walk is held.", made[:1])
    return tails
