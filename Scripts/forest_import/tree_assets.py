"""Build the derived tree meshes under /Game/Forest/Trees, and verify them.

    Scripts/dev/uepy.py Scripts/forest_import/tree_assets.py   # standalone

The generated import_<Level>.py calls ensure_tree_assets() before it plants.
What is built, and why, is forest_generator/tree_meshes.py; this file only
turns a recipe into an asset.

The scan a recipe names is read and never written: the first build duplicates
it to the new path, and every change lands on the duplicate. A built mesh is
tagged with its recipe's stamp, so a later import skips it -- the five take
about two minutes between them, most of it simplifying the 2 M-triangle
deciduous tree -- until the recipe changes.

A build is: read the scan's full-detail mesh, move the trunk onto the origin,
cut each foliage slot (drop a share of its pieces, simplify the rest, grow
them back to the area the slot covered), write it to the copy with the
recipe's Nanite settings.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forest_generator.tree_meshes import (  # noqa: E402
    PIVOT_TOLERANCE_CM, RECIPE_TAG, TREE_MESH_RECIPES)

GS_ASSET = unreal.GeometryScript_AssetUtils
GS_GROUPS = unreal.GeometryScript_PolyGroups
GS_LIST = unreal.GeometryScript_List
GS_QUERY = unreal.GeometryScript_MeshQueries
GS_SPLIT = unreal.GeometryScript_MeshDecomposition
GS_SIMPLIFY = unreal.GeometryScript_MeshSimplification
SIMPLIFY_METHODS = {
    "attribute": unreal.GeometryScriptRemoveMeshSimplificationType.ATTRIBUTE_AWARE,
    "volume": unreal.GeometryScriptRemoveMeshSimplificationType.VOLUME_PRESERVING,
}
SUCCESS = unreal.GeometryScriptOutcomePins.SUCCESS


def _log(msg):
    unreal.log_warning(f"[TREES] {msg}")


def _eas():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _must_load(path):
    asset = _eas().load_asset(path)
    if not asset:
        raise RuntimeError(f"missing asset {path}")
    return asset


def _source_geometry(source):
    """The scan's full-detail mesh, with the normals it is rendered with."""
    opts = unreal.GeometryScriptCopyMeshFromAssetOptions()
    opts.set_editor_property("apply_build_settings", True)
    opts.set_editor_property("request_tangents", True)
    lod = unreal.GeometryScriptMeshReadLOD()
    lod.set_editor_property("lod_type", unreal.GeometryScriptLODType.SOURCE_MODEL)
    lod.set_editor_property("lod_index", 0)
    dm, outcome = GS_ASSET.copy_mesh_from_static_mesh(
        source, unreal.DynamicMesh(), opts, lod)
    if outcome != SUCCESS:
        raise RuntimeError(f"could not read {source.get_path_name()}: {outcome}")
    return dm


def _piece_ids(dm):
    """Per triangle, the id of the disconnected piece it belongs to."""
    layer = unreal.GeometryScriptGroupLayer()
    GS_GROUPS.enable_polygroups(dm)
    GS_GROUPS.convert_components_to_polygroups(dm, layer)
    _, ids = GS_GROUPS.get_all_triangle_polygroup_i_ds(
        dm, layer, unreal.GeometryScriptIndexList())
    return list(GS_LIST.convert_index_list_to_array(ids))


def _piece_count(dm):
    return len(set(_piece_ids(dm)) - {-1})


def _area(dm):
    return GS_QUERY.get_mesh_volume_area(dm)[0]


def _drop_pieces(dm, keep):
    """Delete all but ``keep`` of the pieces. Which ones is a hash of the
    piece's id, so it is the same every build and unrelated to where in the
    crown the piece is."""
    doomed = [tid for tid, piece in enumerate(_piece_ids(dm))
              if piece >= 0 and (piece * 2654435761 % 4294967296) / 4294967296 >= keep]
    unreal.GeometryScript_MeshEdits.delete_triangles_from_mesh(
        dm, GS_LIST.convert_array_to_index_list(doomed))
    unreal.GeometryScript_MeshRepair.compact_mesh(dm)


