"""The sight camera's seat: how the camera goes from the boom onto the gun's
sights, when it may turn onto their line, and the names it is kept under. Constants only; the graph is
weapon_component/seat.py, read by sights.py, ads.py and carry.py, and by the
HUD's reticle (graphics_menu/reticle.py).
"""

import math

# The camera turns onto the gun's sight line only once the gun is up: the
# line within this many degrees of where the player is looking (the control
# rotation). A gun is carried lowered, and the sights key raises it with the
# ready pose's own blend; a camera that took the gun's line through that
# raise looked down at the hand and then swung up onto the target. Looking
# where the player looks until the gun is nearly there, it keeps the target
# in the middle and the sights rise to it. The camera's travel does not wait:
# it leaves for the eye point on the key (weapon_component/seat.py).
# Wide enough that the turn starts while the gun is still settling (what it
# takes from the gun is this angle times a look that has only begun), narrow
# enough that a lowered gun is never inside it.
SIGHT_SEAT_DEG = 10.0
SIGHT_SEAT_COS = math.cos(math.radians(SIGHT_SEAT_DEG))

# BP_WeaponComponent's variables. SightSeated is the latch: the sights key is
# down and the gun has come up since it went down. It stays set until the key
# is let go, so a reload with the sights up keeps the camera on the gun.
# SightSeat is how far the camera has travelled from the boom to the sights,
# eased toward the sights key (SightAiming): one motion, from the key.
# SightLook is how far it has turned from the control rotation onto the gun's
# sight line, eased toward the latch.
SEATED_VAR = "SightSeated"
SEAT_VAR = "SightSeat"
LOOK_VAR = "SightLook"
# A probe's stand-in for the sights key held: no key can be injected into a
# headless game. False in every real game.
SIGHTS_FORCED_VAR = "SightsForced"

# On BP_WeaponItem: it has sights to aim down, which is to say it is a gun.
# Only the guns' rows set it (weapon_items.py), so the knife, the axe, the
# matches, wood, food and any item added later aim over the shoulder
# whichever key is held: nothing has sights unless it says so.
HAS_SIGHTS_VAR = "HasSights"

# The gun stays up, and the body keeps the aim (SightBlend: the upper body's
# pitch, the sway), while the camera is still this far onto the gun. Letting
# the key go lowers the gun and levels the body, and a camera still easing
# home off a gun on its way down would dip with it.
SEAT_HOLD = 0.02

# The HUD's crosshair is not drawn past this much seat, outside debug mode:
# the gun's own sights are on the middle of the view by then.
RETICLE_HIDE_SEAT = 0.9

# The player's own head is hidden past this much seat (head_hide.py). The eye
# point of a gun at the shoulder is inside or beside the head, which then
# stands in the sight picture. The camera comes at the gun from behind, over
# the shoulder, so until the last of the travel the head is simply the back of
# the body's head, in front of the camera where it always is; it goes just
# before the camera reaches it, so the body is not seen headless from behind.
HEAD_HIDE_SEAT = 0.8
