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
from world.world_tuning import read_table as _read_tuning

_DAY = get_preset("day")
_NIGHT = get_preset("night")

# ─── The clock ───────────────────────────────────────────────────────────────
# One cycle is a day followed by a night. The clock runs from 0 (sunrise) to
# DAY_LENGTH_S (sunset) to DAY_LENGTH_S + NIGHT_LENGTH_S (the next sunrise).
# 4 + 4 minutes for testing; a real day wants something like 20 + 10.
# world_tuning.csv (saved by the M panel's WORLD SETTINGS tab) overrides both.
_TUNED = _read_tuning()
DAY_LENGTH_S = float(_TUNED.get("day_length_s", 240.0))
NIGHT_LENGTH_S = float(_TUNED.get("night_length_s", 240.0))
# The night is cold: the player's Temperature (survival's 0-100 bar) falls by
# this many points a second at full night, scaled by 1 - DayAmount through
# twilight (world/night_cold.py). Slow: 0.1 takes 24 points off in a 4-minute
# night. world_tuning.csv overrides it too.
NIGHT_TEMPERATURE_DROP_PER_S = float(_TUNED.get("night_temperature_drop_per_s", 0.1))

# Whether an item lying on the ground glimmers: 1 on, 0 off (the cycle's
# ItemHighlight, which its Tick writes to the glimmer's material collection:
# world/item_highlight.py). world_tuning.csv overrides it too.
ITEM_HIGHLIGHT = float(_TUNED.get("item_highlight", 1.0))
# Where a level starts. RANDOM_START (BP_DayNightCycle.RandomStart, Instance
# Editable) has BeginPlay pick a clock anywhere in the cycle instead; with it
# off, START_CLOCK_S is a little after sunrise, so the first thing the player
# sees is the sun coming up rather than the dark.
RANDOM_START = True
START_CLOCK_S = 20.0

# ─── Hours: how the WORLD SETTINGS tab shows the clock ─────────────────────────
# However long the day and the night last, each is 12 hours on the tab's
# 24-hour dial: sunrise is SUNRISE_HOUR, sunset 12 hours later.
SUNRISE_HOUR = 6.0
HALF_HOURS = 12.0

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
# The moon's disc in the shader: cos of the angle from its centre where the
# disc's edge starts and where it is full (about 3.2 degrees across).
MOON_DISC_COS = (0.99955, 0.99965)
STAR_BRIGHTNESS = _NIGHT["sky_dome"]["star_brightness"]

# ─── The stars (T_NightSkyStars, drawn from star_catalogue.csv) ──────────────
# The real sky as seen from STAR_LATITUDE_DEG north, at the moment the stars of
# right ascension STAR_SIDEREAL_HOUR stand due south: a winter evening, Orion
# to the south-east, the Plough and the Pole Star in the north. The stars do
# not turn with the clock.
STAR_LATITUDE_DEG = 45.0
STAR_SIDEREAL_HOUR = 4.0
STAR_MAP_SIZE = (4096, 2048)        # texels; one is 0.088 degrees of sky
# A star is a Gaussian dot of this radius (sigma), small beside the moon. The
# night's exposure burns every star it shows to white, so the bright ones are
# told apart by size: a star brighter than STAR_SIZE_MAG grows by
# STAR_SIZE_GROWTH a magnitude, up to STAR_SIZE_MAX times (Sirius).
STAR_SIZE_DEG = 0.05
STAR_SIZE_MAG = 3.0
STAR_SIZE_GROWTH = 0.3
STAR_SIZE_MAX = 2.2
# Brightness: full at STAR_FULL_MAG, falling by 10^(-0.4 x STAR_CONTRAST) a
# magnitude down to STAR_MAX_MAG, the faintest star drawn (6.5 is the naked
# eye's limit under a dark sky).
STAR_FULL_MAG = 0.5
STAR_MAX_MAG = 6.5
STAR_CONTRAST = 0.9
STAR_COLOR_BLUE = (0.70, 0.82, 1.0)       # B-V -0.3: Rigel, Spica
STAR_COLOR_WHITE = (1.0, 1.0, 1.0)        # B-V 0.6: the sun's own colour
STAR_COLOR_ORANGE = (1.0, 0.72, 0.45)     # B-V 1.9: Betelgeuse, Antares

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


def clock_to_hour(clock_s, day_s=None, night_s=None):
    """The hour (0-24) a clock reading shows on the tab's dial. The HUD's
    graph (graphics_menu/world_tune_tick.py) does the same sums."""
    day_s, night_s = day_s or DAY_LENGTH_S, night_s or NIGHT_LENGTH_S
    phase = (_map_clamped(clock_s, 0.0, day_s, 0.0, HALF_HOURS)
             + _map_clamped(clock_s, day_s, day_s + night_s, 0.0, HALF_HOURS))
    return (phase + SUNRISE_HOUR) % 24.0


def hour_to_clock(hour, day_s=None, night_s=None):
    """The clock reading for an hour on the dial (any hour: it wraps)."""
    day_s, night_s = day_s or DAY_LENGTH_S, night_s or NIGHT_LENGTH_S
    phase = (hour - SUNRISE_HOUR + 24.0) % 24.0
    return (_map_clamped(phase, 0.0, HALF_HOURS, 0.0, day_s)
            + _map_clamped(phase, HALF_HOURS, 24.0, 0.0, night_s))


def sun_state(clock_s):
    """What BP_DayNightCycle's Tick computes for a clock reading, in Python.

    Returns a dict: angle (0-360 over the cycle, 0-180 by day), the sun's and
    the moon's elevation in degrees, day_amount (0 night .. 1 day), the two
    lights' intensities in lux, star_brightness and night_cold_per_s (how fast
    the player's Temperature falls). The graph authors exactly
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
        "night_cold_per_s": NIGHT_TEMPERATURE_DROP_PER_S * (1.0 - day),
    }

# The dome is the engine's SM_SkySphere at the same scale the generator uses.
SKY_DOME_SCALE = 400.0
