"""The GUN SETTINGS tab's HUD Tick fragment: its keys, a nudge, the save, and
the table written onto every carried gun.

    the M panel's row taken           TuneOpen = NOT TuneOpen, TuneRow = 0
    MenuOpen AND TuneOpen:
        Up / Down                     TuneRow -/+ 1, kept in 0..STAT_COUNT + 1
                                      (the last is BACK, under the list)
      and unless the caret is on BACK:
        Left / Right                  TuneNudge = -1 / +1
        Enter                         TuneSaveRequested = true (a tab with a
                                      save row: only with the caret on it)
    (the mouse: tune_draw raises the same flags from a click; BACK, by Enter
     or a click, is tune_draw's too, because it must not also save. The
     wheel is no key of a tab's; a scrolling tab's bar is dragged:
     tune_scroll.py)
    TuneNudge != 0 -> lower it, then
        TuneRow 0                     TuneWeapon steps round the guns
        else                          TuneValues[gun, stat] +/- its step, never
                                      under its minimum (nor over its maximum,
                                      for a tab that has them); TuneTouched,
                                      NOT TuneSaved, and the table into the
                                      tab's save slot (tune_keep.py; not the
                                      graphics tab's). In a tab with a live
                                      mask, only a cell that is the subject's
                                      own (TuneLive): the others stay
    TuneSaveRequested -> lower it; TuneSaved = ExecutePythonCommand(the save)
    TuneTouched -> for each carried item whose DisplayName is in TuneWeapons,
                   every TUNE_STATS variable that is its own := its cell
                   (ints rounded): a gun's, or for the melee weapons listed
                   after the guns only the throw's (gun_tuning.columns_of)

The keys, the nudge and the save are any TuneTab's (tune_tab.py):
author_tab_flow() is also MONSTER SETTINGS's (monster_tune_tick.py), and
opening any tab shuts the others. Only _author_apply is the guns'.

Tick, not DrawHUD, like the loot window: the M panel does not pause, and a
-nullrhi probe never draws. The keys only raise flags, so
probes/probe_gun_tuning.py tunes and saves without a keyboard. Applying every
Tick once touched, rather than once per nudge, is what reaches a gun picked
up after the nudge: the fire graph reads every stat off Held, so a value
lands on the next shot.
"""

import unreal

from uebp.graph import (
    BEL, _connect, _declare, _float_type, _loose_pin, _palette, _pin, out, then)
from combat.gun_tuning import GUN_COLUMNS, MELEE_COLUMNS, TUNE_COLUMNS, TUNE_STATS, columns_of
from combat.melee_tuning import melee_specs
from combat.paths import (
    ITEM_BP_PATH, ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.weapon_specs import _weapon_specs
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.menu_nav import pause_row_taken
from graphics_menu.loot_find import put
from graphics_menu.tune_consts import (
    GUN_TAB, STAT_COUNT, TUNE_LIVE_VAR, TUNE_TOUCHED_VAR,
    TUNE_VALUES_VAR, TUNE_WEAPONS_VAR,
)
from graphics_menu.tune_keep import author_keep_tab
from graphics_menu.tune_tab import TUNE_DOWN, TUNE_LESS, TUNE_MORE, TUNE_SAVE_KEY, TUNE_UP
from graphics_menu.tune_tabs import other_open_vars
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN, FN_WAS_PRESSED
from uebp.nodes.array import FN_ARR_FIND, FN_ARR_GET, FN_ARR_SET
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_II, FN_AND, FN_EQ_II, FN_FMIN, FN_GE_II, FN_INT_TO_FLOAT, FN_LESS_II,
    FN_MAX_FF, FN_MAX_II, FN_MIN_II, FN_MOD_II, FN_MUL_FF, FN_MUL_II, FN_NOT, FN_ROUND,
    FN_SUB_II)
from uebp.nodes.palette import MACRO_FOR_EACH, NODE_CAST_WEAPON
from uebp.nodes.system import FN_EXEC_PYTHON
from combat import item_vars as IV
from graphics_menu import hud_vars as MV
from combat.weapon_component import vars as WV


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
    if tab.kept:
        _declare(ed, tab.built_var, BEL.get_array_type(_float_type()))
    if tab.live_var:
        _declare(ed, tab.live_var, BEL.get_array_type(BEL.get_basic_type_by_name("bool")))
    _declare(ed, tab.names_var, BEL.get_array_type(BEL.get_basic_type_by_name("string")))


