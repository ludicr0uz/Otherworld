"""verify_graphics_menu.py's checks for the WORLD TUNING tab
(world_tune_tick, tune_draw and wbp_tune over WORLD_TAB). Beside
monster_tune_checks.py, which checks the same machine for the creatures.
world_tuning.csv reaching BP_DayNightCycle is verify_day_night's.
"""

import unreal

from graphics_menu import umg_consts as UC
from graphics_menu import world_tune_consts as WC
from graphics_menu.umg_checks import _tree
from graphics_menu.world_tune_tick import world_tune_defaults
from world.paths import DAY_NIGHT_CLASS_PATH
from world.world_tuning import WORLD_STATS

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TAB = WC.WORLD_TAB


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _same(a, b):
    a, b = list(a), list(b)
    return len(a) == len(b) and all(
        abs(float(x) - float(y)) < 1e-6 if isinstance(y, float) else x == y
        for x, y in zip(a, b))


def _feeds(pin):
    return [_title(PIN.get_owning_node(q)) for q in pin.list_connected_pins()]


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_PAUSE_MENU).items()}
    box = widgets.get(TAB.rows_box)
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR))
              for k in (box.get_all_children() if box else [])]
    check(f"WBP_PauseMenu has the world tuning panel, its {TAB.row_count} rows "
          f"labelled world, time of day, day and night length, night cold, and the "
          f"saved line",
          TAB.panel in widgets and TAB.saved_text in widgets
          and labels == list(TAB.row_labels), str(labels))
    hidden = [n for n in (TAB.panel, TAB.saved_text) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...collapsed until the HUD shows it", len(hidden) == 2, str(hidden))
    check("the M panel lists the world tab's key",
          WC.WORLD_TUNE_ROW_LABEL in UC.PAUSE_ROW_LABELS, str(UC.PAUSE_ROW_LABELS))


def _check_graph(check, nodes):
    runs = [n for n in nodes if "PythonCommand" in _pins(n)
            and str(BEL.find_input_pin(n, "PythonCommand").get_pin_value())
            == TAB.save_command]
    check("Enter on the world tab runs world_tune_save through ExecutePythonCommand, "
          "once, into WorldTuneSaved",
          len(runs) == 1
          and f"Set {TAB.saved_var}" in _feeds(BEL.find_output_pin(runs[0], "ReturnValue")),
          str(len(runs)))

    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
              and f"Get {TAB.values_var}" in _feeds(BEL.find_input_pin(n, "TargetArray"))]
    nudged = [n for n in writes
              if any("Max" in t for t in _feeds(BEL.find_input_pin(n, "Item")))]
    read_back = [n for n in writes if n not in nudged
                 and str(BEL.find_input_pin(n, "Index").get_pin_value()) == "0"]
    check("a world nudge writes WorldTuneValues (held at the row's minimum), and "
          "the cycle's clock is read back into the hour cell",
          len(writes) == 2 and len(nudged) == 1 and len(read_back) == 1,
          f"{len(writes)} writes, {len(nudged)} nudged, {len(read_back)} read back")

    cycle = DAY_NIGHT_CLASS_PATH.rsplit(".", 1)[-1][:-2]
    missing = []
    for var in [s[1] for s in WORLD_STATS if s[1]] + ["Clock"]:
        sets = [n for n in nodes if _title(n) == f"Set {var}"
                and any(t.replace(" ", "").endswith(f"CastTo{cycle}")
                        for t in _feeds(BEL.find_input_pin(n, "self")))]
        if len(sets) != 1:
            missing.append(f"{var} x{len(sets)}")
    check("the tab sets the cycle's day and night lengths, its night cold and its "
          "Clock, once each",
          not missing, str(missing))
    finds = [n for n in nodes if "ActorClass" in _pins(n)
             and "DayNightCycle" in str(BEL.find_input_pin(n, "ActorClass").get_pin_value())]
    check("...on the level's BP_DayNightCycle (one GetActorOfClass)", len(finds) == 1,
          str(len(finds)))
    maps = [n for n in nodes if {"Value", "InRangeA", "OutRangeB"} <= _pins(n)]
    check("hours and the clock convert both ways (four MapRangeClamped)",
          len(maps) == 4, str(len(maps)))


def check_world_tune(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = [k for k, v in world_tune_defaults().items()
             if not (_same(cdo.get_editor_property(k), v) if isinstance(v, list)
                     else cdo.get_editor_property(k) == v)]
    check("the world tab starts shut, untouched, with the built day and night lengths "
          "and night cold",
          not wrong, str(wrong))
    _check_widgets(check)
    _check_graph(check, nodes)
