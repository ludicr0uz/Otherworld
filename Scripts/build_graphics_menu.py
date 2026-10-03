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
                    --> pause on the menu (unless -nomenu), with the HUD
                        ticking while paused (graphics_menu/menu_main.py)

  [Event Tick] --> in play: save and exit (graphics_menu/save_exit.py) and
                   the loot window (graphics_menu/loot_tick.py); then, on the
                   title too, the tuning tabs, the menu's own rows and M
                   (graphics_menu/menu_main.py) and the debug row

  [Event ReceiveDrawHUD] --> DebugOn copy, settings pushed onto the weapon
                             component, difficulty onto the GameMode, FPS
    --> GameStarted?   no: the HUD hidden and the menu held open (the title)
    --> PlayerDead?    yes: the death menu and [R]
                       no:  HP, stamina, survival bars, kills, the wanderers'
                            bars (canvas), inventory, reticle (canvas), the
                            save-and-exit banner, the loot window
    --> the menu while MenuOpen, on the title and in play: its rows, or the
        settings page or a tuning tab in their place
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The authoring helpers every builder shares.
from uebp.graph import (
    BEL, BGE, PIN, _assets, _connect, _create_blueprint, _key, _loose_pin, _node, _palette,
    _pin, _set, else_, make_log, out, then)
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
from graphics_menu.gfx_save import (                                # noqa: E402
    author_load_graphics, build_graphics_savegame)
# The FPS readout, on screen whatever debug mode says; see graphics_menu/fps.py.
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
    DEBUG_ACTION, GAME_STARTED_VAR, PAUSE_ROW_VAR)
from graphics_menu.wbp_hud import build_hud_widget                  # noqa: E402
from graphics_menu.wbp_parts import (                              # noqa: E402
    build_inventory_slot, build_menu_row)
from graphics_menu.wbp_screens import (                            # noqa: E402
    build_death_menu, build_main_menu, build_pause_menu)
from graphics_menu.ui_graph import (                               # noqa: E402
    author_create_screens, declare_ui_vars)
from uebp.layout import arrange                                 # noqa: E402
from graphics_menu.menu_screens import (                           # noqa: E402
    author_alive, author_death_menu, author_pause_menu, author_title)
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
from graphics_menu.wear_draw import author_wear_panel               # noqa: E402
from graphics_menu.inv_drag import declare_inv_vars, inv_defaults   # noqa: E402
from graphics_menu.wear_tick import (                               # noqa: E402
    author_wear_tick, declare_wear_vars, wear_defaults)
from graphics_menu.cursor import (                                  # noqa: E402
    author_cursor_read, cursor_defaults, declare_cursor_vars)
from graphics_menu.menu_nav import pause_row_taken                  # noqa: E402
from graphics_menu.menu_main import (                               # noqa: E402
    author_in_play, author_main_rows_tick, author_title_ticks)
from graphics_menu.menu_still import (                              # noqa: E402
    MENU_STILL_VAR, author_menu_still)
from graphics_menu.monster_tune_consts import MONSTER_TAB           # noqa: E402
from graphics_menu.monster_tune_tick import (                       # noqa: E402
    author_monster_tune_tick, declare_monster_tune_vars, monster_tune_defaults)
from graphics_menu.player_tune_consts import PLAYER_TAB             # noqa: E402
from graphics_menu.player_tune_tick import (                        # noqa: E402
    author_player_tune_tick, declare_player_tune_vars, player_tune_defaults)
from graphics_menu.tune_draw import author_tune_panel               # noqa: E402
from graphics_menu.tune_tick import (                               # noqa: E402
    author_tune_tick, declare_tune_vars, tune_defaults)
from graphics_menu.world_tune_consts import WORLD_TAB               # noqa: E402
from graphics_menu.world_tune_tick import (                         # noqa: E402
    author_world_tune_tick, declare_world_tune_vars, world_tune_defaults)
from graphics_menu.loot_tick import (                               # noqa: E402
    author_loot_tick, declare_loot_vars, loot_defaults)
