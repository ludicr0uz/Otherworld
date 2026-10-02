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


def _thrice(g, value, x, y):
    """A vector of three of ``value``: vector x float is a wildcard node."""
    node = g.call(FN_MAKE_VECTOR, x, y)
    for axis in ("X", "Y", "Z"):
        _connect(value, _pin(node, axis))
    return out(node)


def _along(g, origin, direction, reach, x, y):
    """``origin + direction * reach`` (a float pin); returns the point's pin."""
    step = g.call(FN_MUL_VV, x + 240, y)
    _connect(direction, _pin(step, "A"))
    _connect(_thrice(g, reach, x, y + 140), _pin(step, "B"))
    point = g.call(FN_ADD_VV, x + 480, y)
    _connect(origin, _pin(point, "A"))
    _connect(out(step), _pin(point, "B"))
    return out(point)


def _author_wide(g, exec_in, tree, scale, x0, y0):
    """Is this tree's trunk wide enough to hide behind? ``tree`` is the pin
    of the instanced component the sweep struck and ``scale`` that of the
    instance's scale (a vector). Returns the Branch."""
    mesh = g.keep(g.ed.add_get_member_variable_node(
        "StaticMesh", STATIC_MESH_COMP_CLASS_PATH), x0, y0 + 300)
    _connect(tree, _pin(mesh, "self"))
    # By name: an object pin of an Equal node takes no asset literal.
    named = g.call(FN_OBJECT_NAME, x0, y0 + 620)
    _connect(_pin(mesh, "StaticMesh", is_input=False), _pin(named, "Object"))
    least = None
    for i, (path, scale_min) in enumerate(cover_trees()):
        same = g.call(FN_EQ_SS, x0 + 240, y0 + 300 + 160 * i, B=path.rsplit(".", 1)[-1])
        _connect(out(named), _pin(same, "A"))
        pick = g.call(FN_SELECT_FLOAT, x0 + 480, y0 + 300 + 160 * i, A=scale_min)
        _connect(out(same), _pin(pick, "bPickA"))
        if least is None:
            _pin(pick, "B").set_pin_value(str(NO_COVER_SCALE))
        else:
            _connect(least, _pin(pick, "B"))
        least = out(pick)
    size = g.call(FN_BREAK_VECTOR, x0, y0 + 460)
    _connect(scale, _pin(size, "InVec"))
    return g.branch(g.op(FN_GE_FF, out(size, "X"), least, x0 + 720, y0 + 300),
                    exec_in, x0 + 960, y0)


