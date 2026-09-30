"""verify_graphics_menu.py's checks for the MONSTER TUNING tab
(monster_tune_tick, tune_draw and wbp_tune over MONSTER_TAB, and
monster_tuning.csv reaching the controllers). Beside tune_checks.py, which
checks the same machine for the guns.
"""

import unreal

from graphics_menu import monster_tune_consts as MC
from graphics_menu import umg_consts as UC
from graphics_menu.monster_tune_tick import monster_tune_defaults
from graphics_menu.umg_checks import _tree
from npc.monster_tuning import CSV_PATH, MONSTER_COLUMNS, MONSTER_STATS, read_table

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TAB = MC.MONSTER_TAB


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
    check("monster_tuning.csv has a row for every creature, and a cell for every stat",
          set(table) == set(MC.MON_CREATURES)
          and all(set(table[k]) == set(MONSTER_COLUMNS) for k in MC.MON_CREATURES),
          f"{CSV_PATH}: rows {sorted(table)}")
    bad = []
    for key, bp_path, _cls in MC.MON_CONTROLLERS:
        cdo = unreal.get_default_object(BEL.generated_class(unreal.load_asset(bp_path)))
        for col, var, *_rest in MONSTER_STATS:
            want = table.get(key, {}).get(col)
            got = cdo.get_editor_property(var)
            if want is None or abs(float(got) - float(want)) > 1e-4:
                bad.append(f"{key}.{var}={got} csv {want}")
    check(f"every creature's controller holds its monster_tuning.csv row "
          f"({len(MONSTER_STATS)} Tune variables each)", not bad, "; ".join(bad[:6]))


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_PAUSE_MENU).items()}
    box = widgets.get(TAB.rows_box)
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR))
              for k in (box.get_all_children() if box else [])]
    check(f"WBP_PauseMenu has the monster tuning panel, its {TAB.row_count} rows "
          f"labelled creature then each stat, and the saved line",
          TAB.panel in widgets and TAB.saved_text in widgets
          and labels == list(TAB.row_labels), str(labels))
    hidden = [n for n in (TAB.panel, TAB.saved_text) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...collapsed until the HUD shows it", len(hidden) == 2, str(hidden))
    check("the M panel lists the monster tab's key",
          MC.MON_TUNE_ROW_LABEL in UC.PAUSE_ROW_LABELS, str(UC.PAUSE_ROW_LABELS))


def _check_graph(check, nodes):
    runs = [n for n in nodes if "PythonCommand" in _pins(n)
            and str(BEL.find_input_pin(n, "PythonCommand").get_pin_value())
            == TAB.save_command]
    check("Enter on the monster tab runs monster_tune_save through "
          "ExecutePythonCommand, once, into MonTuneSaved",
          len(runs) == 1 and any(
              _title(PIN.get_owning_node(q)) == f"Set {TAB.saved_var}"
              for q in BEL.find_output_pin(runs[0], "ReturnValue").list_connected_pins()),
          str(len(runs)))

    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
              and any(_title(PIN.get_owning_node(q)) == f"Get {TAB.values_var}"
                      for q in BEL.find_input_pin(n, "TargetArray").list_connected_pins())]
    check("a monster nudge writes MonTuneValues, held at the stat's minimum (FMax)",
          len(writes) == 1 and any(
              "Max" in _title(PIN.get_owning_node(q))
              for q in BEL.find_input_pin(writes[0], "Item").list_connected_pins()),
          str(len(writes)))

    # Each Tune variable is written onto each creature's controller, from the
    # table: one Set per stat per creature, its self from a cast.
    missing = []
    for _key, _bp, cls in MC.MON_CONTROLLERS:
        for _col, var, *_rest in MONSTER_STATS:
            name = cls.rsplit(".", 1)[-1][:-2]
            sets = [n for n in nodes if _title(n) == f"Set {var}"
                    and any(_title(PIN.get_owning_node(q)).replace(" ", "")
                            .endswith(f"CastTo{name}")
                            for q in BEL.find_input_pin(n, "self").list_connected_pins())]
            if len(sets) != 1:
                missing.append(f"{cls.rsplit('.', 1)[-1]}.{var} x{len(sets)}")
    check(f"every Tune variable is written onto every creature's live controllers "
          f"({len(MC.MON_CONTROLLERS)} x {len(MONSTER_STATS)} Sets)",
          not missing, str(missing[:6]))
    classes = [str(BEL.find_input_pin(n, "ActorClass").get_pin_value())
               for n in nodes if "ActorClass" in _pins(n)]
    check("...found with one GetAllActorsOfClass per creature's controller class",
          all(sum(c[2] in f for f in classes) == 1 for c in MC.MON_CONTROLLERS),
          str(sorted(classes)))


def check_monster_tune(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    defaults = monster_tune_defaults()
    wrong = [k for k, v in defaults.items()
             if not (_same(cdo.get_editor_property(k), v) if isinstance(v, list)
                     else cdo.get_editor_property(k) == v)]
    check("the monster tab starts shut, untouched, with the built table "
          f"({len(MC.MON_CREATURES)} creatures x {MC.MON_STAT_COUNT} stats)",
          not wrong, str(wrong))
    _check_csv(check)
    _check_widgets(check)
    _check_graph(check, nodes)
