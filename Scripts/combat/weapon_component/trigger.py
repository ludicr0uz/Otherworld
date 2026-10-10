"""The trigger's input (I1): the fire key is an Enhanced Input action, not a
key the Tick polls.

    IA_Fire Started --> OtherworldCharacter --> the native base's FireInput
        FireHeld = true                        (C++; false on the release)
        OnFirePressed  --> FirePressedAt = the world's time     (this graph)

    Tick: tap  = FirePressedAt == the world's time now, OR FireForced
          held = FireHeld

The event stamps the frame rather than setting a flag the Tick clears: input
is dealt with before physics and the Tick runs after it, in one frame, and
the world's time does not move inside a frame. So the tap is true for the
whole of the Tick that follows the press and for no other, on every path
through it, the dead one included, as WasInputKeyJustPressed was; a flag
would wait out a Tick that returned early and fire on the next one.

The key itself is the mapping context's (combat/input_assets.py), so the
component has no KeyFire variable any more.
"""

from combat.weapon_component import vars as WV
from uebp.g import _G
from uebp.graph import _palette, out, then
from uebp.nodes.math import FN_EQ_FF, FN_OR
from uebp.nodes.system import FN_TIME_SECONDS
from uebp.nodes.weapon import FIRE_HELD, NODE_EVENT_FIRE_PRESSED

# The polled key's variable, taken off a component built before I1.
RETIRED_VARS = ("KeyFire",)


def author_fire_pressed(ed):
    """OnFirePressed, the native base's event: stamp the press."""
    g = _G(ed)
    event = g.keep(_palette(ed, NODE_EVENT_FIRE_PRESSED))
    g.put(WV.FirePressedAt, out(g.call(FN_TIME_SECONDS)), [then(event)])
    ed.add_comment_to_nodes(
        "OnFirePressed (trigger.py): the local player's fire action went down "
        "(IA_Fire, bound by OtherworldCharacter; not told while paused). Stamped "
        "with the world's time, which the Tick later in this frame compares: "
        "its tap.", g.made)


def _author_trigger(ed):
    """``(tap, holding)``: the trigger pressed this frame (or the probe's
    stand-in), and the trigger down."""
    g = _G(ed)
    now = g.call(FN_EQ_FF, A=g.get(WV.FirePressedAt), B=out(g.call(FN_TIME_SECONDS)))
    tapped = g.call(FN_OR, A=out(now), B=g.get(WV.FireForced))
    return out(tapped), g.get(FIRE_HELD)
