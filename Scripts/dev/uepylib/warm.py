"""Running targets in the caller's warm editor, and getting over its crashes.

A warm editor (uepylib/server.py) dies now and then: a second rebuild of the
same Blueprints in one process has segfaulted in the engine, where a cold run
of the same script is fine. A dev-team session that met "the listener stopped
responding" spent minutes on it (ps, the log, kill -9, a guess at whether the
build had finished), and twice sat out a ten-minute timeout behind an editor
that had crashed into its handler with its process still there.

So a target whose editor goes away under it is run once more, in a fresh
editor, without the caller having to notice:

  died      the process is gone (the inbox sees no live heartbeat)
  crashed   the editor's log says ``=== Critical error: ===``; the process may
            sit in the crash handler for a long time, or for good
  stalled   the job is in flight and for STALL_SECONDS the process has used no
            CPU and logged nothing: hung without a word

Targets that already finished are not run again: what they built is on disk,
which is where the fresh editor reads it from. A target that takes the fresh
editor down too is reported as failed, and says so. A plain timeout is not
retried; the editor is killed so the next call is not queued behind it.
"""

import os
import subprocess
import time

from uepylib import inbox, server
from uepylib.paths import log
from uepylib.targets import TargetResult, label_for

CRASH_MARK = b"=== Critical error: ==="
STALL_SECONDS = 180.0
STALL_CPU = 0.5                 # CPU seconds below which a window counts as idle
WATCH_EVERY = 1.0               # seconds between looks at the log
SAMPLE_EVERY = 10.0             # seconds between CPU samples (a ps each)
LOG = "server.log"


def cpu_seconds(pid):
    """The CPU time a process has used, from ps ([[dd-]hh:]mm:ss.ss), or None."""
    ps = subprocess.run(["ps", "-o", "time=", "-p", str(pid)],
                        capture_output=True, text=True)
    return parse_cpu(ps.stdout)


def parse_cpu(text):
    text = text.strip()
    if not text:
        return None
    days, _, clock = text.rpartition("-")
    try:
        total = 0.0
        for part in clock.split(":"):
            total = total * 60 + float(part)
        return total + (int(days) * 86400 if days else 0)
    except ValueError:
        return None


class Watch(object):
    """Called while a job is awaited; returns why the editor is lost, or None.

    It reads what the editor's log gained since the job was sent, and samples
    the process's CPU time; ``clock`` and ``cpu`` are parameters for the tests.
    """

    def __init__(self, directory, pid, clock=time.time, cpu=cpu_seconds):
        self.path = os.path.join(directory, LOG)
        self.pid, self.clock, self.cpu = pid, clock, cpu
        try:
            self.offset = os.path.getsize(self.path)
        except OSError:
            self.offset = 0
        self.tail = b""
        now = clock()
        self.looked = self.sampled = self.moved = now
        self.used = cpu(pid)

    def _read_new(self):
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                new = fh.read()
        except OSError:
            return b""
        self.offset += len(new)
        return new

    def __call__(self):
        now = self.clock()
        if now - self.looked < WATCH_EVERY:
            return None
        self.looked = now
        new = self._read_new()
        if new:
            self.moved = now
            # The mark may straddle two reads.
            seen = self.tail + new
            self.tail = seen[-len(CRASH_MARK):]
            if CRASH_MARK in seen:
                return "the warm editor crashed (a critical error in its log)"
        if now - self.sampled >= SAMPLE_EVERY:
            self.sampled = now
            used = self.cpu(self.pid)
            # A reading that cannot be had is no evidence of a hang.
            if used is None or self.used is None or used - self.used >= STALL_CPU:
                self.used, self.moved = (self.used if used is None else used), now
        if now - self.moved >= STALL_SECONDS:
            return (f"the warm editor hung (no CPU used and nothing logged "
                    f"for {STALL_SECONDS:.0f}s)")
        return None


def run(engine, directory, targets, report, allow_pie=False, boot_timeout=300,
        timeout=inbox.TIMEOUT, make_watch=Watch):
    """Run targets in the warm editor on ``directory``, booting it as needed.
    Returns None if no editor could be had (the caller falls back to a cold
    run for whatever is left: ``targets`` loses each one as it is reported),
    False if a target was lost with its editor twice, else True."""
    retried = False
    while targets:
        if not server.ensure(engine, directory, boot_timeout):
            return None
        beat = inbox.heartbeat(directory) or {}
        log(f"live editor via inbox: {inbox.describe(beat)}")
        while targets:
            kind, value = targets[0]
            label = label_for(kind, value)
            result, why = inbox.run_job(directory, kind, value, allow_pie, timeout=timeout,
                                        watch=make_watch(directory, beat.get("pid")))
            if result is not None:
                report(result)
                targets.pop(0)
                retried = False
                continue
            # Whatever is left of the editor must not serve the next call.
            server.discard(directory)
            if why == inbox.DIED:
                why = "the warm editor died mid-run"
            if why.startswith("timed out") or retried:
                if retried:
                    why += " -- twice, the second time in a fresh editor"
                log(f"{label}: {why}")
                report(TargetResult(label, False, 0.0, why))
                targets.pop(0)
                return False
            log(f"{label}: {why}; running it again in a fresh editor")
            retried = True
            break
    return True
