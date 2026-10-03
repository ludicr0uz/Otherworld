"""The next tree of a wendigo's hunt: where one leg of the stalk ends. The
numbers are forest_generator/npc_stalk.py's; the step that calls this is
npc/stalk.py.

    -> StalkArrived = false, StalkLegUntil = now + the timeout, StalkLegs + 1
    -> StalkIgnore = [what the pawn stands on, the pawn]
    -> for each angle of NPC_STALK_ARC_DEG, round the player the hunt's way:
         sweep a sphere along the line at the player, from a little closer
         than the wendigo stands to a lot closer
         [struck an instanced mesh, and that instance has a transform?]
           [its mesh is one whose trunk hides a wendigo, at this scale?]
           StalkCover = the tree + (tree - player, flat, unit) * BEHIND
           [a line from there to the player strikes that same tree?]
           [closer than the pawn stands, outside the charge range, and on
            the navmesh?] StalkCover = the snapped point, StalkHidden = true
                          -> out
         anything else -> the next angle
    -> none: StalkCover = the first angle's line, in the open
       [on the navmesh?] StalkCover = the snapped point, StalkHidden = false
                         no: nowhere to go -- the caller charges

WHAT A TREE IS. The trees are instances of per-cell instanced meshes
(forest_import/trees.py), and nothing else in a level is an instanced mesh
with collision, so "the sweep struck an InstancedStaticMeshComponent" is the
test, as it is for the axe (combat/weapon_component/chop.py). The hit's item
is the instance, and the instance's transform is where its trunk stands --
which is what the spot is measured from, not the point the sphere touched
(a branch, or nothing at all when the sweep starts inside the crown).

WHAT COVER IS. Not every tree hides anything: a sapling's stem is a few
centimetres across and its twigs are seen through, and some trunks lean off
their own foot. Two tests. The tree has to be of a mesh, and of a scale,
whose trunk is as wide as the wendigo (npc_stalk.cover_trees(): the least
scale per mesh, told by the mesh's name and picked through a chain of
SelectFloats that ends on a scale no tree has). And the spot is tested the way the player would see it: a
line from it to the player has to strike that same tree (the same component
and instance) before it reaches them. Trees collide by their own triangles,
leaves and all, so "any tree" let the twigs of a sapling ten metres on
count as a hiding place.

The terrain is one mesh and blocks the same channel, and a sphere this wide
drags along it on any slope. So the sweep ignores what the pawn stands on
(GetMovementBaseActor) and the pawn itself: bIgnoreSelf here is the
controller.

GetInstanceTransform and the navmesh projection are pure: each is branched
on its bool before its other output is read.
"""

import unreal

from forest_generator.npc_placement import NPC_CAPSULE_HALF_HEIGHT_CM
from forest_generator.npc_stalk import (
    NPC_STALK_ADVANCE_MAX_CM, NPC_STALK_ADVANCE_MIN_CM, NPC_STALK_ARC_DEG,
    NPC_STALK_BEHIND_CM, NPC_STALK_COVER_MIN_CM, NPC_STALK_GAIN_MIN_CM,
    NPC_STALK_LEG_TIMEOUT_S,
    NPC_STALK_NAV_EXTENT_CM, NPC_STALK_OPEN_ADVANCE_CM,
    NPC_STALK_OPEN_NAV_EXTENT_CM,
    NPC_STALK_SWEEP_LIFT_CM, NPC_STALK_SWEEP_RADIUS_CM, cover_trees,
)
from npc.graph import BEL, _Graph, _connect, _loose_pin, _palette, _pin, out
from npc.nodes import (
    FN_ADD_FF, FN_ADD_II, FN_ADD_VV, FN_ARR_ADD, FN_ARR_CLEAR,
    FN_AND, FN_BREAK_TRANSFORM, FN_BREAK_VECTOR, FN_DISTANCE_2D, FN_EQ_II,
    FN_EQ_OO, FN_EQ_SS, FN_FMAX, FN_GE_FF, FN_IN_RANGE, FN_INSTANCE_TRANSFORM,
    FN_LINE_TRACE, FN_MAKE_VECTOR, FN_MOVEMENT_BASE, FN_MUL_FF, FN_MUL_VV,
    FN_NORMAL_2D, FN_OBJECT_NAME, FN_PROJECT_NAV, FN_ROTATE_AXIS, FN_SELECT_FLOAT,
    FN_SPHERE_TRACE, FN_SUB_FF, FN_SUB_VV, NODE_BREAK_HIT, NODE_CAST_INSTANCED,
)
from npc.paths import (
    STALK_ARRIVED_VAR, STALK_COVER_VAR, STALK_HIDDEN_VAR, STALK_IGNORE_VAR,
    STALK_LEG_UNTIL_VAR, STALK_LEGS_VAR, STALK_SIDE_VAR,
    STATIC_MESH_COMP_CLASS_PATH,
)

