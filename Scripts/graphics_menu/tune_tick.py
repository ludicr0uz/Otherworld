"""The GUN TUNING tab's HUD Tick fragment: its keys, a nudge, the save, and
the table written onto every carried gun.

    [T] with MenuOpen                 TuneOpen = NOT TuneOpen
    MenuOpen AND TuneOpen:
        Up / Down                     TuneRow -/+ 1, kept in 0..STAT_COUNT
        Left / Right                  TuneNudge = -1 / +1
        Enter                         TuneSaveRequested = true
    TuneNudge != 0 -> lower it, then
        TuneRow 0                     TuneWeapon steps round the guns
        else                          TuneValues[gun, stat] +/- its step, never
                                      under its minimum; TuneTouched, NOT TuneSaved
    TuneSaveRequested -> lower it; TuneSaved = ExecutePythonCommand(the save)
    TuneTouched -> for each carried item whose DisplayName is in TuneWeapons,
                   every TUNE_STATS variable := its cell (ints rounded)

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
    FN_GET_PLAYER_PAWN, FN_MIN_II, FN_MOD_II, FN_MUL_FF, FN_NOT, FN_SUB_II,
    FN_WAS_PRESSED, MACRO_FOR_EACH,
)
from combat.paths import (
    ITEM_BP_PATH, ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.weapon_specs import _weapon_specs
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.loot_find import put
from graphics_menu.tune_consts import (
    STAT_COUNT, TUNE_DOWN, TUNE_KEY, TUNE_LESS, TUNE_MINS_VAR, TUNE_MORE,
    TUNE_NUDGE_VAR, TUNE_OPEN_VAR, TUNE_ROW_VAR, TUNE_SAVE_COMMAND, TUNE_SAVE_KEY,
    TUNE_SAVE_VAR, TUNE_SAVED_VAR, TUNE_STEPS_VAR, TUNE_TOUCHED_VAR, TUNE_UP,
    TUNE_VALUES_VAR, TUNE_WEAPON_VAR, TUNE_WEAPONS_VAR,
)

FN_MAX_II = "/Script/Engine.KismetMathLibrary.Max"
FN_MUL_II = "/Script/Engine.KismetMathLibrary.Multiply_IntInt"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_FMAX = "/Script/Engine.KismetMathLibrary.FMax"
FN_ROUND = "/Script/Engine.KismetMathLibrary.Round"
FN_INT_TO_FLOAT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"
FN_ARR_SET = "/Script/Engine.KismetArrayLibrary.Array_Set"
FN_ARR_FIND = "/Script/Engine.KismetArrayLibrary.Array_Find"
FN_EXEC_PYTHON = "/Script/PythonScriptPlugin.PythonScriptLibrary.ExecutePythonCommand"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"


_BOOLS = (TUNE_OPEN_VAR, TUNE_SAVE_VAR, TUNE_SAVED_VAR, TUNE_TOUCHED_VAR)
_INTS = (TUNE_ROW_VAR, TUNE_WEAPON_VAR, TUNE_NUDGE_VAR)
_FLOAT_ARRAYS = (TUNE_VALUES_VAR, TUNE_STEPS_VAR, TUNE_MINS_VAR)


def declare_tune_vars(ed):
    """The HUD's tuning variables. Defaults: tune_defaults()."""
    for name in _BOOLS:
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    for name in _INTS:
        _declare(ed, name, BEL.get_basic_type_by_name("int"))
    for name in _FLOAT_ARRAYS:
        _declare(ed, name, BEL.get_array_type(_float_type()))
    _declare(ed, TUNE_WEAPONS_VAR, BEL.get_array_type(BEL.get_basic_type_by_name("string")))


def tune_table():
    """(guns, values): the built guns' DisplayNames and their TUNE_STATS
    cells, flattened gun by gun -- the specs, so gun_tuning.csv's numbers."""
    specs = _weapon_specs()
    guns = [sp["display"] for sp in specs]
    values = [float(sp[col]) for sp in specs for col, *_rest in TUNE_STATS]
    return guns, values


def tune_defaults():
    guns, values = tune_table()
    return {**{b: False for b in _BOOLS}, **{i: 0 for i in _INTS},
            TUNE_VALUES_VAR: values, TUNE_WEAPONS_VAR: guns,
            TUNE_STEPS_VAR: [float(st[3]) for st in TUNE_STATS],
            TUNE_MINS_VAR: [float(st[4]) for st in TUNE_STATS]}