def tab_defaults(tab, names, values, steps, mins):
    """Shut, untouched, on the first subject, with the built table (and, for
    a kept tab, a second copy of it that no nudge moves)."""
    return {**{b: False for b in _bools(tab)}, **{i: 0 for i in _ints(tab)},
            tab.values_var: values, tab.names_var: names,
            tab.steps_var: steps, tab.mins_var: mins,
            **({tab.built_var: list(values)} if tab.kept else {})}


def declare_tune_vars(ed):
    """The HUD's gun tuning variables. Defaults: tune_defaults()."""
    declare_tab_vars(ed, GUN_TAB)


def tune_table():
    """(weapons, values, live): the built guns' DisplayNames, then the melee
    weapons'; their TUNE_STATS cells, flattened weapon by weapon -- the
    specs, so gun_tuning.csv's numbers; and per cell whether the stat is that
    weapon's own. A cell that is not holds 0 and is never read."""
    rows = ([(sp["display"], sp) for sp in _weapon_specs()] + melee_specs())
    names = [name for name, _spec in rows]
    live = [col in columns_of(name) for name, _spec in rows for col in TUNE_COLUMNS]
    values = [float(spec[col]) if col in columns_of(name) else 0.0
              for name, spec in rows for col in TUNE_COLUMNS]
    return names, values, live


def tune_defaults():
    names, values, live = tune_table()
    return {**tab_defaults(GUN_TAB, names, values, [float(st[3]) for st in TUNE_STATS],
                           [float(st[4]) for st in TUNE_STATS]),
            TUNE_LIVE_VAR: live}


def _pressed(ed, pc_out, key, made):
    return out(_call(ed, FN_WAS_PRESSED, made, self=pc_out, Key=key))


def _cell(ed, array_var, index, made):
    """HUD array ``array_var`` [index]: the Item pin."""
    n = _call(ed, FN_ARR_GET, made, TargetArray=_get(ed, array_var, made))
    _connect(index, _pin(n, "Index"))
    return out(n, "Item")


def _author_keys(ed, pc_out, in_execs, made, tab, closes):
    """The tab's row in the M panel, and with the tab open the arrows and
    Enter. Opening it shuts the tabs whose open flags are ``closes``, so only
    one panel shows and takes the arrows, and puts the caret on the subject.
    Returns the exec tails.

    The caret runs past the list, onto BACK (tab.back_row). There Left,
    Right and Enter are not this fragment's: BACK has no cell to nudge, and
    Enter on it shuts the tab, which is DrawHUD's (tune_draw.py). A tab with
    a save row (tab.save_widget) stops on it before BACK, and Enter saves
    there and nowhere else."""
    flip, no_t = _branch(ed, pause_row_taken(ed, tab.action, made), in_execs, made)
    opened = _call(ed, FN_NOT, made, A=_get(ed, tab.open_var, made))
    flow = put(ed, tab.open_var, out(opened), [flip], made)
    flow = _setter(ed, tab.row_var, 0, [flow], made)
    for other in closes:
        flow = _setter(ed, other, "false", [flow], made)

    active = _call(ed, FN_AND, made, A=_get(ed, MV.MenuOpen, made), B=_get(ed, tab.open_var, made))
    on, off = _branch(ed, out(active), [flow, no_t], made)
    flow = [on]
    for key, step, limit, bound in (
            (TUNE_UP, FN_SUB_II, FN_MAX_II, 0),
            (TUNE_DOWN, FN_ADD_II, FN_MIN_II, tab.back_row)):
        asked = _pressed(ed, pc_out, key, made)
        hit, miss = _branch(ed, asked, flow, made)
        moved = _call(ed, step, made, A=_get(ed, tab.row_var, made), B=1)
        held = _call(ed, limit, made, A=out(moved), B=bound)
        flow = [put(ed, tab.row_var, out(held), [hit], made), miss]
    in_list = _call(ed, FN_LESS_II, made, A=_get(ed, tab.row_var, made), B=tab.row_count)
    listed, on_back = _branch(ed, out(in_list), flow, made)
    flow = [listed]
    for key, nudge in ((TUNE_LESS, -1), (TUNE_MORE, 1)):
        turned = _pressed(ed, pc_out, key, made)
        hit, miss = _branch(ed, turned, flow, made)
        flow = [_setter(ed, tab.nudge_var, nudge, [hit], made), miss]
    if not tab.save_widget:
        ask, no_ask = _branch(ed, _pressed(ed, pc_out, TUNE_SAVE_KEY, made), flow, made)
        asked = _setter(ed, tab.save_var, "true", [ask], made)
        return [asked, no_ask, off, on_back]
    # Past the list: Enter on the save row. Nested, not ANDed, so the key is
    # only polled there.
    on_save = _call(ed, FN_EQ_II, made, A=_get(ed, tab.row_var, made), B=tab.save_row)
    there, on_back = _branch(ed, out(on_save), [on_back], made)
    ask, no_ask = _branch(ed, _pressed(ed, pc_out, TUNE_SAVE_KEY, made), [there], made)
    asked = _setter(ed, tab.save_var, "true", [ask], made)
    return [*flow, asked, no_ask, off, on_back]


