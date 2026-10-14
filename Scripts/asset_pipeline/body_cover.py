"""body_cover -- the skin each garment covers, cut out of the whole body
while that garment is worn, so it never shows through the jeans or the
hoodie as the body moves.  Editor side; the rule and the mask are
body_cover_mask.py's (pure).  Run by build_metahuman_retarget.py, before
the bare body's material, which is re-parented onto what this builds.

    BODY_COVER_MASK  a UV mask of the whole body, a channel per COVER_PARTS
                     part: measured here with GeometryScript (the meshes'
                     LOD 0 in their reference pose, which is one A-pose for
                     the body and the three garments), written as a PNG under
                     Saved/body_cover and imported
    BODY_SKIN_WORN   the sample's M_BodySkin copied (never edited under
                     /Game/MetaHumans), Masked: opacity 1 - saturate(mask .
                     (Torso, Legs, Feet)), each a scalar parameter, 0 by
                     default, so a bare body is whole

Why the skin showed: Taro's body is cut where his clothes are, and the
whole body the player wears (BODY_MESH_WHOLE) is not; the jeans lie up to
3 cm inside its skin in the reference pose, and the hoodie's sleeves and the
shoes follow by a copied pose that bends them otherwise than the skin.
"""

import os

import unreal

from asset_pipeline.body_cover_mask import (
    KEPT_CM, dilate, png_rgb, raster, triangle_bits, vertex_bits,
)
from asset_pipeline.metahuman_paths import (
    BODY_COVER_MASK, BODY_MESH, BODY_MESH_WHOLE, BODY_SKIN_MATERIAL, BODY_SKIN_WORN,
    CLOTHING, COVER_PARTS, SOURCED_DIR,
)
from asset_pipeline.rig_util import _load, _log

EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
GQ = unreal.GeometryScript_MeshQueries
GS = unreal.GeometryScript_MeshSpatial
GL = unreal.GeometryScript_List


def _mesh(path):
    """LOD 0 of a skeletal mesh as a DynamicMesh, in its reference pose."""
    got = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
        _load(path), unreal.DynamicMesh(), unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD())
    return got[0]


def _vectors(vector_list):
    got = GL.convert_vector_list_to_array(vector_list)
    return list(got[1] if isinstance(got, tuple) else got)


def _bvh(mesh):
    return GS.build_bvh_for_mesh(mesh)[1]


def _measure():
    """(kept, triangles, triangle UVs, hits, nearest) of the whole body
    (body_cover_mask.vertex_bits's arguments)."""
    body = _mesh(BODY_MESH_WHOLE)
    pos = _vectors(GQ.get_all_vertex_positions(body, False)[1])
    nrm = _vectors(unreal.GeometryScript_Normals.get_mesh_per_vertex_normals(body)[1])
    if GQ.get_has_vertex_id_gaps(body) or GQ.get_has_triangle_id_gaps(body):
        raise RuntimeError(f"{BODY_MESH_WHOLE} copied with id gaps")
    opts = unreal.GeometryScriptSpatialQueryOptions()

    def dist(a, b):
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5

    taro = _mesh(BODY_MESH)
    taro_bvh = _bvh(taro)
    kept = [dist(p, GS.find_nearest_point_on_mesh(taro, taro_bvh, p, opts)[1].position) < KEPT_CM
            for p in pos]
    hits, nearest = [], []
    for part in COVER_PARTS:
        g = _mesh(CLOTHING[part])
        bvh = _bvh(g)
        rays, near = [], []
        for v, (p, n) in enumerate(zip(pos, nrm)):
            hit = []
            # Not -n: unreal.Vector's negation turns n itself round.
            for d in (n, unreal.Vector(-n.x, -n.y, -n.z)):
                r = GS.find_nearest_ray_intersection_with_mesh(g, bvh, p, d, opts)[1]
                hit.append(r.ray_parameter if r.hit else None)
            rays.append(tuple(hit))
            # Only a vertex Taro's body cuts is ever assigned by distance.
            near.append(0.0 if kept[v] else
                        dist(p, GS.find_nearest_point_on_mesh(g, bvh, p, opts)[1].position))
        hits.append(rays)
        nearest.append(near)
    tris, uvs = [], []
    for t in range(GQ.get_num_triangle_i_ds(body)):
        i = GQ.get_triangle_indices(body, t)[0]
        a, b, c, _ok = GQ.get_triangle_u_vs(body, 0, t)
        tris.append((i.x, i.y, i.z))
        uvs.append(((a.x, a.y), (b.x, b.y), (c.x, c.y)))
    return kept, tris, uvs, hits, nearest


