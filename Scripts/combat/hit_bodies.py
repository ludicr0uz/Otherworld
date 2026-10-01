"""The physics bodies a pellet can strike, fitted to the model that wears them.

hit_zones.py says which body is which zone; this says how big each body is.
The importer's physics asset wraps every bone's vertices in a box and then the
box in a capsule, so each body stands 4-8 cm proud of the skin: the zombie's
head was a 26 cm capsule round an 18 cm skull, and a round that passed a hand's
width from its ear was a head shot. fit_hit_bodies() refits every capsule to
the vertices its bone carries, and body_coverage() measures the result the way
a pellet meets it: rays through the bodies against rays through the mesh.
"""

from contextlib import contextmanager

import unreal

from combat.graph import _log
from combat.ragdoll import RAGDOLL_MESH_ROOT

# The share of a bone's vertices, from each end of an axis, left outside the
# fit: a few stray vertices (a tooth, a torn sleeve) must not set the size.
FIT_TRIM = 0.02
# A capsule is round and a head or a chest is not, so its radius sits between
# the body's two half-widths: 0 is the narrower one, 1 the wider.
FIT_ROUNDNESS = 0.5
# How far a capsule's rounded end reaches past its vertices, as a share of its
# radius. Neighbouring bodies meet where the skin's weights change hands, and
# two hemispheres meeting there leave a notch all round the joint.
FIT_END_OVERLAP = 0.25
# body_coverage()'s grid, and how much of what it finds the verifier allows.
COVERAGE_STEP_CM = 2.0
# Rays that strike a body but not the model, as a share of those that strike
# the model: what "forgiving" measures. The importer's bodies scored 0.35-0.45.
# Half of what is left is the grid itself: the cells along an outline.
COVERAGE_MAX_OVERHANG = 0.20
# ...the same for the head's body alone (the importer's: 0.75-0.9)...
COVERAGE_MAX_HEAD_OVERHANG = 0.30
# ...and the model's rays that strike no body: a shot that should have landed.
COVERAGE_MAX_UNCOVERED = 0.06
_MAX_BODIES = 256


def _bodies(pa):
    """{bone: SkeletalBodySetup}. The asset's own array is protected from
    Python, but each setup is a subobject under a predictable name."""
    out = {}
    for i in range(_MAX_BODIES):
        setup = unreal.find_object(pa, f"SkeletalBodySetup_{i}")
        if setup:
            out[str(setup.get_editor_property("bone_name"))] = setup
    return out


@contextmanager
def _posed(mesh):
    """A registered component wearing ``mesh`` in its reference pose: bone
    transforms to read and physics bodies to trace."""
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0, 0, -1000000))
    try:
        comp = actor.skeletal_mesh_component
        comp.set_skeletal_mesh_asset(mesh)
        comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
        yield comp
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)


def _dynamic_mesh(mesh):
    dm = unreal.DynamicMesh()
    dm, _ = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
        mesh, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD())
    return dm


def _clouds(dm, comp, bodies):
    """{body bone: [vertex]}: each vertex goes to the bone that weighs most on
    it, and a bone with no body of its own (a finger, a toe) to the nearest
    parent that has one -- the body that moves it in a ragdoll."""
    owner = {}
    for i in range(comp.get_num_bones()):
        bone = str(comp.get_bone_name(i))
        at = bone
        while at not in bodies and at not in ("", "None"):
            at = str(comp.get_parent_bone(at))
        owner[i] = at if at in bodies else None
    out = {bone: [] for bone in bodies}
    for i in range(dm.get_vertex_count()):
        _d, weights, ok = dm.get_vertex_bone_weights(i)
        if not ok or not weights:
            continue
        top = max(weights, key=lambda w: w.get_editor_property("weight"))
        body = owner.get(top.get_editor_property("bone_index"))
        if body:
            out[body].append(dm.get_vertex_position(i)[0])
    return out


def _span(values):
    """(middle, half-extent) of ``values`` with FIT_TRIM dropped off each end."""
    values = sorted(values)
    lo = values[int(FIT_TRIM * (len(values) - 1))]
    hi = values[int((1.0 - FIT_TRIM) * (len(values) - 1))]
    return (lo + hi) * 0.5, (hi - lo) * 0.5


