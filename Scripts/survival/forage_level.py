"""Putting the forage into a generated level, inside the editor.

Reads what the level already contains rather than re-running the generator:
the terrain actor (labelled <Level>_Terrain), the tree cells (HISM_Tree*__*,
see forest_import/trees.py) for trunk positions, and the PlayerStart. So it
places against the level as built, whatever size, seed or density that was,
and a level regenerated since is simply placed again.

Heights come from the terrain MESH, not from a trace (survival/terrain_heights.py
has the measurement): a level loaded in the same Python call has not cooked
its terrain collision yet, so every trace misses. A world trace would also
land on the tree canopy -- the trap CLAUDE.md records for navmesh probes --
and hang mushrooms in the leaves; the mesh has no trees in it.

Every placed actor carries FORAGE_TAG and is deleted and re-placed on each run,
so the pass is idempotent. Placed actors need no per-instance settings:
consumables default to Dropped = True (see consumables.py).
"""

import random

import unreal

from combat.log import _log
from survival.forage_placement import scatter_forage
from survival.terrain_heights import TriangleHeights
from survival.paths import CANTEEN_CLASS_PATH, MUSHROOM_CLASS_PATH
from survival.tuning import FORAGE_SEED
from world.level_save import save_level

FORAGE_TAG = "OW_Forage"
FORAGE_LIFT_CM = 1.0       # sit on the ground, not in it
CLASS_FOR = {"Mushroom": MUSHROOM_CLASS_PATH, "Canteen": CANTEEN_CLASS_PATH}


def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _trunks(actors):
    out = []
    for a in actors:
        label = a.get_actor_label()
        if not (label.startswith("HISM_Tree") and "__" in label):
            continue
        for comp in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
            for i in range(comp.get_instance_count()):
                t = comp.get_instance_transform(i, True)
                if t is not None:
                    out.append((t.translation.x, t.translation.y))
    return out


def _terrain_heights(ground):
    """The terrain component's mesh, in world space, as a height lookup."""
    mesh = ground.get_editor_property("static_mesh")
    xf = ground.get_world_transform()
    verts, tris = [], []
    for section in range(mesh.get_num_sections(0)):
        v, t, _n, _uv, _tan = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(
            mesh, 0, section)
        base = len(verts)
        for p in v:
            w = xf.transform_location(p)
            verts.append((w.x, w.y, w.z))
        tris.extend(base + i for i in t)
    return TriangleHeights(verts, tris)


def place_forage(level_path):
    """Replace this level's forage and save it. Returns {kind: count placed}."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.load_level(level_path):
        raise RuntimeError(f"could not load {level_path}")
    sub = _actors()
    actors = sub.get_all_level_actors()

    stale = [a for a in actors if a.actor_has_tag(FORAGE_TAG)]
    if stale:
        sub.destroy_actors(stale)
    actors = [a for a in actors if a not in stale]

    terrain = next((a for a in actors
                    if a.get_actor_label().endswith("_Terrain")), None)
    if terrain is None:
        raise RuntimeError(f"{level_path} has no *_Terrain actor")
    ground = terrain.get_editor_property("static_mesh_component")
    origin, extent = terrain.get_actor_bounds(False)
    start = next((a for a in actors if isinstance(a, unreal.PlayerStart)), None)
    start_xy = ((start.get_actor_location().x, start.get_actor_location().y)
                if start else (origin.x, origin.y))

    trunks = _trunks(actors)
    spots = scatter_forage((origin.x - extent.x, origin.x + extent.x),
                           (origin.y - extent.y, origin.y + extent.y),
                           trunks, start_xy)

    heights = _terrain_heights(ground)
    classes = {k: unreal.load_class(None, p) for k, p in CLASS_FOR.items()}
    rng = random.Random(FORAGE_SEED)
    placed, missed = {}, 0
    for kind, x, y in spots:
        z = heights.height(x, y)
        if z is None:
            missed += 1
            continue
        yaw = rng.uniform(0.0, 360.0)
        actor = sub.spawn_actor_from_class(
            classes[kind], unreal.Vector(x, y, z + FORAGE_LIFT_CM),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        n = placed.get(kind, 0) + 1
        placed[kind] = n
        actor.set_actor_label(f"Forage_{kind}_{n:03d}")
        actor.set_editor_property("tags", [unreal.Name(FORAGE_TAG)])

    if missed:
        raise RuntimeError(f"{level_path}: {missed} forage spots are off the "
                           "terrain mesh; nothing saved")
    save_level(level_path)
    _log(f"{level_path}: placed {placed} around {len(trunks)} trunks "
         f"({len(stale)} old forage removed)")
    return placed


def forage_in_level(level_path):
    """The forage actors currently in this level (for the verifier)."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.load_level(level_path):
        raise RuntimeError(f"could not load {level_path}")
    return [a for a in _actors().get_all_level_actors() if a.actor_has_tag(FORAGE_TAG)]