from survival.paths import SURVIVAL_BP_PATH                        # noqa: E402
from uebp.nodes.actor import (  # noqa: E402
    FN_ACTOR_LOC, FN_DRAW_TEXT, FN_GET_COMP, FN_GET_OWNING_PC, FN_PROJECT)
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_CLEAR, FN_ARR_LEN  # noqa: E402
from uebp.nodes.math import (  # noqa: E402
    FN_ADD_VV, FN_AND, FN_BREAK_VECTOR, FN_DIV_FF, FN_GREATER_FF, FN_LE_FF, FN_MAKE_VECTOR,
    FN_MUL_FF, FN_NEQ_II, FN_NOT, FN_SUB_FF)
from uebp.nodes.palette import (  # noqa: E402
    MACRO_FOR_EACH, NODE_BEGIN_PLAY, NODE_CAST_GAME_MODE, NODE_CAST_HEALTH,
    NODE_CAST_SETTINGS, NODE_DRAW_HUD, NODE_TICK)
from uebp.nodes.system import (  # noqa: E402
    FN_ALL_ACTORS, FN_COMMAND_LINE, FN_CONTAINS, FN_CREATE_SAVE, FN_DELAY, FN_GET_GAME_MODE,
    FN_INT_TO_STR, FN_LOAD_SAVE, FN_SAVE_EXISTS, FN_SET_PAUSED, FN_TIME_SECONDS)

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


_log = make_log("UI")


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
    settings_class = _assets().load_asset(combat_paths.SETTINGS_BP_PATH)
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
    declare_wear_vars(ed)
    declare_inv_vars(ed)
    declare_tune_vars(ed)
    declare_monster_tune_vars(ed)
    declare_world_tune_vars(ed)
    declare_player_tune_vars(ed)
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
        return then(node)
    return in_exec


