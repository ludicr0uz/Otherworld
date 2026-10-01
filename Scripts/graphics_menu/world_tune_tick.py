"""The WORLD TUNING tab's HUD Tick fragment: the tab's keys, nudge and save
(tune_tick.author_tab_flow, shared with GUN and MONSTER TUNING), then the
table onto the level's day/night cycle.

    its M panel row taken   WorldTuneOpen = NOT WorldTuneOpen; the other tabs shut
    WorldTuneOpen, and the level has a BP_DayNightCycle (GetActorOfClass, cast):
      WorldTuneTouched      DayLengthSeconds, NightLengthSeconds,
                            NightTemperatureDropPerSecond := the table's
      Values[0] != HourSeen a nudge moved the hour: Clock := hour_to_clock
      always                Values[0] := HourSeen := clock_to_hour(Clock)

The hour row shows the cycle's live clock on a 24-hour dial (sunrise 06:00,
sunset 18:00, whatever the lengths: world_config.clock_to_hour does the same
sums). It is read back every Tick the tab is open, so a nudge steps from the
hour on screen, and the difference from HourSeen is what tells a nudge from
time passing. Only while open: nothing else moves the table.
"""

import unreal

from combat.graph import BEL, _at, _connect, _declare, _float_type, _loose_pin, _palette, _pin
from combat.nodes import FN_ADD_FF, FN_ARR_GET
from graphics_menu.dev_guns import _branch, _call, _class_literal, _get, _out
from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.loot_find import put
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.tune_tick import FN_ARR_SET, author_tab_flow, declare_tab_vars, tab_defaults
from graphics_menu.world_tune_consts import (
    WORLD_SUBJECT, WORLD_TAB, WORLD_TUNE_HOUR_SEEN_VAR,
)
from world import world_config as cfg
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world.world_tuning import WORLD_STATS

KML = "/Script/Engine.KismetMathLibrary"
FN_PERCENT_FF = f"{KML}.Percent_FloatFloat"
FN_MAP_CLAMPED = f"{KML}.MapRangeClamped"
FN_NEQ_FF = f"{KML}.NotEqual_DoubleDouble"
FN_ACTOR_OF_CLASS = "/Script/Engine.GameplayStatics.GetActorOfClass"
NODE_CAST_CYCLE = "Utilities|Casting|CastToBP_DayNightCycle"


def declare_world_tune_vars(ed):
    declare_tab_vars(ed, WORLD_TAB)
    _declare(ed, WORLD_TUNE_HOUR_SEEN_VAR, _float_type())


def world_tune_defaults():
    """The built lengths and night cold; the hour cell and HourSeen both 0 until the tab
    first opens and reads the live clock."""
    values = [0.0, float(cfg.DAY_LENGTH_S), float(cfg.NIGHT_LENGTH_S),
              float(cfg.NIGHT_TEMPERATURE_DROP_PER_S)]
    if len(values) != len(WORLD_STATS):
        raise RuntimeError(f"{len(values)} built values for {len(WORLD_STATS)} WORLD_STATS")
    return {**tab_defaults(WORLD_TAB, [WORLD_SUBJECT], values,
                           [float(s[3]) for s in WORLD_STATS],
                           [float(s[4]) for s in WORLD_STATS]),
            WORLD_TUNE_HOUR_SEEN_VAR: 0.0}


def _value(ed, s, x, y, made):
    """WorldTuneValues[s], a literal index."""
    cell = _call(ed, FN_ARR_GET, x + 240, y, made,
                 TargetArray=_get(ed, WORLD_TAB.values_var, x, y, made), Index=s)
    return _pin(cell, "Item", is_input=False)


def _map(ed, value, in_a, in_b, out_a, out_b, x, y, made):
    """MapRangeClamped; each bound a literal or a pin."""
    return _out(_call(ed, FN_MAP_CLAMPED, x, y, made, Value=value, InRangeA=in_a,
                      InRangeB=in_b, OutRangeA=out_a, OutRangeB=out_b))


def _hour_to_clock(ed, hour, day, night, x, y, made):
    """phase = (hour - SUNRISE + 24) % 24; the day half maps 0..12 h onto
    0..day, the night half 12..24 h onto 0..night after it."""
    lifted = _call(ed, FN_ADD_FF, x, y, made, A=hour, B=24.0 - cfg.SUNRISE_HOUR)
    phase = _out(_call(ed, FN_PERCENT_FF, x + 240, y, made, A=_out(lifted), B=24.0))
    half = cfg.HALF_HOURS
    a = _map(ed, phase, 0.0, half, 0.0, day, x + 480, y, made)
    b = _map(ed, phase, half, 24.0, 0.0, night, x + 480, y + 300, made)
    return _out(_call(ed, FN_ADD_FF, x + 720, y, made, A=a, B=b))


