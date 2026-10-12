"""One world clock (M30): every machine of a server shows one time of day.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_world_clock.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_net_world_clock.py

The processes share a wall clock (they are on one machine), so each reads its
own BP_DayNightCycle's Clock at the same wall instants, every STEP_S seconds,
and posts what it read. The server names the instants. A client then holds
its readings against the server's and against every other client's:

  * over the first MINUTE_STEPS instants (a minute) they agree within a
    second, and the clock ran: the task's own measure;
  * a client's own write to its Clock does nothing (the server's stands);
  * the server then moves its Clock by JUMP_S, and at the next instants
    every client has followed: it is the server's clock they show, not a
    clock of their own that happened to start alike;
  * the lengths of day and night are the server's, and the wind's time
    (MPC_Wind.TimeOffset plus this machine's world time) is the server's.

In single player the same graph's authority arm runs: the clock advances
with the world's time, a write to it stands (the WORLD SETTINGS dial, the
other probes), the GameState holds what was published, and the wind's
offset is 0.
"""

SYSTEMS = ('world', 'net')

import time

import unreal

from forest_generator.wind import MPC_PATH, PARAM_TIME_OFFSET
from net import state_consts as S
from world import day_night_vars as DV
from world import world_config as cfg
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world.world_clock import WIND_WRAP_S

WRITABLE = [(DAY_NIGHT_BP_PATH, DV.Clock)]
# A minute of readings, the two after the jump, and the waits for the others.
TIMEOUT = 200.0

STEP_S = 10             # wall seconds between two readings
MINUTE_STEPS = 6        # readings 0..6 span a minute
AFTER_JUMP_STEPS = 2    # readings after the server moved its clock
JUMP_S = 137.0          # how far the server moves it
CLIENT_WRITE_S = 100.0  # how far a client tries to move its own
WITHIN_S = 1.0          # "the same time of day"
WAIT_S = 40.0           # wall seconds a side waits for another's post


def _until(ready, seconds=WAIT_S):
    end = time.time() + seconds
    return lambda: ready() or time.time() > end


def _apart(a, b, cycle):
    """Seconds between two clock readings, the short way round the cycle."""
    d = abs(a - b) % cycle
    return min(d, cycle - d)


def _state(p):
    return unreal.GameplayStatics.get_game_state(p.world())


def _read(p, cycle):
    """One reading: the Clock, and the wind's time as the materials see it."""
    world = p.world()
    here = unreal.GameplayStatics.get_time_seconds(world)
    mpc = unreal.load_asset(MPC_PATH)
    offset = unreal.MaterialLibrary.get_scalar_parameter_value(world, mpc, PARAM_TIME_OFFSET)
    return {"clock": float(p.get(cycle, DV.Clock)),
            "wind": float((here + offset) % WIND_WRAP_S),
            "day": float(p.get(cycle, DV.DayLengthSeconds)),
            "night": float(p.get(cycle, DV.NightLengthSeconds))}


def _hour(reading):
    h = cfg.clock_to_hour(reading["clock"], reading["day"], reading["night"])
    return f"{int(h):02d}:{int(h % 1 * 60):02d}"


def _readings(p, cycle, first, count, between=None):
    """Read at each wall instant first..first+count-1 (in STEP_S); ``between``
    maps an index to something to do just after that reading."""
    got = {}
    for i in range(count):
        at = (first + i) * STEP_S
        yield lambda at=at: time.time() >= at
        got[str(first + i)] = _read(p, cycle)
        if between and i in between:
            between[i]()
            yield 0.2
    return got