def _author_load_settings(ed, in_exec):
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

    exists = keep(_node(ed, FN_SAVE_EXISTS))
    _set(exists, "SlotName", SETTINGS_SLOT)
    _set(exists, "UserIndex", SETTINGS_USER_INDEX)
    flow = _chain(exists, in_exec)

    have = keep(ed.add_branch_node())
    _connect(out(exists), _pin(have, "Condition"))
    _connect(flow, _pin(have, "execute"))

    loaded = keep(_node(ed, FN_LOAD_SAVE))
    _set(loaded, "SlotName", SETTINGS_SLOT)
    _set(loaded, "UserIndex", SETTINGS_USER_INDEX)
    after_load = _chain(loaded, then(have))

    as_saved = keep(_palette(ed, NODE_CAST_SETTINGS))
    _connect(out(loaded), _pin(as_saved, "Object"))
    _connect(after_load, _pin(as_saved, "execute"))
    took = keep(ed.add_set_member_variable_node("Settings"))
    _connect(_loose_pin(as_saved, "AsBPSettings", is_input=False),
             _pin(took, "Settings"))
    _connect(then(as_saved), _pin(took, "execute"))

    # A save that will not cast is a save from a different class, which is the
    # same situation as no save at all -- so the failed arm joins the create
    # path rather than leaving Settings null and every read below an
    # Accessed None.
    fresh = keep(_node(ed, FN_CREATE_SAVE))
    _pin(fresh, "SaveGameClass").set_pin_value(SETTINGS_CLASS_PATH)
    for e in (else_(have), out(as_saved, "CastFailed")):
        _connect(e, _pin(fresh, "execute"))
    as_new = keep(_palette(ed, NODE_CAST_SETTINGS))
    _connect(out(fresh), _pin(as_new, "Object"))
    _connect(then(fresh), _pin(as_new, "execute"))
    made_it = keep(ed.add_set_member_variable_node("Settings"))
    _connect(_loose_pin(as_new, "AsBPSettings", is_input=False),
             _pin(made_it, "Settings"))
    _connect(then(as_new), _pin(made_it, "execute"))

    got = keep(ed.add_get_member_variable_node("Settings"))
    settings_out = out(got, "Settings")
    binds = keep(ed.add_get_member_variable_node("Binds", SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(binds, "self"))
    binds_out = out(binds, "Binds")

    count = keep(_node(ed, FN_ARR_LEN))
    _connect(binds_out, _loose_pin(count, "TargetArray"))
    short = keep(_node(ed, FN_NEQ_II))
    _connect(out(count), _pin(short, "A"))
    _set(short, "B", len(BIND_VARS))

    repair = keep(ed.add_branch_node())
    _connect(out(short), _pin(repair, "Condition"))
    for e in (then(took), then(made_it), out(as_new, "CastFailed")):
        _connect(e, _pin(repair, "execute"))

    wipe = keep(_node(ed, FN_ARR_CLEAR))
    _connect(binds_out, _loose_pin(wipe, "TargetArray"))
    _connect(then(repair), _pin(wipe, "execute"))
    flow = then(wipe)
    for _var, key in BIND_VARS:
        add = keep(_node(ed, FN_ARR_ADD))
        _connect(binds_out, _loose_pin(add, "TargetArray"))
        # Bare key name, never struct text: FKey exports as just its name, so
        # '(KeyName="Q")' imports back as a key literally called "(".
        _set(add, "NewItem", key)
        _connect(flow, _pin(add, "execute"))
        flow = then(add)
    saved, writer = _emit_save(ed, settings_out, flow)
    made.append(writer)

    ed.add_comment_to_nodes(
        f"The settings the player keeps. Slot {SETTINGS_SLOT!r} if it is on "
        f"disk, a fresh BP_Settings if it is not, and a refill of Binds if it "
        f"is not exactly {len(BIND_VARS)} long -- which is what a save written "
        f"by an older build looks like. Every read on the settings page "
        f"indexes Binds by row, so a short array is an out-of-range Get per "
        f"frame that draws nothing and says nothing.",
        made)
    return (saved, else_(repair))


def _author_restore_debug(ed, in_execs):
    """BeginPlay: GameMode.DebugMode = Settings.DebugMode.

    The save is the record and the GameMode is where the game reads it, so the
    one copy happens as soon as Settings is known to be valid. A GameMode that
    is not BP_ThirdPersonGameMode has nowhere to put it, and goes on without.
    """
    gm = _node(ed, FN_GET_GAME_MODE)
    as_gm = _palette(ed, NODE_CAST_GAME_MODE)
    _connect(out(gm), _pin(as_gm, "Object"))
    for e in in_execs:
        _connect(e, _pin(as_gm, "execute"))
    settings = ed.add_get_member_variable_node("Settings")
    saved = ed.add_get_member_variable_node(DEBUG_MODE_VAR, SETTINGS_CLASS_PATH)
    _connect(out(settings, "Settings"), _pin(saved, "self"))
    put = ed.add_set_member_variable_node(DEBUG_MODE_VAR, GAME_MODE_CLASS_PATH)
    _connect(_loose_pin(as_gm, "AsBPThirdPersonGameMode", is_input=False),
             _pin(put, "self"))
    _connect(out(saved, DEBUG_MODE_VAR), _pin(put, DEBUG_MODE_VAR))
    _connect(then(as_gm), _pin(put, "execute"))
    ed.add_comment_to_nodes(
        "Debug mode as the player last left it (BP_Settings.DebugMode, on for "
        "a first run), onto the GameMode where the HUD and the weapon read it.",
        [gm, as_gm, settings, saved, put])
    return (then(put), out(as_gm, "CastFailed"))


# ─── Event BeginPlay: the startup default ────────────────────────────────────

def _author_begin_play(ed, begin_play):
    # The UMG screens before anything else, so they exist by the first DrawHUD.
    created = author_create_screens(ed, then(begin_play))
    made = emit_apply(ed, DEFAULT_PRESET, created)
    label = PRESETS[DEFAULT_PRESET].label
    ed.add_comment_to_nodes(
        f"A player with no graphics save starts at {label}, graphics_tuning.csv's "
        f"default. Setting Quality applies it: the first Tick hands the preset's "
        f"row to {TUNER_COMPONENT} (gfx_tune_tick.py).",
        made)

    # The settings load comes BEFORE the menu decision: the pause waits
    # MENU_SETTLE_S behind a Delay, and anything chained after it would wait
    # too -- or never run at all if NEW GAME got in first.
    #
    # The settings only have to exist by the first DrawHUD, and putting disk
    # access in front of the preset would let a failed load hide a failed
    # preset.
    loaded_tails = _author_load_settings(ed, then(made[-1]))
    loaded_tails = _author_restore_debug(ed, loaded_tails)
    # The player's own preset and Custom row, over the default set above.
    loaded_tails = author_load_graphics(ed, loaded_tails)

    # --- open paused, on the menu -------------------------------------------
    # Pausing is what makes the menu a menu. Without it the level is live
    # behind the panel: ten wanderers spawn, start running at a player who
    # cannot move, and are on top of them by the time the title is read.
    # GetCommandLine is IMPURE -- it has an Exec pin -- so it has to sit in the
    # chain. Left hanging off it the compiler prunes the node and the Contains
    # below silently reads an empty string, which means the switch would never
    # be seen and every headless run would sit on the menu. It warns, loudly,
    # and verify_graphics_menu fails on node warnings for exactly this reason.
    cmdline = _node(ed, FN_COMMAND_LINE)
    skipping = _node(ed, FN_CONTAINS)
    _connect(out(cmdline), _pin(skipping, "SearchIn"))
    _set(skipping, "Substring", SKIP_MENU_SWITCH)
    wants_menu = _node(ed, FN_NOT)
    _connect(out(skipping), _pin(wants_menu, "A"))
    shown = ed.add_branch_node()
    _connect(out(wants_menu), _pin(shown, "Condition"))
    for tail in loaded_tails:
        _connect(tail, _pin(cmdline, "execute"))
    _connect(then(cmdline), _pin(shown, "execute"))

    # Not paused on frame zero -- see MENU_SETTLE_S. And only if the player has
    # not already pressed Enter inside that window: pausing after NEW GAME
    # would freeze the game with no menu left to unpause it.
    settle = _node(ed, FN_DELAY)
    _set(settle, "Duration", MENU_SETTLE_S)
    # The menu's rows are served on Tick, which a paused world stops.
    _connect(author_title_ticks(ed, [then(shown)]), _pin(settle, "execute"))
    started = ed.add_get_member_variable_node(GAME_STARTED_VAR)
    still_on_menu = ed.add_branch_node()
    _connect(out(started, GAME_STARTED_VAR), _pin(still_on_menu, "Condition"))
    _connect(then(settle), _pin(still_on_menu, "execute"))
    hold = _node(ed, FN_SET_PAUSED)
    _set(hold, "bPaused", "true")
    _connect(else_(still_on_menu), _pin(hold, "execute"))

    # Straight into the game, for a run with nobody to press Enter.
    skip = ed.add_set_member_variable_node(GAME_STARTED_VAR)
    _set(skip, GAME_STARTED_VAR, "true")
    _connect(else_(shown), _pin(skip, "execute"))

    ed.add_comment_to_nodes(
        f"Open on the menu, paused {MENU_SETTLE_S}s in. {GAME_STARTED_VAR} "
        f"defaults to false, so ReceiveDrawHUD holds the menu open over a "
        f"hidden HUD until the player starts -- see author_title. Pausing "
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
    # One PlayerController read feeds every key test and every console command.
    pc = _node(ed, FN_GET_OWNING_PC)
    pc_out = out(pc)

    # First the open menu holds the player still (menu_still.py). Then, only
    # with a game in play: save and exit, the profile load and the death wipe
    # (save_exit.py), and the loot window (loot_tick.py): the body in reach,
    # its keys, a take. The title's Tick skips them (menu_main.py).
    stilled = author_menu_still(ed, pc_out, [then(tick)])
    in_play, on_title = author_in_play(ed, stilled)
    saved = author_save_exit_tick(ed, pc_out, [in_play])
    looted = author_loot_tick(ed, pc_out, saved)
    # The I panel (wear_tick.py): what the player wears, and a take-off.
    looted = author_wear_tick(ed, pc_out, looted)
    # Then the menu's tuning tabs (tune_tick.py and its four siblings).
    # The graphics one also hands the picked preset to the tuner component.
    tuned = author_tune_tick(ed, pc_out, [*looted, on_title])
    tuned = author_monster_tune_tick(ed, pc_out, tuned)
    tuned = author_world_tune_tick(ed, pc_out, tuned)
    tuned = author_gfx_tune_tick(ed, pc_out, tuned)
    tuned = author_player_tune_tick(ed, pc_out, tuned)
    # Then the menu's own rows (new game or resume, settings, exit game) and M.
    toggled = author_main_rows_tick(ed, pc_out, tuned)

    # --- the menu's debug row, gated on the menu being open -----------------
    gate_get = ed.add_get_member_variable_node("MenuOpen")
    gate = ed.add_branch_node()
    _connect(out(gate_get, "MenuOpen"), _pin(gate, "Condition"))
    for tail in toggled:
        _connect(tail, _pin(gate, "execute"))

    # --- the debug row toggles debug mode -----------------------------------
    # Written to the GameMode rather than to this HUD: the pellet tracers are
    # drawn by BP_WeaponComponent, which can reach a GameMode and cannot reach
    # a HUD variable.  The row has no key: Enter on it or a click raises
    # PauseClick, like every other row of the panel.
    br_d = ed.add_branch_node()
    d_taken = []
    _connect(pause_row_taken(ed, DEBUG_ACTION, d_taken), _pin(br_d, "Condition"))
    _connect(then(gate), _pin(br_d, "execute"))

    gm = _node(ed, FN_GET_GAME_MODE)
    as_gm = _palette(ed, NODE_CAST_GAME_MODE)
    _connect(out(gm), _pin(as_gm, "Object"))
    _connect(then(br_d), _pin(as_gm, "execute"))
    gm_out = _loose_pin(as_gm, "AsBPThirdPersonGameMode", is_input=False)

    was_on = ed.add_get_member_variable_node(DEBUG_MODE_VAR, GAME_MODE_CLASS_PATH)
    _connect(gm_out, _pin(was_on, "self"))
    flip = _node(ed, FN_NOT)
    _connect(out(was_on, DEBUG_MODE_VAR), _pin(flip, "A"))
    set_dbg = ed.add_set_member_variable_node(DEBUG_MODE_VAR, GAME_MODE_CLASS_PATH)
    _connect(gm_out, _pin(set_dbg, "self"))
    _connect(out(flip), _pin(set_dbg, DEBUG_MODE_VAR))
    _connect(then(as_gm), _pin(set_dbg, "execute"))

    # ...and into the save, written on the spot like every other setting.
    settings = ed.add_get_member_variable_node("Settings")
    settings_out = out(settings, "Settings")
    keep_dbg = ed.add_set_member_variable_node(DEBUG_MODE_VAR, SETTINGS_CLASS_PATH)
    _connect(settings_out, _pin(keep_dbg, "self"))
    _connect(out(flip), _pin(keep_dbg, DEBUG_MODE_VAR))
    _connect(then(set_dbg), _pin(keep_dbg, "execute"))
    _, writer = _emit_save(ed, settings_out, then(keep_dbg))

    ed.add_comment_to_nodes(
        "The panel's debug row -> debug mode, held on the GameMode so the weapon "
        "component can read it too, and saved to BP_Settings so it survives a "
        "restart.  It turns on the pellet tracers and the "
        "wanderers' numbers.",
        d_taken + [br_d, gm, as_gm, was_on, flip, set_dbg, settings, keep_dbg,
         writer])


# ─── The health readout ──────────────────────────────────────────────────────

def _vec(ed, x, y, z):
    """A constant vector as a node, because struct pins reject text defaults.

    set_pin_value on an FVector pin returns False for every format and leaves
    the pin empty, which the compiler reads as the zero vector.
    """
    n = _node(ed, FN_MAKE_VECTOR)
    for axis, value in (("X", x), ("Y", y), ("Z", z)):
        _set(n, axis, float(value))
    return out(n)


def _author_npc_bars(ed, in_execs):
    """A health bar floating over every NPC, in screen space.

    Drawn on the HUD canvas rather than as a widget component on the NPC: UMG
    layout cannot be authored from Python at all (WidgetTree is protected), and
    a 3D bar would need a material and a facing update. Project() turns the
    world point above each head into canvas pixels, which is all DrawRect needs.
    """
    every = _node(ed, FN_ALL_ACTORS)
    _pin(every, "ActorClass").set_pin_value(NPC_CLASS_PATH)
    for e in in_execs:
        _connect(e, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    loop
    _connect(out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(then(every), _loose_pin(loop, "Exec"))
    npc = _loose_pin(loop, "ArrayElement", is_input=False)

    comp = _node(ed, FN_GET_COMP)
    _connect(npc, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _palette(ed, NODE_CAST_HEALTH)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    health = ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(health, "self"))
    max_health = ed.add_get_member_variable_node("MaxHealth", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(max_health, "self"))

    where = _node(ed, FN_ACTOR_LOC)
    _connect(npc, _pin(where, "self"))
    above = _node(ed, FN_ADD_VV)
    _connect(out(where), _pin(above, "A"))
    _connect(_vec(ed, 0.0, 0.0, NPC_BAR_Z), _pin(above, "B"))

    proj = _node(ed, FN_PROJECT)
    _connect(out(above), _pin(proj, "Location"))
    parts = _node(ed, FN_BREAK_VECTOR)
    _connect(out(proj), _loose_pin(parts, "InVec"))

    # Project returns the depth in Z, and it is negative for anything behind the
    # camera -- without this test those NPCs get their bars mirrored onto the
    # screen as if they were in front.
    in_front = _node(ed, FN_GREATER_FF)
    _connect(out(parts, "Z"), _pin(in_front, "A"))
    _set(in_front, "B", 0.0)

    # ...and hurt recently. A bar over every wanderer at all times is most of
    # the screen once the pack arrives, and it is only ever *read* just after a
    # shot lands; the rest of the time it is clutter over the forest the player
    # is aiming into. LastDamageTime is stamped by the pellet that did the
    # damage (see _author_impact), and defaults far enough in the past that
    # nothing is showing a bar at level start.
    hurt_at = ed.add_get_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(hurt_at, "self"))
    now = _node(ed, FN_TIME_SECONDS)
    since = _node(ed, FN_SUB_FF)
    _connect(out(now), _pin(since, "A"))
    _connect(out(hurt_at, LAST_DAMAGE_VAR), _pin(since, "B"))
    recent = _node(ed, FN_LE_FF)
    _connect(out(since), _pin(recent, "A"))
    _set(recent, "B", NPC_BAR_SECONDS)

    # ...and still alive. A killed wanderer now lies where it fell for a minute
    # (see CORPSE_SECONDS), and it was shot a moment ago by definition, so
    # without this every corpse wears an empty bar for its first five seconds.
    gone = ed.add_get_member_variable_node("Dead", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(gone, "self"))
    alive = _node(ed, FN_NOT)
    _connect(out(gone, "Dead"), _pin(alive, "A"))

    # Safe to fold into one AND: every half is arithmetic on values already
    # read, so pulling them costs two comparisons and has no side effect. (The
    # NPC melee gate could not do this -- there, one half of the AND dragged a
    # whole location chain behind it. See the pure-node note in CLAUDE.md.)
    breathing = _node(ed, FN_AND)
    _connect(out(recent), _pin(breathing, "A"))
    _connect(out(alive), _pin(breathing, "B"))

    showing = _node(ed, FN_AND)
    _connect(out(in_front), _pin(showing, "A"))
    _connect(out(breathing), _pin(showing, "B"))

    visible = ed.add_branch_node()
    _connect(out(showing), _pin(visible, "Condition"))
    _connect(then(cast), _pin(visible, "execute"))

    left = _node(ed, FN_SUB_FF)
    _connect(out(parts, "X"), _pin(left, "A"))
    _set(left, "B", NPC_BAR[0] / 2.0)          # centre the bar on the head
    left_out = out(left)
    top_out = out(parts, "Y")

    frac = _node(ed, FN_DIV_FF)
    _connect(out(health, "Health"), _pin(frac, "A"))
    _connect(out(max_health, "MaxHealth"), _pin(frac, "B"))
    fill_w = _node(ed, FN_MUL_FF)
    _connect(out(frac), _pin(fill_w, "A"))
    _set(fill_w, "B", NPC_BAR[0])

    back = _draw_texture(ed, "T_UI_BarTrack")
    _set(back, "ScreenW", NPC_BAR[0])
    _set(back, "ScreenH", NPC_BAR[1])
    _connect(left_out, _pin(back, "ScreenX"))
    _connect(top_out, _pin(back, "ScreenY"))
    _connect(then(visible), _pin(back, "execute"))

    fill = _draw_texture(ed, "T_UI_Bar", tint=COL_NPC_FILL)
    _set(fill, "ScreenW", NPC_BAR[0])
    _set(fill, "ScreenH", NPC_BAR[1])
    _connect(left_out, _pin(fill, "ScreenX"))
    _connect(top_out, _pin(fill, "ScreenY"))
    _connect(out(fill_w), _pin(fill, "ScreenW"))
    _connect(then(back), _pin(fill, "execute"))

    # The wanderer's number, just left of its bar. Read off the NPC's own health
    # component rather than kept in a list here: the HUD never has to be told
    # that a wanderer died and another took its place.
    nid = ed.add_get_member_variable_node(NPC_ID_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(nid, "self"))
    nid_str = _node(ed, FN_INT_TO_STR)
    _connect(out(nid, NPC_ID_VAR), _pin(nid_str, "InInt"))

    id_x = _node(ed, FN_SUB_FF)
    _connect(left_out, _pin(id_x, "A"))
    _set(id_x, "B", NPC_ID_WIDTH + NPC_ID_GAP)
    id_y = _node(ed, FN_SUB_FF)
    _connect(top_out, _pin(id_y, "A"))
    _set(id_y, "B", NPC_ID_RISE)

    # ...and only in debug mode. The number is how the log's "[NPC-SPAWN] #7"
    # is matched to a body on screen, which is a thing a developer does and not
    # a thing the game is. DebugOn is this frame's copy of the GameMode's flag,
    # taken once in _author_draw.
    numbered = ed.add_get_member_variable_node("DebugOn")
    labelled = ed.add_branch_node()
    _connect(out(numbered, "DebugOn"), _pin(labelled, "Condition"))
    _connect(then(fill), _pin(labelled, "execute"))

    number = _node(ed, FN_DRAW_TEXT)
    _connect(out(nid_str), _pin(number, "Text"))
    _set(number, "TextColor", COL_NPC_ID)
    _set(number, "Scale", NPC_ID_SCALE)
    _connect(out(id_x), _pin(number, "ScreenX"))
    _connect(out(id_y), _pin(number, "ScreenY"))
    _connect(then(labelled), _pin(number, "execute"))

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


def _author_draw(ed):
    draw = _palette(ed, NODE_DRAW_HUD)

    # Dead or alive, before anything is drawn. The death menu replaces the HUD
    # rather than covering it, so this branch is the first thing in the frame.
    mode = _node(ed, FN_GET_GAME_MODE)
    as_mode = _palette(ed, NODE_CAST_GAME_MODE)
    _connect(out(mode), _pin(as_mode, "Object"))
    _connect(then(draw), _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    # This frame's copy of DebugMode, taken here and nowhere else.  Every
    # consumer below reads the HUD's own DebugOn instead of the GameMode's
    # variable, for one reason: the cast-failed path reaches the same drawing
    # code, and a Get with an invalid self is an "Accessed None" per wanderer
    # per frame.  Copying it once gives that path a real answer -- false -- and
    # costs one node.
    on_get = ed.add_get_member_variable_node(DEBUG_MODE_VAR, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(on_get, "self"))
    copy_dbg = ed.add_set_member_variable_node("DebugOn")
    _connect(out(on_get, DEBUG_MODE_VAR), _pin(copy_dbg, "DebugOn"))
    _connect(then(as_mode), _pin(copy_dbg, "execute"))
    no_dbg = ed.add_set_member_variable_node("DebugOn")
    _set(no_dbg, "DebugOn", "false")
    _connect(out(as_mode, "CastFailed"), _pin(no_dbg, "execute"))

    # The player's settings, onto the weapon component. Before the menu and
    # before the dead/alive test, because it is the one thing on this event
    # that has to happen on every frame in every state -- a sensitivity changed
    # on the settings screen has to be in effect the moment the world unpauses.
    # The difficulty onto the GameMode first, where there is one to write.
    to_mode = author_push_difficulty(ed, then(copy_dbg), mode_out)
    pushed = _author_push_settings(ed, (*to_mode, then(no_dbg)))

    # The FPS readout, in every state -- title, game, death -- and whether
    # debug mode is on or off. Drawn first, so every panel after it can sit on top.
    fps_out = author_fps(ed, pushed)

    # Where the mouse cursor is, before the first screen that asks (cursor.py).
    # The title, before the dead/alive test: it is neither, and goes straight
    # on to the menu.
    title, playing = author_title(ed, [author_cursor_read(ed, fps_out)])

    alive = ed.add_branch_node()
    dead_get = ed.add_get_member_variable_node(PLAYER_DEAD_VAR, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(dead_get, "self"))
    _connect(out(dead_get, PLAYER_DEAD_VAR), _pin(alive, "Condition"))
    _connect(playing, _pin(alive, "execute"))

    author_death_menu(ed, (then(alive),), mode_out)

    # A GameMode that is not BP_ThirdPersonGameMode cannot say whether the
    # player is dead, so it is treated as alive and the HUD shows as normal --
    # a missing death menu is recoverable, a missing HUD is not.
    living = author_alive(ed, (else_(alive),))

    # The stat bars and the kill counter, into WBP_HUD.
    after_hp = author_hp(ed, living)
    after_st = _author_stamina(ed, after_hp)
    after_sv = author_survival_bars(ed, after_st)
    after_kills = author_kills(ed, after_sv)

    # The wanderers' bars, still on the canvas: one per wanderer, placed by
    # projecting its head each frame. Then the inventory grid.
    after_npc = _author_npc_bars(ed, after_kills)
    after_inv = author_inventory(ed, after_npc)

    # The crosshair or scope, also on the canvas: centred off the viewport
    # and sized by the gun's cloud every frame.
    after_aim = _author_reticle(ed, after_inv)
    after_aim = author_exit_banner(ed, after_aim)
    after_aim = author_loot_window(ed, after_aim)
    after_aim = author_wear_panel(ed, after_aim)

    # Last: the menu. Every path above -- written or cast-failed -- falls
    # through to it, and so does the title; an exec input takes more than one
    # link.
    shown = author_pause_menu(ed, [*after_aim, title])
    guns = author_tune_panel(ed, shown)
    monsters = author_tune_panel(ed, guns, MONSTER_TAB)
    world = author_tune_panel(ed, monsters, WORLD_TAB)
    gfx = author_tune_panel(ed, world, GFX_TAB)
    author_tune_panel(ed, gfx, PLAYER_TAB)


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
    build_graphics_savegame()
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
        if not _assets().load_asset(path):
            raise RuntimeError(f"could not load {path} for its cast node")

    bp = _create_blueprint(HUD_BP_PATH, unreal.HUD)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{HUD_BP_PATH} has no EventGraph")

    tick = ed.find_event_node("ReceiveTick")
    outgoing = then(tick) if tick else None
    authored = bool(outgoing and outgoing.is_valid() and outgoing.list_connected_pins())

    if authored and not rebuild:
        _log(f"{HUD_BP_PATH} graph already authored — reusing")
        if not BEL.compile_blueprint(bp):
            raise RuntimeError("BP_GraphicsMenuHUD failed to compile")
        _assets().save_loaded_asset(bp)
        return bp

    if authored:
        _log("wiping the existing graph")
        ed.remove_nodes(ed.list_all_nodes())
        tick = None

    if not tick:
        # A fresh Blueprint ships disabled Tick/BeginPlay placeholders, but a
        # wiped graph has none, so put them back from the palette.
        tick = _palette(ed, NODE_TICK)

    _ensure_variables(ed, bp)
    install_tuner(bp)

    begin_play = ed.find_event_node("ReceiveBeginPlay")
    if not begin_play:
        begin_play = _palette(ed, NODE_BEGIN_PLAY)
    _author_begin_play(ed, begin_play)

    _author_tick(ed, tick)
    _author_draw(ed)

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GraphicsMenuHUD failed to compile")
    _apply_defaults(bp, {"MenuOpen": False, "DebugOn": False,
                         PAUSE_ROW_VAR: 0, MENU_STILL_VAR: False,
                         "Quality": DEFAULT_PRESET,
                         "MenuPage": PAGE_TITLE, "MenuRow": 0,
                         "Capturing": False,
                         "KeyPool": [_key(k) for k in KEY_POOL],
                         **difficulty_defaults(), **profile_defaults(),
                         **dev_guns_defaults(), **loot_defaults(), **wear_defaults(), **inv_defaults(),
                         **tune_defaults(), **monster_tune_defaults(),
                         **world_tune_defaults(), **gfx_tune_defaults(),
                         **player_tune_defaults(),
                         **cursor_defaults()})
    _assets().save_loaded_asset(bp)
    _log(f"built {HUD_BP_PATH}")
    return bp


def attach_to_game_mode(hud_bp):
    """Point the project's default game mode at the menu HUD.

    This is the only wiring step: BP_ThirdPersonGameMode is GlobalDefaultGameMode
    and no generated level overrides it, so every level picks the HUD up.
    """
    eas = _assets()
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
    eas = _assets()
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