def body_fit_plan(mesh):
    """[{bone, setup, center, radius, length}]: every capsule refitted.

    Each body keeps the importer's capsule axis -- the long axis of its
    vertices -- and gets a new centre, radius and length off the same vertices,
    measured in the mesh's reference pose and written in the bone's own space.
    A pure function of the mesh and the axes, so a rebuild plans the same
    numbers and the verifier can compare the saved asset to the plan.
    """
    pa = mesh.get_editor_property("physics_asset")
    if not pa:
        return []
    bodies = _bodies(pa)
    math = unreal.MathLibrary
    plan = []
    with _posed(mesh) as comp:
        clouds = _clouds(_dynamic_mesh(mesh), comp, bodies)
        for bone in sorted(bodies):
            geom = bodies[bone].get_editor_property("agg_geom")
            capsules = geom.get_editor_property("sphyl_elems")
            cloud = clouds[bone]
            if len(capsules) != 1 or len(cloud) < 8:
                raise RuntimeError(
                    f"{pa.get_name()}: {bone} has {len(capsules)} capsule(s) and "
                    f"{len(cloud)} vertices -- not a body this fit knows")
            xf = comp.get_socket_transform(
                bone, unreal.RelativeTransformSpace.RTS_COMPONENT)
            # The capsule runs down whichever of the importer's three axes the
            # vertices reach furthest along. The importer's own pick is not
            # always that one: the zombie's hips lay across the pelvis's depth.
            rot = capsules[0].get_editor_property("rotation")
            local_axes = [math.greater_greater_vector_rotator(v, rot)
                          for v in (unreal.Vector(1, 0, 0), unreal.Vector(0, 1, 0),
                                    unreal.Vector(0, 0, 1))]
            reach = [_span([p.dot(math.transform_direction(xf, a).normal())
                            for p in cloud])[1] for a in local_axes]
            # The capsule's own axis (Z) keeps a tie, so a refit of a fitted
            # body plans the same rotation.
            long_axis = max((2, 1, 0), key=lambda i: reach[i] + (0.5 if i == 2 else 0.0))
            if long_axis != 2:
                rot = math.make_rot_from_z(local_axes[long_axis])
            axes = [math.transform_direction(
                        xf, math.greater_greater_vector_rotator(v, rot)).normal()
                    for v in (unreal.Vector(1, 0, 0), unreal.Vector(0, 1, 0),
                              unreal.Vector(0, 0, 1))]
            (mu, hu), (mv, hv), (mt, ht) = (
                _span([p.dot(a) for p in cloud]) for a in axes)
            narrow, wide = sorted((hu, hv))
            radius = narrow + (wide - narrow) * FIT_ROUNDNESS
            # Never rounder than it is long: a capsule's ends are its radius.
            radius = min(radius, ht / (1.0 - FIT_END_OVERLAP)) if ht > 0 else radius
            length = max(0.0, 2.0 * (ht - radius * (1.0 - FIT_END_OVERLAP)))
            centre = axes[0] * mu + axes[1] * mv + axes[2] * mt
            local = math.inverse_transform_location(xf, centre)
            scale = xf.scale3d.x
            plan.append({
                "bone": bone, "setup": bodies[bone], "rotation": rot,
                "center": (round(local.x, 3), round(local.y, 3), round(local.z, 3)),
                "radius": round(radius / scale, 3),
                "length": round(length / scale, 3)})
    return plan


def saved_capsule(setup):
    """(center, radius, length) of a body's one capsule, as body_fit_plan
    writes them."""
    c = setup.get_editor_property("agg_geom").get_editor_property("sphyl_elems")[0]
    at = c.get_editor_property("center")
    return ((round(at.x, 3), round(at.y, 3), round(at.z, 3)),
            round(c.get_editor_property("radius"), 3),
            round(c.get_editor_property("length"), 3))


