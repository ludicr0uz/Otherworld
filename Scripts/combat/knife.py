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
z -24.3 -- measured off the mesh's vertices. It is held in A_HoldKnife,
Mixamo's knife idle (melee_clips.py), whose fist is the pistol pose's, and a pistol's
grip runs up and down through the fist, so the knife's handle does too: the
model is turned over, blade up, and tipped 30 deg forward, a hammer grip with
the edge leading. `Grip` in the outline is the handle, so grip._grip_location
seats it in the fist exactly as it seats a pistol's grip.

Thrown, it is held the other way, by the blade (knife_throw_grip): turned
end for end about the across axis, so the blade runs down through the fist and
the handle stands up over it, with the blade's middle seated in the fist of
A_ThrowReady (throw_pose.py). weapon_component/throw_ready.py puts it there
while the arm is cocked.
"""

import unreal

from combat.slot_tuning import MELEE_KIND, WEAPON_KIND_VAR
from combat.log import _log
from uebp.graph import BEL, _apply_defaults, _assets, _create_blueprint, _must_load, _rot
from combat.grip import _grip_location, _grip_rotation, _rotate_vector
from combat.heat import build_heated_model, build_hot_instance
from combat.heat_tuning import COOL_VAR, HEAT_MATERIAL_VAR, HEATS_VAR, HOT_VAR
from combat.skin import player_skin
from combat.paths import (
    CUBE, HOLD_KNIFE_ANIM_PATH, KNIFE_BP_PATH, MAT_HOT_KNIFE, MAT_METAL,
    THROW_READY_ANIM_PATH,
)
from combat.lodge import lodge_pose
from combat.melee_tuning import melee_throw
from combat.throw_tuning import (
    LODGE_KNIFE_DEPTH_CM, LODGE_POINT_VAR, LODGE_TURN_VAR, MELEE_THROW,
    THROW_GRIP_LOC_VAR, THROW_GRIP_ROT_VAR, THROW_GRIP_VAR,
)
from combat.tuning import COMBAT
from combat.weapon_models import FAB_WEAPONS
from combat.weapon_specs import _weapon_icon
from item_icons.items import ICON_TINT
from combat import item_vars as IV
from Sound.bind import defaults_for
from Sound.sound_items import BINDINGS as ITEM_SOUNDS

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


def knife_lodge():
    """How the knife sits in a tree it was thrown into (lodge.lodge_pose):
    point first, LODGE_KNIFE_DEPTH_CM of the blade in the wood."""
    (_n, _m, loc, rot, _s), = knife_model()
    along = _rotate_vector(rot, unreal.Vector(0.0, 0.0, -1.0))
    tip = (0.0, 0.0, BLADE_CENTRE[2] - BLADE_SIZE[2] / 2.0)
    return lodge_pose(along, _placed(tip, rot, loc), LODGE_KNIFE_DEPTH_CM)


def knife_throw_grip(grip_rot):
    """(ThrowGripLocation, ThrowGripRotation): the knife held by its blade in
    the ready-to-throw pose. The hammer grip turned 180 deg about the weapon's
    own Y (end for end, edge still leading), then the Blade part seated at
    the fist of A_ThrowReady. None if there is no ready pose (no throw clip),
    in which case the knife is thrown from the hammer grip."""
    if not _assets().does_asset_exist(THROW_READY_ANIM_PATH):
        return None
    one = unreal.Vector(1.0, 1.0, 1.0)
    over = unreal.Transform(rotation=unreal.Quat(0.0, 1.0, 0.0, 0.0).rotator(),
                            scale=one)
    hand = unreal.Transform(rotation=grip_rot, scale=one)
    rot = unreal.MathLibrary.compose_transforms(over, hand).rotation.rotator()
    loc = _grip_location(THROW_READY_ANIM_PATH, rot, knife_outline(), part="Blade")
    return unreal.Vector(*loc), rot


def build_knife(item_bp):
    """BP_Knife: the model on Body, the glow of its blade heated (heat.py),
    and the base class's defaults for a knife."""
    bp = _create_blueprint(KNIFE_BP_PATH, BEL.generated_class(item_bp))
    (_n, _m, loc, rot, _s), = knife_model()
    build_heated_model(bp, knife_model(), _placed(BLADE_CENTRE, rot, loc))
    aim = HOLD_KNIFE_ANIM_PATH
    # Seated as a pistol is: the ready pose's fist is the pistol pose's
    # (melee_clips.py), and its hand is turned as Mixamo's clip turns it, so
    # the rotation is the pistol hand's own and not one solved for a hand
    # that faces ahead.
    grip_rot = _grip_rotation(player_skin().aim_pistol)
    lodge = knife_lodge()
    throw_grip = knife_throw_grip(grip_rot)
    _apply_defaults(bp, {
        **defaults_for(KNIFE_BP_PATH, ITEM_SOUNDS),
        IV.DisplayName: KNIFE_DISPLAY,
        IV.Melee: True,
        WEAPON_KIND_VAR: MELEE_KIND,
        # Thrown hard and flat, spinning forward, edge first.
        **MELEE_THROW,
        # ...and it wounds what it strikes, and lodges in a tree. Its tip
        # and its damage are its gun_tuning.csv row's (melee_tuning.py).
        **melee_throw(KNIFE_DISPLAY),
        LODGE_TURN_VAR: lodge[0],
        LODGE_POINT_VAR: lodge[1],
        # Cocked for the throw, held by the blade (throw_ready.py).
        THROW_GRIP_VAR: throw_grip is not None,
        THROW_GRIP_LOC_VAR: throw_grip[0] if throw_grip else unreal.Vector(),
        THROW_GRIP_ROT_VAR: throw_grip[1] if throw_grip else unreal.Rotator(),
        HEATS_VAR: True,
        HOT_VAR: False,
        COOL_VAR: 0.0,
        HEAT_MATERIAL_VAR: build_hot_instance(MAT_HOT_KNIFE, HOT_AXIS, HOT_START,
                                              HOT_FADE),
        IV.Consumable: False,
        IV.Dropped: False,
        IV.UsesAmmo: False,
        IV.Automatic: False,
        # What the slash does, for the record; the blow itself uses
        # COMBAT.knife_damage, since it lands after the press and the knife
        # may no longer be in hand by then.
        IV.Damage: float(COMBAT.knife_damage),
        IV.PelletCount: 0,
        IV.WeaponRange: float(COMBAT.knife_reach_cm),
        IV.MagazineSize: 0,
        IV.Loaded: 0,
        IV.Reserve: 0,
        IV.InfiniteReserve: False,
        IV.NextFireTime: 0.0,
        IV.MuzzleOffset: unreal.Vector(0.0, 0.0, 0.0),
        IV.GripLocation: unreal.Vector(*_grip_location(aim, grip_rot, knife_outline())),
        IV.GripRotation: grip_rot,
        IV.SlotColor: unreal.LinearColor(*ICON_TINT, 1.0),
        # Not 1.0: the ADS speed and the scope fade divide by (AdsZoom - 1),
        # and right-click still aims with a knife in hand (as with food).
        IV.AdsZoom: float(COMBAT.ads_zoom_irons),
        IV.Scoped: False,
        IV.RecoilPitch: 0.0,
        IV.ShotVolume: 0.0,
        IV.TwoHanded: False,
        IV.Icon: _weapon_icon(KNIFE_DISPLAY),
        IV.AimPose: _must_load(aim),
    })
    _log(f"built {KNIFE_BP_PATH} ({KNIFE_MESH.rsplit('/', 1)[-1]}, "
         f"{COMBAT.knife_damage:.0f} per slash every {COMBAT.knife_interval_s:.2f} s)")
    return bp
