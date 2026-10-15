"""verify_graphics_menu.py's checks for the GUN SETTINGS tab (tune_tick,
tune_draw, wbp_tune, and gun_tuning.csv reaching the guns). Here rather than
in the verifier, which is over its size budget.
"""

import os
import tempfile

import unreal

from combat.axe import AXE_DISPLAY
from combat.grip_nudges import GRIP_MIN, GRIP_STATS
from combat.gun_tuning import (
    CSV_PATH, GUN_COLUMNS, MELEE_COLUMNS, MELEE_WEAPONS, TUNE_COLUMNS, TUNE_STATS,
    columns_of, read_table, write_table,
)
from combat.knife import KNIFE_DISPLAY
from combat.paths import AXE_BP_PATH, KNIFE_BP_PATH
from combat.weapon_specs import _weapon_specs
from graphics_menu import tune_consts as TC
from graphics_menu import umg_consts as UC
from graphics_menu.tune_tick import tune_defaults
from graphics_menu.umg_checks import _tree

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _same(a, b):
    a, b = list(a), list(b)
    return len(a) == len(b) and all(
        abs(float(x) - float(y)) < 1e-6 if isinstance(y, float) else x == y
        for x, y in zip(a, b))


def _weapons():
    """[(DisplayName, Blueprint path)]: the guns, then the melee weapons."""
    return ([(sp["display"], sp["path"]) for sp in _weapon_specs()]
            + [(KNIFE_DISPLAY, KNIFE_BP_PATH), (AXE_DISPLAY, AXE_BP_PATH)])


def _check_csv(check):
    table = read_table()
    names = [name for name, _path in _weapons()]
    check("gun_tuning.csv has a row for every gun and each melee weapon, and a "
          "cell for every stat that is the weapon's own, and no other",
          set(table) == set(names)
          and all(set(table[g]) == set(columns_of(g)) for g in names),
          f"{CSV_PATH}: rows {sorted(table)}")
    guns = len(_weapon_specs())
    check("...the melee weapons, which are the knife and the axe, hold only "
          "their throw; a gun holds everything but a throw's damage",
          tuple(names[guns:]) == MELEE_WEAPONS
          and all(columns_of(g) == MELEE_COLUMNS for g in names[guns:])
          and all(len(columns_of(g)) == len(TUNE_COLUMNS) - 1 for g in names[:guns]),
          str(names[guns:]))
    bad = []
    for name, path in _weapons():
        cdo = unreal.get_default_object(BEL.generated_class(unreal.load_asset(path)))
        for col, var, _label, _step, _min, _kind in TUNE_STATS:
            if col not in columns_of(name):
                continue
            want = table.get(name, {}).get(col)
            got = cdo.get_editor_property(var)
            if want is None or abs(float(got) - float(want)) > 1e-4:
                bad.append(f"{name}.{var}={got} csv {want}")
    check(f"every gun holds its gun_tuning.csv row ({len(TUNE_STATS) - 1} stats each), "
          f"and the knife and the axe theirs ({len(MELEE_COLUMNS)})",
          not bad, "; ".join(bad[:6]))


