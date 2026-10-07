#!/usr/bin/env python3
"""Run Unreal Python without paying for an editor boot every time.

A cold ``UnrealEditor-Cmd -ExecutePythonScript`` costs 35-45 s of boot and
shutdown *regardless of what the script does*. This runner sends the script to
an editor that is **already open** (the file inbox, Content/Python/
uepy_inbox.py, then the engine's multicast remote execution), which turns those
40 s into about one, and falls back to a cold boot when nothing is listening.

    Scripts/dev/uepy.py Scripts/build_npc_blueprints.py
    Scripts/dev/uepy.py Scripts/verify_*.py          # many, ONE boot/connection
    Scripts/dev/uepy.py --summary Scripts/verify_*.py   # counts + failures only
    Scripts/dev/uepy.py -c "import unreal; unreal.log_warning('hi')"
    Scripts/dev/uepy.py --list                       # what is listening?
    Scripts/dev/uepy.py --game --seconds 25          # headless -game run
    Scripts/dev/uepy.py --game --probe Scripts/probes/probe_consume_heal.py
    Scripts/dev/uepy.py --in-game probe.py           # into a running -game
    Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_join.py
    Scripts/dev/uepy.py --net --clients 2 --bots 32 --trace --probe Scripts/probes/probe_net_load.py
    Scripts/dev/uepy.py --cold Scripts/verify_level.py   # force a fresh editor
    Scripts/dev/uepy.py --close-editors              # save, quit, or kill them

**Output.** ``--summary`` prints one line per script (verifier counts, time)
plus its failed checks, traceback tails and Python errors; the full output is
saved under Saved/uepy/runs/ and its path printed. ``--full`` prints it all.
$UEPY_OUTPUT=summary|full sets the default (dev-team sets summary).

**Exit code:** non-zero if any script raised *or any verifier reported a
failed check* -- the suites return normally when checks fail, so the count is
what decides.

**$UEPY_SERVE=<dir>** gives the caller a warm editor of its own: the first
call boots a headless editor serving the inbox in <dir> (uepylib/server.py),
and later calls run in it. It never touches the user's editor. dev-team sets
it per task and stops the editor before its verifier sweep. A script whose
warm editor crashes or hangs under it is run again in a fresh one
(uepylib/warm.py); it is reported as failed only if that one goes too.

**$UEPY_COLD=1** forces every run cold.

The pieces live in Scripts/dev/uepylib (see its __init__ for the map).
"""

import argparse
import json
import os
import re
import sys
import time

from uepylib import cold, editors, game, inbox, net, net_plan, remote, server, warm
from uepylib.paths import (
    editor_inbox, engine_dir, game_inbox, log, saved_uepy, serve_inbox, set_project,
)
from uepylib.summary import format_target, summarize, verdict

QUIET_KEEP = re.compile(r"\[uepy\]|LogPython|Error|Warning|❌|✅|Traceback")
KEEP_RUN_LOGS = 30


class Reporter(object):
    """Prints each target as it finishes, in full or as a summary."""

    def __init__(self, summary_mode, quiet):
        self.summary_mode, self.quiet = summary_mode, quiet
        self.results = []

    def __call__(self, result):
        s = summarize(result.text)
        self.results.append((result, s))
        if self.summary_mode:
            for line in format_target(result, s):
                print(line, flush=True)
            return
        log(f"=== {result.label}")
        for line in result.text.splitlines():
            if self.quiet and not QUIET_KEEP.search(line):
                continue
            print(line, flush=True)
        log(f"--- {result.label} ({result.seconds:.1f}s)"
            + ("" if verdict(result, s) else "  FAILED"))

    @property
    def ok(self):
        return all(verdict(r, s) for r, s in self.results)

    def save(self, json_path=None):
        """Keep the full output (summary mode's safety net), and the JSON."""
        runs = saved_uepy("runs")
        os.makedirs(runs, exist_ok=True)
        path = os.path.join(runs, time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}.log")
        with open(path, "w", encoding="utf-8") as fh:
            for r, _s in self.results:
                fh.write(f"=== {r.label} ({'ok' if r.ok else 'FAILED'}, {r.seconds:.1f}s)\n")
                fh.write(r.text + "\n")
        for old in sorted(os.listdir(runs))[:-KEEP_RUN_LOGS]:
            try:
                os.remove(os.path.join(runs, old))
            except OSError:
                pass
        if self.summary_mode:
            log(f"full output: {path}")
        if json_path:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump([dict(s.as_dict(), label=r.label, ok=verdict(r, s),
                                seconds=r.seconds) for r, s in self.results], fh, indent=1)


