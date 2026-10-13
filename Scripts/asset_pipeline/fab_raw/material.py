"""material.py -- one material per texture set, its samplers wired by role.

A material of its own per set, not an instance of a shared parent: a parent
needs a default texture for every role, the engine's defaults are colour
textures, and a mask sampler refuses one, so the parent would never compile
clean. A set's material samples exactly the textures the set has; a role it
lacks is a constant.
"""

import unreal

MEL = unreal.MaterialEditingLibrary
MP = unreal.MaterialProperty
ST = unreal.MaterialSamplerType

# A set with no roughness map is neither a mirror nor chalk.
DEFAULT_ROUGHNESS = 0.6

# role -> (sampler type, the sampler's output, the material input)
WIRING = {
    "basecolor": (ST.SAMPLERTYPE_COLOR, "RGB", MP.MP_BASE_COLOR),
    "normal": (ST.SAMPLERTYPE_NORMAL, "RGB", MP.MP_NORMAL),
    "roughness": (ST.SAMPLERTYPE_MASKS, "R", MP.MP_ROUGHNESS),
    "metallic": (ST.SAMPLERTYPE_MASKS, "R", MP.MP_METALLIC),
    "ao": (ST.SAMPLERTYPE_MASKS, "R", MP.MP_AMBIENT_OCCLUSION),
    "opacity": (ST.SAMPLERTYPE_MASKS, "R", MP.MP_OPACITY_MASK),
}


def build(name, folder, textures):
    """The material ``folder/name`` over ``textures`` ({role: Texture2D}). Returns it."""
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    if mat is None:
        raise RuntimeError(f"could not create {folder}/{name}")
    if "opacity" in textures:
        # Cloth with holes: cut out, and seen from inside.
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        mat.set_editor_property("two_sided", True)
    for row, role in enumerate(r for r in WIRING if r in textures):
        sampler, output, target = WIRING[role]
        node = MEL.create_material_expression(
            mat, unreal.MaterialExpressionTextureSample, -420, row * 260)
        node.set_editor_property("texture", textures[role])
        node.set_editor_property("sampler_type", sampler)
        if not MEL.connect_material_property(node, output, target):
            raise RuntimeError(f"{name}: could not wire the {role} map")
    if "roughness" not in textures:
        node = MEL.create_material_expression(
            mat, unreal.MaterialExpressionConstant, -420, len(textures) * 260)
        node.set_editor_property("r", DEFAULT_ROUGHNESS)
        MEL.connect_material_property(node, "", MP.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    return mat
