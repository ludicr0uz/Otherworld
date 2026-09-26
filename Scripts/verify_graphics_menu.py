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
    expected_cmds.add(G.FPS_COMMAND)
    check("every preset's console overrides are present, plus the FPS readout",
          commands == expected_cmds,
          str(sorted(commands ^ expected_cmds)) if commands != expected_cmds else "")
    # The FPS indicator is the engine's own stat display, so the only evidence
    # of it in the graph is this one command -- nothing is drawn on the canvas.
    check("BeginPlay turns on the built-in FPS readout (top-right)",
          G.FPS_COMMAND in commands)

    # ApplyNonResolutionSettings takes no arguments, so it is the only node in
    # the graph whose inputs are exactly exec + self.
    applies = [n for n in nodes if pin_names(n) == {"execute", "self"}]
    check("ApplyNonResolutionSettings once per preset, plus BeginPlay's",
          len(applies) == len(G.PRESETS) + 1, str(len(applies)))
    # Regression guard, and the single most important check in this file:
    # ApplySettings also applies *resolution*, which on macOS drives
    # SWindow::SetWindowMode -> FMacWindow::UpdateFullScreenState and hangs the
    # editor at 100% CPU the moment PIE starts.
    check("no ApplySettings anywhere (it hangs macOS PIE on a window-mode change)",
          not by_pins("bCheckForCommandLineOverrides"))

    # --- drawing
    texts = by_pins("Text", "ScreenX")
    drawn = {BEL.find_input_pin(n, "Text").get_pin_value() for n in texts}
    expected_text = {"GRAPHICS QUALITY", f"[{G.MENU_KEY}]   close", ">", "HP"}
    expected_text |= {f"[{i + 1}]   {p[0]}" for i, p in enumerate(G.PRESETS)}
    # The health number has no literal text -- its Text pin is driven -- so it
    # contributes an empty string here.
    expected_text |= {""}
    check("panel draws title, three rows, hint, caret and the HP label",
          drawn == expected_text, str(sorted(drawn ^ expected_text)))
    # One backs the quality panel, two are the player's HP track and fill, two
    # more are an NPC bar's track and fill, five are the empty inventory slots,
    # and the last two are a filled slot and the equipped slot's underline.
    expected_rects = 1 + 2 + 2 + G.INVENTORY_SIZE + 2 + 5
    check(f"{expected_rects} DrawRects: panel, HP, NPC bar, inventory, reticle",
          len(by_pins("RectColor")) == expected_rects,
          str(len(by_pins("RectColor"))))

    # The caret is the only text whose position is computed rather than literal.
    caret = [n for n in texts
             if BEL.find_input_pin(n, "Text").get_pin_value() == ">"]
    if caret:
        y = BEL.find_input_pin(caret[0], "ScreenY")
        check("caret's ScreenY is driven by Quality, not a constant",
              bool(y.list_connected_pins()))

    # --- the health readout
    health_reads = [n for n in nodes
                    if "Health" in pin_names(n, False) or
                    "MaxHealth" in pin_names(n, False)]
    # Two pairs now: the player's bar and the NPC bars read the same component.
    check("HUD reads Health and MaxHealth for both the player and the NPCs",
          len(health_reads) == 4, str(len(health_reads)))

    # --- the reticle
    # It must be nailed to the centre of the viewport. Drawing it at the
    # projected impact point was tried and reverted -- the crosshair slid around
    # under its own parallax -- so a second Project() call here is a regression,
    # not a feature.
    projects = [n for n in nodes
                if str(BEL.get_node_title(n)).replace("\n", " ") == "Project"]
    check("only the NPC bars project a world point; the reticle does not",
          len(projects) == 1, str(len(projects)))
    aim_reads = {str(BEL.get_node_title(n)) for n in nodes
                 if str(BEL.get_node_title(n)).startswith("Get Aim")}
    check("the reticle reads AimValid and AimBlocked, and not AimPoint",
          aim_reads == {"Get AimValid", "Get AimBlocked"}, str(sorted(aim_reads)))
    viewports = [n for n in nodes
                 if str(BEL.get_node_title(n)).replace("\n", " ") == "GetViewportSize"]
    check("the reticle and the inventory strip both centre off the viewport size",
          len(viewports) == 2, str(len(viewports)))
    check("a blocked shot colours the reticle differently",
          any(str(BEL.get_node_title(n)) == "SelectColor" for n in nodes)
          and "Get AimBlocked" in aim_reads)

    lookups = by_pins("ComponentClass")
    wanted = {G.HEALTH_CLASS_PATH, G.WEAPON_COMP_CLASS_PATH}
    found = {str(BEL.find_input_pin(n, "ComponentClass").get_pin_value())
             for n in lookups}
    # Four: the player's health, an NPC's health, the weapon component for the
    # inventory strip, and the weapon component again for the reticle.
    check("HUD looks up health (player + NPC) and the weapon component",
          len(lookups) == 4 and all(any(w in f for f in found) for w in wanted),
          f"{len(lookups)} lookups: {sorted(found)}")

    # A fill rect's width is computed from a health fraction; the track behind it
    # is literal. Two of them now -- the player's bar and the NPC bars.
    rects = by_pins("RectColor")
    driven = [n for n in rects
              if BEL.find_input_pin(n, "ScreenW").list_connected_pins()]
    check("both HP fills are driven by Health, not by a constant",
          len(driven) == 2, str(len(driven)))

    # --- the new HUD layers
    npc_scans = [n for n in by_pins("ActorClass")
                 if "ForestWanderer" in
                 str(BEL.find_input_pin(n, "ActorClass").get_pin_value())]
    check("a bar is drawn for every wanderer in the level",
          len(npc_scans) == 1, f"{len(npc_scans)} GetAllActorsOfClass(NPC)")

    # Two texts are driven rather than literal: the player's HP number and each
    # inventory slot's weapon name. A literal slot name would mean the HUD kept
    # its own copy of the weapon list.
    driven_text = [n for n in texts
                   if not BEL.find_input_pin(n, "Text").get_pin_value()
                   and BEL.find_input_pin(n, "Text").list_connected_pins()]
    # Three now: the player's HP number, each inventory slot's weapon name, and
    # each wanderer's spawn number.
    check("HP number, slot names and NPC numbers are read from data",
          len(driven_text) == 3, str(len(driven_text)))
    ids = [n for n in nodes
           if "NpcId" in {str(p_) for p_ in pin_names(n, False)}]
    check("each NPC bar carries the wanderer's spawn number",
          len(ids) == 1, f"{len(ids)} NpcId read(s)")

    # A pawn with no health component must not take the menu down with it.
    check("HP number is drawn from a driven Text pin",
          any(not BEL.find_input_pin(n, "Text").get_pin_value() and
              BEL.find_input_pin(n, "Text").list_connected_pins() for n in texts))

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