def _clock_to_hour(ed, clock, day, night, x, y, made):
    """The inverse: 12 h across each half, then round the dial from sunrise."""
    total = _out(_call(ed, FN_ADD_FF, x, y + 300, made, A=day, B=night))
    a = _map(ed, clock, 0.0, day, 0.0, cfg.HALF_HOURS, x + 240, y, made)
    b = _map(ed, clock, day, total, 0.0, cfg.HALF_HOURS, x + 240, y + 300, made)
    phase = _call(ed, FN_ADD_FF, x + 480, y, made, A=a, B=b)
    shifted = _call(ed, FN_ADD_FF, x + 720, y, made, A=_out(phase), B=cfg.SUNRISE_HOUR)
    return _out(_call(ed, FN_PERCENT_FF, x + 960, y, made, A=_out(shifted), B=24.0))


def _set_on(ed, cyc, var, value, in_execs, x, y, made):
    n = _at(ed.add_set_member_variable_node(var, DAY_NIGHT_CLASS_PATH), x, y)
    made.append(n)
    _connect(cyc, _pin(n, "self"))
    _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    return BEL.find_then_pin(n)


def _author_apply(ed, in_execs, x0, y0, made):
    """The table onto the cycle, and its clock back (module docstring).
    Returns the exec tails."""
    on, shut = _branch(ed, _get(ed, WORLD_TAB.open_var, x0 - 240, y0 + 300, made),
                       in_execs, x0, y0, made)
    find = _call(ed, FN_ACTOR_OF_CLASS, x0 + 260, y0, made)
    _class_literal(find, "ActorClass", DAY_NIGHT_CLASS_PATH)
    _connect(on, _pin(find, "execute"))
    if not unreal.load_asset(DAY_NIGHT_BP_PATH):   # the cast exists only for a loaded class
        raise RuntimeError(f"{DAY_NIGHT_BP_PATH} is missing -- run build_day_night.py first")
    cast = _at(_palette(ed, NODE_CAST_CYCLE), x0 + 560, y0)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_DayNightCycle")
    made.append(cast)
    _connect(_out(find), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(find), _pin(cast, "execute"))
    cyc = _loose_pin(cast, "AsBPDayNightCycle", is_input=False)
    none = _pin(cast, "CastFailed", is_input=False)

    x = x0 + 900
    go, keep = _branch(ed, _get(ed, WORLD_TAB.touched_var, x - 240, y0 + 300, made),
                       [BEL.find_then_pin(cast)], x, y0, made)
    flow = go
    for s, (_col, var, *_rest) in enumerate(WORLD_STATS):
        if var:
            x += 600
            flow = _set_on(ed, cyc, var, _value(ed, s, x - 300, y0 + 440, made),
                           [flow], x, y0, made)

    x += 600
    day = _get(ed, "DayLengthSeconds", x, y0 + 900, made, DAY_NIGHT_CLASS_PATH, cyc)
    night = _get(ed, "NightLengthSeconds", x, y0 + 1040, made, DAY_NIGHT_CLASS_PATH, cyc)
    moved = _call(ed, FN_NEQ_FF, x, y0 + 300, made, A=_value(ed, 0, x - 480, y0 + 300, made),
                  B=_get(ed, WORLD_TUNE_HOUR_SEEN_VAR, x - 240, y0 + 440, made))
    write, same = _branch(ed, _out(moved), [flow, keep], x + 240, y0, made)
    clock = _hour_to_clock(ed, _value(ed, 0, x + 240, y0 + 600, made), day, night,
                           x + 480, y0 + 600, made)
    flow = _set_on(ed, cyc, "Clock", clock, [write], x + 1400, y0, made)

    x += 1800
    now = _get(ed, "Clock", x, y0 + 600, made, DAY_NIGHT_CLASS_PATH, cyc)
    hour = _clock_to_hour(ed, now, day, night, x + 240, y0 + 600, made)
    store = _call(ed, FN_ARR_SET, x + 1500, y0, made,
                  TargetArray=_get(ed, WORLD_TAB.values_var, x + 1260, y0 + 300, made),
                  Index=0)
    _connect(hour, _pin(store, "Item"))
    for e in (flow, same):
        _connect(e, _pin(store, "execute"))
    seen = put(ed, WORLD_TUNE_HOUR_SEEN_VAR, hour, [BEL.find_then_pin(store)],
               x + 1800, y0, made)
    return [seen, none, shut]


def author_world_tune_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, x0, y0, made, WORLD_TAB, 1,
                           (GUN_TAB.open_var, MONSTER_TAB.open_var,
                            GFX_TAB.open_var))
    tails = _author_apply(ed, flow, x0 + 10400, y0, made)
    ed.add_comment_to_nodes(
        "World tuning (its row in the M panel): Up/Down pick a row, "
        "Left/Right move the time of day or a length, Enter saves the lengths to "
        "world_tuning.csv. While open, the table goes onto the day/night cycle "
        "and the cycle's clock comes back as the hour.", made[:1])
    return tails
