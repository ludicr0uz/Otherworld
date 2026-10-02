"""The GUN TUNING tab's HUD Tick fragment: its keys, a nudge, the save, and
the table written onto every carried gun.

    the M panel's row taken           TuneOpen = NOT TuneOpen, TuneRow = 0
    MenuOpen AND TuneOpen:
        Up / Down                     TuneRow -/+ 1, kept in 0..STAT_COUNT + 1
                                      (the last is BACK, under the list)
      and unless the caret is on BACK:
        Left / Right, or the wheel    TuneNudge = -1 / +1
        Enter                         TuneSaveRequested = true (a tab with a
                                      save row: only with the caret on it)
    (the mouse: tune_draw raises the same flags from a click; BACK, by Enter
     or a click, is tune_draw's too, because it must not also save. A
     scrolling tab's wheel is Up / Down instead: the list follows the caret)
    TuneNudge != 0 -> lower it, then
        TuneRow 0                     TuneWeapon steps round the guns
        else                          TuneValues[gun, stat] +/- its step, never
                                      under its minimum (nor over its maximum,
                                      for a tab that has them); TuneTouched,
                                      NOT TuneSaved
    TuneSaveRequested -> lower it; TuneSaved = ExecutePythonCommand(the save)
    TuneTouched -> for each carried item whose DisplayName is in TuneWeapons,
                   every TUNE_STATS variable := its cell (ints rounded)

The keys, the nudge and the save are any TuneTab's (tune_tab.py):
author_tab_flow() is also MONSTER TUNING's (monster_tune_tick.py), and
opening any tab shuts the others. Only _author_apply is the guns'.

Tick, not DrawHUD, like the loot window: the M panel does not pause, and a
-nullrhi probe never draws. The keys only raise flags, so
probes/probe_gun_tuning.py tunes and saves without a keyboard. Applying every
Tick once touched, rather than once per nudge, is what reaches a gun picked
up after the nudge: the fire graph reads every stat off Held, so a value
lands on the next shot.
"""

import unreal

