"""The load test's numbers: what a server and its clients cost with N bots.

    python3 Scripts/dev/uepy.py --net --clients 2 --bots 32 --probe Scripts/probes/probe_net_load.py
    python3 Scripts/dev/uepy.py --net --clients 2 --bots 32 --trace --probe ...   # plus an Insights trace

On the server: once every bot has been spawned (probes/bots.py) and every
client has joined, SETTLE_S of play, then a window of MEASURE_S wall seconds
(the clients open theirs when the server posts that it has) over which it
records, through Source/Otherworld's UOtherworldLoadLibrary: the frame
time and the world-tick time (mean, 99th percentile, max, the rate), each
connection's bytes and packets in and out per second, its open actor
channels (what replicates to it) and its lag, the hit history's characters
and samples, and what the bots did (shots, reloads, deaths). On a client:
its own frame time, its connection to the server the same way, and how many
characters it has. Every figure is a check's detail, and the whole set is
written as load-<process>.json beside the run's logs, for the table in
Scripts/net/CLAUDE.md ("Measured at scale").

Only a check that would make the figures meaningless fails: no frames
sampled, a bot never spawned, a hit history that recorded nothing while
clients were connected. The numbers themselves are the result.
"""

import json
import os
import time

import unreal

from probes import bots
from probes.load_stats import connection_rows, kb, summarize

RUNS_ON = ("server", "client")
TIMEOUT = 420.0              # wall seconds: the waits, the settle and the window
WINDOW = "window"            # the server's post: its window is open
MEASURE_S = float(os.environ.get("UEPY_LOAD_SECONDS") or 90.0)
SETTLE_S = 5.0
BOTS_WAIT_S = 180.0
PAWN_WAIT_S = 30.0


def _await(ready, seconds):
    until = time.time() + seconds
    return lambda: ready() or time.time() > until


def _lib():
    return unreal.OtherworldLoadLibrary


def _snapshot(world):
    """Each connection's totals, read by property name: the struct's fields
    are reached with get_editor_property, not as attributes."""
    def field(c, name):
        return c.get_editor_property(name)
    return [{"name": str(field(c, "Name")), "player": str(field(c, "Player")),
             "in_bytes": int(field(c, "InBytes")),
             "out_bytes": int(field(c, "OutBytes")), "in_packets": int(field(c, "InPackets")),
             "out_packets": int(field(c, "OutPackets")),
             "actor_channels": int(field(c, "ActorChannels")),
             "lag_ms": float(field(c, "AvgLagMs"))}
            for c in _lib().connection_stats(world)]


def _characters(world):
    return len(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Character))


def _times(label):
    return (f"mean {label['mean']:.2f} ms, p99 {label['p99']:.2f} ms, max {label['max']:.1f} ms, "
            f"{label['n']} samples")


def _measure(p):
    """The window: timing on, two snapshots MEASURE_S apart. Yields; leaves
    the figures in the returned dict."""
    world = p.world()
    out = {"where": p.where, "bots": bots.count(), "clients": p.clients}
    _lib().start_frame_timing()
    before = _snapshot(world)
    started = time.time()
    yield _await(lambda: False, MEASURE_S)
    frames = list(_lib().frame_times_ms())
    ticks = list(_lib().world_tick_times_ms())
    _lib().stop_frame_timing()
    seconds = time.time() - started
    after = _snapshot(world)
    out.update(seconds=round(seconds, 1), frame_ms=summarize(frames),
               world_tick_ms=summarize(ticks),
               hz=round(len(frames) / seconds, 1) if seconds else 0.0,
               connections=connection_rows(before, after, seconds),
               characters=_characters(world))
    return out


