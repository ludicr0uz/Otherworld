"""
build_graphics_menu.py — Creates the game's UI from Python: the HUD, the main
menu and settings page, the M panel and the death menu.

Run inside the editor:
    python3 Scripts/dev/uepy.py Scripts/build_graphics_menu.py

Assets produced, plus one wiring change:

  /Game/UI/WBP_MenuRow, WBP_InventorySlot   the pieces the screens are built from
  /Game/UI/WBP_HUD, WBP_MainMenu,           the four UMG screens (layouts in
           WBP_PauseMenu, WBP_DeathMenu      graphics_menu/wbp_*.py)
  /Game/UI/BP_GraphicsMenuHUD  (AHUD)       the controller: reads the game,
                                             polls the keys, writes the screens
  /Game/UI/BP_GraphicsTuner  (component)    on the HUD: applies a quality
                                             preset's numbers to the engine

  BP_ThirdPersonGameMode.HUDClass is pointed at the HUD.  That game mode is the
  project's GlobalDefaultGameMode and no generated level overrides it, so this
  one edit puts the UI in every level.

Widget trees are authored through the engine's UMGToolSet plugin (see
graphics_menu/umg_author.py for why that is the way in). The reticle, the
sniper's scope and the wanderers' bars are still drawn on the HUD canvas:
each is placed per frame, off the viewport centre or a projected world point.

Event graph:

  [Event BeginPlay] --> create the four screens, add them to the viewport
                    --> Quality := the startup preset (Low)
                    --> load BP_Settings --> GameMode.DebugMode = saved
                    --> pause on the main menu (unless -nomenu)

  [Event Tick] --> save and exit (graphics_menu/save_exit.py), the loot
                   window (graphics_menu/loot_tick.py), the tuning tabs, then
                   the M / 1-4 / D keys

  [Event ReceiveDrawHUD] --> DebugOn copy, settings pushed onto the weapon
                             component, difficulty onto the GameMode, FPS
    --> GameStarted?   no: the main menu (title or settings page) and its keys
    --> PlayerDead?    yes: the death menu and [R]
                       no:  HP, stamina, survival bars, kills, the wanderers'
                            bars (canvas), inventory, reticle (canvas), the
                            save-and-exit banner, the loot window, the M panel
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# BP_Settings' asset path. The settings screen's own contract with the combat
# package (BIND_VARS, the sensitivity limits) lives in graphics_menu/settings_rows.py.
from combat import paths as combat_paths                           # noqa: E402
# The presets' names. What one does: graphics_menu/presets.py.
from graphics_menu.presets import (                                # noqa: E402
    DEFAULT_PRESET, PRESETS, emit_apply)
from graphics_menu.gfx_tune_consts import GFX_TAB, TUNER_COMPONENT   # noqa: E402
from graphics_menu.gfx_tune_tick import (                           # noqa: E402
    author_gfx_tune_tick, declare_gfx_tune_vars, gfx_tune_defaults, install_tuner)
from graphics_menu.gfx_tuner import build_graphics_tuner            # noqa: E402
# The FPS readout, one of the debug-mode overlays; see graphics_menu/fps.py.
from graphics_menu.fps import author_fps, declare_fps_vars          # noqa: E402
# The generated art the canvas layers (the wanderers' bars) still draw with.
from graphics_menu.canvas import _draw_texture                      # noqa: E402
# The settings screen: constants, the push, the save.
from graphics_menu.settings_rows import (                          # noqa: E402
    BIND_VARS, KEY_POOL, PAGE_TITLE,
    SETTINGS_CLASS_PATH, SETTINGS_SLOT, SETTINGS_USER_INDEX)
from graphics_menu.settings_input import _emit_save                # noqa: E402
from graphics_menu.settings_page import _author_push_settings      # noqa: E402
# The UMG screens: their layouts, their creation at BeginPlay, and the
# DrawHUD fragments that write into them.
from graphics_menu.umg_consts import (                              # noqa: E402
    CLOSE_ACTION, DEBUG_ACTION, GAME_STARTED_VAR, PAUSE_ROW_VAR)
from graphics_menu.wbp_hud import build_hud_widget                  # noqa: E402
from graphics_menu.wbp_parts import (                              # noqa: E402
    build_inventory_slot, build_menu_row)
from graphics_menu.wbp_screens import (                            # noqa: E402
    build_death_menu, build_main_menu, build_pause_menu)
from graphics_menu.ui_graph import (                               # noqa: E402
    author_create_screens, declare_ui_vars)
from graphics_menu.menu_screens import (                           # noqa: E402
    author_alive, author_death_menu, author_main_menu, author_pause_menu)
from graphics_menu.hud_stats import author_hp, author_kills         # noqa: E402
from graphics_menu.hud_inventory import author_inventory            # noqa: E402
# The stamina bar, centred under the inventory grid.
from graphics_menu.stamina_bar import _author_stamina               # noqa: E402
# Hunger, thirst and temperature under the HP bar, and the debuff names.
from graphics_menu.survival_bars import author_survival_bars       # noqa: E402
# The crosshair, sized by the held gun's accuracy cloud, and the scope.
from graphics_menu.reticle import _author_reticle                  # noqa: E402
from graphics_menu.difficulty import (                             # noqa: E402
    author_push_difficulty, declare_difficulty_vars, difficulty_defaults)
# Save and exit, the saved profile and losing it on death; see save_exit.py.
from graphics_menu.profile_asset import build_profile_savegame     # noqa: E402
from graphics_menu.profile_consts import PROFILE_BP_PATH           # noqa: E402
from graphics_menu.profile_draw import author_exit_banner           # noqa: E402
from graphics_menu.save_exit import (                              # noqa: E402
    author_save_exit_tick, declare_profile_vars, profile_defaults)
from graphics_menu.dev_guns import (                               # noqa: E402
    declare_dev_guns_vars, dev_guns_defaults)
from graphics_menu.loot_draw import author_loot_window              # noqa: E402
from graphics_menu.cursor import (                                  # noqa: E402
    author_cursor_read, cursor_defaults, declare_cursor_vars)
from graphics_menu.menu_nav import or_pause_row, pause_row_taken    # noqa: E402
from graphics_menu.menu_still import (                              # noqa: E402
    MENU_STILL_VAR, author_menu_still)
from graphics_menu.monster_tune_consts import MONSTER_TAB           # noqa: E402
from graphics_menu.monster_tune_tick import (                       # noqa: E402
    author_monster_tune_tick, declare_monster_tune_vars, monster_tune_defaults)
from graphics_menu.tune_draw import author_tune_panel               # noqa: E402
from graphics_menu.tune_tick import (                               # noqa: E402
    author_tune_tick, declare_tune_vars, tune_defaults)
from graphics_menu.world_tune_consts import WORLD_TAB               # noqa: E402
from graphics_menu.world_tune_tick import (                         # noqa: E402
    author_world_tune_tick, declare_world_tune_vars, world_tune_defaults)
from graphics_menu.loot_tick import (                               # noqa: E402
    author_loot_tick, declare_loot_vars, loot_defaults)
from survival.paths import SURVIVAL_BP_PATH                        # noqa: E402

# ─── Configuration ───────────────────────────────────────────────────────────

UI_DIR = "/Game/UI"
HUD_BP_PATH = f"{UI_DIR}/BP_GraphicsMenuHUD"

GAME_MODE_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"

MENU_KEY = "M"

# Debug mode: the developer overlays, on one key in the same menu.  The flag
# itself lives on the GameMode (declared by build_weapons_and_combat.py), not
# here, because the *weapon component* is the other thing that reads it and a
# HUD variable is not reachable from a component.  What lives here is DebugOn,
# a copy taken once per frame at the top of DrawHUD so the draw code can branch
# on a plain bool instead of casting to the GameMode for every wanderer.
#
# The player's choice is kept in BP_Settings.DebugMode (default ON), so it
# survives a restart: BeginPlay copies it onto the GameMode once the save is
# loaded, and the M panel's debug row writes it back and saves on the spot.
DEBUG_MODE_VAR = "DebugMode"

# Where the player's health lives.  Built by build_weapons_and_combat.py; the
# HUD degrades to drawing nothing if the pawn has no such component.
HEALTH_CLASS_PATH = "/Game/Weapons/BP_HealthComponent.BP_HealthComponent_C"

# ─── The main menu ───────────────────────────────────────────────────────────
#
# Shown the moment the level loads, with the game PAUSED, and replaced by the
# HUD when the player starts (graphics_menu/menu_screens.py). Its keys are
# polled inside ReceiveDrawHUD rather than on Tick, because Event Tick does not
# run while the game is paused but PostRender is called by the renderer every
# frame regardless, and APlayerController sets bTickEvenWhenPaused so its
# PlayerInput is still updated. The death menu's [R] lives there for the same
# reason.
#
# How long the world runs before BeginPlay pauses it under the menu. Pausing on
# frame zero froze the view INSIDE the player: LevelTick skips
# UpdateCameraManager while paused (unless the controller full-ticks), so the
# camera never left the spawn point for the boom, and the mesh never evaluated
# its anim graph, so its reference-pose arms filled the screen from within.
# A quarter second lets both settle; the wanderers are 75 m away and cannot
# close that in the time.
MENU_SETTLE_S = 0.25

# The one way past the menu that is not a keypress. A headless -game run has
# nobody to press Enter, so without this every automated run would sit on the
# title screen forever and the whole harness would go quiet -- which is a worse
# outcome than the menu, because a silent test looks like a passing one.
#
# A command-line switch rather than a console variable: it has to be read at
# BeginPlay, before anything could have executed a console command, and
# GetCommandLine is the only thing available that early. Scripts/dev/uepy.py
# passes it on every --game run.
SKIP_MENU_SWITCH = "-nomenu"


# --- NPC health bars, drawn in the world above each wanderer ------------------
# Still on the HUD canvas: one bar per wanderer, placed each frame by
# projecting its head into the viewport.
NPC_CLASS_PATH = "/Game/Forest/NPC/BP_ForestWanderer.BP_ForestWanderer_C"
NPC_BAR_Z = 110.0          # cm above the actor's origin, just over its head
NPC_BAR = (90.0, 10.0)     # width, height in pixels
COL_NPC_FILL = "(R=0.900000,G=0.250000,B=0.180000,A=0.950000)"
# The wanderer's spawn number, drawn just left of its bar. Every NPC takes the
# next number as it spawns (build_weapons_and_combat.py hands them out) and logs
# where it appeared, so a wanderer misbehaving on screen can be looked up in the
# log by the number floating over its head.
NPC_ID_VAR = "NpcId"
# A wanderer's bar is hidden by default and shown only for a few seconds after
# something hurt it. Five bars over five chasing NPCs is most of the screen, and
# the bar is only ever *read* just after a shot lands -- the rest of the time it
# is clutter covering the forest the player is trying to aim into.
LAST_DAMAGE_VAR = "LastDamageTime"
NPC_BAR_SECONDS = 5.0
NPC_ID_GAP = 8.0           # pixels between the number and the left of the bar
NPC_ID_WIDTH = 34.0        # room reserved for up to three digits
NPC_ID_RISE = 4.0          # nudge up, so digits sit level with the bar
NPC_ID_SCALE = 1.0
COL_NPC_ID = "(R=0.960000,G=0.860000,B=0.450000,A=0.950000)"

GAME_MODE_CLASS_PATH = ("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
                        ".BP_ThirdPersonGameMode_C")
PLAYER_DEAD_VAR = "PlayerDead"

# ─── Function paths for the graph nodes ──────────────────────────────────────

FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_ALL_ACTORS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_ADD_VV = "/Script/Engine.KismetMathLibrary.Add_VectorVector"
FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
FN_BREAK_VECTOR = "/Script/Engine.KismetMathLibrary.BreakVector"
FN_PROJECT = "/Script/Engine.HUD.Project"
FN_GREATER = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_COMMAND_LINE = "/Script/Engine.KismetSystemLibrary.GetCommandLine"
FN_CONTAINS = "/Script/Engine.KismetStringLibrary.Contains"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_LE = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"
FN_SAVE_EXISTS = "/Script/Engine.GameplayStatics.DoesSaveGameExist"
FN_LOAD_SAVE = "/Script/Engine.GameplayStatics.LoadGameFromSlot"
FN_CREATE_SAVE = "/Script/Engine.GameplayStatics.CreateSaveGameObject"
FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_ARR_CLEAR = "/Script/Engine.KismetArrayLibrary.Array_Clear"
FN_NEQ_II = "/Script/Engine.KismetMathLibrary.NotEqual_IntInt"

# The DrawHUD event is not one of the placeholder nodes a fresh Blueprint ships
# with (BeginPlay and Tick are), so it has to be created from the palette.
NODE_DRAW_HUD = "AddEvent|EventReceiveDrawHUD"
NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"
NODE_CAST_SETTINGS = "Utilities|Casting|CastToBP_Settings"
MACRO_FOR_EACH = ("/Engine/EditorBlueprintResources/StandardMacros"
                  ".StandardMacros:ForEachLoop")

BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _log(msg):
    unreal.log_warning(f"[UI] {msg}")


def _asset_sub():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


# ─── Small graph helpers ─────────────────────────────────────────────────────
# Deliberately duplicated from build_npc_blueprints.py rather than shared: each
# builder in Scripts/ is standalone and runnable on its own, and three tiny
# wrappers are a cheaper price than a coupling between them.

def _create_blueprint(path, parent_class):
    """Load the Blueprint at ``path``, creating it if absent (never recreating:
    an existing asset is referenced by the game mode's HUDClass)."""
    eas = _asset_sub()
    if eas.does_asset_exist(path):
        existing = eas.load_asset(path)
        if existing:
            return existing
    package_path, asset_name = path.rsplit("/", 1)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, package_path, unreal.Blueprint, factory)
    if not bp:
        raise RuntimeError(f"Could not create Blueprint {path}")
    return bp


