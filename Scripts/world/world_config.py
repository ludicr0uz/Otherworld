"""World config: the settings that shape the world itself rather than any one
system in it. Today that is the day/night cycle: how long each half lasts,
where the clock starts, and what the sky, the sun and the moon look like.

This is the one place to change them. build_day_night.py writes the lengths
and the start time onto BP_DayNightCycle's defaults (and the looks into its
components, graph literals and M_DayNightSky), and verify_day_night.py reads
them back against this file. Change a number here, then re-run the builder.

The night half reuses the forest generator's "night" preset, and the day half
its "day" preset, so a level looks the same at midnight as it did before the
cycle existed.

Pure Python (no ``unreal``), so a probe or a unit test can do the same sums
the Blueprint does: see sun_state().
"""

import math

from forest_generator.lighting import get_preset

_DAY = get_preset("day")
_NIGHT = get_preset("night")

# ─── The clock ───────────────────────────────────────────────────────────────
# One cycle is a day followed by a night. The clock runs from 0 (sunrise) to
# DAY_LENGTH_S (sunset) to DAY_LENGTH_S + NIGHT_LENGTH_S (the next sunrise).
# 4 + 4 minutes for testing; a real day wants something like 20 + 10.
DAY_LENGTH_S = 240.0
NIGHT_LENGTH_S = 240.0
# Where a level starts: a little after sunrise, so the first thing the player
# sees is the sun coming up rather than the dark.
START_CLOCK_S = 20.0

# ─── The sun and the moon ────────────────────────────────────────────────────
# Each crosses the sky in its half of the cycle: it rises at SUNRISE_YAW_DEG,
# peaks at its max elevation halfway through and sets opposite where it rose.
# The moon takes the same path through the night that the sun takes by day.
SUNRISE_YAW_DEG = 90.0
SUN_MAX_ELEVATION_DEG = 60.0
MOON_MAX_ELEVATION_DEG = 45.0
SUN_LUX = _DAY["sun"]["intensity"]
SUN_COLOR = _DAY["sun"]["color"]               # sRGB 0-255
MOON_LUX = _NIGHT["sun"]["intensity"]          # the night preset's light IS the moon
MOON_COLOR = _NIGHT["sun"]["color"]
SHADOW_DISTANCE_CM = _DAY["sun"]["shadow_distance_cm"]

# Twilight: how much "day" there is follows the sun's elevation, fully night at
# NIGHT_BELOW_DEG and fully day at DAY_ABOVE_DEG. The moon fades in over its
# first MOON_FADE_DEG above the horizon. Stars come out as the sun sinks from
# the horizon to STARS_FULL_BELOW_DEG.
DAY_ABOVE_DEG = 8.0
NIGHT_BELOW_DEG = -6.0
MOON_FADE_DEG = 8.0
STARS_FULL_BELOW_DEG = -12.0

# ─── The sky (M_DayNightSky, an emissive dome the SkyLight captures) ─────────
# Linear colours. The dome is the whole sky, so it is also the ambient light:
# the SkyLight's real-time capture turns it into the fill for every shadow.
DAY_ZENITH_COLOR = [0.10, 0.24, 0.62, 1.0]
DAY_HORIZON_COLOR = [0.42, 0.55, 0.72, 1.0]
NIGHT_SKY_COLOR = _NIGHT["sky_dome"]["night_sky_color"]
SUNSET_COLOR = [1.2, 0.45, 0.12, 1.0]
SUN_DISC_COLOR = [40.0, 36.0, 30.0, 1.0]
MOON_DISC_COLOR = [1.6, 1.7, 2.0, 1.0]
STAR_BRIGHTNESS = _NIGHT["sky_dome"]["star_brightness"]
STAR_TILING = _NIGHT["sky_dome"]["star_tiling"]

# ─── Ambient, fog and exposure: night value, day value ───────────────────────
SKY_LIGHT_INTENSITY = (_NIGHT["sky_light"]["intensity"], _DAY["sky_light"]["intensity"])
FOG_DENSITY = (_NIGHT["fog"]["density"], _DAY["fog"]["density"])
FOG_COLOR = (_NIGHT["fog"]["inscattering_color"], _DAY["fog"]["inscattering_color"])
FOG_VOLUMETRIC_EXTINCTION = _NIGHT["fog"]["volumetric_extinction_scale"]
EXPOSURE = (_NIGHT["post_process"], _DAY["post_process"])
# The cycle's two post-process components outrank the level's own volume.
NIGHT_GRADE_PRIORITY = 10.0
DAY_GRADE_PRIORITY = 11.0


def cycle_length():
    return DAY_LENGTH_S + NIGHT_LENGTH_S


def _map_clamped(v, a, b, out_a, out_b):
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return out_a + (out_b - out_a) * t


def sun_state(clock_s):
    """What BP_DayNightCycle's Tick computes for a clock reading, in Python.

    Returns a dict: angle (0-360 over the cycle, 0-180 by day), the sun's and
    the moon's elevation in degrees, day_amount (0 night .. 1 day), the two
    lights' intensities in lux and star_brightness. The graph authors exactly
    these sums (day_night_graph.py); the probe compares the two.
    """
    clock = clock_s % cycle_length()
    angle = (_map_clamped(clock, 0.0, DAY_LENGTH_S, 0.0, 180.0)
             + _map_clamped(clock, DAY_LENGTH_S, cycle_length(), 0.0, 180.0))
    s = math.sin(math.radians(angle))
    sun_elev = SUN_MAX_ELEVATION_DEG * s
    moon_elev = -MOON_MAX_ELEVATION_DEG * s
    day = _map_clamped(sun_elev, NIGHT_BELOW_DEG, DAY_ABOVE_DEG, 0.0, 1.0)
    moon = _map_clamped(moon_elev, 0.0, MOON_FADE_DEG, 0.0, 1.0) * (1.0 - day)
    stars = _map_clamped(sun_elev, 0.0, STARS_FULL_BELOW_DEG, 0.0, 1.0)
    return {
        "clock": clock,
        "angle": angle,
        "is_day": clock < DAY_LENGTH_S,
        "sun_elevation": sun_elev,
        "moon_elevation": moon_elev,
        "day_amount": day,
        "sun_lux": SUN_LUX * day,
        "moon_lux": MOON_LUX * moon,
        "star_brightness": STAR_BRIGHTNESS * stars,
    }

# The dome is the engine's SM_SkySphere at the same scale the generator uses.
SKY_DOME_SCALE = 400.0