def _pressed(ed, pc_out, key, x, y, made):
    return _out(_call(ed, FN_WAS_PRESSED, x, y, made, self=pc_out, Key=key))


def _cell(ed, array_var, index, x, y, made):
    """HUD array ``array_var`` [index]: the Item pin."""
    n = _call(ed, FN_ARR_GET, x, y, made, TargetArray=_get(ed, array_var, x - 240, y, made))
    _connect(index, _pin(n, "Index"))
    return _pin(n, "Item", is_input=False)


def _author_keys(ed, pc_out, in_execs, x0, y0, made):
    """T, and with the tab open the arrows and Enter. Returns the exec tails."""
    t = _call(ed, FN_AND, x0, y0 + 300, made, A=_get(ed, "MenuOpen", x0 - 240, y0 + 300, made),
              B=_pressed(ed, pc_out, TUNE_KEY, x0 - 240, y0 + 440, made))
    flip, no_t = _branch(ed, _out(t), in_execs, x0 + 240, y0, made)
    opened = _call(ed, FN_NOT, x0 + 240, y0 + 440, made,
                   A=_get(ed, TUNE_OPEN_VAR, x0, y0 + 580, made))
    flow = put(ed, TUNE_OPEN_VAR, _out(opened), [flip], x0 + 500, y0 - 200, made)

    x = x0 + 800
    active = _call(ed, FN_AND, x - 240, y0 + 300, made,
                   A=_get(ed, "MenuOpen", x - 480, y0 + 300, made),
                   B=_get(ed, TUNE_OPEN_VAR, x - 480, y0 + 440, made))
    on, off = _branch(ed, _out(active), [flow, no_t], x, y0, made)
    flow = [on]
    for key, step, limit, bound in ((TUNE_UP, FN_SUB_II, FN_MAX_II, 0),
                                    (TUNE_DOWN, FN_ADD_II, FN_MIN_II, STAT_COUNT)):
        x += 300
        hit, miss = _branch(ed, _pressed(ed, pc_out, key, x, y0 + 440, made), flow,
                            x, y0, made)
        moved = _call(ed, step, x + 300, y0 + 300, made,
                      A=_get(ed, TUNE_ROW_VAR, x + 60, y0 + 300, made), B=1)
        held = _call(ed, limit, x + 540, y0 + 300, made, A=_out(moved), B=bound)
        flow = [put(ed, TUNE_ROW_VAR, _out(held), [hit], x + 780, y0, made), miss]
        x += 800
    for key, nudge in ((TUNE_LESS, -1), (TUNE_MORE, 1)):
        hit, miss = _branch(ed, _pressed(ed, pc_out, key, x, y0 + 440, made), flow,
                            x, y0, made)
        flow = [_setter(ed, TUNE_NUDGE_VAR, nudge, [hit], x + 260, y0, made), miss]
        x += 560
    ask, no_ask = _branch(ed, _pressed(ed, pc_out, TUNE_SAVE_KEY, x, y0 + 440, made),
                          flow, x, y0, made)
    asked = _setter(ed, TUNE_SAVE_VAR, "true", [ask], x + 260, y0, made)
    return [asked, no_ask, off]