# What the chain of least scales ends on: a mesh that is not cover at any
# scale (a sapling, or one no row names) needs a scale no tree has.
NO_COVER_SCALE = 1000000.0


def declare_cover_vars(ed):
    """The leg's own state. Zero and false are the right start: no leg yet."""
    kinds = {
        STALK_COVER_VAR: BEL.get_struct_type(unreal.Vector.static_struct()),
        STALK_HIDDEN_VAR: BEL.get_basic_type_by_name("bool"),
        STALK_ARRIVED_VAR: BEL.get_basic_type_by_name("bool"),
        STALK_LEG_UNTIL_VAR: BEL.get_basic_type_by_name("real"),
        STALK_LEGS_VAR: BEL.get_basic_type_by_name("int"),
        STALK_IGNORE_VAR: BEL.get_array_type(
            BEL.get_object_reference_type(unreal.Actor.static_class())),
    }
    for name, kind in kinds.items():
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, kind):
            raise RuntimeError(f"could not declare {name}")


def _thrice(g, value):
    """A vector of three of ``value``: vector x float is a wildcard node."""
    node = g.call(FN_MAKE_VECTOR)
    for axis in ("X", "Y", "Z"):
        _connect(value, _pin(node, axis))
    return out(node)


def _along(g, origin, direction, reach):
    """``origin + direction * reach`` (a float pin); returns the point's pin."""
    step = g.call(FN_MUL_VV)
    _connect(direction, _pin(step, "A"))
    _connect(_thrice(g, reach), _pin(step, "B"))
    point = g.call(FN_ADD_VV)
    _connect(origin, _pin(point, "A"))
    _connect(out(step), _pin(point, "B"))
    return out(point)


def _author_wide(g, exec_in, tree, scale):
    """Is this tree's trunk wide enough to hide behind? ``tree`` is the pin
    of the instanced component the sweep struck and ``scale`` that of the
    instance's scale (a vector). Returns the Branch."""
    mesh = g.keep(g.ed.add_get_member_variable_node("StaticMesh", STATIC_MESH_COMP_CLASS_PATH))
    _connect(tree, _pin(mesh, "self"))
    # By name: an object pin of an Equal node takes no asset literal.
    named = g.call(FN_OBJECT_NAME)
    _connect(_pin(mesh, "StaticMesh", is_input=False), _pin(named, "Object"))
    least = None
    for path, scale_min in cover_trees():
        same = g.call(FN_EQ_SS, B=path.rsplit(".", 1)[-1])
        _connect(out(named), _pin(same, "A"))
        pick = g.call(FN_SELECT_FLOAT, A=scale_min)
        _connect(out(same), _pin(pick, "bPickA"))
        if least is None:
            _pin(pick, "B").set_pin_value(str(NO_COVER_SCALE))
        else:
            _connect(least, _pin(pick, "B"))
        least = out(pick)
    size = g.call(FN_BREAK_VECTOR)
    _connect(scale, _pin(size, "InVec"))
    return g.branch(g.op(FN_GE_FF, out(size, "X"), least), exec_in)


