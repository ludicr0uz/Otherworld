"""BP_GraphicsTuner: the component on the HUD that turns one preset's row of
the graphics table (gfx_stats.GFX_STATS) into the engine's state. The HUD
only hands it the table (gfx_tune_tick.py); what a number does is here.

    Tick, when Dirty:
        Dirty := false; Base := Preset x STAT_COUNT
        engine quality moved   SetOverallScalabilityLevel, then
                               ApplyNonResolutionSettings
        every cvar stat        ExecuteConsoleCommand("<cvar> <number>")
        the foliage            gfx_tuner_foliage.py
        the sky                gfx_tuner_sky.py
        the wind               gfx_tuner_wind.py

The console commands are needed, and come after the scalability level.
Config/DefaultEngine.ini pins r.ShadowQuality (and the GI, reflection and
anti-aliasing methods) at project-setting priority, which outranks
scalability: SetOverallScalabilityLevel silently cannot move them. A console
command outranks both. r.ScreenPercentage is in no scalability group at all.

ApplyNonResolutionSettings, never ApplySettings: that one also applies
resolution, which on macOS drives SWindow::SetWindowMode and hangs the editor
in PIE at 100% CPU. The menu never changes resolution.

A component, not more HUD graph: the HUD's verifier reads every console
command, tag and Clamp in that graph as its own, and this is one owner for
"what a preset does".
"""

import unreal

from combat.graph import (
    BEL, BGE, _apply_defaults, _create_blueprint, _declare, _events, _float_type, _log,
    _pin,
)
from uebp.graph import out
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.gfx_stats import CVAR, LEVEL, STAT_COUNT, stats_by, table_values
from graphics_menu.gfx_tune_consts import (
    TUNER_BASE_VAR, TUNER_BP_PATH, TUNER_DIRTY_VAR, TUNER_GRASS_DISTANCE_APPLIED_VAR,
    TUNER_GRASS_LAYERS_APPLIED_VAR, TUNER_GRASS_SHADOWS_APPLIED_VAR,
    TUNER_LEVEL_APPLIED_VAR, TUNER_NEVER, TUNER_PRESET_VAR,
    TUNER_TREE_DISTANCE_APPLIED_VAR, TUNER_VALUES_VAR, TUNER_WIND_APPLIED_VAR,
    TUNER_WIND_DISTANCE_APPLIED_VAR,
)
from graphics_menu.gfx_tuner_foliage import FN_NEQ_II, author_foliage
from graphics_menu.gfx_tuner_read import applied, whole
from graphics_menu.gfx_tuner_sky import author_sky
from graphics_menu.gfx_tuner_wind import author_wind
from graphics_menu.loot_find import put

FN_MUL_II = "/Script/Engine.KismetMathLibrary.Multiply_IntInt"
FN_GET_GUS = "/Script/Engine.GameUserSettings.GetGameUserSettings"
FN_SET_OVERALL = "/Script/Engine.GameUserSettings.SetOverallScalabilityLevel"
FN_APPLY = "/Script/Engine.GameUserSettings.ApplyNonResolutionSettings"
FN_CONSOLE = "/Script/Engine.KismetSystemLibrary.ExecuteConsoleCommand"
FN_BUILD_FLOAT = "/Script/Engine.KismetStringLibrary.BuildString_Double"
FN_BUILD_INT = "/Script/Engine.KismetStringLibrary.BuildString_Int"

INT_VARS = (TUNER_PRESET_VAR, TUNER_BASE_VAR, TUNER_LEVEL_APPLIED_VAR,
            TUNER_GRASS_SHADOWS_APPLIED_VAR, TUNER_GRASS_LAYERS_APPLIED_VAR,
            TUNER_WIND_APPLIED_VAR, TUNER_WIND_DISTANCE_APPLIED_VAR)
FLOAT_VARS = (TUNER_GRASS_DISTANCE_APPLIED_VAR, TUNER_TREE_DISTANCE_APPLIED_VAR)


def tuner_defaults():
    return {TUNER_VALUES_VAR: table_values(), TUNER_PRESET_VAR: 0, TUNER_BASE_VAR: 0,
            TUNER_DIRTY_VAR: False, TUNER_LEVEL_APPLIED_VAR: TUNER_NEVER,
            TUNER_GRASS_SHADOWS_APPLIED_VAR: TUNER_NEVER,
            TUNER_GRASS_LAYERS_APPLIED_VAR: TUNER_NEVER,
            TUNER_WIND_APPLIED_VAR: TUNER_NEVER, TUNER_WIND_DISTANCE_APPLIED_VAR: TUNER_NEVER,
            TUNER_GRASS_DISTANCE_APPLIED_VAR: 1.0, TUNER_TREE_DISTANCE_APPLIED_VAR: 1.0}


