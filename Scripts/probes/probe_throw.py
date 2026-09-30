"""The throw: holding the key draws the arc, letting go throws what is held,
and it comes down where the arc said, as an item E can pick up.

No key can be injected into a headless game, so the probe holds the throw key
by writing ThrowKeyForced, which throw.py ORs with the key and which nothing
else writes (verify/throw.py checks the key poll itself). The view is levelled
first so the throw goes out across the ground in front of the player.
"""

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.throw_arc import ARC_COMPONENT
from combat.weapon_component.throw import (
    THROWN_VAR, THROW_AIMING_VAR, THROW_ARC_VAR, THROW_FORCED_VAR,
)

WRITABLE = [(WEAPON_COMP_BP_PATH, THROW_FORCED_VAR)]

LANDS_WITHIN_CM = 80.0     # the disc to where it rests: back-off + lift + a sub-step


def _dots(p, wc):
    arc = p.get(wc, THROW_ARC_VAR)
    return arc.get_editor_property(ARC_COMPONENT) if arc else None


def _dist(a, b):
    return (a - b).length()


def probe(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    yield lambda: p.get(wc, "Held") is not None
    item = p.get(wc, "Held")
    carried = len(p.get(wc, "Inventory"))

    pc = p.controller()
    view = pc.get_control_rotation()
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=view.yaw))
    yield 0.05

    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05
    dots = _dots(p, wc)
    count = dots.get_instance_count() if dots else 0
    p.check("holding the key draws the arc as dots", count > 5, f"{count} dots")
    if count < 2:
        p.set(wc, THROW_FORCED_VAR, False)
        return
    first = dots.get_instance_transform(0, True).translation
    mark = dots.get_instance_transform(count - 1, True).translation
    here = player.get_actor_location()
    p.check("...starting just in front of the player",
            _dist(first, here) < 120.0, f"{_dist(first, here):.0f} cm")
    p.check("...and landing some metres away",
            _dist(mark, here) > 300.0, f"{_dist(mark, here):.0f} cm")
    p.check("the item stays in hand while the arc is shown",
            p.get(wc, "Held") == item and p.get(wc, THROWN_VAR) is None)

    p.set(wc, THROW_FORCED_VAR, False)
    yield lambda: p.get(wc, THROWN_VAR) is not None or not p.get(wc, THROW_AIMING_VAR)
    p.check("letting go throws what was held",
            p.get(wc, THROWN_VAR) == item, str(p.get(wc, THROWN_VAR)))
    p.check("...out of the hand and out of the inventory",
            p.get(wc, "Held") != item and item not in list(p.get(wc, "Inventory"))
            and len(p.get(wc, "Inventory")) == carried - 1,
            f"{len(p.get(wc, 'Inventory'))} of {carried} carried")
    p.check("...and the arc is gone", dots.get_instance_count() == 0,
            str(dots.get_instance_count()))
    p.check("...not yet a pick-up while in the air",
            item.get_editor_property("Dropped") is False)

    yield 0.1
    mid = item.get_actor_location()
    p.check("it flies: in the air between the hand and the mark",
            _dist(mid, first) > 20.0 and _dist(mid, mark) > 20.0,
            f"{_dist(mid, first):.0f} cm out, {_dist(mid, mark):.0f} cm to go")

    yield lambda: p.get(wc, THROWN_VAR) is None
    rest = item.get_actor_location()
    p.check("it comes down where the arc said",
            _dist(rest, mark) < LANDS_WITHIN_CM,
            f"{_dist(rest, mark):.0f} cm from the disc")
    p.check("...as a Dropped item, which E picks up",
            item.get_editor_property("Dropped") is True)
    held = p.get(wc, "Held")
    p.check("the emptied hand takes up the next item, as after a drop",
            held is not None and held != item, str(held))
