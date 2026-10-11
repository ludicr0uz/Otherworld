"""The pick-up clip's numbers (weapon_component/pickup_clip.py): Quaternius
UAL2's Farm_Harvest, the reach down to the ground for an item taken.
Constants only.

Measured off the clip on the adventurer (2.5 s): the right hand stands at
92 cm, is on its way down by 0.2 s, reaches its lowest, 26-33 cm off the
floor, between 0.6 and 1.2 s, and is back up by 2.2 s. The take is on the
press, so the clip starts part way in, where the hand already drops, and
the hand is down within half a second of it.
"""

PICKUP_CLIP_START_S = 0.2   # where the play starts: the hand already on its way down
PICKUP_ANIM_BLEND_S = 0.15  # the blend in and out, over the pose the slot held