def _author_nudge(ed, in_execs, made, tab, subjects):
    """Serve the tab's nudge (see the module docstring); ``subjects`` is how
    many rows the table has. Returns the exec tails.

    Both arms read the nudge before lowering it: a Set's pure inputs are
    pulled when it runs, so lowering first would step by zero."""
    idle = _call(ed, FN_EQ_II, made, A=_get(ed, tab.nudge_var, made), B=0)
    still, asked = _branch(ed, out(idle), in_execs, made)
    on_subject = _call(ed, FN_EQ_II, made, A=_get(ed, tab.row_var, made), B=0)
    subject, stat = _branch(ed, out(on_subject), [asked], made)

    # The subject row: (pick + nudge + subjects) % subjects, round the ends.
    stepped = _call(ed, FN_ADD_II, made,
                    A=_get(ed, tab.pick_var, made),
                    B=_get(ed, tab.nudge_var, made))
    lifted = _call(ed, FN_ADD_II, made, A=out(stepped), B=subjects)
    wrapped = _call(ed, FN_MOD_II, made, A=out(lifted), B=subjects)
    picked = put(ed, tab.pick_var, out(wrapped), [subject], made)

    # A stat row: cell := FMax(cell + nudge * step, minimum), and with
    # maximums FMin(that, maximum). Not an FClamp: the verifier reads every
    # Clamp in this graph as a settings slider.
    s = out(_call(ed, FN_SUB_II, made, A=_get(ed, tab.row_var, made), B=1))
    base = _call(ed, FN_MUL_II, made, A=_get(ed, tab.pick_var, made), B=tab.stat_count)
    idx = out(_call(ed, FN_ADD_II, made, A=out(base), B=s))
    sign = _call(ed, FN_INT_TO_FLOAT, made, InInt=_get(ed, tab.nudge_var, made))
    delta = _call(ed, FN_MUL_FF, made, A=_cell(ed, tab.steps_var, s, made), B=out(sign))
    moved = _call(ed, FN_ADD_FF, made, A=_cell(ed, tab.values_var, idx, made), B=out(delta))
    kept = _call(ed, FN_MAX_FF, made, A=out(moved), B=_cell(ed, tab.mins_var, s, made))
    if tab.maxs_var:
        kept = _call(ed, FN_FMIN, made, A=out(kept), B=_cell(ed, tab.maxs_var, s, made))
    write = _call(ed, FN_ARR_SET, made, TargetArray=_get(ed, tab.values_var, made))
    _connect(idx, _pin(write, "Index"))
    _connect(out(kept), _pin(write, "Item"))
    stays = []
    if tab.live_var:
        # A stat that is not the subject's own: nothing moves, nothing is touched.
        stat, dead = _branch(ed, _cell(ed, tab.live_var, idx, made), [stat], made)
        stays = [dead]
    _connect(stat, _pin(write, "execute"))
    flow = _setter(ed, tab.touched_var, "true", [then(write)], made)
    flow = [_setter(ed, tab.saved_var, "false", [flow], made)]
    if tab.kept:
        flow = author_keep_tab(ed, tab, flow, made)
    lowered = _setter(ed, tab.nudge_var, 0, [*flow, picked, *stays], made)
    return [lowered, still]


