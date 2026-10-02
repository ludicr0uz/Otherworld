"""The sight sway's numbers: how far the aim wanders down the sights, how
slowly, and how much a low stance steadies it. Constants only; the graph is
weapon_component/sway.py.
"""

import math

# Down the sights the aim drifts on two sines, one sideways and one up and
# down, with periods that share no small multiple: the path is a slow figure
# that does not visibly repeat. It is the VIEW that drifts (the control
# rotation), and the gun and its sights with it, so the sights stay on the
# point the shot goes to at every moment of it.
#
# 0.30 degrees is 26 cm at 50 m: a head-sized error at the sniper's range and
# nothing at the shotgun's, which is the point -- it is what a long shot costs
# standing up. Through the 4x scope it reads as four times the angle.
SWAY_YAW_DEG = 0.30
SWAY_PITCH_DEG = 0.20
SWAY_YAW_PERIOD_S = 5.6
SWAY_PITCH_PERIOD_S = 3.5
# How fast each gun's sway runs: the clock the sines read advances at this
# times the frame's time, so 0.5 doubles both periods (11.2 s and 7 s) and
# halves how fast the sights wander, at the same width. Per gun: the
# gun_tuning.csv column SWAY_RATE_COLUMN, BP_WeaponItem's SWAY_RATE_VAR,
# copied each frame onto the component's own (sway.py). At 1.0 the sway
# crossed the target too fast to time a shot.
SWAY_RATE = 0.5
SWAY_RATE_COLUMN = "sway_rate"
SWAY_RATE_VAR = "SwayRate"
# A low stance steadies it, as it does the cloud and the recoil.
SWAY_CROUCH_SCALE = 0.6
SWAY_PRONE_SCALE = 0.3

# The view is turned only once the sway has moved this far from what has been
# applied, in either axis. AController::SetControlRotation drops a change
# under a thousandth of a degree, and at a high frame rate every frame's step
# is smaller than that: turned frame by frame, the view would stay put while
# the offsets below counted the sway as given, and letting go would "give
# back" a turn that never happened. Twice the controller's tolerance; a ninth
# of a pixel through the 4x scope.
SWAY_MIN_STEP_DEG = 0.002

# The component's variables: the clock the sines read, and how far the sway
# has turned the view so far (each frame turns it by the change, so the mouse
# and the recoil keep working on top of it and letting go gives it all back).
SWAY_TIME_VAR = "SwayTime"
SWAY_YAW_VAR = "SwayYaw"
SWAY_PITCH_VAR = "SwayPitch"
SWAY_VARS = (SWAY_TIME_VAR, SWAY_YAW_VAR, SWAY_PITCH_VAR)


def sway_rate(period_s):
    """Radians per second for a period: Sin takes radians."""
    return 2.0 * math.pi / period_s


def sway_at(t, blend, stance_scale=1.0, breath_scale=1.0):
    """(yaw, pitch) in degrees the sway holds the view off by at clock `t`
    (the clock is already the rate's: game seconds x SwayRate)."""
    k = blend * stance_scale * breath_scale
    return (SWAY_YAW_DEG * k * math.sin(t * sway_rate(SWAY_YAW_PERIOD_S)),
            SWAY_PITCH_DEG * k * math.sin(t * sway_rate(SWAY_PITCH_PERIOD_S)))
