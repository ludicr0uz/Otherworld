"""The dark, ground-filling grass: its colours, the ground's under it, how wide
a clump is planted, how many to the square metre, and which levels have which.
Pure Python (no ``unreal``).

The library clump (undergrowth_meshes.py) with the pack's material is a light
green tuft 54 cm across on pale ground: about a sixth of the ground covered,
and nothing of a spooky forest. Three things change that, at the same count:

    colour   an instance of the pack's material, ours, set dark and dull
    ground   the terrain's material brought to the grass's hue, so a gap
             between clumps does not read as bare ground
    width    each clump planted 1.8x wider at the same height

``forest_import/grass_look.py`` builds the instance and patches the ground
material from these numbers; nothing is written to a pack asset.

The colour and the width are per level, each by its own list
(``DARK_GRASS_LEVELS``, ``WIDE_GRASS_LEVELS``): a level in neither plants
``DEFAULT_GRASS_SPECS`` as before. The ground material is shared by every
level, so its colour is not. The count is per level too (``density_for``): a
level held in ``HELD_DENSITY_PER_SQM`` is regenerated at the density it was
planted at, not at today's default.

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

from .grass_placement import DEFAULT_DENSITY_PER_SQM, DEFAULT_GRASS_SPECS
from .undergrowth_meshes import GRASS_02_09

# The levels whose grass draws the dark instance.
DARK_GRASS_LEVELS = ("Lvl_Forest_200m", "Lvl_Forest_1000m")
# The levels whose clumps are planted wide. The 1 km map has the colour only:
# its million clumps keep their places and their narrow width.
WIDE_GRASS_LEVELS = ("Lvl_Forest_200m",)
# Clumps per m2 a level is held at when the default moves on without it. The
# 1 km map stays at 1.1 (1.0 M clumps, a 185 MB .umap): at the default's 2.2
# it would be about 2 million.
HELD_DENSITY_PER_SQM = {"Lvl_Forest_1000m": 1.1}

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


def has_wide_grass(level_name):
    return level_name in WIDE_GRASS_LEVELS


def density_for(level_name):
    """Clumps per m2 ``level_name`` is generated at unless told otherwise."""
    return HELD_DENSITY_PER_SQM.get(level_name, DEFAULT_DENSITY_PER_SQM)


def material_object_path():
    """The instance as a spec names it: ``/Game/Dir/Name.Name``."""
    return f"{GRASS_MATERIAL}.{GRASS_MATERIAL.rsplit('/', 1)[1]}"


def grass_specs_for(level_name):
    """The grass specs ``level_name`` plants: the default ones, drawn with the
    dark instance on a dark grass level and wider on a wide grass level."""
    changes = {}
    if has_dark_grass(level_name):
        changes["material_paths"] = [material_object_path()]
    if has_wide_grass(level_name):
        changes["width_jitter"] = WIDE_WIDTH_JITTER
    if not changes:
        return list(DEFAULT_GRASS_SPECS)
    return [replace(spec, **changes) for spec in DEFAULT_GRASS_SPECS]
