# The world: day and night

`Scripts/build_day_night.py` builds `T_NightSkyStars`, `M_DayNightSky` and `BP_DayNightCycle`
(all under `/Game/World`) and puts one cycle actor into every generated level.
`Scripts/verify_day_night.py` checks it, and `Scripts/probes/probe_day_night.py`,
`probe_night_sky.py` and `probe_night_cold.py` run it in a game. The module map is in `__init__.py`.

```bash
python3 Scripts/dev/uepy.py Scripts/build_day_night.py Scripts/verify_day_night.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_day_night.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_night_cold.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_night_sky.py
OW_SKY_SHOTS=1 python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_night_sky.py
```

The last one saves pictures of the midnight sky (towards the moon, the Pole Star and Orion)
to `Saved/Screenshots/MacEditor`: the only way to see the stars without playing.

## Settings: `world_config.py`

- **The world config.** `DAY_LENGTH_S` and `NIGHT_LENGTH_S` are each 240 s for testing, unless
  `world_tuning.csv` (saved by the M panel's WORLD SETTINGS tab) says otherwise. Change a
  number and re-run the builder.
- **The night's cold:** `NIGHT_TEMPERATURE_DROP_PER_S` (0.1, or `world_tuning.csv`'s) is how
  many points of the player's Temperature a second of full night takes. It is the actor's
  `NightTemperatureDropPerSecond`. See "The night is cold" below.
