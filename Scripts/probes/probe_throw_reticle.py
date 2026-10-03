"""The throw goes where the reticle is: an item's arc lies in the upright
plane through the point the reticle rests on (AimPoint), so it stands under
the reticle on screen, and ends ON that point: a gun's near, a blade's near
and far, and the blade thrown comes to rest there. At the sky, where there is
no point to reach, each goes out tipped its own arc over the view, a lob, as
all throws did before.

The keys are held and clicked as probe_throw.py does it (ThrowKeyForced,
ThrowClickForced). The view is turned until the reticle rests on open ground.
"""

import math

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.throw_arc import ARC_COMPONENT
from combat.throw_tuning import (
    THROW_MELEE_SPEED, THROW_PITCH_VAR, THROW_START_FORWARD,
)
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_ARC_VAR, THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR,
)
from combat.weapon_component.throw_flight import THROWN_VAR, THROW_VELOCITY_VAR
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, THROW_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, THROW_CLICK_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh)]

NEAR_PITCH = -14.0         # the reticle on the ground some metres ahead
FAR_PITCH = -6.0           # ...and a good way further
SKY_PITCH = 25.0
IN_PLANE_CM = 3.0          # a dot's distance from the plane through the reticle's point
ON_POINT_CM = 20.0         # the arc's end to the reticle's point
RESTS_WITHIN_CM = 80.0     # the thrown blade to it: back-off + lift + a sub-step
GROUND_CM = 60.0           # the reticle's point is ground if this near the feet's height


def _points(p, wc):
    """The arc's dots, in order; the last is the landing disc (if it landed)."""
    arc = p.get(wc, THROW_ARC_VAR)
    dots = arc.get_editor_property(ARC_COMPONENT)
    return [dots.get_instance_transform(i, True).translation
            for i in range(dots.get_instance_count())]


def _flat(v):
    return unreal.Vector(v.x, v.y, 0.0)


def _off_plane(pts, aim):
    """The furthest any dot is from the upright plane through the first dot
    and ``aim``, in cm."""
    line = _flat(aim - pts[0]).normal()
    across = unreal.Vector(-line.y, line.x, 0.0)
    return max(abs(_flat(q - pts[0]).dot(across)) for q in pts)


def _yaw_of(v):
    return math.degrees(math.atan2(v.y, v.x))


def _turn(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _equip(p, wc, item):
    p.set(wc, "EquippedIndex", list(p.get(wc, "Inventory")).index(item))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item
    yield 0.1


def _look(p, pitch, yaw):
    p.controller().set_control_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))
    yield 0.1


def _open_ground(p, wc, pitch):
    """Turn the view until the reticle rests on the ground; returns the yaw,
    or None."""
    feet = p.pawn().get_actor_location().z - 96.0
    for step in range(24):
        yaw = step * 15.0
        yield from _look(p, pitch, yaw)
        aim = p.get(wc, "AimPoint")
        far = _flat(aim - p.pawn().get_actor_location()).length()
        if abs(aim.z - feet) < GROUND_CM and far > 300.0:
            return yaw
    return None


def _aim(p, wc):
    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05


