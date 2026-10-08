"""The slide is predicted (task G5): under lag the owning client slides at
once out of its sprint and the server slides its copy by the same rule, so
nothing pulls the player back; and the crouch under it is the server's too.

    python3 Scripts/dev/uepy.py --net --clients 1 --lag 120 \
        --probe Scripts/probes/probe_net_slide.py

The slide is a state of the C++ movement component (Source/Otherworld,
UOtherworldCharacterMovement: one press as a saved-move flag, the slide's
clock and way restored with a combined move and carried by a correction).

    client 1   sprints forward, presses the crouch key (CrouchForced) and
               lets everything go: it slides on its own machine at once,
               coasting faster than a crouch walks, for the slide's second,
               and takes no correction through it. It ends crouched.
    the server has the same character sliding while the client says it is,
               in the crouch's capsule, and crouched (not sliding) after.

With `--clients 2`, client 2 would see the slide through the character's
replicated bSliding; that copy's pose is the weapon layers' PoseSlide, which
this probe does not read.
"""

import math
import time

import unreal

from combat import gas_moves_tuning as T
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.sprint_tuning import SPRINT_FORCED_VAR
from combat.tuning import COMBAT
from combat.weapon_component.stance import CROUCH_FORCED_VAR

RUNS_ON = ("server", "client 1")
WRITABLE = [(WEAPON_COMP_BP_PATH, SPRINT_FORCED_VAR), (WEAPON_COMP_BP_PATH, CROUCH_FORCED_VAR)]

MOVE = unreal.OtherworldMovementLibrary
WAIT = 30.0
MIN_PING_MS = 100.0
CROUCH_PACE = COMBAT.jog_speed_cms * COMBAT.crouch_speed_scale


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _speed(pawn):
    v = pawn.get_velocity()
    return math.hypot(v.x, v.y)


def _forward(pawn):
    yaw = math.radians(pawn.get_actor_rotation().yaw)
    pawn.add_movement_input(unreal.Vector(math.cos(yaw), math.sin(yaw), 0.0), 1.0, False)


def _half_height(pawn):
    return pawn.get_editor_property("capsule_component").get_unscaled_capsule_half_height()


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None)
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    move = MOVE.get_otherworld_movement(pawn)
    if not T.GAS_SLIDE or not move.get_editor_property("slide_enabled"):
        p.note("the slide is off (GAS_SLIDE, or no motion-matching body): nothing to probe")
        p.post("done")
        return
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    count = lambda: move.get_editor_property("correction_count")
    state = pawn.get_editor_property("player_state")
    yield from _await(lambda: state.get_ping_in_milliseconds() >= MIN_PING_MS, 8.0)
    ping = state.get_ping_in_milliseconds()
    p.check(f"the run is lagged: {p.where}'s ping is at least {MIN_PING_MS:.0f} ms "
            "(uepy.py --net --lag 120)", ping >= MIN_PING_MS, f"{ping:.0f} ms")

    yield 1.0
    p.set(wc, SPRINT_FORCED_VAR, True)
    start = now()
    while now() - start < 2.0:
        _forward(pawn)
        yield 0.0
    fast, before = _speed(pawn), count()
    p.set(wc, CROUCH_FORCED_VAR, True)
    pressed = now()
    while not MOVE.is_sliding(pawn) and now() - pressed < 0.5:
        _forward(pawn)                  # a sprint is a sprint only while steered ahead
        yield 0.0
    waited = now() - pressed
    p.set(wc, SPRINT_FORCED_VAR, False)
    p.post("sliding")
    track, began = [], now()
    while now() - began < T.SLIDE_SECONDS + 1.0:
        yield 0.0
        if MOVE.is_sliding(pawn):
            track.append((now() - began, _speed(pawn), _half_height(pawn)))
    taken = count() - before
    p.check(f"{p.where} slides on its own machine at once out of its sprint "
            f"({fast:.0f} cm/s), not a round trip later",
            bool(track) and waited < 0.1 and fast > 0.9 * COMBAT.sprint_speed_cms,
            f"sliding {waited * 1000:.0f} ms after the press, at {ping:.0f} ms ping")
    if track:
        mid = [s for t, s, _h in track if 0.2 < t < 0.5]
        p.check(f"...coasting faster than a crouch walks, for {T.SLIDE_SECONDS:g} s, in the "
                "crouch's capsule",
                mid and min(mid) > CROUCH_PACE + 50.0
                and abs(track[-1][0] - T.SLIDE_SECONDS) < 0.2
                and all(abs(h - COMBAT.crouch_half_height_cm) < 1.5 for _t, _s, h in track[3:]),
                f"{track[0][1]:.0f} -> {track[-1][1]:.0f} cm/s over {track[-1][0]:.2f} s")
    p.check(f"...and the server agreed: no correction through the slide at {ping:.0f} ms",
            taken == 0, f"{taken} correction(s)")
    p.check("it ends crouched, not sliding",
            not MOVE.is_sliding(pawn) and MOVE.get_stance(pawn) == 1,
            f"stance {MOVE.get_stance(pawn)}")
    p.post("slid")
    yield 1.0
    # Standing again, for whatever probe shares this game.
    p.set(wc, CROUCH_FORCED_VAR, True)
    yield 1.0
    p.post("done")


def probe_server(p):
    yield from _await(lambda: len(p.players()) >= p.clients
                      and all(c.get_controlled_pawn() for c in p.players()))
    pawns = [c.get_controlled_pawn() for c in p.players()]
    yield from _await(lambda: p.posted("client 1", "sliding") or p.posted("client 1", "done"))
    if p.posted("client 1", "done") and not p.posted("client 1", "sliding"):
        return
    seen = []
    until = time.time() + 4.0
    while time.time() < until and not p.posted("client 1", "slid"):
        yield 0.0
        seen += [(_speed(a), _half_height(a)) for a in pawns if MOVE.is_sliding(a)]
    p.check("the server slides the same character by its own rule: sliding, faster than "
            "a crouch walks, in the crouch's capsule",
            len(seen) > 5 and max(s for s, _h in seen) > CROUCH_PACE + 50.0
            and all(abs(h - COMBAT.crouch_half_height_cm) < 1.5 for _s, h in seen[3:]),
            f"{len(seen)} sliding frames, up to {max((s for s, _h in seen), default=0):.0f} cm/s")
    yield from _await(lambda: p.posted("client 1", "slid"), 8.0)
    yield 0.5
    p.check("...and has it crouched, not sliding, once the slide is over",
            all(not MOVE.is_sliding(a) for a in pawns)
            and any(MOVE.get_stance(a) == 1 for a in pawns),
            str([MOVE.get_stance(a) for a in pawns]))
    yield from _await(lambda: p.posted("client 1", "done"), 15.0)
