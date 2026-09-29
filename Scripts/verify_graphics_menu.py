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
from graphics_menu import canvas as C
from graphics_menu import fps as F
from graphics_menu import menu_nav as N
from graphics_menu import grass_tiers as T
from graphics_menu import presets as P
from graphics_menu import settings_rows as S
from graphics_menu import survival_bars as SB
from graphics_menu import scope as SC
from combat.tuning import COMBAT

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary

_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition)))
    mark = "ok  " if condition else "FAIL"
    unreal.log_warning(f"[VERIFY] {mark} {name}{(' — ' + detail) if detail else ''}")


def float_pin(node, name):
    """An input pin's literal as a float, or None if it has none."""
    p = BEL.find_input_pin(node, name)
    try:
        return float(p.get_pin_value()) if p and p.is_valid() else None
    except ValueError:
        return None


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

    # "Key" and "self" together: a key POLL is a PlayerController method, which
    # Key_GetDisplayName (a static library pure with a Key pin of its own) is
    # not. Without the self pin that node counts as an eighth poll of nothing.
    keys = set()
    driven_keys = []
    for n in by_pins("Key", "self"):
        pin = BEL.find_input_pin(n, "Key")
        if pin.list_connected_pins():
            driven_keys.append(n)
        else:
            keys.add(pin.get_pin_value())
    # Bare key names: FKey exports as its name, so struct text would silently
    # import back as a key called "(".
    # The restart key is polled from ReceiveDrawHUD, not from Tick: Tick does
    # not run while the game is paused, and the death menu only exists paused.
    # The main menu's start keys are polled from ReceiveDrawHUD for the same
    # reason the restart key is, and so are the four navigation keys.
    expected_keys = set((G.MENU_KEY, G.RESTART_KEY, G.DEBUG_KEY,
                         N.NAV_UP, N.NAV_DOWN, N.NAV_LEFT, N.NAV_RIGHT)
                        + G.PRESET_KEYS + G.START_KEYS)
    check("polls exactly the menu, preset, debug, restart, start and nav keys",
          keys == expected_keys,
          f"{sorted(keys)} vs {sorted(expected_keys)}")
    # Exactly one Key pin in this graph is driven rather than literal: the
    # capture poll, which asks the PlayerController about each entry of KeyPool
    # in turn. That is the only place a key is a value rather than a constant.
    check("one key poll is driven -- the rebind capture, over KeyPool",
          len(driven_keys) == 1, str(len(driven_keys)))
    # The navigation keys must not be bindable, or a keypress can lock the
    # settings screen shut with no way back but deleting the save.
    nav = {N.NAV_UP, N.NAV_DOWN, N.NAV_LEFT, N.NAV_RIGHT} | set(G.START_KEYS)
    check("...and the menu's own keys are not in the pool it offers",
          not (nav & set(G.KEY_POOL)), str(sorted(nav & set(G.KEY_POOL))))

    # --- each preset applies its own scalability level and cvars
    # One chain per preset key, plus the BeginPlay one that applies the default.
    expected_levels = sorted([p[1] for p in G.PRESETS]
                             + [G.PRESETS[G.DEFAULT_PRESET][1]])
    # "Value" alone no longer identifies SetOverallScalabilityLevel -- the
    # settings page's FClamp has one too, and its literal is a float.
    levels = sorted(int(BEL.find_input_pin(n, "Value").get_pin_value())
                    for n in by_pins("Value") if "Min" not in pin_names(n))
    check("one scalability call per preset, plus BeginPlay's default",
          levels == expected_levels, f"{levels} vs {expected_levels}")

    commands = {BEL.find_input_pin(n, "Command").get_pin_value()
                for n in by_pins("Command")}
    expected_cmds = set()
    for preset in G.PRESETS:
        expected_cmds.update(P.console_commands(preset))
    check("every preset's console overrides are present, and nothing else",
          commands == expected_cmds,
          str(sorted(commands ^ expected_cmds)) if commands != expected_cmds else "")
    # `stat fps` is a toggle, so sending it could just as well switch the
    # readout off; the FPS readout is drawn on the canvas instead (fps.py).
    check("no `stat` console commands (they toggle)",
          not any(c.startswith("stat ") for c in commands), str(sorted(commands)))

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

    # --- grass lighting follows Quality (presets.author_grass_sync)
    check(f"{P.GRASS_APPLIED_VAR} variable", P.GRASS_APPLIED_VAR in names)
    check(f"{P.GRASS_APPLIED_VAR} defaults to {P.GRASS_APPLIED_DEFAULT} "
          "(so the first Tick always applies)",
          cdo.get_editor_property(P.GRASS_APPLIED_VAR) == P.GRASS_APPLIED_DEFAULT,
          str(cdo.get_editor_property(P.GRASS_APPLIED_VAR)))
    tagged = [BEL.find_input_pin(n, "Tag").get_pin_value()
              for n in by_pins("Tag") if "ComponentClass" not in pin_names(n)]
    want_tags = [P.GRASS_TAG] + [T.tier_tag(i) for i, _ in T.SWITCHED_TIERS]
    check(f"grass cells are found by their tags, {', '.join(want_tags)}",
          sorted(tagged) == sorted(want_tags), str(tagged))
    # --- grass density follows Quality (grass_tiers.author_tier_visibility)
    # One SetActorHiddenInGame per switched tier, each fed by Quality < the
    # tier's first preset, and each looping over that tier's own tag.
    hides = by_pins("bNewHidden", "self", "execute")
    thresholds = []
    for n in hides:
        for src in BEL.find_input_pin(n, "bNewHidden").list_connected_pins():
            b = BEL.find_input_pin(PIN.get_owning_node(src), "B")
            thresholds.append(b.get_pin_value() if b else None)
    want = [str(t.min_preset) for _, t in T.SWITCHED_TIERS]
    check("each grass tier is hidden below its preset "
          f"({', '.join(want)})", sorted(thresholds) == sorted(want),
          str(thresholds))
    check("every tier hide runs (exec wired)",
          len(hides) == len(want) and all(
              BEL.find_input_pin(n, "execute").list_connected_pins() for n in hides),
          str(len(hides)))
    for _fn, arg in P.GRASS_SETTERS:
        setters = by_pins(arg, "self", "execute")
        # Driven by the Quality comparison, never a literal: a literal would
        # light (or unlight) the grass for every preset alike.
        driven = [n for n in setters
                  if BEL.find_input_pin(n, arg).list_connected_pins()
                  and BEL.find_input_pin(n, "execute").list_connected_pins()]
        check(f"{arg} is set once, from Quality", len(driven) == 1 == len(setters),
              f"{len(driven)} driven of {len(setters)}")
    # The comparison feeding the setters, found by following the wire back
    # from SetCastShadow: its B literal is the first preset that lights grass.
    thresholds = []
    arg = P.GRASS_SETTERS[0][1]
    for n in by_pins(arg, "self", "execute"):
        for src in BEL.find_input_pin(n, arg).list_connected_pins():
            b = BEL.find_input_pin(PIN.get_owning_node(src), "B")
            thresholds.append(b.get_pin_value() if b else None)
    check(f"grass is lit from preset {P.GRASS_LIGHTS_FROM} "
          f"({G.PRESETS[P.GRASS_LIGHTS_FROM].label}) up",
          thresholds == [str(P.GRASS_LIGHTS_FROM)], str(thresholds))

    # --- drawing
    texts = by_pins("Text", "ScreenX")
    drawn = {BEL.find_input_pin(n, "Text").get_pin_value() for n in texts}
    expected_text = {"GRAPHICS QUALITY", f"[{G.MENU_KEY}]   close", ">", "HP",
                     "STA", "YOU DIED", f"[{G.RESTART_KEY}]   try again",
                     # Two draws behind one branch, because there is no
                     # SelectString and a bool rendered as "true" is a
                     # variable's value rather than a setting's state.
                     f"[{G.DEBUG_KEY}]   debug   ON",
                     f"[{G.DEBUG_KEY}]   debug   OFF",
                     # The main menu, drawn before anything else while
                     # GameStarted is false, and the settings page behind it.
                     G.GAME_TITLE, G.GAME_SUBTITLE,
                     "UP / DOWN  ·  ENTER selects",
                     S.SETTINGS_TITLE, S.BACK_LABEL,
                     *(sl.label for sl in S.SLIDERS),
                     "press any key to bind it",
                     "arrows adjust  ·  ENTER rebinds"}
    expected_text |= set(G.MENU_ROWS)
    expected_text |= {f"[{i + 1}]   {p[0]}" for i, p in enumerate(G.PRESETS)}
    # The health number has no literal text -- its Text pin is driven -- so it
    # contributes an empty string here.
    expected_text |= {""}
    # The survival bars' labels, and the debuff names drawn beside them.
    expected_text |= {label for _s, label, _c, _y in SB.SURVIVAL_BARS}
    expected_text |= {label for _t, label, _s in SB.DEBUFF_LABELS}
    check("panel, HP, stamina, debug row and the death menu draw their labels",
          drawn == expected_text, str(sorted(drawn ^ expected_text)))
    # Almost everything that used to be a DrawRect is a DrawTexture now -- see
    # the generated-artwork note in build_graphics_menu.py. What is left as
    # rects is the reticle -- five hairline ticks, where a texture would buy
    # nothing and cost a sample -- plus the two strips either side of the
    # sniper's scope, which are flat black by definition.
    expected_rects = 5 + 2
    check(f"{expected_rects} DrawRects: the reticle, and the scope's surround",
          len(by_pins("RectColor")) == expected_rects,
          str(len(by_pins("RectColor"))))

    # One quality panel, one death panel, the main-menu panel and its NEW GAME
    # button plate, five empty slots, the equipped slot's lit background, the
    # equipped frame, the carried weapon's icon, and a track+fill for each of
    # HP, stamina and the NPC bar.
    # ...plus the settings page's panel, which is the same artwork stretched
    # taller rather than a second texture to keep in step.
    # ...plus the sniper's scope.
    # ...plus a track+fill for each survival bar.
    expected_textures = (1 + 1 + 2 + 1 + G.INVENTORY_SIZE + 1 + 1 + 1 + 2 + 2 + 2 + 1
                         + 2 * len(SB.SURVIVAL_BARS))
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

    # DrawTexture's UV rectangle is NORMALISED: the whole picture is 1x1. It
    # was once given the texel size, which tiles the texture that many times
    # -- the menu's button became a grid of amber borders and every panel
    # vanished into transparent corner texels. Nothing errors when that
    # happens, so it is checked here.
    bad_uv = []
    for n in textures:
        uv = tuple(float(BEL.find_input_pin(n, p).get_pin_value() or 0)
                   for p in ("TextureU", "TextureV", "TextureUWidth",
                             "TextureVHeight"))
        if uv != (0.0, 0.0, 1.0, 1.0):
            bad_uv.append(str(uv))
    check("every DrawTexture samples the whole texture once (UV 0,0 + 1x1)",
          not bad_uv, "; ".join(bad_uv))

    # --- the artwork is the size the HUD thinks it is -----------------------
    # The HUD draws each texture at the size in UI_TEX_SIZE -- a table of
    # numbers, not a measurement. If
    # a texture is regenerated at a different size (the slots went from 104x68
    # to 120x84 for exactly this reason) and that table is not updated, or the
    # PNGs are rebuilt and never re-imported, the HUD samples a rectangle that
    # is not the picture. Nothing errors; the art is just subtly wrong.
    wrong = []
    for name, (want_w, want_h) in G.UI_TEX_SIZE.items():
        tex = eas.load_asset(f"{C.UI_ART_DIR}/{name}")
        if not tex:
            wrong.append(f"{name} not imported")
            continue
        got = (tex.blueprint_get_size_x(), tex.blueprint_get_size_y())
        if got != (want_w, want_h):
            wrong.append(f"{name} is {got[0]}x{got[1]}, HUD draws "
                         f"{want_w}x{want_h}")
    check("every imported texture is the size the HUD samples it at",
          not wrong, "; ".join(wrong))
    icons = []
    for display in ("Pistol", "Shotgun", "SMG", "Rifle", "Sniper"):
        tex = eas.load_asset(f"{C.UI_ART_DIR}/T_UI_Icon_{display}")
        if not tex:
            icons.append(f"{display} not imported")
        elif (tex.blueprint_get_size_x(),
              tex.blueprint_get_size_y()) != G.ICON_TEX_SIZE:
            icons.append(f"{display} is "
                         f"{tex.blueprint_get_size_x()}x"
                         f"{tex.blueprint_get_size_y()}")
    check("...and so is every weapon icon", not icons, "; ".join(icons))

    # --- the main menu ------------------------------------------------------
    # The game must not be running behind the title screen: BeginPlay pauses,
    # and only the menu unpauses. Two SetGamePaused calls with a literal true
    # would mean something else pausing as well, which is worth knowing about.
    paused = by_pins("bPaused")
    literals = [BEL.find_input_pin(n, "bPaused").get_pin_value() for n in paused]
    check("exactly one SetGamePaused(true) -- the main menu's, at BeginPlay",
          literals.count("true") == 1, str(literals))
    # ...and not on frame zero: a world paused before its first tick never
    # updates the camera, so the menu would be seen from inside the player.
    delays = [n for n in by_pins("Duration", "execute")
              if abs(float(BEL.find_input_pin(n, "Duration").get_pin_value() or 0)
                     - G.MENU_SETTLE_S) < 1e-6]
    check(f"the menu pause waits {G.MENU_SETTLE_S}s for the camera to settle",
          len(delays) == 1, str(len(delays)))
    # Two unpause: the menu's NEW GAME and the death menu's restart.
    check("two SetGamePaused(false) -- starting a game and restarting one",
          literals.count("false") == 2, str(literals))

    keys = {str(BEL.find_input_pin(n, "Key").get_pin_value())
            for n in by_pins("Key")}
    for key in G.START_KEYS:
        check(f"the main menu accepts {key}", key in keys, str(sorted(keys)))

    started = [n for n in nodes
               if G.GAME_STARTED_VAR in str(BEL.get_node_title(n))]
    check(f"{G.GAME_STARTED_VAR} is read and written",
          len(started) >= 2, str(len(started)))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check(f"{G.GAME_STARTED_VAR} starts false, so the menu is what loads",
          cdo.get_editor_property(G.GAME_STARTED_VAR) is False)

    # Two carets: the quality panel's, driven by Quality, and the settings
    # page's, driven by MenuRow. Both are the same idea -- one number decides
    # which row is marked, so there is no per-row bookkeeping to fall out of
    # step with what is drawn.
    caret = [n for n in texts
             if BEL.find_input_pin(n, "Text").get_pin_value() == ">"]
    check("two carets: the quality panel's and the settings page's",
          len(caret) == 2, str(len(caret)))
    check("...and both take their ScreenY from a variable, not a constant",
          all(BEL.find_input_pin(n, "ScreenY").list_connected_pins()
              for n in caret))

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
    # Six now: the reticle and the inventory strip centre off it, the kill
    # counter right-anchors off it, and the death panel, the main menu and the
    # settings page each centre off it. Seven with the debug FPS readout,
    # right-anchored above the kill counter.
    check("everything positioned off the window edge reads the viewport size",
          len(viewports) == 7, str(len(viewports)))
    check("a blocked shot colours the reticle differently",
          any(str(BEL.get_node_title(n)) == "SelectColor" for n in nodes)
          and "Get AimBlocked" in aim_reads)

    # --- the sniper's scope
    # It must be the SNIPER's ADS and not everyone's, it must replace the
    # crosshair rather than sit under it, and it must cover the viewport at any
    # aspect ratio. All three are structural, and all three are the kind of
    # thing that looks right in the graph and is wrong on screen.
    def after(pin):
        for q in (pin.list_connected_pins() if pin and pin.is_valid() else []):
            return PIN.get_owning_node(q)
        return None

    titles = {str(BEL.get_node_title(n)).replace("\n", " ") for n in nodes}
    for var in ("Get Held", "Get Scoped", "Get AdsZoom",
                "Get BaseFOV", "Get CurrentFOV"):
        check(f"the scope reads {var[4:]}", var in titles)

    def upstream(pin, depth=4):
        """Titles of the nodes feeding a pin through data links, a few deep."""
        found, frontier = set(), [pin]
        for _ in range(depth):
            nxt = []
            for p in frontier:
                for q in p.list_connected_pins():
                    n = PIN.get_owning_node(q)
                    found.add(str(BEL.get_node_title(n)).replace("\n", " "))
                    nxt += [x for x in BEL.list_input_pins(n)
                            if str(PIN.get_pin_name(x)) != "execute"]
            frontier = nxt
        return found

    gate = [n for n in nodes
            if pin_names(n) == {"execute", "Condition"}
            and "Get Scoped" in upstream(BEL.find_input_pin(n, "Condition"))]
    check("one branch decides which sight is drawn, off the weapon's own "
          "Scoped flag", len(gate) == 1, str(len(gate)))
    if gate:
        cond = upstream(BEL.find_input_pin(gate[0], "Condition"))
        past = [n for n in nodes
                if float_pin(n, "B") is not None
                and abs(float_pin(n, "B")
                        - (COMBAT.shoulder_zoom + SC.SCOPE_GATE_SLACK)) < 1e-9
                and "Get CurrentFOV" in upstream(BEL.find_input_pin(n, "A"))]
        check("...AND the zoom being past the shoulder aim's, so the sniper "
              "keeps its crosshair on the hip and the shoulder and the glass "
              "is aiming down the sights only",
              "Get CurrentFOV" in cond and "Get BaseFOV" in cond and len(past) == 1,
              str(sorted(cond)))
    if gate:
        glass = after(BEL.find_then_pin(gate[0]))
        irons = after(BEL.find_else_pin(gate[0]))
        # The strips are sized off the viewport; the crosshair's ticks are
        # literal pixels. That is what tells the two draws apart here.
        check("a scoped weapon draws the surround...",
              glass is not None
              and BEL.find_input_pin(glass, "ScreenW").list_connected_pins())
        check("...and an unscoped one draws the crosshair, so the two centres "
              "never double up",
              irons is not None
              and not BEL.find_input_pin(irons, "ScreenW").list_connected_pins()
              and float(BEL.find_input_pin(irons, "ScreenW").get_pin_value())
              == G.RETICLE_ARM)

    strips = [n for n in by_pins("RectColor")
              if BEL.find_input_pin(n, "ScreenW").list_connected_pins()]
    check("two black strips flank the scope, so the corners of the world "
          "cannot show past it", len(strips) == 2, str(len(strips)))
    # Negative width is what a portrait viewport would ask for, and DrawRect
    # draws that backwards rather than not at all.
    floor = [n for n in nodes
             if str(BEL.get_node_title(n)).replace("\n", " ") == "Max (Float)"]
    check("...with their width floored at zero for a taller-than-wide window",
          len(floor) == 1
          and BEL.find_input_pin(floor[0], "B").get_pin_value() in ("", "0.0"),
          str(len(floor)))

    glass = [n for n in by_pins("Texture")
             if SC.SCOPE_TEX in str(BEL.find_input_pin(n, "Texture").get_pin_value())]
    check("exactly one DrawTexture is the scope itself", len(glass) == 1,
          str(len(glass)))
    if glass:
        w = BEL.find_input_pin(glass[0], "ScreenW").list_connected_pins()
        h = BEL.find_input_pin(glass[0], "ScreenH").list_connected_pins()
        # Same source on both: the texture is square and the hole in it is a
        # circle, so anything but a square on screen is an ellipse.
        check("the scope is drawn square, off the viewport height",
              bool(w) and bool(h)
              and PIN.get_owning_node(w[0]) == PIN.get_owning_node(h[0]))

    # The strips and the scope share one alpha, and that alpha is computed --
    # not a constant and not the Aiming flag, which would snap the glass on a
    # frame before the camera had moved.
    fades = [n for n in nodes
             if str(BEL.get_node_title(n)).replace("\n", " ") == "MakeColor"]
    check("the surround and the glass are one colour pair, faded together",
          len(fades) == 2, str(len(fades)))
    check("...and their alpha is driven by the zoom, not written down",
          all(BEL.find_input_pin(n, "A").list_connected_pins() for n in fades))
    alpha_clamp = [n for n in by_pins("Value", "Min", "Max")
                   if (float(BEL.find_input_pin(n, "Min").get_pin_value() or 0.0),
                       float(BEL.find_input_pin(n, "Max").get_pin_value() or 0.0))
                   == (0.0, 1.0)]
    check("the fade is clamped to 0..1, so a hipfire frame is fully clear",
          len(alpha_clamp) == 1, str(len(alpha_clamp)))
    # Measured from the shoulder aim's zoom, not from 1x: the sniper's shoulder
    # aim zooms 1.5x too, and from 1x that would be a fifth of the glass over
    # a view that is not down the sights.
    from_shoulder = [n for n in by_pins("A", "B")
                     if float_pin(n, "B") is not None
                     and abs(float_pin(n, "B") - COMBAT.shoulder_zoom) < 1e-9]
    check("...and measured from the shoulder aim's zoom, both ends of it, so "
          "a shouldered sniper shows no glass",
          len(from_shoulder) == 2,
          str([str(BEL.get_node_title(n)) for n in from_shoulder]))

    lookups = by_pins("ComponentClass")
    wanted = {G.HEALTH_CLASS_PATH, G.WEAPON_COMP_CLASS_PATH}
    found = {str(BEL.find_input_pin(n, "ComponentClass").get_pin_value())
             for n in lookups}
    # Four: the player's health, an NPC's health, the weapon component for the
    # inventory strip, and the weapon component again for the reticle.
    # Five: the player's health, an NPC's health, and the weapon component
    # three times -- inventory strip, reticle, and the stamina bar.
    # Six: the player's health, an NPC's health, and the weapon component four
    # times -- inventory strip, reticle, stamina bar, and the settings push.
    # Seven: and the survival component, for its bars.
    wanted.add(SB.SURVIVAL_CLASS_PATH)
    check("HUD looks up health (player + NPC), the weapon and survival components",
          len(lookups) == 7 and all(any(w in f for f in found) for w in wanted),
          f"{len(lookups)} lookups: {sorted(found)}")

    # A fill's width is computed from a health fraction; the track behind it is
    # literal. Three of them -- the player's HP, the NPC bars, and stamina.
    # These are DrawTextures now, so the bars can have a lit gradient; the test
    # is unchanged in substance, only in which node type it counts.
    # Four: the scope's square is sized off the viewport for the same reason.
    driven = [n for n in by_pins("Texture")
              if BEL.find_input_pin(n, "ScreenW").list_connected_pins()]
    # ...and one fill per survival bar.
    want_fills = 4 + len(SB.SURVIVAL_BARS)
    check("the HP, NPC, stamina and survival fills and the scope are driven, "
          "not constants", len(driven) == want_fills, f"{len(driven)}, want {want_fills}")

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
    # Nine now: the settings page adds the sensitivity readout and, inside one
    # ForEachLoop over Binds, a row label and a key name. Those last two are
    # what keeps the seven bind rows to a single pair of draws. Ten with the
    # debug FPS readout; one more per extra slider (scope sensitivity).
    want_driven = 9 + len(S.SLIDERS)
    check("HP, slot names, ammo, NPC numbers, kills, score, the settings "
          "rows and the FPS readout read from data",
          len(driven_text) == want_driven, f"{len(driven_text)}, want {want_driven}")
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
    # A corpse lies where it fell for a minute now, and it was shot a moment
    # ago by definition -- so the recency window alone would float an empty bar
    # over every body for its first five seconds.
    check("no bar floats over a corpse",
          any(t == "Get Dead" for t in titles),
          str(sorted({t for t in titles if "Dead" in t})))

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
    # Three SetGamePaused in the graph now: the main menu pauses at BeginPlay,
    # NEW GAME unpauses, and the restart unpauses. What this check is about is
    # the restart one, and the thing that identifies it is that it is the
    # unpause sitting in front of an OpenLevel.
    unpauses = [n for n in by_pins("bPaused")
                if BEL.find_input_pin(n, "bPaused").get_pin_value()
                in ("false", "False")]
    reopening = []
    for n in unpauses:
        then = BEL.find_then_pin(n)
        for other in (then.list_connected_pins() if then else []):
            owner = unreal.BlueprintGraphPinLibrary.get_owning_node(other)
            if owner and "Level" in str(BEL.get_node_title(owner)):
                reopening.append(n)
    check("restarting unpauses before it reopens", len(reopening) == 1,
          f"{len(unpauses)} unpauses, {len(reopening)} of them feeding an "
          f"Open Level")

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
    # Three reads: the toggle reads the GameMode's to flip it, DrawHUD reads
    # it to copy it, and BeginPlay reads the saved one off BP_Settings.
    check("...by flipping what is already there, so it is a toggle",
          sum(1 for t in titles if t == f"Get {G.DEBUG_MODE_VAR}") == 3,
          str(sum(1 for t in titles if t == f"Get {G.DEBUG_MODE_VAR}")))
    # Three writes: BeginPlay restores the saved value onto the GameMode, and
    # the toggle writes both the GameMode and the save.
    check("debug mode is restored from the save and written back to it",
          sum(1 for t in titles if t == f"Set {G.DEBUG_MODE_VAR}") == 3,
          str(sum(1 for t in titles if t == f"Set {G.DEBUG_MODE_VAR}")))
    # Copied once per frame into DebugOn. The point is the cast-failed path:
    # it reaches the same drawing code, and a Get off an invalid object is an
    # "Accessed None" per wanderer per frame. Two writes -- the real value and
    # the false the failed cast gets.
    check("this frame's copy is taken once, with an answer for a failed cast",
          sum(1 for t in titles if t == "Set DebugOn") == 2,
          str(sum(1 for t in titles if t == "Set DebugOn")))
    # Three readers: the menu row that reports the state, the NPC number, and
    # the FPS readout.
    check("the wanderer's number and the FPS readout are gated on the copy",
          sum(1 for t in titles if t == "Get DebugOn") == 3,
          str(sum(1 for t in titles if t == "Get DebugOn")))
    for var in (F.FPS_FRAMES_VAR, F.FPS_SINCE_VAR, F.FPS_SHOWN_VAR):
        check(f"{var} variable", var in names)
    check("the FPS readout counts real time, so it runs under the paused menus",
          any("Real Time" in t or "RealTime" in t for t in titles),
          str(sorted({t for t in titles if "Time" in t})))
    hud_cdo = unreal.get_default_object(BEL.generated_class(bp))
    check("the HUD starts with the overlays off",
          hud_cdo.get_editor_property("DebugOn") is False)

    # ─── Settings: mouse sensitivity, keybinds, and the save behind them ─────
    # The requirement these serve is "loadable across future game runs", so the
    # checks are about the disk and about the wiring, not about the drawing:
    # the page can look perfect and still be a session-only settings screen.
    for var in ("Settings", "MenuPage", "MenuRow", "Capturing", "KeyPool",
                "BindLabels"):
        check(f"{var} variable", var in names)
    check("the menu opens on the title page with the caret at the top",
          cdo.get_editor_property("MenuPage") == G.PAGE_TITLE
          and cdo.get_editor_property("MenuRow") == 0
          and cdo.get_editor_property("Capturing") is False,
          f"page {cdo.get_editor_property('MenuPage')}, "
          f"row {cdo.get_editor_property('MenuRow')}")
    pool = [k.export_text() for k in cdo.get_editor_property("KeyPool")]
    check("KeyPool is the set of keys a bind may be captured as",
          pool == list(G.KEY_POOL), f"{len(pool)} keys")
    check("...with no duplicates, so one press cannot bind twice",
          len(set(pool)) == len(pool))
    labels = [str(x) for x in cdo.get_editor_property("BindLabels")]
    check("one row label per bind, so the seven rows are one loop not seven "
          "pairs of draws",
          len(labels) == len(G.BIND_VARS) and labels == list(G.BIND_LABELS),
          str(labels))

    # --- the save itself
    slots = by_pins("SlotName")
    check("the settings are read and written through a named save slot",
          bool(slots) and {BEL.find_input_pin(n, "SlotName").get_pin_value()
                           for n in slots} == {G.SETTINGS_SLOT},
          str(sorted({BEL.find_input_pin(n, "SlotName").get_pin_value()
                      for n in slots})))
    writes = by_pins("SaveGameObject")
    # BeginPlay's repair of a save from an older build, a rebind, one nudge per
    # slider, and the debug toggle. Written at the moment of the change and not
    # on leaving the page, because a game quit from the settings screen still
    # has to remember what was set -- which is the whole of "across future game runs".
    want_writes = 3 + len(S.SLIDERS)
    check("every change is written to disk on the spot",
          len(writes) == want_writes, f"{len(writes)}, want {want_writes}")
    check("...and there is a load and a create, so a first run is not an error",
          bool(by_pins("SaveGameClass"))
          and any("Load Game from Slot" in t.replace("\n", " ")
                  or "LoadGameFromSlot" in t for t in titles),
          str(sorted({t for t in titles if "Save" in t or "Load" in t})))
    check("...both feeding the same BP_Settings variable",
          sum(1 for t in titles if t == "Set Settings") == 2,
          str(sum(1 for t in titles if t == "Set Settings")))
    # A save written by an older build has whatever number of binds that build
    # had, and every read indexes Binds by row -- so a length that is not
    # exactly len(BIND_VARS) is refilled rather than trusted.
    repairs = [n for n in nodes
               if pin_names(n) == {"A", "B"}
               and BEL.find_input_pin(n, "B").get_pin_value()
               == str(len(G.BIND_VARS))
               and "NotEqual" in str(BEL.get_node_title(n)).replace(" ", "")]
    check(f"a save whose Binds is not {len(G.BIND_VARS)} long is refilled",
          len(repairs) == 1, str(len(repairs)))
    adds = by_pins("NewItem")
    check("...from the defaults build_weapons_and_combat.py documents",
          [BEL.find_input_pin(n, "NewItem").get_pin_value() for n in adds]
          == [d for _v, d in G.BIND_VARS],
          str([BEL.find_input_pin(n, "NewItem").get_pin_value() for n in adds]))

    # --- the push onto the weapon component
    # The component never loads the save and never casts back to this HUD: it
    # is handed the values every DrawHUD frame and keeps its CDO defaults as a
    # standalone fallback. So the evidence is a Set per bind, on another class.
    pushes = {t for t in titles
              if t in {f"Set {v}" for v, _k in G.BIND_VARS}}
    check("every bind is pushed onto BP_WeaponComponent each frame",
          pushes == {f"Set {v}" for v, _k in G.BIND_VARS},
          str(sorted(pushes)))
    # Two Sets per slider: the nudge onto BP_Settings, the push onto the component.
    for slider in S.SLIDERS:
        check(f"...and so is {slider.var} (stored by its nudge, pushed each frame)",
              sum(1 for t in titles if t == f"Set {slider.var}") == 2,
              str(sum(1 for t in titles if t == f"Set {slider.var}")))
    # Literal indices only: the settings page's own Array_Get and Array_Set
    # take theirs from the loop and from MenuRow, and those are not the push.
    reads = [n for n in by_pins("Index")
             if not BEL.find_input_pin(n, "Index").list_connected_pins()]
    check("...read out of Binds by index, one per action",
          sorted(int(BEL.find_input_pin(n, "Index").get_pin_value())
                 for n in reads) == list(range(len(G.BIND_VARS))),
          str(sorted(BEL.find_input_pin(n, "Index").get_pin_value()
                     for n in reads)))

    # --- the slider rows
    # One FClamp per slider, plus the scope's fade. They are told apart by
    # their bounds rather than by position, so none can quietly inherit
    # another's.
    clamps = by_pins("Value", "Min", "Max")
    bounds = {(float(BEL.find_input_pin(n, "Min").get_pin_value() or 0.0),
               float(BEL.find_input_pin(n, "Max").get_pin_value() or 0.0))
              for n in clamps}
    check("every slider is clamped, and no floor is zero",
          len(clamps) == 1 + len(S.SLIDERS)
          and all((sl.lo, sl.hi) in bounds and sl.lo > 0.0 for sl in S.SLIDERS),
          f"{sorted(bounds)}")
    check("the scope sensitivity row is on the page, straight under the mouse's",
          [sl.var for sl in S.SLIDERS][:2] == ["MouseSensitivity", "ScopeSensitivity"]
          and S.SLIDERS[S.SCOPE_SENS_ROW].label == S.SCOPE_SENS_LABEL,
          str([sl.label for sl in S.SLIDERS]))
    # One write with a signed step rather than two arms with the same two
    # writes in them: the pair would drift and the clamp would end up on one.
    # Counted per step size, since two sliders may share one.
    for size in sorted({sl.step for sl in S.SLIDERS}):
        steps = [n for n in by_pins("A", "B")
                 if BEL.find_input_pin(n, "A").get_pin_value() == str(size)
                 and BEL.find_input_pin(n, "B").get_pin_value() == str(-size)]
        want = sum(1 for sl in S.SLIDERS if sl.step == size)
        check(f"Left and Right move each slider by +/-{size} through one "
              f"signed step", len(steps) == want, f"{len(steps)}, want {want}")

    # --- rebinding, and the trap it exists to avoid
    # THE ORDERING CHECK. Enter is what arms a capture, and Enter is still
    # "just pressed" for the rest of that frame -- so a capture poll that ran
    # after the activation would see it and bind the accept key to whatever row
    # the caret was on. The two live in opposite arms of a Branch on Capturing,
    # which puts them in different FRAMES as well as different paths.
    def first_after(pin):
        for q in (pin.list_connected_pins() if pin and pin.is_valid() else []):
            return PIN.get_owning_node(q)
        return None

    branches = [n for n in nodes if pin_names(n) == {"execute", "Condition"}]
    gates = []
    for n in branches:
        src = BEL.find_input_pin(n, "Condition").list_connected_pins()
        if any(str(BEL.get_node_title(PIN.get_owning_node(q))) == "Get Capturing"
               for q in src):
            gates.append(n)
    # Two of them: the input gate, and the hint line that reports its state.
    check("the settings page branches on whether a capture is armed",
          len(gates) == 2, str(len(gates)))
    armed_gate = [g for g in gates
                  if (first_after(BEL.find_then_pin(g)) is not None
                      and first_after(BEL.find_then_pin(g)).get_class()
                      .get_name() == "K2Node_MacroInstance")]
    check("the capture poll is the ARMED arm, and nothing else is",
          len(armed_gate) == 1,
          str([first_after(BEL.find_then_pin(g)).get_class().get_name()
               if first_after(BEL.find_then_pin(g)) else "nothing"
               for g in gates]))
    if armed_gate:
        other = first_after(BEL.find_else_pin(armed_gate[0]))
        check("...and the row activation is the other arm, so the Enter that "
              "armed the capture is never seen by it",
              other is not None
              and pin_names(other) == {"execute", "Condition"},
              other.get_class().get_name() if other else "nothing")
    pools = [n for n in nodes
             if n.get_class().get_name() == "K2Node_MacroInstance"
             and any("Get KeyPool" in
                     str(BEL.get_node_title(PIN.get_owning_node(q)))
                     for p_ in BEL.list_input_pins(n)
                     for q in p_.list_connected_pins())]
    check("...and it walks KeyPool rather than every FKey the engine knows",
          len(pools) == 1, str(len(pools)))
    check("a captured key is written into Binds at the caret's row",
          bool(by_pins("TargetArray", "Index", "Item")),
          f"{len(by_pins('TargetArray', 'Index', 'Item'))} Array_Set")
    # Armed by Enter on a bind row, cleared the moment a key lands. Without the
    # clear the next keypress rebinds the same row again, for ever.
    check("capture mode is armed and then cleared",
          sum(1 for t in titles if t == "Set Capturing") == 2,
          str(sum(1 for t in titles if t == "Set Capturing")))

    # --- two pages, and getting between them
    check("the panel has a title page and a settings page",
          sum(1 for t in titles if t == "Set MenuPage") == 2
          and any(t == "Get MenuPage" for t in titles),
          str(sorted({t for t in titles if "MenuPage" in t})))
    check("...and the caret is reset on every move between them",
          sum(1 for t in titles if t == "Set MenuRow") >= 4,
          str(sum(1 for t in titles if t == "Set MenuRow")))

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
