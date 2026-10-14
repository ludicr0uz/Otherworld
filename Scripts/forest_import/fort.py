"""Place the Horde Survival fort's rocks into the open level, and verify them.

Called by the generated import_<Level>.py (step 5d) and verify_<Level>.py of
a level in forest_generator/horde_layout.HORDE_LEVELS, with the rocks the
generator laid out (``horde_layout.fort_rock_data``: one dict a rock). Each rock is a
StaticMeshActor of a committed moss rock scan, blocking everything, so the
player and the zombies stop at it and the navmesh is cut round it; nothing
is written to the meshes.

The verifier holds the actors to the layout and then measures the wall as a
player meets it: a ray across the ring every half degree at knee and waist
height, which a rock must stop everywhere but at the openings (and, at the
waist, a crack narrower than a pawn), each opening clear for at least the
layout's ``opening_cm``.
"""

import math

import unreal

from forest_generator.horde_layout import layout_for

FORT_TAG = "OW_FortRock"
LABEL_PREFIX = "Fort_Rock_"
RAY_STEP_DEG = 0.5
# (height above the ground, the widest crack allowed there). At knee height
# the wall is shut; at the waist two pointed scans can leave a V between
# them (11 cm, measured), which nothing the size of a pawn gets through.
RAY_HEIGHTS_CM = ((30.0, 0.0), (80.0, 40.0))


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def place_fort(rocks, actor_sub, asset_sub):
    """Spawn one StaticMeshActor per rock. Returns how many were placed."""
    placed = 0
    for i, rock in enumerate(rocks):
        mesh = asset_sub.load_asset(rock["mesh"])
        if not mesh:
            unreal.log_error(f"[GEN] Missing fort rock mesh {rock['mesh']}")
            continue
        actor = actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(rock["x"], rock["y"], rock["z"]),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=rock["yaw"]))
        actor.set_actor_label(f"{LABEL_PREFIX}{i:02d}")
        actor.set_folder_path("Fort")
        actor.set_actor_scale3d(unreal.Vector(rock["scale"], rock["scale"], rock["scale"]))
        actor.tags = [FORT_TAG]
        comp = actor.static_mesh_component
        comp.set_mobility(unreal.ComponentMobility.STATIC)
        comp.set_static_mesh(mesh)
        comp.set_collision_profile_name("BlockAll")
        comp.set_editor_property("can_ever_affect_navigation", True)
        placed += 1
    _log(f"Placed {placed} fort rocks")
    return placed


def _rock_actors(actors):
    return sorted((a for a in actors if a.get_actor_label().startswith(LABEL_PREFIX)),
                  key=lambda a: a.get_actor_label())


def verify_fort(check, actors, rocks, level):
    """Checks over the saved fort, in the verify script's harness."""
    layout = layout_for(level)
    found = _rock_actors(actors)
    check("Fort Rock Count", len(found) == len(rocks),
          f"(expected {len(rocks)}, got {len(found)})")
    bad_place, bad_mesh, bad_coll, bad_height = [], [], [], []
    lo, hi = layout.rock_visible_cm
    for actor, rock in zip(found, rocks):
        label = actor.get_actor_label()
        loc = actor.get_actor_location()
        if (math.hypot(loc.x - rock["x"], loc.y - rock["y"]) > 1.0
                or abs(loc.z - rock["z"]) > 1.0
                or abs(actor.get_actor_scale3d().z - rock["scale"]) > 1e-3):
            bad_place.append(label)
        comp = actor.static_mesh_component
        mesh = comp.static_mesh
        if not mesh or mesh.get_path_name().split(".")[0] != rock["mesh"]:
            bad_mesh.append(label)
        if (comp.get_collision_enabled() != unreal.CollisionEnabled.QUERY_AND_PHYSICS
                or not comp.get_editor_property("can_ever_affect_navigation")
                or FORT_TAG not in [str(t) for t in actor.tags]):
            bad_coll.append(label)
        _origin, extent = actor.get_actor_bounds(False)
        top = _origin.z + extent.z - rock["ground"]
        if not lo - 2.0 <= top <= hi + 2.0:
            bad_height.append(f"{label} {top:.0f} cm")
    check("Fort Rocks Where Laid Out", not bad_place, f"{bad_place[:5]}")
    check("Fort Rocks Are The Moss Scans", not bad_mesh, f"{bad_mesh[:5]}")
    check("Fort Rocks Block And Cut The Navmesh", not bad_coll, f"{bad_coll[:5]}")
    check("Fort Rocks Chest High", not bad_height and bool(found),
          f"(tops {lo:.0f}-{hi:.0f} cm above the ground) {bad_height[:5]}")
    for height, crack_cm in RAY_HEIGHTS_CM:
        _check_wall(check, layout, rocks, height, crack_cm)


