"""The items that have an inventory icon, and how each is photographed.

One row per item: its DisplayName (which names its texture), its Blueprint
(the model is whatever that Blueprint wears, so an item given a new model gets
a new icon from the same row), the view the camera takes and how much of the
slot's width it fills.

No `unreal` and no Pillow: the capture (in the editor), the compose step
(outside it) and the builders that point an item at its texture all import it.
"""

from dataclasses import dataclass

WEAPON_DIR = "/Game/Weapons"
SURVIVAL_DIR = "/Game/Survival"
UI_ART_DIR = "/Game/UI/Art"

# The texture, and the canvas the HUD's slot (78 x 35) and the loot window's
# row (100 x 50) both scale: 2:1.
ICON_W, ICON_H = 128, 64

# A render carries its own colours, so the HUD's tint (the item's SlotColor)
# is white on every item. The white silhouettes this replaced were told apart
# by that tint alone.
ICON_TINT = (1.0, 1.0, 1.0)


def icon_name(display):
    """One texture per item, named after its DisplayName."""
    return f"T_UI_Icon_{display}"


@dataclass(frozen=True)
class Item:
    display: str        # the item's DisplayName
    blueprint: str      # its Blueprint: the model photographed is the one it wears
    # Where the camera stands, in the item's own frame. yaw 90 is on its +Y
    # side looking back at it, which puts the item's +X (a gun's muzzle) on the
    # right of the picture. pitch looks down on it; roll turns the picture
    # clockwise, for a model whose long axis is not the one the slot wants.
    yaw: float = 90.0
    pitch: float = 0.0
    roll: float = 0.0
    # Its share of the slot's width, against the longest (the rifle). A table
    # rather than the models' true sizes: a pistol drawn at its real fifth of
    # a rifle is a dot in a 78-pixel slot.
    length: float = 1.0


ITEMS = (
    Item("Pistol", f"{WEAPON_DIR}/BP_Pistol", length=0.55),
    Item("Shotgun", f"{WEAPON_DIR}/BP_Shotgun", length=0.96),
    Item("SMG", f"{WEAPON_DIR}/BP_SMG", length=0.72),
    Item("Rifle", f"{WEAPON_DIR}/BP_AssaultRifle", length=1.00),
    Item("Sniper", f"{WEAPON_DIR}/BP_SniperRifle", length=1.00),
    Item("Knife", f"{WEAPON_DIR}/BP_Knife", roll=-65.0, length=0.50),
    Item("Axe", f"{WEAPON_DIR}/BP_Axe", roll=-60.0, length=0.70),
    Item("Wood", f"{WEAPON_DIR}/BP_Wood", pitch=25.0, roll=90.0, length=0.60),
    Item("Matches", f"{WEAPON_DIR}/BP_Matches", length=0.30),
    Item("Stick", f"{WEAPON_DIR}/BP_Stick", roll=-60.0, length=0.60),
    Item("Mushroom", f"{SURVIVAL_DIR}/BP_Mushroom", length=0.40),
    Item("Canteen", f"{SURVIVAL_DIR}/BP_WaterCanteen", length=0.40),
)

DISPLAYS = tuple(i.display for i in ITEMS)
