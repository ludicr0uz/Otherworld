"""The flat materials weapons, blood and bullet impacts are drawn with.
"""

import unreal

from combat.log import _log
from uebp.graph import _assets, _must_load
from combat.paths import (
    MAT_BLOOD, MAT_BRASS, MAT_IMPACT_CHIP, MAT_IMPACT_DUST, MAT_METAL, MAT_WOOD,
)


# ─── Materials and sounds ────────────────────────────────────────────────────

# Linear base colours. M_Blood is the one worth stating a number for:
# (0.150, 0.014, 0.012) is sRGB #6C2825, a dark desaturated crimson roughly two
# stops under arterial red. Pure (1, 0, 0) -- or the (0.30, 0.005, 0.005) this
# used to be, which is that hue at lower value -- is the single loudest
# "cartoon" cue there is, because nothing in a forest at night is that
# saturated.
BLOOD_BASE_COLOUR = (0.150, 0.014, 0.012)
# Wet, not painted. The specular highlight off a 0.22-rough droplet is what
# actually makes blood readable at night; emissive was the old answer and it is
# the wrong one -- a glowing droplet cannot sit in the scene's lighting, it only
# sits on top of it.
BLOOD_ROUGHNESS = 0.22
# What a bullet knocks off the scenery (bullet_impact.py). The level is a
# forest: what a round hits is soil, bark and rock, so the chips are a dark
# earth brown and the dust the pale grey-tan of the same stuff ground fine.
# Dry and dull, both, which is what tells them from blood at a glance, and lit
# like blood, for blood's reason.
IMPACT_CHIP_COLOUR = (0.060, 0.042, 0.028)
IMPACT_DUST_COLOUR = (0.360, 0.310, 0.240)
IMPACT_ROUGHNESS = 0.95


def build_materials():
    """Flat constant materials, so the parts read as a gun and not as white boxes.

    Material *instances* of BasicShapeMaterial would be cheaper, but that engine
    material exposes no parameters, so there is nothing to instance.
    """
    for path, (colour, metallic, roughness, emissive) in (
            (MAT_METAL, ((0.055, 0.058, 0.065), 1.0, 0.32, None)),
            (MAT_WOOD, ((0.115, 0.062, 0.030), 0.0, 0.62, None)),
            # Deliberately NOT emissive -- see BLOOD_BASE_COLOUR.
            (MAT_BLOOD, (BLOOD_BASE_COLOUR, 0.0, BLOOD_ROUGHNESS, None)),
            (MAT_IMPACT_CHIP, (IMPACT_CHIP_COLOUR, 0.0, IMPACT_ROUGHNESS, None)),
            (MAT_IMPACT_DUST, (IMPACT_DUST_COLOUR, 0.0, IMPACT_ROUGHNESS, None)),
            # Shells on the forest floor, at night, under trees. Emissive
            # because without it a dropped pickup is a black cylinder on black
            # ground and nobody ever finds it -- a gameplay affordance, which
            # is a reason blood does not get to borrow.
            (MAT_BRASS, ((0.52, 0.36, 0.08), 1.0, 0.28, (0.34, 0.22, 0.03)))):
        build_flat_material(path, colour, metallic, roughness, emissive)


def build_flat_material(path, colour, metallic, roughness, emissive=None):
    """One constant-colour material at ``path``, created or re-authored.

    Re-authored in place on every run rather than skipped when the asset is
    already there. The old skip meant a changed recipe never landed: the blood
    colour could be edited here, the builder re-run, and the material on disk
    would still be last month's. delete_all_material_expressions clears the
    graph without deleting the asset, so every reference to it survives.
    """
    eas = _assets()
    mel = unreal.MaterialEditingLibrary
    package_path, name = path.rsplit("/", 1)
    if eas.does_asset_exist(path):
        mat = _must_load(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, package_path, unreal.Material, unreal.MaterialFactoryNew())
    base = mel.create_material_expression(
        mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
    base.set_editor_property("constant", unreal.LinearColor(*colour, 1.0))
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    for value, prop, offset in ((metallic, unreal.MaterialProperty.MP_METALLIC, 160),
                                (roughness, unreal.MaterialProperty.MP_ROUGHNESS, 300)):
        c = mel.create_material_expression(
            mat, unreal.MaterialExpressionConstant, -400, offset)
        c.set_editor_property("r", value)
        mel.connect_material_property(c, "", prop)
    if emissive:
        e = mel.create_material_expression(
            mat, unreal.MaterialExpressionConstant3Vector, -400, 440)
        e.set_editor_property("constant", unreal.LinearColor(*emissive, 1.0))
        mel.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    # delete_all_material_expressions above leaves the previous run's
    # now-unreferenced nodes behind in the asset; this is what actually
    # removes them, and without it every rebuild grows the graph.
    mel.delete_unused_expressions(mat)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    _log(f"built {path}")
    return mat
