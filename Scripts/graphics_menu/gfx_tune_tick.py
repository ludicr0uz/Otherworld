"""The GRAPHICS TUNING tab's HUD Tick fragment: the tab's keys, nudge and save
(tune_tick.author_tab_flow, shared with the other tabs), then the preset and
the table handed to BP_GraphicsTuner, the HUD's component that applies them.

    its M panel row taken      GfxTuneOpen = NOT GfxTuneOpen; the other tabs shut
    GfxTunePick != PickSeen    Left / Right on the preset row moved the pick:
                               Quality := GfxTunePick
    else                       GfxTunePick := Quality (BeginPlay set it)
    GfxTuneTouched             every look stat (gfx_stats.LOOK_FROM and up) of
                               the picked preset is copied into the other
                               presets' rows: the look is one for all four
    GfxTuneTouched, or         the tuner's Values := GfxTuneValues, its Preset
    Quality != GfxQualityApplied   := Quality, its Dirty := true; unless this
                               is the session's first hand-over, the pick and
                               the table into the player's save (gfx_save.py);
                               then GfxQualityApplied := Quality, NOT
                               GfxTuneTouched

So BeginPlay only sets Quality (presets.emit_apply: the CSV's default, then
gfx_save's load over it), and this is the one place a preset reaches the
engine: BeginPlay's Quality, the tab's preset row and a nudge all converge
through GfxQualityApplied, which starts at -1 so the first Tick of every
session applies. That first hand-over is what was just loaded, so it is not
saved again; every later one is a change the player made, and is.

The pick follows Quality rather than the other way round on a Tick where
neither moved, so the tab always shows the preset that is running.
"""

from combat.graph import (
    BEL, _add_component, _at, _connect, _declare, _drop_components, _loose_pin,
    _must_load, _pin, _root_handle,
)
from combat.nodes import FN_ADD_II, FN_ARR_GET, FN_MOD_II, FN_OR, MACRO_FOR_LOOP
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.gfx_save import author_keep_graphics
from graphics_menu.gfx_stats import (
    GFX_STATS, LOOK_FROM, PRESET_LABELS, STAT_COUNT, table_values,
)
from graphics_menu.gfx_tune_consts import (
    GFX_APPLIED_DEFAULT, GFX_APPLIED_VAR, GFX_TAB,
    GFX_TUNE_PICK_SEEN_VAR, TUNER_BP_PATH, TUNER_CLASS_PATH, TUNER_COMPONENT,
    TUNER_DIRTY_VAR, TUNER_PRESET_VAR, TUNER_VALUES_VAR,
)
from graphics_menu.loot_find import put
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.tune_tick import (
    FN_ARR_SET, FN_GE_II, FN_MUL_II, author_tab_flow, declare_tab_vars, tab_defaults,
)
from graphics_menu.world_tune_consts import WORLD_TAB

FN_NEQ_II = "/Script/Engine.KismetMathLibrary.NotEqual_IntInt"


def install_tuner(bp):
    """The HUD's BP_GraphicsTuner component (gfx_tuner.py builds the class)."""
    _drop_components(bp, {TUNER_COMPONENT})
    _add_component(bp, _root_handle(bp), BEL.generated_class(_must_load(TUNER_BP_PATH)),
                   TUNER_COMPONENT)


def declare_gfx_tune_vars(ed):
    declare_tab_vars(ed, GFX_TAB)
    for name in (GFX_TUNE_PICK_SEEN_VAR, GFX_APPLIED_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("int"))


def gfx_tune_defaults():
    """The built table (so graphics_tuning.csv), on the startup preset, with
    nothing handed to the tuner yet."""
    return {**tab_defaults(GFX_TAB, list(PRESET_LABELS), table_values(),
                           [float(s.step) for s in GFX_STATS],
                           [float(s.lo) for s in GFX_STATS]),
            GFX_TAB.maxs_var: [float(s.hi) for s in GFX_STATS],
            GFX_TUNE_PICK_SEEN_VAR: 0, GFX_APPLIED_VAR: GFX_APPLIED_DEFAULT}


def _author_pick(ed, in_execs, x0, y0, made):
    """The pick and Quality kept as one (module docstring). Returns then."""
    moved = _call(ed, FN_NEQ_II, x0, y0 + 300, made,
                  A=_get(ed, GFX_TAB.pick_var, x0 - 240, y0 + 300, made),
                  B=_get(ed, GFX_TUNE_PICK_SEEN_VAR, x0 - 240, y0 + 440, made))
    picked, followed = _branch(ed, _out(moved), in_execs, x0 + 240, y0, made)
    picked = put(ed, "Quality", _get(ed, GFX_TAB.pick_var, x0 + 260, y0 - 200, made),
                 [picked], x0 + 520, y0 - 300, made)
    followed = put(ed, GFX_TAB.pick_var, _get(ed, "Quality", x0 + 260, y0 + 500, made),
                   [followed], x0 + 520, y0 + 300, made)
    return put(ed, GFX_TUNE_PICK_SEEN_VAR,
               _get(ed, GFX_TAB.pick_var, x0 + 560, y0 + 700, made), [picked, followed],
               x0 + 820, y0, made)


