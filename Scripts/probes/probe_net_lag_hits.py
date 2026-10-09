"""Lag compensation for shots (task M22, combat/lag_tuning.py; the C++ is
Source/Otherworld's OtherworldShotLibrary and OtherworldHitHistory).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_lag_hits.py
    python3 Scripts/dev/uepy.py --net --clients 2 --lag 150 --probe-timeout 240 --probe Scripts/probes/probe_net_lag_hits.py

    server    clears the wanderers, gives both players health to spare,
              brings client 1's pistol to its hand (one round a shot: the
              shotgun's spread would hide a miss) and stands client 2
              STAND_CM in front of client 1
    client 2  runs across client 1's line of fire, turning back every STRAFE_S
    client 1  down the sights, keeps the reticle on the chest of its own copy
              of client 2 (what a player sees) and fires ROUNDS pistol rounds,
              one as soon as the reticle rests on it and the gun has cooled
    server    counts the rounds that hurt client 2 (each fall of its health),
              reads the rewind the last shot was judged with and how many
              samples of client 2's hit boxes it holds

Without --lag the rewind is a few hundredths (the loopback's round trip and
EXTRA_REWIND_S) and the rate is the yardstick. With --lag 150 each shot
reaches the server 150 ms after client 1 fired, at a target that has run
60 cm on since; the rate stays close to the yardstick only because the server
judges the shot where client 1 saw client 2. The lag a run has is read off
client 1's command line (-PktLag=, uepylib/net_plan.py) and posted.
"""

SYSTEMS = ('net',)

import re
import time

import unreal

from combat import health_vars as HV
from combat.lag_tuning import EXTRA_REWIND_S, MAX_REWIND_S
from combat.paths import (
    HEALTH_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.shot_vars import ReloadForced
from combat.slot_tuning import PISTOL_SLOT
from combat.weapon_component.accuracy import AIM_SPREAD_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_hot_blade import _wanderers
from probes.probe_net_fire import (
    SIGHTS_SPREAD_DEG, _await, _bodies, _health, _nearest, _vec)

RUNS_ON = ("server", "client")
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (FIRE_FORCED_VAR, ReloadForced, SIGHTS_FORCED_VAR)]
            + [(HEALTH_BP_PATH, HV.Health)])

SHOOTER, VICTIM = "client 1", "client 2"
STAND_CM = 500.0
STRAFE_S = 0.9
ROUNDS = 8
# The chest, on the mannequin's bones every body wears (asset_pipeline/rig_compat.py).
CHEST_BONE = "spine_03"
# How far the chest may lie off the line from the camera through the reticle
# before the trigger is pulled: the capsule is 34 cm round a body half that
# wide, so a reticle merely on the capsule is a round past the body.
ON_LINE_CM = 12.0
SPARE_HEALTH = 100000.0
# What the strafe must amount to, seen from either side, for the run to prove anything.
ACROSS_CM = 150.0
# The rate either run must keep. Measured on this machine (the pistol, eight
# rounds): 6/8 without lag and 7/8 with --lag 150; the one systematic miss is
# the first shot after the join, rewound by the join's inflated round trip.
# The old graph (no rewind) landed 0/8 with --lag 150. One run is one sample:
# measured again on 2026-10-08 (task A4), runs of the same build landed 4 to 8
# of 8 (Scripts/net/CLAUDE.md, "Lag compensation").
MIN_HIT_RATE = 0.6
# How many samples the history holds for a character after a second of play.
MIN_SAMPLES = 20
NO_LAG_REWIND_S = 0.08
# The history against the bone it records (UOtherworldShotLibrary::HitBoxThen):
# how far back the chest's box is asked for every frame, and how near the
# server's own track of the bone it must lie.
BOX_BACK_S = 0.1
BOX_NEAR_CM = 2.0


