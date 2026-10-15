"""verify_graphics_menu.py's checks for the DEBUG SETTINGS tab
(debug_tune_tick, tune_draw and wbp_tune over DEBUG_TAB): its rows and FULL
STATS, the three switches onto the GameState's DebugMode, DebugShots and DebugShotLog, OFF
or ON in the panel, and the cheat filling the player's stats. What the flags
turn on is verify_weapons_and_combat's (tracers, impact damage:
combat/verify/firing.py) and verify_npc_blueprints' (the sight cones).
"""

import unreal

from graphics_menu import debug_tune_consts as DC
from graphics_menu import umg_consts as UC
from graphics_menu.debug_tune_tick import FILLS, debug_tune_defaults
from graphics_menu.umg_checks import _tree
from graphics_menu.world_tune_checks import _feeds, _pins, _same, _title

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TAB = DC.DEBUG_TAB


def _sources(n, pin):
    return [PIN.get_owning_node(q) for q in BEL.find_input_pin(n, pin).list_connected_pins()]


def _is_set(n, var):
    t = _title(n)
    return t.startswith("Set") and t.endswith(f" {var}")


def _literal(n, pin):
    return str(BEL.find_input_pin(n, pin).get_pin_value())


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_PAUSE_MENU).items()}
    box = widgets.get(TAB.rows_box)
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR))
              for k in (box.get_all_children() if box else [])]
    check("WBP_PauseMenu has the debug panel, its rows overlays, monster vision "
          "and agro, shot trajectory and shot log, its FULL STATS row and the done line",
          TAB.panel in widgets and TAB.saved_text in widgets and TAB.save_widget in widgets
          and labels == list(TAB.row_labels), str(labels))
    hidden = [n for n in (TAB.panel, TAB.saved_text) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...collapsed until the HUD shows it", len(hidden) == 2, str(hidden))
    check("the menu lists Debug Settings where Debug was, and no Debug ON/OFF row",
          UC.PAUSE_ROW_LABELS[3] == DC.DEBUG_TUNE_ROW_LABEL
          and "Debug" not in UC.PAUSE_ROW_LABELS, str(UC.PAUSE_ROW_LABELS))


def _check_switches(check, nodes):
    wrong = []
    for s, (_label, flag) in enumerate(DC.DEBUG_SWITCHES):
        sets = [n for n in nodes if _is_set(n, flag)]
        if len(sets) != 1:
            wrong.append(f"{flag} x{len(sets)}")
            continue
        tests = _sources(sets[0], flag)
        cells = [c for t in tests for c in _sources(t, "A")] if tests else []
        ok = (len(tests) == 1 and "B" in _pins(tests[0])
              and abs(float(_literal(tests[0], "B")) - DC.SWITCH_ON_ABOVE) < 1e-6
              and len(cells) == 1
              # A literal 0 is the pin's default: "" once loaded from disk.
              and _literal(cells[0], "Index") in ((str(s), "") if s == 0 else (str(s),))
              and f"Get {TAB.values_var}" in _feeds(BEL.find_input_pin(cells[0], "TargetArray"))
              and any("GameState" in t.replace(" ", "")
                      for t in _feeds(BEL.find_input_pin(sets[0], "self"))))
        if not ok:
            wrong.append(f"{flag} from {[_title(t) for t in tests]}")
    check("the tab sets the GameState's DebugMode from its first switch, "
          "DebugShots from its second and DebugShotLog from its third, each ON above a half, once each",
          not wrong, str(wrong))
    lowered = [n for n in nodes if _is_set(n, TAB.touched_var)
               and _literal(n, TAB.touched_var).lower() == "false"]
    check("...once per change: the apply lowers DebugTuneTouched",
          len(lowered) == 1, str(len(lowered)))
    words = [n for n in nodes if {"A", "B", "bPickA"} <= _pins(n)
             and _literal(n, "A") == DC.DEBUG_ON_WORD and _literal(n, "B") == DC.DEBUG_OFF_WORD]
    check("the panel shows each switch as ON or OFF, not as a number",
          len(words) == 1, str(len(words)))


def _check_cheat(check, nodes):
    wrong = []
    for _owner, stat, ceiling in FILLS:
        fills = [n for n in nodes if _is_set(n, stat)
                 and f"Get {ceiling}" in _feeds(BEL.find_input_pin(n, str(stat)))]
        if len(fills) != 1:
            wrong.append(f"{stat} x{len(fills)}")
    hands = [n for n in nodes if {"Character", "NewStamina"} <= _pins(n)
             and "Get MaxStamina" in _feeds(BEL.find_input_pin(n, "NewStamina"))]
    check("FULL STATS sets health, stamina, hunger, thirst and temperature to "
          "their maximums, once each, and hands the movement its full stamina",
          not wrong and len(hands) == 1, f"{wrong}, {len(hands)} SetStamina")
    done = [n for n in nodes if _is_set(n, TAB.saved_var)
            and _literal(n, TAB.saved_var).lower() == "true"]
    check("...and says so (DebugTuneCheated), once", len(done) == 1, str(len(done)))
    python = [n for n in nodes if "PythonCommand" in _pins(n)
              and not _literal(n, "PythonCommand")]
    check("the debug tab runs no Python: its row is the cheat, not a save",
          not python, str(len(python)))


def check_debug_tune(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = [k for k, v in debug_tune_defaults().items()
             if not (_same(cdo.get_editor_property(k), v) if isinstance(v, list)
                     else cdo.get_editor_property(k) == v)]
    check("the debug tab starts shut, every switch off, each moving 0 to 1 by 1",
          not wrong, str(wrong))
    _check_widgets(check)
    _check_switches(check, nodes)
    _check_cheat(check, nodes)
