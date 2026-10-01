"""M_DayNightSky: the sky dome's material, the whole sky in one Custom node.

Why not the SkyAtmosphere for the day and the starfield for the night: an
opaque dome either covers the atmosphere or it does not, so a hand-over
between them pops at dusk. One material that blends a day gradient into the
night colour, adds a sunset glow, the sun's and the moon's discs and the stars,
fades smoothly, and -- being unlit and IsSky, like M_NightSky_Starfield -- is
what the SkyLight's real-time capture turns into the level's ambient light, so
the fill in every shadow follows the sky without a second mechanism.

BP_DayNightCycle drives six parameters every frame through a dynamic
instance: DayAmount, StarBrightness, SunDirection and MoonDirection (both
pointing from the viewer to the body), and SunDiscBrightness and
MoonDiscBrightness (the discs' multipliers, 1 unless tuned). The colours are parameters with their
defaults from world_config, so they can be tuned on an instance.
"""

import unreal

from combat.graph import _log, _must_load
from world import world_config as cfg
from world.paths import SKY_MATERIAL_PATH, STARS_TEXTURE_PATH

MEL = unreal.MaterialEditingLibrary

# (parameter name, default) -- scalars and vectors the Custom node reads.
SCALAR_PARAMS = (("DayAmount", 1.0), ("StarBrightness", 0.0),
                 ("SunDiscBrightness", 1.0), ("MoonDiscBrightness", 1.0))
VECTOR_PARAMS = (
    ("SunDirection", [0.0, 0.0, 1.0, 0.0]),
    ("MoonDirection", [0.0, 0.0, -1.0, 0.0]),
    ("DayZenith", cfg.DAY_ZENITH_COLOR),
    ("DayHorizon", cfg.DAY_HORIZON_COLOR),
    ("NightSky", cfg.NIGHT_SKY_COLOR),
    ("SunsetColor", cfg.SUNSET_COLOR),
    ("SunDiscColor", cfg.SUN_DISC_COLOR),
    ("MoonDiscColor", cfg.MOON_DISC_COLOR),
)

# V is the camera vector (pixel -> camera), so the view ray is -V. The discs
# are ~1.3 degrees (sun) and ~1.6 (moon) across: bigger than life, which reads
# better on a screen. Each body fades out as it drops through the horizon.
SKY_HLSL = """
float3 v = -normalize(V);
float up = saturate(v.z);
float3 s = normalize(SunDirection);
float3 m = normalize(MoonDirection);
float sd = dot(v, s);
float md = dot(v, m);
float sunUp = saturate(s.z * 8.0 + 0.5);
float moonUp = saturate(m.z * 8.0 + 0.5);
float3 sky = lerp(NightSky, lerp(DayHorizon, DayZenith, sqrt(up)), DayAmount);
float glow = pow(saturate(sd), 6.0) * saturate(1.0 - abs(s.z) * 4.0) * (1.0 - up);
sky += SunsetColor * glow * sunUp;
sky += SunDiscColor * SunDiscBrightness * smoothstep(0.99970, 0.99980, sd) * sunUp;
sky += MoonDiscColor * MoonDiscBrightness * smoothstep(0.99955, 0.99965, md) * moonUp;
sky += Stars * StarBrightness * saturate(v.z * 4.0 + 0.2);
return sky;
"""
CUSTOM_INPUTS = (["V", "Stars"] + [n for n, _ in SCALAR_PARAMS]
                 + [n for n, _ in VECTOR_PARAMS])


def _linear(c):
    return unreal.LinearColor(c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)


def _material():
    """Load M_DayNightSky emptied of expressions, or create it."""
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    if eas.does_asset_exist(SKY_MATERIAL_PATH):
        mat = eas.load_asset(SKY_MATERIAL_PATH)
        MEL.delete_all_material_expressions(mat)
        return mat
    pkg, name = SKY_MATERIAL_PATH.rsplit("/", 1)
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, pkg, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        raise RuntimeError(f"could not create {SKY_MATERIAL_PATH}")
    return mat


def _expr(mat, cls, x, y):
    e = MEL.create_material_expression(mat, cls, x, y)
    if not e:
        raise RuntimeError(f"could not create {cls.__name__}")
    return e


def _wire(src, src_out, dst, dst_in):
    if not MEL.connect_material_expressions(src, src_out, dst, dst_in):
        raise RuntimeError(f"could not connect into {dst_in!r}")


def build_sky_material():
    """Author M_DayNightSky from scratch (every run), compile and save it."""
    mat = _material()
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("is_sky", True)

    custom = _expr(mat, unreal.MaterialExpressionCustom, -300, 0)
    custom.set_editor_property("code", SKY_HLSL)
    custom.set_editor_property("description", "DayNightSky")
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs = []
    for name in CUSTOM_INPUTS:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)

    cam = _expr(mat, unreal.MaterialExpressionCameraVectorWS, -800, -300)
    _wire(cam, "", custom, "V")

    coord = _expr(mat, unreal.MaterialExpressionTextureCoordinate, -1100, -150)
    coord.set_editor_property("u_tiling", float(cfg.STAR_TILING[0]))
    coord.set_editor_property("v_tiling", float(cfg.STAR_TILING[1]))
    stars = _expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, -800, -150)
    stars.set_editor_property("parameter_name", "StarsTexture")
    stars.set_editor_property("texture", _must_load(STARS_TEXTURE_PATH))
    _wire(coord, "", stars, "UVs")
    _wire(stars, "RGB", custom, "Stars")

    y = 100
    for name, default in SCALAR_PARAMS:
        p = _expr(mat, unreal.MaterialExpressionScalarParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", float(default))
        _wire(p, "", custom, name)
        y += 120
    for name, default in VECTOR_PARAMS:
        p = _expr(mat, unreal.MaterialExpressionVectorParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", _linear(default))
        _wire(p, "", custom, name)
        y += 160

    if not MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError("could not wire the sky into Emissive Color")
    MEL.recompile_material(mat)
    unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(mat)
    _log(f"{SKY_MATERIAL_PATH}: {len(CUSTOM_INPUTS)} inputs into one Custom node")
    return mat
