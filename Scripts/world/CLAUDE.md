# The world: day and night

`Scripts/build_day_night.py` builds `M_DayNightSky` and `BP_DayNightCycle` (both under
`/Game/World`) and puts one cycle actor into every generated level.
`Scripts/verify_day_night.py` checks it, and `Scripts/probes/probe_day_night.py` and
`probe_night_cold.py` run it in a game. The module map is in `__init__.py`.

```bash
python3 Scripts/dev/uepy.py Scripts/build_day_night.py Scripts/verify_day_night.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_day_night.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_night_cold.py
```

## Settings: `world_config.py`

- **The world config.** `DAY_LENGTH_S` and `NIGHT_LENGTH_S` are each 240 s for testing, unless
  `world_tuning.csv` (saved by the M panel's WORLD TUNING tab, [O]) says otherwise. Change a
  number and re-run the builder.
- **The night's cold:** `NIGHT_TEMPERATURE_DROP_PER_S` (0.1, or `world_tuning.csv`'s) is how
  many points of the player's Temperature a second of full night takes. It is the actor's
  `NightTemperatureDropPerSecond`. See "The night is cold" below.
- **A level starts at a random time of day:** with `RANDOM_START` (the actor's `RandomStart`),
  BeginPlay sets `Clock` to `RandomFloatInRange(0, day + night)`. With it off, `Clock`'s default
  `START_CLOCK_S` (20 s, just after sunrise) is where it starts.
- The two lengths, `Clock`, the night's cold and `RandomStart` are also Instance Editable on the placed actor, so
  one level can differ.
- **The time of day can be set in a game** from the WORLD TUNING tab, on a 24-hour dial
  (`clock_to_hour`: sunrise 06:00, sunset 18:00). See `Scripts/graphics_menu/CLAUDE.md`.
- The night values (moon 0.12 lux, sky light 3.0, fog, exposure, star brightness) come from
  `forest_generator/lighting.py`'s night preset, and the day values from its day preset.
- `sun_state(clock)` does the same sums as the Tick graph. The probe compares the two, so keep
  them in step.

## Design

- **The clock:** 0 is sunrise, `DAY_LENGTH_S` is sunset, and the full cycle wraps back to
  sunrise. The sun rises at `SUNRISE_YAW_DEG` and peaks at 60°. The moon takes the same path
  through the night and peaks at 45°. `IsDay` is `Clock < DayLengthSeconds`. `DayAmount` (0–1)
  follows the sun's elevation from -6° to +8°, and everything else blends by it.
- **The cycle owns the whole sky rig:**
  - a Movable sun and moon (atmosphere lights 0 and 1);
  - a real-time SkyLight;
  - the dome;
  - the height fog;
  - two unbound post-process grades that outrank the level's volume: NightGrade is always on,
    and DayGrade is weighted by DayAmount.

  The level's generated rig stays as generated, because its verifier checks it. The builder
  only **tags** it `OW_StaticSky` (the directional light, sky light, fog, clouds and the
  SM_SkySphere dome). The cycle destroys everything with that tag at BeginPlay. A level
  without a cycle still plays at night.
- **The sky is one opaque, unlit, IsSky dome** whose material draws everything: the day
  gradient, the night colour, the sunset glow, the sun and moon discs and the stars. It
  doesn't hand over to the SkyAtmosphere, because an opaque dome can't cross-fade with it and
  would pop at dusk. The SkyLight captures the dome, so the ambient light follows the sky.
- **`import_<Level>.py` rebuilds a level from scratch.** Re-run `build_day_night.py` after it,
  as with `place_forage.py`.

## The night is cold (`night_cold.py`)

- **The Tick's last step** lowers the player's `Temperature` (`BP_SurvivalComponent`) by
  `NightTemperatureDropPerSecond × (1 − DayAmount) × dt`, floored at 0. Scaling by
  `1 − DayAmount` brings the cold in through dusk and eases it through dawn;
  `sun_state()`'s `night_cold_per_s` is the same sum.
- **The cycle writes the survival component,** not the other way round: the cold is the
  world's, and `build_survival.py` runs before `build_day_night.py` (the cast node needs the
  class loaded). So `world` imports `survival.paths`. A level without a cycle has no cold.
- **Only a campfire warms the player** (`survival/campfire.py`, lit with the matches), and
  nothing reads a low Temperature yet. A saved profile carries the bar into the next game.
- **The probe raises the rate** to 20 a second for its run: a headless game's time moves too
  little for 0.1 to show.

## Traps

- **Compile before `_apply_defaults`.** A freshly declared variable isn't on the CDO until the
  class compiles, and `set_editor_property` fails with "Failed to find property".
- **`MaterialInstanceDynamic`'s scalar getter** is `get_scalar_parameter_value` in Python, not
  `k2_…`.
- **Check that a Custom-node material compiled:** `MEL.get_statistics(mat)`'s
  `num_pixel_shader_instructions` is 0 when it didn't. The verifier checks it.

## Still needs a play session

- **The look:** the sky colours, sunset glow, disc sizes and daytime exposure were set by
  numbers, not by eye, because `-nullrhi` can't render them. Tune them in `world_config.py`.
- **Twilight is short** (about 15 s of a 4-minute day), because the sun crosses the horizon
  fast. A longer day stretches it.
