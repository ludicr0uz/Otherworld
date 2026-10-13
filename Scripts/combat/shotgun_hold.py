"""The shotgun's hold: the rifle's ready pose, a shipped clip, with the left
hand's point moved onto the pump. No pose is keyed here (C3): this module
works out one offset, the shotgun's SupportPoint. (The fingers are bent onto
the gun afterwards, like any fitted gun's, in a clip that is that pose but
for them: finger_pose.py, A_AimShotgun, the name the keyed pose had.)

WHY THE SHOTGUN NEEDS ONE
-------------------------
The rifle ready pose (PlayerSkin.aim_rifle, Lyra's MM_Rifle_Idle_ADS) holds a
pistol grip under a tall receiver: the left palm stands on edge beside a deep
handguard, its thumb up the side. The AK's and the Val's sight lines run 14 cm
above the grip, so the thumb is nowhere near the picture. The shotgun
(Stein Games' SM_Shotgun_02) has a wooden stock with no pistol grip, a sight
line that skims the receiver 8.5 cm above the fist, and a bar of a pump 4.8 cm
deep where the middle of that handguard would be. In the rifle's pose, measured in the weapon's frame:

  - the left thumb's tip is 4.2 cm ABOVE the sight line, 5 cm left of the
    barrel: a finger standing beside the bead;
  - the hand is at the pump's back end: one joint 1.4 cm inside the wood,
    the pinky's knuckle 4.5 cm behind it.

Until C3 a pose of its own was keyed for it (A_AimShotgun: both thumbs, the
left hand's turn and every finger joint swung onto directions in a table).
Every gun pose is a shipped clip now, so the hand keeps the clip's shape and
is MOVED instead, as one rigid piece.

HOW
---
Down the sights the left hand is held by an IK on a point in the right hand's
space, each gun's own (support_hand.py, BP_WeaponItem.SupportPoint). The
shotgun's is the rifle pose's point plus support_move(): first straight down
until the thumb is under the barrel's top, then hand_seat.seat's descent to
where the fingers' joints fit the pump best with the thumb kept there. On the
worn hand that is 2.6 cm forward (as far as the arm reaches: the IK does not
stretch it) and 5.4 down: the hand cupped under the pump, its
fingers up the right side, its thumb beside the barrel under the sight line.

The fit itself is every gun's now (gun_hold.py; the shotgun's row names its
pump and its barrel, weapon_models.SHOTGUN_SUPPORT). What is left here is the
shotgun's row for it, which the shotgun's verifier and probes measure
against, and the reasons above.

WHAT A SHIPPED CLIP COSTS
-------------------------
  - The hand's shape is the rifle pose's, made for a deeper handguard: seated,
    its joints ride up to 5.0 cm off the wood (the keyed pose had them
    within 1.6). The barrel is only 2.2 cm over the pump, and the thumb under
    its top holds the hand that low. The knuckles stay there; the fingers
    past them are bent up onto the wood by finger_pose.py.
  - The point holds only down the sights (SupportHand is SightBlend). At the
    hip and on the shoulder the hand is where the clip has it; the camera is
    not on the sights there.
  - The right thumb lies forward along the top of the stock's wrist, 3.6 cm
    under the sight line, as the clip has it on a pistol grip; the keyed pose
    wrapped it over the wrist.
"""

from combat import finger_pose, gun_hold
from combat.grip import _grip_location, _grip_rotation
from combat.paths import WEAPON_DIR
from combat.weapon_models import (
    SHOTGUN_SIGHT_FRONT, SHOTGUN_SIGHT_REAR, SHOTGUN_SUPPORT, shotgun_outline,
)

NAME = "BP_Shotgun"


def row(skin):
    """What gun_hold reads of the shotgun's row of weapon_specs, made here so
    a check of the shotgun does not solve all five guns."""
    grip_rot = _grip_rotation(skin.aim_rifle)
    return dict(display="Shotgun", path=f"{WEAPON_DIR}/{NAME}",
                aim=finger_pose.clip_for(NAME), pose=skin.aim_rifle,
                parts=shotgun_outline(),
                grip_rot=grip_rot,
                grip_loc=_grip_location(skin.aim_rifle, grip_rot, shotgun_outline()),
                sight_rear=SHOTGUN_SIGHT_REAR, sight_front=SHOTGUN_SIGHT_FRONT,
                support=SHOTGUN_SUPPORT)


def barrel_top():
    """The top of the shotgun's barrel, a z in the weapon's frame: what the
    left thumb stays under, and it is under the sight line."""
    return gun_hold.part_box(shotgun_outline(), SHOTGUN_SUPPORT["under"])[1][2]


def held(skin):
    """The rifle pose with the shotgun in its hand: (the pose in the
    component, the weapon's quat there, a function placing a component point
    in the weapon's frame)."""
    return gun_hold.held(skin, row(skin))


def support_move(skin, quiet=False):
    """How far the left hand is moved off the rifle pose's place to sit on
    the pump, (x, y, z) cm in the weapon's frame."""
    return gun_hold.support_move(skin, row(skin), quiet)


def support_point(skin, quiet=False):
    """The shotgun's SupportPoint: where the rifle pose has the left hand,
    moved by support_move(), in the right hand's bone space."""
    return gun_hold.support_point(skin, row(skin), quiet)

