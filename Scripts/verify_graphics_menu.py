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
from graphics_menu.difficulty_checks import check_difficulty
from graphics_menu import fps as F
from graphics_menu import menu_nav as N
from graphics_menu import grass_tiers as T
from graphics_menu import presets as P
from graphics_menu import reticle as R
from graphics_menu import settings_rows as S
from graphics_menu import stamina_bar as ST
from graphics_menu import survival_bars as SB
from graphics_menu import scope as SC
from graphics_menu import profile_consts as PC
from graphics_menu.profile_checks import check_profile
from graphics_menu import dev_consts as DC
from graphics_menu.dev_guns_checks import check_dev_guns
from graphics_menu import loot_consts as LC
from graphics_menu import tune_consts as TC
from graphics_menu import tune_tab as TT
from graphics_menu import monster_tune_consts as MC
from graphics_menu.loot_checks import check_loot
from graphics_menu.tune_checks import check_tune
from graphics_menu.monster_tune_checks import check_monster_tune
from graphics_menu import world_tune_consts as WC
from graphics_menu.world_tune_checks import check_world_tune
from graphics_menu import cursor_consts as CC
from graphics_menu.cursor_checks import check_cursor
from graphics_menu import hud_stats as HS
from graphics_menu import umg_consts as UC
from graphics_menu.hud_bar_checks import check_bar_flash, check_bar_layout
from graphics_menu.legal_checks import check_legal
from graphics_menu.umg_checks import check_hud_graph, check_trees, text_literal
from combat.tuning import COMBAT, SHOT_VOLUME_CM

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
    expected_keys = set((G.MENU_KEY, UC.RESTART_KEY, G.DEBUG_KEY,
                         N.NAV_UP, N.NAV_DOWN, N.NAV_LEFT, N.NAV_RIGHT,
                         PC.EXIT_KEY, DC.DEV_GUNS_KEY,
                         LC.LOOT_KEY, LC.LOOT_UP, LC.LOOT_DOWN, LC.LOOT_TAKE_KEY,
                         TC.TUNE_KEY, TT.TUNE_UP, TT.TUNE_DOWN, TT.TUNE_LESS,
                         TT.TUNE_MORE, TT.TUNE_SAVE_KEY, MC.MON_TUNE_KEY,
                         WC.WORLD_TUNE_KEY)
                        + G.PRESET_KEYS + N.START_KEYS + CC.CURSOR_KEYS)
    check("polls exactly the menu, preset, debug, restart, start, nav, exit, "
          "dev-all-guns, loot, gun, monster and world tuning keys, and the "
          "cursor's click and wheel",
          keys == expected_keys,
          f"{sorted(keys)} vs {sorted(expected_keys)}")
    # Exactly one Key pin in this graph is driven rather than literal: the
    # capture poll, which asks the PlayerController about each entry of KeyPool
    # in turn. That is the only place a key is a value rather than a constant.
    check("one key poll is driven -- the rebind capture, over KeyPool",
          len(driven_keys) == 1, str(len(driven_keys)))
    # The navigation keys must not be bindable, or a keypress can lock the
    # settings screen shut with no way back but deleting the save.
    nav = {N.NAV_UP, N.NAV_DOWN, N.NAV_LEFT, N.NAV_RIGHT} | set(N.START_KEYS)
    check("...and the menu's own keys are not in the pool it offers",
          not (nav & set(G.KEY_POOL)), str(sorted(nav & set(G.KEY_POOL))))

    # --- each preset applies its own scalability level and cvars
    # One chain per preset key, plus the BeginPlay one that applies the default.
    expected_levels = sorted([p[1] for p in G.PRESETS]
                             + [G.PRESETS[G.DEFAULT_PRESET][1]])
    # "Value" alone no longer identifies SetOverallScalabilityLevel -- the
    # settings page's FClamp has one too, and its literal is a float; so has
    # the tuning panel's Conv_DoubleToText, and the world tab's MapRangeClamped.
    levels = sorted(int(BEL.find_input_pin(n, "Value").get_pin_value())
                    for n in by_pins("Value")
                    if not {"Min", "MaximumFractionalDigits", "InRangeA"} & pin_names(n))
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
    # the graph whose inputs are exactly exec + self -- apart from the profile
    # load's DestroyActor and the exit's DisableMovement, told apart by title.
    applies = [n for n in nodes if pin_names(n) == {"execute", "self"}
               and not any(w in str(BEL.get_node_title(n)).replace(" ", "")
                           for w in ("Destroy", "DisableMovement"))]
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

    # --- what is still drawn on the canvas
    # The screens are UMG now (graphics_menu/umg_checks.py). The canvas keeps
    # only what is placed per frame: the reticle and the scope, off the
    # viewport centre, and the wanderers' bars, off a projected world point.
    texts = by_pins("Text", "ScreenX")
    drawn = {BEL.find_input_pin(n, "Text").get_pin_value() for n in texts}
    check("the canvas draws one text, a wanderer's spawn number, from a wire",
          len(texts) == 1 and all(BEL.find_input_pin(n, "Text").list_connected_pins()
                                  for n in texts), str(sorted(drawn)))
    # The reticle -- five hairline ticks, where a texture would buy nothing and
    # cost a sample -- plus the two strips either side of the sniper's scope,
    # which are flat black by definition.
    expected_rects = 5 + 2
    check(f"{expected_rects} DrawRects: the reticle, and the scope's surround",
          len(by_pins("RectColor")) == expected_rects,
          str(len(by_pins("RectColor"))))
    # A wanderer's bar track and fill, and the sniper's scope.
    textures = by_pins("Texture", "ScreenX")
    check("3 DrawTextures: a wanderer's track and fill, and the scope",
          len(textures) == 3, str(len(textures)))

    # DrawTexture's UV rectangle is NORMALISED: the whole picture is 1x1. It
    # was once given the texel size, which tiles the texture that many times.
    # Nothing errors when that happens, so it is checked here.
    bad_uv = []
    for n in textures:
        uv = tuple(float(BEL.find_input_pin(n, p).get_pin_value() or 0)
                   for p in ("TextureU", "TextureV", "TextureUWidth",
                             "TextureVHeight"))
        if uv != (0.0, 0.0, 1.0, 1.0):
            bad_uv.append(str(uv))
    check("every DrawTexture samples the whole texture once (UV 0,0 + 1x1)",
          not bad_uv, "; ".join(bad_uv))

    # --- the artwork the screens' brushes and the canvas sample is imported
    art = ("T_UI_Panel", "T_UI_PanelDeath", "T_UI_Slot", "T_UI_SlotActive",
           "T_UI_SlotFrame", "T_UI_Bar", "T_UI_BarTrack", "T_UI_BarV", "T_UI_BarTrackV",
           "T_UI_Scope")
    wrong = [a for a in art if not eas.load_asset(f"{UC.UI_ART_DIR}/{a}")]
    check("every texture the screens and the canvas draw is imported",
          not wrong, "; ".join(wrong))
    icons = [d for d in ("Pistol", "Shotgun", "SMG", "Rifle", "Sniper")
             if not eas.load_asset(f"{UC.UI_ART_DIR}/T_UI_Icon_{d}")]
    check("...and so is every weapon icon", not icons, "; ".join(icons))

    # --- the UMG screens: their trees, and the graph that writes them
    check_trees(check)
    check_legal(check)
    check_hud_graph(check, nodes)
    check_bar_layout(check)
    check_bar_flash(check, nodes)

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
    for key in N.START_KEYS:
        check(f"the main menu accepts {key}", key in keys, str(sorted(keys)))

    started = [n for n in nodes
               if UC.GAME_STARTED_VAR in str(BEL.get_node_title(n))]
    check(f"{UC.GAME_STARTED_VAR} is read and written",
          len(started) >= 2, str(len(started)))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check(f"{UC.GAME_STARTED_VAR} starts false, so the menu is what loads",
          cdo.get_editor_property(UC.GAME_STARTED_VAR) is False)

    # --- the health readout
    health_reads = [n for n in nodes
                    if "Health" in pin_names(n, False) or
                    "MaxHealth" in pin_names(n, False)]
    # Two pairs now: the player's bar and the NPC bars read the same component.
    # Plus three Health reads for the profile: the death test, the save's
    # copy off the component, and the load's copy off BP_Profile.
    check("HUD reads Health and MaxHealth for both the player and the NPCs",
          len(health_reads) == 4 + 3, str(len(health_reads)))

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
    # One: the reticle's centre, which the scope shares. Everything else on
    # screen is a UMG widget anchored to its edge rather than placed in pixels.
    check("only the reticle reads the viewport size; the screens are anchored",
          len(viewports) == 1, str(len(viewports)))
    # The reticle's gap is the held gun's accuracy cloud (combat accuracy.py
    # writes ReticleSpread, a fraction of half the width): the four ticks move
    # out with it, capped, and the dot stays put.
    spread_reads = [n for n in nodes
                    if str(BEL.get_node_title(n)).replace("\n", " ") == "Get ReticleSpread"]
    caps = [n for n in by_pins("A", "B")
            if float_pin(n, "B") == R.RETICLE_SPREAD_MAX]
    capped = [n for n in caps
              if BEL.find_input_pin(n, "A").list_connected_pins()]
    check("the reticle opens by the gun's cloud (ReticleSpread x half the "
          "width), capped on screen",
          len(spread_reads) == 1 and len(capped) == 1,
          f"{len(spread_reads)} reads, {len(capped)} caps "
          f"{sorted({str(BEL.get_node_title(n)) for n in caps})}")
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
              == R.RETICLE_ARM)

    strips = [n for n in by_pins("RectColor")
              if BEL.find_input_pin(n, "ScreenW").list_connected_pins()]
    check("two black strips flank the scope, so the corners of the world "
          "cannot show past it", len(strips) == 2, str(len(strips)))
    # Negative width is what a portrait viewport would ask for, and DrawRect
    # draws that backwards rather than not at all.
    # B a literal: the tuning tab's FMax takes its floor from TuneMins.
    floor = [n for n in nodes
             if str(BEL.get_node_title(n)).replace("\n", " ") == "Max (Float)"
             and not BEL.find_input_pin(n, "B").list_connected_pins()]
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
    wanted = {G.HEALTH_CLASS_PATH, ST.WEAPON_COMP_CLASS_PATH}
    found = {str(BEL.find_input_pin(n, "ComponentClass").get_pin_value())
             for n in lookups}
    # Four: the player's health, an NPC's health, the weapon component for the
    # inventory strip, and the weapon component again for the reticle.
    # Five: the player's health, an NPC's health, and the weapon component
    # three times -- inventory strip, reticle, and the stamina bar.
    # Six: the player's health, an NPC's health, and the weapon component four
    # times -- inventory strip, reticle, stamina bar, and the settings push.
    # Seven: and the survival component, for its bars.
    # Ten: and the three the profile's save and load cast (player_parts.py).
    # Eleven: and CharacterMovement, frozen while the exit counts down.
    # Fourteen: and the loot window's three -- a body's health and mesh
    # (loot_find.py), and the player's bag (loot_tick.py).
    # Fifteen: and the carried guns the tuning tab writes (tune_tick.py).
    # Sixteen: and the fire press held spent under the cursor (cursor.py).
    # Seventeen: and the weapon component told it is Searching (loot_kneel.py).
    wanted.add(SB.SURVIVAL_CLASS_PATH)
    check("HUD looks up health (player + NPC), the weapon and survival components",
          len(lookups) == 17 and all(any(w in f for f in found) for w in wanted),
          f"{len(lookups)} lookups: {sorted(found)}")

    # The canvas's sized draws: a wanderer's fill from its health fraction,
    # and the scope's square off the viewport. The screens' bars are
    # ProgressBars now (check_hud_graph).
    driven = [n for n in textures
              if BEL.find_input_pin(n, "ScreenW").list_connected_pins()]
    check("the NPC fill and the scope are sized from values, not constants",
          len(driven) == 2, str(len(driven)))

    # --- the new HUD layers
    # The pawns, not the controllers the monster tuning tab writes.
    npc_scans = [n for n in by_pins("ActorClass")
                 if "ForestWanderer" in
                 str(BEL.find_input_pin(n, "ActorClass").get_pin_value())
                 and "ForestWandererAI" not in
                 str(BEL.find_input_pin(n, "ActorClass").get_pin_value())]
    check("a bar is drawn for every wanderer in the level",
          len(npc_scans) == 1, f"{len(npc_scans)} GetAllActorsOfClass(NPC)")

    # A name the data owns -- a weapon's, a difficulty's -- is drawn from the
    # data, never as a literal: a literal would mean the HUD kept its own copy
    # of the list. Checked by name: this used to count the driven draws, and
    # every new readout broke the count without saying what it was.
    owned = set(SHOT_VOLUME_CM) | set(S.DIFFICULTY_LABELS)
    literals = (drawn | {text_literal(n) for n in by_pins("InText")}
                | set(UC.SETTINGS_ROW_LABELS) | set(UC.PAUSE_ROW_LABELS)
                | set(UC.MENU_ROWS))
    check("no weapon or difficulty name is a literal on the HUD -- they come "
          "from data", not literals & owned, str(sorted(literals & owned)))
    blank = [n for n in texts if not BEL.find_input_pin(n, "Text").get_pin_value()
             and not BEL.find_input_pin(n, "Text").list_connected_pins()]
    check("every DrawText has a literal or a wire -- none draws nothing",
          not blank, f"{len(blank)} empty and unwired")
    ids = [n for n in nodes
           if "NpcId" in {str(p_) for p_ in pin_names(n, False)}]
    check("each NPC bar carries the wanderer's spawn number",
          len(ids) == 1, f"{len(ids)} NpcId read(s)")

    # --- the kill counter, the stamina bar and the death menu
    titles = [str(BEL.get_node_title(n)).replace("\n", " ") for n in nodes]

    check("the HUD reads the kill count off the GameMode",
          any(t == f"Get {HS.KILL_COUNT_VAR}" for t in titles),
          str(sorted({t for t in titles if "Kill" in t})))
    # Twice: once for the corner and once for the death menu's final score. The
    # menu re-reads rather than being handed a copy, so the two can never
    # disagree about the score. A third read is the profile's save of it.
    check("the corner and the death menu read the same counter",
          sum(1 for t in titles if t == f"Get {HS.KILL_COUNT_VAR}") == 3,
          str(sum(1 for t in titles if t == f"Get {HS.KILL_COUNT_VAR}")))
    kill_labels = [n for n in by_pins("A", "B")
                   if BEL.find_input_pin(n, "A").get_pin_value() == "KILLS  "]
    check("the counter is labelled KILLS", len(kill_labels) == 1,
          str(len(kill_labels)))

    # --- stamina
    stamina_reads = {t for t in titles if t in ("Get Stamina", "Get MaxStamina",
                                                "Get Sprinting")}
    check("the stamina bar reads Stamina, MaxStamina and Sprinting",
          stamina_reads == {"Get Stamina", "Get MaxStamina", "Get Sprinting"},
          str(sorted(stamina_reads)))
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
    # Once, to pick the death menu over the HUD. Its arm hides the HUD's Body
    # (check_hud_graph) -- a reticle and an inventory over a death screen read
    # as a game still being played.
    check("the death menu is chosen once, ahead of the HUD",
          sum(1 for t in titles if t == f"Get {G.PLAYER_DEAD_VAR}") == 1,
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
    # (The profile's save reads Loaded and Reserve off each item too.)
    saved_ammo = {item_var for _f, item_var in PC.AMMO_FIELDS}
    for var in ("UsesAmmo", "Loaded", "Reserve"):
        check(f"the slot reads the weapon's own {var}",
              sum(1 for t in titles if t == f"Get {var}")
              == 1 + (var in saved_ammo),
              str(sum(1 for t in titles if t == f"Get {var}")))
    check("the count is rounds-in-gun / rounds-in-reserve, not one number",
          any(BEL.find_input_pin(n, "A").get_pin_value() == " / "
              for n in by_pins("A", "B")
              if BEL.find_input_pin(n, "A")),
          "a ' / ' separator")
    check("...and only weapons that use ammunition show it at all",
          sum(1 for t in titles if t == "Get UsesAmmo") == 1)
    # The pistol reloads every eight shots over an endless reserve: "5 / inf".
    check("...an InfiniteReserve weapon shows its reserve as infinity",
          sum(1 for t in titles if t == "Get InfiniteReserve") == 1
          and any(BEL.find_input_pin(n, "A").get_pin_value() == "\u221e"
                  for n in by_pins("A", "B", "bPickA")),
          str(sum(1 for t in titles if t == "Get InfiniteReserve")))

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
    for var in ("Settings", "MenuPage", "MenuRow", "Capturing", "KeyPool"):
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

    # --- the save itself
    # The profile's slot is check_profile's business.
    slots = [n for n in by_pins("SlotName")
             if BEL.find_input_pin(n, "SlotName").get_pin_value() != PC.PROFILE_SLOT]
    check("the settings are read and written through a named save slot",
          bool(slots) and {BEL.find_input_pin(n, "SlotName").get_pin_value()
                           for n in slots} == {G.SETTINGS_SLOT},
          str(sorted({BEL.find_input_pin(n, "SlotName").get_pin_value()
                      for n in slots})))
    writes = [n for n in by_pins("SaveGameObject", "SlotName")
              if BEL.find_input_pin(n, "SlotName").get_pin_value() != PC.PROFILE_SLOT]
    # BeginPlay's repair of a save from an older build, a rebind, one nudge per
    # slider, the difficulty's nudge, and the debug toggle. Written at the moment of the change and not
    # on leaving the page, because a game quit from the settings screen still
    # has to remember what was set -- which is the whole of "across future game runs".
    want_writes = 4 + len(S.SLIDERS)
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
    # Literal adds only: the profile's Array_Adds are all wired.
    adds = [n for n in by_pins("NewItem")
            if not BEL.find_input_pin(n, "NewItem").list_connected_pins()]
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
    # Nor are the monster and world tuning tabs' cells (literal, off
    # MonTuneValues and WorldTuneValues).
    reads = [n for n in by_pins("TargetArray", "Index")
             if not BEL.find_input_pin(n, "Index").list_connected_pins()
             and not {f"Get {MC.MON_TUNE_VALUES_VAR}", f"Get {WC.WORLD_TUNE_VALUES_VAR}"} & {
                 str(BEL.get_node_title(PIN.get_owning_node(q)))
                 for q in BEL.find_input_pin(n, "TargetArray").list_connected_pins()}]
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
        # That arm opens with the cursor's row test (cursor.py), which is
        # what keeps the click that armed a capture out of the capture too.
        check("...and the row activation is the other arm, so the Enter that "
              "armed the capture is never seen by it",
              other is not None
              and str(BEL.get_node_title(other)).replace("\n", " ")
              == f"Set {CC.CURSOR_ROW_VAR}",
              str(BEL.get_node_title(other)) if other else "nothing")
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

    check_difficulty(check, bp, nodes)
    check_profile(check, bp, nodes)
    check_dev_guns(check, bp, nodes)
    check_loot(check, bp, nodes)
    check_tune(check, bp, nodes)
    check_monster_tune(check, bp, nodes)
    check_world_tune(check, bp, nodes)
    check_cursor(check, bp, nodes)

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
