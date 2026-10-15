"""The drawn grip's variables (uebp/vars.py rows): the weapon component's,
which weapon_component/drawn_grip.py writes each frame, and the drawn
MetaHuman's anim Blueprint's, which drawn_grip_graph.py copies them into on
its update and weighs the fitted hands by.
"""

from combat.drawn_grip_consts import (
    GRIP_CARRY_VAR, GRIP_GUN_VAR, GRIP_LEFT_VAR, GRIP_RIGHT_VAR, GRIP_SIGHTS_VAR,
)
from uebp.vars import FLOAT, Var, array, obj

_CLIP = obj("/Script/Engine.AnimSequenceBase")

# The gun's first frame of the clip (seconds, a whole number: its place in
# drawn_grip_consts.GUNS x FRAMES_PER_GUN), the right hand's weight (1 with a
# fitted gun in hand), the left's (eased: on the gun, not lowered unless
# carried, not reloading), and how far the left is the carry's frame (eased).
GripGun = Var(GRIP_GUN_VAR, FLOAT, 0.0)
GripRight = Var(GRIP_RIGHT_VAR, FLOAT, 0.0)
GripLeft = Var(GRIP_LEFT_VAR, FLOAT, 0.0)
GripCarry = Var(GRIP_CARRY_VAR, FLOAT, 0.0)
# Each gun's ready pose (finger_pose.clip_for), in GUNS' order: HandPose is
# found in it.
GripPoses = Var("GripPoses", array(_CLIP))
COMP = (GripGun, GripRight, GripLeft, GripCarry, GripPoses)

# On the anim Blueprint: the four, and how far the left is the sights' frame
# (the component's SightBlend).
ANIM = (Var(GRIP_GUN_VAR, FLOAT), Var(GRIP_RIGHT_VAR, FLOAT), Var(GRIP_LEFT_VAR, FLOAT),
        Var(GRIP_SIGHTS_VAR, FLOAT), Var(GRIP_CARRY_VAR, FLOAT))