def _node(ed, function_path):
    """add_call_function_node, but loud when the function path does not resolve.

    An unresolvable path yields a pinless node rather than None, which surfaces
    much later as a baffling "pin 'self' not found on ''".
    """
    n = ed.add_call_function_node(function_path)
    if not n or not BEL.list_all_pins(n):
        raise RuntimeError(f"{function_path} is not a Blueprint-callable function")
    return n


def _palette(ed, name, x=0.0, y=0.0):
    n = ed.create_node_from_name(name, unreal.Vector2D(float(x), float(y)), [])
    if not n:
        raise RuntimeError(f"palette node {name!r} could not be created")
    return n


def _loose_pin(node, wanted, is_input=True):
    """Find a pin ignoring spaces and case.

    Cast nodes name their output after the class with spaces inserted
    ("AsBP Health Component"), which is not worth depending on exactly.
    """
    key = wanted.replace(" ", "").lower()
    for p in (BEL.list_input_pins(node) if is_input else BEL.list_output_pins(node)):
        if str(PIN.get_pin_name(p)).replace(" ", "").lower() == key:
            return p
    raise RuntimeError(f"no pin like {wanted!r} on node")


def _pin(node, name, is_input=True):
    p = (BEL.find_input_pin(node, name) if is_input
         else BEL.find_output_pin(node, name))
    if not p or not p.is_valid():
        raise RuntimeError(
            f"pin {name!r} ({'in' if is_input else 'out'}) not found on "
            f"{BEL.get_node_title(node)}")
    return p


def _connect(a, b):
    if not a.try_create_connection(b):
        raise RuntimeError("could not connect pins")


def _set(node, name, value):
    """Set a pin's literal, and prove it landed.

    set_pin_value's return is useless as a signal -- False means both "rejected"
    and "already equal to the default" -- so the pin is read back instead. A pin
    that quietly stayed empty compiles as zero and looks perfect in the graph,
    which is exactly how a scale factor can go missing without a single warning.
    """
    pin = _pin(node, name)
    pin.set_pin_value(str(value))
    got = str(PIN.get_pin_value(pin))
    if not _literal_matches(got, value):
        raise RuntimeError(f"pin {name!r} would not take {value!r} — it reads "
                           f"back as {got!r} (struct pins reject every format; "
                           "build the constant as a node instead)")


