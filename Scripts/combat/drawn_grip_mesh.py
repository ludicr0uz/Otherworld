"""A gun's real mesh as a solid the finger fit can bend fingers onto
(finger_fit's ``distance`` and ``toward``), in the gun actor's frame.

Every drawn mesh component of a spawned copy of the gun's Blueprint is
copied into a GeometryScript dynamic mesh, moved into the actor's frame and
given a BVH: the distance is signed (below 0 inside), the nearest surface
point is the mesh's own. The outline's boxes are not used: they are the
silhouette the hands are seated by, and miss the trigger and the guard
(drawn_grip_consts.TRIGGER is where the trigger is, read off this).

A query is about 20 us; a finger's fit asks a few thousand.
"""

import unreal

GS = unreal.GeometryScript_MeshSpatial
OPTS = unreal.GeometryScriptSpatialQueryOptions()
# Where the copy is spawned: out of the way of anything in the level.
SPAWN_AT = unreal.Vector(0.0, 0.0, 100000.0)


def surfaces(actor):
    """[(component name, DynamicMesh, BVH)] of every drawn mesh on
    ``actor``, each moved into the actor's frame."""
    root = actor.get_actor_transform()
    out = []
    for c in actor.get_components_by_class(unreal.MeshComponent):
        if not c.is_visible():
            continue
        if isinstance(c, unreal.StaticMeshComponent) and c.static_mesh:
            dm = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
                c.static_mesh, unreal.DynamicMesh(),
                unreal.GeometryScriptCopyMeshFromAssetOptions(),
                unreal.GeometryScriptMeshReadLOD())[0]
        elif isinstance(c, unreal.SkeletalMeshComponent) and c.get_skeletal_mesh_asset():
            dm = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
                c.get_skeletal_mesh_asset(), unreal.DynamicMesh(),
                unreal.GeometryScriptCopyMeshFromAssetOptions(),
                unreal.GeometryScriptMeshReadLOD())[0]
        else:
            continue
        if unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm) == 0:
            continue
        rel = unreal.MathLibrary.make_relative_transform(c.get_world_transform(), root)
        unreal.GeometryScript_MeshTransforms.transform_mesh(dm, rel)
        out.append((c.get_name(), dm, GS.build_bvh_for_mesh(dm)[1]))
    return out


class MeshSolid:
    """The gun's surfaces as a finger_fit solid (cm, the actor's frame)."""

    def __init__(self, found):
        self.found = list(found)

    def __bool__(self):
        return bool(self.found)

    def _nearest(self, p):
        """(signed distance, nearest surface point): inside any part, the
        deepest; else the nearest."""
        v = unreal.Vector(*p)
        found = []
        for _name, dm, bvh in self.found:
            q = GS.find_nearest_point_on_mesh(dm, bvh, v, OPTS)[1].position
            d = (v - q).length()
            if GS.is_point_inside_mesh(dm, bvh, v, OPTS)[1]:
                d = -d
            found.append((d, (q.x, q.y, q.z)))
        inside = [f for f in found if f[0] < 0.0]
        return min(inside or found, key=lambda f: f[0])

    def distance(self, p):
        return self._nearest(p)[0]

    def toward(self, p):
        return self._nearest(p)[1]


def gun_solid(blueprint):
    """The MeshSolid of ``blueprint``'s gun (its name under /Game/Weapons),
    measured off a copy spawned for it and destroyed again."""
    cls = unreal.load_class(None, f"/Game/Weapons/{blueprint}.{blueprint}_C")
    if cls is None:
        raise RuntimeError(f"no class /Game/Weapons/{blueprint}")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(cls, SPAWN_AT)
    try:
        return MeshSolid(surfaces(actor))
    finally:
        actors.destroy_actor(actor)
