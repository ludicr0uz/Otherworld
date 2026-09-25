"""
verify_graphics_menu.py — in-engine checks for the graphics-quality menu.

    UnrealEditor-Cmd <uproject> -ExecutePythonScript="<abs>/Scripts/verify_graphics_menu.py" -NoUI -stdout

Reads the *saved* assets back, so it catches anything that compiled but did not
persist.  Logs `[VERIFY]` lines and a PASS/FAIL tally, matching the generated
level scripts' convention.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_graphics_menu as G

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary

_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition)))
    mark = "ok  " if condition else "FAIL"
    unreal.log_warning(f"[VERIFY] {mark} {name}{(' — ' + detail) if detail else ''}")


def pin_names(node, direction_inputs=True):
    pins = (BEL.list_input_pins(node) if direction_inputs
            else BEL.list_output_pins(node))
    return {str(PIN.get_pin_name(p)) for p in pins}


def main():
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

    check("HUD blueprint exists", eas.does_asset_exist(G.HUD_BP_PATH), G.HUD_BP_PATH)
    bp = eas.load_asset(G.HUD_BP_PATH)
    check("parented to AHUD",
          BEL.get_blueprint_parent_class(bp) == unreal.HUD.static_class())

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()

    check("compiles without node errors", not ed.list_nodes_with_errors(),
          str(len(ed.list_nodes_with_errors())))
    check("compiles without node warnings", not ed.list_nodes_with_warnings(),
          str(len(ed.list_nodes_with_warnings())))

    # --- member variables
    names = {str(n) for n in BEL.list_member_variable_names(bp, False)}
    check("MenuOpen variable", "MenuOpen" in names)
    check("Quality variable", "Quality" in names)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check("menu starts closed", cdo.get_editor_property("MenuOpen") is False)
    check(f"Quality defaults to {G.DEFAULT_PRESET} ({G.PRESETS[G.DEFAULT_PRESET][0]})",
          cdo.get_editor_property("Quality") == G.DEFAULT_PRESET,
          str(cdo.get_editor_property("Quality")))

    # --- both entry points exist and are wired
    tick = ed.find_event_node("ReceiveTick")
    check("Event Tick present", tick is not None)
    if tick:
        then = BEL.find_then_pin(tick)
        check("Event Tick drives the input chain",
              then and then.is_valid() and bool(then.list_connected_pins()))

    begin = ed.find_event_node("ReceiveBeginPlay")
    check("Event BeginPlay present", begin is not None)
    if begin:
        then = BEL.find_then_pin(begin)
        check(f"BeginPlay applies the startup default "
              f"({G.PRESETS[G.DEFAULT_PRESET][0]})",
              then and then.is_valid() and bool(then.list_connected_pins()))

    draw = ed.find_event_node("ReceiveDrawHUD")
    check("Event ReceiveDrawHUD present", draw is not None)
    if draw:
        then = BEL.find_then_pin(draw)
        check("Event ReceiveDrawHUD drives the draw chain",
              then and then.is_valid() and bool(then.list_connected_pins()))

    # --- input: every key the menu documents is actually polled
    # get_node_title comes back empty for every node in UE 5.8's Python layer,
    # so nodes are identified by their input-pin signature instead -- which is
    # what actually distinguishes these calls from one another anyway.
    def by_pins(*required):
        want = set(required)
        return [n for n in nodes if want <= pin_names(n)]

    keys = set()
    for n in by_pins("Key"):
        keys.add(BEL.find_input_pin(n, "Key").get_pin_value())
    # Bare key names: FKey exports as its name, so struct text would silently
    # import back as a key called "(".
    expected_keys = set((G.MENU_KEY,) + G.PRESET_KEYS)
    check("polls exactly the menu + preset keys", keys == expected_keys,
          f"{sorted(keys)} vs {sorted(expected_keys)}")

    # --- each preset applies its own scalability level and cvars
    # One chain per preset key, plus the BeginPlay one that applies the default.
    expected_levels = sorted([p[1] for p in G.PRESETS]
                             + [G.PRESETS[G.DEFAULT_PRESET][1]])
    levels = sorted(int(BEL.find_input_pin(n, "Value").get_pin_value())
                    for n in by_pins("Value"))
    check("one scalability call per preset, plus BeginPlay's default",
          levels == expected_levels, f"{levels} vs {expected_levels}")

    commands = {BEL.find_input_pin(n, "Command").get_pin_value()
                for n in by_pins("Command")}
    expected_cmds = set()
    for _label, _level, shadow, pct in G.PRESETS:
        expected_cmds.add(f"r.ShadowQuality {shadow}")
        expected_cmds.add(f"r.ScreenPercentage {pct}")
    check("every preset's console overrides are present",
          commands == expected_cmds,
          str(sorted(commands ^ expected_cmds)) if commands != expected_cmds else "")

    applies = by_pins("bCheckForCommandLineOverrides")
    check("ApplySettings once per preset, plus BeginPlay's",
          len(applies) == len(G.PRESETS) + 1, str(len(applies)))
    check("ApplySettings ignores command-line overrides",
          all(BEL.find_input_pin(n, "bCheckForCommandLineOverrides").get_pin_value()
              == "false" for n in applies))

    # --- drawing
    texts = by_pins("Text", "ScreenX")
    drawn = {BEL.find_input_pin(n, "Text").get_pin_value() for n in texts}
    expected_text = {"GRAPHICS QUALITY", f"[{G.MENU_KEY}]   close", ">"}
    expected_text |= {f"[{i + 1}]   {p[0]}" for i, p in enumerate(G.PRESETS)}
    check("panel draws title, three rows, hint and caret",
          drawn == expected_text, str(sorted(drawn ^ expected_text)))
    check("one DrawRect backing the panel", len(by_pins("RectColor")) == 1)

    # The caret is the only text whose position is computed rather than literal.
    caret = [n for n in texts
             if BEL.find_input_pin(n, "Text").get_pin_value() == ">"]
    if caret:
        y = BEL.find_input_pin(caret[0], "ScreenY")
        check("caret's ScreenY is driven by Quality, not a constant",
              bool(y.list_connected_pins()))

    # --- the wiring that actually puts it on screen
    gm = eas.load_asset(G.GAME_MODE_PATH)
    gm_cdo = unreal.get_default_object(BEL.generated_class(gm))
    check("default game mode uses the menu HUD",
          gm_cdo.get_editor_property("hud_class") == BEL.generated_class(bp),
          str(gm_cdo.get_editor_property("hud_class")))

    passed = sum(1 for _n, ok in _results if ok)
    total = len(_results)
    unreal.log_warning(f"[VERIFY] {passed}/{total} checks passed")
    if passed != total:
        for n, ok in _results:
            if not ok:
                unreal.log_error(f"[VERIFY] failed: {n}")


main()
