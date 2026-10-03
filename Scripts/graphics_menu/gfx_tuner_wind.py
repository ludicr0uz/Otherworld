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

from uebp.graph import _connect, _pin, out
from combat.nodes import FN_MUL_FF
from forest_generator.wind import MPC_NAME, MPC_PATH
from graphics_menu.dev_guns import _branch, _call, _class_literal, _get
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


def _distance_cm(ed, made):
    return out(_call(ed, FN_MUL_II, made,
                      A=column(ed, "wind_distance", made, rounded=True), B=CM_PER_M))


def _author_walk(ed, in_execs, made):
    """Every cell's WPO switch and distance, when either moved. Returns the
    exec tails."""
    on = _call(ed, FN_NEQ_II, made,
               A=column(ed, "wind", made, rounded=True),
               B=_get(ed, TUNER_WIND_APPLIED_VAR, made))
    far = _call(ed, FN_NEQ_II, made,
                A=column(ed, "wind_distance", made, rounded=True),
                B=_get(ed, TUNER_WIND_DISTANCE_APPLIED_VAR, made))
    moved = _call(ed, FN_OR_BB, made, A=out(on), B=out(far))
    go, same = _branch(ed, out(moved), in_execs, made)

    actors = _call(ed, FN_ALL_OF_CLASS, made)
    _class_literal(actors, "ActorClass", ACTOR_CLASS_PATH)
    _connect(go, _pin(actors, "execute"))
    actor, body, done = _for_each(ed, out(actors, "OutActors"), out(actors, "then"), made)
    comp, flow = _root_mesh(ed, actor, body, made)
    wpo = _call(ed, FN_SET_WPO, made, self=comp,
                NewValue=out(_call(ed, FN_GE_II, made,
                                    A=column(ed, "wind", made,
                                             rounded=True), B=1)))
    _connect(flow, _pin(wpo, "execute"))
    reach = _call(ed, FN_SET_WPO_DISTANCE, made, self=comp, NewValue=_distance_cm(ed, made))
    _connect(out(wpo, "then"), _pin(reach, "execute"))

    kept = put(ed, TUNER_WIND_APPLIED_VAR, column(ed, "wind", made, rounded=True), [done], made)
    kept = put(ed, TUNER_WIND_DISTANCE_APPLIED_VAR,
               column(ed, "wind_distance", made, rounded=True),
               [kept], made)
    return [kept, same]


def _author_params(ed, in_execs, made):
    """MPC_Wind's scalars, one SetScalarParameterValue each. Returns then."""
    on = out(_call(ed, FN_INT_TO_FLOAT, made, InInt=column(ed, "wind", made, rounded=True)))
    flow = in_execs
    for index, st in stats_by(WIND_PARAM):
        value = applied(ed, index, made)
        if st.target == "Strength":
            value = out(_call(ed, FN_MUL_FF, made, A=value, B=on))
        s = _call(ed, FN_SET_MPC_SCALAR, made, ParameterName=st.target, ParameterValue=value)
        _class_literal(s, "Collection", MPC_OBJECT_PATH)
        for e in flow:
            _connect(e, _pin(s, "execute"))
        flow = [out(s, "then")]
    return flow


def author_wind(ed, in_execs, made):
    """The whole fragment (module docstring). Returns the exec tails."""
    if not unreal.load_asset(MPC_PATH):    # an object literal needs the asset
        raise RuntimeError(f"{MPC_PATH} is missing -- run forest_import/wind.py first")
    flow = _author_walk(ed, in_execs, made)
    return _author_params(ed, flow, made)
