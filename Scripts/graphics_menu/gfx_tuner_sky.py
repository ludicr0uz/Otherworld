"""BP_GraphicsTuner's sky fragment: the look stats that are the day/night
cycle's (gfx_stats.CYCLE) written onto the level's BP_DayNightCycle.

    the level has a BP_DayNightCycle (GetActorOfClass, cast):
        SunScale, SunDiscScale, MoonScale, MoonDiscScale, StarScale,
        AmbientScale, FogScale := the applied preset's numbers (percentages
        in the table, fractions here: gfx_tuner_read.applied)

The cycle multiplies its own sums by them every Tick (world/
day_night_graph.py), so a nudge shows on the next frame. A level without a
cycle fails the cast and keeps its static sky.
"""

import unreal

from combat.graph import BEL, _at, _connect, _loose_pin, _palette, _pin
from graphics_menu.dev_guns import _call, _class_literal, _out
from graphics_menu.gfx_stats import CYCLE, stats_by
from graphics_menu.gfx_tuner_read import applied
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH

FN_ACTOR_OF_CLASS = "/Script/Engine.GameplayStatics.GetActorOfClass"
NODE_CAST_CYCLE = "Utilities|Casting|CastToBP_DayNightCycle"


def author_sky(ed, in_execs, x0, y0, made):
    """The fragment (module docstring). Returns the exec tails."""
    if not unreal.load_asset(DAY_NIGHT_BP_PATH):   # the cast exists only for a loaded class
        raise RuntimeError(f"{DAY_NIGHT_BP_PATH} is missing -- run build_day_night.py first")
    find = _call(ed, FN_ACTOR_OF_CLASS, x0, y0, made)
    _class_literal(find, "ActorClass", DAY_NIGHT_CLASS_PATH)
    for e in in_execs:
        _connect(e, _pin(find, "execute"))
    cast = _at(_palette(ed, NODE_CAST_CYCLE), x0 + 300, y0)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_DayNightCycle")
    made.append(cast)
    _connect(_out(find), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(find), _pin(cast, "execute"))
    cycle = _loose_pin(cast, "AsBPDayNightCycle", is_input=False)

    flow, x = BEL.find_then_pin(cast), x0 + 700
    for index, st in stats_by(CYCLE):
        n = _at(ed.add_set_member_variable_node(st.target, DAY_NIGHT_CLASS_PATH), x + 600, y0)
        made.append(n)
        _connect(cycle, _pin(n, "self"))
        _connect(applied(ed, index, x - 300, y0 + 400, made), _pin(n, st.target))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        x += 900
    return [flow, _pin(cast, "CastFailed", is_input=False)]