def _check_wall(check, layout, rocks, height, crack_cm):
    """Rays across the ring at ``height`` above the ground: the openings are
    the runs that pass wider than ``crack_cm``, and there must be one per
    opening, each as wide as it asks, with every other ray stopped by a
    rock."""
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    ground = sum(r["ground"] for r in rocks) / max(1, len(rocks))
    radius = layout.fort_radius_cm
    steps = int(round(360.0 / RAY_STEP_DEG))
    clear, strangers = [], set()
    for i in range(steps):
        phi = math.radians(i * RAY_STEP_DEG)
        c, s = math.cos(phi), math.sin(phi)
        start = unreal.Vector((radius - 450.0) * c, (radius - 450.0) * s, ground + height)
        end = unreal.Vector((radius + 450.0) * c, (radius + 450.0) * s, ground + height)
        actor = _hit_actor(world, start, end)
        clear.append(actor is None)
        if actor is not None and FORT_TAG not in [str(t) for t in actor.tags]:
            strangers.add(actor.get_actor_label())
    step_cm = math.radians(RAY_STEP_DEG) * radius
    runs = _clear_runs(clear)
    cracks = [round(n * step_cm) for _start, n in runs if n * step_cm <= crack_cm]
    runs = [(start, n) for start, n in runs if n * step_cm > crack_cm]
    widths = [n * step_cm for _start, n in runs]
    centres = [(start + (n - 1) / 2.0) * RAY_STEP_DEG % 360.0 for start, n in runs]
    want = sorted(layout.opening_yaws_deg)
    matched = len(runs) == len(want) and all(
        min(abs((c - w + 180.0) % 360.0 - 180.0) for c in centres) < 10.0 for w in want)
    check(f"Fort Wall Openings At {height:.0f} cm", matched and not strangers,
          f"(clear runs at {[round(c) for c in centres]} deg, expected {want}; "
          f"cracks under {crack_cm:.0f} cm: {cracks}; "
          f"other actors hit: {sorted(strangers)[:5]})")
    check(f"Fort Openings Wide Enough At {height:.0f} cm",
          bool(widths) and min(widths) >= layout.opening_cm,
          f"({[round(w) for w in widths]} cm at the ring, at least "
          f"{layout.opening_cm:.0f})")


def _clear_runs(clear):
    """(first index, length) of each run of clear rays round the circle."""
    n = len(clear)
    if all(clear) or not any(clear):
        return [(0, n)] if all(clear) else []
    first_blocked = clear.index(False)
    runs, i = [], first_blocked
    while i < first_blocked + n:
        if clear[i % n]:
            j = i
            while clear[j % n] and j < first_blocked + n:
                j += 1
            runs.append((i % n, j - i))
            i = j
        else:
            i += 1
    return runs


def _hit_actor(world, start, end):
    hit = unreal.SystemLibrary.line_trace_single(
        world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
        unreal.DrawDebugTrace.NONE, True)
    if isinstance(hit, tuple):
        hit = hit[-1] if hit and hit[0] else None
    if hit is None:
        return None
    parts = hit.to_tuple()
    blocking = parts[0]
    if not blocking:
        return None
    for value in parts:
        if isinstance(value, unreal.Actor):
            return value
    return None
