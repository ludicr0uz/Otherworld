"""The garments' Blueprints and their flat materials: one BP_<Garment>, a
child of BP_WeaponItem, per row of specs.GARMENTS.

A garment IS a BP_WeaponItem for the reason a mushroom is
(survival/consumables.py): the bag is an array of it, so E picks one up, G
drops it, Q cycles to it and the strip draws it with no new code. It is
Consumable, so the fire key uses it instead of firing it, and its ClothingSlot
(the slot's index in combat.wear_tuning.WEAR_SLOTS) is what makes that use
wearing it (combat/weapon_component/wear.py). Dropped by default, as food is,
so one placed in a level is already a pick-up.
"""

import unreal

from combat.log import _log
from uebp.graph import BEL, _apply_defaults, _create_blueprint, _must_load, _rot
from combat.grip import _grip_location, _grip_rotation
from combat.materials import build_flat_material
from combat.paths import HOLD_ITEM_ANIM_PATH, ITEM_BP_PATH
from combat.tuning import COMBAT
from combat.wear_tuning import CLOTHING_SLOT_VAR
from combat.weapon_items import build_parts
from combat.weapon_specs import _weapon_icon
from item_icons.items import ICON_TINT
from clothing.specs import GARMENTS

# A faint glow, as the forage has: a dark thing on dark ground at night is
# never found (survival/consumable_specs.py).
EMISSIVE_SHARE = 0.15


def parts_of(garment):
    """The garment's parts as build_parts takes them."""
    return tuple((name, mesh, loc, _rot(*rot), scale, garment.material)
                 for name, mesh, loc, rot, scale, _key in garment.parts)


def build_garment(garment, item_bp):
    build_flat_material(garment.material, garment.colour, 0.0, 0.85,
                        tuple(c * EMISSIVE_SHARE for c in garment.colour))
    bp = _create_blueprint(garment.path, BEL.generated_class(item_bp))
    parts = parts_of(garment)
    build_parts(bp, parts)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{garment.path} failed to compile")
    aim = HOLD_ITEM_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    _apply_defaults(bp, {
        "DisplayName": garment.display,
        CLOTHING_SLOT_VAR: garment.slot_index,
        "Consumable": True,
        "Dropped": True,
        "Melee": False,
        "UsesAmmo": False,
        "Automatic": False,
        "Damage": 0.0,
        "PelletCount": 0,
        "MagazineSize": 0,
        "Loaded": 0,
        "Reserve": 0,
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(0.0, 0.0, 0.0),
        "GripLocation": unreal.Vector(*_grip_location(aim, grip_rot, parts,
                                                       parts[0][0])),
        "GripRotation": grip_rot,
        "SlotColor": unreal.LinearColor(*ICON_TINT, 1.0),
        # Not 1.0, for the consumables' reason: the aim divides by AdsZoom - 1.
        "AdsZoom": float(COMBAT.ads_zoom_irons),
        "Scoped": False,
        "RecoilPitch": 0.0,
        "ShotVolume": 0.0,
        "Icon": _weapon_icon(garment.display),
        "AimPose": _must_load(aim),
    })
    _log(f"built {garment.path} ({garment.display}, worn as the {garment.slot})")
    return bp


def build_garments():
    """Every row of GARMENTS. Returns {display: Blueprint}."""
    item_bp = _must_load(ITEM_BP_PATH)
    return {g.display: build_garment(g, item_bp) for g in GARMENTS}
