"""The five-hour session limit: waited out instead of died on.

A run that reaches the limit used to lose the rest of its night: the session
in hand ended with a 429 ("You've hit your session limit"), the task was
marked FAILED and the run stopped, idle until someone restarted it. Now:

- Before a session starts, when the latest reading (fast.Meter) puts the
  window at WAIT_THRESHOLD or more, dev-team sleeps until it resets. At the
  start of a run the reading is the newest transcript's, so a run started
  while the limit is spent waits before its first session, triage included.
- A session the limit stops part way is not a failure. dev-team waits for
  the reset and resumes the same session (session.LIMIT_RESUMED); one that
  had not started yet is started again.

The reset time comes from the rate_limit_event the session streamed
(``resetsAt``, epoch seconds), with MARGIN on top. With no reset time on
record dev-team waits FALLBACK and tries again. Typing ``pause`` while it
waits ends the wait (devteam/pause.py takes it from there).
"""

import contextlib
import time

from devteam.accounting import describe_time
from devteam.fast import WINDOW, utilization

WAIT_THRESHOLD = 0.95
MARGIN = 60             # seconds after resetsAt before the first request
FALLBACK = 10 * 60      # the wait when no reset time is on record
TICK = 30               # how often a wait looks for a typed pause


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
