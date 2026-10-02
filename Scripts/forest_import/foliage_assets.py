"""Build the generated grass and bush meshes, and their material, in the editor.

    Scripts/dev/uepy.py Scripts/forest_import/foliage_assets.py   # standalone

The generated import_<Level>.py calls ensure_foliage_assets() before it plants
anything. Geometry is forest_generator/foliage_meshes.py; this file only turns
it into assets under /Game/Forest/Procedural. Everything is rebuilt on every
run -- it is deterministic and takes a second or two -- and meshes are updated
IN PLACE, so cells already planted in an open level keep pointing at them.

M_ProcFoliage
-------------
Opaque, two-sided, Two Sided Foliage shading, no textures:

    BaseColor   = VertexColor.rgb * lerp(TintA, TintB, PerInstanceRandom)
                  * Brightness
    Subsurface  = BaseColor * Translucency     (moonlight through blades)
    AO          = lerp(RootOcclusion, 1, VertexColor.a)
    Roughness, Specular: parameters

    WPO         = wind (forest_import/wind.py): lean and sway x VertexColor.a

Opaque is the point (see foliage_meshes.py): Nanite rasterises it on the
fixed-function path, where the masked scans and the tree leaves need the
programmable one. The wind's world-position offset would put every blade back
on the programmable path, so it is the graphics menu's to switch off per
component (graphics_menu/gfx_tuner_wind.py): with WPO off a cell skips it.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forest_generator.foliage_meshes import (  # noqa: E402
    BUSH_RECIPES, GRASS_RECIPES, MI_BUSH, MI_GRASS, PROC_FOLIAGE_DIR,
    PROC_MATERIAL, build)
from forest_import.wind import (  # noqa: E402
    author_grass_wind, ensure_collection, ensure_wind, verify_wind)

MEL = unreal.MaterialEditingLibrary
MP = unreal.MaterialProperty

# (parameter, grass value, bush value). Tints are multipliers on the baked
# vertex colours; PerInstanceRandom picks a point between A and B per patch,
# so neighbouring patches differ without another mesh.
_VECTORS = (
    ("TintA", (1.00, 1.00, 1.00), (1.00, 1.00, 1.00)),
    ("TintB", (0.80, 1.10, 0.70), (0.75, 0.92, 0.85)),
)
_SCALARS = (
    ("Brightness", 1.0, 1.0),
    ("Translucency", 0.55, 0.35),
    ("RootOcclusion", 0.30, 0.25),
    ("Roughness", 0.80, 0.70),
    ("Specular", 0.25, 0.30),
)


def _log(msg):
    unreal.log_warning(f"[FOLIAGE] {msg}")


def _load_or_create(name, cls, factory):
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    path = f"{PROC_FOLIAGE_DIR}/{name}"
    if eas.does_asset_exist(path):
        return eas.load_asset(path)
    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, PROC_FOLIAGE_DIR, cls, factory)


# ─── Material ────────────────────────────────────────────────────────────────

def _expr(mat, cls, x, y, **props):
    e = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def _scalar(mat, name, value, x, y):
    return _expr(mat, unreal.MaterialExpressionScalarParameter, x, y,
                 parameter_name=name, default_value=value)


def build_material():
    mat = _load_or_create(PROC_MATERIAL.rsplit("/", 1)[1], unreal.Material,
                          unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model",
                            unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    mat.set_editor_property("used_with_nanite", True)

    vc = _expr(mat, unreal.MaterialExpressionVertexColor, -1200, 0)
    pir = _expr(mat, unreal.MaterialExpressionPerInstanceRandom, -1200, 300)
    tint_a = _expr(mat, unreal.MaterialExpressionVectorParameter, -1200, 400,
                   parameter_name="TintA",
                   default_value=unreal.LinearColor(1, 1, 1, 1))
    tint_b = _expr(mat, unreal.MaterialExpressionVectorParameter, -1200, 600,
                   parameter_name="TintB",
                   default_value=unreal.LinearColor(1, 1, 1, 1))
    tint = _expr(mat, unreal.MaterialExpressionLinearInterpolate, -900, 400)
    MEL.connect_material_expressions(tint_a, "", tint, "A")
    MEL.connect_material_expressions(tint_b, "", tint, "B")
    MEL.connect_material_expressions(pir, "", tint, "Alpha")

    tinted = _expr(mat, unreal.MaterialExpressionMultiply, -650, 100)
    MEL.connect_material_expressions(vc, "", tinted, "A")
    MEL.connect_material_expressions(tint, "", tinted, "B")
    base = _expr(mat, unreal.MaterialExpressionMultiply, -420, 100)
    MEL.connect_material_expressions(tinted, "", base, "A")
    MEL.connect_material_expressions(_scalar(mat, "Brightness", 1.0, -650, 260),
                                     "", base, "B")
    MEL.connect_material_property(base, "", MP.MP_BASE_COLOR)

    sss = _expr(mat, unreal.MaterialExpressionMultiply, -200, 300)
    MEL.connect_material_expressions(base, "", sss, "A")
    MEL.connect_material_expressions(_scalar(mat, "Translucency", 0.5, -420, 360),
                                     "", sss, "B")
    MEL.connect_material_property(sss, "", MP.MP_SUBSURFACE_COLOR)

    ao = _expr(mat, unreal.MaterialExpressionLinearInterpolate, -200, 520)
    MEL.connect_material_expressions(_scalar(mat, "RootOcclusion", 0.3, -420, 500),
                                     "", ao, "A")
    ao.set_editor_property("const_b", 1.0)
    MEL.connect_material_expressions(vc, "A", ao, "Alpha")
    MEL.connect_material_property(ao, "", MP.MP_AMBIENT_OCCLUSION)

    MEL.connect_material_property(_scalar(mat, "Roughness", 0.8, -200, 700),
                                  "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(_scalar(mat, "Specular", 0.25, -200, 800),
                                  "", MP.MP_SPECULAR)
    author_grass_wind(mat, ensure_collection(), (vc, "A"))

    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


def build_instance(path, parent, column):
    """column: 1 for grass values, 2 for bush values (see _VECTORS)."""
    mi = _load_or_create(path.rsplit("/", 1)[1], unreal.MaterialInstanceConstant,
                         unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", parent)
    for row in _VECTORS:
        MEL.set_material_instance_vector_parameter_value(
            mi, row[0], unreal.LinearColor(*row[column], 1.0))
    for row in _SCALARS:
        MEL.set_material_instance_scalar_parameter_value(mi, row[0], row[column])
    MEL.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mi


# ─── Meshes ──────────────────────────────────────────────────────────────────

def _dynamic_mesh(buf):
    dm = unreal.DynamicMesh()
    b = unreal.GeometryScriptSimpleMeshBuffers()
    b.vertices = [unreal.Vector(*v) for v in buf.vertices]
    b.normals = [unreal.Vector(*n) for n in buf.normals]
    b.vertex_colors = [unreal.LinearColor(*c) for c in buf.colors]
    b.uv0 = [unreal.Vector2D(*uv) for uv in buf.uvs]
    b.triangles = [unreal.IntVector(*t) for t in buf.triangles]
    unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dm, b, 0)
    return dm


def _nanite_settings(preserve_area):
    ns = unreal.MeshNaniteSettings()
    ns.set_editor_property("enabled", True)
    # Preserve Area: as Nanite drops blades and leaves with distance it widens
    # the ones it keeps, so a far field stays a field instead of thinning to
    # sticks. What it is for, per the engine's own tooltip: foliage.
    if preserve_area:
        ns.set_editor_property("shape_preservation",
                               unreal.NaniteShapePreservation.PRESERVE_AREA)
    return ns


def build_mesh(recipe, material, preserve_area=True):
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    path = f"{PROC_FOLIAGE_DIR}/{recipe.name}"
    dm = _dynamic_mesh(build(recipe))
    ns = _nanite_settings(preserve_area)
    if eas.does_asset_exist(path):
        mesh = eas.load_asset(path)
        opts = unreal.GeometryScriptCopyMeshToAssetOptions()
        opts.set_editor_property("enable_recompute_normals", False)
        opts.set_editor_property("enable_recompute_tangents", True)
        opts.set_editor_property("apply_nanite_settings", True)
        opts.set_editor_property("new_nanite_settings", ns)
        opts.set_editor_property("replace_materials", True)
        opts.set_editor_property("new_materials", [material])
        opts.set_editor_property("new_material_slot_names", ["Foliage"])
        lod = unreal.GeometryScriptMeshWriteLOD()
        _, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
            dm, mesh, opts, lod)
    else:
        opts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        opts.set_editor_property("enable_recompute_normals", False)
        opts.set_editor_property("enable_recompute_tangents", True)
        opts.set_editor_property("enable_collision", False)
        opts.set_editor_property("enable_nanite", True)
        mesh, outcome = (unreal.GeometryScript_NewAssetUtils
                         .create_new_static_mesh_asset_from_mesh(dm, path, opts))
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS or not mesh:
        raise RuntimeError(f"could not build {path}: {outcome}")

    unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(
        mesh, ns, apply_changes=True)
    mesh.set_material(0, material)
    # Walk-through: no simple or complex collision to pay for, or to trip on.
    body = mesh.get_editor_property("body_setup")
    if body:
        body.set_editor_property("collision_trace_flag",
                                 unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).remove_collisions(mesh)
    eas.save_loaded_asset(mesh)
    return mesh


def ensure_foliage_assets():
    """Build the material, its two instances and every mesh. Returns the
    meshes by recipe name. The tree masters' wind goes in first."""
    ensure_wind()
    mat = build_material()
    mi_grass = build_instance(MI_GRASS, mat, 1)
    mi_bush = build_instance(MI_BUSH, mat, 2)
    built = {}
    for recipe in GRASS_RECIPES:
        built[recipe.name] = build_mesh(recipe, mi_grass)
    for recipe in BUSH_RECIPES:
        built[recipe.name] = build_mesh(recipe, mi_bush)
    for name, mesh in built.items():
        _log(f"{name}: {mesh.get_static_mesh_description(0).get_triangle_count()} "
             f"tris, {mesh.get_bounds().box_extent.z * 2:.0f} cm tall")
    return built