def _author_save(ed, in_execs, made, tab):
    """Serve the save flag: run the tab's save through the Python plugin."""
    serve, idle = _branch(ed, _get(ed, tab.save_var, made), in_execs, made)
    flow = _setter(ed, tab.save_var, "false", [serve], made)
    run = _call(ed, FN_EXEC_PYTHON, made, PythonCommand=tab.save_command)
    _connect(flow, _pin(run, "execute"))
    done = put(ed, tab.saved_var, out(run), [then(run)], made)
    return [done, idle]


def _author_apply(ed, in_execs, made, guns):
    """TuneTouched: the table onto every carried weapon it lists, each stat
    that is the weapon's own. ``guns``: how many of TuneWeapons are guns, the
    rest being melee weapons. Returns the exec tails: the loop's Completed
    among them, or a touched table ends Tick here, and the fragments after it
    (the menu's own rows: new game) are never reached."""
    go, idle = _branch(ed, _get(ed, TUNE_TOUCHED_VAR, made), in_execs, made)
    pawn = out(_call(ed, FN_GET_OWNING_PAWN, made))
    comp = _call(ed, FN_GET_COMP, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    unreal.load_asset(ITEM_BP_PATH)
    cast = _palette(ed, NODE_CAST_WEAPON)
    made.append(cast)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(go, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(_get(ed, WV.Inventory, made, WEAPON_COMP_CLASS_PATH, wc), _loose_pin(loop, "Array"))
    _connect(then(cast), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    find = _call(ed, FN_ARR_FIND, made, TargetArray=_get(ed, TUNE_WEAPONS_VAR, made))
    _connect(_get(ed, IV.DisplayName, made, ITEM_CLASS_PATH, item), _pin(find, "ItemToFind"))
    known = _call(ed, FN_GE_II, made, A=out(find), B=0)
    tuned, _other = _branch(ed, out(known), [_loose_pin(loop, "LoopBody", is_input=False)], made)
    base = out(_call(ed, FN_MUL_II, made, A=out(find), B=STAT_COUNT))
    # The guns are listed first: past them it is a melee weapon, which takes
    # only its own columns.
    melee = _call(ed, FN_GE_II, made, A=out(find), B=guns)
    blade, gun = _branch(ed, out(melee), [tuned], made)
    for flow, columns in ((gun, GUN_COLUMNS), (blade, MELEE_COLUMNS)):
        for s, (col, var, _label, _step, _min, kind) in enumerate(TUNE_STATS):
            if col not in columns:
                continue
            idx = out(_call(ed, FN_ADD_II, made, A=base, B=s))
            value = _cell(ed, TUNE_VALUES_VAR, idx, made)
            if kind is int:
                value = out(_call(ed, FN_ROUND, made, A=value))
            n = ed.add_set_member_variable_node(var, ITEM_CLASS_PATH)
            made.append(n)
            _connect(item, _pin(n, "self"))
            _connect(value, _pin(n, var))
            _connect(flow, _pin(n, "execute"))
            flow = then(n)
    return [_loose_pin(loop, "Completed", is_input=False), idle, out(cast, "CastFailed")]


def author_tab_flow(ed, pc_out, in_execs, made, tab, subjects, closes):
    """Any tab's keys, nudge and save, in that order. ``closes``: the other
    tabs' open flags. Returns the exec tails, for the tab's own apply."""
    flow = _author_keys(ed, pc_out, in_execs, made, tab, closes)
    flow = _author_nudge(ed, flow, made, tab, subjects)
    return _author_save(ed, flow, made, tab)


def author_tune_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    weapons = len(tune_table()[0])
    flow = author_tab_flow(ed, pc_out, in_execs, made, GUN_TAB, weapons, other_open_vars(GUN_TAB))
    tails = _author_apply(ed, flow, made, weapons - len(melee_specs()))
    ed.add_comment_to_nodes(
        "Gun tuning (its row in the M panel): Up/Down pick a row, Left/Right "
        "change the gun or the stat, Enter saves gun_tuning.csv. Once anything is "
        "tuned, every carried gun takes the table each Tick, and the knife and "
        "the axe their throw's rows.", made[:1])
    return tails
