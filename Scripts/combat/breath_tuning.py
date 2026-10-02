"""Holding the breath down the sights: the key, how long a breath lasts, how
much it steadies the sway and what running out of it costs. Constants only;
the graph is weapon_component/breath.py, and the sway it scales sway.py.
"""

# The key, rebindable like the others (tuning.BIND_VARS lists it last).
# Not LeftShift, the hold breath key of many shooters: here it sprints, and
# a sprint started down the sights would drop them.
HOLD_BREATH_KEY = "LeftAlt"

# A full breath is held this long, then the player is winded.
BREATH_HOLD_S = 5.0
# Seconds to refill an empty breath. Held for part of a breath, what is left
# can be held again at once; winded, not until it is full again.
BREATH_RECOVER_S = 5.0
# The sway's width is multiplied by these: holding the breath all but stills
# it, and being winded shakes it harder than at rest until the breath is
# back.
BREATH_SWAY_SCALE = 0.15
BREATH_WINDED_SCALE = 1.5
# How fast the width eases to the scale it is going to (FInterpTo's speed):
# a jump in the width is a jump in the view, so it eases over ~0.5 s.
BREATH_EASE_SPEED = 4.0

# The component's variables: the breath left (seconds), the breath held this
# frame, winded (run out, and not yet full again), the scale the sway's
# width is multiplied by now, and the probes' stand-in for the key.
BREATH_VAR = "Breath"
BREATH_HELD_VAR = "BreathHeld"
WINDED_VAR = "Winded"
BREATH_SCALE_VAR = "BreathScale"
BREATH_FORCED_VAR = "BreathForced"


def breath_target(held, winded):
    """The sway scale the width eases to."""
    return BREATH_SWAY_SCALE if held else BREATH_WINDED_SCALE if winded else 1.0


def breath_step(breath, winded, key, sighted, dt):
    """One frame of the graph in Python: (breath, winded, held)."""
    held = key and sighted and not winded
    rate = -1.0 if held else BREATH_HOLD_S / BREATH_RECOVER_S
    breath = min(max(breath + dt * rate, 0.0), BREATH_HOLD_S)
    winded = breath <= 0.0 or (winded and breath < BREATH_HOLD_S)
    return breath, winded, held
