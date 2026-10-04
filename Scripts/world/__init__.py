"""world -- the world around the player: today, the day/night cycle.

Entry point: Scripts/build_day_night.py. Checks: Scripts/verify_day_night.py
(the world.verify package) and Scripts/probes/probe_day_night.py.

  world_config         THE world settings: day and night lengths, the night's
                       cold, start time, sun/moon paths, sky colours;
                       sun_state() does the Tick's sums in Python,
                       clock_to_hour() the tuning dial's
  world_tuning         world_tuning.csv: the lengths, the night's cold and the
                       item highlight the M panel's WORLD SETTINGS tab
                       saves, laid over world_config's
  paths                /Game paths, class paths, the two actor tags
  day_night_vars       BP_DayNightCycle's variables and components, named once
  sky_material         M_DayNightSky: the whole sky (gradient, glow, discs,
                       stars) in one Custom node the SkyLight captures
  star_catalogue       star_catalogue.csv: the real stars (the Yale Bright
                       Star Catalogue), and the fetcher that rewrites it
  star_map             where each star stands in the world's sky and how big
                       and bright it is drawn; the shader's sums in Python
  star_texture         T_NightSkyStars: the catalogue drawn as a texture
  day_night_blueprint  BP_DayNightCycle's components, variables, defaults
  day_night_graph      its BeginPlay (take over the level's sky) and Tick
  (the beds)           Sound/sound_world.py: three looping beds on the cycle,
                       the day's and the night's faded by DayAmount
  night_cold           the Tick's last step: the player's Temperature falls
                       at night, by NightTemperatureDropPerSecond
  item_highlight       a Tick step: the cycle's ItemHighlight onto
                       MPC_ItemGlimmer, the switch of every item's glimmer
  level_placement      tag each level's static sky, place the cycle actor
  verify/              the verifier's sections
"""
