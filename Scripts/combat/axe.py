"""BP_Axe: Quaternius's Survival Pack axe as a melee item, the fourth thing the
player starts with.

An axe IS a BP_WeaponItem flagged `Melee`, for the reasons the knife is one
(knife.py): the bag, Q, G, E and the HUD strip are keyed on that class, and
the fire key's gate branches on `Melee` before anything gun-shaped runs. So
with the axe in hand the fire key swings it through the knife's own stage
(weapon_component/knife.py): the same clip, cooldown, reach and damage. It has
no numbers of its own yet; an axe that hits harder, or bites a tree, needs its
own Strike there.

THE MODEL AND HOW IT SITS IN THE HAND
-------------------------------------
SM_Axe (CC0, imported by asset_pipeline/import_quaternius.py) stands on its
end, head up, 326 units tall with the bit towards -X: the pack is at no one
size (weapon_models.py), so it carries AXE_SCALE to a 65 cm camp axe. Every
number below is measured off the mesh's vertices and given on the scaled mesh,
in cm: the haft from z -16 (its knob) to 23, the straight of it between the
rings at z -4 and 6.5, the head z 25.7..49.2 from the bit at x -17.5 to the
poll at x 7.8.

It is held as the knife is, in A_HoldKnife, whose fist is the pistol pose's:
the haft runs up through the fist, the model is turned round so the bit leads
and tipped TILT_DEG forward. `Grip` in the outline is the stretch of haft
above the knob, so grip._grip_location seats it in the fist exactly as it
seats the knife's handle.
"""

import unreal

from combat.graph import (
    BEL, _apply_defaults, _create_blueprint, _log, _must_load, _rot,
)
from combat.grip import _grip_location, _grip_rotation, _rotate_vector
from combat.knife import _placed
from combat.paths import AXE_BP_PATH, CUBE, HOLD_KNIFE_ANIM_PATH, MAT_METAL
from combat.tuning import COMBAT
from combat.weapon_items import build_model
from combat.weapon_specs import _weapon_icon

# asset_pipeline/import_quaternius.py imports every Survival Pack FBX here.
AXE_MESH = "/Game/Sourced/Quaternius/Survival/SM_Axe"
AXE_DISPLAY = "Axe"
AXE_COLOUR = (0.62, 0.42, 0.26)
AXE_SCALE = 0.2

# On the scaled mesh, in its own frame (cm): the stretch of haft the fist
# closes on, and the head from bit to poll.
HANDLE_CENTRE = (0.2, 0.0, 2.0)
HANDLE_SIZE = (3.3, 2.6, 12.0)
HEAD_CENTRE = (-4.8, 0.0, 37.5)
HEAD_SIZE = (25.2, 3.6, 23.4)
TILT_DEG = 30.0


def head_rotation():
    """The model's rotation: its +Z (the head) up and tipped TILT_DEG towards
    +X, its -X (the bit) leading. Found by testing, as knife.blade_rotation
    is, not argued from rotator handedness."""
    for pitch in (-TILT_DEG, TILT_DEG):
        r = _rot(pitch=pitch, yaw=180.0)
        up = _rotate_vector(r, unreal.Vector(0.0, 0.0, 1.0))
        bit = _rotate_vector(r, unreal.Vector(-1.0, 0.0, 0.0))
        if up.x > 0.1 and up.z > 0.8 and bit.x > 0.8:
            return r
    raise RuntimeError("no rotation puts the axe's head up and its bit forward")


def axe_model():
    """The model, placed so the gripped haft's centre is the weapon's origin."""
    rot = head_rotation()
    c = _rotate_vector(rot, unreal.Vector(*HANDLE_CENTRE))
    return (("Model", AXE_MESH, (-c.x, -c.y, -c.z), rot, (AXE_SCALE,) * 3),)


def axe_outline():
    """Grip and Head as boxes in the weapon's frame, the form the grip solve
    reads (weapon_models.py says why an outline). Never built."""
    (_n, _m, loc, rot, _s), = axe_model()
    return tuple((name, CUBE, _placed(centre, rot, loc), rot,
                  tuple(s / 100.0 for s in size), MAT_METAL)
                 for name, centre, size in (("Grip", HANDLE_CENTRE, HANDLE_SIZE),
                                            ("Head", HEAD_CENTRE, HEAD_SIZE)))


def build_axe(item_bp):
    """BP_Axe: the model on Body, and the base class's defaults for an axe."""
    bp = _create_blueprint(AXE_BP_PATH, BEL.generated_class(item_bp))
    build_model(bp, axe_model())
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{AXE_BP_PATH} failed to compile")
    aim = HOLD_KNIFE_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    _apply_defaults(bp, {
        "DisplayName": AXE_DISPLAY,
        "Melee": True,
        "Consumable": False,
        "Dropped": False,
        "UsesAmmo": False,
        "Automatic": False,
        # For the record, as on the knife: the blow is the knife's Strike and
        # uses COMBAT.knife_*, whichever Melee item is in hand.
        "Damage": float(COMBAT.knife_damage),
        "PelletCount": 0,
        "WeaponRange": float(COMBAT.knife_reach_cm),
        "MagazineSize": 0,
        "Loaded": 0,
        "Reserve": 0,
        "InfiniteReserve": False,
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(0.0, 0.0, 0.0),
        "GripLocation": unreal.Vector(*_grip_location(aim, grip_rot, axe_outline())),
        "GripRotation": grip_rot,
        "SlotColor": unreal.LinearColor(*AXE_COLOUR, 1.0),
        # Not 1.0, for the knife's reason: right-click still aims.
        "AdsZoom": float(COMBAT.ads_zoom_irons),
        "Scoped": False,
        "RecoilPitch": 0.0,
        "ShotVolume": 0.0,
        "TwoHanded": False,
        "Icon": _weapon_icon(AXE_DISPLAY),
        "AimPose": _must_load(aim),
    })
    _log(f"built {AXE_BP_PATH} ({AXE_MESH.rsplit('/', 1)[-1]} at {AXE_SCALE}, "
         f"swung as the knife is)")
    return bp
