"""The blood splatter sprite's numbers (blood_sprite.py builds it): how big a
splat is for each part of the body it came out of, the flipbook's grid and
how long it plays. Constants and one pure rule; no Blueprint authoring.

A splat is a flipbook on a flat card that blooms out of the wound and breaks
up, beside BP_BloodSplash's droplets (blood.py): the droplets are the spray
in flight, the splat is what the eye reads as "that hit". Its size is the
zone's, not the round's: a limb bleeds least, the chest more, the head most.
"""

# Across the card, in cm, by the zone the pellet struck. The pellet's zone is
# read off PelletFlew (impact.py): bHead is the head; a multiplier under 1
# (COMBAT.limb_multiplier, 0.75) is an arm or a leg; anything else, the torso.
SPLAT_LIMB_CM = 16.0
SPLAT_CHEST_CM = 26.0
SPLAT_HEAD_CM = 38.0
# The engine plane is 100 cm across at scale 1, so the spawn scale is cm / 100.
PLANE_CM = 100.0
# Off the wound toward the camera, in the card's own units (scaled with it):
# 0.35 of its width, so a splat seen from the side is not half inside the body.
SPLAT_LIFT = 35.0
# The card's component, a child of the root: the actor turns to the camera and
# the card keeps its quarter turn and its lift.
SPLAT_COMPONENT = "Splat"
SPLAT_ROOT = "Facing"

# The flipbook: GRID x GRID frames of CELL px each, in one atlas.
SPLAT_GRID = 4
SPLAT_FRAMES = SPLAT_GRID * SPLAT_GRID
SPLAT_CELL = 128
SPLAT_SEED = 23
# The card shows one frame of the flipbook, its fullest (the last of the bloom,
# before the break-up: the unit tests hold it to the largest coverage), for
# this many seconds, then the actor is gone (SetLifeSpan). The bloom and the
# break-up frames are not played: they read as blood hanging in the air.
SPLAT_LIFETIME = 0.35
SPLAT_HOLD_FRAME = 8
# The share of the life spent blooming out; the rest breaks it up to nothing.
SPLAT_GROW = 0.55
# The texture is a shade (thick blood darker) times this, the M_Blood colour
# lifted a little: a flat card lit face-on reads darker than a droplet's
# highlight does.
SPLAT_COLOUR_GAIN = 1.25
SPLAT_ROUGHNESS = 0.3


def splat_scale(head, worth):
    """The card's spawn scale for one pellet: what the graph in impact.py
    picks with two SelectFloats (bHead first, then Worth under 1)."""
    if head:
        return SPLAT_HEAD_CM / PLANE_CM
    if worth < 1.0:
        return SPLAT_LIMB_CM / PLANE_CM
    return SPLAT_CHEST_CM / PLANE_CM
