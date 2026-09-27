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
    # The restart key is polled from ReceiveDrawHUD, not from Tick: Tick does
    # not run while the game is paused, and the death menu only exists paused.
    expected_keys = set((G.MENU_KEY, G.RESTART_KEY, G.DEBUG_KEY) + G.PRESET_KEYS)
    check("polls exactly the menu, preset, debug and restart keys",
          keys == expected_keys,
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
    expected_text = {"GRAPHICS QUALITY", f"[{G.MENU_KEY}]   close", ">", "HP",
                     "STA", "YOU DIED", f"[{G.RESTART_KEY}]   try again",
                     # Two draws behind one branch, because there is no
                     # SelectString and a bool rendered as "true" is a
                     # variable's value rather than a setting's state.
                     f"[{G.DEBUG_KEY}]   debug   ON",
                     f"[{G.DEBUG_KEY}]   debug   OFF"}
    expected_text |= {f"[{i + 1}]   {p[0]}" for i, p in enumerate(G.PRESETS)}
    # The health number has no literal text -- its Text pin is driven -- so it
    # contributes an empty string here.
    expected_text |= {""}
    check("panel, HP, stamina, debug row and the death menu draw their labels",
          drawn == expected_text, str(sorted(drawn ^ expected_text)))
    # Almost everything that used to be a DrawRect is a DrawTexture now -- see
    # the generated-artwork note in build_graphics_menu.py. What is left as
    # rects is the reticle, and only the reticle: five hairline ticks, where a
    # texture would buy nothing and cost a sample.
    expected_rects = 5
    check(f"{expected_rects} DrawRects, all of them the reticle",
          len(by_pins("RectColor")) == expected_rects,
          str(len(by_pins("RectColor"))))

    # One quality panel, one death panel, five empty slots, the equipped
    # frame, the carried weapon's icon, and a track+fill for each of HP,
    # stamina and the NPC bar.
    expected_textures = 1 + 1 + G.INVENTORY_SIZE + 1 + 1 + 2 + 2 + 2
    textures = by_pins("Texture")
    check(f"{expected_textures} DrawTextures: panels, slots, weapon icon, bars",
          len(textures) == expected_textures, str(len(textures)))

    # The weapon icon is the one whose Texture is DRIVEN -- it comes off the
    # item, so the strip holds no table of weapon names. Everything else names
    # a constant.
    driven = [n for n in textures
              if BEL.find_input_pin(n, "Texture").list_connected_pins()]
    check("exactly one DrawTexture takes its texture from the weapon itself",
          len(driven) == 1, str(len(driven)))

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
    # Four now: the reticle and the inventory strip centre off it, the kill
    # counter right-anchors off it, and the death panel centres off it.
    check("everything positioned off the window edge reads the viewport size",
          len(viewports) == 4, str(len(viewports)))
    check("a blocked shot colours the reticle differently",
          any(str(BEL.get_node_title(n)) == "SelectColor" for n in nodes)
          and "Get AimBlocked" in aim_reads)

    lookups = by_pins("ComponentClass")
    wanted = {G.HEALTH_CLASS_PATH, G.WEAPON_COMP_CLASS_PATH}
    found = {str(BEL.find_input_pin(n, "ComponentClass").get_pin_value())
             for n in lookups}
    # Four: the player's health, an NPC's health, the weapon component for the
    # inventory strip, and the weapon component again for the reticle.
    # Five: the player's health, an NPC's health, and the weapon component
    # three times -- inventory strip, reticle, and the stamina bar.
    check("HUD looks up health (player + NPC) and the weapon component",
          len(lookups) == 5 and all(any(w in f for f in found) for w in wanted),
          f"{len(lookups)} lookups: {sorted(found)}")

    # A fill's width is computed from a health fraction; the track behind it is
    # literal. Three of them -- the player's HP, the NPC bars, and stamina.
    # These are DrawTextures now, so the bars can have a lit gradient; the test
    # is unchanged in substance, only in which node type it counts.
    driven = [n for n in by_pins("Texture")
              if BEL.find_input_pin(n, "ScreenW").list_connected_pins()]
    check("the HP, NPC and stamina fills are all driven, not constants",
          len(driven) == 3, str(len(driven)))

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
    # Six now: the HP number, each slot's weapon name, each slot's ammunition,
    # each wanderer's spawn number, the kill counter and the final score.
    check("HP, slot names, ammo, NPC numbers, kills and the score read from data",
          len(driven_text) == 6, str(len(driven_text)))
    ids = [n for n in nodes
           if "NpcId" in {str(p_) for p_ in pin_names(n, False)}]
    check("each NPC bar carries the wanderer's spawn number",
          len(ids) == 1, f"{len(ids)} NpcId read(s)")

    # A pawn with no health component must not take the menu down with it.
    check("HP number is drawn from a driven Text pin",
          any(not BEL.find_input_pin(n, "Text").get_pin_value() and
              BEL.find_input_pin(n, "Text").list_connected_pins() for n in texts))

    # --- the kill counter, the stamina bar and the death menu
    titles = [str(BEL.get_node_title(n)).replace("\n", " ") for n in nodes]

    check("the HUD reads the kill count off the GameMode",
          any(t == f"Get {G.KILL_COUNT_VAR}" for t in titles),
          str(sorted({t for t in titles if "Kill" in t})))
    # Twice: once for the corner and once for the death menu's final score. The
    # menu re-reads rather than being handed a copy, so the two can never
    # disagree about the score.
    check("the corner and the death menu read the same counter",
          sum(1 for t in titles if t == f"Get {G.KILL_COUNT_VAR}") == 2,
          str(sum(1 for t in titles if t == f"Get {G.KILL_COUNT_VAR}")))
    kill_labels = [n for n in by_pins("A", "B")
                   if BEL.find_input_pin(n, "A").get_pin_value() == "KILLS  "]
    check("the counter is labelled KILLS", len(kill_labels) == 1,
          str(len(kill_labels)))

    # Right-anchored, not placed at a fixed x: the counter has to stay in the
    # corner at any window size, like the inventory strip stays centred.
    kill_texts = [n for n in texts
                  if BEL.find_input_pin(n, "ScreenX").list_connected_pins()
                  and float(BEL.find_input_pin(n, "ScreenY").get_pin_value() or 0)
                  == G.KILL_TOP]
    check("the kill counter is anchored to the right edge, not a fixed x",
          len(kill_texts) == 1, str(len(kill_texts)))

    # --- stamina
    stamina_reads = {t for t in titles if t in ("Get Stamina", "Get MaxStamina",
                                                "Get Sprinting")}
    check("the stamina bar reads Stamina, MaxStamina and Sprinting",
          stamina_reads == {"Get Stamina", "Get MaxStamina", "Get Sprinting"},
          str(sorted(stamina_reads)))
    st_rects = [n for n in by_pins("Texture")
                if float(BEL.find_input_pin(n, "ScreenY").get_pin_value() or -1)
                == G.ST_BAR[1]]
    check("the stamina bar has a track and a fill, under the HP bar",
          len(st_rects) == 2 and G.ST_BAR[1] > G.HP_BAR[1],
          f"{len(st_rects)} rects at y={G.ST_BAR[1]}")
    # Two SelectColors now: the reticle's blocked state and the stamina fill.
    check("the stamina fill changes colour while the key is held",
          sum(1 for t in titles if t == "SelectColor") == 2,
          str(sum(1 for t in titles if t == "SelectColor")))

    # --- the NPC bars are hidden unless something just got hurt
    check("a wanderer's bar reads when it was last damaged",
          any(t == f"Get {G.LAST_DAMAGE_VAR}" for t in titles),
          str(sorted({t for t in titles if "Damage" in t})))
    windows = [n for n in nodes
               if pin_names(n) == {"A", "B"}
               and BEL.find_input_pin(n, "B").get_pin_value()
               == str(G.NPC_BAR_SECONDS)]
    check(f"the bar is shown for {G.NPC_BAR_SECONDS:.0f}s after a hit and "
          f"hidden otherwise", len(windows) == 1, str(len(windows)))
    check("...measured against the clock, not against a frame counter",
          any(t == "GetTimeSeconds" for t in titles), str(len(titles)))

    # --- the death menu
    check("the HUD knows whether the player is dead",
          any(t == f"Get {G.PLAYER_DEAD_VAR}" for t in titles))
    # Twice: once to decide whether to draw the HUD at all, once inside the
    # menu block. The first is what makes the menu *replace* the HUD -- a
    # reticle and an inventory strip over a death screen read as a game still
    # being played.
    check("the death menu replaces the HUD rather than covering it",
          sum(1 for t in titles if t == f"Get {G.PLAYER_DEAD_VAR}") == 2,
          str(sum(1 for t in titles if t == f"Get {G.PLAYER_DEAD_VAR}")))
    check("the menu offers a restart",
          any(t.startswith("Open Level") for t in titles),
          str(sorted({t for t in titles if "Level" in t})))
    # ...of whatever level is loaded, so a generated map restarts as itself.
    check("it restarts the current level, not a path written down here",
          any("Current Level Name" in t or "GetCurrentLevelName" in t
              for t in titles),
          str(sorted({t for t in titles if "Level" in t})))
    # And it unpauses first: a level opened while the world is paused comes up
    # paused, with nothing left able to unpause it.
    unpauses = by_pins("bPaused")
    check("restarting unpauses before it reopens", len(unpauses) == 1
          and BEL.find_input_pin(unpauses[0], "bPaused").get_pin_value()
          in ("false", "False"),
          str([BEL.find_input_pin(n, "bPaused").get_pin_value()
               for n in unpauses]))

    # --- the shotgun's ammunition, beside its icon
    # Read off the item like SlotColor and DisplayName are, so the strip stays
    # a view of whatever is carried and knows nothing about shotguns.
    for var in ("UsesAmmo", "Loaded", "Reserve"):
        check(f"the slot reads the weapon's own {var}",
              sum(1 for t in titles if t == f"Get {var}") == 1,
              str(sum(1 for t in titles if t == f"Get {var}")))
    check("the count is rounds-in-gun / rounds-in-reserve, not one number",
          any(BEL.find_input_pin(n, "A").get_pin_value() == " / "
              for n in by_pins("A", "B")
              if BEL.find_input_pin(n, "A")),
          "a ' / ' separator")
    # The pistol is deliberately unlimited, so its slot must stay empty rather
    # than claim an infinity nobody has to manage.
    check("...and only weapons that use ammunition show it at all",
          sum(1 for t in titles if t == "Get UsesAmmo") == 1)

    # --- debug mode
    # The flag lives on the GameMode, because BP_WeaponComponent draws the
    # tracers and a component cannot reach a HUD variable.
    check(f"{G.DEBUG_KEY} toggles debug mode on the GameMode, not on the HUD",
          any(t == f"Set {G.DEBUG_MODE_VAR}" for t in titles),
          str(sorted({t for t in titles if G.DEBUG_MODE_VAR in t})))
    # Twice: the toggle reads it to flip it, and DrawHUD reads it to copy it.
    check("...by flipping what is already there, so it is a toggle",
          sum(1 for t in titles if t == f"Get {G.DEBUG_MODE_VAR}") == 2,
          str(sum(1 for t in titles if t == f"Get {G.DEBUG_MODE_VAR}")))
    # Copied once per frame into DebugOn. The point is the cast-failed path:
    # it reaches the same drawing code, and a Get off an invalid object is an
    # "Accessed None" per wanderer per frame. Two writes -- the real value and
    # the false the failed cast gets.
    check("this frame's copy is taken once, with an answer for a failed cast",
          sum(1 for t in titles if t == "Set DebugOn") == 2,
          str(sum(1 for t in titles if t == "Set DebugOn")))
    # Two readers: the menu row that reports the state, and the NPC number.
    check("the tracer's twin -- the wanderer's number -- is gated on the copy",
          sum(1 for t in titles if t == "Get DebugOn") == 2,
          str(sum(1 for t in titles if t == "Get DebugOn")))
    hud_cdo = unreal.get_default_object(BEL.generated_class(bp))
    check("the HUD starts with the overlays off",
          hud_cdo.get_editor_property("DebugOn") is False)

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