def _literal_matches(got, want):
    want = str(want)
    if got == want:
        return True
    try:
        # An empty numeric pin *is* zero: the compiler reads a blank literal as
        # 0, so setting zero and reading back "" is a genuine match.
        return abs(float(got or 0.0) - float(want)) < 1e-6
    except ValueError:
        pass
    # Enum literals read back namespaced, bools lower-cased.
    return got.lower() == want.lower() or got.endswith(f"::{want}")



# Source sizes, so DrawTexture can be handed a UV rectangle in texels.

# The weapon icon inside its slot: nearly the full width, on the upper line so
# the ammunition count has the lower one.
#
# 112 x 50, up from 88 x 44. That is not a tweak -- the icons were reported as
# unreadable ("lots of small dots"), and while the drawings themselves were
# redrawn for it (see build_ui_art.py) the other half of the fix is simply
# giving them more pixels. A weapon silhouette at 88 px wide has about 40 px of
# usable length once the margins are off it, and no silhouette survives that.
# Since shrunk with the slot, by 30%, to 78 x 35 at the player's request.


def _at(node, x, y):
    BEL.set_node_pos(node, unreal.IntPoint(int(x), int(y)))
    return node


def _key(name):
    """An FKey value for a CDO default.

    unreal.Key takes no constructor argument and exposes no fields, so the only
    way in is the key_name property -- which at least fails loudly on a
    misspelling, where import_text() returns True for anything.
    """
    k = unreal.Key()
    k.set_editor_property("key_name", name)
    return k


# ─── Member variables ────────────────────────────────────────────────────────

def _ensure_variables(ed, bp):
    """MenuOpen drives both input gating and drawing; Quality drives the caret.

    Re-declared rather than skipped-if-present: a variable's *default value* is
    not editable once it exists, and a rebuild wipes the graph but keeps the
    variables -- so skipping would silently strand `Quality` on whatever
    DEFAULT_PRESET used to be.  Only ever called after a wipe or on a fresh
    asset, so nothing is referencing them at this point.
    """
    for name, kind, default in (("MenuOpen", "bool", "false"),
                                # The M panel's caret, and whether the
                                # controller was told to ignore move input
                                # for the open panel (menu_still.py).
                                (PAUSE_ROW_VAR, "int", "0"),
                                (MENU_STILL_VAR, "bool", "false"),
                                # This frame's copy of the GameMode's
                                # DebugMode.  Taken once at the top of DrawHUD.
                                ("DebugOn", "bool", "false"),
                                # False until the player picks NEW GAME.
                                # BeginPlay pauses the world alongside it.
                                (GAME_STARTED_VAR, "bool", "false"),
                                ("Quality", "int", str(DEFAULT_PRESET)),
                                # Which page of the menu panel is on screen,
                                # and which line of it the caret is on.
                                ("MenuPage", "int", str(PAGE_TITLE)),
                                ("MenuRow", "int", "0"),
                                # Armed by Enter on a bind row; the next key
                                # the player presses becomes that bind.
                                ("Capturing", "bool", "false")):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name(kind),
                                      default):
            raise RuntimeError(f"could not declare member variable {name}")

    # The loaded save. Typed as BP_Settings rather than as SaveGame so the page
    # can read MouseSensitivity and Binds off it without a cast per read; the
    # one cast is at BeginPlay, where LoadGameFromSlot hands back a USaveGame.
    settings_class = _asset_sub().load_asset(combat_paths.SETTINGS_BP_PATH)
    if not settings_class:
        raise RuntimeError(f"{combat_paths.SETTINGS_BP_PATH} must be built first "
                           "(build_weapons_and_combat.py)")
    for name, pin_type in (
            ("Settings", BEL.get_object_reference_type(
                BEL.generated_class(settings_class))),
            # What a bind may be captured as -- walked by a ForEachLoop while
            # Capturing. A variable rather than a literal chain because the
            # graph tests every entry with the same three nodes.
            ("KeyPool", BEL.get_array_type(
                BEL.get_struct_type(unreal.Key.static_struct())))):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, pin_type):
            raise RuntimeError(f"could not declare member variable {name}")
    # The canvas HUD's bind labels: the settings rows carry their own now.
    ed.remove_member_variable("BindLabels")
    declare_ui_vars(ed)
    declare_fps_vars(ed)
    declare_difficulty_vars(ed)
    declare_profile_vars(ed)
    declare_dev_guns_vars(ed)
    declare_loot_vars(ed)
    declare_tune_vars(ed)
    declare_monster_tune_vars(ed)
    declare_world_tune_vars(ed)
    declare_gfx_tune_vars(ed)
    declare_cursor_vars(ed)