def _author_nudge(ed, in_execs, x0, y0, made, guns):
    """Serve TuneNudge (see the module docstring). Returns the exec tails.

    Both arms read the nudge before lowering it: a Set's pure inputs are
    pulled when it runs, so lowering first would step by zero."""
    idle = _call(ed, FN_EQ_II, x0, y0 + 300, made,
                 A=_get(ed, TUNE_NUDGE_VAR, x0 - 240, y0 + 300, made), B=0)
    still, asked = _branch(ed, _out(idle), in_execs, x0 + 240, y0, made)
    on_gun = _call(ed, FN_EQ_II, x0 + 240, y0 + 440, made,
                   A=_get(ed, TUNE_ROW_VAR, x0, y0 + 440, made), B=0)
    gun, stat = _branch(ed, _out(on_gun), [asked], x0 + 500, y0, made)

    # The gun row: (TuneWeapon + nudge + guns) % guns, round the ends.
    x = x0 + 800
    stepped = _call(ed, FN_ADD_II, x, y0 - 300, made,
                    A=_get(ed, TUNE_WEAPON_VAR, x - 240, y0 - 300, made),
                    B=_get(ed, TUNE_NUDGE_VAR, x - 240, y0 - 160, made))
    lifted = _call(ed, FN_ADD_II, x + 240, y0 - 300, made, A=_out(stepped), B=guns)
    wrapped = _call(ed, FN_MOD_II, x + 480, y0 - 300, made, A=_out(lifted), B=guns)
    picked = put(ed, TUNE_WEAPON_VAR, _out(wrapped), [gun], x + 720, y0 - 500, made)

    # A stat row: cell := FMax(cell + nudge * step, minimum).
    s = _out(_call(ed, FN_SUB_II, x, y0 + 700, made,
                   A=_get(ed, TUNE_ROW_VAR, x - 240, y0 + 700, made), B=1))
    base = _call(ed, FN_MUL_II, x, y0 + 900, made,
                 A=_get(ed, TUNE_WEAPON_VAR, x - 240, y0 + 900, made), B=STAT_COUNT)
    idx = _out(_call(ed, FN_ADD_II, x + 240, y0 + 900, made, A=_out(base), B=s))
    sign = _call(ed, FN_INT_TO_FLOAT, x + 240, y0 + 1100, made,
                 InInt=_get(ed, TUNE_NUDGE_VAR, x, y0 + 1100, made))
    delta = _call(ed, FN_MUL_FF, x + 720, y0 + 1000, made,
                  A=_cell(ed, TUNE_STEPS_VAR, s, x + 480, y0 + 1200, made), B=_out(sign))
    moved = _call(ed, FN_ADD_FF, x + 960, y0 + 800, made,
                  A=_cell(ed, TUNE_VALUES_VAR, idx, x + 720, y0 + 800, made),
                  B=_out(delta))
    kept = _call(ed, FN_FMAX, x + 1200, y0 + 800, made, A=_out(moved),
                 B=_cell(ed, TUNE_MINS_VAR, s, x + 960, y0 + 1300, made))
    write = _call(ed, FN_ARR_SET, x + 1440, y0, made,
                  TargetArray=_get(ed, TUNE_VALUES_VAR, x + 1200, y0 + 600, made))
    _connect(idx, _pin(write, "Index"))
    _connect(_out(kept), _pin(write, "Item"))
    _connect(stat, _pin(write, "execute"))
    flow = _setter(ed, TUNE_TOUCHED_VAR, "true", [BEL.find_then_pin(write)],
                   x + 1740, y0, made)
    flow = _setter(ed, TUNE_SAVED_VAR, "false", [flow], x + 2000, y0, made)
    lowered = _setter(ed, TUNE_NUDGE_VAR, 0, [flow, picked], x + 2260, y0, made)
    return [lowered, still]


def _author_save(ed, in_execs, x0, y0, made):
    """Serve TuneSaveRequested: run tune_save.save() through the Python plugin."""
    serve, idle = _branch(ed, _get(ed, TUNE_SAVE_VAR, x0 - 240, y0 + 300, made),
                          in_execs, x0, y0, made)
    flow = _setter(ed, TUNE_SAVE_VAR, "false", [serve], x0 + 260, y0, made)
    run = _call(ed, FN_EXEC_PYTHON, x0 + 520, y0, made, PythonCommand=TUNE_SAVE_COMMAND)
    _connect(flow, _pin(run, "execute"))
    done = put(ed, TUNE_SAVED_VAR, _out(run), [BEL.find_then_pin(run)], x0 + 820, y0, made)
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


def author_tune_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    guns = len(tune_table()[0])
    flow = _author_keys(ed, pc_out, in_execs, x0, y0, made)
    flow = _author_nudge(ed, flow, x0 + 5400, y0, made, guns)
    flow = _author_save(ed, flow, x0 + 9000, y0, made)
    tails = _author_apply(ed, flow, x0 + 10400, y0, made)
    ed.add_comment_to_nodes(
        f"Gun tuning ([{TUNE_KEY}] in the M panel): Up/Down pick a row, Left/Right "
        f"change the gun or the stat, Enter saves gun_tuning.csv. Once anything is "
        f"tuned, every carried gun takes the table each Tick.", made[:1])
    return tails