from combat.graph import BEL, _at, _connect, _declare, _float_type, _loose_pin, _palette, _pin
from combat.gun_tuning import TUNE_STATS
from combat.nodes import (
    FN_ADD_FF, FN_ADD_II, FN_AND, FN_ARR_GET, FN_EQ_II, FN_GET_COMP,
    FN_GET_PLAYER_PAWN, FN_LESS_II, FN_MIN_II, FN_MOD_II, FN_MUL_FF, FN_NOT, FN_SUB_II,
    FN_WAS_PRESSED, MACRO_FOR_EACH,
)
from combat.paths import (
    ITEM_BP_PATH, ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.weapon_specs import _weapon_specs
from graphics_menu.cursor_consts import WHEEL_LESS, WHEEL_MORE
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.menu_nav import or_wheel, pause_row_taken
from graphics_menu.loot_find import put
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.tune_consts import (
    GUN_TAB, STAT_COUNT, TUNE_TOUCHED_VAR,
    TUNE_VALUES_VAR, TUNE_WEAPONS_VAR,
)
from graphics_menu.tune_tab import TUNE_DOWN, TUNE_LESS, TUNE_MORE, TUNE_SAVE_KEY, TUNE_UP
from graphics_menu.world_tune_consts import WORLD_TAB

FN_MAX_II = "/Script/Engine.KismetMathLibrary.Max"
FN_MUL_II = "/Script/Engine.KismetMathLibrary.Multiply_IntInt"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_FMAX = "/Script/Engine.KismetMathLibrary.FMax"
FN_FMIN = "/Script/Engine.KismetMathLibrary.FMin"
FN_ROUND = "/Script/Engine.KismetMathLibrary.Round"
FN_INT_TO_FLOAT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"
FN_ARR_SET = "/Script/Engine.KismetArrayLibrary.Array_Set"
FN_ARR_FIND = "/Script/Engine.KismetArrayLibrary.Array_Find"
FN_EXEC_PYTHON = "/Script/PythonScriptPlugin.PythonScriptLibrary.ExecutePythonCommand"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"


def _bools(tab):
    return (tab.open_var, tab.save_var, tab.saved_var, tab.touched_var)


def _ints(tab):
    return (tab.row_var, tab.pick_var, tab.nudge_var)


def declare_tab_vars(ed, tab):
    """A tab's HUD variables. Defaults: tab_defaults()."""
    for name in _bools(tab):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    for name in _ints(tab):
        _declare(ed, name, BEL.get_basic_type_by_name("int"))
    for name in filter(None, (tab.values_var, tab.steps_var, tab.mins_var,
                              tab.maxs_var)):
        _declare(ed, name, BEL.get_array_type(_float_type()))
    _declare(ed, tab.names_var, BEL.get_array_type(BEL.get_basic_type_by_name("string")))


def tab_defaults(tab, names, values, steps, mins):
    """Shut, untouched, on the first subject, with the built table."""
    return {**{b: False for b in _bools(tab)}, **{i: 0 for i in _ints(tab)},
            tab.values_var: values, tab.names_var: names,
            tab.steps_var: steps, tab.mins_var: mins}


def declare_tune_vars(ed):
    """The HUD's gun tuning variables. Defaults: tune_defaults()."""
    declare_tab_vars(ed, GUN_TAB)


def tune_table():
    """(guns, values): the built guns' DisplayNames and their TUNE_STATS
    cells, flattened gun by gun -- the specs, so gun_tuning.csv's numbers."""
    specs = _weapon_specs()
    guns = [sp["display"] for sp in specs]
    values = [float(sp[col]) for sp in specs for col, *_rest in TUNE_STATS]
    return guns, values


def tune_defaults():
    guns, values = tune_table()
    return tab_defaults(GUN_TAB, guns, values, [float(st[3]) for st in TUNE_STATS],
                        [float(st[4]) for st in TUNE_STATS])


def _pressed(ed, pc_out, key, x, y, made):
    return _out(_call(ed, FN_WAS_PRESSED, x, y, made, self=pc_out, Key=key))


def _cell(ed, array_var, index, x, y, made):
    """HUD array ``array_var`` [index]: the Item pin."""
    n = _call(ed, FN_ARR_GET, x, y, made, TargetArray=_get(ed, array_var, x - 240, y, made))
    _connect(index, _pin(n, "Index"))
    return _pin(n, "Item", is_input=False)


def _author_keys(ed, pc_out, in_execs, x0, y0, made, tab, closes):
    """The tab's row in the M panel, and with the tab open the arrows and
    Enter. Opening it shuts the tabs whose open flags are ``closes``, so only
    one panel shows and takes the arrows, and puts the caret on the subject.
    Returns the exec tails.

    The caret runs past the list, onto BACK (tab.back_row). There Left,
    Right and Enter are not this fragment's: BACK has no cell to nudge, and
    Enter on it shuts the tab, which is DrawHUD's (tune_draw.py). A tab with
    a save row (tab.save_widget) stops on it before BACK, and Enter saves
    there and nowhere else."""
    flip, no_t = _branch(ed, pause_row_taken(ed, tab.action, x0 - 480, y0 + 760, made),
                         in_execs, x0 + 240, y0, made)
    opened = _call(ed, FN_NOT, x0 + 240, y0 + 440, made,
                   A=_get(ed, tab.open_var, x0, y0 + 580, made))
    flow = put(ed, tab.open_var, _out(opened), [flip], x0 + 500, y0 - 200, made)
    flow = _setter(ed, tab.row_var, 0, [flow], x0 + 500, y0 - 400, made)
    for i, other in enumerate(closes):
        flow = _setter(ed, other, "false", [flow], x0 + 760 + 260 * i, y0 - 400, made)

    x = x0 + 800
    active = _call(ed, FN_AND, x - 240, y0 + 300, made,
                   A=_get(ed, "MenuOpen", x - 480, y0 + 300, made),
                   B=_get(ed, tab.open_var, x - 480, y0 + 440, made))
    on, off = _branch(ed, _out(active), [flow, no_t], x, y0, made)
    flow = [on]
    # A scrolling tab's wheel moves the caret (the list follows it); the
    # others' wheel changes the value under it.
    scrolls = tab.visible_rows > 0
    for key, wheel, step, limit, bound in (
            (TUNE_UP, WHEEL_MORE, FN_SUB_II, FN_MAX_II, 0),
            (TUNE_DOWN, WHEEL_LESS, FN_ADD_II, FN_MIN_II, tab.back_row)):
        x += 300
        asked = _pressed(ed, pc_out, key, x, y0 + 440, made)
        if scrolls:
            asked = or_wheel(ed, pc_out, asked, wheel, x, y0 + 600, made)
        hit, miss = _branch(ed, asked, flow, x, y0, made)
        moved = _call(ed, step, x + 300, y0 + 300, made,
                      A=_get(ed, tab.row_var, x + 60, y0 + 300, made), B=1)
        held = _call(ed, limit, x + 540, y0 + 300, made, A=_out(moved), B=bound)
        flow = [put(ed, tab.row_var, _out(held), [hit], x + 780, y0, made), miss]
        x += 800
    in_list = _call(ed, FN_LESS_II, x, y0 + 300, made,
                    A=_get(ed, tab.row_var, x - 240, y0 + 300, made), B=tab.row_count)
    listed, on_back = _branch(ed, _out(in_list), flow, x + 240, y0, made)
    flow = [listed]
    x += 300
    for key, wheel, nudge in ((TUNE_LESS, WHEEL_LESS, -1), (TUNE_MORE, WHEEL_MORE, 1)):
        turned = _pressed(ed, pc_out, key, x, y0 + 440, made)
        if not scrolls:
            turned = or_wheel(ed, pc_out, turned, wheel, x, y0 + 600, made)
        hit, miss = _branch(ed, turned, flow, x, y0, made)
        flow = [_setter(ed, tab.nudge_var, nudge, [hit], x + 260, y0, made), miss]
        x += 560
    if not tab.save_widget:
        ask, no_ask = _branch(ed, _pressed(ed, pc_out, TUNE_SAVE_KEY, x, y0 + 440, made),
                              flow, x, y0, made)
        asked = _setter(ed, tab.save_var, "true", [ask], x + 260, y0, made)
        return [asked, no_ask, off, on_back]
    # Past the list: Enter on the save row. Nested, not ANDed, so the key is
    # only polled there.
    on_save = _call(ed, FN_EQ_II, x, y0 + 900, made,
                    A=_get(ed, tab.row_var, x - 240, y0 + 900, made), B=tab.save_row)
    there, on_back = _branch(ed, _out(on_save), [on_back], x + 240, y0 + 700, made)
    ask, no_ask = _branch(ed, _pressed(ed, pc_out, TUNE_SAVE_KEY, x + 300, y0 + 1140, made),
                          [there], x + 540, y0 + 700, made)
    asked = _setter(ed, tab.save_var, "true", [ask], x + 800, y0 + 700, made)
    return [*flow, asked, no_ask, off, on_back]


def _author_nudge(ed, in_execs, x0, y0, made, tab, subjects):
    """Serve the tab's nudge (see the module docstring); ``subjects`` is how
    many rows the table has. Returns the exec tails.

    Both arms read the nudge before lowering it: a Set's pure inputs are
    pulled when it runs, so lowering first would step by zero."""
    idle = _call(ed, FN_EQ_II, x0, y0 + 300, made,
                 A=_get(ed, tab.nudge_var, x0 - 240, y0 + 300, made), B=0)
    still, asked = _branch(ed, _out(idle), in_execs, x0 + 240, y0, made)
    on_subject = _call(ed, FN_EQ_II, x0 + 240, y0 + 440, made,
                       A=_get(ed, tab.row_var, x0, y0 + 440, made), B=0)
    subject, stat = _branch(ed, _out(on_subject), [asked], x0 + 500, y0, made)

    # The subject row: (pick + nudge + subjects) % subjects, round the ends.
    x = x0 + 800
    stepped = _call(ed, FN_ADD_II, x, y0 - 300, made,
                    A=_get(ed, tab.pick_var, x - 240, y0 - 300, made),
                    B=_get(ed, tab.nudge_var, x - 240, y0 - 160, made))
    lifted = _call(ed, FN_ADD_II, x + 240, y0 - 300, made, A=_out(stepped), B=subjects)
    wrapped = _call(ed, FN_MOD_II, x + 480, y0 - 300, made, A=_out(lifted), B=subjects)
    picked = put(ed, tab.pick_var, _out(wrapped), [subject], x + 720, y0 - 500, made)

    # A stat row: cell := FMax(cell + nudge * step, minimum), and with
    # maximums FMin(that, maximum). Not an FClamp: the verifier reads every
    # Clamp in this graph as a settings slider.
    s = _out(_call(ed, FN_SUB_II, x, y0 + 700, made,
                   A=_get(ed, tab.row_var, x - 240, y0 + 700, made), B=1))
    base = _call(ed, FN_MUL_II, x, y0 + 900, made,
                 A=_get(ed, tab.pick_var, x - 240, y0 + 900, made), B=tab.stat_count)
    idx = _out(_call(ed, FN_ADD_II, x + 240, y0 + 900, made, A=_out(base), B=s))
    sign = _call(ed, FN_INT_TO_FLOAT, x + 240, y0 + 1100, made,
                 InInt=_get(ed, tab.nudge_var, x, y0 + 1100, made))
    delta = _call(ed, FN_MUL_FF, x + 720, y0 + 1000, made,
                  A=_cell(ed, tab.steps_var, s, x + 480, y0 + 1200, made), B=_out(sign))
    moved = _call(ed, FN_ADD_FF, x + 960, y0 + 800, made,
                  A=_cell(ed, tab.values_var, idx, x + 720, y0 + 800, made),
                  B=_out(delta))
    kept = _call(ed, FN_FMAX, x + 1200, y0 + 800, made, A=_out(moved),
                 B=_cell(ed, tab.mins_var, s, x + 960, y0 + 1300, made))
    if tab.maxs_var:
        kept = _call(ed, FN_FMIN, x + 1200, y0 + 1100, made, A=_out(kept),
                     B=_cell(ed, tab.maxs_var, s, x + 960, y0 + 1500, made))
    write = _call(ed, FN_ARR_SET, x + 1440, y0, made,
                  TargetArray=_get(ed, tab.values_var, x + 1200, y0 + 600, made))
    _connect(idx, _pin(write, "Index"))
    _connect(_out(kept), _pin(write, "Item"))
    _connect(stat, _pin(write, "execute"))
    flow = _setter(ed, tab.touched_var, "true", [BEL.find_then_pin(write)],
                   x + 1740, y0, made)
    flow = _setter(ed, tab.saved_var, "false", [flow], x + 2000, y0, made)
    lowered = _setter(ed, tab.nudge_var, 0, [flow, picked], x + 2260, y0, made)
    return [lowered, still]


def _author_save(ed, in_execs, x0, y0, made, tab):
    """Serve the save flag: run the tab's save through the Python plugin."""
    serve, idle = _branch(ed, _get(ed, tab.save_var, x0 - 240, y0 + 300, made),
                          in_execs, x0, y0, made)
    flow = _setter(ed, tab.save_var, "false", [serve], x0 + 260, y0, made)
    run = _call(ed, FN_EXEC_PYTHON, x0 + 520, y0, made, PythonCommand=tab.save_command)
    _connect(flow, _pin(run, "execute"))
    done = put(ed, tab.saved_var, _out(run), [BEL.find_then_pin(run)], x0 + 820, y0, made)
    return [done, idle]


def _author_apply(ed, in_execs, x0, y0, made):
    """TuneTouched: the table onto every carried gun. Returns the exec tails."""
    go, idle = _branch(ed, _get(ed, TUNE_TOUCHED_VAR, x0 - 240, y0 + 300, made),
                       in_execs, x0, y0, made)
    pawn = _out(_call(ed, FN_GET_PLAYER_PAWN, x0, y0 + 440, made, PlayerIndex=0))
    comp = _call(ed, FN_GET_COMP, x0 + 260, y0 + 440, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    unreal.load_asset(ITEM_BP_PATH)
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 520, y0)
    made.append(cast)
    _connect(_out(comp), _pin(cast, "Object"))
    _connect(go, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    loop = _at(ed.add_macro_node(MACRO_FOR_EACH), x0 + 820, y0)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(_get(ed, "Inventory", x0 + 580, y0 + 300, made, WEAPON_COMP_CLASS_PATH, wc),
             _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(cast), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    x = x0 + 1120
    find = _call(ed, FN_ARR_FIND, x, y0 + 300, made,
                 TargetArray=_get(ed, TUNE_WEAPONS_VAR, x - 240, y0 + 300, made))
    _connect(_get(ed, "DisplayName", x - 240, y0 + 440, made, ITEM_CLASS_PATH, item),
             _pin(find, "ItemToFind"))
    known = _call(ed, FN_GE_II, x + 240, y0 + 300, made, A=_out(find), B=0)
    tuned, _other = _branch(ed, _out(known), [_loose_pin(loop, "LoopBody", is_input=False)],
                            x + 480, y0, made)
    base = _out(_call(ed, FN_MUL_II, x + 480, y0 + 440, made, A=_out(find), B=STAT_COUNT))
    flow = tuned
    x += 760
    for s, (_col, var, _label, _step, _min, kind) in enumerate(TUNE_STATS):
        idx = _out(_call(ed, FN_ADD_II, x, y0 + 300, made, A=base, B=s))
        value = _cell(ed, TUNE_VALUES_VAR, idx, x + 240, y0 + 440, made)
        if kind is int:
            value = _out(_call(ed, FN_ROUND, x + 240, y0 + 600, made, A=value))
        n = _at(ed.add_set_member_variable_node(var, ITEM_CLASS_PATH), x + 480, y0)
        made.append(n)
        _connect(item, _pin(n, "self"))
        _connect(value, _pin(n, var))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        x += 600
    return [idle, _pin(cast, "CastFailed", is_input=False)]


def author_tab_flow(ed, pc_out, in_execs, x0, y0, made, tab, subjects, closes):
    """Any tab's keys, nudge and save, in that order. ``closes``: the other
    tabs' open flags. Returns the exec tails, for the tab's own apply."""
    flow = _author_keys(ed, pc_out, in_execs, x0, y0, made, tab, closes)
    flow = _author_nudge(ed, flow, x0 + 5400, y0, made, tab, subjects)
    return _author_save(ed, flow, x0 + 9000, y0, made, tab)


def author_tune_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, x0, y0, made, GUN_TAB,
                           len(tune_table()[0]),
                           (MONSTER_TAB.open_var, WORLD_TAB.open_var,
                            GFX_TAB.open_var))
    tails = _author_apply(ed, flow, x0 + 10400, y0, made)
    ed.add_comment_to_nodes(
        "Gun tuning (its row in the M panel): Up/Down pick a row, Left/Right "
        "change the gun or the stat, Enter saves gun_tuning.csv. Once anything is "
        "tuned, every carried gun takes the table each Tick.", made[:1])
    return tails