def _check_native_format(check, defaults):
    """A packaged build's save (OtherworldTuningLibrary.SaveTuningCsv) writes
    the built table as the editor's (gun_tuning.write_table) does, byte for
    byte, so the file it leaves can stand in for gun_tuning.csv."""
    names = list(defaults[TC.TUNE_WEAPONS_VAR])
    values = list(defaults[TC.TUNE_VALUES_VAR])
    live = list(defaults[TC.TUNE_LIVE_VAR])
    name = "verify_gun_tuning.csv"   # never the name a build saves under
    lib = unreal.OtherworldTuningLibrary
    wrote = lib.save_tuning_csv(name, TC.TUNE_CSV_HEADER, names, values, live, TC.STAT_COUNT)
    path = lib.tuning_csv_path(name)
    native = open(path).read() if wrote and os.path.exists(path) else ""
    n = TC.STAT_COUNT
    rows = [(w, {c: values[i * n + s] for s, c in enumerate(TUNE_COLUMNS)
                 if c in columns_of(w)}) for i, w in enumerate(names)]
    with tempfile.TemporaryDirectory() as tmp:
        write_table(rows, os.path.join(tmp, "g.csv"))
        python = open(os.path.join(tmp, "g.csv")).read()
    if os.path.exists(path):
        os.remove(path)
    diff = [(a, b) for a, b in zip(native.splitlines(), python.splitlines()) if a != b]
    check("a packaged build's save (SaveTuningCsv) writes the built table as "
          "gun_tuning.write_table does", wrote and native == python,
          f"wrote {wrote}, {len(native)} vs {len(python)} chars, first diff {diff[:1]}")


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_PAUSE_MENU).items()}
    panel, box = widgets.get(TC.TUNE_PANEL), widgets.get(TC.TUNE_ROWS_BOX)
    kids = list(box.get_all_children()) if box else []
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR)) for k in kids]
    check(f"WBP_PauseMenu has the tuning panel, its {TC.TUNE_ROW_COUNT} rows labelled "
          f"gun then each stat, and the saved line",
          panel is not None and TC.TUNE_SAVED_TEXT in widgets
          and labels == list(TC.TUNE_ROW_LABELS), str(labels))
    hidden = [n for n in (TC.TUNE_PANEL, TC.TUNE_SAVED_TEXT) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...collapsed until the HUD shows it", len(hidden) == 2, str(hidden))
    check("the M panel lists the tab's key", TC.TUNE_ROW_LABEL in UC.PAUSE_ROW_LABELS,
          str(UC.PAUSE_ROW_LABELS))


def _check_native_save(check, nodes, runs):
    """A packaged build has no Python: there the save is SaveTuningCsv's, on
    the false side of the branch whose true side is the Python save."""
    def lit(n, pin):
        return str(BEL.find_input_pin(n, pin).get_pin_value())

    def fed(n, pin):
        return [q for q in BEL.find_input_pin(n, pin).list_connected_pins()]

    csvs = [n for n in nodes if {"FileName", "Header", "Subjects", "Values", "Live",
                                 "Stride"} <= _pins(n)]
    check("in a packaged build the save writes gun_tuning.csv through SaveTuningCsv, "
          "once, with gun_tuning.csv's header and a row of STAT_COUNT cells per weapon",
          len(csvs) == 1 and lit(csvs[0], "FileName") == TC.TUNE_CSV_NAME
          and lit(csvs[0], "Header") == TC.TUNE_CSV_HEADER
          and lit(csvs[0], "Stride") == str(TC.STAT_COUNT),
          f"{len(csvs)} nodes" + (f": {lit(csvs[0], 'Header')!r} stride "
                                  f"{lit(csvs[0], 'Stride')}" if csvs else ""))
    if len(csvs) != 1 or len(runs) != 1:
        return
    sources = {_title(PIN.get_owning_node(q)): q for pin in ("Subjects", "Values", "Live")
               for q in fed(csvs[0], pin)}
    check("...of TuneWeapons, TuneValues and TuneLive",
          set(sources) == {f"Get {v}" for v in (TC.TUNE_WEAPONS_VAR, TC.TUNE_VALUES_VAR,
                                                TC.TUNE_LIVE_VAR)}, str(sorted(sources)))
    saved = [q for q in BEL.find_output_pin(csvs[0], "ReturnValue").list_connected_pins()]
    check("...and its success is what TuneSaved shows",
          any(_title(PIN.get_owning_node(q)) == f"Set {TC.TUNE_SAVED_VAR}" for q in saved))
    native = [str(PIN.get_pin_name(q)) for q in fed(csvs[0], "execute")]
    python = [str(PIN.get_pin_name(q)) for q in fed(runs[0], "execute")]
    branches = {PIN.get_owning_node(q).get_name() for q in
                fed(csvs[0], "execute") + fed(runs[0], "execute")}
    conds = [_title(PIN.get_owning_node(q)) for n in nodes if n.get_name() in branches
             for q in fed(n, "Condition")]
    check("...only where CanRunPython is false: the Python save is the same branch's true side",
          native == ["else"] and python == ["then"] and len(branches) == 1
          and any("CanRunPython" in c.replace(" ", "") for c in conds),
          f"native {native}, python {python}, {len(branches)} branches, {conds}")


def _check_graph(check, nodes):
    # MONSTER SETTINGS has its own, with its own command (monster_tune_checks).
    calls = [n for n in nodes if "PythonCommand" in _pins(n)]
    runs = [n for n in calls if str(BEL.find_input_pin(n, "PythonCommand")
                                    .get_pin_value()) == TC.TUNE_SAVE_COMMAND]
    check("Enter's save runs tune_save through ExecutePythonCommand, once",
          len(runs) == 1, f"{len(runs)} of {len(calls)} Python calls")
    saved = [q for n in runs for q in BEL.find_output_pin(n, "ReturnValue")
             .list_connected_pins()]
    check("...and its success is what TuneSaved shows",
          any(_title(PIN.get_owning_node(q)) == f"Set {TC.TUNE_SAVED_VAR}" for q in saved))

    _check_native_save(check, nodes, runs)

    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)]
    fed = [n for n in writes
           if any(_title(PIN.get_owning_node(q)) == f"Get {TC.TUNE_VALUES_VAR}"
                  for q in BEL.find_input_pin(n, "TargetArray").list_connected_pins())
           and any("Max" in _title(PIN.get_owning_node(q))
                   for q in BEL.find_input_pin(n, "Item").list_connected_pins())]
    check("a nudge writes TuneValues, held at the stat's minimum (FMax)",
          len(fed) == 1, f"{len(writes)} Set Array Elem, {len(fed)} on TuneValues")

    missing = []
    for _col, var, _label, _step, _min, kind in TUNE_STATS:
        sets = [n for n in nodes if _title(n) == f"Set {var}"
                and BEL.find_input_pin(n, "self").list_connected_pins()]
        into = [PIN.get_owning_node(q) for n in sets
                for q in BEL.find_input_pin(n, var).list_connected_pins()]
        want = "Round" if kind is int else "Get"
        if not any(want in _title(f) for f in into):
            missing.append(var)
    check(f"every tuned stat is written onto the carried gun ({len(TUNE_STATS)} Sets, "
          "ints rounded)", not missing, str(missing))
    _check_apply_goes_on(check, nodes)
    _check_melee(check, nodes)