def list_listeners(engine):
    _, rem, nodes = remote.discover(engine, project_filter=False)
    rem.stop()
    if not nodes:
        log("multicast: no editor answered (expected on this machine)")
    for n in nodes:
        log(f"multicast: {remote.node_label(n)}")
    for what, directory, fresh in (("editor", editor_inbox(), inbox.EDITOR_FRESH_SECONDS),
                                   ("game", game_inbox(), inbox.GAME_FRESH_SECONDS)):
        beat = inbox.heartbeat(directory, fresh)
        log(f"{what} inbox: {inbox.describe(beat)} -- {directory}" if beat
            else f"{what} inbox: nothing listening in {directory}")
    for proc in editors.find_editors():
        log(f"process: {proc.binary} pid={proc.pid}")


def parse_args():
    ap = argparse.ArgumentParser(
        description="Run Unreal Python in a live editor when there is one.")
    ap.add_argument("scripts", nargs="*", help="script paths to execute in order")
    ap.add_argument("-c", "--code", action="append", default=[],
                    help="inline statement(s) to execute")
    ap.add_argument("--cold", action="store_true",
                    help="force a fresh UnrealEditor-Cmd boot ($UEPY_COLD=1 too)")
    ap.add_argument("--remote-only", action="store_true",
                    help="fail rather than cold boot when no editor is live")
    ap.add_argument("--in-game", action="store_true",
                    help="run in the uepy-launched -game that is running now")
    ap.add_argument("--allow-pie", action="store_true",
                    help="run even though the editor is mid-PIE")
    ap.add_argument("--list", action="store_true",
                    help="list editors, games and inboxes, then exit")
    ap.add_argument("--close-editors", action="store_true",
                    help="save and quit (or kill) this project's editors, then exit")
    ap.add_argument("--game", action="store_true",
                    help="headless -game run instead of a script")
    ap.add_argument("--net", action="store_true",
                    help="a dedicated server and --clients N on this machine, "
                         "instead of a script")
    ap.add_argument("--clients", type=int, default=1, metavar="N",
                    help="with --net: how many clients join (default 1)")
    ap.add_argument("--port", type=int, default=net_plan.DEFAULT_PORT,
                    help=f"with --net: the server's port (default {net_plan.DEFAULT_PORT})")
    ap.add_argument("--bots", type=int, default=0, metavar="N",
                    help="with --net: the server spawns N more characters driven by "
                         "simple AI (Scripts/probes/bots.py), the load test's players "
                         f"(0-{net_plan.MAX_BOTS}, default 0)")
    ap.add_argument("--trace", action="store_true",
                    help=f"with --net: the server writes an Unreal Insights trace "
                         f"(-trace={net_plan.TRACE_CHANNELS}) into the run's folder")
    ap.add_argument("--lag", type=int, default=0, metavar="MS",
                    help="with --net: delay every packet a client sends by MS "
                         "(the engine's Net PktLag), to check prediction")
    ap.add_argument("--probe", action="append", default=[], metavar="FILE",
                    help="with --game or --net: run this probe (Scripts/probes); "
                         "repeatable")
    ap.add_argument("--probe-timeout", type=float,
                    help="wall seconds allowed per probe (default 60)")
    ap.add_argument("--windowed", action="store_true",
                    help="with --game or --net: render (each client) into a "
                         "window instead of -nullrhi")
    ap.add_argument("--title", action="store_true",
                    help="with --game or --net: keep the title menu (no -nomenu), "
                         "for a probe that works it; with --net each client "
                         "starts alone on the level and the probe joins")
    ap.add_argument("--map", default=game.DEFAULT_MAP, help="level for --game and --net")
    ap.add_argument("--seconds", type=int,
                    help=f"--game duration (default {game.GAME_SECONDS}; with "
                         f"--probe, a ceiling of {game.PROBE_SECONDS}); with --net, "
                         f"the play after the last join (default {net.NET_SECONDS}; "
                         f"with --probe, a ceiling of {net.PROBE_SECONDS})")
    ap.add_argument("--grep", action="append", default=[],
                    help="extra regex to count in a --game log")
    out = ap.add_mutually_exclusive_group()
    out.add_argument("--summary", action="store_true",
                     help="one line per script plus its failures (full log saved)")
    out.add_argument("--full", action="store_true", help="print everything")
    ap.add_argument("--json", metavar="FILE", help="write per-script results as JSON")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="drop routine Info lines (full output only)")
    ap.add_argument("--project", help="run against another .uproject (file or directory)")
    ap.add_argument("--boot-timeout", type=int, default=900,
                    help="kill a cold run that overruns (seconds, default 900)")
    ap.add_argument("--engine", help="engine directory override")
    return ap, ap.parse_args()