def _restore_area(dm, area_wanted):
    """Grow every piece about its own centre until the section has the area
    wanted: what it had before it was cut, or a share of that. Simplifying a curled leaf flattens it and
    drops a few of the smallest; grown back, the canopy covers what it did."""
    grow = (area_wanted / max(_area(dm), 1e-6)) ** 0.5
    if grow <= 1.001:
        return 1.0
    _, tri_list, _ = GS_QUERY.get_all_triangle_indices(dm, False)
    _, pos_list, _ = GS_QUERY.get_all_vertex_positions(dm, False)
    triangles = GS_LIST.convert_triangle_list_to_array(tri_list)
    positions = [(v.x, v.y, v.z) for v in GS_LIST.convert_vector_list_to_array(pos_list)]
    piece_of = {}                    # vertex id -> piece id
    for tri, piece in zip(triangles, _piece_ids(dm)):
        if piece >= 0:
            piece_of[tri.x] = piece_of[tri.y] = piece_of[tri.z] = piece
    sums = {}                        # piece id -> [x, y, z, vertex count]
    for vid, piece in piece_of.items():
        acc = sums.setdefault(piece, [0.0, 0.0, 0.0, 0])
        x, y, z = positions[vid]
        acc[0] += x
        acc[1] += y
        acc[2] += z
        acc[3] += 1
    moved = []
    for vid, (x, y, z) in enumerate(positions):
        piece = piece_of.get(vid)
        if piece is None:
            moved.append(unreal.Vector(x, y, z))
            continue
        sx, sy, sz, n = sums[piece]
        cx, cy, cz = sx / n, sy / n, sz / n
        moved.append(unreal.Vector(cx + (x - cx) * grow, cy + (y - cy) * grow,
                                   cz + (z - cz) * grow))
    unreal.GeometryScript_MeshEdits.set_all_mesh_vertex_positions(
        dm, GS_LIST.convert_array_to_vector_list(moved))
    return grow


def _cut_sections(dm, cuts):
    """Simplify each cut's material slot to its budget (tree_meshes.SectionCut)
    and return the mesh put back together. Slots are simplified apart from
    each other, so a budget is spent where the recipe put it."""
    if not cuts:
        return dm
    by_slot = {c.slot: c for c in cuts}
    _, parts, slots = GS_SPLIT.split_mesh_by_material_i_ds(dm, None)
    whole = unreal.DynamicMesh()
    for part, slot in sorted(zip(parts, slots), key=lambda ps: ps[1]):
        cut = by_slot.get(slot)
        if cut:
            before = part.get_triangle_count()
            opts = unreal.GeometryScriptSimplifyMeshOptions()
            opts.set_editor_property("method", SIMPLIFY_METHODS[cut.method])
            pieces, area = _piece_count(part), _area(part)
            if cut.keep_pieces < 1.0:
                _drop_pieces(part, cut.keep_pieces)
            if cut.triangles_per_piece is not None:
                target = int(_piece_count(part) * cut.triangles_per_piece)
                GS_SIMPLIFY.apply_simplify_to_triangle_count(part, target, opts)
            share = float(cut.restore_area)
            grow = _restore_area(part, area * share) if share else 1.0
            _log(f"  slot {slot}: {before} -> {part.get_triangle_count()} tris, "
                 f"{pieces} -> {_piece_count(part)} pieces, grown x{grow:.2f}")
        unreal.GeometryScript_MeshEdits.append_mesh(whole, part, unreal.Transform())
    return whole