def _author_try(g, exec_in, angle, pins):
    """One sweep, ``angle`` degrees round the player. Returns ``(found,
    missed, heading)``: the exec pin after a cover was stored, the exec pins
    of every way it was not, and the pin of the unit vector swept along (from
    the player)."""
    yaw = g.op(FN_MUL_FF, g.get(STALK_SIDE_VAR), angle)
    turned = g.call(FN_ROTATE_AXIS)
    _connect(pins["radial"], _pin(turned, "InVect"))
    _connect(yaw, _pin(turned, "AngleDeg"))
    _connect(pins["up"], _pin(turned, "Axis"))
    heading = out(turned)

    sweep = g.call(FN_SPHERE_TRACE, Radius=NPC_STALK_SWEEP_RADIUS_CM,
                   TraceChannel="TraceTypeQuery1", bTraceComplex="false",
                   bIgnoreSelf="true", DrawDebugType="None")
    _connect(_along(g, pins["lifted"], heading, pins["far"]), _pin(sweep, "Start"))
    _connect(_along(g, pins["lifted"], heading, pins["near"]), _pin(sweep, "End"))
    _connect(g.get(STALK_IGNORE_VAR), _pin(sweep, "ActorsToIgnore"))
    for source in exec_in:
        _connect(source, _pin(sweep, "execute"))
    struck = g.branch(out(sweep), BEL.find_then_pin(sweep))
    hit = g.keep(_palette(g.ed, NODE_BREAK_HIT))
    _connect(out(sweep, "OutHit"), _pin(hit, "Hit"))

    # --- is it a tree, and where does its trunk stand? ------------------------
    tree = g.keep(_palette(g.ed, NODE_CAST_INSTANCED))
    _connect(_loose_pin(hit, "HitComponent", is_input=False), _pin(tree, "Object"))
    _connect(BEL.find_then_pin(struck), _pin(tree, "execute"))
    stands = g.call(FN_INSTANCE_TRANSFORM, bWorldSpace="true")
    _connect(_loose_pin(tree, "AsInstancedStaticMeshComponent", is_input=False),
             _pin(stands, "self"))
    _connect(_loose_pin(hit, "HitItem", is_input=False), _pin(stands, "InstanceIndex"))
    known = g.branch(out(stands), BEL.find_then_pin(tree))
    trunk = g.call(FN_BREAK_TRANSFORM)
    _connect(out(stands, "OutInstanceTransform"), _pin(trunk, "InTransform"))

    # --- the spot: past the trunk, seen from the player ----------------------
    past = g.call(FN_SUB_VV)
    _connect(out(trunk, "Location"), _pin(past, "A"))
    _connect(pins["player_loc"], _pin(past, "B"))
    shadow = g.call(FN_NORMAL_2D)
    _connect(out(past), _pin(shadow, "A"))
    behind = g.call(FN_MUL_VV)
    _connect(out(shadow), _pin(behind, "A"))
    _connect(pins["behind"], _pin(behind, "B"))
    spot = g.call(FN_ADD_VV)
    _connect(out(trunk, "Location"), _pin(spot, "A"))
    _connect(out(behind), _pin(spot, "B"))
    # The trunk's transform is its foot; the pawn's centre is half a capsule up.
    stood = g.call(FN_ADD_VV)
    _connect(out(spot), _pin(stood, "A"))
    _connect(pins["half_height"], _pin(stood, "B"))
    its = _loose_pin(tree, "AsInstancedStaticMeshComponent", is_input=False)
    wide = _author_wide(g, BEL.find_then_pin(known), its, out(trunk, "Scale"))
    raw = g.put(STALK_COVER_VAR, BEL.find_then_pin(wide), pin=out(stood))

    # --- ...out of the player's sight ------------------------------------------
    stored = g.get(STALK_COVER_VAR)
    line = g.call(FN_LINE_TRACE, TraceChannel="TraceTypeQuery1",
                  bTraceComplex="false", bIgnoreSelf="true", DrawDebugType="None")
    _connect(stored, _pin(line, "Start"))
    _connect(pins["player_loc"], _pin(line, "End"))
    _connect(g.get(STALK_IGNORE_VAR), _pin(line, "ActorsToIgnore"))
    _connect(raw, _pin(line, "execute"))
    blocked = g.branch(out(line), BEL.find_then_pin(line))
    between = g.keep(_palette(g.ed, NODE_BREAK_HIT))
    _connect(out(line, "OutHit"), _pin(between, "Hit"))
    # That tree, and no other: the same cell and the same instance of it.
    cell = g.op(FN_EQ_OO, _loose_pin(between, "HitComponent", is_input=False), its)
    item = g.op(FN_EQ_II, _loose_pin(between, "HitItem", is_input=False),
                _loose_pin(hit, "HitItem", is_input=False))
    shade = g.branch(g.op(FN_AND, cell, item), BEL.find_then_pin(blocked))
    raw = BEL.find_then_pin(shade)

    # --- ...a step in (the sphere may have touched a crown, metres from its
    # trunk), and somewhere it can stand ---------------------------------------
    off = g.call(FN_DISTANCE_2D)
    _connect(stored, _pin(off, "V1"))
    _connect(pins["player_loc"], _pin(off, "V2"))
    gains = g.call(FN_IN_RANGE, Min=NPC_STALK_COVER_MIN_CM)
    _connect(out(off), _pin(gains, "Value"))
    _connect(pins["gain"], _pin(gains, "Max"))
    on_nav = g.call(FN_PROJECT_NAV)
    _connect(stored, _pin(on_nav, "Point"))
    _connect(pins["nav_extent"], _pin(on_nav, "QueryExtent"))
    good = g.op(FN_AND, out(gains), out(on_nav))
    walkable = g.branch(good, raw)
    snapped = g.put(STALK_COVER_VAR, BEL.find_then_pin(walkable),
                    pin=out(on_nav, "ProjectedLocation"))
    found = g.put(STALK_HIDDEN_VAR, snapped, literal="true")
    missed = [BEL.find_else_pin(struck), _loose_pin(tree, "CastFailed", is_input=False),
              BEL.find_else_pin(known), BEL.find_else_pin(wide),
              BEL.find_else_pin(blocked), BEL.find_else_pin(shade),
              BEL.find_else_pin(walkable)]
    return found, missed, heading