def _check_apply_goes_on(check, nodes):
    """The apply's loop over the carried items must hand Tick on. With its
    Completed loose, a touched table (a nudge, or a kept save loaded at
    BeginPlay) ended Tick there, and the menu's rows after it went dead: no
    new game from the title."""
    first = f"Set {TUNE_STATS[0][1]}"
    loops = [n for n in nodes
             if any(str(PIN.get_pin_name(q)) == "LoopBody" for q in BEL.list_output_pins(n))
             and any(_title(PIN.get_owning_node(q)) == first
                     for o in BEL.list_output_pins(n)
                     if str(PIN.get_pin_name(o)).replace(" ", "") == "ArrayElement"
                     for q in o.list_connected_pins())]
    done = [o for n in loops for o in BEL.list_output_pins(n)
            if str(PIN.get_pin_name(o)) == "Completed" and o.list_connected_pins()]
    check("the apply's loop over the carried items hands Tick on when it completes, "
          "so a touched table never cuts off the fragments after it (the menu's rows)",
          len(loops) == 1 and len(done) == 1,
          f"{len(loops)} loop(s), {len(done)} with Completed wired")


def _from_live(pin):
    """Is this bool pin a cell of TuneLive?"""
    return any(_title(PIN.get_owning_node(q)) == f"Get {TC.TUNE_LIVE_VAR}"
               for src in pin.list_connected_pins()
               for q in BEL.find_input_pin(PIN.get_owning_node(src), "TargetArray")
               .list_connected_pins()
               if "TargetArray" in _pins(PIN.get_owning_node(src)))


