"""The five-hour session limit: waited out instead of died on.

A run that reaches the limit used to lose the rest of its night: the session
in hand ended with a 429 ("You've hit your session limit"), the task was
marked FAILED and the run stopped, idle until someone restarted it. Now:

- Before a session starts, when the latest reading (Meter) puts the window
  at WAIT_THRESHOLD or more, dev-team sleeps until it resets. At the start
  of a run the reading is the newest transcript's, so a run started while
  the limit is spent waits before its first session, triage included.
- A session the limit stops part way is not a failure. dev-team waits for
  the reset and resumes the same session (session.LIMIT_RESUMED); one that
  had not started yet is started again.

The reading is the last ``rate_limit_event`` any session streamed: this
run's once it has one (Meter.see), before that the newest transcript in
Saved/DevTeam (last_seen). A reading whose window has since reset counts as
an empty window. The reset time comes from the same event (``resetsAt``,
epoch seconds), with MARGIN on top. With no reset time on record dev-team
waits FALLBACK and tries again. Typing ``pause`` while it waits ends the
wait (devteam/pause.py takes it from there).
"""

import contextlib
import glob
import json
import os
import time

from devteam.accounting import describe_time

WINDOW = "five_hour"
WAIT_THRESHOLD = 0.95
MARGIN = 60             # seconds after resetsAt before the first request
FALLBACK = 10 * 60      # the wait when no reset time is on record
TICK = 30               # how often a wait looks for a typed pause


def utilization(info, now):
    """The session window's used share (0-1) in a rate_limit_info, 0.0 if that
    window has reset since, None if it holds no reading."""
    window = ((info or {}).get("unifiedWindows") or {}).get(WINDOW) or {}
    used = window.get("utilization")
    if not isinstance(used, (int, float)) or isinstance(used, bool):
        return None
    resets = window.get("resetsAt")
    if isinstance(resets, (int, float)) and resets <= now:
        return 0.0
    return float(used)


def last_seen(log_root):
    """The newest rate_limit_info in the transcripts under log_root, or None."""
    logs = sorted(glob.glob(os.path.join(log_root, "*", "task-*.jsonl")),
                  key=os.path.getmtime, reverse=True)
    for path in logs[:5]:
        found = None
        try:
            with open(path, errors="replace") as fh:
                for line in fh:
                    if '"rate_limit_event"' not in line:
                        continue
                    try:
                        found = json.loads(line).get("rate_limit_info") or found
                    except ValueError:
                        pass
        except OSError:
            continue
        if found:
            return found
    return None


class Meter(object):
    """The latest reading of the session limit."""

    def __init__(self, info=None):
        self.info = info

    def see(self, info):
        """A session streamed a rate_limit_event."""
        if info:
            self.info = info


def reset_at(info):
    """When the window the reading is about resets (epoch seconds), or None."""
    info = info or {}
    window = (info.get("unifiedWindows") or {}).get(WINDOW) or {}
    for value in (info.get("resetsAt"), window.get("resetsAt")):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def spent(info, now):
    """True when the reading says the window is at WAIT_THRESHOLD or more
    and has not reset since."""
    used = utilization(info, now)
    return used is not None and used >= WAIT_THRESHOLD


def limited(result):
    """True when a session's result event says the limit stopped it."""
    if not result or not result.get("is_error"):
        return False
    if result.get("api_error_status") == 429:
        return True
    return "session limit" in (result.get("result") or "").lower()


def clock(epoch):
    return time.strftime("%H:%M", time.localtime(epoch))


def wait(meter, pauser=None, refused=False, now=time.time, sleep=time.sleep, say=print):
    """Sleep until the window resets when it is spent. ``refused`` says a
    session was just stopped by the limit, whatever the reading says.
    Returns the seconds waited, 0 when there was room."""
    started = now()
    if not refused and not spent(meter.info, started):
        return 0
    until = reset_at(meter.info)
    if until is None or until <= started:
        if not refused:
            return 0
        until = started + FALLBACK
        say("dev-team: the session limit is spent and no reset time is on record; "
            f"waiting {describe_time(FALLBACK * 1000)}")
    else:
        until += MARGIN
        used = utilization(meter.info, started)
        say(f"dev-team: session limit at {used:.0%}; sleeping until {clock(until)} "
            f"({describe_time((until - started) * 1000)})")
    watching = pauser.watching if pauser else (lambda: contextlib.nullcontext())
    with watching():
        while now() < until and not (pauser and pauser.requested):
            sleep(max(0, min(TICK, until - now())))
    waited = now() - started
    if not (pauser and pauser.requested):
        say("dev-team: the session limit has reset; carrying on")
    return waited