def _box_off_track(track, boxes):
    """For each frame's (time, where the history put the chest box BOX_BACK_S
    before it): how far that is from the bone's own track at that moment."""
    apart = []
    for at, box in boxes:
        then = at - BOX_BACK_S
        for (t0, a), (t1, b) in zip(track, track[1:]):
            if t0 <= then <= t1 and t1 > t0:
                apart.append((box - (a + (b - a) * ((then - t0) / (t1 - t0)))).length())
                break
    return apart


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _lag_ms():
    """The -PktLag this process was started with, or 0."""
    found = re.search(r"-PktLag=(\d+)", str(unreal.SystemLibrary.get_command_line()))
    return int(found.group(1)) if found else 0


def _ideal_rewinds(track, shots, seen):
    """[(rewind used, rewind that would have put the shot where client 1 saw
    the chest, how far off the track that point lay)] per shot: the time,
    before the shot's arrival, at which the server's track of the chest passed
    nearest the point client 1 saw, and the miss at that nearest pass."""
    out = []
    for (arrived, got), point in zip(shots, seen):
        best = None
        for (t0, a), (t1, b) in zip(track, track[1:]):
            if t1 < arrived - 0.6 or t0 > arrived:
                continue
            seg = b - a
            length = seg.length()
            f = 0.0 if length < 1e-3 else max(0.0, min(1.0, (point - a).dot(seg) / (length * length)))
            d = (a + seg * f - point).length()
            if best is None or d < best[0]:
                best = (d, arrived - (t0 + (t1 - t0) * f))
        out.append((got, best[1], best[0]) if best else (got, float("nan"), float("nan")))
    return out


