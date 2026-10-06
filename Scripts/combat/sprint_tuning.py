"""The sprint's direction rule, and the names of the numbers the sprint
reads off the component. Constants only; the graph is
weapon_component/sprint.py and the sprint itself the movement component's
(combat/player_move.py). (The speed and the stamina are COMBAT's, which
takes them from player_tuning.csv.)
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
# A probe's hand on the sprint key (ORed with it): no key can be pressed in a
# headless game.
SPRINT_FORCED_VAR = "SprintForced"

# What the sprint graph hands the movement component instead of literals, so the menu's PLAYER
# SETTINGS tab can change them in a running game (graphics_menu/
# player_tune_tick.py). Built from COMBAT; cm/s and stamina points a second.
# The jog has no variable of its own: it is BaseSpeed, cached off the
# character at BeginPlay.
BASE_SPEED_VAR = "BaseSpeed"
SPRINT_SPEED_VAR = "SprintSpeed"
STAMINA_DRAIN_VAR = "StaminaDrainPerSecond"
STAMINA_REGEN_VAR = "StaminaRegenPerSecond"
SPRINT_RATE_VARS = (SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR)
