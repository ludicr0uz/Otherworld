"""The eight garments as data: where each is built, its name, the slot it is
worn in, and the primitive model it lies on the ground as. Adding a garment
is a row in GARMENTS. No `unreal`: the verifier and the placement read it too.
Three also name the mesh they are drawn as, worn (`worn`): the MetaHuman's
hoodie, jeans and running shoes, each on the body component it fills.

The models are stand-ins for a pick-up to be seen and taken, not clothing
drawn on the player (that is `worn`, drawn by
combat/weapon_component/wear_draw.py). A garment with a `worn` mesh lies on
the ground as that mesh instead (`lay`: how it is turned to lie flat), and
its parts are built by nothing: they only say where the fist holds it, as a
model gun's outline does (clothing/ground_model.py). The part frame is the
items' (combat/weapon_specs.py): the origin sits in the fist and +Z is up, so
a garment lies on the ground at its origin and is carried by its first part.
No part may be called Body: that is the inherited root the parts hang off.
"""

from dataclasses import dataclass

from combat.paths import CUBE, CYLINDER
from asset_pipeline.metahuman_paths import CLOTHING
from combat.wear_tuning import WEAR_SLOTS

CLOTHING_DIR = "/Game/Clothing"
MAT_DIR = f"{CLOTHING_DIR}/Materials"


@dataclass(frozen=True)
class Garment:
    display: str        # DisplayName: the bag's slot, the I panel, the icon
    asset: str          # the Blueprint's name under CLOTHING_DIR
    slot: str           # one of WEAR_SLOTS
    colour: tuple       # its flat material's base colour
    parts: tuple        # (name, mesh, location, rotation (p, y, r), scale, material key)
    worn: tuple = None  # (the body component it fills, the skeletal mesh), or None
    lay: tuple = None   # with `worn`: the mesh's rotation (p, y, r) lying on the ground

    @property
    def path(self):
        return f"{CLOTHING_DIR}/{self.asset}"

    @property
    def class_path(self):
        return f"{self.path}.{self.asset}_C"

    @property
    def slot_index(self):
        return WEAR_SLOTS.index(self.slot)

    @property
    def material(self):
        return f"{MAT_DIR}/M_Cloth_{self.asset[3:]}"


def _worn(part):
    """The MetaHuman's garment that fills `part` (metahuman_paths.CLOTHING)."""
    return (part, CLOTHING[part])


_FLAT = (0.0, 0.0, 0.0)
# A MetaHuman's garment stands as its wearer does: +X across, +Y in front, +Z
# up. On its back, the front up, with the collar away along the item's -X
# (the jeans) or along the row, +Y (the hoodie: its sleeves are 97 cm across,
# and the test garments lie 55 cm apart); the shoes stand on their soles.
_ON_BACK = (0.0, -90.0, -90.0)
_ON_BACK_ACROSS = (0.0, 180.0, -90.0)
_ON_SOLES = (0.0, 90.0, 0.0)
_LENS = (90.0, 0.0, 0.0)        # a cylinder's axis turned onto +X


def _pair(name, mesh, x, y, z, rot, scale):
    """The same part twice, mirrored across X (gloves, boots, lenses)."""
    return ((f"{name}L", mesh, (x, -y, z), rot, scale, "main"),
            (f"{name}R", mesh, (x, y, z), rot, scale, "main"))


GARMENTS = (
    Garment("Hat", "BP_Hat", "hat", (0.33, 0.22, 0.12), (
        ("Brim", CYLINDER, (0.0, 0.0, 1.0), _FLAT, (0.36, 0.36, 0.02), "main"),
        ("Crown", CYLINDER, (0.0, 0.0, 7.0), _FLAT, (0.22, 0.22, 0.12), "main"))),
    Garment("Glasses", "BP_Glasses", "glasses", (0.05, 0.05, 0.06), (
        *_pair("Lens", CYLINDER, 0.0, 3.5, 2.5, _LENS, (0.05, 0.05, 0.006)),
        ("Bridge", CUBE, (0.0, 0.0, 2.5), _FLAT, (0.006, 0.02, 0.006), "main"),
        *_pair("Arm", CUBE, -6.0, 6.0, 2.5, _FLAT, (0.12, 0.004, 0.006)))),
    Garment("Shirt", "BP_Shirt", "shirt", (0.42, 0.55, 0.70), (
        ("Torso", CUBE, (0.0, 0.0, 2.0), _FLAT, (0.25, 0.30, 0.04), "main"),
        ("Collar", CUBE, (11.0, 0.0, 4.5), _FLAT, (0.04, 0.14, 0.01), "main"))),
    Garment("Jacket", "BP_Jacket", "jacket", (0.20, 0.24, 0.12), (
        ("Coat", CUBE, (0.0, 0.0, 4.0), _FLAT, (0.30, 0.36, 0.08), "main"),
        ("Collar", CUBE, (13.0, 0.0, 8.5), _FLAT, (0.06, 0.20, 0.02), "main")),
        worn=_worn("Torso"), lay=_ON_BACK_ACROSS),
    Garment("Gloves", "BP_Gloves", "gloves", (0.45, 0.33, 0.20), (
        *_pair("Glove", CUBE, 0.0, 5.0, 1.5, _FLAT, (0.18, 0.09, 0.03)),)),
    Garment("Pants", "BP_Pants", "pants", (0.16, 0.24, 0.45), (
        ("Legs", CUBE, (0.0, 0.0, 2.5), _FLAT, (0.35, 0.24, 0.05), "main"),
        ("Belt", CUBE, (16.0, 0.0, 5.5), _FLAT, (0.03, 0.24, 0.01), "main")),
        worn=_worn("Legs"), lay=_ON_BACK),
    Garment("Boots", "BP_Boots", "boots", (0.18, 0.11, 0.06), (
        *_pair("Foot", CUBE, 4.0, 7.0, 4.0, _FLAT, (0.28, 0.10, 0.08)),
        *_pair("Shaft", CYLINDER, -6.0, 7.0, 14.0, _FLAT, (0.11, 0.11, 0.18))),
        worn=_worn("Feet"), lay=_ON_SOLES),
    Garment("Backpack", "BP_Backpack", "backpack", (0.30, 0.34, 0.16), (
        ("Pack", CUBE, (0.0, 0.0, 20.0), _FLAT, (0.16, 0.30, 0.40), "main"),
        ("Pocket", CUBE, (10.0, 0.0, 12.0), _FLAT, (0.05, 0.22, 0.16), "main"),
        ("Strap", CUBE, (-9.0, 0.0, 24.0), _FLAT, (0.02, 0.06, 0.30), "main"))),
)

# A garment has a mesh to lie as exactly when it has one to be worn as.
assert all((g.worn is None) == (g.lay is None) for g in GARMENTS)

# One garment per slot, in the slots' order.
assert tuple(g.slot for g in GARMENTS) == WEAR_SLOTS