def _apply_defaults(bp, defaults):
    """Bake variable defaults onto the CDO, because add_member_variable cannot.

    Passing a default to add_member_variable returns True and then the compiler
    logs `Can't parse default value` and leaves the property at zero. That is
    invisible here today only because MenuOpen defaults to false and Quality to
    DEFAULT_PRESET 0 -- both of which *are* zero. Point DEFAULT_PRESET at
    Medium and the caret would silently start on Low. UE 5.8 exposes no API for
    a member variable's default, so it is written to the compiled class's
    default object and baked in by recompiling.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        cdo.set_editor_property(name, value)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GraphicsMenuHUD failed to recompile after defaults")
    fresh = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        if not _same_default(fresh.get_editor_property(name), value):
            raise RuntimeError(f"default for {name} did not stick")


def _same_default(got, want):
    """Compare a read-back CDO default with what was written.

    Plain == is enough for the bools and ints, but not for the two arrays: an
    unreal.Array is never equal to a list, and an FKey is never equal to another
    FKey (the Python wrapper compares identity, and to_tuple() is empty for
    every key because FKey exposes no fields). export_text() is the only view of
    a key that answers the question -- and it is the same bare name a pin
    literal uses.
    """
    if isinstance(want, (list, tuple)):
        return (len(got) == len(want)
                and all(_same_default(a, b) for a, b in zip(got, want)))
    if isinstance(want, unreal.Key):
        return got is not None and got.export_text() == want.export_text()
    return got == want


def _chain(node, in_exec):
    """Wire ``in_exec`` into a node if it has an exec pin; return what follows.

    Several of the GameplayStatics calls used here are const BlueprintCallable,
    which UHT silently promotes to BlueprintPure -- those have no exec pins at
    all and are pulled by whatever reads their output. Asking the node rather
    than remembering which is which is one line and cannot go stale.
    """
    pin = BEL.find_input_pin(node, "execute")
    if pin and pin.is_valid():
        _connect(in_exec, pin)
        return BEL.find_then_pin(node)
    return in_exec


def _author_load_settings(ed, x0, y0, in_exec):
    """BeginPlay: bring the saved settings in, or start a fresh set.

    Two ways to end up with a BP_Settings and one repair. The repair -- refill
    Binds when it is not exactly len(BIND_VARS) long -- is not paranoia: a save
    written by an older build has whatever number of binds that build had, and
    every read on the settings page indexes into this array by row. A short
    array would be an out-of-range Array_Get per frame, drawing nothing and
    saying nothing.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    exists = keep(_at(_node(ed, FN_SAVE_EXISTS), x0, y0 + 240))
    _set(exists, "SlotName", SETTINGS_SLOT)
    _set(exists, "UserIndex", SETTINGS_USER_INDEX)
    flow = _chain(exists, in_exec)

    have = keep(_at(ed.add_branch_node(), x0 + 260, y0))
    _connect(_pin(exists, "ReturnValue", is_input=False), _pin(have, "Condition"))
    _connect(flow, _pin(have, "execute"))

    loaded = keep(_at(_node(ed, FN_LOAD_SAVE), x0 + 520, y0))
    _set(loaded, "SlotName", SETTINGS_SLOT)
    _set(loaded, "UserIndex", SETTINGS_USER_INDEX)
    after_load = _chain(loaded, BEL.find_then_pin(have))

    as_saved = keep(_at(_palette(ed, NODE_CAST_SETTINGS), x0 + 780, y0))
    _connect(_pin(loaded, "ReturnValue", is_input=False), _pin(as_saved, "Object"))
    _connect(after_load, _pin(as_saved, "execute"))
    took = keep(_at(ed.add_set_member_variable_node("Settings"), x0 + 1040, y0))
    _connect(_loose_pin(as_saved, "AsBPSettings", is_input=False),
             _pin(took, "Settings"))
    _connect(BEL.find_then_pin(as_saved), _pin(took, "execute"))

    # A save that will not cast is a save from a different class, which is the
    # same situation as no save at all -- so the failed arm joins the create
    # path rather than leaving Settings null and every read below an
    # Accessed None.
    fresh = keep(_at(_node(ed, FN_CREATE_SAVE), x0 + 520, y0 + 460))
    _pin(fresh, "SaveGameClass").set_pin_value(SETTINGS_CLASS_PATH)
    for e in (BEL.find_else_pin(have),
              _pin(as_saved, "CastFailed", is_input=False)):
        _connect(e, _pin(fresh, "execute"))
    as_new = keep(_at(_palette(ed, NODE_CAST_SETTINGS), x0 + 780, y0 + 460))
    _connect(_pin(fresh, "ReturnValue", is_input=False), _pin(as_new, "Object"))
    _connect(BEL.find_then_pin(fresh), _pin(as_new, "execute"))
    made_it = keep(_at(ed.add_set_member_variable_node("Settings"),
                       x0 + 1040, y0 + 460))
    _connect(_loose_pin(as_new, "AsBPSettings", is_input=False),
             _pin(made_it, "Settings"))
    _connect(BEL.find_then_pin(as_new), _pin(made_it, "execute"))

    got = keep(_at(ed.add_get_member_variable_node("Settings"),
                   x0 + 1300, y0 + 700))
    settings_out = _pin(got, "Settings", is_input=False)
    binds = keep(_at(ed.add_get_member_variable_node("Binds",
                                                     SETTINGS_CLASS_PATH),
                     x0 + 1300, y0 + 840))
    _connect(settings_out, _pin(binds, "self"))
    binds_out = _pin(binds, "Binds", is_input=False)

    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 1560, y0 + 840))
    _connect(binds_out, _loose_pin(count, "TargetArray"))
    short = keep(_at(_node(ed, FN_NEQ_II), x0 + 1800, y0 + 840))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(short, "A"))
    _set(short, "B", len(BIND_VARS))

    repair = keep(_at(ed.add_branch_node(), x0 + 2060, y0 + 240))
    _connect(_pin(short, "ReturnValue", is_input=False), _pin(repair, "Condition"))
    for e in (BEL.find_then_pin(took), BEL.find_then_pin(made_it),
              _pin(as_new, "CastFailed", is_input=False)):
        _connect(e, _pin(repair, "execute"))

    wipe = keep(_at(_node(ed, FN_ARR_CLEAR), x0 + 2320, y0 + 240))
    _connect(binds_out, _loose_pin(wipe, "TargetArray"))
    _connect(BEL.find_then_pin(repair), _pin(wipe, "execute"))
    flow = BEL.find_then_pin(wipe)
    for i, (_var, key) in enumerate(BIND_VARS):
        add = keep(_at(_node(ed, FN_ARR_ADD), x0 + 2580 + i * 260, y0 + 240))
        _connect(binds_out, _loose_pin(add, "TargetArray"))
        # Bare key name, never struct text: FKey exports as just its name, so
        # '(KeyName="Q")' imports back as a key literally called "(".
        _set(add, "NewItem", key)
        _connect(flow, _pin(add, "execute"))
        flow = BEL.find_then_pin(add)
    saved, writer = _emit_save(ed, settings_out, flow,
                               x0 + 2580 + len(BIND_VARS) * 260, y0 + 240)
    made.append(writer)

    ed.add_comment_to_nodes(
        f"The settings the player keeps. Slot {SETTINGS_SLOT!r} if it is on "
        f"disk, a fresh BP_Settings if it is not, and a refill of Binds if it "
        f"is not exactly {len(BIND_VARS)} long -- which is what a save written "
        f"by an older build looks like. Every read on the settings page "
        f"indexes Binds by row, so a short array is an out-of-range Get per "
        f"frame that draws nothing and says nothing.",
        made)
    return (saved, BEL.find_else_pin(repair))


def _author_restore_debug(ed, x0, y0, in_execs):
    """BeginPlay: GameMode.DebugMode = Settings.DebugMode.

    The save is the record and the GameMode is where the game reads it, so the
    one copy happens as soon as Settings is known to be valid. A GameMode that
    is not BP_ThirdPersonGameMode has nowhere to put it, and goes on without.
    """
    gm = _at(_node(ed, FN_GET_GAME_MODE), x0, y0 + 240)
    as_gm = _at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 260, y0)
    _connect(_pin(gm, "ReturnValue", is_input=False), _pin(as_gm, "Object"))
    for e in in_execs:
        _connect(e, _pin(as_gm, "execute"))
    settings = _at(ed.add_get_member_variable_node("Settings"), x0 + 260, y0 + 400)
    saved = _at(ed.add_get_member_variable_node(DEBUG_MODE_VAR, SETTINGS_CLASS_PATH),
                x0 + 520, y0 + 400)
    _connect(_pin(settings, "Settings", is_input=False), _pin(saved, "self"))
    put = _at(ed.add_set_member_variable_node(DEBUG_MODE_VAR, GAME_MODE_CLASS_PATH),
              x0 + 780, y0)
    _connect(_loose_pin(as_gm, "AsBPThirdPersonGameMode", is_input=False),
             _pin(put, "self"))
    _connect(_pin(saved, DEBUG_MODE_VAR, is_input=False), _pin(put, DEBUG_MODE_VAR))
    _connect(BEL.find_then_pin(as_gm), _pin(put, "execute"))
    ed.add_comment_to_nodes(
        "Debug mode as the player last left it (BP_Settings.DebugMode, on for "
        "a first run), onto the GameMode where the HUD and the weapon read it.",
        [gm, as_gm, settings, saved, put])
    return (BEL.find_then_pin(put), _pin(as_gm, "CastFailed", is_input=False))


# ─── Event BeginPlay: the startup default ────────────────────────────────────

