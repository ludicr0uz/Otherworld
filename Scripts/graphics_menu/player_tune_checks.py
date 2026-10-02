"""verify_graphics_menu.py's checks for the PLAYER TUNING tab
(player_tune_tick, tune_draw and wbp_tune over PLAYER_TAB). Beside
world_tune_checks.py, which checks the same machine for the day and night.
player_tuning.csv reaching the character and BP_WeaponComponent is
verify_weapons_and_combat's (combat/verify/sprint.py).
"""

import unreal

from combat.player_tuning import PLAYER_STATS
from combat.sprint_tuning import BASE_SPEED_VAR, SPRINT_RATE_VARS
from graphics_menu import player_tune_consts as PC
from graphics_menu import umg_consts as UC
from graphics_menu.player_tune_tick import APPLIES, SPEED, player_tune_defaults
from graphics_menu.umg_checks import _tree
from graphics_menu.world_tune_checks import _feeds, _pins, _same, _title

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TAB = PC.PLAYER_TAB


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_PAUSE_MENU).items()}
    box = widgets.get(TAB.rows_box)
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR))
              for k in (box.get_all_children() if box else [])]
    check(f"WBP_PauseMenu has the player tuning panel, its {TAB.row_count} rows "
          f"labelled player, jog and sprint speed, sprint from full, recharge to "
          f"full, and the saved line",
          TAB.panel in widgets and TAB.saved_text in widgets
          and labels == list(TAB.row_labels), str(labels))
    hidden = [n for n in (TAB.panel, TAB.saved_text) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...collapsed until the HUD shows it", len(hidden) == 2, str(hidden))
    check("the menu lists the player tab's row",
          PC.PLAYER_TUNE_ROW_LABEL in UC.PAUSE_ROW_LABELS, str(UC.PAUSE_ROW_LABELS))


def _check_graph(check, nodes):
    runs = [n for n in nodes if "PythonCommand" in _pins(n)
            and str(BEL.find_input_pin(n, "PythonCommand").get_pin_value())
            == TAB.save_command]
    check("Enter on the player tab runs player_tune_save through "
          "ExecutePythonCommand, once, into PlayerTuneSaved",
          len(runs) == 1
          and f"Set {TAB.saved_var}" in _feeds(BEL.find_output_pin(runs[0], "ReturnValue")),
          str(len(runs)))
    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
              and f"Get {TAB.values_var}" in _feeds(BEL.find_input_pin(n, "TargetArray"))]
    check("a player nudge writes PlayerTuneValues, held at the row's minimum (so "
          "no time reaches zero), and nothing else does",
          len(writes) == 1
          and any("Max" in t for t in _feeds(BEL.find_input_pin(writes[0], "Item")))
          and all(s[3] > 0.0 for s in PLAYER_STATS), f"{len(writes)} writes")

    wrong = []
    for s, (col, *_rest) in enumerate(PLAYER_STATS):
        var, kind = APPLIES[col]
        sets = [n for n in nodes if _title(n) == f"Set {var}"
                and any("WeaponComponent" in t.replace(" ", "")
                        for t in _feeds(BEL.find_input_pin(n, "self")))]
        if len(sets) != 1:
            wrong.append(f"{var} x{len(sets)}")
            continue
        maths = [PIN.get_owning_node(q)
                 for q in BEL.find_input_pin(sets[0], var).list_connected_pins()]
        # A speed is its cell x 100; a time divides the component's MaxStamina.
        cell_pin, other = ("A", "B") if kind == SPEED else ("B", "A")
        cells = [PIN.get_owning_node(q) for m in maths
                 for q in BEL.find_input_pin(m, cell_pin).list_connected_pins()]
        ok = (len(maths) == 1 and len(cells) == 1
              # A literal 0 is the pin's default: "" once loaded from disk.
              and str(BEL.find_input_pin(cells[0], "Index").get_pin_value())
              in ((str(s), "") if s == 0 else (str(s),))
              and f"Get {TAB.values_var}" in _feeds(BEL.find_input_pin(cells[0], "TargetArray"))
              and (float(BEL.find_input_pin(maths[0], other).get_pin_value()) == 100.0
                   if kind == SPEED else
                   _feeds(BEL.find_input_pin(maths[0], other)) == ["Get MaxStamina"]))
        if not ok:
            wrong.append(f"{var} from {[_title(m) for m in maths]}")
    check("once touched, the tab sets the weapon component's BaseSpeed and "
          "SprintSpeed (m/s x 100) and its stamina drain and regen (MaxStamina / "
          "seconds), once each, from its own cell",
          not wrong and set(v for v, _k in APPLIES.values())
          == {BASE_SPEED_VAR, *SPRINT_RATE_VARS}, str(wrong))


def check_player_tune(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = [k for k, v in player_tune_defaults().items()
             if not (_same(cdo.get_editor_property(k), v) if isinstance(v, list)
                     else cdo.get_editor_property(k) == v)]
    check("the player tab starts shut, untouched, with player_tuning.csv's speeds "
          "and stamina times",
          not wrong, str(wrong))
    _check_widgets(check)
    _check_graph(check, nodes)