def _check_melee(check, nodes):
    """The melee weapons' rows: only their own stats move, show and land."""
    guards = [n for n in nodes if _title(n) == "Branch"
              and _from_live(BEL.find_input_pin(n, "Condition"))]
    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
              and any(_title(PIN.get_owning_node(q)) == f"Get {TC.TUNE_VALUES_VAR}"
                      for q in BEL.find_input_pin(n, "TargetArray").list_connected_pins())]
    gated = [n for n in writes
             if any(PIN.get_owning_node(q) in guards
                    for q in BEL.find_input_pin(n, "execute").list_connected_pins())]
    check(f"a nudge moves only a stat that is the shown weapon's own: the write "
          f"is behind one Branch on its {TC.TUNE_LIVE_VAR} cell",
          len(guards) == 1 and gated == writes and len(writes) == 1,
          f"{len(guards)} Branch(es), {len(gated)} of {len(writes)} write(s)")
    per_var = {}
    for _col, var, *_rest in TUNE_STATS:
        per_var[var] = len([n for n in nodes if _title(n) == f"Set {var}"
                            and BEL.find_input_pin(n, "self").list_connected_pins()])
    want = {var: (col in MELEE_COLUMNS) + (col in GUN_COLUMNS) for col, var, *_r in TUNE_STATS}
    check("the table is written per kind: a carried gun takes its own stats, a "
          f"carried melee weapon only its throw's ({len(MELEE_COLUMNS)} Sets)",
          per_var == want, str({v: n for v, n in per_var.items() if n != want[v]}))
    picks = [n for n in nodes if {"A", "B", "bPickA"} <= _pins(n)
             and _from_live(BEL.find_input_pin(n, "bPickA"))]
    check(f"the panel shows a {TC.TUNE_DASH!r} for a stat that is not the weapon's own",
          len(picks) == 1
          and str(BEL.find_input_pin(picks[0], "B").get_pin_value()) == TC.TUNE_DASH,
          str(len(picks)))


def _check_grip(check, nodes):
    """The grip rows (grip_tune.py): the held item's row of the nudge table
    into the table's grip cells and back, one C++ node each."""
    cells = [n for n in nodes if {"Item", "Table", "First"} <= _pins(n)]
    wired = [n for n in cells
             if any(_title(PIN.get_owning_node(q)) == f"Get {TC.TUNE_VALUES_VAR}"
                    for q in BEL.find_input_pin(n, "Table").list_connected_pins())
             and any("HeldItemOf" in _title(PIN.get_owning_node(q)).replace(" ", "")
                     for q in BEL.find_input_pin(n, "Item").list_connected_pins())
             and BEL.find_input_pin(n, "execute").list_connected_pins()]
    kinds = sorted(_title(n).replace(" ", "") for n in wired)
    check("the grip rows are the held item's row of the nudge table: read into "
          f"{TC.TUNE_VALUES_VAR} and written back, once each",
          len(cells) == 2 and kinds == ["ReadGripCells", "WriteGripCells"], str(kinds))
    labels = TC.TUNE_ROW_LABELS[1 + TC.GRIP_FIRST:]
    check(f"...the tab's last {len(GRIP_STATS)} rows, a step and a signed minimum each",
          labels == tuple(s[1] for s in GRIP_STATS)
          and TC.STAT_COUNT == len(TUNE_STATS) + len(GRIP_STATS)
          and tune_defaults()[TC.TUNE_MINS_VAR][TC.GRIP_FIRST:] == [GRIP_MIN] * len(GRIP_STATS)
          and all(tune_defaults()[TC.TUNE_LIVE_VAR][w * TC.STAT_COUNT + TC.GRIP_FIRST + i]
                  for w in range(len(tune_defaults()[TC.TUNE_WEAPONS_VAR]))
                  for i in range(len(GRIP_STATS))), str(labels))


def check_tune(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    defaults = tune_defaults()
    wrong = [k for k, v in defaults.items()
             if not (_same(cdo.get_editor_property(k), v) if isinstance(v, list)
                     else cdo.get_editor_property(k) == v)]
    check("the tuning tab starts shut, untouched, with the built table "
          f"({len(defaults[TC.TUNE_WEAPONS_VAR])} guns x {TC.STAT_COUNT} stats)",
          not wrong, str(wrong))
    _check_csv(check)
    _check_native_format(check, defaults)
    _check_widgets(check)
    _check_graph(check, nodes)
    _check_grip(check, nodes)