def _author_spread(ed, in_execs, x0, y0, made):
    """Touched: the picked preset's look stats into every preset's row.
    Returns the exec tails."""
    go, idle = _branch(ed, _get(ed, GFX_TAB.touched_var, x0 - 240, y0 + 300, made),
                       in_execs, x0, y0, made)
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    made.append(_at(loop, x0 + 260, y0))
    _loose_pin(loop, "FirstIndex").set_pin_value("0")
    _loose_pin(loop, "LastIndex").set_pin_value(str(len(PRESET_LABELS) * STAT_COUNT - 1))
    _connect(go, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)
    s = _out(_call(ed, FN_MOD_II, x0 + 560, y0 + 300, made, A=i, B=STAT_COUNT))
    look = _call(ed, FN_GE_II, x0 + 800, y0 + 300, made, A=s, B=LOOK_FROM)
    copy, _skip = _branch(ed, _out(look), [_pin(loop, "LoopBody", is_input=False)],
                          x0 + 1040, y0, made)
    base = _call(ed, FN_MUL_II, x0 + 800, y0 + 600, made,
                 A=_get(ed, GFX_TAB.pick_var, x0 + 560, y0 + 600, made), B=STAT_COUNT)
    source = _call(ed, FN_ADD_II, x0 + 1040, y0 + 600, made, A=_out(base), B=s)
    cell = _call(ed, FN_ARR_GET, x0 + 1280, y0 + 600, made,
                 TargetArray=_get(ed, GFX_TAB.values_var, x0 + 1040, y0 + 800, made))
    _connect(_out(source), _pin(cell, "Index"))
    write = _call(ed, FN_ARR_SET, x0 + 1560, y0, made,
                  TargetArray=_get(ed, GFX_TAB.values_var, x0 + 1300, y0 + 300, made))
    _connect(i, _pin(write, "Index"))
    _connect(_pin(cell, "Item", is_input=False), _pin(write, "Item"))
    _connect(copy, _pin(write, "execute"))
    return [_pin(loop, "Completed", is_input=False), idle]


def _author_hand_over(ed, in_execs, x0, y0, made):
    """Touched or a new Quality: the table and the preset onto the tuner.
    Returns the exec tails."""
    new = _call(ed, FN_NEQ_II, x0 - 240, y0 + 500, made,
                A=_get(ed, "Quality", x0 - 480, y0 + 500, made),
                B=_get(ed, GFX_APPLIED_VAR, x0 - 480, y0 + 640, made))
    stale = _call(ed, FN_OR, x0, y0 + 300, made,
                  A=_get(ed, GFX_TAB.touched_var, x0 - 240, y0 + 300, made), B=_out(new))
    go, idle = _branch(ed, _out(stale), in_execs, x0 + 240, y0, made)
    tuner = _get(ed, TUNER_COMPONENT, x0 + 260, y0 + 500, made)
    flow = [go]
    for i, (var, source) in enumerate(((TUNER_VALUES_VAR, GFX_TAB.values_var),
                                       (TUNER_PRESET_VAR, "Quality"))):
        n = _at(ed.add_set_member_variable_node(var, TUNER_CLASS_PATH),
                x0 + 560 + i * 320, y0)
        made.append(n)
        _connect(tuner, _pin(n, "self"))
        _connect(_get(ed, source, x0 + 300 + i * 320, y0 + 700, made), _pin(n, var))
        for e in flow:
            _connect(e, _pin(n, "execute"))
        flow = [BEL.find_then_pin(n)]
    flow = _setter(ed, TUNER_DIRTY_VAR, "true", flow, x0 + 1200, y0, made,
                   TUNER_CLASS_PATH, tuner)
    # Read before GfxQualityApplied is written below: -1 is the session's
    # first hand-over, which is the save itself (or the defaults).
    again = _call(ed, FN_NEQ_II, x0 + 1480, y0 + 300, made,
                  A=_get(ed, GFX_APPLIED_VAR, x0 + 1240, y0 + 300, made),
                  B=GFX_APPLIED_DEFAULT)
    keep, first = _branch(ed, _out(again), [flow], x0 + 1720, y0, made)
    kept = author_keep_graphics(ed, [keep], x0 + 2000, y0 - 700, made)
    flow = put(ed, GFX_APPLIED_VAR, _get(ed, "Quality", x0 + 3500, y0 + 300, made),
               [*kept, first], x0 + 3760, y0, made)
    done = _setter(ed, GFX_TAB.touched_var, "false", [flow], x0 + 4040, y0, made)
    return [done, idle]


def author_gfx_tune_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, x0, y0, made, GFX_TAB,
                           len(PRESET_LABELS),
                           (GUN_TAB.open_var, MONSTER_TAB.open_var, WORLD_TAB.open_var))
    flow = [_author_pick(ed, flow, x0 + 10400, y0, made)]
    flow = _author_spread(ed, flow, x0 + 11800, y0, made)
    tails = _author_hand_over(ed, flow, x0 + 14200, y0, made)
    ed.add_comment_to_nodes(
        f"Graphics tuning (its row in the M panel): Up/Down pick a row, "
        f"Left/Right change the preset or a number, SAVE DEFAULT saves "
        f"graphics_tuning.csv. The preset and its numbers go to the {TUNER_COMPONENT} "
        f"component, which applies them, whenever Quality or a number moved; the "
        f"pick and the Custom row are kept in the player's save.", made[:1])
    return tails