def _author_begin_play(ed, begin_play):
    origin = BEL.get_node_pos(begin_play)
    # The UMG screens before anything else, so they exist by the first DrawHUD.
    created = author_create_screens(ed, BEL.find_then_pin(begin_play),
                                    origin.x + 320, origin.y - 2400)
    made = emit_apply(ed, DEFAULT_PRESET, origin.x + 320, origin.y, created)
    label = PRESETS[DEFAULT_PRESET].label
    ed.add_comment_to_nodes(
        f"Every session starts at {label}. Setting Quality applies it: the first "
        f"Tick hands the preset's row to {TUNER_COMPONENT} (gfx_tune_tick.py).",
        made)

    # The settings load comes BEFORE the menu decision: the pause waits
    # MENU_SETTLE_S behind a Delay, and anything chained after it would wait
    # too -- or never run at all if NEW GAME got in first.
    #
    # The settings only have to exist by the first DrawHUD, and putting disk
    # access in front of the preset would let a failed load hide a failed
    # preset.
    loaded_tails = _author_load_settings(ed, origin.x + 320, origin.y + 1100,
                                         BEL.find_then_pin(made[-1]))
    loaded_tails = _author_restore_debug(ed, origin.x + 320, origin.y + 2300,
                                         loaded_tails)

    # --- open paused, on the menu -------------------------------------------
    # Pausing is what makes the menu a menu. Without it the level is live
    # behind the panel: ten wanderers spawn, start running at a player who
    # cannot move, and are on top of them by the time the title is read.
    # GetCommandLine is IMPURE -- it has an Exec pin -- so it has to sit in the
    # chain. Left hanging off it the compiler prunes the node and the Contains
    # below silently reads an empty string, which means the switch would never
    # be seen and every headless run would sit on the menu. It warns, loudly,
    # and verify_graphics_menu fails on node warnings for exactly this reason.
    mx, my = origin.x + 320, origin.y - 900
    cmdline = _at(_node(ed, FN_COMMAND_LINE), mx, my + 320)
    skipping = _at(_node(ed, FN_CONTAINS), mx + 240, my + 320)
    _connect(_pin(cmdline, "ReturnValue", is_input=False), _pin(skipping, "SearchIn"))
    _set(skipping, "Substring", SKIP_MENU_SWITCH)
    wants_menu = _at(_node(ed, FN_NOT), mx + 480, my + 320)
    _connect(_pin(skipping, "ReturnValue", is_input=False), _pin(wants_menu, "A"))
    shown = _at(ed.add_branch_node(), mx + 480, my)
    _connect(_pin(wants_menu, "ReturnValue", is_input=False), _pin(shown, "Condition"))
    for tail in loaded_tails:
        _connect(tail, _pin(cmdline, "execute"))
    _connect(BEL.find_then_pin(cmdline), _pin(shown, "execute"))

    # Not paused on frame zero -- see MENU_SETTLE_S. And only if the player has
    # not already pressed Enter inside that window: pausing after NEW GAME
    # would freeze the game with no menu left to unpause it.
    settle = _at(_node(ed, FN_DELAY), mx + 740, my)
    _set(settle, "Duration", MENU_SETTLE_S)
    _connect(BEL.find_then_pin(shown), _pin(settle, "execute"))
    started = _at(ed.add_get_member_variable_node(GAME_STARTED_VAR),
                  mx + 740, my + 320)
    still_on_menu = _at(ed.add_branch_node(), mx + 1000, my)
    _connect(_pin(started, GAME_STARTED_VAR, is_input=False),
             _pin(still_on_menu, "Condition"))
    _connect(BEL.find_then_pin(settle), _pin(still_on_menu, "execute"))
    hold = _at(_node(ed, FN_SET_PAUSED), mx + 1260, my)
    _set(hold, "bPaused", "true")
    _connect(BEL.find_else_pin(still_on_menu), _pin(hold, "execute"))

    # Straight into the game, for a run with nobody to press Enter.
    skip = _at(ed.add_set_member_variable_node(GAME_STARTED_VAR),
               mx + 740, my + 480)
    _set(skip, GAME_STARTED_VAR, "true")
    _connect(BEL.find_else_pin(shown), _pin(skip, "execute"))

    ed.add_comment_to_nodes(
        f"Open on the main menu, paused {MENU_SETTLE_S}s in. {GAME_STARTED_VAR} "
        f"defaults to false, so ReceiveDrawHUD draws the title panel instead "
        f"of the HUD until the player starts -- see _author_main_menu. Pausing "
        f"is what makes it a menu rather than a picture: unpaused, ten "
        f"wanderers are already running at a player who cannot move. The "
        f"delay is because a world paused on frame zero never updates its "
        f"camera or animates the player, so the view sits inside the "
        f"reference-posed mesh. {SKIP_MENU_SWITCH} on the command line skips "
        f"the menu, which is how the headless runs still test a game.",
        [cmdline, skipping, wants_menu, shown, settle, started, still_on_menu,
         hold, skip])


# ─── Event Tick: input ───────────────────────────────────────────────────────

def _author_tick(ed, tick):
    origin = BEL.get_node_pos(tick)
    x0, y0 = origin.x, origin.y

    # One PlayerController read feeds every key test and every console command.
    pc = _at(_node(ed, FN_GET_OWNING_PC), x0, y0 + 180)
    pc_out = _pin(pc, "ReturnValue", is_input=False)

    # --- M toggles the menu -------------------------------------------------
    was_m = _at(_node(ed, FN_WAS_PRESSED), x0 + 260, y0 + 120)
    _connect(pc_out, _pin(was_m, "self"))
    _set(was_m, "Key", MENU_KEY)

    br_m = _at(ed.add_branch_node(), x0 + 560, y0)
    # The key, or the panel's close row taken (Enter on it, or a click:
    # menu_screens.py). Only an open panel has rows, so a row never opens it.
    m_clicks = []
    _connect(or_pause_row(ed, _pin(was_m, "ReturnValue", is_input=False), CLOSE_ACTION,
                          x0 - 240, y0 + 400, m_clicks), _pin(br_m, "Condition"))
    # First the open panel holds the player still (menu_still.py). Then save
    # and exit, the profile load and the death wipe (save_exit.py).
    # Then the loot window (loot_tick.py): the body in reach, its keys, a take.
    stilled = author_menu_still(ed, pc_out, [BEL.find_then_pin(tick)], x0, y0 - 6000)
    saved = author_save_exit_tick(ed, pc_out, stilled, x0, y0 - 4000)
    looted = author_loot_tick(ed, pc_out, saved, x0 + 30000, y0 - 4000)
    # Then the M panel's tuning tabs (tune_tick.py and its three siblings).
    # The graphics one also hands the picked preset to the tuner component.
    tuned = author_tune_tick(ed, pc_out, looted, x0 + 44000, y0 - 4000)
    tuned = author_monster_tune_tick(ed, pc_out, tuned, x0 + 58000, y0 - 4000)
    tuned = author_world_tune_tick(ed, pc_out, tuned, x0 + 72000, y0 - 4000)
    for tail in author_gfx_tune_tick(ed, pc_out, tuned, x0 + 92000, y0 - 4000):
        _connect(tail, _pin(br_m, "execute"))

    get_open = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 560, y0 + 200)
    not_open = _at(_node(ed, FN_NOT), x0 + 740, y0 + 200)
    _connect(_pin(get_open, "MenuOpen", is_input=False), _pin(not_open, "A"))

    set_open = _at(ed.add_set_member_variable_node("MenuOpen"), x0 + 900, y0)
    _connect(_pin(not_open, "ReturnValue", is_input=False), _pin(set_open, "MenuOpen"))
    _connect(BEL.find_then_pin(br_m), _pin(set_open, "execute"))

    ed.add_comment_to_nodes(
        f"{MENU_KEY} toggles the menu, and its close row shuts it.  Polled on Tick rather than bound as an "
        "input action: an FInputActionValue binding would need an IA asset and "
        "an IMC entry, and neither is authorable from Python.",
        [was_m, br_m, get_open, not_open, set_open] + m_clicks)

    # --- the panel's own rows, gated on the menu being open -----------------
    gate_get = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 1120, y0 + 200)
    gate = _at(ed.add_branch_node(), x0 + 1280, y0)
    _connect(_pin(gate_get, "MenuOpen", is_input=False), _pin(gate, "Condition"))
    # Both arms of the toggle fall through to the gate; an exec input accepts
    # more than one link, so no Sequence node is needed.
    _connect(BEL.find_then_pin(set_open), _pin(gate, "execute"))
    _connect(_pin(br_m, "else", is_input=False), _pin(gate, "execute"))

    # --- the debug row toggles debug mode -----------------------------------
    # Written to the GameMode rather than to this HUD: the pellet tracers are
    # drawn by BP_WeaponComponent, which can reach a GameMode and cannot reach
    # a HUD variable.  The row has no key: Enter on it or a click raises
    # PauseClick, like every other row of the panel.
    bx = x0 + 1500
    by = y0
    br_d = _at(ed.add_branch_node(), bx + 300, by)
    d_taken = []
    _connect(pause_row_taken(ed, DEBUG_ACTION, bx - 500, by + 280, d_taken),
             _pin(br_d, "Condition"))
    _connect(BEL.find_then_pin(gate), _pin(br_d, "execute"))

    gm = _at(_node(ed, FN_GET_GAME_MODE), bx + 500, by + 240)
    as_gm = _at(_palette(ed, NODE_CAST_GAME_MODE), bx + 740, by)
    _connect(_pin(gm, "ReturnValue", is_input=False), _pin(as_gm, "Object"))
    _connect(BEL.find_then_pin(br_d), _pin(as_gm, "execute"))
    gm_out = _loose_pin(as_gm, "AsBPThirdPersonGameMode", is_input=False)

    was_on = _at(ed.add_get_member_variable_node(DEBUG_MODE_VAR,
                                                 GAME_MODE_CLASS_PATH),
                 bx + 980, by + 240)
    _connect(gm_out, _pin(was_on, "self"))
    flip = _at(_node(ed, FN_NOT), bx + 1220, by + 240)
    _connect(_pin(was_on, DEBUG_MODE_VAR, is_input=False), _pin(flip, "A"))
    set_dbg = _at(ed.add_set_member_variable_node(DEBUG_MODE_VAR,
                                                  GAME_MODE_CLASS_PATH),
                  bx + 1460, by)
    _connect(gm_out, _pin(set_dbg, "self"))
    _connect(_pin(flip, "ReturnValue", is_input=False), _pin(set_dbg, DEBUG_MODE_VAR))
    _connect(BEL.find_then_pin(as_gm), _pin(set_dbg, "execute"))

    # ...and into the save, written on the spot like every other setting.
    settings = _at(ed.add_get_member_variable_node("Settings"), bx + 1460, by + 400)
    settings_out = _pin(settings, "Settings", is_input=False)
    keep_dbg = _at(ed.add_set_member_variable_node(DEBUG_MODE_VAR,
                                                   SETTINGS_CLASS_PATH),
                   bx + 1720, by)
    _connect(settings_out, _pin(keep_dbg, "self"))
    _connect(_pin(flip, "ReturnValue", is_input=False), _pin(keep_dbg, DEBUG_MODE_VAR))
    _connect(BEL.find_then_pin(set_dbg), _pin(keep_dbg, "execute"))
    _, writer = _emit_save(ed, settings_out, BEL.find_then_pin(keep_dbg),
                           bx + 1980, by)

    ed.add_comment_to_nodes(
        "The panel's debug row -> debug mode, held on the GameMode so the weapon "
        "component can read it too, and saved to BP_Settings so it survives a "
        "restart.  It turns on the FPS readout, the pellet tracers and the "
        "wanderers' numbers.",
        d_taken + [br_d, gm, as_gm, was_on, flip, set_dbg, settings, keep_dbg,
         writer])


