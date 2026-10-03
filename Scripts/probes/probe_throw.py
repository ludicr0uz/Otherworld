"""The throw: holding the key draws the arc, with nothing under the reticle
in reach a lob whose height is the held item's ThrowArcDegrees, and cocks the arm, ready to throw; letting the key go
calls it off and brings the arm down; a click of the fire key over the arc
plays the throw's clip on from that pose and, when its hand lets go, throws
what is held; it tumbles end over end through the air and comes down where
the arc said, as an item E can pick up.

No key can be injected into a headless game, so the probe holds the throw key
by writing ThrowKeyForced and clicks by writing ThrowClickForced, which
throw.py ORs with the keys and which nothing else writes (verify/throw.py
checks the key polls themselves). The view is levelled first, and turned to
where the reticle rests on nothing near, so the throw is the lob and goes out
across the ground in front of the player (a throw at a point in reach is
probe_throw_reticle.py's).

Run with --windowed and OW_THROW_SHOTS=1 to save pictures of the wind-up and
of the item in the air to Saved/Screenshots/MacEditor.
"""

import math
import os

import unreal

from combat.skin import SKIN_ADVENTURER, SKIN_QUINN
from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.throw_arc import ARC_COMPONENT
from combat.anim_blueprint import AIM_SLOT
from combat.throw_tuning import (
    THROW_PITCH_UP_DEG, THROW_PITCH_VAR, THROW_SPIN_DEG_S, THROW_WINDUP_S,
)
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_ARC_VAR, THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR,
)
from combat.weapon_component.throw_flight import THROWN_VAR
from combat.weapon_component.throw_ready import THROW_READY_ANIM_VAR
from combat.weapon_component.throw_windup import THROW_ANIM_VAR, THROW_WINDING_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, THROW_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, THROW_CLICK_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, "EquippedIndex"),
            (WEAPON_COMP_BP_PATH, "NeedsRefresh"),
            (ITEM_BP_PATH, THROW_PITCH_VAR)]

LANDS_WITHIN_CM = 80.0     # the disc to where it rests: back-off + lift + a sub-step
OPEN_CM = 3000.0           # the reticle's point is out of every item's reach past this
LOB_CM = 100.0             # the default arc peaks at least this far over the hand
FLAT_DEG = 5.0             # a tuned-down arc, to see the tuning move it
HAND_UP_CM = 30.0          # the wind-up takes the hand this far over the capsule's centre
READY_UP_CM = 45.0         # the ready pose holds the hand this far over it
SHOTS = bool(os.environ.get("OW_THROW_SHOTS"))
SHOT_AT_S = 0.05           # into the wind-up: the hand is over the head


def _shot(p):
    """Save a picture of this frame (windowed runs only)."""
    if SHOTS:
        unreal.SystemLibrary.execute_console_command(p.pawn(), "shot")


