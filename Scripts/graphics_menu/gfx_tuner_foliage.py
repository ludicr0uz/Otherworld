"""BP_GraphicsTuner's foliage fragment: how far the grass and the trees are
drawn, how thick the grass is and whether it is lit.

    grass draw distance or grass shadows moved
        every actor tagged OW_Grass (grass and bush cells): its root HISM's
        shadow, distance-field and dynamic indirect lighting := grass shadows,
        and its distances scaled by wanted / applied
    tree draw distance moved
        every other actor whose root is an instanced mesh (the tree cells):
        its distances scaled the same way

A draw distance is metres in the table, and a ratio here: what the level's
own distances are multiplied by. The engine multiplies every cull distance
by r.ViewDistanceScale, so

    wanted = metres / (the level's metres at 100% x view distance % / 100)

which makes "28 m" 28 m on the ground at any view distance, and "moved"
also true when the view distance did. The applied variables hold ratios,
and start at 1: a level is saved at its own distances.
    grass layers moved
        for each density tier above the first, every actor tagged
        OW_GrassTier<n>: hidden in game unless layers > n

Each walk runs only when its number differs from what was last applied, so
nudging the fog does not touch a thousand grass cells.

Scaling a cell. The instance fade (start, end) is multiplied; the cell's own
max draw distance moves by as many centimetres as the end did, because it is
the end plus a fixed reach to the cell's far corner (grass_cells.
cell_max_draw_cm), and a reach scaled down would drop a cell while its
clumps were still in range. GetCullDistances is pure, so it is re-read by
each node that uses it: the max draw distance is set first, while the
distances are still the old ones.

There is no cvar for one component's shadow or distance, which is why this
walks components. A level always loads with the grass as the import saved it
(unlit, upper tiers hidden, its own distances), and a new HUD starts with
nothing applied, so a reload converges through the same walks.

Trees carry no tag (the levels were generated without one), so they are
found as "an instanced-mesh root that is not grass". The walk over every
actor happens only when the tree distance moves.
"""

from combat.graph import BEL, _connect, _loose_pin, _palette, _pin
from uebp.graph import out
from combat.nodes import FN_ADD_FF, FN_LESS_II, FN_MUL_FF, FN_OR, MACRO_FOR_EACH
from forest_generator.grass_cells import GRASS_TAG, GRASS_TIERS, tier_tag
from graphics_menu.dev_guns import _branch, _call, _class_literal, _get
from graphics_menu.gfx_stats import FULL_VIEW_M, PERCENT
from graphics_menu.gfx_tune_consts import (
    TUNER_GRASS_DISTANCE_APPLIED_VAR, TUNER_GRASS_LAYERS_APPLIED_VAR,
    TUNER_GRASS_SHADOWS_APPLIED_VAR, TUNER_TREE_DISTANCE_APPLIED_VAR,
)
from graphics_menu.gfx_tuner_read import FN_ROUND, column
from graphics_menu.loot_find import put

KML = "/Script/Engine.KismetMathLibrary"
FN_NEQ_FF = f"{KML}.NotEqual_DoubleDouble"
FN_NEQ_II = f"{KML}.NotEqual_IntInt"
FN_GE_II = f"{KML}.GreaterEqual_IntInt"
FN_SUB_II = f"{KML}.Subtract_IntInt"
FN_DIV_FF = f"{KML}.Divide_DoubleDouble"
FN_INT_TO_FLOAT = f"{KML}.Conv_IntToDouble"
FN_WITH_TAG = "/Script/Engine.GameplayStatics.GetAllActorsWithTag"
FN_ALL_OF_CLASS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"
FN_HAS_TAG = "/Script/Engine.Actor.ActorHasTag"
FN_ROOT = "/Script/Engine.Actor.K2_GetRootComponent"
FN_HIDE = "/Script/Engine.Actor.SetActorHiddenInGame"
ACTOR_CLASS_PATH = "/Script/Engine.Actor"
ISM_CLASS_PATH = "/Script/Engine.InstancedStaticMeshComponent"
PRIMITIVE_CLASS_PATH = "/Script/Engine.PrimitiveComponent"
FN_GET_CULLS = f"{ISM_CLASS_PATH}.GetCullDistances"
FN_SET_CULLS = f"{ISM_CLASS_PATH}.SetCullDistances"
FN_SET_MAX_DRAW = f"{PRIMITIVE_CLASS_PATH}.SetCullDistance"
MAX_DRAW_VAR = "LDMaxDrawDistance"
NODE_CAST_ISM = "Utilities|Casting|CastToInstancedStaticMeshComponent"

