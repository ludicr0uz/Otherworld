"""body -- a cached Meshy rig as the bind works on it: Unreal's space,
centimetres, every primitive's vertices in one list."""

import glob
import os
from dataclasses import dataclass

from asset_pipeline.mannequin_bind import glb, paths, space
from asset_pipeline.mannequin_bind.bone_map import MESHY_BONES


@dataclass
class Body:
    spec_id: str
    mesh: glb.SkinnedMesh
    bones: list                  # parents first
    parents: dict                # bone -> parent bone or None
    joints: dict                 # bone -> rest position
    verts: list
    normals: list
    tangents: list               # (x, y, z, w), or [] if the file has none
    weights: list                # per vertex {bone: weight}
    slices: list                 # (start, end) per primitive
    triangles: list              # (a, b, c) over ``verts``

    def children(self, bone):
        return [b for b in self.bones if self.parents[b] == bone]

    def held_by(self, bone):
        """Vertex ids a bone has any hold on."""
        return [i for i, w in enumerate(self.weights) if w.get(bone, 0.0) > 0.0]


def rigged_glb(spec_id):
    """The rigged character itself: not the armature-only file beside it, nor
    an animation variant."""
    hits = sorted(glob.glob(os.path.join(paths.meshy_cache(spec_id), "rigged",
                                         "*rigged_character*.glb")))
    if not hits:
        raise FileNotFoundError(
            f"no rigged GLB for {spec_id} under {paths.meshy_cache(spec_id)}/rigged "
            "(fetch_monsters.py makes it)")
    return hits[0]


def _parents_first(bones, parents):
    out, seen = [], set()

    def visit(b):
        if b in seen:
            return
        if parents[b] is not None:
            visit(parents[b])
        seen.add(b)
        out.append(b)

    for b in bones:
        visit(b)
    return out


def from_mesh(mesh, spec_id=""):
    unknown = sorted(set(mesh.bones) - MESHY_BONES)
    missing = sorted(MESHY_BONES - set(mesh.bones))
    if unknown or missing:
        raise ValueError(
            f"{mesh.path}: not the Meshy humanoid rig (unknown bones {unknown}, "
            f"missing {missing}); bone_map.py lists what the bind understands")
    verts, normals, tangents, weights, slices, triangles = [], [], [], [], [], []
    for prim in mesh.primitives:
        start = len(verts)
        verts += [space.point_to_ue(p) for p in prim.positions]
        normals += [space.dir_swap(n) for n in prim.normals]
        tangents += [space.tangent_swap(t) for t in prim.tangents]
        weights += prim.weights
        triangles += [(a + start, b + start, c + start) for a, b, c in prim.triangles]
        slices.append((start, len(verts)))
    if tangents and len(tangents) != len(verts):
        raise ValueError(f"{mesh.path}: tangents on some primitives only")
    return Body(spec_id=spec_id, mesh=mesh,
                bones=_parents_first(mesh.bones, mesh.parents),
                parents=dict(mesh.parents),
                joints={b: space.point_to_ue(p) for b, p in mesh.joints.items()},
                verts=verts, normals=normals, tangents=tangents,
                weights=weights, slices=slices,
                triangles=triangles)


def load(spec_id):
    return from_mesh(glb.read_skinned(rigged_glb(spec_id)), spec_id)
