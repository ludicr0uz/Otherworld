"""The look's names (look.py owns the graph and says what they are for): the
three variables replicated to the other players, the pose the equip plays,
what the owning machine last reported, and the Server event.
"""

from uebp.vars import BOOL, INT, Var, obj

POSE_TYPE = obj("/Script/Engine.AnimSequence")
HIP, SHOULDER, SIGHTS = 0, 1, 2

# Replicated, to everyone but the owner.
LookAim = Var("LookAim", INT, HIP)
LookLowered = Var("LookLowered", BOOL, False)
LookPose = Var("LookPose", POSE_TYPE)
REPLICATED = (LookAim, LookLowered, LookPose)
# The pose the hand's item is held in, on this copy: what the equip plays.
HandPose = Var("HandPose", POSE_TYPE)
# What the owning machine last reported. SentAim starts at no mode, so the
# first local frame reports.
SentAim = Var("SentAim", INT, -1)
SentLowered = Var("SentLowered", BOOL, False)
SentPose = Var("SentPose", POSE_TYPE)
TABLE = REPLICATED + (HandPose, SentAim, SentLowered, SentPose)

SERVER_SET_LOOK = "Server_SetLook"
LOOK_PARAMS = (("Aim", INT), ("Lowered", BOOL), ("Pose", POSE_TYPE))
