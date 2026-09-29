"""The food and the water as data: their primitive parts, materials, colours
and what each restores. Adding a consumable is a row in consumable_specs().

Part frame is the weapons' frame (combat/weapon_specs.py): the origin sits in
the fist and +Z is up, so an item standing on the ground and an item held in
the hand are the same actor with nothing flipped.
"""

from combat.graph import _rot
from combat.paths import CYLINDER, MAT_METAL, SPHERE
from survival.paths import (
    CANTEEN_BP_PATH, MAT_CANTEEN, MAT_MUSHROOM_CAP, MAT_MUSHROOM_STEM,
    MUSHROOM_BP_PATH,
)
from survival.tuning import (
    CANTEEN_HUNGER, CANTEEN_THIRST, MUSHROOM_HUNGER, MUSHROOM_THIRST,
)

# (path, colour, metallic, roughness, emissive). Both items glow faintly, for
# the reason M_Brass does: at night under the canopy a dark object on dark
# ground is never found, and finding them is the whole mechanic. The cap is the
# brighter of the two -- a pale bioluminescent mushroom suits a forest called
# Otherworld better than a realistic one nobody can see.
MATERIALS = (
    (MAT_MUSHROOM_CAP, (0.46, 0.20, 0.09), 0.0, 0.55, (0.16, 0.07, 0.03)),
    (MAT_MUSHROOM_STEM, (0.62, 0.58, 0.48), 0.0, 0.70, (0.05, 0.05, 0.04)),
    (MAT_CANTEEN, (0.10, 0.13, 0.06), 0.25, 0.45, (0.02, 0.03, 0.01)),
)


def _mushroom_parts():
    """A stem and a squashed-sphere cap, 12 cm across -- a big porcini."""
    return (
        ("Stem", CYLINDER, (0.0, 0.0, 4.0), _rot(), (0.04, 0.04, 0.08), MAT_MUSHROOM_STEM),
        ("Cap",  SPHERE,   (0.0, 0.0, 8.5), _rot(), (0.12, 0.12, 0.06), MAT_MUSHROOM_CAP),
    )


def _canteen_parts():
    """A round, flat flask standing on its rim, with a neck and a metal cap.

    The body is a cylinder turned onto its side (axis along Y), which is the
    silhouette that says "canteen" rather than "bottle".
    """
    return (
        ("Flask", CYLINDER, (0.0, 0.0, 9.0),  _rot(roll=90.0), (0.18, 0.18, 0.07), MAT_CANTEEN),
        ("Neck",  CYLINDER, (0.0, 0.0, 19.0), _rot(),          (0.035, 0.035, 0.04), MAT_CANTEEN),
        ("Cap",   CYLINDER, (0.0, 0.0, 21.5), _rot(),          (0.045, 0.045, 0.02), MAT_METAL),
    )


def consumable_specs():
    """Everything that differs between the consumables, in one table."""
    return (
        # grip_part: what the fingers close round (grip._grip_location).
        dict(path=MUSHROOM_BP_PATH, display="Mushroom", parts=_mushroom_parts(),
             grip_part="Stem",
             colour=(0.86, 0.62, 0.40),
             hunger=MUSHROOM_HUNGER, thirst=MUSHROOM_THIRST),
        dict(path=CANTEEN_BP_PATH, display="Canteen", parts=_canteen_parts(),
             grip_part="Neck",
             colour=(0.36, 0.84, 0.78),
             hunger=CANTEEN_HUNGER, thirst=CANTEEN_THIRST),
    )
