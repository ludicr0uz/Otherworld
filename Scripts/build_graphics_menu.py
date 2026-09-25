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
                       SetOverallScalabilityLevel -> ApplySettings ->
                       ConsoleCommand r.ShadowQuality -> ConsoleCommand r.ScreenPercentage

  [Event ReceiveDrawHUD] --> [Branch: MenuOpen]
                                True --> DrawRect(panel) --> DrawText x5
                                         (the caret's ScreenY is computed from
                                          Quality, so it tracks the selection)
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

# The preset every session starts at.  BeginPlay *applies* it rather than just
# setting the caret: the menu can only tell the truth about the current quality
# if it is the thing that established it.
DEFAULT_PRESET = 0  # Low

# ─── Panel geometry (HUD canvas pixels, top-left origin) ─────────────────────
# Fixed coordinates rather than viewport-relative ones: centring would need the
# DrawHUD event's SizeX/SizeY through int->float conversion nodes for every
# coordinate, which triples the node count of the draw graph to move a box that
# is legible where it is.
PANEL = (60.0, 60.0, 600.0, 300.0)   # x, y, w, h
TITLE_POS = (92.0, 88.0)
TITLE_SCALE = 2.2
ROW_X = 150.0
ROW_Y0 = 168.0
ROW_STEP = 46.0
ROW_SCALE = 2.0
CARET_X = 112.0
HINT_POS = (92.0, 312.0)
HINT_SCALE = 1.5

COL_PANEL = "(R=0.020000,G=0.025000,B=0.035000,A=0.780000)"
COL_TITLE = "(R=0.850000,G=0.900000,B=1.000000,A=1.000000)"
COL_ROW = "(R=0.720000,G=0.750000,B=0.800000,A=1.000000)"
COL_CARET = "(R=1.000000,G=0.820000,B=0.320000,A=1.000000)"
COL_HINT = "(R=0.480000,G=0.510000,B=0.560000,A=1.000000)"

# ─── Function paths for the graph nodes ──────────────────────────────────────

FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_CONSOLE = "/Script/Engine.KismetSystemLibrary.ExecuteConsoleCommand"
FN_GET_GUS = "/Script/Engine.GameUserSettings.GetGameUserSettings"
FN_SET_OVERALL = "/Script/Engine.GameUserSettings.SetOverallScalabilityLevel"
FN_APPLY = "/Script/Engine.GameUserSettings.ApplySettings"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_CONV_INT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_DRAW_RECT = "/Script/Engine.HUD.DrawRect"
FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"

# The DrawHUD event is not one of the placeholder nodes a fresh Blueprint ships
# with (BeginPlay and Tick are), so it has to be created from the palette.
NODE_DRAW_HUD = "AddEvent|EventReceiveDrawHUD"
NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"

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
    _pin(node, name).set_pin_value(str(value))


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

    app = _at(_node(ed, FN_APPLY), x + 620, y)
    _connect(gus_out, _pin(app, "self"))
    # False: command-line overrides would re-clamp the level we just picked.
    _set(app, "bCheckForCommandLineOverrides", "false")
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


# ─── Event ReceiveDrawHUD: the panel ─────────────────────────────────────────

def _author_draw(ed, x0, y0):
    draw = ed.create_node_from_name(NODE_DRAW_HUD, unreal.Vector2D(x0, y0), [])
    if not draw:
        raise RuntimeError(f"could not create {NODE_DRAW_HUD}")

    get_open = _at(ed.add_get_member_variable_node("MenuOpen"), x0 + 240, y0 + 200)
    br = _at(ed.add_branch_node(), x0 + 420, y0)
    _connect(_pin(get_open, "MenuOpen", is_input=False), _pin(br, "Condition"))
    _connect(BEL.find_then_pin(draw), _pin(br, "execute"))

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