def _spread(points):
    """How far apart the points lie, in the plane: the strafe's reach."""
    if len(points) < 2:
        return 0.0
    xs = [q[0] for q in points]
    ys = [q[1] for q in points]
    return max(max(xs) - min(xs), max(ys) - min(ys))


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield _await(lambda: p.posted(SHOOTER, "pos"))
    if not p.posted(SHOOTER, "pos"):
        p.check("client 1 said where it stands", False, "no post")
        return
    players, _npcs = _bodies(p)
    one = _nearest(players, p.posted(SHOOTER, "pos"))
    two = next((b for b in players if b != one), None)
    if two is None:
        p.check("the server has two players' characters", False, str(len(players)))
        return
    for ctrl in _wanderers(p):
        pawn = ctrl.get_controlled_pawn()
        if pawn:
            pawn.destroy_actor()
    for body in players:
        p.set(_health(p, body), HV.Health, SPARE_HEALTH)
    health = _health(p, two)
    hp = lambda: float(p.get(health, HV.Health))
    wc = p.component(one, WEAPON_COMP_CLASS_PATH)
    gun = p.get(wc, "Held")
    p.ask_slot(wc, PISTOL_SLOT)
    yield _await(lambda: p.get(wc, "Held") not in (None, gun), 5.0)
    pistol = p.get(wc, "Held")
    spot = one.get_actor_location() + one.get_actor_forward_vector() * STAND_CM
    two.set_actor_location(spot, False, True)
    p.post("placed", {"spot": _vec(spot),
                      "held": pistol.get_class().get_name() if pistol else ""})

    hits, last = [0], [hp()]
    lib = unreal.OtherworldShotLibrary
    # Client 2's chest on every frame, by the server's clock, and each shot's
    # arrival with the rewind it got: what the rewind should have been is how
    # far back along that track the chest client 1 says it fired at lies.
    track, shots, judged, fell = [], [], [0], []

    boxes = []

    def count():
        now = hp()
        if now < last[0] - 1e-3:
            hits[0] += 1
            fell.append(_now(p))
        last[0] = now
        track.append((_now(p), two.mesh.get_socket_location(CHEST_BONE)))
        boxes.append((_now(p), lib.hit_box_then(two, CHEST_BONE, BOX_BACK_S)))
        n = int(lib.rewound_shots(p.world()))
        if n > judged[0]:
            shots.append((_now(p), float(lib.last_rewind_seconds(p.world()))))
            judged[0] = n
        return False

    yield _await(lambda: count() or p.posted(SHOOTER, "done") is not None, 150.0)
    done = p.posted(SHOOTER, "done")
    if not done:
        p.check("client 1 finished its rounds", False, "no post")
        return
    # The last ask is still on its way for as long as the lag.
    yield _await(count, 1.0)
    rounds, lag_ms = int(done["rounds"]), int(done["lag_ms"])
    rewind = float(lib.last_rewind_seconds(p.world()))
    ideal = _ideal_rewinds(track, shots, [unreal.Vector(*q) for q in done["seen"]])
    p.note("per shot: the rewind it got / how far back the chest client 1 fired at lay "
           "on the server's own track of it (ms), how far off that track it lay (cm), "
           "and whether the round hurt: " + ", ".join(
               f"{got * 1000:.0f}/{want * 1000:.0f} {off:.0f}cm "
               f"{'hit' if any(0.0 <= t - at < 0.2 for t in fell) else 'miss'}"
               for (got, want, off), (at, _r) in zip(ideal, shots)))
    apart = _box_off_track(track, boxes)
    p.check(f"the history puts the chest's hit box where the chest was: {BOX_BACK_S * 1000:.0f} ms "
            f"back it is within {BOX_NEAR_CM:g} cm of the server's own track of the bone, "
            "frame after frame of the strafe", len(apart) >= 30 and max(apart) < BOX_NEAR_CM,
            f"{len(apart)} frame(s), {max(apart) if apart else 0:.2f} cm at most")
    samples = int(lib.hit_history_samples(two))
    judged = int(lib.rewound_shots(p.world()))
    p.check("the server records every character's hit boxes while it has clients: "
            f"at least {MIN_SAMPLES} samples of client 2's",
            bool(lib.is_recording_hit_history(p.world())) and samples >= MIN_SAMPLES,
            f"recording {lib.is_recording_hit_history(p.world())}, {samples} samples")
    rate = hits[0] / float(rounds) if rounds else 0.0
    how = f"with {lag_ms} ms of lag" if lag_ms else "without lag"
    p.check(f"client 1's rounds hit strafing client 2 at least {MIN_HIT_RATE:.0%} of the "
            f"time {how}: the server judges each where client 1 saw the target",
            rounds >= ROUNDS - 1 and rate >= MIN_HIT_RATE,
            f"{hits[0]}/{rounds} = {rate:.0%}, the last shot judged {rewind * 1000:.0f} ms back")
    if lag_ms:
        floor = lag_ms / 1000.0 * 0.8
        p.check(f"...each judged against the past: at least {floor * 1000:.0f} ms back "
                f"(the round trip and {EXTRA_REWIND_S * 1000:.0f} ms over it), never "
                f"more than the cap ({MAX_REWIND_S * 1000:.0f} ms)",
                floor <= rewind <= MAX_REWIND_S + 1e-6 and judged >= rounds,
                f"{rewind * 1000:.0f} ms, {judged} shots judged against the history")
    else:
        p.check("...with no lag the rewind is all but nil: the present, as single "
                "player has it", 0.0 <= rewind < NO_LAG_REWIND_S,
                f"{rewind * 1000:.0f} ms")
    p.post("judged", {"hits": hits[0], "rounds": rounds, "rewind_ms": rewind * 1000.0})


# ─── the clients ─────────────────────────────────────────────────────────────

def _strafe(p, mine, other, until):
    """Run across the line from ``other`` to ``mine``, turning back every
    STRAFE_S, until ``until()``. Returns the ground covered, side to side."""
    seen = []
    turned = [time.time()]
    side = [1.0]

    def step():
        across = unreal.Vector(0.0, 0.0, 1.0).cross(
            mine.get_actor_location() - other.get_actor_location()).normal()
        if time.time() - turned[0] > STRAFE_S:
            side[0], turned[0] = -side[0], time.time()
        mine.add_movement_input(across * side[0], 1.0, False)
        seen.append(_vec(mine.get_actor_location()))
        return until()

    yield _await(step, 150.0)
    return _spread(seen)


