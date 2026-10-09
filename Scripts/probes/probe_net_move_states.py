"""Sprint, prone and the aim-walk are predicted: under lag the owning client
moves at once and the server agrees, so nothing pulls the player back (M12).

    python3 Scripts/dev/uepy.py --net --clients 1 --lag 120 \
        --probe Scripts/probes/probe_net_move_states.py

The movement component (C++, Source/Otherworld; combat/player_move.py) logs
one MOVE-CORRECTION line each time the server puts the client back on its
own answer, and counts them. With every packet 120 ms late:

    client 1   walks forward through each change of state in turn: the jog,
               a sprint started, the sprint stopped, a crouch, prone, standing again,
               the aim-walk, the aim let go. Each state reaches its own
               speed on the client at once, and the stretch takes no
               correction. Then the two controls: it is told to sprint
               faster than the server allows, which the server corrects
               (so the count does see rubber-banding), and the server takes
               stamina off it, which reaches its bar.
    the server sees the same character sprint, lie down at prone's height
               and walk at the aim's speed: the states are the server's too,
               not the client's word.

Run without --lag it fails its first check: over loopback a misprediction
is corrected before it shows.

Single player (`uepy.py --game --probe <this>`) walks the same states with
no server to disagree: each has its speed, a crouch its own, and stamina
spent is off the bar. It is the check that the feel did not change.
"""

SYSTEMS = ('net', 'movement')

import math
import os
import re
import time

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.sprint_tuning import SPRINT_FORCED_VAR
from combat.tuning import COMBAT
from combat.weapon_component.ads import AIM_FORCED_VAR
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR, STAND

RUNS_ON = ("server", "client 1", "standalone")
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in (SPRINT_FORCED_VAR, AIM_FORCED_VAR, STANCE_VAR)]

MOVE = unreal.OtherworldMovementLibrary
WAIT = 30.0             # wall seconds any wait may take
MIN_PING_MS = 100.0     # what --lag 120 has to show before the run means anything
STRETCH_S = 1.5         # game seconds in each state: several round trips
NEAR = 0.12             # a state's speed, give or take
TOO_FAST_CMS = 900.0    # the control: a sprint the server does not allow
SPENT = 40.0            # the control: stamina the server takes

JOG = COMBAT.jog_speed_cms
SPEEDS = {"jog": JOG, "sprint": COMBAT.sprint_speed_cms,
          "crouch": JOG * COMBAT.crouch_speed_scale,
          "prone": JOG * COMBAT.prone_speed_scale,
          "aim": JOG * COMBAT.ads_move_speed_scale}


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


