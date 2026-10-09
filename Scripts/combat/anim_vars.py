"""What the builders add to the player's anim Blueprints' member variables
(the weapon layers, and before G4 ABP_Unarmed itself), named once: each row is
the name and the pin type (uebp/vars.py). Each fragment declares its own
group, where it always has; all start at zero or false.
"""

from uebp.vars import BOOL, FLOAT, VECTOR, Var
from combat import item_vars as IV
from combat.gas_moves_tuning import POSE_SLIDE
from combat.server_anim_consts import SERVER_POSE_VAR

# aim_pitch.py: the view's pitch, which two spine bones take half of each.
AimPitch = Var("AimPitch", FLOAT)
AIM = (AimPitch,)

# body_pose.py: the pose weights (pose_weights.py writes them), then the kneel
# over a body being searched and how far into its clip.
GuardArms = Var("GuardArms", FLOAT)
GuardGun = Var("GuardGun", FLOAT)
PoseCrouch = Var("PoseCrouch", FLOAT)
PoseProne = Var("PoseProne", FLOAT)
PoseKneel = Var("PoseKneel", FLOAT)
KneelTime = Var("KneelTime", FLOAT)
POSE_WEIGHTS = (GuardArms, GuardGun, PoseCrouch, PoseProne)
POSE = (*POSE_WEIGHTS, PoseKneel, KneelTime)

# support_hand.py: the IK's weight and its point; under the same name, each
# gun's own on BP_WeaponItem.
SupportHand = Var("SupportHand", FLOAT)
SupportPoint = Var(str(IV.SupportPoint), VECTOR)
SUPPORT = (SupportHand, SupportPoint)

# stance_clips.py: the slide's weight, declared only with the slide on.
SLIDE = (Var(POSE_SLIDE, FLOAT),)

# server_anim.py, gas_locomotion.py: this machine is a dedicated server.
SERVER = (Var(SERVER_POSE_VAR, BOOL),)

# weapon_layers.py, player_gait.py: the pawn's speed over the ground.
GroundSpeed = Var("GroundSpeed", FLOAT)
GROUND = (GroundSpeed,)