def fit_hit_bodies():
    """Refit every imported creature's physics bodies to its model.

    Every skeletal mesh under RAGDOLL_MESH_ROOT, as tune_ragdolls does: the
    same bodies are the ragdoll, and one that hugs the skin lies on the ground
    rather than a hand above it.
    """
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    for path in sorted(eas.list_assets(RAGDOLL_MESH_ROOT, recursive=True)):
        mesh = eas.load_asset(path.split(".")[0])
        if not isinstance(mesh, unreal.SkeletalMesh):
            continue
        plan = body_fit_plan(mesh)
        if not plan:
            continue
        pa = mesh.get_editor_property("physics_asset")
        pa.modify()
        for b in plan:
            setup = b["setup"]
            setup.modify()
            geom = setup.get_editor_property("agg_geom")
            capsules = geom.get_editor_property("sphyl_elems")
            # Elements come out of the array as copies: edit one, put it back.
            capsule = capsules[0]
            capsule.set_editor_properties({
                "center": unreal.Vector(*b["center"]), "rotation": b["rotation"],
                "radius": b["radius"], "length": b["length"]})
            geom.set_editor_property("sphyl_elems", [capsule])
            setup.set_editor_property("agg_geom", geom)
            want = (b["center"], b["radius"], b["length"])
            if saved_capsule(setup) != want:
                raise RuntimeError(f"{pa.get_name()}: {b['bone']}'s capsule did "
                                   f"not stick: {saved_capsule(setup)} != {want}")
        eas.save_loaded_asset(pa)
        cover = body_coverage(mesh)
        _log(f"{pa.get_name()}: {len(plan)} bodies fitted to the model -- "
             f"overhang {cover['overhang']:.2f}, uncovered {cover['uncovered']:.2f}")


def body_coverage(mesh, rows=None):
    """How the bodies sit on the model, seen from the front and from the side.

    A grid of parallel rays is traced twice, against the physics bodies
    (K2_LineTraceComponent, what the fire graph asks) and against the render
    mesh (a BVH over its triangles), in the reference pose. Returns the
    ``overhang`` (body but no model) and ``uncovered`` (model but no body)
    ray counts as shares of the model's rays, and ``head_overhang`` for the
    rays that struck a head body alone. ``rows``, a list, collects the picture.
    """
    spatial = unreal.GeometryScript_MeshSpatial
    dm = _dynamic_mesh(mesh)
    bvh = [x for x in spatial.build_bvh_for_mesh(dm)
           if isinstance(x, unreal.GeometryScriptDynamicMeshBVH)][0]
    options = unreal.GeometryScriptSpatialQueryOptions()
    bounds = mesh.get_bounds()
    o, e = bounds.origin, bounds.box_extent
    reach = max(e.x, e.y) + 50.0
    counts = {"model": 0, "overhang": 0, "uncovered": 0, "head": 0,
              "head_overhang": 0}
    with _posed(mesh) as comp:
        base = comp.get_world_location()
        for along, across, lo, hi in (
                (unreal.Vector(0, 1, 0), unreal.Vector(1, 0, 0), o.x - e.x, o.x + e.x),
                (unreal.Vector(1, 0, 0), unreal.Vector(0, 1, 0), o.y - e.y, o.y + e.y)):
            z = o.z + e.z + 3 * COVERAGE_STEP_CM
            while z > o.z - e.z:
                row = ""
                u = lo - 3 * COVERAGE_STEP_CM
                while u <= hi + 3 * COVERAGE_STEP_CM:
                    start = across * u + unreal.Vector(0, 0, z) - along * reach
                    end = start + along * (2 * reach)
                    struck = comp.line_trace_component(
                        base + start, base + end, False, False, False)
                    bone = str(struck[2]) if struck else None
                    ray = spatial.find_nearest_ray_intersection_with_mesh(
                        dm, bvh, start, along, options)
                    model = [x for x in ray if isinstance(
                        x, unreal.GeometryScriptRayHitResult)][0].hit
                    head = bone is not None and bone.lower() == "head"
                    counts["model"] += model
                    counts["overhang"] += bool(bone) and not model
                    counts["uncovered"] += model and not bone
                    counts["head"] += head and model
                    counts["head_overhang"] += head and not model
                    row += (".", "m", "o", "#")[2 * bool(bone) + model]
                    u += COVERAGE_STEP_CM
                if rows is not None:
                    rows.append(f"{z:6.1f} {row}")
                z -= COVERAGE_STEP_CM
    return {"overhang": counts["overhang"] / max(1, counts["model"]),
            "uncovered": counts["uncovered"] / max(1, counts["model"]),
            "head_overhang": counts["head_overhang"] / max(1, counts["head"]),
            "counts": counts}