def _let_go(p, wc):
    p.set(wc, THROW_FORCED_VAR, False)
    yield lambda: not p.get(wc, THROW_AIMING_VAR)


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
    guns = [i for i in bag if i.get_editor_property("UsesAmmo")]
    blades = [i for i in bag if i.get_editor_property("Melee")]
    if not guns or not blades:
        p.check("the player carries a gun and a blade", False,
                str([i.get_name() for i in bag]))
        return
    gun, blade = guns[0], blades[0]
    name = str(blade.get_editor_property("DisplayName")).lower()

    yaw = yield from _open_ground(p, wc, NEAR_PITCH)
    p.check("the reticle can be put on open ground", yaw is not None)
    if yaw is None:
        return

    # --- the arc in line with the reticle, and ending on its point -------------
    cam = unreal.GameplayStatics.get_player_camera_manager(player, 0)
    for item, what, views in ((gun, "a gun", (("near", NEAR_PITCH),)),
                              (blade, f"the {name}", (("near", NEAR_PITCH),
                                                      ("far", FAR_PITCH)))):
        yield from _equip(p, wc, item)
        for label, pitch in views:
            yield from _look(p, pitch, yaw)
            yield from _aim(p, wc)
            aim, pts = p.get(wc, "AimPoint"), _points(p, wc)
            off = _off_plane(pts, aim)
            gap = (pts[-1] - aim).length()
            out = _flat(aim - pts[0]).length()
            p.check(f"{what}'s arc lies in the upright plane through the point "
                    f"the reticle rests on, {label}: it stands under the reticle",
                    len(pts) > 3 and off < IN_PLANE_CM,
                    f"{len(pts)} dots, the furthest {off:.1f} cm out of it")
            p.check("...and ends on that point",
                    gap < ON_POINT_CM, f"{gap:.0f} cm from it, {out / 100.0:.1f} m out")
            if item is gun:
                bearing = _yaw_of(aim - pts[0])
                aside = abs(_flat(pts[0] - cam.get_camera_location()).dot(
                    unreal.MathLibrary.get_right_vector(
                        unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))))
                p.check("...turned off the view's own heading to do it, the "
                        "launch point being off to one side of the camera's line",
                        aside < 1.0 or _turn(bearing, yaw) > 0.05,
                        f"launch {aside:.0f} cm aside of the camera's line, the "
                        f"arc turned {_turn(bearing, yaw):.2f} deg onto the point")
            yield from _let_go(p, wc)

        # At the sky: no point to reach, the item's own arc over the view.
        yield from _look(p, SKY_PITCH, yaw)
        yield from _aim(p, wc)
        aim, pts = p.get(wc, "AimPoint"), _points(p, wc)
        rise = math.degrees(math.atan2(pts[1].z - pts[0].z,
                                       _flat(pts[1] - pts[0]).length()))
        # The first step of the curve is a little under the launch pitch.
        tip = p.get(item, THROW_PITCH_VAR)
        want = SKY_PITCH + tip
        p.check(f"at the sky, out of reach, {what} goes out its own {tip:g} "
                "degrees over the view, still in line with the reticle",
                (aim - pts[0]).length() > 5000.0 and want - 4.0 < rise < want + 0.5
                and _off_plane(pts, aim) < IN_PLANE_CM,
                f"the point {(aim - pts[0]).length() / 100.0:.0f} m off, the arc "
                f"leaving {rise:.1f} deg up, {want:g} wanted")
        yield from _let_go(p, wc)

    # --- thrown: it comes to rest where the reticle was ------------------------
    yield from _look(p, NEAR_PITCH, yaw)
    yield from _aim(p, wc)
    aim = p.get(wc, "AimPoint")
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield lambda: p.get(wc, THROWN_VAR) is not None \
        or (p.get(wc, "TriggerSpent") and not p.get(wc, THROW_AIMING_VAR))
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    yield lambda: p.get(wc, THROWN_VAR) is not None
    p.set(wc, THROW_FORCED_VAR, False)
    velocity = p.get(wc, THROW_VELOCITY_VAR)
    p.check(f"the {name} leaves the hand at its own speed",
            p.get(wc, THROWN_VAR) == blade
            and abs(velocity.length() - THROW_MELEE_SPEED) < 1.0,
            f"{velocity.length():.0f} cm/s")
    yield lambda: p.get(wc, THROWN_VAR) is None
    rest = blade.get_actor_location()
    p.check("...and comes to rest where the reticle was",
            (rest - aim).length() < RESTS_WITHIN_CM
            and blade.get_editor_property("Dropped") is True,
            f"{(rest - aim).length():.0f} cm from the point, "
            f"{_flat(aim - player.get_actor_location()).length() / 100.0:.1f} m out "
            f"(launch {THROW_START_FORWARD:g} cm ahead)")
