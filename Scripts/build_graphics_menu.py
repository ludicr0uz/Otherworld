"""
build_graphics_menu.py — Creates the in-game graphics-quality menu from Python.

Run inside the editor:
    UnrealEditor-Cmd <uproject> -ExecutePythonScript="<abs>/Scripts/build_graphics_menu.py" -NoUI -stdout

One asset is produced, plus one wiring change:

  /Game/UI/BP_GraphicsMenuHUD  (parent AHUD)  — the whole menu.

  BP_ThirdPersonGameMode.HUDClass is pointed at it.  That game mode is the
  project's GlobalDefaultGameMode (Config/DefaultEngine.ini) and no generated
  level overrides it, so this single edit puts the menu in every level.  No
  actor is placed and no level is touched, which is what keeps the menu out of
  the code-generated level pipeline entirely.

Why AHUD and not UMG: UE 5.8 does not expose UWidgetBlueprint::WidgetTree to
Python (it is a protected UPROPERTY, so get_editor_property refuses it), which
means a Widget Blueprint's *layout* cannot be authored from a script -- only
hand-built in the editor.  AHUD's canvas draw calls are ordinary BlueprintCallable
functions, so the entire menu is reachable through BlueprintGraphEditor and this
file stays the single source of truth, per the project's no-hand-editing rule.

Event graph:

  [Event BeginPlay] --> apply the startup preset (Low)
                    --> load BP_Settings --> GameMode.DebugMode =
                        Settings.DebugMode  (debug mode survives a restart)

  [Event Tick] --> [Branch: Quality != GrassQualityApplied]
                      True  --> for each actor tagged OW_Grass: SetCastShadow,
                                SetAffectDistanceFieldLighting,
                                SetAffectDynamicIndirectLighting (Ultra only)
                                --> for each tier n above Low, each actor
                                    tagged OW_GrassTier<n>:
                                    SetActorHiddenInGame(Quality < n's preset)
                                --> GrassQualityApplied = Quality
              --> [Branch: WasInputKeyJustPressed(M)]
                      True  --> [Set MenuOpen = Not MenuOpen] --,
                      False ------------------------------------+
                                                                v
                                                   [Branch: MenuOpen]
                      True --> [Branch: key "1"] True --> apply Low    --.
                                     | False                             |
                               [Branch: key "2"] True --> apply Medium --+
                                     | False                             |
                               [Branch: key "3"] True --> apply High   --+
                                     | False                             |
                               [Branch: key "4"] True --> apply Ultra  --'

    "apply <preset>" = Set Quality -> GetGameUserSettings ->
                       SetOverallScalabilityLevel -> ApplyNonResolutionSettings ->
                       ConsoleCommand r.ShadowQuality -> ConsoleCommand r.ScreenPercentage
    (graphics_menu/presets.py owns both fragments and the preset table.)

  Every wanderer's bar carries its spawn number (read off its own
  BP_HealthComponent.NpcId), so what is on screen can be matched to the
  [NPC-SPAWN] lines in the log.

  [Event ReceiveDrawHUD] --> GetPlayerPawn -> GetComponentByClass(Health)
                             --> [Cast to BP_HealthComponent]
                                   ok --> DrawRect(bar back) -> DrawRect(bar
                                          fill, width = Health/MaxHealth * W)
                                          -> DrawText("HP") -> DrawText(Health)
                                   failed ------------------------------------,
                             --> [Branch: MenuOpen]                           |
                                   True --> DrawRect(panel) --> DrawText x5 <-'
                                            (the caret's ScreenY is computed
                                             from Quality, so it tracks the
                                             selection)

The health readout draws every frame; the quality panel only while MenuOpen.
Health is read off BP_HealthComponent (built by build_weapons_and_combat.py)
rather than off the character class, so the HUD does not care which pawn is
possessed -- anything carrying the component displays.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# BP_Settings' asset path. The settings screen's own contract with the combat
# package (BIND_VARS, the sensitivity limits) lives in graphics_menu/settings_rows.py.
from combat import paths as combat_paths                           # noqa: E402
# The presets, the chain that applies one and the grass-lighting Tick prologue
# live in graphics_menu/presets.py; see there for why each preset is what it is.
from graphics_menu.presets import (                                # noqa: E402
    DEFAULT_PRESET, GRASS_APPLIED_DEFAULT, GRASS_APPLIED_VAR, PRESET_KEYS,
    PRESETS, author_grass_sync, console_commands, emit_apply)
from forest_generator.grass_cells import GRASS_TIERS                 # noqa: E402
# The FPS readout, one of the debug-mode overlays; see graphics_menu/fps.py.
from graphics_menu.fps import author_fps, declare_fps_vars          # noqa: E402
# The art, font and panel palette every page draws with.
from graphics_menu.canvas import (                                 # noqa: E402
    COL_CARET, COL_MAIN_HINT, COL_ROW, COL_TITLE, UI_FONT, _draw_texture)
# Up/Down/accept, shared by the title page and the settings page.
from graphics_menu.menu_nav import (                               # noqa: E402
    START_KEYS, _emit_accept, _emit_row_nav)
# The settings screen: constants, the page and its push, the save.
from graphics_menu.settings_rows import (                          # noqa: E402
    BIND_LABELS, BIND_VARS, KEY_POOL, PAGE_SETTINGS, PAGE_TITLE,
    SETTINGS_CLASS_PATH, SETTINGS_SLOT, SETTINGS_USER_INDEX)
from graphics_menu.settings_input import _emit_save                # noqa: E402
# The stamina bar, centred under the inventory strip.
from graphics_menu.stamina_bar import (                             # noqa: E402
    ST_BOTTOM, ST_H, _author_stamina)
# Hunger, thirst and temperature under the HP bar, and the debuff names.
from graphics_menu.survival_bars import author_survival_bars       # noqa: E402
# The crosshair, sized by the held gun's accuracy cloud, and the scope.
from graphics_menu.reticle import _author_reticle                  # noqa: E402
# The one inventory size: the weapon component refuses a pick-up past it, and
# the strip draws exactly that many slots.
from combat.tuning import INVENTORY_SIZE                            # noqa: E402
from graphics_menu.settings_page import (                          # noqa: E402
    _author_push_settings, _author_settings_page)
from graphics_menu.difficulty import (                             # noqa: E402
    author_push_difficulty, declare_difficulty_vars, difficulty_defaults)
# Save and exit, the saved profile and losing it on death; see save_exit.py.
from graphics_menu.profile_asset import build_profile_savegame     # noqa: E402
from graphics_menu.profile_consts import PROFILE_BP_PATH           # noqa: E402
from graphics_menu.profile_draw import (                           # noqa: E402
    author_exit_banner, author_exit_row)
from graphics_menu.save_exit import (                              # noqa: E402
    author_save_exit_tick, declare_profile_vars, profile_defaults)
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
# loaded, and the D toggle writes it back and saves on the spot.
DEBUG_KEY = "D"
DEBUG_MODE_VAR = "DebugMode"

# Where the player's health lives.  Built by build_weapons_and_combat.py; the
# HUD degrades to drawing nothing if the pawn has no such component.
HEALTH_CLASS_PATH = "/Game/Weapons/BP_HealthComponent.BP_HealthComponent_C"

# ─── Panel geometry (HUD canvas pixels, top-left origin) ─────────────────────
# Fixed coordinates rather than viewport-relative ones: centring would need the
# DrawHUD event's SizeX/SizeY through int->float conversion nodes for every
# coordinate, which triples the node count of the draw graph to move a box that
# is legible where it is.
# The health readout owns the top-left corner because it is always on screen;
# the quality panel was moved down to open underneath it rather than across it.
HP_LABEL_POS = (62.0, 30.0)
HP_LABEL_SCALE = 1.5
HP_BAR = (60.0, 62.0, 420.0, 30.0)   # x, y, w, h -- w is the *full* bar
HP_NUM_POS = (500.0, 58.0)
HP_NUM_SCALE = 2.4

PANEL = (60.0, 130.0, 600.0, 438.0)   # x, y, w, h
TITLE_POS = (92.0, 158.0)
TITLE_SCALE = 2.2
ROW_X = 150.0
ROW_Y0 = 238.0
ROW_STEP = 46.0
ROW_SCALE = 2.0
DEBUG_ROW_Y = ROW_Y0 + len(PRESETS) * ROW_STEP   # one row below the presets
CARET_X = 112.0
EXIT_ROW_Y = DEBUG_ROW_Y + ROW_STEP                # save and exit, under debug
HINT_POS = (92.0, EXIT_ROW_Y + 52.0)
HINT_SCALE = 1.5

COL_PANEL = "(R=0.020000,G=0.025000,B=0.035000,A=0.780000)"
COL_HINT = "(R=0.480000,G=0.510000,B=0.560000,A=1.000000)"
COL_HP_BACK = "(R=0.030000,G=0.030000,B=0.035000,A=0.800000)"
COL_HP_FILL = "(R=0.750000,G=0.130000,B=0.120000,A=0.950000)"
COL_HP_LABEL = "(R=0.620000,G=0.650000,B=0.700000,A=1.000000)"
COL_HP_NUM = "(R=0.960000,G=0.960000,B=0.970000,A=1.000000)"

# --- the kill counter, top right ---------------------------------------------
# Under the debug-mode FPS readout (graphics_menu/fps.py), which owns the very
# top of that corner. Right-anchored off the viewport width rather than placed at a fixed
# x, for the same reason the inventory strip is centred that way.
KILL_RIGHT_MARGIN = 150.0
KILL_TOP = 92.0
KILL_SCALE = 2.2
COL_KILL = "(R=0.960000,G=0.860000,B=0.450000,A=0.950000)"

# --- the death menu ----------------------------------------------------------
# R, not Enter or Space: Enter opens the editor console in PIE and Space is the
# jump key, which is still bound while the pawn stands dead.
RESTART_KEY = "R"
# ── The main menu ────────────────────────────────────────────────────────────
#
# Shown the moment the level loads, with the game PAUSED, and replaced by the
# HUD when the player starts. Nothing about it is a new mechanism: it is the
# death menu's shape, and it works for the same reason -- it is drawn AND
# polled inside ReceiveDrawHUD rather than on Tick, because Event Tick does not
# run while the game is paused but PostRender is called by the renderer every
# frame regardless, and APlayerController sets bTickEvenWhenPaused so its
# PlayerInput is still updated. A key polled on Tick here would simply never be
# seen. (That is not a guess -- it is why the death menu's [R] is where it is.)
#
# Enter and Space accept. The left mouse button used to be a third, on the
# argument that a button you cannot click is a strange button -- it is gone now
# that the panel has two rows, because with no cursor and no hit test a click
# cannot say WHICH row it means. Keyboard navigation is the whole of the menu
# instead: Up/Down move the caret, Enter takes the row.
MENU_PANEL = (600.0, 346.0)
GAME_TITLE = "OTHERWORLD"
GAME_SUBTITLE = "a night in the forest"
START_LABEL = "NEW GAME"
START_BUTTON = (300.0, 64.0)
MAIN_TITLE_SCALE = 3.4
MAIN_SUB_SCALE = 1.4
MAIN_START_SCALE = 2.2
MAIN_HINT_SCALE = 1.2
# Where the two rows sit under the subtitle, and where the lit plate sits
# behind whichever one the caret is on. The plate is 16 px taller than the row
# step so it reads as a button around the text rather than as a highlight of it.
MAIN_ROW0_OFF = 192.0
MAIN_ROW_STEP = 52.0
MAIN_PLATE_OFF = 176.0
MAIN_HINT_OFF = MAIN_ROW0_OFF + len(("NEW GAME", "SETTINGS")) * MAIN_ROW_STEP + 26.0
COL_MAIN_TITLE = "(R=0.920000,G=0.945000,B=1.000000,A=1.000000)"
COL_MAIN_SUB = "(R=0.520000,G=0.560000,B=0.630000,A=1.000000)"
COL_MAIN_START = "(R=1.000000,G=0.870000,B=0.450000,A=1.000000)"
GAME_STARTED_VAR = "GameStarted"
# How long the world runs before BeginPlay pauses it under the menu. Pausing on
# frame zero froze the view INSIDE the player: LevelTick skips
# UpdateCameraManager while paused (unless the controller full-ticks), so the
# camera never left the spawn point for the boom, and the mesh never evaluated
# its anim graph, so its reference-pose arms filled the screen from within.
# A quarter second lets both settle; the wanderers are 75 m away and cannot
# close that in the time.
MENU_SETTLE_S = 0.25


MENU_ROWS = (START_LABEL, "SETTINGS")




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

DEATH_PANEL = (560.0, 300.0)      # width, height; centred on the viewport
COL_DEATH_PANEL = "(R=0.040000,G=0.010000,B=0.012000,A=0.880000)"
COL_DEATH_TITLE = "(R=0.880000,G=0.220000,B=0.180000,A=1.000000)"
COL_DEATH_TEXT = "(R=0.900000,G=0.900000,B=0.920000,A=1.000000)"
COL_DEATH_HINT = "(R=0.700000,G=0.720000,B=0.760000,A=1.000000)"
DEATH_TITLE_SCALE = 3.4
DEATH_SCORE_SCALE = 2.2
DEATH_HINT_SCALE = 1.6

# --- NPC health bars, drawn in the world above each wanderer ------------------
NPC_CLASS_PATH = "/Game/Forest/NPC/BP_ForestWanderer.BP_ForestWanderer_C"
NPC_BAR_Z = 110.0          # cm above the actor's origin, just over its head
NPC_BAR = (90.0, 10.0)     # width, height in pixels
COL_NPC_BACK = "(R=0.020000,G=0.020000,B=0.025000,A=0.750000)"
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

# --- inventory strip, bottom centre ------------------------------------------
GAME_MODE_CLASS_PATH = ("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
                        ".BP_ThirdPersonGameMode_C")
KILL_COUNT_VAR = "NpcKillCount"
PLAYER_DEAD_VAR = "PlayerDead"
WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
ITEM_CLASS_PATH = "/Game/Weapons/BP_WeaponItem.BP_WeaponItem_C"
# Two rows of five rather than one row of ten. The slots were 120 x 84, sized
# for icons once reported unreadable; they were then asked to be about 30%
# smaller, so every slot measurement below is the old one x 0.7.
INVENTORY_COLUMNS = 5
INVENTORY_ROWS = -(-INVENTORY_SIZE // INVENTORY_COLUMNS)
SLOT_W = 84.0
SLOT_H = 59.0
SLOT_GAP = 7.0
# The stamina bar sits under the strip (graphics_menu/stamina_bar.py), so the
# strip stands on it: this many px between the strip and the bottom edge.
SLOT_OVER_STAMINA = 12.0
SLOT_BOTTOM = ST_BOTTOM + ST_H + SLOT_OVER_STAMINA

# The equipped weapon's name, drawn ONCE above the strip rather than five times
# inside it.
#
# It used to be a label in every slot, at 1.3x, sharing a 104 px row with the
# ammunition count. That was the wrong trade twice over: four of the five names
# on screen name a weapon the player is not holding, and the one that matters
# was the same size as the four that do not. Above the strip it can be big
# enough to read at a glance, and taking it out of the slot is what leaves room
# for an ammunition count that can also be read at a glance.
EQUIPPED_NAME_SCALE = 1.7
EQUIPPED_NAME_ABOVE = 12.0   # px between the strip's top edge and the baseline
COL_EQUIPPED_NAME = "(R=1.000000,G=0.870000,B=0.450000,A=1.000000)"
# The ammunition readout, in the slot's own top-right corner: "3 / 15" is
# rounds in the magazine and rounds in reserve.  Drawn only for weapons whose
# UsesAmmo is true, so the pistol's slot stays empty rather than claiming an
# infinity nobody has to manage.
# Bigger, and moved off the icon. At 1.2x in the top-right corner the count was
# drawn ON TOP of the silhouette, which is both hard to read and the reason the
# silhouette looked cluttered. It now has the slot's lower row to itself, and
# is right-aligned from a real measurement (HUD::GetTextSize) rather than from
# a guessed character width -- "5/15" and "30/90" are different widths and a
# fixed offset cannot be right for both. Scaled x 0.7 with the slot.
SLOT_AMMO_SCALE = 1.2
SLOT_AMMO_RIGHT = 6.0      # px from the slot's right edge to the text's RIGHT
SLOT_AMMO_BASELINE = 38.0  # px down from the slot's top edge
COL_SLOT_AMMO = "(R=0.960000,G=0.860000,B=0.450000,A=0.950000)"
COL_SLOT_BACK = "(R=0.020000,G=0.025000,B=0.035000,A=0.700000)"
COL_SLOT_NAME = "(R=0.960000,G=0.960000,B=0.970000,A=1.000000)"
COL_SLOT_MARK = "(R=1.000000,G=0.820000,B=0.320000,A=1.000000)"

# The sniper's scope is graphics_menu/scope.py (SCOPE_TEX is imported below).

# ─── Function paths for the graph nodes ──────────────────────────────────────

FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_CONSOLE = "/Script/Engine.KismetSystemLibrary.ExecuteConsoleCommand"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_CONV_INT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_DRAW_RECT = "/Script/Engine.HUD.DrawRect"
FN_DRAW_TEXTURE = "/Script/Engine.HUD.DrawTexture"
FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_ROUND = "/Script/Engine.KismetMathLibrary.Round"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_ALL_ACTORS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_ADD_VV = "/Script/Engine.KismetMathLibrary.Add_VectorVector"
FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
FN_BREAK_VECTOR = "/Script/Engine.KismetMathLibrary.BreakVector"
FN_BREAK_V2D = "/Script/Engine.KismetMathLibrary.BreakVector2D"
FN_PROJECT = "/Script/Engine.HUD.Project"
FN_GREATER = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
# How wide a string will be drawn. A HUD method, so its self pin is this HUD;
# it must be given the same Font and Scale as the DrawText it is measuring for,
# or it measures a different string from the one that appears.
FN_TEXT_SIZE = "/Script/Engine.HUD.GetTextSize"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_COMMAND_LINE = "/Script/Engine.KismetSystemLibrary.GetCommandLine"
FN_CONTAINS = "/Script/Engine.KismetStringLibrary.Contains"
FN_VIEWPORT = "/Script/UMG.WidgetLayoutLibrary.GetViewportSize"
FN_SELECT_COLOR = "/Script/Engine.KismetMathLibrary.SelectColor"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_LE = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"
FN_OPEN_LEVEL = "/Script/Engine.GameplayStatics.OpenLevel"
FN_LEVEL_NAME = "/Script/Engine.GameplayStatics.GetCurrentLevelName"
FN_SAVE_EXISTS = "/Script/Engine.GameplayStatics.DoesSaveGameExist"
FN_LOAD_SAVE = "/Script/Engine.GameplayStatics.LoadGameFromSlot"
FN_CREATE_SAVE = "/Script/Engine.GameplayStatics.CreateSaveGameObject"
FN_WRITE_SAVE = "/Script/Engine.GameplayStatics.SaveGameToSlot"
# Key_GetName does not exist in 5.8; the display name is the only readable
# spelling of an FKey, and it comes back as Text rather than as a String.
FN_KEY_DISPLAY = "/Script/Engine.KismetInputLibrary.Key_GetDisplayName"
FN_TEXT_TO_STR = "/Script/Engine.KismetTextLibrary.Conv_TextToString"
FN_FLOAT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_DoubleToString"
FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_ARR_SET = "/Script/Engine.KismetArrayLibrary.Array_Set"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_ARR_CLEAR = "/Script/Engine.KismetArrayLibrary.Array_Clear"
FN_NEQ_II = "/Script/Engine.KismetMathLibrary.NotEqual_IntInt"
FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_MOD_II = "/Script/Engine.KismetMathLibrary.Percent_IntInt"
FN_DIV_II = "/Script/Engine.KismetMathLibrary.Divide_IntInt"
FN_MIN_II = "/Script/Engine.KismetMathLibrary.Min"
FN_MAX_II = "/Script/Engine.KismetMathLibrary.Max"
FN_FCLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_SELECT_FLOAT = "/Script/Engine.KismetMathLibrary.SelectFloat"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
# MakeColor returns a LinearColor, which is the only way to hand DrawRect and
# DrawTexture a colour whose alpha is computed: a struct pin rejects every
# literal format there is.
FN_MAKE_COLOR = "/Script/Engine.KismetMathLibrary.MakeColor"
FN_FMAX = "/Script/Engine.KismetMathLibrary.FMax"

# The DrawHUD event is not one of the placeholder nodes a fresh Blueprint ships
# with (BeginPlay and Tick are), so it has to be created from the palette.
NODE_DRAW_HUD = "AddEvent|EventReceiveDrawHUD"
NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"
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
UI_TEX_SIZE = {
    "T_UI_Panel": (600, 346),
    "T_UI_PanelDeath": (560, 300),
    "T_UI_Slot": (120, 84),
    "T_UI_SlotActive": (120, 84),
    "T_UI_SlotFrame": (120, 84),
    "T_UI_Bar": (240, 32),
    "T_UI_BarTrack": (240, 32),
    "T_UI_Scope": (1024, 1024),
}
ICON_TEX_SIZE = (128, 64)

# The weapon icon inside its slot: nearly the full width, on the upper line so
# the ammunition count has the lower one.
#
# 112 x 50, up from 88 x 44. That is not a tweak -- the icons were reported as
# unreadable ("lots of small dots"), and while the drawings themselves were
# redrawn for it (see build_ui_art.py) the other half of the fix is simply
# giving them more pixels. A weapon silhouette at 88 px wide has about 40 px of
# usable length once the margins are off it, and no silhouette survives that.
# Since shrunk with the slot, by 30%, to 78 x 35 at the player's request.
SLOT_ICON_W = 78.0
SLOT_ICON_H = 35.0
SLOT_ICON_TOP = 2.0


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
                                # This frame's copy of the GameMode's
                                # DebugMode.  Taken once at the top of DrawHUD.
                                ("DebugOn", "bool", "false"),
                                # False until the player picks NEW GAME.
                                # BeginPlay pauses the world alongside it.
                                (GAME_STARTED_VAR, "bool", "false"),
                                ("Quality", "int", str(DEFAULT_PRESET)),
                                # The Quality the grass cells were last lit
                                # for -- see presets.author_grass_sync.
                                (GRASS_APPLIED_VAR, "int",
                                 str(GRASS_APPLIED_DEFAULT)),
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
                BEL.get_struct_type(unreal.Key.static_struct()))),
            # The row labels, so the seven bind rows are ONE draw inside the
            # loop over Binds rather than seven pairs of DrawTexts with their
            # y positions written out by hand.
            ("BindLabels", BEL.get_array_type(
                BEL.get_basic_type_by_name("string")))):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, pin_type):
            raise RuntimeError(f"could not declare member variable {name}")
    declare_fps_vars(ed)
    declare_difficulty_vars(ed)
    declare_profile_vars(ed)


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
    made = emit_apply(ed, DEFAULT_PRESET, origin.x + 320, origin.y,
                       BEL.find_then_pin(begin_play))
    label = PRESETS[DEFAULT_PRESET].label
    ed.add_comment_to_nodes(
        f"Every session starts at {label}.  This has to *apply* the preset, not "
        f"just point the caret at it: otherwise the panel would claim {label} "
        "while the engine ran at whatever scalability it happened to boot with.",
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
    _connect(_pin(was_m, "ReturnValue", is_input=False), _pin(br_m, "Condition"))
    # Grass lighting catches up with Quality first, so a preset picked on the
    # previous frame is on the grass before anything else runs this one.
    # Then save and exit, the profile load and the death wipe (save_exit.py).
    synced = author_grass_sync(ed, x0, y0 - 1100, BEL.find_then_pin(tick))
    for tail in author_save_exit_tick(ed, pc_out, synced, x0, y0 - 4000):
        _connect(tail, _pin(br_m, "execute"))

    get_open = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 560, y0 + 200)
    not_open = _at(_node(ed, FN_NOT), x0 + 740, y0 + 200)
    _connect(_pin(get_open, "MenuOpen", is_input=False), _pin(not_open, "A"))

    set_open = _at(ed.add_set_member_variable_node("MenuOpen"), x0 + 900, y0)
    _connect(_pin(not_open, "ReturnValue", is_input=False), _pin(set_open, "MenuOpen"))
    _connect(BEL.find_then_pin(br_m), _pin(set_open, "execute"))

    ed.add_comment_to_nodes(
        f"{MENU_KEY} toggles the menu.  Polled on Tick rather than bound as an "
        "input action: an FInputActionValue binding would need an IA asset and "
        "an IMC entry, and neither is authorable from Python.",
        [was_m, br_m, get_open, not_open, set_open])

    # --- the preset keys, gated on the menu being open ----------------------
    gate_get = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 1120, y0 + 200)
    gate = _at(ed.add_branch_node(), x0 + 1280, y0)
    _connect(_pin(gate_get, "MenuOpen", is_input=False), _pin(gate, "Condition"))
    # Both arms of the toggle fall through to the gate; an exec input accepts
    # more than one link, so no Sequence node is needed.
    _connect(BEL.find_then_pin(set_open), _pin(gate, "execute"))
    _connect(_pin(br_m, "else", is_input=False), _pin(gate, "execute"))

    flow = BEL.find_then_pin(gate)
    for i, preset in enumerate(PRESETS):
        bx = x0 + 1500
        by = y0 + i * 420

        was = _at(_node(ed, FN_WAS_PRESSED), bx, by + 140)
        _connect(pc_out, _pin(was, "self"))
        _set(was, "Key", PRESET_KEYS[i])

        br = _at(ed.add_branch_node(), bx + 300, by)
        _connect(_pin(was, "ReturnValue", is_input=False), _pin(br, "Condition"))
        _connect(flow, _pin(br, "execute"))

        applied = emit_apply(ed, i, bx + 500, by, BEL.find_then_pin(br))

        ed.add_comment_to_nodes(
            f"{PRESET_KEYS[i]} -> {preset.label}: scalability {preset.level}, "
            f"{', '.join(console_commands(preset))}, grass lighting "
            f"{'on' if preset.grass_lights else 'off'}, grass tiers "
            f"{', '.join(str(n) for n, t in enumerate(GRASS_TIERS) if t.min_preset <= i)}.",
            [was, br] + applied)

        # An unmatched key falls through to the next test.
        flow = _pin(br, "else", is_input=False)

    # --- D toggles debug mode -----------------------------------------------
    # Written to the GameMode rather than to this HUD: the pellet tracers are
    # drawn by BP_WeaponComponent, which can reach a GameMode and cannot reach
    # a HUD variable.  Behind the same MenuOpen gate as the preset keys, so D
    # is a walking key everywhere except with the menu open.
    bx = x0 + 1500
    by = y0 + len(PRESETS) * 420
    was_d = _at(_node(ed, FN_WAS_PRESSED), bx, by + 140)
    _connect(pc_out, _pin(was_d, "self"))
    _set(was_d, "Key", DEBUG_KEY)
    br_d = _at(ed.add_branch_node(), bx + 300, by)
    _connect(_pin(was_d, "ReturnValue", is_input=False), _pin(br_d, "Condition"))
    _connect(flow, _pin(br_d, "execute"))

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
        f"{DEBUG_KEY} -> debug mode, held on the GameMode so the weapon "
        "component can read it too, and saved to BP_Settings so it survives a "
        "restart.  It turns on the FPS readout, the pellet tracers and the "
        "wanderers' numbers.",
        [was_d, br_d, gm, as_gm, was_on, flip, set_dbg, settings, keep_dbg,
         writer])


# ─── The health readout ──────────────────────────────────────────────────────

def _author_hp(ed, x0, y0, in_execs):
    """Draw the player's HP bar and number.  Returns the exec pins to go on from.

    Two of them: a pawn carrying no BP_HealthComponent fails the cast, and the
    graphics menu still has to draw in that case, so the failure pin is a
    continuation rather than a dead end.
    """
    pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 240)
    _set(pawn, "PlayerIndex", 0)

    comp = _at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 240)
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 500, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    health = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                 x0 + 760, y0 + 260)
    _connect(as_health, _pin(health, "self"))
    max_health = _at(ed.add_get_member_variable_node("MaxHealth", HEALTH_CLASS_PATH),
                     x0 + 760, y0 + 400)
    _connect(as_health, _pin(max_health, "self"))
    health_out = _pin(health, "Health", is_input=False)

    frac = _at(_node(ed, FN_DIV), x0 + 1000, y0 + 320)
    _connect(health_out, _pin(frac, "A"))
    _connect(_pin(max_health, "MaxHealth", is_input=False), _pin(frac, "B"))
    fill_w = _at(_node(ed, FN_MUL), x0 + 1200, y0 + 320)
    _connect(_pin(frac, "ReturnValue", is_input=False), _pin(fill_w, "A"))
    _set(fill_w, "B", HP_BAR[2])

    back = _draw_texture(ed, x0 + 760, y0, "T_UI_BarTrack")
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"), HP_BAR):
        _set(back, name, value)
    _connect(BEL.find_then_pin(cast), _pin(back, "execute"))

    # Same texture, but its width is driven rather than set: the empty part of
    # the bar is the track showing through.
    fill = _draw_texture(ed, x0 + 1000, y0, "T_UI_Bar", tint=COL_HP_FILL)
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"), HP_BAR):
        _set(fill, name, value)
    _connect(_pin(fill_w, "ReturnValue", is_input=False), _pin(fill, "ScreenW"))
    _connect(BEL.find_then_pin(back), _pin(fill, "execute"))

    label = _at(_node(ed, FN_DRAW_TEXT), x0 + 1240, y0)
    _set(label, "Text", "HP")
    _set(label, "TextColor", COL_HP_LABEL)
    _set(label, "ScreenX", HP_LABEL_POS[0])
    _set(label, "ScreenY", HP_LABEL_POS[1])
    _set(label, "Scale", HP_LABEL_SCALE)
    _set(label, "bScalePosition", "false")
    _set(label, "Font", UI_FONT)
    _connect(BEL.find_then_pin(fill), _pin(label, "execute"))

    rounded = _at(_node(ed, FN_ROUND), x0 + 1240, y0 + 320)
    _connect(health_out, _pin(rounded, "A"))
    as_text = _at(_node(ed, FN_INT_TO_STR), x0 + 1420, y0 + 320)
    _connect(_pin(rounded, "ReturnValue", is_input=False), _pin(as_text, "InInt"))

    number = _at(_node(ed, FN_DRAW_TEXT), x0 + 1480, y0)
    _set(number, "TextColor", COL_HP_NUM)
    _set(number, "ScreenX", HP_NUM_POS[0])
    _set(number, "ScreenY", HP_NUM_POS[1])
    _set(number, "Scale", HP_NUM_SCALE)
    _set(number, "bScalePosition", "false")
    _set(number, "Font", UI_FONT)
    _connect(_pin(as_text, "ReturnValue", is_input=False), _pin(number, "Text"))
    _connect(BEL.find_then_pin(label), _pin(number, "execute"))

    ed.add_comment_to_nodes(
        "Always drawn.  Health is rounded for display only -- the bar reads the "
        "unrounded value, so chip damage still moves it.",
        [pawn, comp, cast, health, max_health, frac, fill_w,
         back, fill, label, rounded, as_text, number])
    return (BEL.find_then_pin(number), _pin(cast, "CastFailed", is_input=False))


def _author_kills(ed, x0, y0, in_execs):
    """The kill counter, top right, under the debug-mode FPS readout.

    The number lives on the GameMode -- it has to outlast the wanderers that
    earn it and the player's own components, and Blueprints have no statics.
    The HUD only reads it; build_weapons_and_combat.py's death path is the one
    thing that writes it, and only for a wanderer a pellet actually killed.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    mode = keep(_at(_node(ed, FN_GET_GAME_MODE), x0, y0 + 260))
    cast = keep(_at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 260, y0))
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))

    kills = keep(_at(ed.add_get_member_variable_node(KILL_COUNT_VAR,
                                                     GAME_MODE_CLASS_PATH),
                     x0 + 520, y0 + 260))
    _connect(_loose_pin(cast, "AsBPThirdPersonGameMode", is_input=False),
             _pin(kills, "self"))
    as_text = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 760, y0 + 260))
    _connect(_pin(kills, KILL_COUNT_VAR, is_input=False), _pin(as_text, "InInt"))
    line = keep(_at(_node(ed, FN_CONCAT), x0 + 1000, y0 + 260))
    _set(line, "A", "KILLS  ")
    _connect(_pin(as_text, "ReturnValue", is_input=False), _pin(line, "B"))

    # Right-anchored: x is the viewport width less a margin, not a constant.
    size = keep(_at(_node(ed, FN_VIEWPORT), x0 + 520, y0 + 460))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 760, y0 + 460))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))
    right = keep(_at(_node(ed, FN_SUB), x0 + 1000, y0 + 460))
    _connect(_loose_pin(wh, "X", is_input=False), _pin(right, "A"))
    _set(right, "B", KILL_RIGHT_MARGIN)

    text = keep(_at(_node(ed, FN_DRAW_TEXT), x0 + 1260, y0))
    _connect(_pin(line, "ReturnValue", is_input=False), _pin(text, "Text"))
    _set(text, "TextColor", COL_KILL)
    _connect(_pin(right, "ReturnValue", is_input=False), _pin(text, "ScreenX"))
    _set(text, "ScreenY", KILL_TOP)
    _set(text, "Scale", KILL_SCALE)
    _set(text, "bScalePosition", "false")
    _set(text, "Font", UI_FONT)
    _connect(BEL.find_then_pin(cast), _pin(text, "execute"))

    ed.add_comment_to_nodes(
        f"Kills, {KILL_RIGHT_MARGIN:.0f} px in from the right edge and "
        f"{KILL_TOP:.0f} px down -- clear of the debug-mode FPS readout, "
        "which owns the very top of that corner.",
        made)
    return (BEL.find_then_pin(text), _pin(cast, "CastFailed", is_input=False))


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


