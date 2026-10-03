"""BP_Axe: Quaternius's Survival Pack axe as a melee item, the fourth thing the
player starts with.

An axe IS a BP_WeaponItem flagged `Melee`, for the reasons the knife is one
(knife.py): the bag, Q, G, E and the HUD strip are keyed on that class, and
the fire key's gate branches on `Melee` before anything gun-shaped runs. So
with the axe in hand the fire key swings it through the knife's own stage
(weapon_component/knife.py): the same clip, cooldown, reach and damage. It has
no numbers of its own yet; an axe that hits harder needs its own Strike there.
What is its own is `Chops`: a blow of it that lands on a tree cuts wood
(weapon_component/chop.py).

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

from combat.slot_tuning import MELEE_KIND, WEAPON_KIND_VAR
from combat.chop_tuning import CHOPS_VAR
from combat.log import _log
from uebp.graph import BEL, _apply_defaults, _create_blueprint, _must_load, _rot
from combat.grip import _grip_location, _grip_rotation, _rotate_vector
from combat.heat import build_heated_model, build_hot_instance
from combat.heat_tuning import COOL_VAR, HEAT_MATERIAL_VAR, HEATS_VAR, HOT_VAR
from combat.knife import _placed
from combat.paths import (
    AXE_BP_PATH, CUBE, HOLD_KNIFE_ANIM_PATH, MAT_HOT_AXE, MAT_METAL,
)
from combat.lodge import lodge_pose
from combat.melee_tuning import melee_throw
from combat.throw_tuning import (
    LODGE_AXE_DEPTH_CM, LODGE_POINT_VAR, LODGE_TURN_VAR, MELEE_THROW,
)
from combat.tuning import COMBAT
from combat.weapon_specs import _weapon_icon
from item_icons.items import ICON_TINT
from combat import item_vars as IV

# asset_pipeline/import_quaternius.py imports every Survival Pack FBX here.
AXE_MESH = "/Game/Sourced/Quaternius/Survival/SM_Axe"
AXE_DISPLAY = "Axe"
AXE_SCALE = 0.2

# On the scaled mesh, in its own frame (cm): the stretch of haft the fist
# closes on, and the head from bit to poll.
HANDLE_CENTRE = (0.2, 0.0, 2.0)
HANDLE_SIZE = (3.3, 2.6, 12.0)
HEAD_CENTRE = (-4.8, 0.0, 37.5)
HEAD_SIZE = (25.2, 3.6, 23.4)
TILT_DEG = 30.0
# Heated, the head glows (heat.py): past HOT_START_CM up the scaled mesh's +Z,
# where the head begins, coming in over HOT_FADE_CM. The overlay measures in
# the mesh's own units, so both go to it divided by AXE_SCALE.
HOT_AXIS = (0.0, 0.0, 1.0)
HOT_START_CM = 25.7
HOT_FADE_CM = 2.0


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


def axe_lodge():
    """How the axe sits in a tree it was thrown into (lodge.lodge_pose): bit
    first, LODGE_AXE_DEPTH_CM of the head in the wood, the haft hanging."""
    (_n, _m, loc, rot, _s), = axe_model()
    along = _rotate_vector(rot, unreal.Vector(-1.0, 0.0, 0.0))
    bit = (HEAD_CENTRE[0] - HEAD_SIZE[0] / 2.0, 0.0, HEAD_CENTRE[2])
    return lodge_pose(along, _placed(bit, rot, loc), LODGE_AXE_DEPTH_CM)


def build_axe(item_bp):
    """BP_Axe: the model on Body, the glow of its head heated (heat.py), and
    the base class's defaults for an axe."""
    bp = _create_blueprint(AXE_BP_PATH, BEL.generated_class(item_bp))
    (_n, _m, loc, rot, _s), = axe_model()
    build_heated_model(bp, axe_model(), _placed(HEAD_CENTRE, rot, loc))
    aim = HOLD_KNIFE_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    lodge = axe_lodge()
    _apply_defaults(bp, {
        IV.DisplayName: AXE_DISPLAY,
        IV.Melee: True,
        WEAPON_KIND_VAR: MELEE_KIND,
        # Thrown hard and flat, spinning forward, edge first.
        **MELEE_THROW,
        # ...and it wounds what it strikes, and lodges in a tree. Its tip
        # and its damage are its gun_tuning.csv row's (melee_tuning.py).
        **melee_throw(AXE_DISPLAY),
        LODGE_TURN_VAR: lodge[0],
        LODGE_POINT_VAR: lodge[1],
        CHOPS_VAR: True,
        HEATS_VAR: True,
        HOT_VAR: False,
        COOL_VAR: 0.0,
        HEAT_MATERIAL_VAR: build_hot_instance(
            MAT_HOT_AXE, HOT_AXIS, HOT_START_CM / AXE_SCALE, HOT_FADE_CM / AXE_SCALE),
        IV.Consumable: False,
        IV.Dropped: False,
        IV.UsesAmmo: False,
        IV.Automatic: False,
        # For the record, as on the knife: the blow is the knife's Strike and
        # uses COMBAT.knife_*, whichever Melee item is in hand.
        IV.Damage: float(COMBAT.knife_damage),
        IV.PelletCount: 0,
        IV.WeaponRange: float(COMBAT.knife_reach_cm),
        IV.MagazineSize: 0,
        IV.Loaded: 0,
        IV.Reserve: 0,
        IV.InfiniteReserve: False,
        IV.NextFireTime: 0.0,
        IV.MuzzleOffset: unreal.Vector(0.0, 0.0, 0.0),
        IV.GripLocation: unreal.Vector(*_grip_location(aim, grip_rot, axe_outline())),
        IV.GripRotation: grip_rot,
        IV.SlotColor: unreal.LinearColor(*ICON_TINT, 1.0),
        # Not 1.0, for the knife's reason: right-click still aims.
        IV.AdsZoom: float(COMBAT.ads_zoom_irons),
        IV.Scoped: False,
        IV.RecoilPitch: 0.0,
        IV.ShotVolume: 0.0,
        IV.TwoHanded: False,
        IV.Icon: _weapon_icon(AXE_DISPLAY),
        IV.AimPose: _must_load(aim),
    })
    _log(f"built {AXE_BP_PATH} ({AXE_MESH.rsplit('/', 1)[-1]} at {AXE_SCALE}, "
         f"swung as the knife is)")
    return bp