def _author_try(g, exec_in, angle, pins, x0, y0):
    """One sweep, ``angle`` degrees round the player. Returns ``(found,
    missed, heading)``: the exec pin after a cover was stored, the exec pins
    of every way it was not, and the pin of the unit vector swept along (from
    the player)."""
    yaw = g.op(FN_MUL_FF, g.get(STALK_SIDE_VAR, x0 - 240, y0 + 300), angle,
               x0, y0 + 300)
    turned = g.call(FN_ROTATE_AXIS, x0 + 240, y0 + 300)
    _connect(pins["radial"], _pin(turned, "InVect"))
    _connect(yaw, _pin(turned, "AngleDeg"))
    _connect(pins["up"], _pin(turned, "Axis"))
    heading = out(turned)

    sweep = g.call(FN_SPHERE_TRACE, x0 + 1000, y0, Radius=NPC_STALK_SWEEP_RADIUS_CM,
                   TraceChannel="TraceTypeQuery1", bTraceComplex="false",
                   bIgnoreSelf="true", DrawDebugType="None")
    _connect(_along(g, pins["lifted"], heading, pins["far"], x0 + 480, y0 + 300),
             _pin(sweep, "Start"))
    _connect(_along(g, pins["lifted"], heading, pins["near"], x0 + 480, y0 + 600),
             _pin(sweep, "End"))
    _connect(g.get(STALK_IGNORE_VAR, x0 + 760, y0 + 160), _pin(sweep, "ActorsToIgnore"))
    for source in exec_in:
        _connect(source, _pin(sweep, "execute"))
    struck = g.branch(out(sweep), BEL.find_then_pin(sweep), x0 + 1300, y0)
    hit = g.keep(_palette(g.ed, NODE_BREAK_HIT), x0 + 1300, y0 + 300)
    _connect(out(sweep, "OutHit"), _pin(hit, "Hit"))

    # --- is it a tree, and where does its trunk stand? ------------------------
    tree = g.keep(_palette(g.ed, NODE_CAST_INSTANCED), x0 + 1600, y0)
    _connect(_loose_pin(hit, "HitComponent", is_input=False), _pin(tree, "Object"))
    _connect(BEL.find_then_pin(struck), _pin(tree, "execute"))
    stands = g.call(FN_INSTANCE_TRANSFORM, x0 + 1900, y0 + 300, bWorldSpace="true")
    _connect(_loose_pin(tree, "AsInstancedStaticMeshComponent", is_input=False),
             _pin(stands, "self"))
    _connect(_loose_pin(hit, "HitItem", is_input=False), _pin(stands, "InstanceIndex"))
    known = g.branch(out(stands), BEL.find_then_pin(tree), x0 + 2200, y0)
    trunk = g.call(FN_BREAK_TRANSFORM, x0 + 2200, y0 + 300)
    _connect(out(stands, "OutInstanceTransform"), _pin(trunk, "InTransform"))

    # --- the spot: past the trunk, seen from the player ----------------------
    past = g.call(FN_SUB_VV, x0 + 2460, y0 + 300)
    _connect(out(trunk, "Location"), _pin(past, "A"))
    _connect(pins["player_loc"], _pin(past, "B"))
    shadow = g.call(FN_NORMAL_2D, x0 + 2700, y0 + 300)
    _connect(out(past), _pin(shadow, "A"))
    behind = g.call(FN_MUL_VV, x0 + 2940, y0 + 300)
    _connect(out(shadow), _pin(behind, "A"))
    _connect(pins["behind"], _pin(behind, "B"))
    spot = g.call(FN_ADD_VV, x0 + 3180, y0 + 300)
    _connect(out(trunk, "Location"), _pin(spot, "A"))
    _connect(out(behind), _pin(spot, "B"))
    # The trunk's transform is its foot; the pawn's centre is half a capsule up.
    stood = g.call(FN_ADD_VV, x0 + 3420, y0 + 300)
    _connect(out(spot), _pin(stood, "A"))
    _connect(pins["half_height"], _pin(stood, "B"))
    its = _loose_pin(tree, "AsInstancedStaticMeshComponent", is_input=False)
    wide = _author_wide(g, BEL.find_then_pin(known), its, out(trunk, "Scale"),
                        x0 + 2200, y0 - 900)
    raw = g.put(STALK_COVER_VAR, BEL.find_then_pin(wide), x0 + 3660, y0,
                pin=out(stood))

    # --- ...out of the player's sight ------------------------------------------
    stored = g.get(STALK_COVER_VAR, x0 + 3660, y0 + 300)
    line = g.call(FN_LINE_TRACE, x0 + 3960, y0 - 300, TraceChannel="TraceTypeQuery1",
                  bTraceComplex="false", bIgnoreSelf="true", DrawDebugType="None")
    _connect(stored, _pin(line, "Start"))
    _connect(pins["player_loc"], _pin(line, "End"))
    _connect(g.get(STALK_IGNORE_VAR, x0 + 3700, y0 - 160), _pin(line, "ActorsToIgnore"))
    _connect(raw, _pin(line, "execute"))
    blocked = g.branch(out(line), BEL.find_then_pin(line), x0 + 4260, y0 - 300)
    between = g.keep(_palette(g.ed, NODE_BREAK_HIT), x0 + 4260, y0 - 100)
    _connect(out(line, "OutHit"), _pin(between, "Hit"))
    # That tree, and no other: the same cell and the same instance of it.
    cell = g.op(FN_EQ_OO, _loose_pin(between, "HitComponent", is_input=False), its,
                x0 + 4560, y0 - 100)
    item = g.op(FN_EQ_II, _loose_pin(between, "HitItem", is_input=False),
                _loose_pin(hit, "HitItem", is_input=False), x0 + 4560, y0 + 60)
    shade = g.branch(g.op(FN_AND, cell, item, x0 + 4800, y0 - 100),
                     BEL.find_then_pin(blocked), x0 + 4600, y0 - 300)
    raw = BEL.find_then_pin(shade)

    # --- ...a step in (the sphere may have touched a crown, metres from its
    # trunk), and somewhere it can stand ---------------------------------------
    off = g.call(FN_DISTANCE_2D, x0 + 3900, y0 + 500)
    _connect(stored, _pin(off, "V1"))
    _connect(pins["player_loc"], _pin(off, "V2"))
    gains = g.call(FN_IN_RANGE, x0 + 4140, y0 + 500, Min=NPC_STALK_COVER_MIN_CM)
    _connect(out(off), _pin(gains, "Value"))
    _connect(pins["gain"], _pin(gains, "Max"))
    on_nav = g.call(FN_PROJECT_NAV, x0 + 3900, y0 + 300)
    _connect(stored, _pin(on_nav, "Point"))
    _connect(pins["nav_extent"], _pin(on_nav, "QueryExtent"))
    good = g.op(FN_AND, out(gains), out(on_nav), x0 + 4380, y0 + 400)
    walkable = g.branch(good, raw, x0 + 4900, y0)
    snapped = g.put(STALK_COVER_VAR, BEL.find_then_pin(walkable), x0 + 5200, y0,
                    pin=out(on_nav, "ProjectedLocation"))
    found = g.put(STALK_HIDDEN_VAR, snapped, x0 + 5500, y0, literal="true")
    missed = [BEL.find_else_pin(struck), _loose_pin(tree, "CastFailed", is_input=False),
              BEL.find_else_pin(known), BEL.find_else_pin(wide),
              BEL.find_else_pin(blocked), BEL.find_else_pin(shade),
              BEL.find_else_pin(walkable)]
    return found, missed, heading