def _author_inventory(ed, x0, y0, in_execs):
    """INVENTORY_SIZE slots along the bottom, INVENTORY_COLUMNS to a row,
    filled from the weapon component's Inventory. Slot i sits in column
    i % INVENTORY_COLUMNS of row i / INVENTORY_COLUMNS, top row first.

    The strip is drawn from the viewport size rather than from fixed pixels so
    it stays centred and bottom-anchored at any window size -- DrawRect works in
    canvas pixels, which change with the window.
    """
    size = _at(_node(ed, FN_VIEWPORT), x0, y0 + 700)
    wh = _at(_node(ed, FN_BREAK_V2D), x0 + 240, y0 + 700)
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))

    strip_w = INVENTORY_COLUMNS * SLOT_W + (INVENTORY_COLUMNS - 1) * SLOT_GAP
    half = _at(_node(ed, FN_MUL), x0 + 480, y0 + 700)
    _connect(_pin(wh, "X", is_input=False), _pin(half, "A"))
    _set(half, "B", 0.5)
    origin_x = _at(_node(ed, FN_SUB), x0 + 720, y0 + 700)
    _connect(_pin(half, "ReturnValue", is_input=False), _pin(origin_x, "A"))
    _set(origin_x, "B", strip_w / 2.0)
    x_out = _pin(origin_x, "ReturnValue", is_input=False)

    row_y = _at(_node(ed, FN_SUB), x0 + 720, y0 + 840)
    _connect(_pin(wh, "Y", is_input=False), _pin(row_y, "A"))
    _set(row_y, "B", INVENTORY_ROWS * SLOT_H + (INVENTORY_ROWS - 1) * SLOT_GAP
         + SLOT_BOTTOM)
    y_out = _pin(row_y, "ReturnValue", is_input=False)   # the TOP row

    made = [size, wh, half, origin_x, row_y]

    def slot_at(base, offset, px, py):
        """base + offset, as a node: a slot's column or row, off the strip's."""
        n = _at(_node(ed, FN_ADD), px, py)
        _connect(base, _pin(n, "A"))
        _set(n, "B", offset)
        made.append(n)
        return _pin(n, "ReturnValue", is_input=False)

    # Five empty slots first, so the strip is visible even with nothing carried
    # and even if the weapon component is missing entirely.
    flow = None
    for i in range(INVENTORY_SIZE):
        r = _draw_texture(ed, x0 + 1000 + i * 240, y0, "T_UI_Slot",
                          w=SLOT_W, h=SLOT_H)
        col, row = i % INVENTORY_COLUMNS, i // INVENTORY_COLUMNS
        _connect(slot_at(x_out, col * (SLOT_W + SLOT_GAP), x0 + 1000 + i * 240, y0 + 300),
                 _pin(r, "ScreenX"))
        _connect(slot_at(y_out, row * (SLOT_H + SLOT_GAP), x0 + 1000 + i * 240, y0 + 420),
                 _pin(r, "ScreenY"))
        if flow is None:
            for e in in_execs:
                _connect(e, _pin(r, "execute"))
        else:
            _connect(flow, _pin(r, "execute"))
        flow = BEL.find_then_pin(r)
        made.append(r)

    ed.add_comment_to_nodes(
        f"{INVENTORY_SIZE} empty slots, centred on the viewport and anchored "
        f"{SLOT_BOTTOM:.0f} px off the bottom.", made)

    # --- what is actually carried -------------------------------------------
    pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), x0 + 2400, y0 + 300)
    _set(pawn, "PlayerIndex", 0)
    comp = _at(_node(ed, FN_GET_COMP), x0 + 2640, y0 + 300)
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)

    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 2900, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(flow, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    inv = _at(ed.add_get_member_variable_node("Inventory", WEAPON_COMP_CLASS_PATH),
              x0 + 3160, y0 + 300)
    _connect(as_weapon, _pin(inv, "self"))
    equipped = _at(ed.add_get_member_variable_node("EquippedIndex",
                                                   WEAPON_COMP_CLASS_PATH),
                   x0 + 3160, y0 + 420)
    _connect(as_weapon, _pin(equipped, "self"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(loop, x0 + 3420, y0)
    _connect(_pin(inv, "Inventory", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(cast), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)
    index = _loose_pin(loop, "ArrayIndex", is_input=False)

    # The slot's position is index-driven, so one draw covers every slot
    # instead of unrolled copies with baked-in coordinates: column is
    # index % INVENTORY_COLUMNS, row is index / INVENTORY_COLUMNS.
    def along(op, base, pitch, py):
        cell = _at(_node(ed, op), x0 + 3460, py)
        _connect(index, _pin(cell, "A"))
        _set(cell, "B", INVENTORY_COLUMNS)
        as_float = _at(_node(ed, FN_CONV_INT), x0 + 3700, py)
        _connect(_pin(cell, "ReturnValue", is_input=False), _pin(as_float, "InInt"))
        step = _at(_node(ed, FN_MUL), x0 + 3940, py)
        _connect(_pin(as_float, "ReturnValue", is_input=False), _pin(step, "A"))
        _set(step, "B", pitch)
        at = _at(_node(ed, FN_ADD), x0 + 4180, py)
        _connect(base, _pin(at, "A"))
        _connect(_pin(step, "ReturnValue", is_input=False), _pin(at, "B"))
        return _pin(at, "ReturnValue", is_input=False), [cell, as_float, step, at]

    at_x_out, x_nodes = along(FN_MOD_II, x_out, SLOT_W + SLOT_GAP, y0 + 520)
    at_y_out, y_nodes = along(FN_DIV_II, y_out, SLOT_H + SLOT_GAP, y0 + 1180)

    colour = _at(ed.add_get_member_variable_node("SlotColor", ITEM_CLASS_PATH),
                 x0 + 3700, y0 + 660)
    _connect(item, _pin(colour, "self"))
    name = _at(ed.add_get_member_variable_node("DisplayName", ITEM_CLASS_PATH),
               x0 + 3700, y0 + 780)
    _connect(item, _pin(name, "self"))

    # The weapon's own silhouette, tinted with its own SlotColor: the colour
    # still identifies it at a glance from across the strip, and the shape says
    # which gun it is without reading the label.
    icon = _at(ed.add_get_member_variable_node("Icon", ITEM_CLASS_PATH),
               x0 + 3700, y0 + 900)
    _connect(item, _pin(icon, "self"))

    # --- is this the equipped slot? -----------------------------------------
    # Computed before anything in the slot is drawn, because the answer now
    # changes the BACKGROUND as well as the border. A lit edge over a dark slot
    # was reported as not reading at all; a lit slot with a lit edge is a
    # different shape from its neighbours, not a brighter outline on the same
    # one.
    is_equipped = _at(_node(ed, FN_EQ_II), x0 + 3940, y0 + 1040)
    _connect(index, _pin(is_equipped, "A"))
    _connect(_pin(equipped, "EquippedIndex", is_input=False), _pin(is_equipped, "B"))
    lit = _at(ed.add_branch_node(), x0 + 4180, y0 - 300)
    _connect(_pin(is_equipped, "ReturnValue", is_input=False), _pin(lit, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(lit, "execute"))

    back = _draw_texture(ed, x0 + 4420, y0 - 300, "T_UI_SlotActive",
                         w=SLOT_W, h=SLOT_H)
    _connect(at_x_out, _pin(back, "ScreenX"))
    _connect(at_y_out, _pin(back, "ScreenY"))
    _connect(BEL.find_then_pin(lit), _pin(back, "execute"))

    icon_x = _at(_node(ed, FN_ADD), x0 + 4180, y0 + 660)
    _connect(at_x_out, _pin(icon_x, "A"))
    _set(icon_x, "B", (SLOT_W - SLOT_ICON_W) / 2.0)
    icon_y = _at(_node(ed, FN_ADD), x0 + 4180, y0 + 780)
    _connect(at_y_out, _pin(icon_y, "A"))
    _set(icon_y, "B", SLOT_ICON_TOP)

    fill = _at(_node(ed, FN_DRAW_TEXTURE), x0 + 4420, y0)
    _connect(_pin(icon, "Icon", is_input=False), _pin(fill, "Texture"))
    _connect(_pin(colour, "SlotColor", is_input=False), _pin(fill, "TintColor"))
    _set(fill, "ScreenW", SLOT_ICON_W)
    _set(fill, "ScreenH", SLOT_ICON_H)
    _set(fill, "TextureU", 0.0)
    _set(fill, "TextureV", 0.0)
    _set(fill, "TextureUWidth", 1.0)    # normalised -- see _draw_texture
    _set(fill, "TextureVHeight", 1.0)
    _connect(_pin(icon_x, "ReturnValue", is_input=False), _pin(fill, "ScreenX"))
    _connect(_pin(icon_y, "ReturnValue", is_input=False), _pin(fill, "ScreenY"))
    _connect(BEL.find_then_pin(back), _pin(fill, "execute"))
    _connect(BEL.find_else_pin(lit), _pin(fill, "execute"))

    # --- how much ammunition this weapon has --------------------------------
    # Read off the item, like SlotColor and DisplayName, so the strip stays a
    # view of whatever is carried and knows nothing about shotguns.
    uses = _at(ed.add_get_member_variable_node("UsesAmmo", ITEM_CLASS_PATH),
               x0 + 4680, y0 + 660)
    _connect(item, _pin(uses, "self"))
    counted = _at(ed.add_branch_node(), x0 + 4940, y0 + 900)
    _connect(_pin(uses, "UsesAmmo", is_input=False), _pin(counted, "Condition"))
    _connect(BEL.find_then_pin(fill), _pin(counted, "execute"))

    in_gun = _at(ed.add_get_member_variable_node("Loaded", ITEM_CLASS_PATH),
                 x0 + 4680, y0 + 780)
    _connect(item, _pin(in_gun, "self"))
    in_bag = _at(ed.add_get_member_variable_node("Reserve", ITEM_CLASS_PATH),
                 x0 + 4680, y0 + 900)
    _connect(item, _pin(in_bag, "self"))
    in_gun_s = _at(_node(ed, FN_INT_TO_STR), x0 + 4940, y0 + 780)
    _connect(_pin(in_gun, "Loaded", is_input=False), _pin(in_gun_s, "InInt"))
    in_bag_s = _at(_node(ed, FN_INT_TO_STR), x0 + 4940, y0 + 1020)
    _connect(_pin(in_bag, "Reserve", is_input=False), _pin(in_bag_s, "InInt"))
    sep = _at(_node(ed, FN_CONCAT), x0 + 5180, y0 + 900)
    _set(sep, "A", " / ")
    _connect(_pin(in_bag_s, "ReturnValue", is_input=False), _pin(sep, "B"))
    ammo_str = _at(_node(ed, FN_CONCAT), x0 + 5420, y0 + 840)
    _connect(_pin(in_gun_s, "ReturnValue", is_input=False), _pin(ammo_str, "A"))
    _connect(_pin(sep, "ReturnValue", is_input=False), _pin(ammo_str, "B"))

    # Right-aligned, from the width the font actually reports. GetTextSize is
    # a HUD method, so "self" is this HUD -- and it has to be given the same
    # Font and Scale the DrawText below uses or it measures a different string.
    measure = _at(_node(ed, FN_TEXT_SIZE), x0 + 5420, y0 + 1080)
    _connect(_pin(ammo_str, "ReturnValue", is_input=False), _pin(measure, "Text"))
    _set(measure, "Font", UI_FONT)
    _set(measure, "Scale", SLOT_AMMO_SCALE)

    ammo_right = _at(_node(ed, FN_ADD), x0 + 5180, y0 + 660)
    _connect(at_x_out, _pin(ammo_right, "A"))
    _set(ammo_right, "B", SLOT_W - SLOT_AMMO_RIGHT)
    ammo_x = _at(_node(ed, FN_SUB), x0 + 5660, y0 + 660)
    _connect(_pin(ammo_right, "ReturnValue", is_input=False), _pin(ammo_x, "A"))
    _connect(_pin(measure, "OutWidth", is_input=False), _pin(ammo_x, "B"))
    ammo_y = _at(_node(ed, FN_ADD), x0 + 5180, y0 + 780)
    _connect(at_y_out, _pin(ammo_y, "A"))
    _set(ammo_y, "B", SLOT_AMMO_BASELINE)

    ammo = _at(_node(ed, FN_DRAW_TEXT), x0 + 5680, y0 + 640)
    _connect(_pin(ammo_str, "ReturnValue", is_input=False), _pin(ammo, "Text"))
    _set(ammo, "TextColor", COL_SLOT_AMMO)
    _set(ammo, "Scale", SLOT_AMMO_SCALE)
    _set(ammo, "bScalePosition", "false")
    _set(ammo, "Font", UI_FONT)
    _connect(_pin(ammo_x, "ReturnValue", is_input=False), _pin(ammo, "ScreenX"))
    _connect(_pin(ammo_y, "ReturnValue", is_input=False), _pin(ammo, "ScreenY"))
    _connect(BEL.find_then_pin(counted), _pin(ammo, "execute"))

    # --- the equipped slot gets its frame and its name ----------------------
    marked = _at(ed.add_branch_node(), x0 + 5940, y0)
    _connect(_pin(is_equipped, "ReturnValue", is_input=False), _pin(marked, "Condition"))
    # Both arms of the ammunition branch carry on: a pistol still gets its
    # underline.
    _connect(BEL.find_then_pin(ammo), _pin(marked, "execute"))
    _connect(BEL.find_else_pin(counted), _pin(marked, "execute"))

    # A lit frame around the whole slot rather than a 5px underline. It is a
    # separate texture from T_UI_SlotActive because it is drawn OVER the icon:
    # the filled variant would hide the thing the player is looking at.
    mark = _draw_texture(ed, x0 + 6200, y0, "T_UI_SlotFrame",
                         w=SLOT_W, h=SLOT_H)
    _connect(at_x_out, _pin(mark, "ScreenX"))
    _connect(at_y_out, _pin(mark, "ScreenY"))
    _connect(BEL.find_then_pin(marked), _pin(mark, "execute"))

    # And its name, once, centred over the whole strip. Centred from a real
    # measurement for the same reason the ammunition count is right-aligned
    # from one: "SMG" and "Shotgun" are not the same width.
    name_size = _at(_node(ed, FN_TEXT_SIZE), x0 + 6200, y0 + 900)
    _connect(_pin(name, "DisplayName", is_input=False), _pin(name_size, "Text"))
    _set(name_size, "Font", UI_FONT)
    _set(name_size, "Scale", EQUIPPED_NAME_SCALE)
    half_name = _at(_node(ed, FN_MUL), x0 + 6440, y0 + 900)
    _connect(_pin(name_size, "OutWidth", is_input=False), _pin(half_name, "A"))
    _set(half_name, "B", 0.5)
    mid = _at(_node(ed, FN_MUL), x0 + 6440, y0 + 1040)
    _connect(_pin(wh, "X", is_input=False), _pin(mid, "A"))
    _set(mid, "B", 0.5)
    name_x = _at(_node(ed, FN_SUB), x0 + 6680, y0 + 900)
    _connect(_pin(mid, "ReturnValue", is_input=False), _pin(name_x, "A"))
    _connect(_pin(half_name, "ReturnValue", is_input=False), _pin(name_x, "B"))
    name_y = _at(_node(ed, FN_SUB), x0 + 6680, y0 + 1040)
    _connect(y_out, _pin(name_y, "A"))
    _set(name_y, "B", EQUIPPED_NAME_ABOVE + 20.0)

    who = _at(_node(ed, FN_DRAW_TEXT), x0 + 6940, y0)
    _connect(_pin(name, "DisplayName", is_input=False), _pin(who, "Text"))
    _set(who, "TextColor", COL_EQUIPPED_NAME)
    _set(who, "Scale", EQUIPPED_NAME_SCALE)
    _set(who, "bScalePosition", "false")
    _set(who, "Font", UI_FONT)
    _connect(_pin(name_x, "ReturnValue", is_input=False), _pin(who, "ScreenX"))
    _connect(_pin(name_y, "ReturnValue", is_input=False), _pin(who, "ScreenY"))
    _connect(BEL.find_then_pin(mark), _pin(who, "execute"))

    ed.add_comment_to_nodes(
        "Each carried weapon paints its own silhouette into its slot, tinted "
        "with its own SlotColor, and its rounds-in-gun / rounds-in-reserve "
        "right-aligned underneath if it uses ammunition at all. The equipped "
        "one gets three things rather than one -- a lit background, a lit "
        "frame over the icon, and its name centred above the strip -- because "
        "a lit edge alone was reported as not reading. Everything is off the "
        "weapon's own properties, so the HUD needs no table of weapon names "
        "and no idea which of them is the one with a magazine.",
        [pawn, comp, cast, inv, equipped, loop, *x_nodes, *y_nodes, colour,
         name, fill, uses, counted, in_gun, in_bag,
         in_gun_s, in_bag_s, sep, ammo_str, ammo_x, ammo_y, ammo,
         is_equipped, marked, icon, icon_x, icon_y, mark, lit, back,
         measure, ammo_right, name_size, half_name, mid, name_x, name_y, who])

    # A pawn with no weapon component still has to reach the menu below.
    return (_loose_pin(loop, "Completed", is_input=False),
            _pin(cast, "CastFailed", is_input=False))


# ─── Event ReceiveDrawHUD: the panel ─────────────────────────────────────────

def _author_main_menu(ed, x0, y0, in_execs):
    """The menu the game opens on, and the one thing that leaves it.

    Returns ``(exec_pins_when_already_started,)`` -- the path the rest of the
    HUD hangs off. Nothing below this point draws until the player has started,
    which is the point: a reticle and a health bar over a title screen read as
    a game that is already being played.

    Two rows now, NEW GAME and SETTINGS, which is why the left mouse button is
    no longer an accept key: with no cursor and no hit test a click cannot say
    which row it means. See START_KEYS.

    See START_KEYS for why this is polled here and not on Event Tick.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    started = keep(_at(ed.add_get_member_variable_node(GAME_STARTED_VAR),
                       x0, y0 + 240))
    playing = keep(_at(ed.add_branch_node(), x0 + 260, y0))
    _connect(_pin(started, GAME_STARTED_VAR, is_input=False), _pin(playing, "Condition"))
    for e in in_execs:
        _connect(e, _pin(playing, "execute"))

    # Which page the panel is showing. The settings page is a separate block
    # rather than more rows on this one because it is a different panel size,
    # a different column layout and a different set of keys.
    page = keep(_at(ed.add_get_member_variable_node("MenuPage"), x0 + 260, y0 + 400))
    on_title = keep(_at(_node(ed, FN_EQ_II), x0 + 500, y0 + 400))
    _connect(_pin(page, "MenuPage", is_input=False), _pin(on_title, "A"))
    _set(on_title, "B", PAGE_TITLE)
    which = keep(_at(ed.add_branch_node(), x0 + 760, y0 + 160))
    _connect(_pin(on_title, "ReturnValue", is_input=False), _pin(which, "Condition"))
    _connect(BEL.find_else_pin(playing), _pin(which, "execute"))

    _author_settings_page(ed, x0, y0 + 9000, BEL.find_else_pin(which))

    size = keep(_at(_node(ed, FN_VIEWPORT), x0 + 260, y0 + 420))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 500, y0 + 420))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))

    def centred(axis, span, py):
        half = keep(_at(_node(ed, FN_MUL), x0 + 740, py))
        _connect(_loose_pin(wh, axis, is_input=False), _pin(half, "A"))
        _set(half, "B", 0.5)
        off = keep(_at(_node(ed, FN_SUB), x0 + 980, py))
        _connect(_pin(half, "ReturnValue", is_input=False), _pin(off, "A"))
        _set(off, "B", span)
        return _pin(off, "ReturnValue", is_input=False)

    panel_x = centred("X", MENU_PANEL[0] / 2.0, y0 + 420)
    panel_y = centred("Y", MENU_PANEL[1] / 2.0, y0 + 560)

    panel = keep(_draw_texture(ed, x0 + 1240, y0, "T_UI_Panel",
                               w=MENU_PANEL[0], h=MENU_PANEL[1]))
    _connect(panel_x, _pin(panel, "ScreenX"))
    _connect(panel_y, _pin(panel, "ScreenY"))
    _connect(BEL.find_then_pin(which), _pin(panel, "execute"))

    # The button plate, so a row reads as something you press rather than as a
    # line of text. T_UI_SlotActive stretched: it is already the lit,
    # amber-edged surface the inventory strip uses for "this is the one", which
    # is the same thing being said here.
    #
    # It is also the caret. Its y is MenuRow-driven, exactly as the quality
    # panel's ">" is Quality-driven, so the selected row is the lit one and
    # there is no second marker to keep in step with it.
    button_x = keep(_at(_node(ed, FN_ADD), x0 + 1240, y0 + 700))
    _connect(panel_x, _pin(button_x, "A"))
    _set(button_x, "B", (MENU_PANEL[0] - START_BUTTON[0]) / 2.0)
    row = keep(_at(ed.add_get_member_variable_node("MenuRow"), x0 + 1240, y0 + 940))
    row_f = keep(_at(_node(ed, FN_CONV_INT), x0 + 1480, y0 + 940))
    _connect(_pin(row, "MenuRow", is_input=False), _pin(row_f, "InInt"))
    row_off = keep(_at(_node(ed, FN_MUL), x0 + 1720, y0 + 940))
    _connect(_pin(row_f, "ReturnValue", is_input=False), _pin(row_off, "A"))
    _set(row_off, "B", MAIN_ROW_STEP)
    plate_y = keep(_at(_node(ed, FN_ADD), x0 + 1240, y0 + 820))
    _connect(panel_y, _pin(plate_y, "A"))
    _set(plate_y, "B", MAIN_PLATE_OFF)
    button_y = keep(_at(_node(ed, FN_ADD), x0 + 1960, y0 + 940))
    _connect(_pin(plate_y, "ReturnValue", is_input=False), _pin(button_y, "A"))
    _connect(_pin(row_off, "ReturnValue", is_input=False), _pin(button_y, "B"))
    button = keep(_draw_texture(ed, x0 + 1500, y0, "T_UI_SlotActive",
                                w=START_BUTTON[0], h=START_BUTTON[1]))
    _connect(_pin(button_x, "ReturnValue", is_input=False), _pin(button, "ScreenX"))
    _connect(_pin(button_y, "ReturnValue", is_input=False), _pin(button, "ScreenY"))
    _connect(BEL.find_then_pin(panel), _pin(button, "execute"))

    flow = BEL.find_then_pin(button)
    column = 0

    def line(text, y_off, scale, color, px):
        """One centred line, measured rather than guessed.

        GetTextSize with the SAME font and scale the draw uses -- a fixed x
        offset per string is a guess at Roboto's advance widths that is wrong
        by a different amount for every line, and the miscentring shows most on
        exactly the biggest one.
        """
        nonlocal flow, column
        column += 1
        py = y0 + 900 + column * 200
        m = keep(_at(_node(ed, FN_TEXT_SIZE), px, py))
        _set(m, "Text", text)
        _set(m, "Font", UI_FONT)
        _set(m, "Scale", scale)
        half = keep(_at(_node(ed, FN_MUL), px + 240, py))
        _connect(_pin(m, "OutWidth", is_input=False), _pin(half, "A"))
        _set(half, "B", 0.5)
        mid = keep(_at(_node(ed, FN_MUL), px + 240, py + 120))
        _connect(_loose_pin(wh, "X", is_input=False), _pin(mid, "A"))
        _set(mid, "B", 0.5)
        at_x = keep(_at(_node(ed, FN_SUB), px + 480, py))
        _connect(_pin(mid, "ReturnValue", is_input=False), _pin(at_x, "A"))
        _connect(_pin(half, "ReturnValue", is_input=False), _pin(at_x, "B"))
        at_y = keep(_at(_node(ed, FN_ADD), px + 480, py + 120))
        _connect(panel_y, _pin(at_y, "A"))
        _set(at_y, "B", y_off)

        n = keep(_at(_node(ed, FN_DRAW_TEXT), px + 720, y0))
        _set(n, "Text", text)
        _set(n, "TextColor", color)
        _set(n, "Scale", scale)
        _set(n, "bScalePosition", "false")
        _set(n, "Font", UI_FONT)
        _connect(_pin(at_x, "ReturnValue", is_input=False), _pin(n, "ScreenX"))
        _connect(_pin(at_y, "ReturnValue", is_input=False), _pin(n, "ScreenY"))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        return n

    line(GAME_TITLE, 56.0, MAIN_TITLE_SCALE, COL_MAIN_TITLE, x0 + 1760)
    line(GAME_SUBTITLE, 124.0, MAIN_SUB_SCALE, COL_MAIN_SUB, x0 + 2600)
    for i, label in enumerate(MENU_ROWS):
        line(label, MAIN_ROW0_OFF + i * MAIN_ROW_STEP, MAIN_START_SCALE,
             COL_MAIN_START, x0 + 3440 + i * 840)
    line("UP / DOWN  ·  ENTER selects", MAIN_HINT_OFF, MAIN_HINT_SCALE,
         COL_MAIN_HINT, x0 + 5120)

    # --- choosing a row -------------------------------------------------------
    pc = keep(_at(_node(ed, FN_GET_OWNING_PC), x0 + 5960, y0 + 400))
    pc_out = _pin(pc, "ReturnValue", is_input=False)
    moved, nav_nodes = _emit_row_nav(ed, pc_out, len(MENU_ROWS) - 1, flow,
                                     x0 + 6200, y0 + 1200)
    made += nav_nodes
    go = _emit_accept(ed, pc_out, x0 + 7700, y0 + 400, moved, made)

    # NEW GAME or SETTINGS, off the same MenuRow the lit plate is drawn from.
    new_game = keep(_at(_node(ed, FN_EQ_II), x0 + 7960, y0 + 400))
    _connect(_pin(keep(_at(ed.add_get_member_variable_node("MenuRow"),
                           x0 + 7700, y0 + 400)), "MenuRow", is_input=False),
             _pin(new_game, "A"))
    _set(new_game, "B", 0)
    chosen = keep(_at(ed.add_branch_node(), x0 + 8220, y0))
    _connect(_pin(new_game, "ReturnValue", is_input=False), _pin(chosen, "Condition"))
    _connect(BEL.find_then_pin(go), _pin(chosen, "execute"))

    mark = keep(_at(ed.add_set_member_variable_node(GAME_STARTED_VAR),
                    x0 + 8480, y0))
    _set(mark, GAME_STARTED_VAR, "true")
    _connect(BEL.find_then_pin(chosen), _pin(mark, "execute"))

    # Unpause LAST. Setting GameStarted first means the very next frame draws
    # the HUD rather than the menu, so there is no frame where the world is
    # running behind a title screen.
    resume = keep(_at(_node(ed, FN_SET_PAUSED), x0 + 8740, y0))
    _set(resume, "bPaused", "false")
    _connect(BEL.find_then_pin(mark), _pin(resume, "execute"))

    # ...or the other row: open the settings page, with the caret at the top of
    # it rather than wherever it was left on this one.
    to_settings = keep(_at(ed.add_set_member_variable_node("MenuPage"),
                           x0 + 8480, y0 + 600))
    _set(to_settings, "MenuPage", PAGE_SETTINGS)
    _connect(BEL.find_else_pin(chosen), _pin(to_settings, "execute"))
    reset_row = keep(_at(ed.add_set_member_variable_node("MenuRow"),
                         x0 + 8740, y0 + 600))
    _set(reset_row, "MenuRow", 0)
    _connect(BEL.find_then_pin(to_settings), _pin(reset_row, "execute"))

    ed.add_comment_to_nodes(
        f"The main menu. Drawn instead of the HUD while {GAME_STARTED_VAR} is "
        f"false, which BeginPlay sets it to along with pausing the world, so "
        f"the wanderers are not already running at the player behind the title. "
        f"{' / '.join(START_KEYS)} takes the row the lit plate is on, and both "
        f"the plate and the keys are polled HERE rather than on Event Tick "
        f"because Tick does not run while the game is paused -- the same "
        f"reason the death menu's restart key lives in DrawHUD.",
        made)
    return (BEL.find_then_pin(playing),)


def _author_death_menu(ed, x0, y0, in_execs, mode_out):
    """What is on screen once the player is dead and the game is paused.

    Drawn instead of the HUD, not on top of it: a reticle and an inventory
    strip over a death screen read as a game that is still being played.

    The restart key is polled *here*, in DrawHUD, and that is the load-bearing
    detail. Event Tick does not run while the game is paused, so a key polled
    there would never be seen -- but DrawHUD is called from the renderer every
    frame regardless, and APlayerController sets bTickEvenWhenPaused, so its
    PlayerInput is still updated and WasInputKeyJustPressed still answers.

    Restarting is SetGamePaused(false) *then* OpenLevel: a level opened while
    the world is paused comes up paused, with nothing left able to unpause it.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    dead = keep(_at(ed.add_get_member_variable_node(PLAYER_DEAD_VAR,
                                                    GAME_MODE_CLASS_PATH),
                    x0, y0 + 240))
    _connect(mode_out, _pin(dead, "self"))
    over = keep(_at(ed.add_branch_node(), x0 + 260, y0))
    _connect(_pin(dead, PLAYER_DEAD_VAR, is_input=False), _pin(over, "Condition"))
    for e in in_execs:
        _connect(e, _pin(over, "execute"))

    # Centred on the viewport, so the panel lands in the middle of any window.
    size = keep(_at(_node(ed, FN_VIEWPORT), x0 + 260, y0 + 420))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 500, y0 + 420))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))

    def centred(axis, span, py):
        half = keep(_at(_node(ed, FN_MUL), x0 + 740, py))
        _connect(_loose_pin(wh, axis, is_input=False), _pin(half, "A"))
        _set(half, "B", 0.5)
        off = keep(_at(_node(ed, FN_SUB), x0 + 980, py))
        _connect(_pin(half, "ReturnValue", is_input=False), _pin(off, "A"))
        _set(off, "B", span)
        return _pin(off, "ReturnValue", is_input=False)

    panel_x = centred("X", DEATH_PANEL[0] / 2.0, y0 + 420)
    panel_y = centred("Y", DEATH_PANEL[1] / 2.0, y0 + 560)

    panel = keep(_draw_texture(ed, x0 + 1240, y0, "T_UI_PanelDeath",
                               w=DEATH_PANEL[0], h=DEATH_PANEL[1]))
    _connect(panel_x, _pin(panel, "ScreenX"))
    _connect(panel_y, _pin(panel, "ScreenY"))
    _connect(BEL.find_then_pin(over), _pin(panel, "execute"))

    flow = BEL.find_then_pin(panel)
    column = 0

    def line(x_off, y_off, scale, color, px):
        """One line of the menu, positioned relative to the panel's corner."""
        nonlocal flow, column
        column += 1
        at_x = keep(_at(_node(ed, FN_ADD), px, y0 + 700 + column * 140))
        _connect(panel_x, _pin(at_x, "A"))
        _set(at_x, "B", x_off)
        at_y = keep(_at(_node(ed, FN_ADD), px, y0 + 770 + column * 140))
        _connect(panel_y, _pin(at_y, "A"))
        _set(at_y, "B", y_off)
        n = keep(_at(_node(ed, FN_DRAW_TEXT), px + 240, y0))
        _set(n, "TextColor", color)
        _set(n, "Scale", scale)
        _set(n, "bScalePosition", "false")
        _set(n, "Font", UI_FONT)
        _connect(_pin(at_x, "ReturnValue", is_input=False), _pin(n, "ScreenX"))
        _connect(_pin(at_y, "ReturnValue", is_input=False), _pin(n, "ScreenY"))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        return n

    title = line(150.0, 50.0, DEATH_TITLE_SCALE, COL_DEATH_TITLE, x0 + 1480)
    _set(title, "Text", "YOU DIED")

    # The same counter the corner shows, read once more so the final score is
    # the live number rather than a copy taken when the player fell.
    kills = keep(_at(ed.add_get_member_variable_node(KILL_COUNT_VAR,
                                                     GAME_MODE_CLASS_PATH),
                     x0 + 1240, y0 + 1120))
    _connect(mode_out, _pin(kills, "self"))
    kills_str = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 1480, y0 + 1120))
    _connect(_pin(kills, KILL_COUNT_VAR, is_input=False), _pin(kills_str, "InInt"))
    score_text = keep(_at(_node(ed, FN_CONCAT), x0 + 1720, y0 + 1120))
    _set(score_text, "A", "NPCs killed:  ")
    _connect(_pin(kills_str, "ReturnValue", is_input=False), _pin(score_text, "B"))

    score = line(150.0, 140.0, DEATH_SCORE_SCALE, COL_DEATH_TEXT, x0 + 2000)
    _connect(_pin(score_text, "ReturnValue", is_input=False), _pin(score, "Text"))

    hint = line(150.0, 220.0, DEATH_HINT_SCALE, COL_DEATH_HINT, x0 + 2520)
    _set(hint, "Text", f"[{RESTART_KEY}]   try again")

    # --- the restart itself --------------------------------------------------
    pc = keep(_at(_node(ed, FN_GET_OWNING_PC), x0 + 3040, y0 + 300))
    pressed = keep(_at(_node(ed, FN_WAS_PRESSED), x0 + 3280, y0 + 300))
    _connect(_pin(pc, "ReturnValue", is_input=False), _pin(pressed, "self"))
    _set(pressed, "Key", RESTART_KEY)
    again = keep(_at(ed.add_branch_node(), x0 + 3540, y0))
    _connect(_pin(pressed, "ReturnValue", is_input=False), _pin(again, "Condition"))
    _connect(flow, _pin(again, "execute"))

    unpause = keep(_at(_node(ed, FN_SET_PAUSED), x0 + 3800, y0))
    _set(unpause, "bPaused", "false")
    _connect(BEL.find_then_pin(again), _pin(unpause, "execute"))

    # The current map by name, so the menu restarts whatever level is loaded
    # rather than a path written down here that a generated level would not
    # match. bRemovePrefixString strips PIE's UEDPIE_0_ -- without it the open
    # would look for a map that only exists inside a running PIE session.
    where = keep(_at(_node(ed, FN_LEVEL_NAME), x0 + 4060, y0))
    _set(where, "bRemovePrefixString", "true")
    _connect(BEL.find_then_pin(unpause), _pin(where, "execute"))
    reopen = keep(_at(_node(ed, FN_OPEN_LEVEL), x0 + 4320, y0))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(reopen, "LevelName"))
    _connect(BEL.find_then_pin(where), _pin(reopen, "execute"))

    ed.add_comment_to_nodes(
        f"The death menu, drawn instead of the HUD while the GameMode's "
        f"{PLAYER_DEAD_VAR} is set and the game is paused. [{RESTART_KEY}] "
        f"unpauses and reopens the current level, which resets the kill count "
        f"with it -- the counter lives on the GameMode, and OpenLevel builds a "
        f"new one.",
        made)


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
    fps_out = author_fps(ed, x0 + 3000, y0 + 16000, pushed, UI_FONT)

    # The main menu, before anything else is drawn and before the dead/alive
    # test: a title screen is neither.
    playing = _author_main_menu(ed, x0 + 3000, y0 + 6000, fps_out)

    alive = _at(ed.add_branch_node(), x0 + 60, y0)
    dead_get = _at(ed.add_get_member_variable_node(PLAYER_DEAD_VAR,
                                                   GAME_MODE_CLASS_PATH),
                   x0 - 440, y0 + 240)
    _connect(mode_out, _pin(dead_get, "self"))
    _connect(_pin(dead_get, PLAYER_DEAD_VAR, is_input=False), _pin(alive, "Condition"))
    for e in playing:
        _connect(e, _pin(alive, "execute"))

    _author_death_menu(ed, x0 + 3000, y0 + 3000,
                       (BEL.find_then_pin(alive),), mode_out)

    # A GameMode that is not BP_ThirdPersonGameMode cannot say whether the
    # player is dead, so it is treated as alive and the HUD draws as normal --
    # a missing death menu is recoverable, a missing HUD is not.
    living = (BEL.find_else_pin(alive),)

    # HP first, so it is on screen whether or not the menu is open.
    after_hp = _author_hp(ed, x0, y0 - 900, living)
    after_st = _author_stamina(ed, x0, y0 - 1600, after_hp)
    after_sv = author_survival_bars(ed, x0 + 9000, y0 - 1600, after_st)
    after_kills = _author_kills(ed, x0, y0 - 2300, after_sv)

    # Then the world-space NPC bars and the inventory strip, both of which are
    # always on screen for the same reason the HP bar is.
    after_npc = _author_npc_bars(ed, x0, y0 - 3200, after_kills)
    after_inv = _author_inventory(ed, x0, y0 - 5000, after_npc)

    # Last of the always-on layers, so the crosshair sits on top of the rest.
    after_aim = _author_reticle(ed, x0, y0 - 6800, after_inv)
    # The save-and-exit countdown, over everything but the panel.
    after_aim = author_exit_banner(ed, x0, y0 - 8200, after_aim)

    get_open = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 240, y0 + 200)
    br = _at(ed.add_branch_node(), x0 + 420, y0)
    _connect(_pin(get_open, "MenuOpen", is_input=False), _pin(br, "Condition"))
    # Every path above -- drawn or cast-failed -- falls through to the menu; an
    # exec input takes more than one link, so no Sequence node is needed.
    for exec_out in after_aim:
        _connect(exec_out, _pin(br, "execute"))

    rect = _draw_texture(ed, x0 + 640, y0, "T_UI_Panel",
                         w=PANEL[2], h=PANEL[3])
    _set(rect, "ScreenX", PANEL[0])
    _set(rect, "ScreenY", PANEL[1])
    _connect(BEL.find_then_pin(br), _pin(rect, "execute"))

    flow = BEL.find_then_pin(rect)
    made = [rect]

    def text(label, x, y, scale, color, at_x, at_y):
        nonlocal flow
        n = _at(_node(ed, FN_DRAW_TEXT), at_x, at_y)
        _set(n, "Text", label)
        _set(n, "TextColor", color)
        _set(n, "ScreenX", x)
        _set(n, "ScreenY", y)
        _set(n, "Scale", scale)
        _set(n, "bScalePosition", "false")
        _set(n, "Font", UI_FONT)
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        made.append(n)
        return n

    text("GRAPHICS QUALITY", TITLE_POS[0], TITLE_POS[1], TITLE_SCALE, COL_TITLE,
         x0 + 860, y0)
    for i, preset in enumerate(PRESETS):
        text(f"[{i + 1}]   {preset.label}", ROW_X, ROW_Y0 + i * ROW_STEP, ROW_SCALE,
             COL_ROW, x0 + 1080 + i * 220, y0)
    # Two draws behind one branch rather than one draw with a driven string:
    # KismetStringLibrary has no Select, and a bool converted to a string reads
    # "[D]   debug   true", which is a variable's value and not a setting.
    dbg_get = _at(ed.add_get_member_variable_node("DebugOn"), x0 + 1740, y0 + 320)
    dbg_br = _at(ed.add_branch_node(), x0 + 1740, y0)
    _connect(_pin(dbg_get, "DebugOn", is_input=False), _pin(dbg_br, "Condition"))
    _connect(flow, _pin(dbg_br, "execute"))
    made += [dbg_get, dbg_br]

    def debug_row(label, at_x, exec_in):
        n = _at(_node(ed, FN_DRAW_TEXT), at_x, y0)
        _set(n, "Text", label)
        _set(n, "TextColor", COL_ROW)
        _set(n, "ScreenX", ROW_X)
        _set(n, "ScreenY", DEBUG_ROW_Y)
        _set(n, "Scale", ROW_SCALE)
        _set(n, "bScalePosition", "false")
        _set(n, "Font", UI_FONT)
        _connect(exec_in, _pin(n, "execute"))
        made.append(n)
        return BEL.find_then_pin(n)

    on_tail = debug_row(f"[{DEBUG_KEY}]   debug   ON", x0 + 1960,
                        BEL.find_then_pin(dbg_br))
    off_tail = debug_row(f"[{DEBUG_KEY}]   debug   OFF", x0 + 2180,
                         BEL.find_else_pin(dbg_br))

    hint = _at(_node(ed, FN_DRAW_TEXT), x0 + 2400, y0)
    _set(hint, "Text", f"[{MENU_KEY}]   close")
    _set(hint, "TextColor", COL_HINT)
    _set(hint, "ScreenX", HINT_POS[0])
    _set(hint, "ScreenY", HINT_POS[1])
    _set(hint, "Scale", HINT_SCALE)
    _set(hint, "bScalePosition", "false")
    _set(hint, "Font", UI_FONT)
    exit_tail = author_exit_row(ed, ROW_X, EXIT_ROW_Y, ROW_SCALE,
                                (on_tail, off_tail), x0 + 2290, y0 + 200)
    _connect(exit_tail, _pin(hint, "execute"))
    made.append(hint)
    flow = BEL.find_then_pin(hint)

    # The caret's Y is Quality-driven, so the selection is read off the variable
    # instead of needing three separate draws with baked-in coordinates.
    q = _at(ed.add_get_member_variable_node("Quality"), x0 + 860, y0 + 320)
    conv = _at(_node(ed, FN_CONV_INT), x0 + 1040, y0 + 320)
    _connect(_pin(q, "Quality", is_input=False), _pin(conv, "InInt"))
    mul = _at(_node(ed, FN_MUL), x0 + 1220, y0 + 320)
    _connect(_pin(conv, "ReturnValue", is_input=False), _pin(mul, "A"))
    _set(mul, "B", ROW_STEP)
    add = _at(_node(ed, FN_ADD), x0 + 1400, y0 + 320)
    _connect(_pin(mul, "ReturnValue", is_input=False), _pin(add, "A"))
    _set(add, "B", ROW_Y0)

    caret = text(">", CARET_X, ROW_Y0, ROW_SCALE, COL_CARET, x0 + 2620, y0)
    _connect(_pin(add, "ReturnValue", is_input=False), _pin(caret, "ScreenY"))

    ed.add_comment_to_nodes(
        "Drawn only while MenuOpen.  The caret's ScreenY is "
        f"{ROW_Y0:.0f} + Quality * {ROW_STEP:.0f}, so it follows the selection.",
        made + [q, conv, mul, add])


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
                         "Quality": DEFAULT_PRESET,
                         GRASS_APPLIED_VAR: GRASS_APPLIED_DEFAULT,
                         "MenuPage": PAGE_TITLE, "MenuRow": 0,
                         "Capturing": False,
                         "KeyPool": [_key(k) for k in KEY_POOL],
                         "BindLabels": list(BIND_LABELS),
                         **difficulty_defaults(), **profile_defaults()})
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
