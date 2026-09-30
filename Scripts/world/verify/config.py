"""world_config's lengths, and what sun_state() says a cycle looks like."""

from combat.verify.common import check
from world import world_config as cfg
from world.world_tuning import CSV_PATH, read_table


def run():
    tuned = read_table()
    check("world config: a day lasts world_tuning.csv's length (else 4 minutes)",
          cfg.DAY_LENGTH_S == tuned.get("day_length_s", 240.0),
          f"{cfg.DAY_LENGTH_S} s, {CSV_PATH}: {tuned}")
    check("world config: a night lasts world_tuning.csv's length (else 4 minutes)",
          cfg.NIGHT_LENGTH_S == tuned.get("night_length_s", 240.0),
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
    hours = [cfg.clock_to_hour(cfg.hour_to_clock(h)) for h in (0.0, 6.0, 12.0, 18.0, 23.5)]
    check("the tab's dial: sunrise is 06:00, sunset 18:00, and an hour round-trips",
          cfg.hour_to_clock(cfg.SUNRISE_HOUR) == 0.0
          and cfg.hour_to_clock(cfg.SUNRISE_HOUR + 12.0) == cfg.DAY_LENGTH_S
          and all(abs(a - b) < 1e-9 for a, b in zip(hours, (0.0, 6.0, 12.0, 18.0, 23.5))),
          str(hours))
    check("the cycle wraps: the end of the night is the next sunrise",
          cfg.sun_state(cfg.cycle_length())["clock"] == 0.0)