# What grass shadows switches, one PrimitiveComponent setter each.
GRASS_SETTERS = (
    (f"{PRIMITIVE_CLASS_PATH}.SetCastShadow", "NewCastShadow"),
    (f"{PRIMITIVE_CLASS_PATH}.SetAffectDistanceFieldLighting",
     "NewAffectDistanceFieldLighting"),
    (f"{PRIMITIVE_CLASS_PATH}.SetAffectDynamicIndirectLighting",
     "bNewAffectDynamicIndirectLighting"),
)
# The tiers the layers stat switches: every one above the first, which is
# saved shown and carries no tier tag. Tier n is drawn when layers > n.
SWITCHED_TIERS = tuple(range(1, len(GRASS_TIERS)))


def _for_each(ed, array, in_exec, made):
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(array, _loose_pin(loop, "Array"))
    _connect(in_exec, _loose_pin(loop, "Exec"))
    return (_loose_pin(loop, "ArrayElement", is_input=False),
            _loose_pin(loop, "LoopBody", is_input=False),
            _loose_pin(loop, "Completed", is_input=False))


def _root_mesh(ed, actor, in_exec, made):
    """The actor's root as an instanced mesh. Returns (component, then); an
    actor with some other root fails the cast and is skipped."""
    root = _call(ed, FN_ROOT, made, self=actor)
    cast = _palette(ed, NODE_CAST_ISM)
    made.append(cast)
    _connect(out(root), _pin(cast, "Object"))
    _connect(in_exec, _pin(cast, "execute"))
    return (_loose_pin(cast, "AsInstancedStaticMeshComponent", is_input=False),
            BEL.find_then_pin(cast))


def _author_scale(ed, comp, ratio, in_exec, made):
    """One cell's distances x ``ratio`` (module docstring). Returns then."""
    culls = _call(ed, FN_GET_CULLS, made, self=comp)
    ends = {}
    for name in ("Start", "End"):
        was = _pin(culls, f"Out{name}CullDistance", is_input=False)
        # Not Multiply_IntFloat: it is promoted to a wildcard that takes its
        # type from the int, and the ratio is truncated on the way in.
        scaled = _call(ed, FN_MUL_FF, made, B=ratio,
                       A=out(_call(ed, FN_INT_TO_FLOAT, made,
                                    InInt=was)))
        ends[name] = (was, out(_call(ed, FN_ROUND, made, A=out(scaled))))
    grew = _call(ed, FN_SUB_II, made, A=ends["End"][1], B=ends["End"][0])
    reach = _call(ed, FN_ADD_FF, made,
                  A=_get(ed, MAX_DRAW_VAR, made, PRIMITIVE_CLASS_PATH,
                         comp),
                  B=out(_call(ed, FN_INT_TO_FLOAT, made,
                               InInt=out(grew))))
    far = _call(ed, FN_SET_MAX_DRAW, made, self=comp, NewCullDistance=out(reach))
    _connect(in_exec, _pin(far, "execute"))
    fade = _call(ed, FN_SET_CULLS, made, self=comp,
                 StartCullDistance=ends["Start"][1], EndCullDistance=ends["End"][1])
    _connect(BEL.find_then_pin(far), _pin(fade, "execute"))
    return BEL.find_then_pin(fade)


def _wanted(ed, column_name, made):
    """The ratio that draws ``column_name``'s metres (module docstring)."""
    reach = _call(ed, FN_MUL_FF, made,
                  A=column(ed, "view_distance", made),
                  B=round(FULL_VIEW_M[column_name] * PERCENT, 6))
    return out(_call(ed, FN_DIV_FF, made, A=column(ed, column_name, made), B=out(reach)))


def _ratio(ed, column_name, applied_var, made):
    return out(_call(ed, FN_DIV_FF, made,
                      A=_wanted(ed, column_name, made),
                      B=_get(ed, applied_var, made)))


