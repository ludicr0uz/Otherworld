"""BP_Matches: a box of matches, the fifth thing the player starts with.

Matches ARE a BP_WeaponItem, for the reason the axe and the wood are: the
bag, Q, G, E, the throw, the profile and the HUD strip are keyed on that
class. The item is flagged `Lights`, which the fire key's gate branches on
(weapon_component/light.py): a strike with wood in the bag lights a campfire.
It is neither Melee nor Consumable, and a strike spends the wood, never the
matches.

THE MODEL
---------
SM_Matchbox (CC0, Quaternius's Survival Pack, imported by
asset_pipeline/import_quaternius.py) stands on its end: 54 units wide (X), 16
thick (Y) and 109 tall with the matches standing out of the open box. The
pack is at no one size (weapon_models.py), so it carries MATCHES_SCALE to a
box 4 cm wide and 9 cm tall with its matches. It is held in A_HoldItem, as
food is, upright in the fist: the box's middle is the item's origin.
"""

import unreal

from combat.chop_tuning import CHOPS_VAR
from combat.graph import (
    BEL, _apply_defaults, _create_blueprint, _log, _must_load, _rot,
)
from combat.grip import _grip_location, _grip_rotation
from combat.light_tuning import LIGHTS_VAR
from combat.paths import CUBE, HOLD_ITEM_ANIM_PATH, MAT_METAL, MATCHES_BP_PATH
from combat.tuning import COMBAT
from combat.weapon_items import build_model
from combat.weapon_specs import _weapon_icon

MATCHES_MESH = "/Game/Sourced/Quaternius/Survival/SM_Matchbox"
MATCHES_DISPLAY = "Matches"
MATCHES_COLOUR = (0.90, 0.72, 0.22)
MATCHES_SCALE = 0.08

# The middle of the mesh's bounds, in its own units, and the scaled box (cm):
# across, through and up.
MESH_CENTRE = (0.0, -2.17, 24.56)
BOX_CM = (4.3, 1.3, 8.7)


def matches_model():
    """The model, upright, placed so the box's middle is the item's origin."""
    c = tuple(-m * MATCHES_SCALE for m in MESH_CENTRE)
    return (("Model", MATCHES_MESH, c, _rot(), (MATCHES_SCALE,) * 3),)


def matches_outline():
    """Grip: the box, in the item's frame, the form the grip solve reads
    (weapon_models.py says why an outline). Never built."""
    return (("Grip", CUBE, (0.0, 0.0, 0.0), _rot(),
             tuple(s / 100.0 for s in BOX_CM), MAT_METAL),)


def build_matches(item_bp):
    """BP_Matches: the model on Body, and the base class's defaults for it."""
    bp = _create_blueprint(MATCHES_BP_PATH, BEL.generated_class(item_bp))
    build_model(bp, matches_model())
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{MATCHES_BP_PATH} failed to compile")
    aim = HOLD_ITEM_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    _apply_defaults(bp, {
        "DisplayName": MATCHES_DISPLAY,
        LIGHTS_VAR: True,
        "Melee": False,
        "Consumable": False,
        CHOPS_VAR: False,
        "Dropped": False,
        # Nothing to fire: the Lights branch takes the fire key before the
        # guns' gate is reached.
        "UsesAmmo": False,
        "Automatic": False,
        "Damage": 0.0,
        "PelletCount": 0,
        "MagazineSize": 0,
        "Loaded": 0,
        "Reserve": 0,
        "InfiniteReserve": False,
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(0.0, 0.0, 0.0),
        "GripLocation": unreal.Vector(*_grip_location(aim, grip_rot, matches_outline())),
        "GripRotation": grip_rot,
        "SlotColor": unreal.LinearColor(*MATCHES_COLOUR, 1.0),
        # Not 1.0, for the knife's reason: right-click still aims.
        "AdsZoom": float(COMBAT.ads_zoom_irons),
        "Scoped": False,
        "RecoilPitch": 0.0,
        "ShotVolume": 0.0,
        "TwoHanded": False,
        "Icon": _weapon_icon(MATCHES_DISPLAY),
        "AimPose": _must_load(aim),
    })
    _log(f"built {MATCHES_BP_PATH} ({MATCHES_MESH.rsplit('/', 1)[-1]} at {MATCHES_SCALE}, "
         f"a {BOX_CM[2]:.0f} cm box of matches)")
    return bp