def _report(p, out):
    p.check(f"{p.where}: frame time over {out['seconds']:.0f} s", out["frame_ms"]["n"] > 0,
            f"{_times(out['frame_ms'])}, {out['hz']} Hz")
    p.check(f"{p.where}: world tick (the frame less the tick-rate sleep)",
            out["world_tick_ms"]["n"] > 0, _times(out["world_tick_ms"]))
    for row in out["connections"]:
        who = f" ({row['player']})" if row.get("player") else ""
        p.check(f"{p.where}: connection {row['name']}{who}", True,
                f"in {kb(row['in_bps'])} ({row['in_pps']} pkt/s), out {kb(row['out_bps'])} "
                f"({row['out_pps']} pkt/s), {row['actor_channels']} actor channels, "
                f"lag {row['lag_ms']} ms")
    p.check(f"{p.where}: characters in its world", True, str(out["characters"]))


def _write(p, out):
    if not p.net.directory:
        return
    path = os.path.join(p.net.directory, f"load-{p.where.replace(' ', '')}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    p.note(f"written to {path}")


def _posed(world):
    """{frames between two poses: how many bodies}, off the server's pose rule
    (UOtherworldPoseLibrary; 0 is a body it does not throttle)."""
    tally = {}
    for body in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Character):
        every = str(unreal.OtherworldPoseLibrary.server_pose_every_frames(body))
        tally[every] = tally.get(every, 0) + 1
    return tally


def probe_server(p):
    want = bots.count()
    if want:
        yield _await(bots.ready, BOTS_WAIT_S)
    status = bots.status()
    p.check(f"the server spawned {want} bot(s)", status["spawned"] >= want,
            f"{status['spawned']} spawned, {status['alive']} alive, {status['seconds']:.0f} s in")
    yield _await(lambda: False, SETTLE_S)
    first = bots.status()
    bots.take_driver_ms()
    p.post(WINDOW)
    out = yield from _measure(p)
    status = bots.status()
    out["driver_ms"] = summarize(bots.take_driver_ms())
    world = p.world()
    out["bots"] = {"want": want, "alive": status["alive"],
                   "shots": status["shots"] - first["shots"],
                   "reloads": status["reloads"] - first["reloads"],
                   "deaths": status["deaths"] - first["deaths"]}
    out["hit_history"] = {"characters": _lib().hit_history_characters(world),
                          "samples": _lib().hit_history_total_samples(world)}
    out["posed"] = _posed(world)
    _report(p, out)
    hist = out["hit_history"]
    posed = out["posed"]
    p.check("the server poses a body by how near a player is (combat/pose_tuning.py): "
            "the bodies by the frames between two poses, at the window's end",
            sum(posed.values()) >= want,
            ", ".join(f"{n} every {'frame' if k == '1' else k + ' frames'}"
                      for k, n in sorted(posed.items(), key=lambda kv: int(kv[0]))))
    p.check("the hit history records every character (a server with clients)",
            hist["samples"] > 0 and hist["characters"] >= want,
            f"{hist['characters']} characters, {hist['samples']} samples"
            + (f" ({hist['samples'] / hist['characters']:.0f} each)" if hist["characters"] else ""))
    b = out["bots"]
    p.check("the bots played through the window", want == 0 or b["shots"] > 0,
            f"{b['alive']}/{want} alive at the end; {b['shots']} shots, {b['reloads']} reloads, "
            f"{b['deaths']} deaths in {out['seconds']:.0f} s")
    p.check("the bot driver's own time per frame (Python, read off the frame time)",
            True, _times(out["driver_ms"]))
    _write(p, out)


def probe_client(p):
    yield _await(lambda: p.pawn() is not None, PAWN_WAIT_S)
    p.check(f"{p.where} has its pawn", p.pawn() is not None)
    yield _await(lambda: p.posted("server", WINDOW), BOTS_WAIT_S + SETTLE_S)
    p.check(f"{p.where} measures the same window as the server",
            bool(p.posted("server", WINDOW)), "the server posted that its window is open")
    out = yield from _measure(p)
    _report(p, out)
    _write(p, out)
