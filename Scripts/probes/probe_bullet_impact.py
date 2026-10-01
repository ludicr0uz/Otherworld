"""A bullet into the scenery throws chips and dust; one into a body bleeds.

FireForced stands in for the fire key (no key can be injected into a headless
game). First the view is tipped at the ground and a round fired: every pellet
that lands must leave a BP_BulletImpact on the surface it hit, facing out of
it, its pieces flying apart, and no blood. Then a wanderer is stood in front and
another round fired: it bleeds, and the two bursts together never outnumber
the pellets (a pellet gets one or the other).

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil
import time

import unreal

from combat.bullet_impact import IMPACT_PIECES
from combat.burst import BURST_VELOCITY_ENCODE
from combat.paths import (
    BLOOD_CLASS_PATH, BULLET_IMPACT_CLASS_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH,
    WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.weapon_component.tick import FIRE_FORCED_VAR
from graphics_menu.profile_consts import PROFILE_SLOT

WRITABLE = [(WEAPON_COMP_BP_PATH, FIRE_FORCED_VAR), (HEALTH_BP_PATH, "Health")]

LOOK_DOWN_DEG = -55.0   # the reticle on the ground a few metres ahead
IN_FRONT_CM = 150.0     # past the muzzle, inside every pellet's pattern
WALL_WAIT_S = 20.0      # a headless game's clock is slow: bound waits by the wall


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _all(p, class_path):
    return list(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(class_path)))


def _wanderer(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls
             if "ForestWandererAI" in c.get_class().get_name()]
    return next((x for x in pawns if x is not None), None)


def _seat(p, burst):
    """(distance to the surface under ``burst``, its forward . that surface's
    normal), by tracing through it along its own forward; Nones on a miss."""
    at, out = burst.get_actor_location(), burst.get_actor_forward_vector()
    hit = unreal.SystemLibrary.line_trace_single(
        p.world(), at + out * 10.0, at - out * 10.0,
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
        unreal.DrawDebugTrace.NONE, True)
    if hit is None:
        return None, None
    # A HitResult has no named fields in Python: to_tuple() is Break Hit
    # Result's pin order (..., Location, ImpactPoint, Normal, ImpactNormal, ...).
    fields = hit.to_tuple()
    return (fields[5] - at).length(), fields[7].dot(out)


def _until(cond):
    """A wait on ``cond`` that gives up after WALL_WAIT_S of wall clock."""
    end = time.time() + WALL_WAIT_S
    return lambda: cond() or time.time() > end


def _look(p, pitch):
    pc = p.controller()
    pc.set_control_rotation(unreal.Rotator(
        roll=0.0, pitch=pitch, yaw=pc.get_control_rotation().yaw))


def _fire(p, wc, held):
    """One forced round. Yields until it has left; the bursts exist by then."""
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    yield _until(lambda: now() > p.get(held, "NextFireTime") + 0.05)
    loaded = p.get(held, "Loaded")
    p.set(wc, FIRE_FORCED_VAR, True)
    yield _until(lambda: p.get(held, "Loaded") < loaded)
    p.set(wc, FIRE_FORCED_VAR, False)
    p.check("the forced trigger fires a round", p.get(held, "Loaded") < loaded,
            f"{loaded} -> {p.get(held, 'Loaded')}")


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: _wanderer(p) is not None
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    held = p.get(wc, "Held")
    p.check("the player holds a loaded gun",
            held is not None and p.get(held, "Loaded") > 1,
            held.get_class().get_name() if held else "None")
    if held is None:
        return
    pellets = p.get(held, "PelletCount")

    # --- into the ground ---------------------------------------------------
    _look(p, LOOK_DOWN_DEG)
    feet = player.get_actor_location().z
    yield _until(lambda: p.get(wc, "AimValid") and p.get(wc, "AimPoint").z < feet)
    yield 0.3      # the boom's camera is still swinging down: let the reticle rest
    aim = p.get(wc, "AimPoint")
    p.check("the reticle rests on the ground ahead",
            p.get(wc, "AimValid") and aim.z < feet, f"AimPoint {aim}, pawn z {feet:.0f}")
    p.check("nothing has burst before the shot",
            not _all(p, BULLET_IMPACT_CLASS_PATH) and not _all(p, BLOOD_CLASS_PATH))

    yield from _fire(p, wc, held)
    bursts = _all(p, BULLET_IMPACT_CLASS_PATH)
    p.check(f"the round's pellets leave bullet impacts ({pellets} fired)",
            1 <= len(bursts) <= pellets, f"{len(bursts)} BP_BulletImpact")
    p.check("...and the ground does not bleed", not _all(p, BLOOD_CLASS_PATH),
            f"{len(_all(p, BLOOD_CLASS_PATH))} BP_BloodSplash")
    if not bursts:
        return
    # Not "round the reticle": a hip-fired shell is a wide cloud, and on a
    # shallow line a pellet that misses the ground carries on to a trunk or a
    # rock. What every burst owes is its own surface: on it, facing out of it.
    seats = [_seat(p, b) for b in bursts]
    p.note("bursts at " + ", ".join(
        f"{tuple(round(v) for v in b.get_actor_location().to_tuple())}" for b in bursts))
    p.check("each sits on the surface its pellet hit",
            all(gap is not None and gap < 2.0 for gap, _facing in seats),
            f"gaps (cm) {[None if g is None else round(g, 2) for g, _f in seats]}")
    p.check("...facing out of it (+X on the surface normal)",
            all(facing is not None and facing > 0.98 for _gap, facing in seats),
            f"forward . normal {[None if f is None else round(f, 3) for _g, f in seats]}")
    ground = [b for b in bursts if b.get_actor_forward_vector().z > 0.9
              and (b.get_actor_location() - aim).length() < 300.0]
    p.check("...and the ground under the reticle took some of them, facing up",
            len(ground) >= 1, f"{len(ground)} of {len(bursts)}")
    scales = {round(b.get_actor_scale3d().x, 3) for b in bursts}
    p.check("...at blood's scale, the clamp on the round's damage",
            all(0.65 - 1e-3 <= s <= 1.6 + 1e-3 for s in scales), str(sorted(scales)))

    one = bursts[0]
    blobs = one.get_components_by_class(unreal.StaticMeshComponent)
    p.check(f"a burst is {len(IMPACT_PIECES)} pieces", len(blobs) == len(IMPACT_PIECES),
            str(len(blobs)))

    def spread():
        return max(c.get_relative_transform().translation.length() for c in blobs)

    # Built, a piece sits at its velocity over the encode: metres per second
    # read as centimetres. Flown, it is tens of centimetres out.
    built = max(sum(v * v for v in piece.velocity) ** 0.5 for piece in IMPACT_PIECES)
    yield _until(lambda: not unreal.SystemLibrary.is_valid(one)
                 or spread() > built * 4.0)
    alive = unreal.SystemLibrary.is_valid(one)
    p.check("the pieces fly apart from the hit",
            alive and spread() > built * 4.0,
            f"{spread():.1f} cm out, built at {built:.1f} "
            f"(launch speed / {BURST_VELOCITY_ENCODE:.0f})" if alive else "gone already")
    yield _until(lambda: not _all(p, BULLET_IMPACT_CLASS_PATH))
    p.check("the bursts remove themselves", not _all(p, BULLET_IMPACT_CLASS_PATH),
            f"{len(_all(p, BULLET_IMPACT_CLASS_PATH))} left")

    # --- into a body -------------------------------------------------------
    npc = _wanderer(p)
    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, "Health", 1000.0)    # it must outlive the round
    _look(p, 0.0)

    def stand():
        npc.set_actor_location(
            player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM,
            False, True)

    stand()
    yield 0.1
    stand()
    yield 0.05
    stand()
    yield from _fire(p, wc, held)
    blood, chips = _all(p, BLOOD_CLASS_PATH), _all(p, BULLET_IMPACT_CLASS_PATH)
    p.check("a round into a wanderer bleeds", len(blood) >= 1,
            f"{len(blood)} BP_BloodSplash, {len(chips)} BP_BulletImpact")
    p.check("...and no pellet leaves both bursts",
            len(blood) + len(chips) <= pellets,
            f"{len(blood)} + {len(chips)} from {pellets} pellets")
    p.check("...and the wanderer took the hit", p.get(health, "Health") < 1000.0,
            f"{p.get(health, 'Health'):.0f}")