def probe_server(p):
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    state = _state(p)
    total = MINUTE_STEPS + 1 + AFTER_JUMP_STEPS
    first = int(time.time() // STEP_S) + 2
    p.post("plan", {"first": first, "count": total})

    def jump():
        cycle_s = p.get(cycle, DV.DayLengthSeconds) + p.get(cycle, DV.NightLengthSeconds)
        p.set(cycle, DV.Clock, (p.get(cycle, DV.Clock) + JUMP_S) % cycle_s)

    held = []

    def note():
        held.append(float(p.get(state, S.WORLD_CLOCK_OFFSET_VAR)))

    got = yield from _readings(p, cycle, first, total,
                               {0: note, MINUTE_STEPS - 1: note, MINUTE_STEPS: jump})
    p.post("readings", got)
    a, b = got[str(first)], got[str(first + MINUTE_STEPS)]
    cycle_s = a["day"] + a["night"]
    ran = (b["clock"] - a["clock"]) % cycle_s
    p.check("the server's clock ran a minute in a minute",
            abs(ran - MINUTE_STEPS * STEP_S) < 2.0,
            f"{_hour(a)} -> {_hour(b)}: {ran:.2f} s of the cycle in "
            f"{MINUTE_STEPS * STEP_S} s")
    p.check("the server published its lengths on the GameState",
            p.get(state, S.WORLD_DAY_LENGTH_VAR) == a["day"]
            and p.get(state, S.WORLD_NIGHT_LENGTH_VAR) == a["night"],
            f"{p.get(state, S.WORLD_DAY_LENGTH_VAR)} / {p.get(state, S.WORLD_NIGHT_LENGTH_VAR)}")
    p.check("...and the offset it published stood still while the clock only ran "
            "(nothing replicates per frame)",
            len(held) == 2 and held[0] == held[1], str(held))
    after = float(p.get(state, S.WORLD_CLOCK_OFFSET_VAR))
    p.check(f"...and moved by the {JUMP_S:.0f} s the clock was moved",
            _apart((held[-1] + JUMP_S) % cycle_s, after, cycle_s) < 0.2,
            f"{held[-1]:.2f} -> {after:.2f}")
    # Stay until every client has read these: a server that ends first takes
    # the clients' world with it.
    yield _until(lambda: all(p.posted(f"client {c}", "done")
                             for c in range(1, p.clients + 1)), 60.0)


def probe_client(p):
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    yield _until(lambda: p.posted("server", "plan"))
    plan = p.posted("server", "plan")
    p.check(f"{p.where} has the server's plan", bool(plan), str(plan))
    if not plan:
        p.post("done")
        return
    first, count = plan["first"], plan["count"]

    def write():
        p.set(cycle, DV.Clock, p.get(cycle, DV.Clock) + CLIENT_WRITE_S)

    got = yield from _readings(p, cycle, first, count, {2: write})
    p.post("readings", got)
    others = ["server"] + [f"client {c}" for c in range(1, p.clients + 1) if c != p.client]
    yield _until(lambda: all(p.posted(o, "readings") for o in others))
    theirs = {o: p.posted(o, "readings") for o in others}
    p.post("done")
    missing = [o for o, r in theirs.items() if not r]
    p.check(f"{p.where} has the readings of {', '.join(others)}", not missing, str(missing))
    if missing:
        return

    minute = [str(first + i) for i in range(MINUTE_STEPS + 1)]
    after = [str(first + i) for i in range(MINUTE_STEPS + 1, count)]
    cycle_s = theirs["server"][minute[0]]["day"] + theirs["server"][minute[0]]["night"]

    def worst(keys, field="clock", wrap=cycle_s):
        return max((_apart(got[k][field], r[k][field], wrap), o, k)
                   for o, r in theirs.items() for k in keys)

    gap, who, k = worst(minute)
    last = minute[-1]
    p.check(f"{p.where}: through a minute its time of day is the server's and every "
            f"other client's within {WITHIN_S:.0f} s",
            gap < WITHIN_S,
            f"worst {gap:.3f} s (against {who}); after the minute it shows "
            f"{_hour(got[last])}, " + ", ".join(
                f"{o} {_hour(r[last])}" for o, r in theirs.items()))
    ran = (got[last]["clock"] - got[minute[0]]["clock"]) % cycle_s
    p.check(f"{p.where}: its clock ran that minute (and its own write of "
            f"+{CLIENT_WRITE_S:.0f} s did nothing)",
            abs(ran - MINUTE_STEPS * STEP_S) < 2.0, f"{ran:.2f} s of the cycle")
    gap, who, k = worst(after)
    moved = (got[after[0]]["clock"] - got[last]["clock"]) % cycle_s
    p.check(f"{p.where}: the server moved its clock {JUMP_S:.0f} s and this client "
            f"followed within {WITHIN_S:.0f} s",
            gap < WITHIN_S and abs(moved - JUMP_S - STEP_S) < 2.0,
            f"worst {gap:.3f} s (against {who}); it moved {moved:.2f} s in {STEP_S} s")
    mine, srv = got[last], theirs["server"][last]
    p.check(f"{p.where}: its day and night are as long as the server's",
            (mine["day"], mine["night"]) == (srv["day"], srv["night"]),
            f"{mine['day']}/{mine['night']} against {srv['day']}/{srv['night']}")
    gap, who, k = worst(minute + after, "wind", WIND_WRAP_S)
    p.check(f"{p.where}: the wind's time in its materials is the server's and every "
            f"other client's within {WITHIN_S:.0f} s",
            gap < WITHIN_S, f"worst {gap:.3f} s (against {who})")


def probe(p):
    """Single player: the authority arm, alone."""
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    state = _state(p)
    world = p.world()
    cycle_s = p.get(cycle, DV.DayLengthSeconds) + p.get(cycle, DV.NightLengthSeconds)
    yield 0.2
    t0, c0 = unreal.GameplayStatics.get_time_seconds(world), p.get(cycle, DV.Clock)
    yield 0.5
    t1, c1 = unreal.GameplayStatics.get_time_seconds(world), p.get(cycle, DV.Clock)
    p.check("single player: the clock advances with the world's time",
            t1 > t0 and abs((c1 - c0) % cycle_s - (t1 - t0)) < 0.05,
            f"clock +{(c1 - c0) % cycle_s:.3f} s in {t1 - t0:.3f} s")
    want = (c1 + JUMP_S) % cycle_s
    p.set(cycle, DV.Clock, want)
    yield 0.3
    t2, c2 = unreal.GameplayStatics.get_time_seconds(world), p.get(cycle, DV.Clock)
    p.check("...a write to it stands (the WORLD SETTINGS dial's way in)",
            _apart(c2, want + (t2 - t1), cycle_s) < 0.5, f"{want:.2f} written, {c2:.2f} read")
    held = p.get(state, S.WORLD_CLOCK_OFFSET_VAR)
    now = state.get_server_world_time_seconds()
    p.check("...the GameState holds the clock as published: the lengths, and an "
            "offset that gives the Clock back",
            p.get(state, S.WORLD_DAY_LENGTH_VAR) == p.get(cycle, DV.DayLengthSeconds)
            and p.get(state, S.WORLD_NIGHT_LENGTH_VAR) == p.get(cycle, DV.NightLengthSeconds)
            and _apart((held + now) % cycle_s, p.get(cycle, DV.Clock), cycle_s) < 0.2,
            f"offset {held:.2f} + time {now:.2f} against Clock {p.get(cycle, DV.Clock):.2f}")
    p.check("...and the wind's offset is 0: the materials keep this machine's time",
            abs(_read(p, cycle)["wind"] - unreal.GameplayStatics.get_time_seconds(world)
                % WIND_WRAP_S) < 1e-3
            and abs(p.get(cycle, DV.WindTimeOffset)) < 1e-6,
            f"WindTimeOffset {p.get(cycle, DV.WindTimeOffset)}")
