"""BP_GraphicsTuner's wind fragment: whether the grass and the trees move,
how far off they still do, and how hard and fast (forest_generator/wind.py
has what moves; forest_import/wind.py puts it in the materials).

    wind or wind distance moved
        every actor whose root is an instanced mesh (the grass, bush and
        tree cells): SetEvaluateWorldPositionOffset(wind >= 1) and
        SetWorldPositionOffsetDisableDistance(wind distance m x 100)
    always (the apply is already only on a change)
        MPC_Wind.Strength := wind strength % x 0.01 x wind
        MPC_Wind.Speed    := wind speed % x 0.01

Off is per component, not a zero strength alone: a component that does not
evaluate WPO skips the material's offset, so its cost goes with it. The
strength is zeroed too, so anything the walk missed stands still as well.
Past the distance an instance stands still (and Nanite stops evaluating its
WPO); it is plain metres from the camera, not scaled by the view distance.

The walk is every actor, as the tree walk is (the trees carry no tag), and
runs only when one of its two numbers moved. A level loads with the cells
as the import saved them (WPO on, no disable distance) and a new tuner has
nothing applied, so a reload converges through the same walk.
"""

import unreal

from combat.graph import _connect, _pin
from combat.nodes import FN_MUL_FF
from forest_generator.wind import MPC_NAME, MPC_PATH
from graphics_menu.dev_guns import _branch, _call, _class_literal, _get, _out
from graphics_menu.gfx_stats import WIND_PARAM, stats_by
from graphics_menu.gfx_tune_consts import (
    TUNER_WIND_APPLIED_VAR, TUNER_WIND_DISTANCE_APPLIED_VAR,
)
from graphics_menu.gfx_tuner_foliage import (
    ACTOR_CLASS_PATH, FN_ALL_OF_CLASS, FN_GE_II, FN_INT_TO_FLOAT, FN_NEQ_II, _for_each,
    _root_mesh,
)
from graphics_menu.gfx_tuner_read import applied, column
from graphics_menu.loot_find import put

KML = "/Script/Engine.KismetMathLibrary"
FN_MUL_II = f"{KML}.Multiply_IntInt"
FN_OR_BB = f"{KML}.BooleanOR"
SMC = "/Script/Engine.StaticMeshComponent"
FN_SET_WPO = f"{SMC}.SetEvaluateWorldPositionOffset"
FN_SET_WPO_DISTANCE = f"{SMC}.SetWorldPositionOffsetDisableDistance"
FN_SET_MPC_SCALAR = "/Script/Engine.KismetMaterialLibrary.SetScalarParameterValue"
MPC_OBJECT_PATH = f"{MPC_PATH}.{MPC_NAME}"
CM_PER_M = 100


def _distance_cm(ed, x, y, made):
    return _out(_call(ed, FN_MUL_II, x + 520, y, made,
                      A=column(ed, "wind_distance", x, y, made, rounded=True), B=CM_PER_M))


def _author_walk(ed, in_execs, x0, y0, made):
    """Every cell's WPO switch and distance, when either moved. Returns the
    exec tails."""
    on = _call(ed, FN_NEQ_II, x0, y0 + 300, made,
               A=column(ed, "wind", x0 - 980, y0 + 300, made, rounded=True),
               B=_get(ed, TUNER_WIND_APPLIED_VAR, x0 - 240, y0 + 500, made))
    far = _call(ed, FN_NEQ_II, x0, y0 + 700, made,
                A=column(ed, "wind_distance", x0 - 980, y0 + 700, made, rounded=True),
                B=_get(ed, TUNER_WIND_DISTANCE_APPLIED_VAR, x0 - 240, y0 + 900, made))
    moved = _call(ed, FN_OR_BB, x0 + 240, y0 + 300, made, A=_out(on), B=_out(far))
    go, same = _branch(ed, _out(moved), in_execs, x0 + 480, y0, made)

    actors = _call(ed, FN_ALL_OF_CLASS, x0 + 760, y0, made)
    _class_literal(actors, "ActorClass", ACTOR_CLASS_PATH)
    _connect(go, _pin(actors, "execute"))
    actor, body, done = _for_each(ed, _pin(actors, "OutActors", is_input=False),
                                  _pin(actors, "then", is_input=False), x0 + 1060, y0, made)
    comp, flow = _root_mesh(ed, actor, body, x0 + 1360, y0, made)
    wpo = _call(ed, FN_SET_WPO, x0 + 2000, y0, made, self=comp,
                NewValue=_out(_call(ed, FN_GE_II, x0 + 1700, y0 + 500, made,
                                    A=column(ed, "wind", x0 + 700, y0 + 500, made,
                                             rounded=True), B=1)))
    _connect(flow, _pin(wpo, "execute"))
    reach = _call(ed, FN_SET_WPO_DISTANCE, x0 + 2300, y0, made, self=comp,
                  NewValue=_distance_cm(ed, x0 + 1200, y0 + 800, made))
    _connect(_pin(wpo, "then", is_input=False), _pin(reach, "execute"))

    kept = put(ed, TUNER_WIND_APPLIED_VAR,
               column(ed, "wind", x0 + 1000, y0 - 600, made, rounded=True), [done],
               x0 + 1500, y0 - 700, made)
    kept = put(ed, TUNER_WIND_DISTANCE_APPLIED_VAR,
               column(ed, "wind_distance", x0 + 1500, y0 - 600, made, rounded=True),
               [kept], x0 + 2000, y0 - 700, made)
    return [kept, same]


def _author_params(ed, in_execs, x0, y0, made):
    """MPC_Wind's scalars, one SetScalarParameterValue each. Returns then."""
    on = _out(_call(ed, FN_INT_TO_FLOAT, x0, y0 + 900, made,
                    InInt=column(ed, "wind", x0 - 980, y0 + 900, made, rounded=True)))
    flow, x = in_execs, x0
    for index, st in stats_by(WIND_PARAM):
        value = applied(ed, index, x - 760, y0 + 500, made)
        if st.target == "Strength":
            value = _out(_call(ed, FN_MUL_FF, x + 200, y0 + 700, made, A=value, B=on))
        s = _call(ed, FN_SET_MPC_SCALAR, x + 500, y0, made,
                  ParameterName=st.target, ParameterValue=value)
        _class_literal(s, "Collection", MPC_OBJECT_PATH)
        for e in flow:
            _connect(e, _pin(s, "execute"))
        flow = [_pin(s, "then", is_input=False)]
        x += 1200
    return flow


def author_wind(ed, in_execs, x0, y0, made):
    """The whole fragment (module docstring). Returns the exec tails."""
    if not unreal.load_asset(MPC_PATH):    # an object literal needs the asset
        raise RuntimeError(f"{MPC_PATH} is missing -- run forest_import/wind.py first")
    flow = _author_walk(ed, in_execs, x0, y0, made)
    return _author_params(ed, flow, x0 + 3200, y0, made)