# ─── The health readout ──────────────────────────────────────────────────────

def _vec(ed, x, y, z, px, py):
    """A constant vector as a node, because struct pins reject text defaults.

    set_pin_value on an FVector pin returns False for every format and leaves
    the pin empty, which the compiler reads as the zero vector.
    """
    n = _at(_node(ed, FN_MAKE_VECTOR), px, py)
    for axis, value in (("X", x), ("Y", y), ("Z", z)):
        _set(n, axis, float(value))
    return _pin(n, "ReturnValue", is_input=False)


def _author_npc_bars(ed, x0, y0, in_execs):
    """A health bar floating over every NPC, in screen space.

    Drawn on the HUD canvas rather than as a widget component on the NPC: UMG
    layout cannot be authored from Python at all (WidgetTree is protected), and
    a 3D bar would need a material and a facing update. Project() turns the
    world point above each head into canvas pixels, which is all DrawRect needs.
    """
    every = _at(_node(ed, FN_ALL_ACTORS), x0, y0)
    _pin(every, "ActorClass").set_pin_value(NPC_CLASS_PATH)
    for e in in_execs:
        _connect(e, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(loop, x0 + 280, y0)
    _connect(_pin(every, "OutActors", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(every), _loose_pin(loop, "Exec"))
    npc = _loose_pin(loop, "ArrayElement", is_input=False)

    comp = _at(_node(ed, FN_GET_COMP), x0 + 580, y0 + 260)
    _connect(npc, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 840, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    health = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                 x0 + 1100, y0 + 260)
    _connect(as_health, _pin(health, "self"))
    max_health = _at(ed.add_get_member_variable_node("MaxHealth", HEALTH_CLASS_PATH),
                     x0 + 1100, y0 + 380)
    _connect(as_health, _pin(max_health, "self"))

    where = _at(_node(ed, FN_ACTOR_LOC), x0 + 1100, y0 + 520)
    _connect(npc, _pin(where, "self"))
    above = _at(_node(ed, FN_ADD_VV), x0 + 1360, y0 + 520)
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(above, "A"))
    _connect(_vec(ed, 0.0, 0.0, NPC_BAR_Z, x0 + 1100, y0 + 660), _pin(above, "B"))

    proj = _at(_node(ed, FN_PROJECT), x0 + 1620, y0 + 520)
    _connect(_pin(above, "ReturnValue", is_input=False), _pin(proj, "Location"))
    parts = _at(_node(ed, FN_BREAK_VECTOR), x0 + 1860, y0 + 520)
    _connect(_pin(proj, "ReturnValue", is_input=False), _loose_pin(parts, "InVec"))

    # Project returns the depth in Z, and it is negative for anything behind the
    # camera -- without this test those NPCs get their bars mirrored onto the
    # screen as if they were in front.
    in_front = _at(_node(ed, FN_GREATER), x0 + 2120, y0 + 640)
    _connect(_pin(parts, "Z", is_input=False), _pin(in_front, "A"))
    _set(in_front, "B", 0.0)

    # ...and hurt recently. A bar over every wanderer at all times is most of
    # the screen once the pack arrives, and it is only ever *read* just after a
    # shot lands; the rest of the time it is clutter over the forest the player
    # is aiming into. LastDamageTime is stamped by the pellet that did the
    # damage (see _author_impact), and defaults far enough in the past that
    # nothing is showing a bar at level start.
    hurt_at = _at(ed.add_get_member_variable_node(LAST_DAMAGE_VAR,
                                                  HEALTH_CLASS_PATH),
                  x0 + 1100, y0 + 940)
    _connect(as_health, _pin(hurt_at, "self"))
    now = _at(_node(ed, FN_TIME_SECONDS), x0 + 1100, y0 + 1080)
    since = _at(_node(ed, FN_SUB), x0 + 1620, y0 + 940)
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(since, "A"))
    _connect(_pin(hurt_at, LAST_DAMAGE_VAR, is_input=False), _pin(since, "B"))
    recent = _at(_node(ed, FN_LE), x0 + 1860, y0 + 940)
    _connect(_pin(since, "ReturnValue", is_input=False), _pin(recent, "A"))
    _set(recent, "B", NPC_BAR_SECONDS)

    # ...and still alive. A killed wanderer now lies where it fell for a minute
    # (see CORPSE_SECONDS), and it was shot a moment ago by definition, so
    # without this every corpse wears an empty bar for its first five seconds.
    gone = _at(ed.add_get_member_variable_node("Dead", HEALTH_CLASS_PATH),
               x0 + 1100, y0 + 1200)
    _connect(as_health, _pin(gone, "self"))
    alive = _at(_node(ed, FN_NOT), x0 + 1620, y0 + 1200)
    _connect(_pin(gone, "Dead", is_input=False), _pin(alive, "A"))

    # Safe to fold into one AND: every half is arithmetic on values already
    # read, so pulling them costs two comparisons and has no side effect. (The
    # NPC melee gate could not do this -- there, one half of the AND dragged a
    # whole location chain behind it. See the pure-node note in CLAUDE.md.)
    breathing = _at(_node(ed, FN_AND), x0 + 1860, y0 + 1080)
    _connect(_pin(recent, "ReturnValue", is_input=False), _pin(breathing, "A"))
    _connect(_pin(alive, "ReturnValue", is_input=False), _pin(breathing, "B"))

    showing = _at(_node(ed, FN_AND), x0 + 2120, y0 + 800)
    _connect(_pin(in_front, "ReturnValue", is_input=False), _pin(showing, "A"))
    _connect(_pin(breathing, "ReturnValue", is_input=False), _pin(showing, "B"))

    visible = _at(ed.add_branch_node(), x0 + 2380, y0)
    _connect(_pin(showing, "ReturnValue", is_input=False), _pin(visible, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(visible, "execute"))

    left = _at(_node(ed, FN_SUB), x0 + 2380, y0 + 300)
    _connect(_pin(parts, "X", is_input=False), _pin(left, "A"))
    _set(left, "B", NPC_BAR[0] / 2.0)          # centre the bar on the head
    left_out = _pin(left, "ReturnValue", is_input=False)
    top_out = _pin(parts, "Y", is_input=False)

    frac = _at(_node(ed, FN_DIV), x0 + 2380, y0 + 440)
    _connect(_pin(health, "Health", is_input=False), _pin(frac, "A"))
    _connect(_pin(max_health, "MaxHealth", is_input=False), _pin(frac, "B"))
    fill_w = _at(_node(ed, FN_MUL), x0 + 2620, y0 + 440)
    _connect(_pin(frac, "ReturnValue", is_input=False), _pin(fill_w, "A"))
    _set(fill_w, "B", NPC_BAR[0])

    back = _draw_texture(ed, x0 + 2640, y0, "T_UI_BarTrack")
    _set(back, "ScreenW", NPC_BAR[0])
    _set(back, "ScreenH", NPC_BAR[1])
    _connect(left_out, _pin(back, "ScreenX"))
    _connect(top_out, _pin(back, "ScreenY"))
    _connect(BEL.find_then_pin(visible), _pin(back, "execute"))

    fill = _draw_texture(ed, x0 + 2900, y0, "T_UI_Bar", tint=COL_NPC_FILL)
    _set(fill, "ScreenW", NPC_BAR[0])
    _set(fill, "ScreenH", NPC_BAR[1])
    _connect(left_out, _pin(fill, "ScreenX"))
    _connect(top_out, _pin(fill, "ScreenY"))
    _connect(_pin(fill_w, "ReturnValue", is_input=False), _pin(fill, "ScreenW"))
    _connect(BEL.find_then_pin(back), _pin(fill, "execute"))

    # The wanderer's number, just left of its bar. Read off the NPC's own health
    # component rather than kept in a list here: the HUD never has to be told
    # that a wanderer died and another took its place.
    nid = _at(ed.add_get_member_variable_node(NPC_ID_VAR, HEALTH_CLASS_PATH),
              x0 + 1100, y0 + 800)
    _connect(as_health, _pin(nid, "self"))
    nid_str = _at(_node(ed, FN_INT_TO_STR), x0 + 1360, y0 + 800)
    _connect(_pin(nid, NPC_ID_VAR, is_input=False), _pin(nid_str, "InInt"))

    id_x = _at(_node(ed, FN_SUB), x0 + 2620, y0 + 700)
    _connect(left_out, _pin(id_x, "A"))
    _set(id_x, "B", NPC_ID_WIDTH + NPC_ID_GAP)
    id_y = _at(_node(ed, FN_SUB), x0 + 2620, y0 + 840)
    _connect(top_out, _pin(id_y, "A"))
    _set(id_y, "B", NPC_ID_RISE)

    # ...and only in debug mode. The number is how the log's "[NPC-SPAWN] #7"
    # is matched to a body on screen, which is a thing a developer does and not
    # a thing the game is. DebugOn is this frame's copy of the GameMode's flag,
    # taken once in _author_draw.
    numbered = _at(ed.add_get_member_variable_node("DebugOn"), x0 + 2900, y0 + 300)
    labelled = _at(ed.add_branch_node(), x0 + 3160, y0)
    _connect(_pin(numbered, "DebugOn", is_input=False), _pin(labelled, "Condition"))
    _connect(BEL.find_then_pin(fill), _pin(labelled, "execute"))

    number = _at(_node(ed, FN_DRAW_TEXT), x0 + 3420, y0)
    _connect(_pin(nid_str, "ReturnValue", is_input=False), _pin(number, "Text"))
    _set(number, "TextColor", COL_NPC_ID)
    _set(number, "Scale", NPC_ID_SCALE)
    _connect(_pin(id_x, "ReturnValue", is_input=False), _pin(number, "ScreenX"))
    _connect(_pin(id_y, "ReturnValue", is_input=False), _pin(number, "ScreenY"))
    _connect(BEL.find_then_pin(labelled), _pin(number, "execute"))

    ed.add_comment_to_nodes(
        f"One bar per LIVING wanderer, and only for {NPC_BAR_SECONDS:.0f}s "
        "after something hurt it -- hidden by default. GetAllActorsOfClass every "
        "frame is not free, but the alternative -- a registry the NPCs write "
        "themselves into -- would need a graph on BP_ForestWanderer, which "
        "build_npc_blueprints.py owns.",
        [every, loop, comp, cast, health, max_health, where, above, proj, parts,
         in_front, hurt_at, now, since, recent, gone, alive, breathing,
         showing, visible, left, frac,
         fill_w, back, fill, nid, nid_str, id_x, id_y, numbered, labelled,
         number])
    return (_loose_pin(loop, "Completed", is_input=False),)


def _author_draw(ed, x0, y0):
    draw = ed.create_node_from_name(NODE_DRAW_HUD, unreal.Vector2D(x0, y0), [])
    if not draw:
        raise RuntimeError(f"could not create {NODE_DRAW_HUD}")

    # Dead or alive, before anything is drawn. The death menu replaces the HUD
    # rather than covering it, so this branch is the first thing in the frame.
    mode = _at(_node(ed, FN_GET_GAME_MODE), x0 - 700, y0 + 240)
    as_mode = _at(_palette(ed, NODE_CAST_GAME_MODE), x0 - 440, y0)
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(BEL.find_then_pin(draw), _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    # This frame's copy of DebugMode, taken here and nowhere else.  Every
    # consumer below reads the HUD's own DebugOn instead of the GameMode's
    # variable, for one reason: the cast-failed path reaches the same drawing
    # code, and a Get with an invalid self is an "Accessed None" per wanderer
    # per frame.  Copying it once gives that path a real answer -- false -- and
    # costs one node.
    on_get = _at(ed.add_get_member_variable_node(DEBUG_MODE_VAR,
                                                 GAME_MODE_CLASS_PATH),
                 x0 - 440, y0 + 380)
    _connect(mode_out, _pin(on_get, "self"))
    copy_dbg = _at(ed.add_set_member_variable_node("DebugOn"), x0 - 180, y0 + 380)
    _connect(_pin(on_get, DEBUG_MODE_VAR, is_input=False), _pin(copy_dbg, "DebugOn"))
    _connect(BEL.find_then_pin(as_mode), _pin(copy_dbg, "execute"))
    no_dbg = _at(ed.add_set_member_variable_node("DebugOn"), x0 - 180, y0 + 620)
    _set(no_dbg, "DebugOn", "false")
    _connect(_pin(as_mode, "CastFailed", is_input=False), _pin(no_dbg, "execute"))

    # The player's settings, onto the weapon component. Before the menu and
    # before the dead/alive test, because it is the one thing on this event
    # that has to happen on every frame in every state -- a sensitivity changed
    # on the settings screen has to be in effect the moment the world unpauses.
    # The difficulty onto the GameMode first, where there is one to write.
    to_mode = author_push_difficulty(ed, x0 + 3000, y0 + 13400,
                                     BEL.find_then_pin(copy_dbg), mode_out)
    pushed = _author_push_settings(ed, x0 + 3000, y0 + 14000,
                                   (*to_mode, BEL.find_then_pin(no_dbg)))

    # The FPS readout, in every state -- title, game, death -- while debug
    # mode is on. Drawn first, so every panel after it can sit on top.
    fps_out = author_fps(ed, x0 + 3000, y0 + 16000, pushed)

    # Where the mouse cursor is, before the first screen that asks (cursor.py).
    # The main menu, before the dead/alive test: a title screen is neither.
    playing = author_main_menu(ed, x0 + 3000, y0 + 6000,
                               [author_cursor_read(ed, fps_out, x0 + 3000, y0 + 18000)])

    alive = _at(ed.add_branch_node(), x0 + 60, y0)
    dead_get = _at(ed.add_get_member_variable_node(PLAYER_DEAD_VAR,
                                                   GAME_MODE_CLASS_PATH),
                   x0 - 440, y0 + 240)
    _connect(mode_out, _pin(dead_get, "self"))
    _connect(_pin(dead_get, PLAYER_DEAD_VAR, is_input=False), _pin(alive, "Condition"))
    for e in playing:
        _connect(e, _pin(alive, "execute"))

    author_death_menu(ed, x0 + 3000, y0 + 3000, (BEL.find_then_pin(alive),), mode_out)

    # A GameMode that is not BP_ThirdPersonGameMode cannot say whether the
    # player is dead, so it is treated as alive and the HUD shows as normal --
    # a missing death menu is recoverable, a missing HUD is not.
    living = author_alive(ed, x0 + 300, y0 - 600, (BEL.find_else_pin(alive),))

    # The stat bars and the kill counter, into WBP_HUD.
    after_hp = author_hp(ed, x0, y0 - 900, living)
    after_st = _author_stamina(ed, x0, y0 - 1600, after_hp)
    after_sv = author_survival_bars(ed, x0 + 9000, y0 - 1600, after_st)
    after_kills = author_kills(ed, x0, y0 - 2300, after_sv)

    # The wanderers' bars, still on the canvas: one per wanderer, placed by
    # projecting its head each frame. Then the inventory grid.
    after_npc = _author_npc_bars(ed, x0, y0 - 3200, after_kills)
    after_inv = author_inventory(ed, x0, y0 - 5000, after_npc)

    # The crosshair or scope, also on the canvas: centred off the viewport
    # and sized by the gun's cloud every frame.
    after_aim = _author_reticle(ed, x0, y0 - 6800, after_inv)
    after_aim = author_exit_banner(ed, x0, y0 - 8200, after_aim)
    after_aim = author_loot_window(ed, x0, y0 - 9600, after_aim)

    # Last: the M panel. Every path above -- written or cast-failed -- falls
    # through to it; an exec input takes more than one link.
    shown = author_pause_menu(ed, x0 + 420, y0, after_aim)
    guns = author_tune_panel(ed, x0 + 4800, y0, shown)
    monsters = author_tune_panel(ed, x0 + 11000, y0, guns, MONSTER_TAB)
    world = author_tune_panel(ed, x0 + 17200, y0, monsters, WORLD_TAB)
    author_tune_panel(ed, x0 + 23400, y0, world, GFX_TAB)


# ─── Entry points ────────────────────────────────────────────────────────────

def build_hud_blueprint(rebuild=False):
    """Create BP_GraphicsMenuHUD and author its input and draw graphs.

    ``rebuild`` wipes an existing graph first.  Without it an already-authored
    blueprint is left alone, because re-running the node adds would duplicate
    both graphs -- but that also means no edit to this file would ever reach the
    asset, which is the trap the NPC builder fell into.
    """
    # Cast nodes only appear in the palette for classes that are already
    # loaded; this graph casts to the health and weapon components. Without the
    # loads create_node_from_name returns None and the error reads like a typo
    # in the node name rather than a missing asset.
    build_profile_savegame()
    # The tuner component before the HUD that carries it and sets its variables.
    build_graphics_tuner()
    # The screens first: the HUD's variables are typed to their classes, and
    # the cast nodes to the rows and slots need those classes loaded.
    build_menu_row()
    build_inventory_slot()
    build_hud_widget()
    build_main_menu()
    build_pause_menu()
    build_death_menu()
    for path in ("/Game/Weapons/BP_HealthComponent",
                 "/Game/Weapons/BP_WeaponComponent",
                 "/Game/Weapons/BP_WeaponItem",
                 SURVIVAL_BP_PATH, PROFILE_BP_PATH,
                 GAME_MODE_PATH):
        if not _asset_sub().load_asset(path):
            raise RuntimeError(f"could not load {path} for its cast node")

    bp = _create_blueprint(HUD_BP_PATH, unreal.HUD)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{HUD_BP_PATH} has no EventGraph")

    tick = ed.find_event_node("ReceiveTick")
    outgoing = BEL.find_then_pin(tick) if tick else None
    authored = bool(outgoing and outgoing.is_valid() and outgoing.list_connected_pins())

    if authored and not rebuild:
        _log(f"{HUD_BP_PATH} graph already authored — reusing")
        if not BEL.compile_blueprint(bp):
            raise RuntimeError("BP_GraphicsMenuHUD failed to compile")
        _asset_sub().save_loaded_asset(bp)
        return bp

    if authored:
        _log("wiping the existing graph")
        ed.remove_nodes(ed.list_all_nodes())
        tick = None

    if not tick:
        # A fresh Blueprint ships disabled Tick/BeginPlay placeholders, but a
        # wiped graph has none, so put them back from the palette.
        tick = ed.create_node_from_name(NODE_TICK, unreal.Vector2D(0.0, 0.0), [])
        if not tick:
            raise RuntimeError(f"could not create {NODE_TICK}")

    _ensure_variables(ed, bp)
    install_tuner(bp)
    origin = BEL.get_node_pos(tick)

    begin_play = ed.find_event_node("ReceiveBeginPlay")
    if not begin_play:
        begin_play = ed.create_node_from_name(
            NODE_BEGIN_PLAY, unreal.Vector2D(float(origin.x), float(origin.y - 500)), [])
        if not begin_play:
            raise RuntimeError(f"could not create {NODE_BEGIN_PLAY}")
    _author_begin_play(ed, begin_play)

    _author_tick(ed, tick)
    _author_draw(ed, origin.x, origin.y + 1800)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GraphicsMenuHUD failed to compile")
    _apply_defaults(bp, {"MenuOpen": False, "DebugOn": False,
                         PAUSE_ROW_VAR: 0, MENU_STILL_VAR: False,
                         "Quality": DEFAULT_PRESET,
                         "MenuPage": PAGE_TITLE, "MenuRow": 0,
                         "Capturing": False,
                         "KeyPool": [_key(k) for k in KEY_POOL],
                         **difficulty_defaults(), **profile_defaults(),
                         **dev_guns_defaults(), **loot_defaults(),
                         **tune_defaults(), **monster_tune_defaults(),
                         **world_tune_defaults(), **gfx_tune_defaults(),
                         **cursor_defaults()})
    _asset_sub().save_loaded_asset(bp)
    _log(f"built {HUD_BP_PATH}")
    return bp


def attach_to_game_mode(hud_bp):
    """Point the project's default game mode at the menu HUD.

    This is the only wiring step: BP_ThirdPersonGameMode is GlobalDefaultGameMode
    and no generated level overrides it, so every level picks the HUD up.
    """
    eas = _asset_sub()
    gm = eas.load_asset(GAME_MODE_PATH)
    if not gm:
        raise RuntimeError(f"could not load {GAME_MODE_PATH}")
    hud_class = BEL.generated_class(hud_bp)
    cdo = unreal.get_default_object(BEL.generated_class(gm))
    if cdo.get_editor_property("hud_class") == hud_class:
        _log("game mode already points at the menu HUD")
        return
    cdo.set_editor_property("hud_class", hud_class)
    if not BEL.compile_blueprint(gm):
        raise RuntimeError("BP_ThirdPersonGameMode failed to compile")
    eas.save_loaded_asset(gm)
    _log(f"{GAME_MODE_PATH}.HUDClass -> {HUD_BP_PATH}")


def ensure_graphics_menu(force=False):
    """Build the menu if missing (or unconditionally when ``force``)."""
    eas = _asset_sub()
    if not force and eas.does_asset_exist(HUD_BP_PATH):
        hud = eas.load_asset(HUD_BP_PATH)
        attach_to_game_mode(hud)
        return hud
    hud = build_hud_blueprint(rebuild=force)
    attach_to_game_mode(hud)
    return hud


if __name__ == "__main__":
    ensure_graphics_menu(force=True)
    _log("done")
