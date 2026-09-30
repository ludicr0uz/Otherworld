"""world -- the world around the player: today, the day/night cycle.

Entry point: Scripts/build_day_night.py. Checks: Scripts/verify_day_night.py
(the world.verify package) and Scripts/probes/probe_day_night.py.

  world_config         THE world settings: day and night lengths, start
                       time, sun/moon paths, sky colours; sun_state() does the
                       Tick's sums in Python
  paths                /Game paths, class paths, the two actor tags
  sky_material         M_DayNightSky: the whole sky (gradient, glow, discs,
                       stars) in one Custom node the SkyLight captures
  day_night_blueprint  BP_DayNightCycle's components, variables, defaults
  day_night_graph      its BeginPlay (take over the level's sky) and Tick
  level_placement      tag each level's static sky, place the cycle actor
  verify/              the verifier's sections
"""
