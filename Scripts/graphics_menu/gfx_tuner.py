"""BP_GraphicsTuner: the component on the HUD that turns one preset's row of
the graphics table (gfx_stats.GFX_STATS) into the engine's state. The HUD
only hands it the table (gfx_tune_tick.py); what a number does is here.

    Tick, when Dirty:
        Dirty := false; Base := Preset x STAT_COUNT
        each engine quality    Set<Group>Quality on GameUserSettings, then
        group that moved       ApplyNonResolutionSettings
        every cvar stat        ExecuteConsoleCommand("<cvar> <number>")
        the foliage            gfx_tuner_foliage.py
        the sky                gfx_tuner_sky.py
        the wind               gfx_tuner_wind.py

A group is one section of BaseScalability.ini (gfx_stats.GROUP_STATS), and
moving it sets that section's cvars at scalability priority. The setter only
writes GameUserSettings' copy; ApplyNonResolutionSettings is what sets the
sg.* variable, and only where it differs (Scalability.cpp), so a group that
did not move is not applied again by the graph or by the engine.

The console commands are needed, and come after the groups.
Config/DefaultEngine.ini pins r.ShadowQuality (and the GI, reflection and
anti-aliasing methods) at project-setting priority, which outranks
scalability: a group silently cannot move them. A console command outranks
both, so a cvar that has a row is that row's from its first apply on, and
its group never moves it again: the row wins, and every row is sent on every
apply. The group still moves its other cvars (the ini section is applied
cvar by cvar). The sg.* variables themselves are never set by console here:
one that was would be out of GameUserSettings' reach for the session.
r.ScreenPercentage is in no scalability group at all.

ApplyNonResolutionSettings, never ApplySettings: that one also applies
resolution, which on macOS drives SWindow::SetWindowMode and hangs the editor
in PIE at 100% CPU. The menu never changes resolution.

A component, not more HUD graph: the HUD's verifier reads every console
command, tag and Clamp in that graph as its own, and this is one owner for
"what a preset does".
"""

from uebp.vars import declare, defaults
from graphics_menu.gfx_tune_consts import TUNER_TABLE
import unreal

from combat.log import _log
from uebp.graph import BEL, BGE, _apply_defaults, _create_blueprint, _events, _pin, out, then
from uebp.layout import arrange
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.gfx_stats import CVAR, GROUP, STAT_COUNT, stats_by, table_values
from graphics_menu.gfx_tune_consts import (
    TUNER_BASE_VAR, TUNER_BP_PATH, TUNER_DIRTY_VAR, TUNER_GROUP_APPLIED, TUNER_PRESET_VAR,
    TUNER_VALUES_VAR,
)
from graphics_menu.gfx_tuner_foliage import author_foliage
from graphics_menu.gfx_tuner_read import applied, whole
from graphics_menu.gfx_tuner_sky import author_sky
from graphics_menu.gfx_tuner_wind import author_wind
from graphics_menu.loot_find import put
from uebp.nodes.math import FN_MUL_II, FN_NEQ_II
from uebp.nodes import system
from uebp.nodes.system import FN_APPLY, FN_BUILD_FLOAT, FN_BUILD_INT, FN_CONSOLE, FN_GET_GUS

# A group stat's target is its setter's name: the catalog's path for it.
FN_SET_QUALITY_GROUP = {path.rsplit(".", 1)[-1]: path for name, path in vars(system).items()
                        if name.startswith("FN_SET_") and name.endswith("_QUALITY")}
assert all(st.target in FN_SET_QUALITY_GROUP for _i, st in stats_by(GROUP))


def tuner_defaults():
    return {**defaults(TUNER_TABLE), TUNER_VALUES_VAR: table_values()}


def command_prefix(cvar):
    """What a cvar stat's command starts with; the number follows."""
    return f"{cvar} "


def _declare_vars(bp, ed):
    """The table's variables, and none an older build left (LevelApplied,
    from when one engine quality row set every group)."""
    for name in BEL.list_member_variable_names(bp, False):
        if str(name) not in TUNER_TABLE:
            ed.remove_member_variable(str(name))
    declare(ed, TUNER_TABLE)


def _author_groups(ed, in_execs, made):
    """Each engine quality group, when it moved. Returns the exec tails."""
    tails = in_execs
    for index, st in stats_by(GROUP):
        kept_var = TUNER_GROUP_APPLIED[st.column]
        moved = _call(ed, FN_NEQ_II, made,
                      A=whole(ed, index, made), B=_get(ed, kept_var, made))
        go, same = _branch(ed, out(moved), tails, made)
        gus = _call(ed, FN_GET_GUS, made)
        _connect_exec(go, gus)
        level = _call(ed, FN_SET_QUALITY_GROUP[st.target], made, self=out(gus),
                      Value=whole(ed, index, made))
        _connect_exec(then(gus), level)
        apply = _call(ed, FN_APPLY, made, self=out(gus))
        _connect_exec(then(level), apply)
        kept = put(ed, kept_var, whole(ed, index, made), [then(apply)], made)
        tails = [kept, same]
    return tails


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
    tails = _author_groups(ed, [flow], made)
    flow = _author_cvars(ed, tails, made)
    tails = author_foliage(ed, [flow], made)
    tails = author_sky(ed, tails, made)
    author_wind(ed, tails, made)
    ed.add_comment_to_nodes(
        "A preset's row of the graphics table, applied when the HUD marks it "
        "Dirty: each engine quality group that moved, one console command per cvar stat, the "
        "grass and tree cells (gfx_tuner_foliage.py), the day/night cycle's "
        "look (gfx_tuner_sky.py), the wind (gfx_tuner_wind.py).", made[:1])


def build_graphics_tuner(rebuild=True):
    bp = _create_blueprint(TUNER_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, _begin = _events(ed, rebuild)
    _declare_vars(bp, ed)
    _author_tick(ed, tick)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GraphicsTuner failed to compile")
    _apply_defaults(bp, tuner_defaults())       # recompiles and saves
    _log(f"built {TUNER_BP_PATH}")
    return bp
