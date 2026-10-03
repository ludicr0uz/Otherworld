"""The headshot mark's numbers: the weapon component stamps the time of a
round or a thrown blade that struck a head (weapon_component/headshot.py),
and the HUD draws an X round the reticle for a moment after it
(graphics_menu/hit_marker.py).
"""

HEADSHOT_TIME_VAR = "HeadshotTime"
# Game time starts at 0, so a stamp of 0 would read as a headshot at the
# start of every level. Far enough back that it never does.
HEADSHOT_NEVER = -1000.0
HEADSHOT_MARK_SECONDS = 0.35    # how long the X stays up
