"""world_config's lengths, and what sun_state() says a cycle looks like."""

from combat.verify.common import check
from world import world_config as cfg


def run():
    check("world config: a day lasts 4 minutes", cfg.DAY_LENGTH_S == 240.0,
          f"{cfg.DAY_LENGTH_S} s")
    check("world config: a night lasts 4 minutes", cfg.NIGHT_LENGTH_S == 240.0,
          f"{cfg.NIGHT_LENGTH_S} s")
    check("world config: the clock starts in the day",
          0.0 <= cfg.START_CLOCK_S < cfg.DAY_LENGTH_S, f"{cfg.START_CLOCK_S} s")

    noon = cfg.sun_state(cfg.DAY_LENGTH_S / 2)
    midnight = cfg.sun_state(cfg.DAY_LENGTH_S + cfg.NIGHT_LENGTH_S / 2)
    check("noon: the sun is at its highest and full",
          abs(noon["sun_elevation"] - cfg.SUN_MAX_ELEVATION_DEG) < 1e-6
          and noon["sun_lux"] == cfg.SUN_LUX, str(noon))
    check("noon: no moon and no stars",
          noon["moon_lux"] == 0.0 and noon["star_brightness"] == 0.0, str(noon))
    check("midnight: the moon is at its highest and full",
          abs(midnight["moon_elevation"] - cfg.MOON_MAX_ELEVATION_DEG) < 1e-6
          and abs(midnight["moon_lux"] - cfg.MOON_LUX) < 1e-9, str(midnight))
    check("midnight: no sun, all the stars",
          midnight["sun_lux"] == 0.0
          and midnight["star_brightness"] == cfg.STAR_BRIGHTNESS, str(midnight))
    check("night light is dim: the moon under 5% of the sun",
          cfg.MOON_LUX < 0.05 * cfg.SUN_LUX, f"{cfg.MOON_LUX} vs {cfg.SUN_LUX} lux")
    inside = [cfg.sun_state(t) for t in range(1, int(cfg.cycle_length()), 5)
              if t != cfg.DAY_LENGTH_S]
    check("the sun is up exactly in the day half, the moon in the night half",
          all((s["sun_elevation"] > 0) == s["is_day"] == (s["moon_elevation"] < 0)
              for s in inside), f"{len(inside)} samples")
    check("the cycle wraps: the end of the night is the next sunrise",
          cfg.sun_state(cfg.cycle_length())["clock"] == 0.0)