def command_prefix(cvar):
    """What a cvar stat's command starts with; the number follows."""
    return f"{cvar} "


def _declare_vars(ed):
    _declare(ed, TUNER_VALUES_VAR, BEL.get_array_type(_float_type()))
    _declare(ed, TUNER_DIRTY_VAR, BEL.get_basic_type_by_name("bool"))
    for name in INT_VARS:
        _declare(ed, name, BEL.get_basic_type_by_name("int"))
    for name in FLOAT_VARS:
        _declare(ed, name, _float_type())


def _author_level(ed, in_execs, x0, y0, made):
    """The scalability level, when it moved. Returns the exec tails."""
    (index, _st), = stats_by(LEVEL)
    moved = _call(ed, FN_NEQ_II, x0, y0 + 300, made,
                  A=whole(ed, index, x0 - 980, y0 + 300, made),
                  B=_get(ed, TUNER_LEVEL_APPLIED_VAR, x0 - 240, y0 + 500, made))
    go, same = _branch(ed, out(moved), in_execs, x0 + 240, y0, made)
    gus = _call(ed, FN_GET_GUS, x0 + 520, y0, made)
    _connect_exec(go, gus)
    level = _call(ed, FN_SET_OVERALL, x0 + 820, y0, made, self=out(gus),
                  Value=whole(ed, index, x0 - 200, y0 + 700, made))
    _connect_exec(BEL.find_then_pin(gus), level)
    apply = _call(ed, FN_APPLY, x0 + 1120, y0, made, self=out(gus))
    _connect_exec(BEL.find_then_pin(level), apply)
    kept = put(ed, TUNER_LEVEL_APPLIED_VAR, whole(ed, index, x0 + 400, y0 + 1000, made),
               [BEL.find_then_pin(apply)], x0 + 1420, y0, made)
    return [kept, same]


def _connect_exec(src, node):
    if not src.try_create_connection(_pin(node, "execute")):
        raise RuntimeError("could not connect an exec pin")


def _author_cvars(ed, in_execs, x0, y0, made):
    """One console command per cvar stat: a whole number as an int, a
    percentage as the fraction the cvar takes. Returns the last then pin."""
    flow, x = None, x0
    for index, st in stats_by(CVAR):
        if st.kind is int and st.scale == 1:
            words = _call(ed, FN_BUILD_INT, x, y0 + 400, made,
                          Prefix=command_prefix(st.target),
                          InInt=whole(ed, index, x - 760, y0 + 600, made))
        else:
            words = _call(ed, FN_BUILD_FLOAT, x, y0 + 400, made,
                          Prefix=command_prefix(st.target),
                          InDouble=applied(ed, index, x - 760, y0 + 600, made))
        # WorldContextObject is a hidden pin the compiler fills from self, and
        # a null SpecificPlayer is the first local player.
        run = _call(ed, FN_CONSOLE, x + 300, y0, made, Command=out(words))
        for e in ([flow] if flow else in_execs):
            _connect_exec(e, run)
        flow = BEL.find_then_pin(run)
        x += 1100
    return flow


def _author_tick(ed, tick):
    made = []
    go, _idle = _branch(ed, _get(ed, TUNER_DIRTY_VAR, 60, 300, made),
                        [BEL.find_then_pin(tick)], 300, 0, made)
    flow = _setter(ed, TUNER_DIRTY_VAR, "false", [go], 560, 0, made)
    base = _call(ed, FN_MUL_II, 620, 300, made,
                 A=_get(ed, TUNER_PRESET_VAR, 380, 300, made), B=STAT_COUNT)
    flow = put(ed, TUNER_BASE_VAR, out(base), [flow], 860, 0, made)
    tails = _author_level(ed, [flow], 2200, 0, made)
    flow = _author_cvars(ed, tails, 5000, 0, made)
    tails = author_foliage(ed, [flow], 5000, 3000, made)
    tails = author_sky(ed, tails, 5000, 6000, made)
    author_wind(ed, tails, 5000, 9000, made)
    ed.add_comment_to_nodes(
        "A preset's row of the graphics table, applied when the HUD marks it "
        "Dirty: the scalability level, one console command per cvar stat, the "
        "grass and tree cells (gfx_tuner_foliage.py), the day/night cycle's "
        "look (gfx_tuner_sky.py), the wind (gfx_tuner_wind.py).", made[:1])


def build_graphics_tuner(rebuild=True):
    bp = _create_blueprint(TUNER_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, _begin = _events(ed, rebuild)
    _declare_vars(ed)
    _author_tick(ed, tick)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GraphicsTuner failed to compile")
    _apply_defaults(bp, tuner_defaults())       # recompiles and saves
    _log(f"built {TUNER_BP_PATH}")
    return bp
