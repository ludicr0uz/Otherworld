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

from combat.log import _log
from uebp.graph import (
    BEL, BGE, _apply_defaults, _create_blueprint, _declare, _events, _float_type, _pin, out,
    then)
from uebp.layout import arrange
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.gfx_stats import CVAR, LEVEL, STAT_COUNT, stats_by, table_values
from graphics_menu.gfx_tune_consts import (
    TUNER_BASE_VAR, TUNER_BP_PATH, TUNER_DIRTY_VAR, TUNER_GRASS_DISTANCE_APPLIED_VAR,
    TUNER_GRASS_LAYERS_APPLIED_VAR, TUNER_GRASS_SHADOWS_APPLIED_VAR,
    TUNER_LEVEL_APPLIED_VAR, TUNER_NEVER, TUNER_PRESET_VAR,
    TUNER_TREE_DISTANCE_APPLIED_VAR, TUNER_VALUES_VAR, TUNER_WIND_APPLIED_VAR,
    TUNER_WIND_DISTANCE_APPLIED_VAR,
)
from graphics_menu.gfx_tuner_foliage import author_foliage
from graphics_menu.gfx_tuner_read import applied, whole
from graphics_menu.gfx_tuner_sky import author_sky
from graphics_menu.gfx_tuner_wind import author_wind
from graphics_menu.loot_find import put
from uebp.nodes.math import FN_MUL_II, FN_NEQ_II
from uebp.nodes.system import (
    FN_APPLY, FN_BUILD_FLOAT, FN_BUILD_INT, FN_CONSOLE, FN_GET_GUS, FN_SET_OVERALL)


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


def _author_level(ed, in_execs, made):
    """The scalability level, when it moved. Returns the exec tails."""
    (index, _st), = stats_by(LEVEL)
    moved = _call(ed, FN_NEQ_II, made,
                  A=whole(ed, index, made),
                  B=_get(ed, TUNER_LEVEL_APPLIED_VAR, made))
    go, same = _branch(ed, out(moved), in_execs, made)
    gus = _call(ed, FN_GET_GUS, made)
    _connect_exec(go, gus)
    level = _call(ed, FN_SET_OVERALL, made, self=out(gus), Value=whole(ed, index, made))
    _connect_exec(then(gus), level)
    apply = _call(ed, FN_APPLY, made, self=out(gus))
    _connect_exec(then(level), apply)
    kept = put(ed, TUNER_LEVEL_APPLIED_VAR, whole(ed, index, made), [then(apply)], made)
    return [kept, same]


def _connect_exec(src, node):
    if not src.try_create_connection(_pin(node, "execute")):
        raise RuntimeError("could not connect an exec pin")


def _author_cvars(ed, in_execs, made):
    """One console command per cvar stat: a whole number as an int, a
    percentage as the fraction the cvar takes. Returns the last then pin."""
    flow = None
    for index, st in stats_by(CVAR):
        if st.kind is int and st.scale == 1:
            words = _call(ed, FN_BUILD_INT, made,
                          Prefix=command_prefix(st.target),
                          InInt=whole(ed, index, made))
        else:
            words = _call(ed, FN_BUILD_FLOAT, made,
                          Prefix=command_prefix(st.target),
                          InDouble=applied(ed, index, made))
        # WorldContextObject is a hidden pin the compiler fills from self, and
        # a null SpecificPlayer is the first local player.
        run = _call(ed, FN_CONSOLE, made, Command=out(words))
        for e in ([flow] if flow else in_execs):
            _connect_exec(e, run)
        flow = then(run)
    return flow


def _author_tick(ed, tick):
    made = []
    go, _idle = _branch(ed, _get(ed, TUNER_DIRTY_VAR, made), [then(tick)], made)
    flow = _setter(ed, TUNER_DIRTY_VAR, "false", [go], made)
    base = _call(ed, FN_MUL_II, made, A=_get(ed, TUNER_PRESET_VAR, made), B=STAT_COUNT)
    flow = put(ed, TUNER_BASE_VAR, out(base), [flow], made)
    tails = _author_level(ed, [flow], made)
    flow = _author_cvars(ed, tails, made)
    tails = author_foliage(ed, [flow], made)
    tails = author_sky(ed, tails, made)
    author_wind(ed, tails, made)
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
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GraphicsTuner failed to compile")
    _apply_defaults(bp, tuner_defaults())       # recompiles and saves
    _log(f"built {TUNER_BP_PATH}")
    return bp
