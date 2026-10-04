"""The WORLD SETTINGS tab's HUD Tick fragment: the tab's keys, nudge and save
(tune_tick.author_tab_flow, shared with GUN and MONSTER SETTINGS), then the
table onto the level's day/night cycle.

    its M panel row taken   WorldTuneOpen = NOT WorldTuneOpen; the other tabs shut
    WorldTuneOpen OR WorldTuneTouched, and the level has a BP_DayNightCycle
    (GetActorOfClass, cast):
      WorldTuneTouched      DayLengthSeconds, NightLengthSeconds,
                            NightTemperatureDropPerSecond, ItemHighlight
                            := the table's
      Values[0] != HourSeen a nudge moved the hour: Clock := hour_to_clock
      always                Values[0] := HourSeen := clock_to_hour(Clock)

The hour row shows the cycle's live clock on a 24-hour dial (sunrise 06:00,
sunset 18:00, whatever the lengths: world_config.clock_to_hour does the same
sums). It is read back every Tick the tab is open, so a nudge steps from the
hour on screen, and the difference from HourSeen is what tells a nudge from
time passing. While open, or once touched: a nudge touches it, and so does a
table loaded from the player's save (tune_keep.py), which has to reach the
cycle with the tab shut. Nothing else moves the table.
"""

import unreal

from uebp.graph import (
    BEL, _connect, _declare, _float_type, _loose_pin, _palette, _pin, out, then)
from graphics_menu.dev_guns import _branch, _call, _class_literal, _get
from graphics_menu.loot_find import put
from graphics_menu.tune_tabs import other_open_vars
from graphics_menu.tune_tick import author_tab_flow, declare_tab_vars, tab_defaults
from graphics_menu.world_tune_consts import (
    WORLD_SUBJECT, WORLD_TAB, WORLD_TUNE_HOUR_SEEN_VAR,
)
from world import world_config as cfg
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world.world_tuning import WORLD_MAXS, WORLD_STATS
from uebp.nodes.array import FN_ARR_GET, FN_ARR_SET
from uebp.nodes.math import FN_ADD_FF, FN_MAP_CLAMPED, FN_NEQ_FF, FN_OR, FN_PERCENT_FF
from uebp.nodes.palette import NODE_CAST_CYCLE
from uebp.nodes.system import FN_ACTOR_OF_CLASS
from world import day_night_vars as DV


def declare_world_tune_vars(ed):
    declare_tab_vars(ed, WORLD_TAB)
    _declare(ed, WORLD_TUNE_HOUR_SEEN_VAR, _float_type())


def world_tune_defaults():
    """The built lengths, night cold and item highlight; the hour cell and HourSeen
    both 0 until the tab first opens and reads the live clock."""
    values = [0.0, float(cfg.DAY_LENGTH_S), float(cfg.NIGHT_LENGTH_S),
              float(cfg.NIGHT_TEMPERATURE_DROP_PER_S), float(cfg.ITEM_HIGHLIGHT)]
    if len(values) != len(WORLD_STATS):
        raise RuntimeError(f"{len(values)} built values for {len(WORLD_STATS)} WORLD_STATS")
    return {**tab_defaults(WORLD_TAB, [WORLD_SUBJECT], values,
                           [float(s[3]) for s in WORLD_STATS],
                           [float(s[4]) for s in WORLD_STATS]),
            WORLD_TAB.maxs_var: [float(m) for m in WORLD_MAXS],
            WORLD_TUNE_HOUR_SEEN_VAR: 0.0}


def _value(ed, s, made):
    """WorldTuneValues[s], a literal index."""
    cell = _call(ed, FN_ARR_GET, made, TargetArray=_get(ed, WORLD_TAB.values_var, made), Index=s)
    return out(cell, "Item")


def _map(ed, value, in_a, in_b, out_a, out_b, made):
    """MapRangeClamped; each bound a literal or a pin."""
    return out(_call(ed, FN_MAP_CLAMPED, made, Value=value, InRangeA=in_a,
                      InRangeB=in_b, OutRangeA=out_a, OutRangeB=out_b))


def _hour_to_clock(ed, hour, day, night, made):
    """phase = (hour - SUNRISE + 24) % 24; the day half maps 0..12 h onto
    0..day, the night half 12..24 h onto 0..night after it."""
    lifted = _call(ed, FN_ADD_FF, made, A=hour, B=24.0 - cfg.SUNRISE_HOUR)
    phase = out(_call(ed, FN_PERCENT_FF, made, A=out(lifted), B=24.0))
    half = cfg.HALF_HOURS
    a = _map(ed, phase, 0.0, half, 0.0, day, made)
    b = _map(ed, phase, half, 24.0, 0.0, night, made)
    return out(_call(ed, FN_ADD_FF, made, A=a, B=b))


