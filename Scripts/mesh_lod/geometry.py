"""In the editor: a source mesh cut into the geometry of each mesh LOD.

The cutting itself -- dropping a share of a slot's pieces by a hash of the
piece, simplifying, growing the survivors back to the area the slot covered
-- is forest_import/tree_assets.py's, which built the trees this was first
run on; what is decided here is how much, per LOD and per slot (spec.py).
Every LOD is cut from the source, never from the LOD above it: an error made
simplifying one does not carry into the next.
"""

import unreal

from forest_import import tree_assets as cut
from mesh_lod import spec as S

GS_SPLIT = unreal.GeometryScript_MeshDecomposition
GS_SIMPLIFY = unreal.GeometryScript_MeshSimplification
GS_EDITS = unreal.GeometryScript_MeshEdits
SOLID_SLACK = 1.15               # a solid slot this far over budget loses pieces


def _copy(dm):
    return GS_EDITS.append_mesh(unreal.DynamicMesh(), dm, unreal.Transform())


def foliage_slots(mesh, spec):
    """The material slots cut as foliage: the spec's, or those whose material
    is masked."""
    if spec.foliage_slots:
        return set(spec.foliage_slots)
    found = set()
    for index, slot in enumerate(mesh.static_materials):
        material = slot.material_interface
        if material and material.get_blend_mode() == unreal.BlendMode.BLEND_MASKED:
            found.add(index)
    return found


def read_source(mesh):
    """{slot: its part of the source's full-detail geometry}."""
    dm = cut._source_geometry(mesh)
    _, parts, slots = GS_SPLIT.split_mesh_by_material_i_ds(dm, None)
    return dict(zip(list(slots), list(parts)))


def _cut_foliage(part, plan, spec):
    pieces, area = cut._piece_count(part), cut._area(part)
    if plan.keep_pieces < 1.0:
        cut._drop_pieces(part, plan.keep_pieces)
    if plan.simplify:
        opts = unreal.GeometryScriptSimplifyMeshOptions()
        opts.set_editor_property("method", cut.SIMPLIFY_METHODS["attribute"])
        GS_SIMPLIFY.apply_simplify_to_triangle_count(part, plan.triangles, opts)
    grow = cut._restore_area(part, area * spec.foliage_area) if spec.foliage_area else 1.0
    return pieces, cut._piece_count(part), grow


def _drop_smallest(part, target):
    """Delete the smallest pieces until ``target`` triangles are left; the
    largest piece always stays. Returns how many pieces went."""
    ids = cut._piece_ids(part)
    sizes = {}
    for piece in ids:
        sizes[piece] = sizes.get(piece, 0) + 1
    order = sorted(sizes, key=lambda piece: (sizes[piece], piece))[:-1]
    doomed, left = set(), len(ids)
    for piece in order:
        if left <= target:
            break
        doomed.add(piece)
        left -= sizes[piece]
    if doomed:
        GS_EDITS.delete_triangles_from_mesh(part, unreal.GeometryScript_List.convert_array_to_index_list(
            [tid for tid, piece in enumerate(ids) if piece in doomed]))
        unreal.GeometryScript_MeshRepair.compact_mesh(part)
    return len(doomed)


def _cut_solid(part, target):
    """Simplify a solid slot, then drop its smallest pieces if that was not
    enough: a slot of boughs and twigs is thousands of closed tubes, and a
    tube cannot be simplified to nothing. Returns how many pieces went."""
    opts = unreal.GeometryScriptSimplifyMeshOptions()
    opts.set_editor_property("method", cut.SIMPLIFY_METHODS["volume"])
    GS_SIMPLIFY.apply_simplify_to_triangle_count(part, target, opts)
    if part.get_triangle_count() > target * SOLID_SLACK:
        return _drop_smallest(part, target)
    return 0


def build_lods(parts, foliage, spec, log):
    """The geometry of each mesh LOD, and per LOD {slot: triangles}."""
    counts = {slot: part.get_triangle_count() for slot, part in parts.items()}
    pieces = {slot: cut._piece_count(parts[slot]) for slot in parts if slot in foliage}
    lods, table = [], []
    for lod, target in enumerate(S.lod_targets(spec, sum(counts.values()))):
        budgets = S.slot_budgets(spec, counts, target, lod)
        whole, row = unreal.DynamicMesh(), {}
        for slot in sorted(parts):
            part = _copy(parts[slot])
            if budgets[slot] < counts[slot]:
                if slot in foliage:
                    plan = S.foliage_cut(spec, counts[slot], pieces[slot], budgets[slot])
                    before, after, grow = _cut_foliage(part, plan, spec)
                    log(f"  LOD{lod} slot {slot} (foliage): {counts[slot]} -> "
                        f"{part.get_triangle_count()} tris, {before} -> {after} pieces, "
                        f"grown x{grow:.2f}")
                else:
                    gone = _cut_solid(part, budgets[slot])
                    log(f"  LOD{lod} slot {slot}: {counts[slot]} -> "
                        f"{part.get_triangle_count()} tris"
                        + (f", {gone} smallest pieces dropped" if gone else ""))
            row[slot] = part.get_triangle_count()
            GS_EDITS.append_mesh(whole, part, unreal.Transform())
        lods.append(whole)
        table.append(row)
    return lods, table