def _off_line(cam, aim, point):
    """How far ``point`` lies off the line from the camera through the reticle."""
    along = (aim - cam).normal()
    to = point - cam
    return (to - along * to.dot(along)).length()


def _shoot(p, wc, held, point, seen):
    """Turn the view onto ``point()`` every frame; once the reticle's line
    runs through it (ON_LINE_CM) and the gun has cooled, pull the trigger,
    still steering, until the round has left. True if one did; its target as
    seen then is appended to ``seen``."""
    cam = unreal.GameplayStatics.get_player_camera_manager(p.world(), 0)
    was = int(p.get(held, "Loaded"))
    pulled = [False]

    def step():
        p.controller().set_control_rotation(unreal.MathLibrary.find_look_at_rotation(
            cam.get_camera_location(), point()))
        if pulled[0]:
            return int(p.get(held, "Loaded")) < was
        if (bool(p.get(wc, "AimValid"))
                and _off_line(cam.get_camera_location(), p.get(wc, "AimPoint"), point()) < ON_LINE_CM
                and _now(p) > float(p.get(held, "NextFireTime")) + 0.05):
            seen.append(_vec(point()))
            p.set(wc, FIRE_FORCED_VAR, True)
            pulled[0] = True
        return False

    yield _await(step, 6.0)
    p.set(wc, FIRE_FORCED_VAR, False)
    return pulled[0] and int(p.get(held, "Loaded")) < was


def probe_client(p):
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    yield _await(lambda: len(_bodies(p)[0]) == 2)
    other = next((b for b in _bodies(p)[0] if b != mine), None)
    held = p.get(wc, "Held")
    if held is None or other is None:
        p.check(f"{p.where} holds its gun and sees the other player", False,
                f"{held}, {other}")
        return
    if p.where == SHOOTER:
        p.post("pos", _vec(mine.get_actor_location()))
    yield _await(lambda: p.posted("server", "placed"))
    placed = p.posted("server", "placed") or {}
    yield 0.5

    if p.where == VICTIM:
        covered = yield from _strafe(p, mine, other,
                                     lambda: p.posted(SHOOTER, "done") is not None)
        p.check(f"client 2 ran across client 1's line of fire ({ACROSS_CM:.0f} cm or more, "
                "side to side)", covered >= ACROSS_CM, f"{covered:.0f} cm")
        return

    # --- client 1: the pistol, down the sights, at the chest it sees ---------------
    yield _await(lambda: p.get(wc, "Held") is not None
                 and p.get(wc, "Held").get_class().get_name() == placed.get("held"), 5.0)
    held = p.get(wc, "Held")
    p.check("client 1 holds the pistol the server brought to its hand",
            held is not None and held.get_class().get_name() == placed.get("held"),
            str(held))
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield _await(lambda: p.get(wc, "SightAiming")
                 and float(p.get(wc, AIM_SPREAD_VAR)) < SIGHTS_SPREAD_DEG, 5.0)
    yield 0.5
    chest = lambda: other.mesh.get_socket_location(CHEST_BONE)
    seen, rounds = [], 0
    for _ in range(ROUNDS):
        if int(p.get(held, "Loaded")) == 0:
            p.set(wc, ReloadForced, True)
            yield _await(lambda: int(p.get(held, "Loaded")) > 0, 5.0)
            p.set(wc, ReloadForced, False)
        fired = yield from _shoot(p, wc, held, chest, seen)
        rounds += 1 if fired else 0
    p.set(wc, SIGHTS_FORCED_VAR, False)
    p.check(f"client 1 fired {ROUNDS} rounds down the sights at client 2's chest as it "
            "saw it", rounds == ROUNDS, f"{rounds} round(s)")
    p.check(f"...which crossed its line of fire meanwhile ({ACROSS_CM:.0f} cm or more, "
            "side to side)", _spread(seen) >= ACROSS_CM, f"{_spread(seen):.0f} cm")
    p.post("done", {"rounds": rounds, "lag_ms": _lag_ms(), "seen": seen})
    yield _await(lambda: p.posted("server", "judged"))
