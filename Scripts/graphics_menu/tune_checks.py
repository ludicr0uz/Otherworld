"""verify_graphics_menu.py's checks for the GUN TUNING tab (tune_tick,
tune_draw, wbp_tune, and gun_tuning.csv reaching the guns). Here rather than
in the verifier, which is over its size budget.
"""

import unreal

from combat.gun_tuning import CSV_PATH, TUNE_COLUMNS, TUNE_STATS, read_table
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


def _check_csv(check):
    table = read_table()
    guns = [sp["display"] for sp in _weapon_specs()]
    check("gun_tuning.csv has a row for every gun, and a cell for every stat",
          set(table) == set(guns)
          and all(set(table[g]) == set(TUNE_COLUMNS) for g in guns),
          f"{CSV_PATH}: rows {sorted(table)}")
    bad = []
    for sp in _weapon_specs():
        cdo = unreal.get_default_object(BEL.generated_class(unreal.load_asset(sp["path"])))
        for col, var, _label, _step, _min, _kind in TUNE_STATS:
            want = table.get(sp["display"], {}).get(col)
            got = cdo.get_editor_property(var)
            if want is None or abs(float(got) - float(want)) > 1e-4:
                bad.append(f"{sp['display']}.{var}={got} csv {want}")
    check(f"every gun holds its gun_tuning.csv row ({len(TUNE_STATS)} stats each)",
          not bad, "; ".join(bad[:6]))


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


def _check_graph(check, nodes):
    # MONSTER TUNING has its own, with its own command (monster_tune_checks).
    calls = [n for n in nodes if "PythonCommand" in _pins(n)]
    runs = [n for n in calls if str(BEL.find_input_pin(n, "PythonCommand")
                                    .get_pin_value()) == TC.TUNE_SAVE_COMMAND]
    check("Enter's save runs tune_save through ExecutePythonCommand, once",
          len(runs) == 1, f"{len(runs)} of {len(calls)} Python calls")
    saved = [q for n in runs for q in BEL.find_output_pin(n, "ReturnValue")
             .list_connected_pins()]
    check("...and its success is what TuneSaved shows",
          any(_title(PIN.get_owning_node(q)) == f"Set {TC.TUNE_SAVED_VAR}" for q in saved))

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
    _check_widgets(check)
    _check_graph(check, nodes)