def build_mask():
    """BODY_COVER_MASK, measured and imported. Returns the texture."""
    kept, tris, uvs, hits, nearest = _measure()
    bits = vertex_bits(kept, hits, nearest)
    tri_bits = triangle_bits(tris, bits)
    whole = sum(1 for b in tri_bits if not b)
    for p, part in enumerate(COVER_PARTS):
        _log(f"{part}: covers {sum(1 for b in bits if (b >> p) & 1)} vertices, "
             f"{sum(1 for b in tri_bits if (b >> p) & 1)} triangles")
    _log(f"{whole} triangles kept whatever is worn, as Taro's cut body keeps them")
    folder = os.path.join(unreal.Paths.project_saved_dir(), "body_cover")
    os.makedirs(folder, exist_ok=True)
    name = BODY_COVER_MASK.rsplit("/", 1)[1]
    png = os.path.join(folder, f"{name}.png")
    with open(png, "wb") as f:
        f.write(png_rgb(dilate(raster(uvs, tri_bits))))
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", png)
    task.set_editor_property("destination_path", SOURCED_DIR)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = _load(BODY_COVER_MASK)
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    # No mips: a smaller one would blend a cut island with its neighbours.
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    EAL.save_asset(BODY_COVER_MASK)
    _log(f"{BODY_COVER_MASK}: {png}")
    return tex


def _expr(mat, cls):
    return MEL.create_material_expression(mat, cls, 0, 0)


def build_material(mask, rebuild=False):
    """BODY_SKIN_WORN (module docstring). Kept when it already has the
    parameters, unless ``rebuild``."""
    if EAL.does_asset_exist(BODY_SKIN_WORN):
        mat = _load(BODY_SKIN_WORN)
        if not rebuild and all(p in MEL.get_scalar_parameter_names(mat) for p in COVER_PARTS):
            _log(f"{BODY_SKIN_WORN}: already built, reusing")
            return mat
        if not EAL.delete_asset(BODY_SKIN_WORN):
            raise RuntimeError(f"could not delete {BODY_SKIN_WORN}")
    if not EAL.duplicate_asset(BODY_SKIN_MATERIAL, BODY_SKIN_WORN):
        raise RuntimeError(f"could not duplicate {BODY_SKIN_MATERIAL}")
    mat = _load(BODY_SKIN_WORN)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("opacity_mask_clip_value", 0.5)
    sample = _expr(mat, unreal.MaterialExpressionTextureSample)
    sample.set_editor_property("texture", mask)
    sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    params = []
    for part in COVER_PARTS:
        p = _expr(mat, unreal.MaterialExpressionScalarParameter)
        p.set_editor_property("parameter_name", part)
        p.set_editor_property("default_value", 0.0)
        params.append(p)
    ab = _expr(mat, unreal.MaterialExpressionAppendVector)
    MEL.connect_material_expressions(params[0], "", ab, "A")
    MEL.connect_material_expressions(params[1], "", ab, "B")
    abc = _expr(mat, unreal.MaterialExpressionAppendVector)
    MEL.connect_material_expressions(ab, "", abc, "A")
    MEL.connect_material_expressions(params[2], "", abc, "B")
    dot = _expr(mat, unreal.MaterialExpressionDotProduct)
    MEL.connect_material_expressions(sample, "RGB", dot, "A")
    MEL.connect_material_expressions(abc, "", dot, "B")
    sat = _expr(mat, unreal.MaterialExpressionSaturate)
    MEL.connect_material_expressions(dot, "", sat, "")
    keep = _expr(mat, unreal.MaterialExpressionOneMinus)
    MEL.connect_material_expressions(sat, "", keep, "")
    if not MEL.connect_material_property(keep, "", unreal.MaterialProperty.MP_OPACITY_MASK):
        raise RuntimeError(f"{BODY_SKIN_WORN}: the opacity mask did not connect")
    MEL.layout_material_expressions(mat)
    MEL.recompile_material(mat)
    EAL.save_asset(BODY_SKIN_WORN)
    got = MEL.get_scalar_parameter_names(mat)
    if not all(p in got for p in COVER_PARTS):
        raise RuntimeError(f"{BODY_SKIN_WORN}: parameters {list(got)}")
    _log(f"{BODY_SKIN_WORN}: {BODY_SKIN_MATERIAL}, Masked, cut by "
         f"{BODY_COVER_MASK.rsplit('/', 1)[1]} for {', '.join(COVER_PARTS)}")
    return mat


def build(rebuild=False):
    """The mask and the material. Returns the material."""
    return build_material(build_mask(), rebuild=rebuild)
