"""A melee weapon's throw: where a gun is lobbed, the knife and the axe go out
flat and fast, and spin forward like a throwing knife or a throwing axe: the
item leaves the hand squared up to the throw, its blade in the plane it flies
in, and turns in that plane, top first, until it lands where the arc said.

The keys are held and clicked as probe_throw.py does it (ThrowKeyForced,
ThrowClickForced), and the view is levelled first. The gun that is in hand at
the start gives the lob the melee arcs are measured against.

Run with --windowed and OW_THROW_SHOTS=1 to save a picture of each item in
the air to Saved/Screenshots/MacEditor.
"""

import math
import os

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.throw_arc import ARC_COMPONENT
from combat.throw_tuning import (
    MELEE_THROW, THROW_EDGE_ON_VAR, THROW_MELEE_SPIN_DEG_S, THROW_PITCH_VAR,
    THROW_SPEED_VAR, THROW_SPIN_VAR,
)
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_ARC_VAR, THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR,
)
from combat.weapon_component.throw_flight import THROWN_VAR, THROW_VELOCITY_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, THROW_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, THROW_CLICK_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, "EquippedIndex"),
            (WEAPON_COMP_BP_PATH, "NeedsRefresh")]

LANDS_WITHIN_CM = 80.0     # the disc to where it rests, as in probe_throw.py
FLAT_CM = 50.0             # a melee arc peaks no further than this over the hand
SAMPLE_S = 0.08            # between two looks at the spin: under half a turn
SHOTS = bool(os.environ.get("OW_THROW_SHOTS"))


def _dots(p, wc):
    arc = p.get(wc, THROW_ARC_VAR)
    return arc.get_editor_property(ARC_COMPONENT) if arc else None


def _arc(dots):
    """(first dot, landing disc, rise over the first dot in cm, how far the
    path strays from the straight line between its ends in cm)."""
    n = dots.get_instance_count()
    pts = [dots.get_instance_transform(i, True).translation for i in range(n)]
    first, mark, path = pts[0], pts[-1], pts[:-1]
    line = mark - first
    length = max(line.length(), 1.0)
    bow = max((line.cross(q - first).length() / length for q in path), default=0.0)
    return first, mark, max(q.z for q in path) - first.z, bow


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.pawn())


def _equip(p, wc, item):
    index = list(p.get(wc, "Inventory")).index(item)
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)


def _aim(p, wc, item):
    """Hold the throw key with item in hand; returns the arc's dots."""
    _equip(p, wc, item)
    yield lambda: p.get(wc, "Held") == item
    yield 0.1
    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05