def _hand_z(player):
    """The throwing hand's height over the capsule's centre, in cm."""
    mesh = player.get_editor_property("mesh")
    bone = next(s.pose_bones["hand_r"] for s in (SKIN_ADVENTURER, SKIN_QUINN)
                if mesh.get_bone_index(s.pose_bones["hand_r"]) >= 0)
    return mesh.get_socket_location(bone).z - player.get_actor_location().z


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


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.pawn())


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
    for step in range(24):
        view = unreal.Rotator(roll=0.0, pitch=0.0, yaw=view.yaw + 15.0 * bool(step))
        pc.set_control_rotation(view)
        yield 0.1
        if _dist(p.get(wc, "AimPoint"), player.get_actor_location()) > OPEN_CM:
            break
    p.check("the level view can be turned to where the reticle rests on nothing "
            "in reach", _dist(p.get(wc, "AimPoint"), player.get_actor_location()) > OPEN_CM,
            f"{_dist(p.get(wc, 'AimPoint'), player.get_actor_location()) / 100.0:.0f} m")

    clip = p.get(wc, THROW_ANIM_VAR)
    ready = p.get(wc, THROW_READY_ANIM_VAR)
    anim = player.get_editor_property("mesh").get_anim_instance()
    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05
    dots = _dots(p, wc)
    count = dots.get_instance_count() if dots else 0
    p.check("holding the key draws the arc as dots", count > 5, f"{count} dots")
    if count < 2:
        p.set(wc, THROW_FORCED_VAR, False)
        return
    if ready is not None:
        # The arm going up, over the pose's blend.
        yield 0.3
        _shot(p)
        p.check("...and cocks the arm, ready to throw: the ready pose held in "
                f"{AIM_SLOT}, the hand up beside the head with the item in it",
                anim.is_playing_slot_animation(ready, AIM_SLOT)
                and _hand_z(player) >= READY_UP_CM,
                f"hand {_hand_z(player):.0f} cm over the capsule's centre")
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
    if ready is not None:
        yield 0.4
        p.check("letting the key go brings the arm down: the ready pose is "
                "out of the slot and the hand back where it carries the item",
                not anim.is_playing_slot_animation(ready, AIM_SLOT)
                and _hand_z(player) < HAND_UP_CM,
                f"hand {_hand_z(player):.0f} cm over the capsule's centre")
    p.check("letting the key go throws nothing, and a click without the arc "
            "throws nothing either",
            p.get(wc, "Held") == item and p.get(wc, THROWN_VAR) is None
            and len(p.get(wc, "Inventory")) == carried
            and dots.get_instance_count() == 0,
            f"held {p.get(wc, 'Held')}, {dots.get_instance_count()} dots")

    carried_at = _hand_z(player)
    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05
    count = dots.get_instance_count()
    first = dots.get_instance_transform(0, True).translation
    mark = dots.get_instance_transform(count - 1, True).translation
    # The click starts the clip; the item stays in the hand until it lets go.
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_WINDING_VAR) is not None \
        or p.get(wc, THROWN_VAR) is not None or not p.get(wc, THROW_AIMING_VAR)
    clicked = _now(p)
    p.check("a click over the arc is spent, so it fires nothing",
            p.get(wc, "TriggerSpent") is True)
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    if clip is not None:
        p.check("a click over the arc winds up: the item still in the hand, "
                "nothing in the air, the arc gone",
                p.get(wc, THROW_WINDING_VAR) == item and p.get(wc, "Held") == item
                and p.get(wc, THROWN_VAR) is None and dots.get_instance_count() == 0,
                f"winding {p.get(wc, THROW_WINDING_VAR)}, {dots.get_instance_count()} dots")
        yield 0.03
        p.check(f"...playing the throw's clip into {AIM_SLOT}",
                anim.is_playing_slot_animation(clip, AIM_SLOT), clip.get_name())
        p.check("...with no arc drawn over it, the key still held",
                not p.get(wc, THROW_AIMING_VAR) and dots.get_instance_count() == 0,
                f"{dots.get_instance_count()} dots")
    top, pictured = carried_at, False
    while p.get(wc, THROWN_VAR) is None and p.get(wc, THROW_WINDING_VAR) is not None:
        top = max(top, _hand_z(player))
        # One picture, late in the wind-up: a shot stalls the frame after it.
        if not pictured and _now(p) - clicked >= SHOT_AT_S:
            pictured = True
            _shot(p)
        yield 0.01
    waited = _now(p) - clicked
    if clip is not None:
        p.check("...the throwing hand coming up over the shoulder with the item "
                "in it", top >= HAND_UP_CM and top - carried_at >= 20.0,
                f"hand {carried_at:.0f} -> {top:.0f} cm over the capsule's centre")
    p.set(wc, THROW_FORCED_VAR, False)
    p.check("the hand lets go of what was held"
            + (f" {THROW_WINDUP_S:.2f} s after the click, the clip played on "
               "from the ready pose" if clip is not None
               else " on the click (this skin has no throw clip)"),
            p.get(wc, THROWN_VAR) == item
            and (THROW_WINDUP_S - 0.02 <= waited
                 and (SHOTS or waited <= THROW_WINDUP_S + 0.15)
                 if clip is not None else waited < 0.1),
            f"{p.get(wc, THROWN_VAR)} after {waited:.2f} s")
    p.check("...and the wind-up is over", p.get(wc, THROW_WINDING_VAR) is None)
    p.check("...out of the hand and out of the inventory",
            p.get(wc, "Held") != item and item not in list(p.get(wc, "Inventory"))
            and len(p.get(wc, "Inventory")) == carried - 1,
            f"{len(p.get(wc, 'Inventory'))} of {carried} carried")
    p.check("...and the arc is gone", dots.get_instance_count() == 0,
            str(dots.get_instance_count()))
    p.check("...not yet a pick-up while in the air",
            item.get_editor_property("Dropped") is False)

    # The tumble: the turn between two moments of the flight, in the world.
    lib = unreal.MathLibrary
    at0, rot0 = _now(p), item.get_actor_rotation()
    yield 0.1
    at1, rot1 = _now(p), item.get_actor_rotation()
    _shot(p)
    mid = item.get_actor_location()
    p.check("it flies: in the air between the hand and the mark",
            _dist(mid, first) > 20.0 and _dist(mid, mark) > 20.0,
            f"{_dist(mid, first):.0f} cm out, {_dist(mid, mark):.0f} cm to go")
    turn = lib.compose_rotators(lib.negate_rotator(rot0), rot1)
    quat = turn.quaternion()
    angle = math.degrees(quat.get_angle())
    want = THROW_SPIN_DEG_S * (at1 - at0)
    p.check(f"...turning in the air, {THROW_SPIN_DEG_S:g} degrees a second",
            abs(angle - want) <= max(15.0, 0.25 * want),
            f"{angle:.0f} deg in {at1 - at0:.2f} s, {want:.0f} expected")
    ahead = unreal.Rotator(roll=0.0, pitch=0.0, yaw=view.yaw)
    across = lib.get_right_vector(ahead)
    axis = quat.get_rotation_axis()
    tipped = turn.quaternion().rotate_vector(lib.get_forward_vector(ahead))
    p.check("...end over end, top first: about the level axis across the "
            "throw, which takes what pointed ahead downwards",
            abs(axis.dot(across)) > 0.95 and tipped.z < -0.3,
            f"axis . across {axis.dot(across):+.2f}, ahead now z {tipped.z:+.2f}")

    yield lambda: p.get(wc, THROWN_VAR) is None
    rest = item.get_actor_location()
    lay = item.get_actor_rotation()
    yield 0.2
    p.check("it stops turning where it lands",
            lay.is_near_equal(item.get_actor_rotation(), 0.01), str(item.get_actor_rotation()))
    p.check("it comes down where the arc said",
            _dist(rest, mark) < LANDS_WITHIN_CM,
            f"{_dist(rest, mark):.0f} cm from the disc")
    p.check("...as a Dropped item, which E picks up",
            item.get_editor_property("Dropped") is True)
    p.check("the emptied hand stays empty, as after a drop: nothing comes up "
            "out of a slot unasked (combat/slot_tuning.py)",
            p.get(wc, "Held") is None, str(p.get(wc, "Held")))

    # A hand that changes in the wind-up throws nothing: the throw was of the
    # item the click wound up with.
    if clip is None or len(p.get(wc, "Inventory")) < 2:
        return
    p.set(wc, "EquippedIndex", 0)             # the first item to hand (context.hold)
    yield lambda: p.get(wc, "Held") is not None
    held = p.get(wc, "Held")
    carried = len(p.get(wc, "Inventory"))
    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_WINDING_VAR) is not None
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    p.set(wc, THROW_FORCED_VAR, False)
    wound = p.get(wc, THROW_WINDING_VAR)
    p.set(wc, "EquippedIndex", 1)
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, THROW_WINDING_VAR) is None
    other = p.get(wc, "Held")
    yield 0.1
    p.check("switching to another item in the wind-up calls the throw off: "
            "nothing in the air, nothing gone from the bag",
            wound == held and other is not None and other != wound
            and p.get(wc, THROWN_VAR) is None
            and len(p.get(wc, "Inventory")) == carried
            and wound.get_editor_property("Dropped") is False
            and p.get(wc, "Held") == other,
            f"wound up {wound.get_name()}, holding {other.get_name() if other else None}, "
            f"{len(p.get(wc, 'Inventory'))} of {carried} carried")
