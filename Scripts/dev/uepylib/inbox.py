"""The file-based inbox (Content/Python/uepy_inbox.py), client side.

The engine's own remote execution discovers editors over UDP multicast, which
does not work on this machine: a plain Python sender/receiver pair on
239.0.0.1 delivers nothing on lo0 *or* en0, with no Unreal in the picture
(macOS Local Network privacy drops it silently). The editor binds its socket
and ticks happily and never hears a ping. So there is a second transport that
needs no network at all -- a request/result directory the editor polls on its
Slate tick.

Two directories: the UI editor's (Saved/uepy) and the one a uepy-launched
-game run polls (Saved/uepy/game). Sharing one let a job meant for the editor
be taken by whichever process polled first.
"""

import json
import os
import time
import uuid

from uepylib.paths import log
from uepylib.targets import TargetResult, label_for

EDITOR_FRESH_SECONDS = 6.0    # a heartbeat older than this means "not running"
# A -game run beats only when it gets a frame, and a busy headless frame can
# take many seconds: 6 s declared a live game dead mid-job.
GAME_FRESH_SECONDS = 30.0
POLL = 0.05
TIMEOUT = 1800.0


def heartbeat(directory, fresh=EDITOR_FRESH_SECONDS):
    """The listener's liveness record, or None."""
    try:
        with open(os.path.join(directory, "heartbeat"), encoding="utf-8") as fh:
            beat = json.load(fh)
    except (OSError, ValueError):
        return None
    if time.time() - float(beat.get("time", 0)) > fresh:
        return None
    # A killed process leaves its last beat behind, still "fresh" for a while.
    if not pid_alive(beat.get("pid")):
        return None
    return beat


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (TypeError, ValueError):
        return True             # no pid recorded: trust the timestamp
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def describe(beat):
    return (f"pid={beat.get('pid')} {os.path.basename(str(beat.get('project')))}"
            + (" [PIE]" if beat.get("pie") else ""))


def send(directory, kind, value, allow_pie=False):
    """Queue one job; returns the path its result will appear at."""
    job_id = uuid.uuid4().hex[:12]
    tmp = os.path.join(directory, job_id + ".request.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"kind": kind, "value": value, "allow_pie": allow_pie}, fh)
    # Atomic rename so the listener never reads a half-written request.
    os.replace(tmp, os.path.join(directory, job_id + ".request"))
    return os.path.join(directory, job_id + ".result")


def _collect(result_path, directory, fresh, timeout):
    """Wait for a result. Returns (dict or None, why-not)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(result_path):
            try:
                with open(result_path, encoding="utf-8") as fh:
                    result = json.load(fh)
                os.remove(result_path)
                return result, ""
            except (OSError, ValueError):
                pass
        if heartbeat(directory, fresh) is None and not os.path.exists(result_path):
            # Take the job back, or the next listener to start would run it.
            try:
                os.remove(result_path[: -len(".result")] + ".request")
            except OSError:
                pass
            return None, "the listener stopped responding -- is it still running?"
        time.sleep(POLL)
    return None, f"timed out after {timeout:.0f}s"


def run_inbox(targets, report, directory, allow_pie=False, fresh=EDITOR_FRESH_SECONDS,
              timeout=TIMEOUT, what="editor"):
    """Run targets through the inbox at ``directory``. Returns None if nothing
    is listening, else False if the listener died, else True."""
    beat = heartbeat(directory, fresh)
    if not beat:
        return None
    log(f"live {what} via inbox: {describe(beat)}")
    for kind, value in targets:
        label = label_for(kind, value)
        result_path = send(directory, kind, value, allow_pie)
        result, why = _collect(result_path, directory, fresh, timeout)
        if result is None:
            log(f"{label}: {why}")
            report(TargetResult(label, False, 0.0, why))
            return False
        text = str(result.get("output", "")).rstrip()
        report(TargetResult(label, result.get("success"),
                            result.get("seconds", 0.0), text))
    return True

