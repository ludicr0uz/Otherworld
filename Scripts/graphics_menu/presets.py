"""The quality presets and what picking one does.

Two graph fragments live here, both authored into BP_GraphicsMenuHUD by
build_graphics_menu.py:

  emit_apply          -- the chain one preset key (and BeginPlay) runs:
                         Set Quality -> scalability -> two console overrides.
  author_grass_sync   -- a Tick prologue that pushes the preset's grass
                         lighting onto every grass cell whenever Quality has
                         changed since it last ran.

Grass lighting cannot ride on the preset chain itself. There is no cvar for one
component's shadow, so it has to be set on the components -- and a level
always boots with the grass the way the import script saved it. Comparing
Quality with the value last applied puts that one fact in one place: the
startup preset, a key press and a level reload all converge through it.
"""

from collections import namedtuple

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from forest_generator.grass_cells import GRASS_TAG

# One preset, in menu order.
#
#   level        -- UE's scalability groups: 0 Low, 1 Medium, 2 High, 3 Epic.
#   shadow       -- r.ShadowQuality, set by console (see below).
#   screen_pct   -- r.ScreenPercentage.
#   grass_lights -- whether knee-high grass casts shadows and takes part in
#                   distance-field / Lumen lighting.
#
# "High" maps to Epic, not to 2, on purpose: Epic is what the project runs at
# (HardwareTargeting DefaultGraphicsPerformance=Maximum), and the top preset had
# to be the *current* look, not a downgrade of it. Ultra is that look plus the
# grass lighting -- the only thing it adds, which is also why it is the only
# preset that pays for it: 1.1 million shadow-casting clumps on the 1 km map
# are drawn again into every shadow cascade, for shadows a 0.12-lux moon makes
# nearly invisible.
#
# The two console commands are not redundant with the scalability level:
#
#   r.ShadowQuality  — Config/DefaultEngine.ini pins this to 3 under
#     [/Script/Engine.RendererSettings].  That is SetByProjectSetting priority,
#     which *outranks* SetByScalability, so SetOverallScalabilityLevel silently
#     cannot move it (the editor logs "was ignored as it is lower priority").
#     A console command is SetByConsole, which outranks both, so this is the
#     only way the menu can reach shadows.
#   r.ScreenPercentage — not part of any scalability group, and on a forest this
#     dense it is the single biggest GPU lever available.
Preset = namedtuple("Preset", "label level shadow screen_pct grass_lights")
PRESETS = (
    Preset("Low",    0, 1,  70, False),
    Preset("Medium", 1, 2,  85, False),
    Preset("High",   3, 3, 100, False),
    Preset("Ultra",  3, 3, 100, True),
)
# Keys 1-4.  UE's FKey names for the number row are One/Two/Three/Four.
#
# These go into the pin verbatim, NOT as struct text: FKey overrides
# ExportTextItem to write just the key name, so a pin set to '(KeyName="M")'
# imports back as a key literally called "(" -- it compiles, it saves, and the
# key silently never matches at runtime.
PRESET_KEYS = ("One", "Two", "Three", "Four")

# The preset every session starts at.  BeginPlay *applies* it rather than just
# setting the caret: the menu can only tell the truth about the current quality
# if it is the thing that established it.
DEFAULT_PRESET = 0  # Low

# The graph turns Quality into the grass flag with one comparison, which only
# describes the table above while the grass presets are a contiguous top run.
GRASS_LIGHTS_FROM = next(i for i, p in enumerate(PRESETS) if p.grass_lights)
assert all(p.grass_lights == (i >= GRASS_LIGHTS_FROM) for i, p in enumerate(PRESETS)), \
    "grass-lit presets must be the top of the list"

# The Quality the grass was last set up for. -1 is no preset, so the first Tick
# of every session always applies -- a level saved by an older import script
# is corrected the moment it loads.
GRASS_APPLIED_VAR = "GrassQualityApplied"
GRASS_APPLIED_DEFAULT = -1

# What the grass flag switches, one PrimitiveComponent setter each.
GRASS_SETTERS = (
    ("/Script/Engine.PrimitiveComponent.SetCastShadow", "NewCastShadow"),
    ("/Script/Engine.PrimitiveComponent.SetAffectDistanceFieldLighting",
     "NewAffectDistanceFieldLighting"),
    ("/Script/Engine.PrimitiveComponent.SetAffectDynamicIndirectLighting",
     "bNewAffectDynamicIndirectLighting"),
)

FN_CONSOLE = "/Script/Engine.KismetSystemLibrary.ExecuteConsoleCommand"
FN_GET_GUS = "/Script/Engine.GameUserSettings.GetGameUserSettings"
FN_SET_OVERALL = "/Script/Engine.GameUserSettings.SetOverallScalabilityLevel"
FN_APPLY = "/Script/Engine.GameUserSettings.ApplyNonResolutionSettings"
FN_WITH_TAG = "/Script/Engine.GameplayStatics.GetAllActorsWithTag"
FN_ROOT = "/Script/Engine.Actor.K2_GetRootComponent"
FN_NEQ_II = "/Script/Engine.KismetMathLibrary.NotEqual_IntInt"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
NODE_CAST_PRIMITIVE = "Utilities|Casting|CastToPrimitiveComponent"
MACRO_FOR_EACH = ("/Engine/EditorBlueprintResources/StandardMacros"
                  ".StandardMacros:ForEachLoop")


