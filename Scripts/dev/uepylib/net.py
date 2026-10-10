"""A network run: one dedicated server and N clients on this machine.

``uepy.py --net --clients N`` starts them all at once (net_plan.py), each from
the editor binary with a log, an inbox and a results file of its own in
Saved/uepy/net/<stamp>/. Scripts/probes/boot.py runs in each: the clients
wait in an empty map until the server's level is up, join, and every process
then runs the probes meant for it (Scripts/probes/net.py). The run ends when
the last process has written its results -- with no probe, ``--seconds``
after everyone has joined -- and all of them are killed, the clients first.
One report follows (net_report.py).

A kill is recorded by the engine as a crash via GracefulTerminationHandler:
expected, as in a --game run.
"""

import glob
import json
import os
import shutil
import subprocess
import time

from uepylib import editors, game, inbox, net_memory, net_plan, net_report
from uepylib.paths import editor_cmd, log, saved_uepy, serve_inbox, uproject

# With no probe: how long everyone plays after the last client has joined.
NET_SECONDS = 20
# The ceiling on a probe run, boots included (three editor binaries at once).
PROBE_SECONDS = 420
# How long the boots and the joins may take before a run with no probe gives up.
JOIN_SECONDS = 300
KEEP_RUNS = 10
POLL = 0.25
# Scripts/probes/kept_slots.py's suffix: what the server set aside for the run.
KEPT_BACKUP = ".probe-backup"


def pie_editor():
    """An open editor of this project that is mid-PIE (its inbox's beat), or None."""
    for directory in filter(None, (saved_uepy(), serve_inbox())):
        beat = inbox.heartbeat(directory)
        if beat and beat.get("pie"):
            return beat
    return None


def run_dir():
    """A fresh folder for this run; all but the last few runs' are dropped."""
    root = saved_uepy("net")
    os.makedirs(root, exist_ok=True)
    for old in sorted(os.listdir(root))[:-(KEEP_RUNS - 1)]:
        shutil.rmtree(os.path.join(root, old), ignore_errors=True)
    path = os.path.join(root, time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}")
    os.makedirs(path)
    return path


def put_back_kept(save_dir):
    """The tuning tabs' save slots the server set aside (probes/kept_slots.py),
    put back once every process is gone."""
    for backup in glob.glob(os.path.join(save_dir, "*" + KEPT_BACKUP)):
        live = backup[:-len(KEPT_BACKUP)]
        if os.path.exists(live):
            os.remove(live)
        shutil.move(backup, live)


def _read(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _wait(running, seconds, has_probes, meter):
    """Until every process has written its results (then, with no probe, the
    play time on top), one of them has died, or the ceiling. ``meter`` reads
    every process's memory on the way."""
    deadline = time.time() + (seconds if has_probes else JOIN_SECONDS)
    joined_at = None
    next_read = 0.0
    while time.time() < deadline:
        if time.time() >= next_read:
            meter.read(running)
            next_read = time.time() + net_memory.EVERY
        if any(proc.poll() is not None for _p, proc in running):
            return
        if joined_at is None and all(os.path.exists(p.results) for p, _proc in running):
            if has_probes:
                return
            joined_at = time.time()
            deadline = joined_at + seconds
            log(f"everyone has joined; playing for {seconds}s")
        time.sleep(POLL)


def run_net(engine, level, clients, port, seconds=None, probes=(), probe_timeout=None,
            windowed=False, allow_pie=False, title=False, lag_ms=0, bots=0, trace=False,
            collect=None):
    """Run the server and the clients, print the report. True when clean.
    ``collect``, a list, receives (probe name, passed) per probe asked for,
    passed only when every process that ran it passed (uepylib/game.py)."""
    beat = pie_editor()
    if beat and not allow_pie:
        log(f"the editor ({inbox.describe(beat)}) is in PIE -- a network run beside a "
            "running game would starve both. Stop PIE, or pass --allow-pie.")
        return False
    open_editors = editors.find_editors()
    if open_editors:
        log(f"{len(open_editors)} editor(s) of this project are open: a network run "
            f"wants their memory (uepy.py --close-editors)")
    seconds = seconds or (PROBE_SECONDS if probes else NET_SECONDS)
    folder = run_dir()
    plan = net_plan.processes(folder, clients)
    what = f"{len(probes)} probe(s)" if probes else f"{seconds}s of play"
    if title:
        what += ", the clients starting alone on the title"
    if lag_ms:
        what += f", each client's packets {lag_ms} ms late"
    if bots:
        what += f", {bots} bot(s) on the server"
    if trace:
        what += ", the server traced"
    log(f"--net: a server and {clients} client(s) on {level}, port {port}, {what} "
        f"-> {folder}")
    started = time.time()
    editor, project = editor_cmd(engine), uproject()
    running = []
    meter = net_memory.Meter()
    try:
        for process in plan:
            os.makedirs(process.inbox, exist_ok=True)
            running.append((process, subprocess.Popen(
                net_plan.command(editor, project, process, port, windowed, level, lag_ms,
                                 trace),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=net_plan.environment(os.environ, process, folder, clients, port,
                                         level, list(probes), probe_timeout, title, bots))))
        _wait(running, seconds, bool(probes), meter)
    finally:
        meter.read(running)
        exits = {}
        for process, proc in reversed(running):      # the clients, then the server
            exits[process.name] = proc.poll()
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        put_back_kept(os.path.join(os.path.dirname(project), "Saved", "SaveGames"))
    reports = [net_report.ProcessReport(p.name, _read(p.log), _read_json(p.results),
                                        exits.get(p.name), p.log) for p in plan]
    names = [os.path.splitext(os.path.basename(p))[0] for p in probes]
    lines, ok = net_report.report(reports, clients, names,
                                  net_memory.lines(meter.usage, [p.name for p in plan]))
    for line in lines:
        print(line, flush=True)
    if collect is not None and probes:
        collect.extend(game.asked_verdicts(probes, [r.payload for r in reports]))
    log(f"{time.time() - started:.0f}s; one log per process in {folder}")
    if trace:
        path = plan[0].trace
        log(f"the server's trace: {path}" if os.path.exists(path)
            else f"no trace was written at {path}")
    return ok
