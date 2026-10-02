"""BP_Knife: the FPS Weapon Bundle's M9 knife as a melee item, one of the
three the player starts with.

A knife IS a BP_WeaponItem, for the reason a mushroom is one
(survival/consumables.py): the inventory, Q, G, E and the HUD strip are all
keyed on that class. It is not a row in weapon_specs._weapon_specs(), because
every column there is about a gun -- muzzle, pellets, magazine, accuracy -- and
every check that iterates the table measures a gun. What marks it is `Melee`:
the fire key's gate branches on it before anything gun-shaped runs, and the
slash is weapon_component/knife.py.

THE MODEL AND HOW IT SITS IN THE HAND
-------------------------------------
SK_M9_Knife_X stands on its end in its own frame: the handle z -5.2..7.2
(2.7 cm round, centred on z 1.0), the guard at z -5.4, the blade down to
z -24.3 -- measured off the mesh's vertices. It is held in A_HoldKnife, a
fighting stance (hold_pose.py) whose fist is the pistol pose's, and a pistol's
grip runs up and down through the fist, so the knife's handle does too: the
model is turned over, blade up, and tipped 30 deg forward, a hammer grip with
the edge leading. `Grip` in the outline is the handle, so grip._grip_location
seats it in the fist exactly as it seats a pistol's grip.
"""

import unreal

from combat.graph import (
    BEL, _apply_defaults, _create_blueprint, _log, _must_load, _rot,
)
from combat.grip import _grip_location, _grip_rotation, _rotate_vector
from combat.heat import build_heated_model, build_hot_instance
from combat.heat_tuning import COOL_VAR, HEAT_MATERIAL_VAR, HEATS_VAR, HOT_VAR
from combat.paths import (
    CUBE, HOLD_KNIFE_ANIM_PATH, KNIFE_BP_PATH, MAT_HOT_KNIFE, MAT_METAL,
)
from combat.tuning import COMBAT
from combat.weapon_models import FAB_WEAPONS
from combat.weapon_specs import _weapon_icon
from item_icons.items import ICON_TINT

KNIFE_MESH = f"{FAB_WEAPONS}/M9_Knife/SK_M9_Knife_X"
KNIFE_DISPLAY = "Knife"

# Measured in the mesh's frame (cm): the handle's centre and size, and the
# blade's, which runs from the guard to the tip.
HANDLE_CENTRE = (0.0, 0.0, 0.98)
HANDLE_SIZE = (2.7, 3.1, 12.3)
BLADE_CENTRE = (0.0, 0.0, -14.8)
BLADE_SIZE = (3.6, 0.3, 18.6)
TILT_DEG = 30.0
# Heated, the blade glows from the guard down (heat.py): past HOT_START along
# the mesh's -Z, coming in over HOT_FADE.
HOT_AXIS = (0.0, 0.0, -1.0)
HOT_START = 5.4
HOT_FADE = 2.0


def blade_rotation():
    """The model's rotation: its -Z (the blade) up and tipped TILT_DEG towards
    +X. Found by testing, as grip._barrel_rotation is, not argued from
    rotator handedness."""
    for pitch in (-TILT_DEG, TILT_DEG):
        r = _rot(pitch=pitch, roll=180.0)
        b = _rotate_vector(r, unreal.Vector(0.0, 0.0, -1.0))
        if b.x > 0.1 and b.z > 0.8:
            return r
    raise RuntimeError("no rotation puts the knife's blade up and forward")


def _placed(point, rot, offset):
    v = _rotate_vector(rot, unreal.Vector(*point))
    return (v.x + offset[0], v.y + offset[1], v.z + offset[2])


def knife_model():
    """The model, placed so the handle's centre is the weapon's origin."""
    rot = blade_rotation()
    c = _rotate_vector(rot, unreal.Vector(*HANDLE_CENTRE))
    loc = (-c.x, -c.y, -c.z)
    return (("Model", KNIFE_MESH, loc, rot, (1.0, 1.0, 1.0)),)


def knife_outline():
    """Grip and Blade as boxes in the weapon's frame, the form the grip solve
    reads (weapon_models.py says why an outline). Never built."""
    (_n, _m, loc, rot, _s), = knife_model()
    return tuple((name, CUBE, _placed(centre, rot, loc), rot,
                  tuple(s / 100.0 for s in size), MAT_METAL)
                 for name, centre, size in (("Grip", HANDLE_CENTRE, HANDLE_SIZE),
                                            ("Blade", BLADE_CENTRE, BLADE_SIZE)))


def build_knife(item_bp):
    """BP_Knife: the model on Body, the glow of its blade heated (heat.py),
    and the base class's defaults for a knife."""
    bp = _create_blueprint(KNIFE_BP_PATH, BEL.generated_class(item_bp))
    (_n, _m, loc, rot, _s), = knife_model()
    build_heated_model(bp, knife_model(), _placed(BLADE_CENTRE, rot, loc))
    aim = HOLD_KNIFE_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    _apply_defaults(bp, {
        "DisplayName": KNIFE_DISPLAY,
        "Melee": True,
        HEATS_VAR: True,
        HOT_VAR: False,
        COOL_VAR: 0.0,
        HEAT_MATERIAL_VAR: build_hot_instance(MAT_HOT_KNIFE, HOT_AXIS, HOT_START,
                                              HOT_FADE),
        "Consumable": False,
        "Dropped": False,
        "UsesAmmo": False,
        "Automatic": False,
        # What the slash does, for the record; the blow itself uses
        # COMBAT.knife_damage, since it lands after the press and the knife
        # may no longer be in hand by then.
        "Damage": float(COMBAT.knife_damage),
        "PelletCount": 0,
        "WeaponRange": float(COMBAT.knife_reach_cm),
        "MagazineSize": 0,
        "Loaded": 0,
        "Reserve": 0,
        "InfiniteReserve": False,
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(0.0, 0.0, 0.0),
        "GripLocation": unreal.Vector(*_grip_location(aim, grip_rot, knife_outline())),
        "GripRotation": grip_rot,
        "SlotColor": unreal.LinearColor(*ICON_TINT, 1.0),
        # Not 1.0: the ADS speed and the scope fade divide by (AdsZoom - 1),
        # and right-click still aims with a knife in hand (as with food).
        "AdsZoom": float(COMBAT.ads_zoom_irons),
        "Scoped": False,
        "RecoilPitch": 0.0,
        "ShotVolume": 0.0,
        "TwoHanded": False,
        "Icon": _weapon_icon(KNIFE_DISPLAY),
        "AimPose": _must_load(aim),
    })
    _log(f"built {KNIFE_BP_PATH} ({KNIFE_MESH.rsplit('/', 1)[-1]}, "
         f"{COMBAT.knife_damage:.0f} per slash every {COMBAT.knife_interval_s:.2f} s)")
    return bp