- **The item highlight:** `ITEM_HIGHLIGHT` (1 on, 0 off; or `world_tuning.csv`'s) is whether
  an item lying on the ground glimmers. It is the actor's `ItemHighlight`. See "The item
  highlight" below.
- **A level starts at a random time of day:** with `RANDOM_START` (the actor's `RandomStart`),
  BeginPlay sets `Clock` to `RandomFloatInRange(0, day + night)`. With it off, `Clock`'s default
  `START_CLOCK_S` (20 s, just after sunrise) is where it starts.
- The two lengths, `Clock`, the night's cold, the item highlight and `RandomStart` are also Instance Editable on the placed actor, so
  one level can differ.
- **The time of day can be set in a game** from the WORLD SETTINGS tab, on a 24-hour dial
  (`clock_to_hour`: sunrise 06:00, sunset 18:00). See `Scripts/graphics_menu/CLAUDE.md`.
- **The look multipliers** (`SunScale`, `MoonScale`, `StarScale`, `AmbientScale`, `FogScale`,
  `SunDiscScale`, `MoonDiscScale`; `day_night_blueprint.LOOK_SCALE_VARS`) are 1 as built. Tick
  multiplies the sun's and the moon's light, the stars, the sky light, the fog's density and
  the two discs by them. Only the M panel's GRAPHICS SETTINGS tab writes them
  (`graphics_menu/gfx_tuner_sky.py`); `sun_state()` is the world at 1.
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

## The forest's sound (`Sound/sound_world.py`)

- **Three looping beds on the cycle actor:** `BedDay` (birds), `BedNight` (crickets and owls)
  and `BedWind`, each an AudioComponent playing a stereo wave of `/Game/Audio/Beds`
  (`Sound/sound_world.py`, `BEDS`; which recordings is `Scripts/Sound`'s selection). Not
  spatialised: where the actor stands does not matter.
- **Tick fades the day's into the night's by `DayAmount`:** `BedDay`'s volume is
  `DayAmount`, `BedNight`'s `1 - DayAmount`; the wind plays on, **at volume 0 by default**
  (its SOUND SETTINGS row: the recording is not a good match, and is kept only so the
  bed is there to be replaced). A bed at zero goes on
  playing (the wave's virtualization mode), so it keeps its place.
- **How loud** is each bed's row on the SOUND SETTINGS tab (`day birds`, `night`, `wind`),
  which the component's volume multiplies.
- **Checks:** `world/verify/ambience.py`; `probe_ambience.py` jumps the clock to noon and to
  midnight and reads the two volumes.
- **Run the weapons build first:** it imports the waves. It needs a play session: the
  levels against the guns, and whether dusk's cross-fade is too long.

## The stars are the real ones (`star_catalogue.py`, `star_map.py`, `star_texture.py`)

- **The layout is the real sky.** `star_catalogue.csv` is the Yale Bright Star Catalogue
  (9,096 stars: position, magnitude, colour index; free to use). It is committed, so a build
  needs no network. `python3 Scripts/fetch_star_catalogue.py` rewrites it from the CDS's copy.
- **The texture:** `T_NightSkyStars` is an equirectangular map of the whole celestial sphere
  (u is right ascension, v runs down from the north pole), drawn from the CSV on every build.
  It is uncompressed, without mips and never streamed, because a star is a texel or two.
- **The frame:** the sky is the one seen from `STAR_LATITUDE_DEG` (45° north) with the stars of
  right ascension `STAR_SIDEREAL_HOUR` (4 h) due south: Orion in the south-east, the Pleiades
  overhead, the Pole Star in the north. South is where the sun and the moon culminate. The
  material's `StarUV` Custom node turns the view ray into the map's coordinate, with the frame
  baked into its code; `star_map.direction_uv()` does the same sums, and the verifier compares.
- **The stars stand still.** They do not turn about the pole as the night goes: that needs a
  rotation parameter driven by Tick.
- **Size:** a star is a Gaussian dot of `STAR_SIZE_DEG` (0.05°, about 0.2° across; the moon is
  3.2°). One brighter than magnitude 3 is drawn bigger, up to 2.2 times for Sirius. The
  verifier holds the brightest under a sixth of the moon's width.
- **Brightness** falls with magnitude (`STAR_CONTRAST`), down to `STAR_MAX_MAG` (6.5). The
  night's exposure burns every star it shows to white, so it is the size that tells a bright
  star from a faint one, and the faintest ones are lost in the sky's own glow.
- **The moon hides the stars behind its disc.**
- **The level's static rig** (`M_NightSky_Starfield`, what the editor viewport shows) still
  tiles the engine's `T_Sky_Stars`. The cycle destroys it at BeginPlay, so a game never draws it.

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

## The item highlight (`item_highlight.py`)

- **The glimmer is combat's, the switch is the world's.** Every item carries a sprite that
  shows while it lies on the ground, drawn with a material multiplied by
  `MPC_ItemGlimmer.Highlight` (`combat/glimmer.py`, `Scripts/combat/CLAUDE.md`). The cycle's
  Tick writes that scalar from `ItemHighlight` every frame, which is what makes the WORLD
  SETTINGS row live: one float, and no item is told.
- **The step sits before the night's cold** in the Tick's chain: the cold stops at a level
  with no player, and nothing after it would run.
- **`build_weapons_and_combat.py` makes the collection** and runs before this build. A level
  without a cycle keeps the collection's own default: on.
- `probes/probe_item_glimmer.py` switches it from the tab in a game.

## Traps

- **Compile before `_apply_defaults`.** A freshly declared variable isn't on the CDO until the
  class compiles, and `set_editor_property` fails with "Failed to find property".
- **`MaterialInstanceDynamic`'s scalar getter** is `get_scalar_parameter_value` in Python, not
  `k2_…`.
- **`MaterialEditingLibrary.delete_all_material_expressions` deletes about half** of them per
  call. A parameter left behind keeps its old default, and of two with one name the old one
  won: the rebuilt material went on sampling the old star texture. Loop until
  `get_num_material_expressions` is 0. The verifier counts the expressions.
- **Check that a Custom-node material compiled:** `MEL.get_statistics(mat)`'s
  `num_pixel_shader_instructions` is 0 when it didn't. The verifier checks it.

## Still needs a play session

- **The look:** the sky colours, sunset glow, disc sizes and daytime exposure were set by
  numbers, not by eye, because `-nullrhi` can't render them. Tune them in `world_config.py`.
- **The stars** were judged from 1280x720 pictures only: their size and how many show at the
  night's exposure want a look on the real screen (`STAR_SIZE_DEG`, `STAR_CONTRAST`, or the
  GRAPHICS SETTINGS tab's stars row).
- **Twilight is short** (about 15 s of a 4-minute day), because the sun crosses the horizon
  fast. A longer day stretches it.
