"""The day/night cycle runs: it takes over the level's sky, its clock moves,
and at noon, at midnight and in twilight the sun, the moon, the stars, the
ambient light and the exposure are what world_config.sun_state() says.

Clock is written directly to jump through the cycle; each jump waits a few
frames for Tick to apply it, then compares against sun_state() for the clock
the actor reads back (Tick adds its frame time on top of the write).
"""

import math

from world import world_config as cfg
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH, STATIC_SKY_TAG

WRITABLE = [(DAY_NIGHT_BP_PATH, "Clock")]

SETTLE = 0.1


def _elevation(light):
    """Degrees above the horizon of the body a directional light stands for."""
    z = light.get_forward_vector().z
    return math.degrees(math.asin(max(-1.0, min(1.0, -z))))


def _scalar(mid, name):
    """A dynamic material's scalar (the Python name of K2_GetScalarParameterValue
    differs across engine versions, so both are tried)."""
    for fn in ("get_scalar_parameter_value", "k2_get_scalar_parameter_value"):
        if hasattr(mid, fn):
            return getattr(mid, fn)(name)
    raise AttributeError(f"no scalar getter on {mid}: "
                         f"{[n for n in dir(mid) if 'scalar' in n]}")


def _state(p, cycle):
    sky = p.get(cycle, "SkyMaterial")
    return {
        "clock": p.get(cycle, "Clock"),
        "is_day": p.get(cycle, "IsDay"),
        "day": p.get(cycle, "DayAmount"),
        "sun_lux": p.get(cycle, "Sun").get_editor_property("intensity"),
        "moon_lux": p.get(cycle, "Moon").get_editor_property("intensity"),
        "sun_elev": _elevation(p.get(cycle, "Sun")),
        "moon_elev": _elevation(p.get(cycle, "Moon")),
        "sky_light": p.get(cycle, "SkyLight").get_editor_property("intensity"),
        "grade": p.get(cycle, "DayGrade").get_editor_property("blend_weight"),
        "stars": _scalar(sky, "StarBrightness") if sky else None,
    }


def _jump(p, cycle, clock):
    p.set(cycle, "Clock", float(clock))
    yield SETTLE
    return _state(p, cycle)


def _close(a, b, tol=1e-3):
    return a is not None and abs(a - b) <= tol


def probe(p):
    import unreal
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    left = unreal.GameplayStatics.get_all_actors_with_tag(p.world(), STATIC_SKY_TAG)
    p.check("the level's static sky is gone", len(left) == 0,
            str([a.get_name() for a in left]))
    p.check("the dome has its dynamic material", p.get(cycle, "SkyMaterial") is not None)

    before = p.get(cycle, "Clock")
    yield 0.5
    after = p.get(cycle, "Clock")
    p.check("the clock runs", after > before, f"{before:.3f} -> {after:.3f}")

    noon = yield from _jump(p, cycle, cfg.DAY_LENGTH_S / 2)
    p.check("noon: it is day", noon["is_day"] and _close(noon["day"], 1.0), str(noon))
    p.check("noon: the sun is high and full, the moon is out",
            _close(noon["sun_lux"], cfg.SUN_LUX)
            and abs(noon["sun_elev"] - cfg.SUN_MAX_ELEVATION_DEG) < 1.0
            and noon["moon_lux"] == 0.0 and noon["moon_elev"] < 0, str(noon))
    p.check("noon: no stars, the day grade and ambient",
            noon["stars"] == 0.0 and _close(noon["grade"], 1.0)
            and _close(noon["sky_light"], cfg.SKY_LIGHT_INTENSITY[1]), str(noon))

    night = yield from _jump(p, cycle, cfg.DAY_LENGTH_S + cfg.NIGHT_LENGTH_S / 2)
    p.check("midnight: it is night", not night["is_day"] and night["day"] == 0.0, str(night))
    p.check("midnight: the moon is up and dim, the sun is out",
            _close(night["moon_lux"], cfg.MOON_LUX, 1e-4)
            and abs(night["moon_elev"] - cfg.MOON_MAX_ELEVATION_DEG) < 1.0
            and night["sun_lux"] == 0.0 and night["sun_elev"] < 0, str(night))
    p.check("midnight: the stars are out, the night grade and ambient",
            _close(night["stars"], cfg.STAR_BRIGHTNESS) and night["grade"] == 0.0
            and _close(night["sky_light"], cfg.SKY_LIGHT_INTENSITY[0]), str(night))

    for label, clock in (("dusk", cfg.DAY_LENGTH_S - 2.0),
                         ("dawn", cfg.DAY_LENGTH_S + cfg.NIGHT_LENGTH_S - 4.0)):
        got = yield from _jump(p, cycle, clock)
        want = cfg.sun_state(got["clock"])
        p.check(f"{label}: the Blueprint does sun_state()'s sums",
                _close(got["day"], want["day_amount"])
                and _close(got["sun_lux"], want["sun_lux"])
                and _close(got["moon_lux"], want["moon_lux"], 1e-4)
                and _close(got["stars"], want["star_brightness"])
                and abs(got["sun_elev"] - want["sun_elevation"]) < 0.5,
                f"got {got} want {want}")