def _author_cover(ed, exec_in, pins):
    """Pick this leg's spot into StalkCover. ``exec_in`` is the exec pin a
    pass that needs a new leg arrives on; ``pins`` are the step's shared
    values: ``self_pawn``, ``self_loc``, ``player_loc``, ``gap`` (flat) and
    ``now``.

    Returns ``(nodes, tails, lost)``: the nodes made, the exec pins it ends
    on, one per way a spot was settled, and the exec pin of a pick that found
    nowhere to go at all.
    """
    g = _Graph(ed)

    # --- a new leg -----------------------------------------------------------
    step = g.put(STALK_ARRIVED_VAR, exec_in, literal="false")
    give_up = g.op(FN_ADD_FF, pins["now"], NPC_STALK_LEG_TIMEOUT_S)
    step = g.put(STALK_LEG_UNTIL_VAR, step, pin=give_up)
    count = g.op(FN_ADD_II, g.get(STALK_LEGS_VAR), 1)
    step = g.put(STALK_LEGS_VAR, step, pin=count)

    # --- what the sweep ignores ----------------------------------------------
    clear = g.call(FN_ARR_CLEAR)
    _connect(g.get(STALK_IGNORE_VAR), _pin(clear, "TargetArray"))
    _connect(step, _pin(clear, "execute"))
    ground = g.call(FN_MOVEMENT_BASE)
    _connect(pins["self_pawn"], _pin(ground, "Pawn"))
    step = BEL.find_then_pin(clear)
    for actor in (out(ground), pins["self_pawn"]):
        add = g.call(FN_ARR_ADD)
        _connect(g.get(STALK_IGNORE_VAR), _pin(add, "TargetArray"))
        _connect(actor, _pin(add, "NewItem"))
        _connect(step, _pin(add, "execute"))
        step = BEL.find_then_pin(add)

    # --- shared by every angle -----------------------------------------------
    away = g.call(FN_SUB_VV)
    _connect(pins["self_loc"], _pin(away, "A"))
    _connect(pins["player_loc"], _pin(away, "B"))
    radial = g.call(FN_NORMAL_2D)
    _connect(out(away), _pin(radial, "A"))
    # The sweeps start from the player's spot on the map, at the wendigo's own
    # height plus the lift: the trunks are tall, and the ground is ignored.
    here = g.call(FN_BREAK_VECTOR)
    _connect(pins["self_loc"], _pin(here, "InVec"))
    there = g.call(FN_BREAK_VECTOR)
    _connect(pins["player_loc"], _pin(there, "InVec"))
    high = g.op(FN_ADD_FF, out(here, "Z"), NPC_STALK_SWEEP_LIFT_CM)
    lifted = g.call(FN_MAKE_VECTOR)
    _connect(out(there, "X"), _pin(lifted, "X"))
    _connect(out(there, "Y"), _pin(lifted, "Y"))
    _connect(high, _pin(lifted, "Z"))
    far = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_ADVANCE_MIN_CM)
    deep = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_ADVANCE_MAX_CM)
    near = g.op(FN_FMAX, deep, NPC_STALK_COVER_MIN_CM)
    gain = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_GAIN_MIN_CM)
    shared = dict(
        pins, radial=out(radial), lifted=out(lifted), far=far, near=near, gain=gain,
        up=out(g.call(FN_MAKE_VECTOR, Z=1.0)),
        behind=out(g.call(FN_MAKE_VECTOR, X=NPC_STALK_BEHIND_CM,
                          Y=NPC_STALK_BEHIND_CM, Z=NPC_STALK_BEHIND_CM)),
        half_height=out(g.call(FN_MAKE_VECTOR,
                               Z=NPC_CAPSULE_HALF_HEIGHT_CM)),
        nav_extent=out(g.call(FN_MAKE_VECTOR,
                              **dict(zip("XYZ", NPC_STALK_NAV_EXTENT_CM)))))

    # --- one sweep per angle, until one finds a tree -------------------------
    tails, missed, first = [], [step], None
    for angle in NPC_STALK_ARC_DEG:
        found, missed, heading = _author_try(g, missed, angle, shared)
        tails.append(found)
        first = heading if first is None else first

    # --- none: on round the player, in the open ------------------------------
    closer = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_OPEN_ADVANCE_CM)
    bare = g.put(STALK_COVER_VAR, missed, pin=_along(g, shared["lifted"], first, closer))
    on_nav = g.call(FN_PROJECT_NAV)
    _connect(g.get(STALK_COVER_VAR), _pin(on_nav, "Point"))
    _connect(out(g.call(FN_MAKE_VECTOR,
                        **dict(zip("XYZ", NPC_STALK_OPEN_NAV_EXTENT_CM)))),
             _pin(on_nav, "QueryExtent"))
    walkable = g.branch(out(on_nav), bare)
    snapped = g.put(STALK_COVER_VAR, BEL.find_then_pin(walkable),
                    pin=out(on_nav, "ProjectedLocation"))
    tails.append(g.put(STALK_HIDDEN_VAR, snapped, literal="false"))
    return g.made, tails, BEL.find_else_pin(walkable)