def _throw(p, wc, item, name, lob_rise, lob_bow):
    """Aim item, check its arc against the lob, throw it and watch it fly."""
    lib = unreal.MathLibrary
    got = {v: p.get(item, v) for v in MELEE_THROW}
    p.check(f"the {name} carries a melee weapon's throw", got == MELEE_THROW, str(got))
    yield from _aim(p, wc, item)
    dots = _dots(p, wc)
    first, mark, rise, bow = _arc(dots)
    p.check(f"the {name}'s arc is nearly flat where the gun's is a lob",
            rise < FLAT_CM and rise < lob_rise / 3.0,
            f"peaks {rise:.0f} cm over the hand, the gun's {lob_rise:.0f}")
    p.check("...a more direct path: it strays under half as far from the "
            "straight line to where it lands",
            bow < lob_bow / 2.0, f"{bow:.0f} cm, the gun's {lob_bow:.0f}")

    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield lambda: p.get(wc, THROWN_VAR) is not None \
        or (p.get(wc, "TriggerSpent") and not p.get(wc, THROW_AIMING_VAR))
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    yield lambda: p.get(wc, THROWN_VAR) is not None
    p.set(wc, THROW_FORCED_VAR, False)
    p.check(f"the {name} leaves the hand", p.get(wc, THROWN_VAR) == item)

    velocity = p.get(wc, THROW_VELOCITY_VAR)
    speed = velocity.length()
    p.check(f"...at its own {MELEE_THROW[THROW_SPEED_VAR]:g} cm/s, "
            f"{MELEE_THROW[THROW_PITCH_VAR]:g} degrees over the view",
            abs(speed - MELEE_THROW[THROW_SPEED_VAR]) < 1.0
            and abs(math.degrees(math.asin(velocity.z / speed))
                    - MELEE_THROW[THROW_PITCH_VAR]) < 0.5,
            f"{speed:.0f} cm/s, {math.degrees(math.asin(velocity.z / speed)):.1f} deg up")
    heading = unreal.Vector(velocity.x, velocity.y, 0.0).normal()
    across = unreal.Vector(-heading.y, heading.x, 0.0)

    # The spin: the turn between two moments of the flight, and through all of
    # it the item's own Y level across the throw, which keeps the blade's
    # plane (its X and Z) the plane it flies in.
    at0, rot0 = _now(p), item.get_actor_rotation()
    off = []
    while p.get(wc, THROWN_VAR) == item and _now(p) - at0 < SAMPLE_S:
        off.append(abs(lib.get_right_vector(item.get_actor_rotation()).dot(across)))
        yield 0.01
    at1, rot1 = _now(p), item.get_actor_rotation()
    if SHOTS:
        unreal.SystemLibrary.execute_console_command(p.pawn(), "shot")
    flying = p.get(wc, THROWN_VAR) == item
    quat = lib.compose_rotators(lib.negate_rotator(rot0), rot1).quaternion()
    # The same turn reads as a or 360 - a, by the quaternion's sign.
    angle = math.degrees(quat.get_angle())
    angle = min(angle, 360.0 - angle)
    want = THROW_MELEE_SPIN_DEG_S * (at1 - at0)
    p.check(f"it spins {THROW_MELEE_SPIN_DEG_S:g} degrees a second in the air",
            flying and abs(angle - want) <= max(15.0, 0.25 * want),
            f"{angle:.0f} deg in {at1 - at0:.2f} s, {want:.0f} expected")
    ahead = lib.make_rot_from_x(heading)
    tipped = quat.rotate_vector(lib.get_forward_vector(ahead))
    p.check("...forward: about the level axis across the throw, what pointed "
            "ahead going down",
            abs(quat.get_rotation_axis().dot(across)) > 0.95 and tipped.z < -0.3,
            f"axis . across {quat.get_rotation_axis().dot(across):+.2f}, "
            f"ahead now z {tipped.z:+.2f}")
    while p.get(wc, THROWN_VAR) == item:
        off.append(abs(lib.get_right_vector(item.get_actor_rotation()).dot(across)))
        yield 0.02
    p.check("...in the plane of the throw from the hand to the ground: its "
            "blade never turns out of it",
            len(off) >= 3 and min(off) > 0.99,
            f"{len(off)} looks, its Y . across no less than {min(off):.3f}")

    rest = item.get_actor_location()
    p.check(f"the {name} comes down where the arc said, as a pick-up",
            (rest - mark).length() < LANDS_WITHIN_CM
            and item.get_editor_property("Dropped") is True,
            f"{(rest - mark).length():.0f} cm from the disc")
    yield 0.1


def probe(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    yield lambda: p.get(wc, "Held") is not None
    bag = list(p.get(wc, "Inventory"))
    melee = [i for i in bag if i.get_editor_property("Melee")]
    guns = [i for i in bag if i.get_editor_property("UsesAmmo")]
    p.check("the player carries a gun and two melee weapons, the knife and the axe",
            bool(guns) and len(melee) == 2,
            str([i.get_name() for i in bag]))
    if not guns or not melee:
        return

    pc = p.controller()
    view = pc.get_control_rotation()
    pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=view.yaw))
    yield 0.05

    # The lob every other item is thrown on, off a gun's arc.
    gun = guns[0]
    yield from _aim(p, wc, gun)
    _first, _mark, lob_rise, lob_bow = _arc(_dots(p, wc))
    p.set(wc, THROW_FORCED_VAR, False)
    yield lambda: not p.get(wc, THROW_AIMING_VAR)
    p.check("a gun is lobbed, tumbling as the hand held it",
            lob_rise > 100.0 and p.get(gun, THROW_EDGE_ON_VAR) is False
            and p.get(gun, THROW_SPIN_VAR) < THROW_MELEE_SPIN_DEG_S,
            f"peaks {lob_rise:.0f} cm over the hand, strays {lob_bow:.0f} cm "
            "from the straight line")

    for item in melee:
        name = str(item.get_editor_property("DisplayName")).lower()
        yield from _throw(p, wc, item, name, lob_rise, lob_bow)
