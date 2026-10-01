"""The throw: holding the key draws the arc, a lob whose height is the held
item's ThrowArcDegrees; letting the key go calls it off; a click of the fire
key over the arc throws what is held, and it comes down where the arc said,
as an item E can pick up.

No key can be injected into a headless game, so the probe holds the throw key
by writing ThrowKeyForced and clicks by writing ThrowClickForced, which
throw.py ORs with the keys and which nothing else writes (verify/throw.py
checks the key polls themselves). The view is levelled first so the throw
goes out across the ground in front of the player.
"""

import unreal

from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.throw_arc import ARC_COMPONENT
from combat.throw_tuning import THROW_PITCH_UP_DEG, THROW_PITCH_VAR
from combat.weapon_component.throw import (
    THROWN_VAR, THROW_AIMING_VAR, THROW_ARC_VAR, THROW_CLICK_FORCED_VAR,
    THROW_FORCED_VAR,
)

WRITABLE = [(WEAPON_COMP_BP_PATH, THROW_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, THROW_CLICK_FORCED_VAR),
            (ITEM_BP_PATH, THROW_PITCH_VAR)]

LANDS_WITHIN_CM = 80.0     # the disc to where it rests: back-off + lift + a sub-step
LOB_CM = 100.0             # the default arc peaks at least this far over the hand
FLAT_DEG = 5.0             # a tuned-down arc, to see the tuning move it


def _peak(dots):
    """How far the arc rises above its first dot, in cm. The last instance is
    the landing disc."""
    n = dots.get_instance_count()
    zs = [dots.get_instance_transform(i, True).translation.z for i in range(n - 1)]
    return max(zs) - zs[0] if zs else 0.0


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

    # The arc's height is the held item's own number, which GUN TUNING writes.
    lob = _peak(dots)
    p.check(f"the default arc ({THROW_PITCH_UP_DEG:g} deg) is a lob over the hand",
            p.get(item, THROW_PITCH_VAR) == THROW_PITCH_UP_DEG and lob > LOB_CM,
            f"{p.get(item, THROW_PITCH_VAR)} deg peaks {lob:.0f} cm up")
    p.set(item, THROW_PITCH_VAR, FLAT_DEG)
    yield 0.05
    flat = _peak(dots)
    p.check(f"tuning the item's arc down to {FLAT_DEG:g} deg flattens it",
            flat < lob * 0.25, f"peaks {flat:.0f} cm up, was {lob:.0f}")
    p.set(item, THROW_PITCH_VAR, THROW_PITCH_UP_DEG)
    yield 0.05

    # Letting the key go calls the throw off; a click with no arc does nothing.
    p.set(wc, THROW_FORCED_VAR, False)
    yield lambda: not p.get(wc, THROW_AIMING_VAR)
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield 0.05
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    p.check("letting the key go throws nothing, and a click without the arc "
            "throws nothing either",
            p.get(wc, "Held") == item and p.get(wc, THROWN_VAR) is None
            and len(p.get(wc, "Inventory")) == carried
            and dots.get_instance_count() == 0,
            f"held {p.get(wc, 'Held')}, {dots.get_instance_count()} dots")

    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05
    count = dots.get_instance_count()
    first = dots.get_instance_transform(0, True).translation
    mark = dots.get_instance_transform(count - 1, True).translation
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield lambda: p.get(wc, THROWN_VAR) is not None or not p.get(wc, THROW_AIMING_VAR)
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    p.set(wc, THROW_FORCED_VAR, False)
    p.check("a click over the arc throws what was held",
            p.get(wc, THROWN_VAR) == item, str(p.get(wc, THROWN_VAR)))
    p.check("...and that click is spent, so it fires nothing",
            p.get(wc, "TriggerSpent") is True)
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
