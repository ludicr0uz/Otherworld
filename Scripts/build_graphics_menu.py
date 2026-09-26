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
                    --> ConsoleCommand "stat fps"  (engine's own readout,
                        which draws itself in the top-right corner)

  [Event Tick] --> [Branch: WasInputKeyJustPressed(M)]
                      True  --> [Set MenuOpen = Not MenuOpen] --,
                      False ------------------------------------+
                                                                v
                                                   [Branch: MenuOpen]
                      True --> [Branch: key "1"] True --> apply Low    --.
                                     | False                             |
                               [Branch: key "2"] True --> apply Medium --+
                                     | False                             |
                               [Branch: key "3"] True --> apply High   --'

    "apply <preset>" = Set Quality -> GetGameUserSettings ->
                       SetOverallScalabilityLevel -> ApplyNonResolutionSettings ->
                       ConsoleCommand r.ShadowQuality -> ConsoleCommand r.ScreenPercentage

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
Health is read off BP_HealthComponent (built by build_shotgun_and_health.py)
rather than off the character class, so the HUD does not care which pawn is
possessed -- anything carrying the component displays.
"""

import unreal

# ─── Configuration ───────────────────────────────────────────────────────────

UI_DIR = "/Game/UI"
HUD_BP_PATH = f"{UI_DIR}/BP_GraphicsMenuHUD"

GAME_MODE_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"

# The three presets, in menu order.  Each is
#   (label, scalability level, r.ShadowQuality, r.ScreenPercentage)
#
# scalability level indexes UE's own groups: 0 Low, 1 Medium, 2 High, 3 Epic.
# "High" maps to Epic, not to 2, on purpose: Epic is what the project runs at
# today (HardwareTargeting DefaultGraphicsPerformance=Maximum), and the brief
# was that the top preset must be the *current* look, not a downgrade of it.
# Level 2 is skipped rather than squeezed in -- three well-separated presets
# beat four adjacent ones.
#
# The two console commands are not redundant with the scalability level:
#
#   r.ShadowQuality  — Config/DefaultEngine.ini pins this to 3 under
#     [/Script/Engine.RendererSettings].  That is SetByProjectSetting priority,
#     which *outranks* SetByScalability, so SetOverallScalabilityLevel silently
#     cannot move it (the editor logs "was ignored as it is lower priority").
#     A console command is SetByConsole, which outranks both, so this is the
#     only way the menu can reach shadows.  High passes 3 — the pinned value —
#     so picking High reproduces the shipping look exactly.
#   r.ScreenPercentage — not part of any scalability group, and on a forest this
#     dense it is the single biggest GPU lever available.
PRESETS = (
    ("Low",    0, 1,  70),
    ("Medium", 1, 2,  85),
    ("High",   3, 3, 100),
)
# Keys 1/2/3.  UE's FKey names for the number row are One/Two/Three.
#
# These go into the pin verbatim, NOT as struct text: FKey overrides
# ExportTextItem to write just the key name, so a pin set to '(KeyName="M")'
# imports back as a key literally called "(" -- it compiles, it saves, and the
# key silently never matches at runtime.
PRESET_KEYS = ("One", "Two", "Three")

MENU_KEY = "M"

# The FPS readout.  "stat fps" is the engine's own frame-rate display and it
# renders in the **top-right** corner of the viewport on its own -- there is no
# position to set, and nothing is drawn by this HUD's canvas for it.  Doing it
# this way rather than with a DrawText of 1/DeltaSeconds is deliberate: the stat
# system's number is the engine's own smoothed frame time (the same one the
# profiler reports), it costs nothing to maintain, and it keeps working if the
# HUD's draw graph is ever rewritten.  Chained onto BeginPlay for the same
# reason the startup preset is: a readout has to be on for the session, not
# waiting on a keypress the player has to know about.
FPS_COMMAND = "stat fps"

# The preset every session starts at.  BeginPlay *applies* it rather than just
# setting the caret: the menu can only tell the truth about the current quality
# if it is the thing that established it.
DEFAULT_PRESET = 0  # Low

# Where the player's health lives.  Built by build_shotgun_and_health.py; the
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

PANEL = (60.0, 130.0, 600.0, 300.0)   # x, y, w, h
TITLE_POS = (92.0, 158.0)
TITLE_SCALE = 2.2
ROW_X = 150.0
ROW_Y0 = 238.0
ROW_STEP = 46.0
ROW_SCALE = 2.0
CARET_X = 112.0
HINT_POS = (92.0, 382.0)
HINT_SCALE = 1.5

COL_PANEL = "(R=0.020000,G=0.025000,B=0.035000,A=0.780000)"
COL_TITLE = "(R=0.850000,G=0.900000,B=1.000000,A=1.000000)"
COL_ROW = "(R=0.720000,G=0.750000,B=0.800000,A=1.000000)"
COL_CARET = "(R=1.000000,G=0.820000,B=0.320000,A=1.000000)"
COL_HINT = "(R=0.480000,G=0.510000,B=0.560000,A=1.000000)"
COL_HP_BACK = "(R=0.030000,G=0.030000,B=0.035000,A=0.800000)"
COL_HP_FILL = "(R=0.750000,G=0.130000,B=0.120000,A=0.950000)"
COL_HP_LABEL = "(R=0.620000,G=0.650000,B=0.700000,A=1.000000)"
COL_HP_NUM = "(R=0.960000,G=0.960000,B=0.970000,A=1.000000)"

# --- the stamina bar, directly under the HP bar ------------------------------
# Same left edge and same width as HP, half the height: it reads as the second
# line of one readout rather than as a second widget. Sprint is on the weapon
# component (see build_weapons_and_combat.py), which this HUD already casts to
# every frame for the inventory strip, so the bar costs one extra variable read.
ST_BAR = (60.0, 100.0, 420.0, 14.0)
ST_LABEL_POS = (16.0, 96.0)
ST_LABEL_SCALE = 1.1
COL_ST_BACK = "(R=0.030000,G=0.030000,B=0.035000,A=0.800000)"
COL_ST_FILL = "(R=0.320000,G=0.720000,B=0.880000,A=0.950000)"
COL_ST_SPENT = "(R=0.820000,G=0.560000,B=0.180000,A=0.950000)"
COL_ST_LABEL = "(R=0.620000,G=0.650000,B=0.700000,A=1.000000)"

# --- the kill counter, top right ---------------------------------------------
# Under the engine's own `stat fps` line, which owns the very top of that
# corner. Right-anchored off the viewport width rather than placed at a fixed
# x, for the same reason the inventory strip is centred that way.
KILL_RIGHT_MARGIN = 150.0
KILL_TOP = 92.0
KILL_SCALE = 2.2
COL_KILL = "(R=0.960000,G=0.860000,B=0.450000,A=0.950000)"

# --- the death menu ----------------------------------------------------------
# R, not Enter or Space: Enter opens the editor console in PIE and Space is the
# jump key, which is still bound while the pawn stands dead.
RESTART_KEY = "R"
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
INVENTORY_SIZE = 5
SLOT_W = 104.0
SLOT_H = 68.0
SLOT_GAP = 10.0
SLOT_BOTTOM = 46.0         # pixels between the strip and the bottom edge
SLOT_NAME_SCALE = 1.3
SLOT_MARK_H = 5.0          # the equipped slot's underline
COL_SLOT_BACK = "(R=0.020000,G=0.025000,B=0.035000,A=0.700000)"
COL_SLOT_NAME = "(R=0.960000,G=0.960000,B=0.970000,A=1.000000)"
COL_SLOT_MARK = "(R=1.000000,G=0.820000,B=0.320000,A=1.000000)"

# --- reticle, nailed to the centre of the viewport ----------------------------
# The aim ray is cast from the camera along its forward vector, which is the
# centre of the screen, so the centre is where the shot goes. Drawing it at the
# projected impact point instead was tried and reverted: that point is a world
# position on whatever surface the ray lands on, so the crosshair slid around
# under its own parallax and could not be aimed with. Only the colour still
# reflects the world -- red when the muzzle's line is blocked.
RETICLE_GAP = 7.0          # pixels of clear space around the centre dot
RETICLE_ARM = 11.0         # length of each of the four ticks
RETICLE_THICK = 2.0
RETICLE_DOT = 3.0
COL_RETICLE = "(R=0.960000,G=0.960000,B=0.970000,A=0.900000)"
COL_RETICLE_BLOCKED = "(R=0.950000,G=0.250000,B=0.200000,A=0.950000)"

# ─── Function paths for the graph nodes ──────────────────────────────────────

FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_CONSOLE = "/Script/Engine.KismetSystemLibrary.ExecuteConsoleCommand"
FN_GET_GUS = "/Script/Engine.GameUserSettings.GetGameUserSettings"
FN_SET_OVERALL = "/Script/Engine.GameUserSettings.SetOverallScalabilityLevel"
FN_APPLY = "/Script/Engine.GameUserSettings.ApplyNonResolutionSettings"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_CONV_INT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_DRAW_RECT = "/Script/Engine.HUD.DrawRect"
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
FN_VIEWPORT = "/Script/UMG.WidgetLayoutLibrary.GetViewportSize"
FN_SELECT_COLOR = "/Script/Engine.KismetMathLibrary.SelectColor"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_LE = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_OPEN_LEVEL = "/Script/Engine.GameplayStatics.OpenLevel"
FN_LEVEL_NAME = "/Script/Engine.GameplayStatics.GetCurrentLevelName"

# The DrawHUD event is not one of the placeholder nodes a fresh Blueprint ships
# with (BeginPlay and Tick are), so it has to be created from the palette.
NODE_DRAW_HUD = "AddEvent|EventReceiveDrawHUD"
NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"
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


def _at(node, x, y):
    BEL.set_node_pos(node, unreal.IntPoint(int(x), int(y)))
    return node


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
                                ("Quality", "int", str(DEFAULT_PRESET))):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name(kind),
                                      default):
            raise RuntimeError(f"could not declare member variable {name}")


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
        if fresh.get_editor_property(name) != value:
            raise RuntimeError(f"default for {name} did not stick")


# ─── One preset, applied ─────────────────────────────────────────────────────

def _emit_apply(ed, index, x, y, in_exec):
    """Emit the chain that applies preset ``index`` and hook it to ``in_exec``.

    Shared by BeginPlay (which applies the startup default) and by each preset
    key, so there is exactly one description of what picking a preset does.
    Returns the nodes it made, for the caller to wrap in a comment.
    """
    _label, level, shadow, screen_pct = PRESETS[index]

    set_q = _at(ed.add_set_member_variable_node("Quality"), x, y)
    _set(set_q, "Quality", index)
    _connect(in_exec, _pin(set_q, "execute"))

    gus = _at(_node(ed, FN_GET_GUS), x + 200, y)
    _connect(BEL.find_then_pin(set_q), _pin(gus, "execute"))
    gus_out = _pin(gus, "ReturnValue", is_input=False)

    sos = _at(_node(ed, FN_SET_OVERALL), x + 400, y)
    _connect(gus_out, _pin(sos, "self"))
    _set(sos, "Value", level)
    _connect(BEL.find_then_pin(gus), _pin(sos, "execute"))

    # ApplyNonResolutionSettings, *never* ApplySettings.  ApplySettings also
    # applies resolution, which fires the console-variable sinks ->
    # SystemResolutionSinkCallback -> FSceneViewport::ResizeFrame ->
    # SWindow::SetWindowMode.  On macOS that lands in
    # FMacWindow::UpdateFullScreenState, which pumps the Cocoa run loop waiting
    # on a window-mode transition that never completes inside PIE: the editor
    # hangs at 100% CPU, on this very BeginPlay, with no log line after
    # "Bringing up level for play".  The menu never changes resolution, so
    # there is nothing to lose by skipping that half.
    app = _at(_node(ed, FN_APPLY), x + 620, y)
    _connect(gus_out, _pin(app, "self"))
    _connect(BEL.find_then_pin(sos), _pin(app, "execute"))

    made = [set_q, gus, sos, app]
    flow = BEL.find_then_pin(app)
    for offset, command in enumerate((f"r.ShadowQuality {shadow}",
                                      f"r.ScreenPercentage {screen_pct}")):
        c = _at(_node(ed, FN_CONSOLE), x + 840 + offset * 260, y)
        # WorldContextObject is a hidden pin the compiler fills from self, and a
        # null SpecificPlayer means "the first local player" -- which in a HUD
        # is always the player owning it.
        _set(c, "Command", command)
        _connect(flow, _pin(c, "execute"))
        flow = BEL.find_then_pin(c)
        made.append(c)
    return made


# ─── Event BeginPlay: the startup default ────────────────────────────────────

def _author_begin_play(ed, begin_play):
    origin = BEL.get_node_pos(begin_play)
    made = _emit_apply(ed, DEFAULT_PRESET, origin.x + 320, origin.y,
                       BEL.find_then_pin(begin_play))
    label = PRESETS[DEFAULT_PRESET][0]
    ed.add_comment_to_nodes(
        f"Every session starts at {label}.  This has to *apply* the preset, not "
        f"just point the caret at it: otherwise the panel would claim {label} "
        "while the engine ran at whatever scalability it happened to boot with.",
        made)

    # ...and then turn the engine's own FPS display on.  It is last in the chain
    # so that a failure to apply the preset cannot be hidden behind it.
    fps = _at(_node(ed, FN_CONSOLE), origin.x + 320, origin.y + 240)
    _set(fps, "Command", FPS_COMMAND)
    _connect(BEL.find_then_pin(made[-1]), _pin(fps, "execute"))
    ed.add_comment_to_nodes(
        f"{FPS_COMMAND!r} -- UE's built-in frame-rate readout, which draws "
        "itself in the top-right corner. Nothing on this HUD's canvas is "
        "involved, so it cannot collide with the HP bar or the quality panel.",
        [fps])


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
    _connect(BEL.find_then_pin(tick), _pin(br_m, "execute"))

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
    for i, (label, level, shadow, screen_pct) in enumerate(PRESETS):
        bx = x0 + 1500
        by = y0 + i * 420

        was = _at(_node(ed, FN_WAS_PRESSED), bx, by + 140)
        _connect(pc_out, _pin(was, "self"))
        _set(was, "Key", PRESET_KEYS[i])

        br = _at(ed.add_branch_node(), bx + 300, by)
        _connect(_pin(was, "ReturnValue", is_input=False), _pin(br, "Condition"))
        _connect(flow, _pin(br, "execute"))

        applied = _emit_apply(ed, i, bx + 500, by, BEL.find_then_pin(br))

        ed.add_comment_to_nodes(
            f"{PRESET_KEYS[i]} -> {label}: scalability {level}, "
            f"r.ShadowQuality {shadow}, r.ScreenPercentage {screen_pct}.",
            [was, br] + applied)

        # An unmatched key falls through to the next test.
        flow = _pin(br, "else", is_input=False)


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

    back = _at(_node(ed, FN_DRAW_RECT), x0 + 760, y0)
    _set(back, "RectColor", COL_HP_BACK)
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"), HP_BAR):
        _set(back, name, value)
    _connect(BEL.find_then_pin(cast), _pin(back, "execute"))

    # Same rect, but its width is driven rather than set: the empty part of the
    # bar is the background showing through.
    fill = _at(_node(ed, FN_DRAW_RECT), x0 + 1000, y0)
    _set(fill, "RectColor", COL_HP_FILL)
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
    _connect(_pin(as_text, "ReturnValue", is_input=False), _pin(number, "Text"))
    _connect(BEL.find_then_pin(label), _pin(number, "execute"))

    ed.add_comment_to_nodes(
        "Always drawn.  Health is rounded for display only -- the bar reads the "
        "unrounded value, so chip damage still moves it.",
        [pawn, comp, cast, health, max_health, frac, fill_w,
         back, fill, label, rounded, as_text, number])
    return (BEL.find_then_pin(number), _pin(cast, "CastFailed", is_input=False))


def _author_stamina(ed, x0, y0, in_execs):
    """The sprint bar, directly under the HP bar.

    Read off BP_WeaponComponent rather than off the health component: that is
    where sprint lives (it is the thing that has to refuse to fire while the key
    is held), and this HUD already casts to it for the inventory strip anyway.

    The fill changes colour while the key is down, which is the cheapest way to
    answer the only question a stamina bar is ever asked mid-fight -- "is it
    going down because I am sprinting, or did I stop and it is coming back?"
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 260))
    _set(pawn, "PlayerIndex", 0)
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 260))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)

    cast = keep(_at(_palette(ed, NODE_CAST_WEAPON), x0 + 500, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    def var(name, py):
        n = keep(_at(ed.add_get_member_variable_node(name, WEAPON_COMP_CLASS_PATH),
                     x0 + 760, py))
        _connect(as_weapon, _pin(n, "self"))
        return _pin(n, name, is_input=False)

    stamina = var("Stamina", y0 + 260)
    max_stamina = var("MaxStamina", y0 + 400)
    sprinting = var("Sprinting", y0 + 540)

    frac = keep(_at(_node(ed, FN_DIV), x0 + 1000, y0 + 320))
    _connect(stamina, _pin(frac, "A"))
    _connect(max_stamina, _pin(frac, "B"))
    fill_w = keep(_at(_node(ed, FN_MUL), x0 + 1200, y0 + 320))
    _connect(_pin(frac, "ReturnValue", is_input=False), _pin(fill_w, "A"))
    _set(fill_w, "B", ST_BAR[2])

    back = keep(_at(_node(ed, FN_DRAW_RECT), x0 + 760, y0))
    _set(back, "RectColor", COL_ST_BACK)
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"), ST_BAR):
        _set(back, name, value)
    _connect(BEL.find_then_pin(cast), _pin(back, "execute"))

    tint = keep(_at(_node(ed, FN_SELECT_COLOR), x0 + 1000, y0 + 560))
    _set(tint, "A", COL_ST_SPENT)
    _set(tint, "B", COL_ST_FILL)
    _connect(sprinting, _pin(tint, "bPickA"))

    fill = keep(_at(_node(ed, FN_DRAW_RECT), x0 + 1000, y0))
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"), ST_BAR):
        _set(fill, name, value)
    _connect(_pin(fill_w, "ReturnValue", is_input=False), _pin(fill, "ScreenW"))
    _connect(_pin(tint, "ReturnValue", is_input=False), _pin(fill, "RectColor"))
    _connect(BEL.find_then_pin(back), _pin(fill, "execute"))

    label = keep(_at(_node(ed, FN_DRAW_TEXT), x0 + 1240, y0))
    _set(label, "Text", "STA")
    _set(label, "TextColor", COL_ST_LABEL)
    _set(label, "ScreenX", ST_LABEL_POS[0])
    _set(label, "ScreenY", ST_LABEL_POS[1])
    _set(label, "Scale", ST_LABEL_SCALE)
    _set(label, "bScalePosition", "false")
    _connect(BEL.find_then_pin(fill), _pin(label, "execute"))

    ed.add_comment_to_nodes(
        "Stamina, under the HP bar. The fill goes amber while the sprint key is "
        "held and back to blue while it refills, so a bar that is moving always "
        "says which way it is going.",
        made)
    return (BEL.find_then_pin(label), _pin(cast, "CastFailed", is_input=False))


def _author_kills(ed, x0, y0, in_execs):
    """The kill counter, top right, under the engine's fps readout.

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
    _connect(BEL.find_then_pin(cast), _pin(text, "execute"))

    ed.add_comment_to_nodes(
        f"Kills, {KILL_RIGHT_MARGIN:.0f} px in from the right edge and "
        f"{KILL_TOP:.0f} px down -- clear of the engine's own `stat fps` line, "
        "which owns the very top of that corner and is not drawn on this canvas.",
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

    # Safe to fold into one AND: both halves are arithmetic on values already
    # read, so pulling both costs two comparisons and has no side effect. (The
    # NPC melee gate could not do this -- there, one half of the AND dragged a
    # whole location chain behind it. See the pure-node note in CLAUDE.md.)
    showing = _at(_node(ed, FN_AND), x0 + 2120, y0 + 800)
    _connect(_pin(in_front, "ReturnValue", is_input=False), _pin(showing, "A"))
    _connect(_pin(recent, "ReturnValue", is_input=False), _pin(showing, "B"))

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

    back = _at(_node(ed, FN_DRAW_RECT), x0 + 2640, y0)
    _set(back, "RectColor", COL_NPC_BACK)
    _set(back, "ScreenW", NPC_BAR[0])
    _set(back, "ScreenH", NPC_BAR[1])
    _connect(left_out, _pin(back, "ScreenX"))
    _connect(top_out, _pin(back, "ScreenY"))
    _connect(BEL.find_then_pin(visible), _pin(back, "execute"))

    fill = _at(_node(ed, FN_DRAW_RECT), x0 + 2900, y0)
    _set(fill, "RectColor", COL_NPC_FILL)
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

    number = _at(_node(ed, FN_DRAW_TEXT), x0 + 3160, y0)
    _connect(_pin(nid_str, "ReturnValue", is_input=False), _pin(number, "Text"))
    _set(number, "TextColor", COL_NPC_ID)
    _set(number, "Scale", NPC_ID_SCALE)
    _connect(_pin(id_x, "ReturnValue", is_input=False), _pin(number, "ScreenX"))
    _connect(_pin(id_y, "ReturnValue", is_input=False), _pin(number, "ScreenY"))
    _connect(BEL.find_then_pin(fill), _pin(number, "execute"))

    ed.add_comment_to_nodes(
        f"One bar per wanderer, and only for {NPC_BAR_SECONDS:.0f}s after "
        "something hurt it -- hidden by default. GetAllActorsOfClass every "
        "frame is not free, but the alternative -- a registry the NPCs write "
        "themselves into -- would need a graph on BP_ForestWanderer, which "
        "build_npc_blueprints.py owns.",
        [every, loop, comp, cast, health, max_health, where, above, proj, parts,
         in_front, hurt_at, now, since, recent, showing, visible, left, frac,
         fill_w, back, fill, nid, nid_str, id_x, id_y, number])
    return (_loose_pin(loop, "Completed", is_input=False),)


def _author_inventory(ed, x0, y0, in_execs):
    """Five slots along the bottom, filled from the weapon component's Inventory.

    The strip is drawn from the viewport size rather than from fixed pixels so
    it stays centred and bottom-anchored at any window size -- DrawRect works in
    canvas pixels, which change with the window.
    """
    size = _at(_node(ed, FN_VIEWPORT), x0, y0 + 700)
    wh = _at(_node(ed, FN_BREAK_V2D), x0 + 240, y0 + 700)
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))

    strip_w = INVENTORY_SIZE * SLOT_W + (INVENTORY_SIZE - 1) * SLOT_GAP
    half = _at(_node(ed, FN_MUL), x0 + 480, y0 + 700)
    _connect(_pin(wh, "X", is_input=False), _pin(half, "A"))
    _set(half, "B", 0.5)
    origin_x = _at(_node(ed, FN_SUB), x0 + 720, y0 + 700)
    _connect(_pin(half, "ReturnValue", is_input=False), _pin(origin_x, "A"))
    _set(origin_x, "B", strip_w / 2.0)
    x_out = _pin(origin_x, "ReturnValue", is_input=False)

    row_y = _at(_node(ed, FN_SUB), x0 + 720, y0 + 840)
    _connect(_pin(wh, "Y", is_input=False), _pin(row_y, "A"))
    _set(row_y, "B", SLOT_H + SLOT_BOTTOM)
    y_out = _pin(row_y, "ReturnValue", is_input=False)

    made = [size, wh, half, origin_x, row_y]

    def slot_x(index, px, py):
        """origin_x + index * (SLOT_W + SLOT_GAP), as a node chain."""
        n = _at(_node(ed, FN_ADD), px, py)
        _connect(x_out, _pin(n, "A"))
        _set(n, "B", index * (SLOT_W + SLOT_GAP))
        made.append(n)
        return _pin(n, "ReturnValue", is_input=False)

    # Five empty slots first, so the strip is visible even with nothing carried
    # and even if the weapon component is missing entirely.
    flow = None
    for i in range(INVENTORY_SIZE):
        r = _at(_node(ed, FN_DRAW_RECT), x0 + 1000 + i * 240, y0)
        _set(r, "RectColor", COL_SLOT_BACK)
        _set(r, "ScreenW", SLOT_W)
        _set(r, "ScreenH", SLOT_H)
        _connect(slot_x(i, x0 + 1000 + i * 240, y0 + 300), _pin(r, "ScreenX"))
        _connect(y_out, _pin(r, "ScreenY"))
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

    # The slot's X is index-driven, so one draw covers all five positions
    # instead of five unrolled copies with baked-in coordinates.
    as_float = _at(_node(ed, FN_CONV_INT), x0 + 3700, y0 + 520)
    _connect(index, _pin(as_float, "InInt"))
    step = _at(_node(ed, FN_MUL), x0 + 3940, y0 + 520)
    _connect(_pin(as_float, "ReturnValue", is_input=False), _pin(step, "A"))
    _set(step, "B", SLOT_W + SLOT_GAP)
    at_x = _at(_node(ed, FN_ADD), x0 + 4180, y0 + 520)
    _connect(x_out, _pin(at_x, "A"))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(at_x, "B"))
    at_x_out = _pin(at_x, "ReturnValue", is_input=False)

    colour = _at(ed.add_get_member_variable_node("SlotColor", ITEM_CLASS_PATH),
                 x0 + 3700, y0 + 660)
    _connect(item, _pin(colour, "self"))
    name = _at(ed.add_get_member_variable_node("DisplayName", ITEM_CLASS_PATH),
               x0 + 3700, y0 + 780)
    _connect(item, _pin(name, "self"))

    fill = _at(_node(ed, FN_DRAW_RECT), x0 + 4420, y0)
    _connect(_pin(colour, "SlotColor", is_input=False), _pin(fill, "RectColor"))
    _set(fill, "ScreenW", SLOT_W)
    _set(fill, "ScreenH", SLOT_H)
    _connect(at_x_out, _pin(fill, "ScreenX"))
    _connect(y_out, _pin(fill, "ScreenY"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(fill, "execute"))

    label_x = _at(_node(ed, FN_ADD), x0 + 4420, y0 + 520)
    _connect(at_x_out, _pin(label_x, "A"))
    _set(label_x, "B", 8.0)
    label_y = _at(_node(ed, FN_ADD), x0 + 4420, y0 + 640)
    _connect(y_out, _pin(label_y, "A"))
    _set(label_y, "B", SLOT_H - 24.0)

    label = _at(_node(ed, FN_DRAW_TEXT), x0 + 4680, y0)
    _connect(_pin(name, "DisplayName", is_input=False), _pin(label, "Text"))
    _set(label, "TextColor", COL_SLOT_NAME)
    _set(label, "Scale", SLOT_NAME_SCALE)
    _set(label, "bScalePosition", "false")
    _connect(_pin(label_x, "ReturnValue", is_input=False), _pin(label, "ScreenX"))
    _connect(_pin(label_y, "ReturnValue", is_input=False), _pin(label, "ScreenY"))
    _connect(BEL.find_then_pin(fill), _pin(label, "execute"))

    # --- the equipped slot gets an underline --------------------------------
    is_equipped = _at(_node(ed, FN_EQ_II), x0 + 4680, y0 + 520)
    _connect(index, _pin(is_equipped, "A"))
    _connect(_pin(equipped, "EquippedIndex", is_input=False), _pin(is_equipped, "B"))
    marked = _at(ed.add_branch_node(), x0 + 4940, y0)
    _connect(_pin(is_equipped, "ReturnValue", is_input=False), _pin(marked, "Condition"))
    _connect(BEL.find_then_pin(label), _pin(marked, "execute"))

    mark_y = _at(_node(ed, FN_ADD), x0 + 4940, y0 + 520)
    _connect(y_out, _pin(mark_y, "A"))
    _set(mark_y, "B", SLOT_H - SLOT_MARK_H)
    mark = _at(_node(ed, FN_DRAW_RECT), x0 + 5200, y0)
    _set(mark, "RectColor", COL_SLOT_MARK)
    _set(mark, "ScreenW", SLOT_W)
    _set(mark, "ScreenH", SLOT_MARK_H)
    _connect(at_x_out, _pin(mark, "ScreenX"))
    _connect(_pin(mark_y, "ReturnValue", is_input=False), _pin(mark, "ScreenY"))
    _connect(BEL.find_then_pin(marked), _pin(mark, "execute"))

    ed.add_comment_to_nodes(
        "Each carried weapon paints its own SlotColor and DisplayName into its "
        "slot, and the equipped one gets the underline. Reading the weapon's "
        "own properties means the HUD needs no table of weapon names to keep "
        "in step with BP_Shotgun and BP_Pistol.",
        [pawn, comp, cast, inv, equipped, loop, as_float, step, at_x, colour,
         name, fill, label_x, label_y, label, is_equipped, marked, mark_y, mark])

    # A pawn with no weapon component still has to reach the menu below.
    return (_loose_pin(loop, "Completed", is_input=False),
            _pin(cast, "CastFailed", is_input=False))


def _author_reticle(ed, x0, y0, in_execs):
    """A crosshair pinned to the centre of the screen.

    It was briefly drawn at the projected impact point instead, on the theory
    that a reticle should sit on the thing about to be hit. In practice that
    reticle will not hold still: the impact point is a world position on
    whatever surface the ray lands on, so it slides as the player walks, jumps
    between a near trunk and the ground behind it, and shifts under its own
    parallax. A crosshair that moves is unusable -- you aim with it by holding
    it still and turning the camera, which only works if it is nailed down.

    Fixed at the centre is also *correct* here, not a compromise: the aim ray is
    cast from the camera along its forward vector, and the camera's forward
    vector is the centre of the screen. AimPoint is still where the shot lands;
    the reticle just no longer tries to follow it around.

    What is kept from the impact point is the one thing worth showing: the
    crosshair turns red when the muzzle's line is blocked short of what the
    camera can see, so a barrel against a tree reads as such without moving.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 300))
    _set(pawn, "PlayerIndex", 0)
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 300))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)

    cast = keep(_at(_palette(ed, NODE_CAST_WEAPON), x0 + 500, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    valid = keep(_at(ed.add_get_member_variable_node("AimValid",
                                                     WEAPON_COMP_CLASS_PATH),
                     x0 + 760, y0 + 300))
    _connect(as_weapon, _pin(valid, "self"))
    blocked = keep(_at(ed.add_get_member_variable_node("AimBlocked",
                                                       WEAPON_COMP_CLASS_PATH),
                       x0 + 760, y0 + 420))
    _connect(as_weapon, _pin(blocked, "self"))

    # Empty hands draw nothing: a reticle with no weapon behind it points at a
    # shot that cannot be taken.
    armed = keep(_at(ed.add_branch_node(), x0 + 1020, y0))
    _connect(_pin(valid, "AimValid", is_input=False), _pin(armed, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(armed, "execute"))

    # Centre from the viewport, not from a constant: DrawRect works in canvas
    # pixels, which change with the window.
    size = keep(_at(_node(ed, FN_VIEWPORT), x0 + 1020, y0 + 560))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 1260, y0 + 560))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))

    def half(axis, py):
        n = keep(_at(_node(ed, FN_MUL), x0 + 1500, py))
        _connect(_loose_pin(wh, axis, is_input=False), _pin(n, "A"))
        _set(n, "B", 0.5)
        return _pin(n, "ReturnValue", is_input=False)

    cx = half("X", y0 + 560)
    cy = half("Y", y0 + 700)

    colour = keep(_at(_node(ed, FN_SELECT_COLOR), x0 + 1500, y0 + 840))
    _set(colour, "A", COL_RETICLE_BLOCKED)
    _set(colour, "B", COL_RETICLE)
    _connect(_pin(blocked, "AimBlocked", is_input=False), _pin(colour, "bPickA"))
    colour_out = _pin(colour, "ReturnValue", is_input=False)

    def offset(src, by, px, py):
        """centre + by, as a node -- DrawRect wants the corner, we have the middle."""
        n = keep(_at(_node(ed, FN_ADD), px, py))
        _connect(src, _pin(n, "A"))
        _set(n, "B", by)
        return _pin(n, "ReturnValue", is_input=False)

    half_t = RETICLE_THICK / 2.0
    half_d = RETICLE_DOT / 2.0
    inner = RETICLE_GAP
    outer = RETICLE_GAP + RETICLE_ARM
    # (name, dx, dy, w, h) of each piece relative to the centre of the screen.
    pieces = (
        ("left",   -outer,   -half_t,  RETICLE_ARM,   RETICLE_THICK),
        ("right",   inner,   -half_t,  RETICLE_ARM,   RETICLE_THICK),
        ("top",    -half_t,  -outer,   RETICLE_THICK, RETICLE_ARM),
        ("bottom", -half_t,   inner,   RETICLE_THICK, RETICLE_ARM),
        ("dot",    -half_d,  -half_d,  RETICLE_DOT,   RETICLE_DOT),
    )

    flow = BEL.find_then_pin(armed)
    for i, (name, dx, dy, w, h) in enumerate(pieces):
        px = x0 + 1800 + i * 260
        r = keep(_at(_node(ed, FN_DRAW_RECT), px, y0))
        _set(r, "ScreenW", w)
        _set(r, "ScreenH", h)
        _connect(colour_out, _pin(r, "RectColor"))
        _connect(offset(cx, dx, px, y0 + 300), _pin(r, "ScreenX"))
        _connect(offset(cy, dy, px, y0 + 440), _pin(r, "ScreenY"))
        _connect(flow, _pin(r, "execute"))
        flow = BEL.find_then_pin(r)

    ed.add_comment_to_nodes(
        "Reticle, nailed to the centre of the viewport. The aim ray is cast "
        "along the camera's forward vector, and that *is* the centre of the "
        "screen, so this is where the shot goes -- it turns red when the muzzle "
        "cannot reach what the camera is looking at.",
        made)

    return (flow,
            BEL.find_else_pin(armed),
            _pin(cast, "CastFailed", is_input=False))


