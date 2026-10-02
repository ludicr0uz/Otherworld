"""Fast mode: the same Opus at a higher output speed, used while the session
limit has room.

Model time is over half a task's wall time and nearly all of it is output, so
fast mode (up to 2.5x the output speed, same model) is the one switch that
shortens it without touching effort. A headless session only gets it when
launched with ``"fastMode": true`` in --settings (session.build_cmd).

The rule: a task runs fast while the five-hour session limit is under
THRESHOLD used. The reading is the last ``rate_limit_event`` any session
streamed: this run's once it has one, before that the newest transcript in
Saved/DevTeam. A reading whose window has since reset counts as an empty
window; with no reading at all the task runs at standard speed. It is decided
once per task and kept for its follow-ups (a gate fix, a Fab resume): turning
fast mode on mid-conversation re-bills the whole context uncached.

Fast mode is billed to usage credits, not to the plan's limits, and needs
them turned on. Where it cannot run the session runs at standard speed and
its init event says why, which session.run_session prints.
"""

import glob
import json
import os

THRESHOLD = 0.5
WINDOW = "five_hour"
MODES = ("auto", "on", "off")


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
    """The latest reading of the session limit, and the rule on it."""

    def __init__(self, mode="auto", info=None):
        self.mode, self.info = mode, info

    def see(self, info):
        """A session streamed a rate_limit_event."""
        if info:
            self.info = info

    def decide(self, now):
        """(run this task fast?, why -- one phrase for the run's output)."""
        if self.mode != "auto":
            return self.mode == "on", f"--fast {self.mode}"
        used = utilization(self.info, now)
        if used is None:
            return False, "no reading of the session limit yet"
        return used < THRESHOLD, (f"session limit at {used:.0%}, "
                                  f"fast under {THRESHOLD:.0%}")
