"""BP_Wood: a piece of firewood, what a tree gives the axe
(weapon_component/chop.py spawns it beside the trunk).

Wood IS a BP_WeaponItem, for the reason food is one (survival/consumables.py):
the bag, Q, G, E, the throw, the profile and the HUD strip are keyed on that
class. It defaults to `Dropped`, as food does, so a spawned piece is already
what E looks for.

It is neither Melee nor Consumable, and the fire key does nothing with it
without a branch of its own: it takes the guns' path as a gun with no pellets,
no sound, no recoil and no noise. The carry treats it as a gun too, so it
rides in the lowered hand.

THE MODEL
---------
SM_WoodLog (CC0, Quaternius's Survival Pack, imported by
asset_pipeline/import_quaternius.py) lies along X, 377 units long and 110
thick, resting on z = 0 and off centre. The pack is at no one size
(weapon_models.py), and this log is a fat one, so it is scaled apart: 0.08
along its length and 0.055 across, a 30 cm split of firewood 6 cm thick.

A log has no handle, and the hand has one pose, the pistol's, closed on a
handle running up through it: its joints sit inside anything over 4 cm thick.
So the log stands on end in the item's frame, its middle at the origin, and is
held like a club, where the fist sinks least (1.6 cm; across the fist, or
thicker, 2 to 2.7 cm: verify/chop.py bounds it). A dropped item is set down level in its own frame, so a
dropped log stands on its end; the one a tree gives is laid flat by the spawn
(chop_tuning.WOOD_LIE_PITCH_DEG).
"""

import unreal

from combat.chop_tuning import CHOPS_VAR
from combat.log import _log
from uebp.graph import BEL, _apply_defaults, _create_blueprint, _must_load, _rot
from combat.grip import _grip_location, _grip_rotation, _rotate_vector
from combat.paths import CUBE, HOLD_ITEM_ANIM_PATH, MAT_METAL, WOOD_BP_PATH
from combat.tuning import COMBAT
from combat.weapon_items import build_model
from combat.weapon_specs import _weapon_icon
from item_icons.items import ICON_TINT

WOOD_MESH = "/Game/Sourced/Quaternius/Survival/SM_WoodLog"
WOOD_DISPLAY = "Wood"
# Along the mesh's length (its X), and across it.
WOOD_SCALE = (0.08, 0.055, 0.055)

# The middle of the mesh's bounds, in its own units, and the scaled log (cm):
# its length, and its thickness either way.
MESH_CENTRE = (-2.33, -9.47, 52.73)
LOG_LENGTH_CM = 30.2
LOG_THICK_CM = (6.1, 6.0)
GRIP_LENGTH_CM = 12.0


def log_rotation():
    """The model's rotation: its +X (the log's length) up the item's +Z. Found
    by testing, as axe.head_rotation is."""
    for pitch in (90.0, -90.0):
        r = _rot(pitch=pitch)
        if _rotate_vector(r, unreal.Vector(1.0, 0.0, 0.0)).z > 0.99:
            return r
    raise RuntimeError("no rotation stands the log on its end")


def wood_model():
    """The model, on end, placed so the log's middle is the item's origin."""
    rot = log_rotation()
    c = _rotate_vector(rot, unreal.Vector(*(m * k for m, k in zip(MESH_CENTRE, WOOD_SCALE))))
    return (("Model", WOOD_MESH, (-c.x, -c.y, -c.z), rot, WOOD_SCALE),)


def wood_outline():
    """Grip: the middle of the log as a box in the item's frame, the form the
    grip solve reads (weapon_models.py says why an outline). Never built."""
    return (("Grip", CUBE, (0.0, 0.0, 0.0), _rot(),
             (LOG_THICK_CM[1] / 100.0, LOG_THICK_CM[0] / 100.0, GRIP_LENGTH_CM / 100.0),
             MAT_METAL),)


def build_wood(item_bp):
    """BP_Wood: the model on Body, and the base class's defaults for a log."""
    bp = _create_blueprint(WOOD_BP_PATH, BEL.generated_class(item_bp))
    build_model(bp, wood_model())
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{WOOD_BP_PATH} failed to compile")
    aim = HOLD_ITEM_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    _apply_defaults(bp, {
        "DisplayName": WOOD_DISPLAY,
        "Melee": False,
        "Consumable": False,
        CHOPS_VAR: False,
        # True, as on food: a piece of wood starts life on the ground, which
        # is what E looks for; picking it up clears it.
        "Dropped": True,
        # Nothing to fire: the fire key runs the guns' path over no pellets.
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
        "GripLocation": unreal.Vector(*_grip_location(aim, grip_rot, wood_outline())),
        "GripRotation": grip_rot,
        "SlotColor": unreal.LinearColor(*ICON_TINT, 1.0),
        # Not 1.0, for the knife's reason: right-click still aims.
        "AdsZoom": float(COMBAT.ads_zoom_irons),
        "Scoped": False,
        "RecoilPitch": 0.0,
        "ShotVolume": 0.0,
        "TwoHanded": False,
        "Icon": _weapon_icon(WOOD_DISPLAY),
        "AimPose": _must_load(aim),
    })
    _log(f"built {WOOD_BP_PATH} ({WOOD_MESH.rsplit('/', 1)[-1]} at {WOOD_SCALE}, "
         f"a {LOG_LENGTH_CM:.0f} cm log)")
    return bp
