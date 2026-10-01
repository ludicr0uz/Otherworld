"""M_DayNightSky: flags, parameters and a shader that compiled."""

import unreal

from combat.verify.common import check, load
from world.paths import SKY_MATERIAL_PATH, STARS_TEXTURE_PATH
from world.sky_material import EXPRESSION_COUNT, SCALAR_PARAMS, STARS_PARAM, VECTOR_PARAMS

MEL = unreal.MaterialEditingLibrary


def run():
    mat = load(SKY_MATERIAL_PATH)
    check("M_DayNightSky exists", mat is not None, SKY_MATERIAL_PATH)
    if mat is None:
        return
    check("M_DayNightSky is unlit, two-sided and a sky",
          mat.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_UNLIT
          and mat.get_editor_property("two_sided") and mat.get_editor_property("is_sky"))
    scalars = {str(n) for n in MEL.get_scalar_parameter_names(mat)}
    vectors = {str(n) for n in MEL.get_vector_parameter_names(mat)}
    want_s = {n for n, _ in SCALAR_PARAMS}
    want_v = {n for n, _ in VECTOR_PARAMS}
    check("M_DayNightSky exposes the scalars the cycle drives", want_s <= scalars,
          f"missing {sorted(want_s - scalars)}")
    check("M_DayNightSky exposes the directions and colours", want_v <= vectors,
          f"missing {sorted(want_v - vectors)}")
    stats = MEL.get_statistics(mat)
    n = stats.get_editor_property("num_pixel_shader_instructions")
    check("M_DayNightSky's shader compiled", n > 0, f"{n} pixel instructions")
    count = MEL.get_num_material_expressions(mat)
    check("M_DayNightSky holds only what the builder authors (nothing left of an "
          "earlier build)", count == EXPRESSION_COUNT, f"{count} expressions")
    tex = MEL.get_material_default_texture_parameter_value(mat, STARS_PARAM)
    check("M_DayNightSky's stars are the star map",
          tex is not None and tex.get_path_name().split(".")[0] == STARS_TEXTURE_PATH,
          str(tex.get_path_name() if tex else None))
