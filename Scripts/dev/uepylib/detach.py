"""Detached runs: ``uepy.py --detach`` starts a --game or --net run and returns,
``--wait <run dir>`` blocks for its report, ``--status`` lists them.

A headless session never hears a background command finish, so it cannot use
run_in_background; it detaches the probe, reads or edits meanwhile, then waits.

A run lives in <Saved/uepy>/detached/<stamp>/:  ``cmd`` (the argv), ``pid`` (of
the wrapper shell), ``report.txt`` (the run's output as it goes) and ``result``
(the run's exit code, written last, atomically: its existence is "finished").
One run at a time: a server and two -nullrhi clients are 12.9 of 16 GB.
"""

import os
import shlex
import subprocess
import sys
import time

from uepylib.paths import log, saved_uepy

POLL_SECONDS = 1.0
KEEP_RUNS = 10
# $1 is the run directory, the rest the run; its exit code lands in result only once complete.
WRAPPER = ('d=$1; shift; "$@" > "$d/report.txt" 2>&1; '
           'echo $? > "$d/result.tmp"; mv "$d/result.tmp" "$d/result"')


def runs_root():
    return saved_uepy("detached")


def _read(run, name):
    try:
        with open(os.path.join(run, name), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def state(run):
    """'done' (result written), 'running', or 'dead' (gone with no result)."""
    if _read(run, "result") is not None:
        return "done"
    pid = _read(run, "pid")
    return "running" if pid and pid.isdigit() and _alive(int(pid)) else "dead"


def runs(root):
    if not os.path.isdir(root):
        return []
    return [os.path.join(root, n) for n in sorted(os.listdir(root))
            if os.path.isdir(os.path.join(root, n))]


def running(root):
    return [r for r in runs(root) if state(r) == "running"]


def start(argv, root, script):
    """Launch ``script argv`` detached. Returns the run directory, or None if one runs."""
    busy = running(root)
    if busy:
        log(f"a detached run is still running: {busy[0]} (--wait it first)")
        return None
    os.makedirs(root, exist_ok=True)
    run = os.path.join(root, time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(run)
    cmd = [sys.executable, script] + argv
    with open(os.path.join(run, "cmd"), "w", encoding="utf-8") as fh:
        fh.write(shlex.join(cmd) + "\n")
    proc = subprocess.Popen(["sh", "-c", WRAPPER, "sh", run] + cmd,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    with open(os.path.join(run, "pid"), "w", encoding="utf-8") as fh:
        fh.write(str(proc.pid))
    for old in runs(root)[:-KEEP_RUNS]:
        if state(old) != "running":
            for n in os.listdir(old):
                os.remove(os.path.join(old, n))
            os.rmdir(old)
    return run


def wait(run, timeout=None, poll=POLL_SECONDS):
    """Block for the run's result, print its report; returns the run's exit code
    (1 on timeout or a run that died)."""
    if not os.path.isdir(run):
        log(f"no such run: {run}")
        return 1
    deadline = None if timeout is None else time.time() + timeout
    while True:
        st = state(run)
        if st != "running":
            break
        if deadline is not None and time.time() >= deadline:
            log(f"timed out after {timeout:g}s waiting for {run} (still running)")
            return 1
        time.sleep(poll)
    report = _read(run, "report.txt")
    if report:
        print(report, flush=True)
    code = _read(run, "result")
    if code is None:
        log(f"the run died without a result: {run}")
        return 1
    return int(code) if code.lstrip("-").isdigit() else 1


def status(root):
    for run in runs(root):
        st = state(run)
        code = _read(run, "result")
        log(f"{run}  {st}" + (f" (exit {code})" if code is not None else "")
            + f"  {_read(run, 'cmd') or ''}")
    if not runs(root):
        log("no detached runs")
    return 0