def _nanite_settings(recipe):
    """The copy's Nanite build settings. A fresh struct, never the scan's own:
    the struct ``get_editor_property("nanite_settings")`` returns is still
    bound to its mesh, so setting a field on it edits the scan in memory and
    marks its package dirty -- one Save All from overwriting it."""
    ns = unreal.MeshNaniteSettings()
    ns.set_editor_property("enabled", True)
    ns.set_editor_property("keep_percent_triangles", recipe.keep_triangles)
    ns.set_editor_property(
        "shape_preservation",
        unreal.NaniteShapePreservation.PRESERVE_AREA if recipe.preserve_area
        else unreal.NaniteShapePreservation.NONE)
    if recipe.fallback_triangles is not None:
        ns.set_editor_property("fallback_target",
                               unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
        ns.set_editor_property("fallback_percent_triangles",
                               recipe.fallback_triangles)
    return ns


def _write_geometry(dm, mesh, nanite):
    """Replace ``mesh``'s geometry, keeping its material slots."""
    opts = unreal.GeometryScriptCopyMeshToAssetOptions()
    opts.set_editor_property("enable_recompute_normals", False)
    opts.set_editor_property("enable_recompute_tangents", False)
    opts.set_editor_property("replace_materials", False)
    opts.set_editor_property("apply_nanite_settings", True)
    opts.set_editor_property("new_nanite_settings", nanite)
    _, outcome = GS_ASSET.copy_mesh_to_static_mesh(
        dm, mesh, opts, unreal.GeometryScriptMeshWriteLOD())
    if outcome != SUCCESS:
        raise RuntimeError(f"could not write {mesh.get_path_name()}: {outcome}")
    # The copy leaves the settings on the source model; the build reads these.
    unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(
        mesh, nanite, apply_changes=True)


def _refit_collision(mesh):
    """The duplicate's hull is the scan's. Trees are hit and walked round
    through their complex collision (the scan's own setting, kept); the simple
    shape is refitted so that none is left where the scan's trunk stood."""
    sms = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    sms.remove_collisions(mesh)
    sms.add_simple_collisions(mesh, unreal.ScriptCollisionShapeType.NDOP10_Z)


def build_mesh(recipe):
    """Build ``recipe``'s mesh unless the one on disk already carries its
    stamp. Returns the mesh."""
    eas = _eas()
    source = _must_load(recipe.source_path)
    if eas.does_asset_exist(recipe.path):
        mesh = _must_load(recipe.path)
        if eas.get_metadata_tag(mesh, RECIPE_TAG) == recipe.stamp:
            return mesh
    else:
        mesh = eas.duplicate_asset(recipe.source_path, recipe.path)
        if not mesh:
            raise RuntimeError(f"could not duplicate {recipe.source_path} "
                               f"to {recipe.path}")

    _log(f"building {recipe.name} from {source.get_name()}")
    dm = _source_geometry(source)
    x, y, z = recipe.trunk_base_cm
    if x or y or z:
        unreal.GeometryScript_MeshTransforms.translate_mesh(
            dm, unreal.Vector(-x, -y, -z))
    dm = _cut_sections(dm, recipe.cuts)
    _write_geometry(dm, mesh, _nanite_settings(recipe))
    for slot, path in enumerate(recipe.material_paths):
        mesh.set_material(slot, _must_load(path))
    _refit_collision(mesh)
    eas.set_metadata_tag(mesh, RECIPE_TAG, recipe.stamp)
    eas.save_loaded_asset(mesh, only_if_is_dirty=False)
    return mesh


def _source_triangles(mesh):
    """The full-detail count. get_num_triangles() counts the fallback."""
    return mesh.get_static_mesh_description(0).get_triangle_count()


def fallback_triangles_by_slot(mesh):
    """The non-Nanite fallback's triangles per material slot. It is also the
    mesh the trees' complex collision is cooked from."""
    lod = unreal.GeometryScriptMeshReadLOD()
    lod.set_editor_property("lod_type", unreal.GeometryScriptLODType.RENDER_DATA)
    dm, outcome = GS_ASSET.copy_mesh_from_static_mesh(
        mesh, unreal.DynamicMesh(), unreal.GeometryScriptCopyMeshFromAssetOptions(), lod)
    if outcome != SUCCESS:
        return {}
    _, parts, slots = GS_SPLIT.split_mesh_by_material_i_ds(dm, None)
    return dict(zip(list(slots), [part.get_triangle_count() for part in parts]))


def ensure_tree_assets():
    """Build every derived tree mesh. Returns the meshes by recipe name."""
    built = {}
    for recipe in TREE_MESH_RECIPES:
        mesh = build_mesh(recipe)
        built[recipe.name] = mesh
        _log(f"{recipe.name}: {_source_triangles(mesh)} tris, "
             f"{mesh.get_bounds().box_extent.z * 2:.0f} cm tall, "
             f"fallback {fallback_triangles_by_slot(mesh)}")
    return built


def _dirty_packages():
    return {p.get_name() for p in
            unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}


def verify_tree_assets(check):
    """``check(name, ok, detail)`` is the verify script's harness."""
    eas = _eas()
    dirty = _dirty_packages()
    for recipe in TREE_MESH_RECIPES:
        mesh = eas.load_asset(recipe.path)
        check(f"{recipe.name} Exists", bool(mesh))
        source = eas.load_asset(recipe.source_path)
        check(f"{recipe.name} Scan Still There", bool(source), recipe.source_path)
        # Nothing here may leave a scan modified in memory: the editor would
        # offer to save it over the original.
        check(f"{recipe.name} Scan Left Unmodified",
              recipe.source_path not in dirty, recipe.source_path)
        if not (mesh and source):
            continue
        check(f"{recipe.name} Built From The Current Recipe",
              eas.get_metadata_tag(mesh, RECIPE_TAG) == recipe.stamp,
              str(eas.get_metadata_tag(mesh, RECIPE_TAG)))
        check(f"{recipe.name} Nanite",
              mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))
        origin = mesh.get_bounds().origin
        check(f"{recipe.name} Pivot Under The Trunk",
              max(abs(origin.x), abs(origin.y)) <= PIVOT_TOLERANCE_CM,
              f"(bounds centre {origin.x:.0f}, {origin.y:.0f} cm)")
        got = _source_triangles(mesh)
        check(f"{recipe.name} Within Its Triangle Budget",
              not recipe.triangle_budget or got <= recipe.triangle_budget,
              f"({got} of {recipe.triangle_budget})")
        slots = [m.get_editor_property("material_interface")
                 for m in mesh.get_editor_property("static_materials")]
        wanted = [eas.load_asset(p) for p in recipe.material_paths]
        check(f"{recipe.name} Materials", slots == wanted,
              str([m.get_name() if m else None for m in slots]))


if __name__ == "__main__":
    ensure_tree_assets()