def verify_foliage_assets(check):
    """The built assets are what the performance case rests on: Nanite on,
    opaque, no collision, and the wind. ``check`` is the verify script's harness."""
    verify_wind(check)
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    mat = eas.load_asset(PROC_MATERIAL)
    check("M_ProcFoliage Exists", bool(mat))
    if mat:
        check("M_ProcFoliage Opaque",
              mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_OPAQUE)
        check("M_ProcFoliage Two-Sided Foliage",
              mat.get_editor_property("shading_model")
              == unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    for recipe in GRASS_RECIPES + BUSH_RECIPES:
        mesh = eas.load_asset(f"{PROC_FOLIAGE_DIR}/{recipe.name}")
        check(f"{recipe.name} Exists", bool(mesh))
        if not mesh:
            continue
        check(f"{recipe.name} Nanite",
              mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))
        # The source mesh, which is what Nanite draws near the camera.
        # get_num_triangles() would count the non-Nanite fallback instead.
        expected = build(recipe).triangle_count
        got = mesh.get_static_mesh_description(0).get_triangle_count()
        check(f"{recipe.name} Built From The Current Recipe", got == expected,
              f"(expected {expected} triangles, got {got})")
        body = mesh.get_editor_property("body_setup")
        prims = body.get_editor_property("agg_geom") if body else None
        n_prims = (len(prims.get_editor_property("box_elems"))
                   + len(prims.get_editor_property("convex_elems"))
                   + len(prims.get_editor_property("sphyl_elems"))
                   + len(prims.get_editor_property("sphere_elems"))) if prims else 0
        check(f"{recipe.name} No Collision Shapes", n_prims == 0, str(n_prims))


if __name__ == "__main__":
    ensure_foliage_assets()
