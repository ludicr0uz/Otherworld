"""
lighting.py — Time-of-day lighting presets for generated forest levels.

Each preset is a plain dict so it can be JSON-embedded straight into the
auto-generated Unreal Python import/verify scripts.

Units follow Unreal conventions:
  * DirectionalLight intensity  → lux
  * SkyLight intensity          → intensity scale for the real-time capture
  * Colors                      → sRGB 0-255 for lights, linear 0-1 for materials
"""

STARFIELD_MATERIAL_PATH = "/Game/Forest/Materials/M_NightSky_Starfield"
STARS_TEXTURE_PATH = "/Engine/EngineSky/T_Sky_Stars.T_Sky_Stars"
SIMPLE_SKY_DOME_PATH = "/Engine/EngineSky/M_SimpleSkyDome.M_SimpleSkyDome"

# How far the directional light draws real-time (cascaded) shadows. The engine
# default is 400 m, and every tree's masked leaves are drawn again into every
# cascade over that range -- the canopy overhead most of all. 100 m keeps the
# shadows that read on screen; the scalability ShadowQuality level then scales
# it (r.Shadow.DistanceScale: 0.6 Low, 0.7 Medium, 1.0 High/Ultra), and past
# it High/Ultra fall back to cheap distance-field shadows.
SHADOW_DISTANCE_CM = 10000.0


TIME_OF_DAY_PRESETS = {
    # ── Bright overhead daylight ──────────────────────────────────────────
    "day": {
        "key": "day",
        "label": "Daytime — bright sun, blue sky, volumetric clouds",
        "sun": {
            "enabled": True,
            "label_suffix": "Sun",
            "intensity": 6.0,          # lux
            "color": [255, 248, 235],  # warm white sunlight
            "pitch": -50.0,            # high sun
            "yaw": -30.0,
            "cast_shadows": True,
            "shadow_distance_cm": SHADOW_DISTANCE_CM,
        },
        "sky_light": {
            "intensity": 1.2,
            "real_time_capture": True,
        },
        "sky_dome": {
            "enabled": True,
            "material": SIMPLE_SKY_DOME_PATH,
            "build_starfield": False,
        },
        "volumetric_cloud": {
            "enabled": True,
        },
        "fog": {
            "density": 0.02,
            "inscattering_color": [0.45, 0.55, 0.65],
            "enable_volumetric": True,
            "volumetric_extinction_scale": 1.0,
        },
        "post_process": {
            "auto_exposure_min_brightness": 0.03,
            "auto_exposure_max_brightness": 2.0,
            "auto_exposure_bias": 0.5,
        },
    },

    # ── Starlit night: the starry sky itself is the light source ──────────
    "night": {
        "key": "night",
        "label": "Night — starry sky as the only light source, low luminosity",
        "sun": {
            # A faint moon/starlight directional light: just enough to give
            # trees a readable silhouette and soft directional shadows.
            "enabled": True,
            "label_suffix": "Moon",
            "intensity": 0.12,         # lux — ~1/50th of daylight
            "color": [170, 195, 255],  # cool moonlight blue
            "pitch": -32.0,            # low in the sky
            "yaw": 120.0,
            "cast_shadows": True,
            "shadow_distance_cm": SHADOW_DISTANCE_CM,
        },
        "sky_light": {
            # Real-time capture picks up the emissive starfield dome (it is
            # tagged IsSky), so the stars themselves supply the dim ambient.
            "intensity": 3.0,
            "real_time_capture": True,
        },
        "sky_dome": {
            "enabled": True,
            "material": STARFIELD_MATERIAL_PATH,
            "build_starfield": True,
            "star_brightness": 2.5,
            # Deep blue night base so the sky is never pure black.
            "night_sky_color": [0.004, 0.008, 0.022, 1.0],
            "star_tiling": [2.0, 1.0],
        },
        "volumetric_cloud": {
            # Clear sky — clouds would occlude the stars that light the level.
            "enabled": False,
        },
        "fog": {
            "density": 0.035,
            "inscattering_color": [0.015, 0.025, 0.055],
            "enable_volumetric": True,
            "volumetric_extinction_scale": 0.6,
        },
        "post_process": {
            # Let the eye adapt much further down so a dim scene stays readable
            # without washing out into fake daylight.
            "auto_exposure_min_brightness": 0.004,
            "auto_exposure_max_brightness": 0.6,
            "auto_exposure_bias": 1.6,
        },
    },
}


def get_preset(name: str) -> dict:
    """Return the lighting preset for ``name`` (``day`` or ``night``)."""
    try:
        return TIME_OF_DAY_PRESETS[name]
    except KeyError:
        valid = ", ".join(sorted(TIME_OF_DAY_PRESETS))
        raise ValueError(f"Unknown time of day '{name}' (valid: {valid})") from None