def console_commands(preset):
    """The console overrides a preset issues, in order."""
    return (f"r.ShadowQuality {preset.shadow}",
            f"r.ScreenPercentage {preset.screen_pct}")


# ─── One preset, applied ─────────────────────────────────────────────────────

def emit_apply(ed, index, x, y, in_exec):
    """Emit the chain that applies preset ``index`` and hook it to ``in_exec``.

    Shared by BeginPlay (which applies the startup default) and by each preset
    key, so there is exactly one description of what picking a preset does.
    Returns the nodes it made, for the caller to wrap in a comment.
    """
    preset = PRESETS[index]

    set_q = _at(ed.add_set_member_variable_node("Quality"), x, y)
    _set(set_q, "Quality", index)
    _connect(in_exec, _pin(set_q, "execute"))

    gus = _at(_node(ed, FN_GET_GUS), x + 200, y)
    _connect(BEL.find_then_pin(set_q), _pin(gus, "execute"))
    gus_out = _pin(gus, "ReturnValue", is_input=False)

    sos = _at(_node(ed, FN_SET_OVERALL), x + 400, y)
    _connect(gus_out, _pin(sos, "self"))
    _set(sos, "Value", preset.level)
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
    for offset, command in enumerate(console_commands(preset)):
        c = _at(_node(ed, FN_CONSOLE), x + 840 + offset * 260, y)
        # WorldContextObject is a hidden pin the compiler fills from self, and a
        # null SpecificPlayer means "the first local player" -- which in a HUD
        # is always the player owning it.
        _set(c, "Command", command)
        _connect(flow, _pin(c, "execute"))
        flow = BEL.find_then_pin(c)
        made.append(c)
    return made


# ─── Tick prologue: grass lighting follows Quality ───────────────────────────

def author_grass_sync(ed, x0, y0, in_exec):
    """Re-light the grass cells when Quality differs from what they carry.

    Returns the exec pins the rest of Tick continues from. Costs one int
    compare on a frame where nothing changed; on a change it walks every
    actor tagged GRASS_TAG (about 900 on the 1 km map) once.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    def quality(px, py):
        q = keep(_at(ed.add_get_member_variable_node("Quality"), px, py))
        return _pin(q, "Quality", is_input=False)

    applied = keep(_at(ed.add_get_member_variable_node(GRASS_APPLIED_VAR),
                       x0, y0 + 340))
    stale = keep(_at(_node(ed, FN_NEQ_II), x0 + 240, y0 + 220))
    _connect(quality(x0, y0 + 220), _pin(stale, "A"))
    _connect(_pin(applied, GRASS_APPLIED_VAR, is_input=False), _pin(stale, "B"))
    changed = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(stale, "ReturnValue", is_input=False), _pin(changed, "Condition"))
    _connect(in_exec, _pin(changed, "execute"))

    cells = keep(_at(_node(ed, FN_WITH_TAG), x0 + 720, y0))
    _set(cells, "Tag", GRASS_TAG)
    _connect(BEL.find_then_pin(changed), _pin(cells, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 1000, y0))
    _connect(_pin(cells, "OutActors", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(cells), _loose_pin(loop, "Exec"))

    # Each cell is one HISM as its root. The cast is what SetCastShadow's
    # self pin needs; a tagged actor with some other root simply fails it.
    root = keep(_at(_node(ed, FN_ROOT), x0 + 1300, y0 + 260))
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(root, "self"))
    cast = keep(_at(_palette(ed, NODE_CAST_PRIMITIVE), x0 + 1540, y0))
    _connect(_pin(root, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    comp = _loose_pin(cast, "AsPrimitiveComponent", is_input=False)

    lit = keep(_at(_node(ed, FN_GE_II), x0 + 1540, y0 + 340))
    _connect(quality(x0 + 1300, y0 + 400), _pin(lit, "A"))
    _set(lit, "B", GRASS_LIGHTS_FROM)
    lit_out = _pin(lit, "ReturnValue", is_input=False)

    flow = BEL.find_then_pin(cast)
    for i, (fn, arg) in enumerate(GRASS_SETTERS):
        s = keep(_at(_node(ed, fn), x0 + 1820 + i * 280, y0))
        _connect(comp, _pin(s, "self"))
        _connect(lit_out, _pin(s, arg))
        _connect(flow, _pin(s, "execute"))
        flow = BEL.find_then_pin(s)

    done = keep(_at(ed.add_set_member_variable_node(GRASS_APPLIED_VAR),
                    x0 + 1300, y0 - 260))
    _connect(quality(x0 + 1060, y0 - 140), _pin(done, GRASS_APPLIED_VAR))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(done, "execute"))

    ultra = PRESETS[GRASS_LIGHTS_FROM].label
    ed.add_comment_to_nodes(
        f"Grass lighting follows Quality. When Quality differs from "
        f"{GRASS_APPLIED_VAR}, every actor tagged {GRASS_TAG} gets shadows, "
        f"distance-field and dynamic indirect lighting switched on for "
        f"{ultra} and off below it. The import script saves the grass unlit, "
        f"and {GRASS_APPLIED_VAR} starts at {GRASS_APPLIED_DEFAULT} so the "
        f"first Tick always applies.",
        made)
    return (BEL.find_then_pin(done), BEL.find_else_pin(changed))