def _author_cover(ed, exec_in, pins, x0, y0):
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
    step = g.put(STALK_ARRIVED_VAR, exec_in, x0, y0, literal="false")
    give_up = g.op(FN_ADD_FF, pins["now"], NPC_STALK_LEG_TIMEOUT_S, x0 + 60, y0 + 300)
    step = g.put(STALK_LEG_UNTIL_VAR, step, x0 + 300, y0, pin=give_up)
    count = g.op(FN_ADD_II, g.get(STALK_LEGS_VAR, x0 + 120, y0 + 440), 1,
                 x0 + 360, y0 + 300)
    step = g.put(STALK_LEGS_VAR, step, x0 + 600, y0, pin=count)

    # --- what the sweep ignores ----------------------------------------------
    clear = g.call(FN_ARR_CLEAR, x0 + 900, y0)
    _connect(g.get(STALK_IGNORE_VAR, x0 + 660, y0 + 300), _pin(clear, "TargetArray"))
    _connect(step, _pin(clear, "execute"))
    ground = g.call(FN_MOVEMENT_BASE, x0 + 900, y0 + 440)
    _connect(pins["self_pawn"], _pin(ground, "Pawn"))
    step = BEL.find_then_pin(clear)
    for i, actor in enumerate((out(ground), pins["self_pawn"])):
        add = g.call(FN_ARR_ADD, x0 + 1200 + 300 * i, y0)
        _connect(g.get(STALK_IGNORE_VAR, x0 + 1200 + 300 * i, y0 + 300),
                 _pin(add, "TargetArray"))
        _connect(actor, _pin(add, "NewItem"))
        _connect(step, _pin(add, "execute"))
        step = BEL.find_then_pin(add)

    # --- shared by every angle -----------------------------------------------
    sx, sy = x0, y0 + 800
    away = g.call(FN_SUB_VV, sx, sy)
    _connect(pins["self_loc"], _pin(away, "A"))
    _connect(pins["player_loc"], _pin(away, "B"))
    radial = g.call(FN_NORMAL_2D, sx + 240, sy)
    _connect(out(away), _pin(radial, "A"))
    # The sweeps start from the player's spot on the map, at the wendigo's own
    # height plus the lift: the trunks are tall, and the ground is ignored.
    here = g.call(FN_BREAK_VECTOR, sx, sy + 160)
    _connect(pins["self_loc"], _pin(here, "InVec"))
    there = g.call(FN_BREAK_VECTOR, sx, sy + 320)
    _connect(pins["player_loc"], _pin(there, "InVec"))
    high = g.op(FN_ADD_FF, out(here, "Z"), NPC_STALK_SWEEP_LIFT_CM, sx + 240, sy + 160)
    lifted = g.call(FN_MAKE_VECTOR, sx + 480, sy + 240)
    _connect(out(there, "X"), _pin(lifted, "X"))
    _connect(out(there, "Y"), _pin(lifted, "Y"))
    _connect(high, _pin(lifted, "Z"))
    far = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_ADVANCE_MIN_CM, sx + 720, sy)
    deep = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_ADVANCE_MAX_CM, sx + 720, sy + 160)
    near = g.op(FN_FMAX, deep, NPC_STALK_COVER_MIN_CM, sx + 960, sy + 160)
    gain = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_GAIN_MIN_CM, sx + 720, sy + 320)
    shared = dict(
        pins, radial=out(radial), lifted=out(lifted), far=far, near=near, gain=gain,
        up=out(g.call(FN_MAKE_VECTOR, sx + 240, sy + 480, Z=1.0)),
        behind=out(g.call(FN_MAKE_VECTOR, sx + 480, sy + 480, X=NPC_STALK_BEHIND_CM,
                          Y=NPC_STALK_BEHIND_CM, Z=NPC_STALK_BEHIND_CM)),
        half_height=out(g.call(FN_MAKE_VECTOR, sx + 720, sy + 480,
                               Z=NPC_CAPSULE_HALF_HEIGHT_CM)),
        nav_extent=out(g.call(FN_MAKE_VECTOR, sx + 960, sy + 480,
                              **dict(zip("XYZ", NPC_STALK_NAV_EXTENT_CM)))))

    # --- one sweep per angle, until one finds a tree -------------------------
    tails, missed, first = [], [step], None
    for i, angle in enumerate(NPC_STALK_ARC_DEG):
        found, missed, heading = _author_try(g, missed, angle, shared,
                                             x0 + 1900, y0 + 1300 * i)
        tails.append(found)
        first = heading if first is None else first

    # --- none: on round the player, in the open ------------------------------
    ox, oy = x0 + 1900, y0 + 1300 * len(NPC_STALK_ARC_DEG)
    closer = g.op(FN_SUB_FF, pins["gap"], NPC_STALK_OPEN_ADVANCE_CM, ox, oy + 300)
    bare = g.put(STALK_COVER_VAR, missed, ox + 1000, oy,
                 pin=_along(g, shared["lifted"], first, closer, ox + 240, oy + 300))
    on_nav = g.call(FN_PROJECT_NAV, ox + 1300, oy + 300)
    _connect(g.get(STALK_COVER_VAR, ox + 1060, oy + 300), _pin(on_nav, "Point"))
    _connect(out(g.call(FN_MAKE_VECTOR, ox + 1060, oy + 460,
                        **dict(zip("XYZ", NPC_STALK_OPEN_NAV_EXTENT_CM)))),
             _pin(on_nav, "QueryExtent"))
    walkable = g.branch(out(on_nav), bare, ox + 1600, oy)
    snapped = g.put(STALK_COVER_VAR, BEL.find_then_pin(walkable), ox + 1900, oy,
                    pin=out(on_nav, "ProjectedLocation"))
    tails.append(g.put(STALK_HIDDEN_VAR, snapped, ox + 2200, oy, literal="false"))
    return g.made, tails, BEL.find_else_pin(walkable)