def _clock_to_hour(ed, clock, day, night, made):
    """The inverse: 12 h across each half, then round the dial from sunrise."""
    total = out(_call(ed, FN_ADD_FF, made, A=day, B=night))
    a = _map(ed, clock, 0.0, day, 0.0, cfg.HALF_HOURS, made)
    b = _map(ed, clock, day, total, 0.0, cfg.HALF_HOURS, made)
    phase = _call(ed, FN_ADD_FF, made, A=a, B=b)
    shifted = _call(ed, FN_ADD_FF, made, A=out(phase), B=cfg.SUNRISE_HOUR)
    return out(_call(ed, FN_PERCENT_FF, made, A=out(shifted), B=24.0))


def _set_on(ed, cyc, var, value, in_execs, made):
    n = ed.add_set_member_variable_node(var, DAY_NIGHT_CLASS_PATH)
    made.append(n)
    _connect(cyc, _pin(n, "self"))
    _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    return then(n)


def _author_apply(ed, in_execs, made):
    """The table onto the cycle, and its clock back (module docstring).
    Returns the exec tails."""
    live = _call(ed, FN_OR, made, A=_get(ed, WORLD_TAB.open_var, made),
                 B=_get(ed, WORLD_TAB.touched_var, made))
    on, shut = _branch(ed, out(live), in_execs, made)
    find = _call(ed, FN_ACTOR_OF_CLASS, made)
    _class_literal(find, "ActorClass", DAY_NIGHT_CLASS_PATH)
    _connect(on, _pin(find, "execute"))
    if not unreal.load_asset(DAY_NIGHT_BP_PATH):   # the cast exists only for a loaded class
        raise RuntimeError(f"{DAY_NIGHT_BP_PATH} is missing -- run build_day_night.py first")
    cast = _palette(ed, NODE_CAST_CYCLE)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_DayNightCycle")
    made.append(cast)
    _connect(out(find), _pin(cast, "Object"))
    _connect(then(find), _pin(cast, "execute"))
    cyc = _loose_pin(cast, "AsBPDayNightCycle", is_input=False)
    none = out(cast, "CastFailed")

    go, keep = _branch(ed, _get(ed, WORLD_TAB.touched_var, made), [then(cast)], made)
    flow = go
    for s, (_col, var, *_rest) in enumerate(WORLD_STATS):
        if var:
            flow = _set_on(ed, cyc, var, _value(ed, s, made), [flow], made)

    day = _get(ed, DV.DayLengthSeconds, made, DAY_NIGHT_CLASS_PATH, cyc)
    night = _get(ed, DV.NightLengthSeconds, made, DAY_NIGHT_CLASS_PATH, cyc)
    moved = _call(ed, FN_NEQ_FF, made, A=_value(ed, 0, made),
                  B=_get(ed, WORLD_TUNE_HOUR_SEEN_VAR, made))
    write, same = _branch(ed, out(moved), [flow, keep], made)
    clock = _hour_to_clock(ed, _value(ed, 0, made), day, night, made)
    flow = _set_on(ed, cyc, DV.Clock, clock, [write], made)

    now = _get(ed, DV.Clock, made, DAY_NIGHT_CLASS_PATH, cyc)
    hour = _clock_to_hour(ed, now, day, night, made)
    store = _call(ed, FN_ARR_SET, made, TargetArray=_get(ed, WORLD_TAB.values_var, made), Index=0)
    _connect(hour, _pin(store, "Item"))
    for e in (flow, same):
        _connect(e, _pin(store, "execute"))
    seen = put(ed, WORLD_TUNE_HOUR_SEEN_VAR, hour, [then(store)], made)
    return [seen, none, shut]


def author_world_tune_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, made, WORLD_TAB, 1, other_open_vars(WORLD_TAB))
    tails = _author_apply(ed, flow, made)
    ed.add_comment_to_nodes(
        "World tuning (its row in the M panel): Up/Down pick a row, "
        "Left/Right move the time of day, a length or a switch, Enter saves all but "
        "the hour to world_tuning.csv. While open, the table goes onto the day/night cycle "
        "and the cycle's clock comes back as the hour.", made[:1])
    return tails
