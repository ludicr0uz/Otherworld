"""The dark, ground-filling grass: its colours, the ground's under it, how wide
a clump is planted, and which levels have it. Pure Python (no ``unreal``).

The library clump (undergrowth_meshes.py) with the pack's material is a light
green tuft 54 cm across on pale ground: about a sixth of the ground covered,
and nothing of a spooky forest. Three things change that, at the same count:

    colour   an instance of the pack's material, ours, set dark and dull
    ground   the terrain's material brought to the grass's hue, so a gap
             between clumps does not read as bare ground
    width    each clump planted 1.8x wider at the same height

``forest_import/grass_look.py`` builds the instance and patches the ground
material from these numbers; nothing is written to a pack asset.

The colour and the width are per level (``DARK_GRASS_LEVELS``): a level not
named here plants ``DEFAULT_GRASS_SPECS`` as before. The ground material is
shared by every level, so its colour is not.

What the pack's material does with the numbers (MA_Grass, read in the editor):

    base colour  = desaturate(variation(albedo x Brightness) x Tint.rgb,
                              1 - Saturation)
    subsurface   = variation(desaturate(albedo x "Subsurface Strengh",
                                        1 - "Subsurface Saturation"))

``Tint``'s alpha is wired to nothing (the pack ships it 0): only its RGB output
is used, once, in that multiply. The light through a blade is not tinted at
all, so it is brought down by its own two parameters or a backlit clump stays
bright green.
"""

from dataclasses import replace

from .grass_placement import DEFAULT_GRASS_SPECS
from .undergrowth_meshes import GRASS_02_09

# The levels whose grass is the dark, wide one. The 1 km map is not here until
# its pictures have been seen: it keeps the pack material and the narrow clump.
DARK_GRASS_LEVELS = ("Lvl_Forest_200m",)

# ─── The grass's colour ──────────────────────────────────────────────────────

GRASS_MATERIAL = "/Game/Forest/Materials/MI_Grass_02_09_Dark"
GRASS_MATERIAL_PARENT = ("/Game/PN_GrassLibrary/Materials/grassMaterials/"
                         "grassMaterials/grass_02_09_Mat")
# Every /Game package the instance needs: itself and what the mesh already
# brings (its parent is one of the mesh's packages).
GRASS_MATERIAL_PACKAGES = (GRASS_MATERIAL,) + GRASS_02_09.packages

# Olive: red and green near level and blue well under, so the spring green
# turns towards the brown of the ground.
GRASS_TINT = (0.80, 0.72, 0.42)
# A quarter of the albedo: darker than the trees' leaves in daylight, and
# still a shape under the moon. Lower (0.20 was tried) and the auto exposure
# lifts a noon frame until the sky and the leaves burn out.
GRASS_BRIGHTNESS = 0.24
# Dull, not grey: what is left of the green after the tint.
GRASS_SATURATION = 0.55
# A quarter of the pack's. It turns the hue per clump, and on a dull olive
# the pack's 0.02 already shows as teal and maroon clumps among the others.
GRASS_COLOR_VARIATION = 0.005
# The light through a blade is the untinted albedo: cut with the brightness,
# or the sun behind a clump lights it spring green again.
GRASS_SUBSURFACE_STRENGTH = 0.18
# And dulled like the lit side (the pack ships 1.2, greener than the albedo).
GRASS_SUBSURFACE_SATURATION = 0.55

# Parameter name in MA_Grass -> value. "Strengh" is the pack's spelling.
GRASS_SCALARS = {
    "Brightness": GRASS_BRIGHTNESS,
    "Saturation": GRASS_SATURATION,
    "ColorVariation": GRASS_COLOR_VARIATION,
    # The light through a blade turns by its own parameter: held to the same.
    "Subsurface ColorVariation": GRASS_COLOR_VARIATION,
    "Subsurface Strengh": GRASS_SUBSURFACE_STRENGTH,
    "Subsurface Saturation": GRASS_SUBSURFACE_SATURATION,
}

# ─── The ground's colour ─────────────────────────────────────────────────────

GROUND_MATERIAL = "/Game/Forest/Materials/M_Forest_Ground_PBR"
# The names of the two parameters the import adds to the ground material.
GROUND_TINT_PARAM = "GroundTint"
GROUND_SATURATION_PARAM = "GroundSaturation"

# The ground's textures are pale straw. This multiplies them down to the dark
# grass's olive, a shade browner and darker, so the clumps still stand on it.
GROUND_TINT = (0.11, 0.105, 0.068)
# Dull as the grass is, so neither stands out of the other.
GROUND_SATURATION = 0.60

# ─── The clump's width ───────────────────────────────────────────────────────

# 1.8x the default 0.85-1.20 at the same height: about 3.2x the area, so
# roughly 40% of the ground under grass at one clump per square metre.
WIDE_WIDTH_JITTER = (1.55, 2.10)


def has_dark_grass(level_name):
    return level_name in DARK_GRASS_LEVELS


def material_object_path():
    """The instance as a spec names it: ``/Game/Dir/Name.Name``."""
    return f"{GRASS_MATERIAL}.{GRASS_MATERIAL.rsplit('/', 1)[1]}"


def grass_specs_for(level_name):
    """The grass specs ``level_name`` plants: the default ones, or on a dark
    grass level the same specs wider and drawn with the dark instance."""
    if not has_dark_grass(level_name):
        return list(DEFAULT_GRASS_SPECS)
    return [replace(spec, material_paths=[material_object_path()],
                    width_jitter=WIDE_WIDTH_JITTER)
            for spec in DEFAULT_GRASS_SPECS]
