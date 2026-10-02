"""The sprint's direction rule: its numbers and names. Constants only; the
graph is weapon_component/sprint.py. (The speed and the stamina are COMBAT's.)
"""

import math

# A sprint runs only forwards: the way the player is steering has to lie
# within this many degrees, left or right, of the way the character faces
# (which is the camera's yaw: the character turns with the controller). So
# forward and the two forward diagonals sprint (a keyboard's are at 45);
# sideways, backwards and standing still do not, and cost no stamina.
SPRINT_CONE_HALF_ANGLE_DEG = 60.0
# What the graph compares: the dot of the two unit vectors, at the cone's edge.
SPRINT_CONE_MIN_DOT = round(math.cos(math.radians(SPRINT_CONE_HALF_ANGLE_DEG)), 4)

# Stored once a frame, before Sprinting: is the player steering into the cone?
SPRINT_AHEAD_VAR = "SprintAhead"