def main():
    ap, args = parse_args()
    set_project(args.project)
    engine = engine_dir(args.engine)

    if args.list:
        list_listeners(engine)
        return 0
    if args.close_editors:
        _closed, left = editors.close_editors()
        return 1 if left else 0
    if args.net and args.game:
        ap.error("--net and --game are two different runs: pass one")
    if args.net or args.game:
        probes = [os.path.abspath(p) for p in args.probe]
        for p in probes:
            if not os.path.isfile(p):
                sys.exit(f"[uepy] no such probe: {p}")
    if args.net:
        problem = net_plan.check_args(args.clients, args.port, args.seconds, args.lag,
                                      args.bots)
        if problem:
            ap.error(problem)
        ok = net.run_net(engine, args.map, args.clients, args.port, args.seconds, probes,
                         args.probe_timeout, args.windowed, args.allow_pie, args.title,
                         args.lag, args.bots, args.trace)
        return 0 if ok else 1
    if args.game:
        seconds = args.seconds or (game.PROBE_SECONDS if probes else game.GAME_SECONDS)
        extra = [(f"/{p}/", p) for p in args.grep]
        ok = game.run_game(engine, args.map, seconds, extra, probes, args.probe_timeout,
                           args.windowed, args.title)
        return 0 if ok else 1

    targets = [("file", os.path.abspath(s)) for s in args.scripts]
    targets += [("code", c) for c in args.code]
    if not targets:
        ap.error("nothing to run -- pass a script, -c, --game, --net or --list")
    for kind, value in targets:
        if kind == "file" and not os.path.isfile(value):
            sys.exit(f"[uepy] no such script: {value}")

    summary_mode = args.summary or (
        not args.full and os.environ.get("UEPY_OUTPUT", "").lower() == "summary")
    report = Reporter(summary_mode, args.quiet)
    outcome = None
    if args.in_game:
        outcome = inbox.run_inbox(targets, report, game_inbox(), args.allow_pie,
                                  inbox.GAME_FRESH_SECONDS, what="game")
        if outcome is None:
            sys.exit("[uepy] no -game run is listening (start one with --game)")
    else:
        forced_cold = args.cold or os.environ.get("UEPY_COLD") == "1"
        if forced_cold and not args.cold:
            log("UEPY_COLD=1: not using any open editor")
        serve_dir = serve_inbox()
        if serve_dir and forced_cold and server.stop(serve_dir):
            # A cold run writes packages the warm editor would not see, and it
            # would later save its stale copies over them.
            log("stopped this session's warm editor for the cold run; the next "
                "call boots it again")
        if serve_dir and not forced_cold:
            # This caller's own editor: booted on first use, reused after.
            # Never multicast, which could reach the user's editor.
            # warm.run drops each target it reports, so a cold run below
            # (no warm editor could be booted) takes only what is left.
            outcome = warm.run(engine, serve_dir, targets, report, args.allow_pie,
                               args.boot_timeout)
        elif not forced_cold:
            # Inbox first: a single file stat, while multicast discovery costs
            # a fixed 2.5 s and, here, always costs it for nothing.
            outcome = inbox.run_inbox(targets, report, editor_inbox(), args.allow_pie)
            if outcome is None:
                outcome = remote.run_remote(engine, targets, report, args.allow_pie)
            if outcome is None and args.remote_only:
                sys.exit("[uepy] no live editor and --remote-only was given")
        if outcome is None:
            cold.run_cold(engine, targets, report, args.boot_timeout)
            outcome = True
    report.save(args.json)
    return 0 if outcome and report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
