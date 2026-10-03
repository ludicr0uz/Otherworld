"""verify_graphics_menu.py's checks for the SOUND SETTINGS tab
(sound_tune_tick, tune_draw and wbp_tune over SOUND_TAB). Beside
player_tune_checks.py, which checks the same machine for the player. The
sound classes on the waves are verify_weapons_and_combat's
(combat/verify/sound_mix.py).
"""

import unreal

from combat.sound_mix import SOUND_MIX_PATH, class_path
from combat.sound_tuning import FOOTSTEPS, SOUND_STATS, VOLUME_MAX, VOLUME_MIN
from graphics_menu import sound_tune_consts as SC
from graphics_menu import umg_consts as UC
from graphics_menu.sound_tune_tick import CLASS_PIN, MIX_PIN, sound_tune_defaults
from graphics_menu.umg_checks import _tree
from graphics_menu.world_tune_checks import _feeds, _pins, _same, _title

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TAB = SC.SOUND_TAB


def _literal(node, name):
    return str(BEL.find_input_pin(node, name).get_pin_value())


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_PAUSE_MENU).items()}
    box = widgets.get(TAB.rows_box)
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR))
              for k in (box.get_all_children() if box else [])]
    check(f"WBP_PauseMenu has the sound tuning panel, its {TAB.row_count} rows "
          f"labelled volume and then one per sound, and the saved line",
          TAB.panel in widgets and TAB.saved_text in widgets
          and labels == list(TAB.row_labels), str(labels))
    hidden = [n for n in (TAB.panel, TAB.saved_text) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...collapsed until the HUD shows it", len(hidden) == 2, str(hidden))
    check("the menu lists the sound tab's row",
          SC.SOUND_TUNE_ROW_LABEL in UC.PAUSE_ROW_LABELS, str(UC.PAUSE_ROW_LABELS))


def _check_graph(check, nodes):
    runs = [n for n in nodes if "PythonCommand" in _pins(n)
            and _literal(n, "PythonCommand") == TAB.save_command]
    check("Enter on the sound tab runs sound_tune_save through "
          "ExecutePythonCommand, once, into SoundTuneSaved",
          len(runs) == 1
          and f"Set {TAB.saved_var}" in _feeds(BEL.find_output_pin(runs[0], "ReturnValue")),
          str(len(runs)))
    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
              and f"Get {TAB.values_var}" in _feeds(BEL.find_input_pin(n, "TargetArray"))]
    check("a sound nudge writes SoundTuneValues, held between the row's minimum "
          "and maximum, and nothing else does",
          len(writes) == 1
          and any("Max" in t or "Min" in t
                  for t in _feeds(BEL.find_input_pin(writes[0], "Item")))
          and VOLUME_MIN == 0.0 and VOLUME_MAX > 1.0, f"{len(writes)} writes")

    bases = [n for n in nodes if "InSoundMix" in _pins(n)]
    check("the HUD makes A_Mix_Game the base sound mix (one SetBaseSoundMix)",
          len(bases) == 1 and SOUND_MIX_PATH in _literal(bases[0], "InSoundMix"),
          str([_literal(n, "InSoundMix") for n in bases]))
    sets = [n for n in nodes if {MIX_PIN, CLASS_PIN, "Volume", "FadeInTime"} <= _pins(n)]
    wrong = []
    for s, (sound, *_rest) in enumerate(SOUND_STATS):
        mine = [n for n in sets if class_path(sound) + "." in _literal(n, CLASS_PIN)]
        if len(mine) != 1:
            wrong.append(f"{sound} x{len(mine)}")
            continue
        cells = [PIN.get_owning_node(q)
                 for q in BEL.find_input_pin(mine[0], "Volume").list_connected_pins()]
        ok = (len(cells) == 1 and SOUND_MIX_PATH in _literal(mine[0], MIX_PIN)
              # A literal 0 is the pin's default: "" once loaded from disk.
              and _literal(cells[0], "Index") in ((str(s), "") if s == 0 else (str(s),))
              and f"Get {TAB.values_var}" in _feeds(BEL.find_input_pin(cells[0], "TargetArray"))
              and float(_literal(mine[0], "FadeInTime") or 0.0) == 0.0)
        if not ok:
            wrong.append(f"{sound} from {[_title(c) for c in cells]}")
    check(f"...and overrides each of the {len(SOUND_STATS)} sound classes' volume in "
          f"it, once each, from its own cell, with no fade",
          not wrong and len(sets) == len(SOUND_STATS), f"{len(sets)} overrides; {wrong}")
    gates = [n for n in nodes if _title(n) == "Branch"
             and any("OR" in t.upper() for t in _feeds(BEL.find_input_pin(n, "Condition")))
             and any(f"Get {TAB.touched_var}" in _feeds(p) and any(
                 "NOT" in t.upper() for t in _feeds(q))
                 for o in (PIN.get_owning_node(c) for c in
                           BEL.find_input_pin(n, "Condition").list_connected_pins())
                 for p, q in ((BEL.find_input_pin(o, "A"), BEL.find_input_pin(o, "B")),)
                 if p and q)]
    lowered = [n for n in nodes if _title(n) == f"Set {TAB.touched_var}"
               and _literal(n, TAB.touched_var) == "false"]
    raised = [n for n in nodes if _title(n) == f"Set {SC.SOUND_TUNE_APPLIED_VAR}"
              and _literal(n, SC.SOUND_TUNE_APPLIED_VAR) == "true"]
    check("...on the HUD's first Tick (SoundTuneApplied still false) and after a "
          "nudge (SoundTuneTouched, lowered again once the mix is told)",
          len(gates) == 1 and len(lowered) == 1 and len(raised) == 1,
          f"{len(gates)} gates, {len(lowered)} lowered, {len(raised)} raised")


def check_sound_tune(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    built = sound_tune_defaults()
    wrong = [k for k, v in built.items()
             if not (_same(cdo.get_editor_property(k), v) if isinstance(v, list)
                     else cdo.get_editor_property(k) == v)]
    check("the sound tab starts shut, untouched, the mix not yet told, with "
          "sound_tuning.csv's volumes",
          not wrong, str(wrong))
    steps = built[TAB.values_var][[s[0] for s in SOUND_STATS].index(FOOTSTEPS)]
    check("the footsteps are quieter than recorded (under 1)", steps < 1.0, f"{steps}")
    _check_widgets(check)
    _check_graph(check, nodes)