# ─── Event ReceiveDrawHUD: the panel ─────────────────────────────────────────

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

    panel = keep(_at(_node(ed, FN_DRAW_RECT), x0 + 1240, y0))
    _set(panel, "RectColor", COL_DEATH_PANEL)
    _set(panel, "ScreenW", DEATH_PANEL[0])
    _set(panel, "ScreenH", DEATH_PANEL[1])
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

    alive = _at(ed.add_branch_node(), x0 - 180, y0)
    dead_get = _at(ed.add_get_member_variable_node(PLAYER_DEAD_VAR,
                                                   GAME_MODE_CLASS_PATH),
                   x0 - 440, y0 + 240)
    _connect(mode_out, _pin(dead_get, "self"))
    _connect(_pin(dead_get, PLAYER_DEAD_VAR, is_input=False), _pin(alive, "Condition"))
    _connect(BEL.find_then_pin(as_mode), _pin(alive, "execute"))

    _author_death_menu(ed, x0 + 3000, y0 + 3000,
                       (BEL.find_then_pin(alive),), mode_out)

    # A GameMode that is not BP_ThirdPersonGameMode cannot say whether the
    # player is dead, so it is treated as alive and the HUD draws as normal --
    # a missing death menu is recoverable, a missing HUD is not.
    living = (BEL.find_else_pin(alive),
              _pin(as_mode, "CastFailed", is_input=False))

    # HP first, so it is on screen whether or not the menu is open.
    after_hp = _author_hp(ed, x0, y0 - 900, living)
    after_st = _author_stamina(ed, x0, y0 - 1600, after_hp)
    after_kills = _author_kills(ed, x0, y0 - 2300, after_st)

    # Then the world-space NPC bars and the inventory strip, both of which are
    # always on screen for the same reason the HP bar is.
    after_npc = _author_npc_bars(ed, x0, y0 - 3200, after_kills)
    after_inv = _author_inventory(ed, x0, y0 - 5000, after_npc)

    # Last of the always-on layers, so the crosshair sits on top of the rest.
    after_aim = _author_reticle(ed, x0, y0 - 6800, after_inv)

    get_open = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 240, y0 + 200)
    br = _at(ed.add_branch_node(), x0 + 420, y0)
    _connect(_pin(get_open, "MenuOpen", is_input=False), _pin(br, "Condition"))
    # Every path above -- drawn or cast-failed -- falls through to the menu; an
    # exec input takes more than one link, so no Sequence node is needed.
    for exec_out in after_aim:
        _connect(exec_out, _pin(br, "execute"))

    rect = _at(_node(ed, FN_DRAW_RECT), x0 + 640, y0)
    _set(rect, "RectColor", COL_PANEL)
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"), PANEL):
        _set(rect, name, value)
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
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        made.append(n)
        return n

    text("GRAPHICS QUALITY", TITLE_POS[0], TITLE_POS[1], TITLE_SCALE, COL_TITLE,
         x0 + 860, y0)
    for i, (label, _lvl, _sq, _sp) in enumerate(PRESETS):
        text(f"[{i + 1}]   {label}", ROW_X, ROW_Y0 + i * ROW_STEP, ROW_SCALE,
             COL_ROW, x0 + 1080 + i * 220, y0)
    text(f"[{MENU_KEY}]   close", HINT_POS[0], HINT_POS[1], HINT_SCALE, COL_HINT,
         x0 + 1740, y0)

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

    caret = text(">", CARET_X, ROW_Y0, ROW_SCALE, COL_CARET, x0 + 1960, y0)
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
    for path in ("/Game/Weapons/BP_HealthComponent",
                 "/Game/Weapons/BP_WeaponComponent",
                 "/Game/Weapons/BP_WeaponItem",
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
    _apply_defaults(bp, {"MenuOpen": False, "Quality": DEFAULT_PRESET})
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