def _author_grass(ed, in_execs, made):
    """The grass and bush cells: lighting and distance. Returns the tails."""
    far = _call(ed, FN_NEQ_FF, made,
                A=_wanted(ed, "grass_distance", made),
                B=_get(ed, TUNER_GRASS_DISTANCE_APPLIED_VAR, made))
    lit = _call(ed, FN_NEQ_II, made,
                A=column(ed, "grass_shadows", made, rounded=True),
                B=_get(ed, TUNER_GRASS_SHADOWS_APPLIED_VAR, made))
    moved = _call(ed, FN_OR, made, A=out(far), B=out(lit))
    go, same = _branch(ed, out(moved), in_execs, made)

    cells = _call(ed, FN_WITH_TAG, made, Tag=GRASS_TAG)
    _connect(go, _pin(cells, "execute"))
    cell, body, done = _for_each(ed, _pin(cells, "OutActors", is_input=False),
                                 BEL.find_then_pin(cells), made)
    comp, flow = _root_mesh(ed, cell, body, made)
    on = out(_call(ed, FN_GE_II, made, A=column(ed, "grass_shadows", made, rounded=True), B=1))
    for fn, arg in GRASS_SETTERS:
        s = _call(ed, fn, made, self=comp)
        _connect(on, _pin(s, arg))
        _connect(flow, _pin(s, "execute"))
        flow = BEL.find_then_pin(s)
    _author_scale(ed, comp,
                  _ratio(ed, "grass_distance", TUNER_GRASS_DISTANCE_APPLIED_VAR, made),
                  flow, made)

    kept = put(ed, TUNER_GRASS_DISTANCE_APPLIED_VAR,
               _wanted(ed, "grass_distance", made), [done], made)
    kept = put(ed, TUNER_GRASS_SHADOWS_APPLIED_VAR,
               column(ed, "grass_shadows", made, rounded=True),
               [kept], made)
    return [kept, same]


def _author_trees(ed, in_execs, made):
    """The tree cells' distance. Returns the tails."""
    moved = _call(ed, FN_NEQ_FF, made,
                  A=_wanted(ed, "tree_distance", made),
                  B=_get(ed, TUNER_TREE_DISTANCE_APPLIED_VAR, made))
    go, same = _branch(ed, out(moved), in_execs, made)
    actors = _call(ed, FN_ALL_OF_CLASS, made)
    _class_literal(actors, "ActorClass", ACTOR_CLASS_PATH)
    _connect(go, _pin(actors, "execute"))
    actor, body, done = _for_each(ed, _pin(actors, "OutActors", is_input=False),
                                  BEL.find_then_pin(actors), made)
    grass = _call(ed, FN_HAS_TAG, made, self=actor, Tag=GRASS_TAG)
    _skip, other = _branch(ed, out(grass), [body], made)
    comp, flow = _root_mesh(ed, actor, other, made)
    _author_scale(ed, comp,
                  _ratio(ed, "tree_distance", TUNER_TREE_DISTANCE_APPLIED_VAR, made),
                  flow, made)
    kept = put(ed, TUNER_TREE_DISTANCE_APPLIED_VAR,
               _wanted(ed, "tree_distance", made), [done], made)
    return [kept, same]


def _author_layers(ed, in_execs, made):
    """Which density tiers are drawn. Returns the tails."""
    moved = _call(ed, FN_NEQ_II, made,
                  A=column(ed, "grass_layers", made, rounded=True),
                  B=_get(ed, TUNER_GRASS_LAYERS_APPLIED_VAR, made))
    flow, same = _branch(ed, out(moved), in_execs, made)
    for tier in SWITCHED_TIERS:
        cells = _call(ed, FN_WITH_TAG, made, Tag=tier_tag(tier))
        _connect(flow, _pin(cells, "execute"))
        cell, body, flow = _for_each(ed, _pin(cells, "OutActors", is_input=False),
                                     BEL.find_then_pin(cells), made)
        below = _call(ed, FN_LESS_II, made,
                      A=column(ed, "grass_layers", made, rounded=True),
                      B=tier + 1)
        hide = _call(ed, FN_HIDE, made, self=cell, bNewHidden=out(below))
        _connect(body, _pin(hide, "execute"))
    kept = put(ed, TUNER_GRASS_LAYERS_APPLIED_VAR,
               column(ed, "grass_layers", made, rounded=True), [flow], made)
    return [kept, same]


def author_foliage(ed, in_execs, made):
    """The whole fragment (module docstring). Returns the exec tails."""
    flow = _author_grass(ed, in_execs, made)
    flow = _author_trees(ed, flow, made)
    return _author_layers(ed, flow, made)
