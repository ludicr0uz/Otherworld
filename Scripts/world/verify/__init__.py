"""world.verify -- reads the saved day/night assets back and checks them.

Run through Scripts/verify_day_night.py, which calls each module's run() in
SECTIONS order, on combat.verify.common's check() ledger.

  config      world_config's numbers and sun_state()'s shape of a day
  sky         M_DayNightSky: flags, parameters, a shader that compiled
  stars       the star catalogue, the sky's frame, the stars' size beside the
              moon, T_NightSkyStars
  blueprint   BP_DayNightCycle: defaults, components, the graph's key nodes
  levels      what build_day_night.py put in each generated level
"""

SECTIONS = ("config", "sky", "stars", "blueprint", "levels")