def _own_log_corrections(p):
    """MOVE-CORRECTION lines in this process's own log (uepylib/net_plan.py
    names it), or None when it cannot be read."""
    path = os.path.join(os.environ.get("UEPY_NET_DIR", ""),
                        p.where.replace(" ", "") + ".log")
    try:
        with open(path, errors="replace") as f:
            return len(re.findall(r"MOVE-CORRECTION", f.read()))
    except OSError:
        return None


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None)
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    move = MOVE.get_otherworld_movement(pawn)
    p.check(f"{p.where}'s character has the predicting movement component",
            move is not None and wc is not None, str(move))
    if move is None or wc is None:
        return
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    count = lambda: move.get_editor_property("correction_count")

    ping = 0.0
    if p.is_client:
        state = pawn.get_editor_property("player_state")
        yield from _await(lambda: state.get_ping_in_milliseconds() >= MIN_PING_MS, 8.0)
        ping = state.get_ping_in_milliseconds()
        p.check(f"the run is lagged: {p.where}'s ping is at least {MIN_PING_MS:.0f} ms "
                f"(uepy.py --net --lag 120)", ping >= MIN_PING_MS, f"{ping:.0f} ms")

    def stretch(label, want, told=None):
        """Walk forward for STRETCH_S in the state just set. Returns
        (corrections taken, the speed it settled at, seconds to get near it)."""
        before, t0 = count(), now()
        reached, speeds = None, []
        while now() - t0 < STRETCH_S:
            _forward(pawn)
            yield 0.0
            speeds.append(_speed(pawn))
            if reached is None and abs(speeds[-1] - want) < NEAR * want:
                reached = now() - t0
            if told and not p.posted(p.where, told) and now() - t0 > STRETCH_S * 0.4:
                p.post(told)
        tail = sorted(speeds[len(speeds) // 2:])
        results.append((label, count() - before, tail[len(tail) // 2] if tail else 0.0,
                        reached, want))

    results = []
    yield 1.0                                   # the spawn's own settling
    yield from stretch("the jog", SPEEDS["jog"])
    p.set(wc, SPRINT_FORCED_VAR, True)
    yield from stretch("a sprint started", SPEEDS["sprint"], told="sprinting")
    p.set(wc, SPRINT_FORCED_VAR, False)
    yield from stretch("the sprint stopped", SPEEDS["jog"])
    p.set(wc, STANCE_VAR, CROUCH)
    yield from stretch("crouching", SPEEDS["crouch"])
    crouched = _half_height(pawn)
    p.set(wc, STANCE_VAR, PRONE)
    yield from stretch("going prone", SPEEDS["prone"], told="prone")
    height = _half_height(pawn)
    p.set(wc, STANCE_VAR, STAND)
    yield from stretch("standing up again", SPEEDS["jog"])
    p.set(wc, AIM_FORCED_VAR, True)
    yield from stretch("aiming", SPEEDS["aim"], told="aiming")
    aimed = bool(p.get(wc, "Aiming"))
    p.set(wc, AIM_FORCED_VAR, False)
    yield from stretch("the aim let go", SPEEDS["jog"])

    for label, taken, settled, reached, want in results:
        p.check(f"{label}: {p.where} moves at {want:.0f} cm/s at once, on its own "
                f"prediction", reached is not None and abs(settled - want) < NEAR * want,
                f"settled at {settled:.0f} cm/s, near it after "
                f"{'never' if reached is None else f'{reached:.2f} s'}")
        if p.is_client:
            p.check(f"...and the server agreed: no correction in that {STRETCH_S:g} s at "
                    f"{ping:.0f} ms", taken == 0, f"{taken} correction(s)")
    p.check(f"a crouch is the crouch's capsule and prone is prone's, on {p.where}",
            abs(crouched - COMBAT.crouch_half_height_cm) < 0.5
            and abs(height - COMBAT.prone_half_height_cm) < 0.5,
            f"half heights {crouched:.1f}, {height:.1f}")
    p.check("the aim was an aim: the weapon component's Aiming", aimed)
    if not p.is_client:
        # Single player: the one machine is the server, so it spends its own.
        full = move.get_editor_property("stamina")
        MOVE.spend_stamina(pawn, SPENT)
        yield 0.1
        left = p.get(wc, "Stamina")
        p.check(f"stamina spent ({SPENT:g}, as a blocked blow does) is off the bar",
                full - SPENT - 1.0 < left < full - SPENT + 5.0, f"{full:.1f} -> {left:.1f}")
        return
    clean = count()
    p.check(f"{p.where} took no correction through all eight changes of state",
            clean == 0, f"{clean} in all")

    # --- the control: the count does see a misprediction ----------------------
    p.set(move, "sprint_speed", TOO_FAST_CMS)
    p.set(wc, SPRINT_FORCED_VAR, True)
    t0 = now()
    while now() - t0 < STRETCH_S:
        _forward(pawn)
        yield 0.0
    p.set(wc, SPRINT_FORCED_VAR, False)
    p.set(move, "sprint_speed", COMBAT.sprint_speed_cms)
    yield 0.5
    pulled = count() - clean
    p.check(f"the control: sprinting at {TOO_FAST_CMS:.0f} cm/s on the client's word "
            f"alone is corrected by the server, and counted", pulled > 0,
            f"{pulled} correction(s)")

    # --- and the stamina is the server's ---------------------------------------
    yield from _await(lambda: move.get_editor_property("stamina")
                      >= COMBAT.max_stamina - 1.0, 20.0)
    full = move.get_editor_property("stamina")
    p.post("spend")
    yield from _await(lambda: move.get_editor_property("stamina") < full - SPENT / 2, 10.0)
    left = move.get_editor_property("stamina")
    yield 0.2
    p.check(f"stamina the server takes ({SPENT:g}, as a blocked blow does) comes off "
            f"the client's bar", left < full - SPENT / 2
            and p.get(wc, "Stamina") < full - SPENT / 2,
            f"{full:.1f} -> {left:.1f}, the weapon component's copy "
            f"{p.get(wc, 'Stamina'):.1f}")
    logged = _own_log_corrections(p)
    p.check("each correction is one MOVE-CORRECTION line in the client's log",
            logged is not None and logged == count(), f"{logged} lines, {count()} counted")
    p.post("done")


def probe_server(p):
    yield from _await(lambda: len(p.players()) >= p.clients
                      and all(c.get_controlled_pawn() for c in p.players()))
    pawns = [c.get_controlled_pawn() for c in p.players()]
    moves = {a: MOVE.get_otherworld_movement(a) for a in pawns}
    p.check("every player's character has the predicting movement component on "
            "the server", pawns and all(moves.values()), str(len(pawns)))
    if not pawns or not all(moves.values()):
        return

    def seen(told, test):
        """Once client 1 says it is in a state, does the server hold a
        character in it, within a moment?"""
        yield from _await(lambda: p.posted("client 1", told) or p.posted("client 1", "done"))
        found = []
        yield from _await(lambda: bool(found.extend(
            a for a in pawns if not found and test(a, moves[a])) or found), 3.0)
        return found[0] if found else None

    def near(a, name):
        return abs(_speed(a) - SPEEDS[name]) < NEAR * SPEEDS[name]

    runner = yield from seen("sprinting", lambda a, m: m.get_editor_property("sprinting")
                             and near(a, "sprint"))
    p.check(f"the server has the character sprinting, at {SPEEDS['sprint']:.0f} cm/s",
            runner is not None, ", ".join(f"{_speed(a):.0f} cm/s" for a in pawns))
    if runner is not None:
        spent = moves[runner].get_editor_property("stamina")
        p.check("...and its own stamina for it is draining", spent < COMBAT.max_stamina - 1.0,
                f"{spent:.1f}")
    low = yield from seen("prone", lambda a, m: m.get_editor_property("wants_prone")
                          and abs(_half_height(a) - COMBAT.prone_half_height_cm) < 0.5
                          and near(a, "prone"))
    p.check(f"the server has it prone: a {COMBAT.prone_half_height_cm:.0f} cm capsule "
            f"at {SPEEDS['prone']:.0f} cm/s", low is not None,
            ", ".join(f"{_half_height(a):.0f} cm, {_speed(a):.0f} cm/s" for a in pawns))
    slow = yield from seen("aiming", lambda a, m: m.get_editor_property("wants_aim_walk")
                           and near(a, "aim"))
    p.check(f"the server has it aim-walking, at {SPEEDS['aim']:.0f} cm/s",
            slow is not None, ", ".join(f"{_speed(a):.0f} cm/s" for a in pawns))

    yield from _await(lambda: p.posted("client 1", "spend") or p.posted("client 1", "done"),
                      90.0)
    mover = runner or pawns[0]
    MOVE.spend_stamina(mover, SPENT)
    yield from _await(lambda: p.posted("client 1", "done"), 30.0)


def probe(p):
    """Single player: the same walk, with no server to disagree."""
    yield from probe_client(p)
