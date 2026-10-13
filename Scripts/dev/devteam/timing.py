"""Where a task's time went, stage by stage.

Two clocks, added up by ``breakdown``:

- dev-team's own (``Stages``): the sweeps round the session, the waits for the
  session limit, the sessions themselves, and what is left of the task's wall
  time ("dev-team itself": closing editors, snapshots, Fab questions). It is
  the gate table's ``timings`` dict too, and is kept in the run directory
  (task-NN-time.json), so a task paused and resumed keeps the time of both
  halves.
- the session's (``tool_time``): the transcript stamps every model message and
  every tool result, so each tool call's time goes to what it ran (``stage_of``:
  an editor script, a verifier, a probe launch, the commit hook, ...), a
  compaction's to "compaction", and the rest of the session time is the model
  thinking and writing.

Seconds throughout; ``describe`` is the one-line form.
"""

import contextlib
import datetime
import json
import os
import re
import time

from devteam.accounting import describe_time

# Every stage, in the order the log's columns and the printout have them.
MODEL = "model"
OWN = "dev-team itself"
SESSION = "session"                 # Stages' name for the sessions' wall time
HARNESS = ("baseline sweep", "after sweeps", "limit wait", OWN)
IN_SESSION = (MODEL, "editor scripts", "verifiers", "game probes", "multiplayer probes",
              "C++ compile", "unit tests", "commit", "reading and editing", "waiting",
              "subagents", "other tools", "compaction")
STAGES = IN_SESSION + HARNESS

_UEPY = re.compile(r"\buepy\.py\b")
_WAITING = re.compile(r"^\s*(?:sleep|until|while)\b|\btail\s+-f\b")
_TOOLS = {"Read": "reading and editing", "Grep": "reading and editing",
          "Glob": "reading and editing", "Edit": "reading and editing",
          "Write": "reading and editing", "NotebookEdit": "reading and editing",
          "Task": "subagents", "Agent": "subagents"}


def path(run_dir, n):
    return os.path.join(run_dir, f"task-{n:02d}-time.json")


def stage_of(name, command=""):
    """The stage a tool call's time belongs to. A compound command is the
    slowest thing it holds: a launch before a verifier, a verifier before
    any other editor script."""
    if name != "Bash":
        return _TOOLS.get(name, "other tools")
    if _UEPY.search(command):
        if "--net" in command:
            return "multiplayer probes"
        if re.search(r"--(?:game|wait|detach)\b", command):
            return "game probes"
        if "--compile" in command:
            return "C++ compile"
        if "--verify-for" in command or "verify_" in command:
            return "verifiers"
        return "editor scripts"
    if "unittest" in command:
        return "unit tests"
    if re.search(r"\bgit\b[^|;&\n]*\bcommit\b", command):
        return "commit"
    if _WAITING.search(command):
        return "waiting"
    return "reading and editing"


def _stamp(event):
    try:
        return datetime.datetime.fromisoformat(
            event["timestamp"].replace("Z", "+00:00")).timestamp()
    except (KeyError, ValueError, AttributeError):
        return None


def tool_time(log_path):
    """Seconds per stage inside the sessions of one transcript: every tool
    call from the message that made it to its result, and every compaction.
    Calls made side by side are not counted twice: each moment goes to the
    call that began first."""
    spent, calls, covered = {}, {}, 0.0
    try:
        fh = open(log_path, errors="replace")
    except OSError:
        return spent
    with fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict) or event.get("parent_tool_use_id"):
                continue                    # a subagent's own calls: the Task call covers them
            if event.get("subtype") == "compact_boundary":
                took = (event.get("compact_metadata") or {}).get("duration_ms") or 0
                spent["compaction"] = spent.get("compaction", 0.0) + took / 1000.0
                continue
            when, content = _stamp(event), (event.get("message") or {}).get("content")
            if when is None or not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    command = (block.get("input") or {}).get("command") or ""
                    calls[block.get("id")] = (when, stage_of(block.get("name"), str(command)))
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                    began, stage = calls.pop(block["tool_use_id"])
                    began = max(began, covered)
                    if when > began:
                        spent[stage] = spent.get(stage, 0.0) + when - began
                        covered = when
    return spent


def spend(timings, stage, seconds):
    """Add to a stage of ``timings`` when it is a Stages (a plain dict, as the
    gate table alone needs, keeps no clock)."""
    if isinstance(timings, Stages):
        timings.add(stage, seconds)


@contextlib.contextmanager
def timed(timings, stage):
    began = time.time()
    try:
        yield
    finally:
        spend(timings, stage, time.time() - began)


class Stages(dict):
    """dev-team's clock for one task. As a dict it is the gate table's
    {sweep: text}; ``spent`` is {stage: seconds}, saved to ``path`` on every
    change and taken up again from it (``resume=True``: a paused task's
    second half, or the write-up reading what run_one clocked)."""

    def __init__(self, path=None, resume=True):
        super().__init__()
        self.path, self.spent = path, {}
        kept = self._read() if resume else {}
        self.spent.update(kept.get("spent") or {})
        self.started = kept.get("started") or time.time()   # the task's first start
        self.began = kept.get("began") or time.time()       # this half's
        self.carried = kept.get("carried") or 0.0           # spent before this half

    def _read(self):
        try:
            with open(self.path) as fh:
                kept = json.load(fh)
        except (OSError, ValueError, TypeError):
            return {}
        return kept if isinstance(kept, dict) else {}

    def begin(self):
        """Start this half's clock: what is on record so far is the earlier
        half's."""
        self.began, self.carried = time.time(), sum(self.spent.values())
        self._save()

    def add(self, stage, seconds):
        self.spent[stage] = self.spent.get(stage, 0.0) + max(0.0, seconds)
        self._save()

    def finish(self, now=None):
        """Close this half: its wall time no stage claimed is dev-team's own."""
        claimed = sum(self.spent.values()) - self.carried
        self.add(OWN, (now or time.time()) - self.began - claimed)
        self.begin()

    def _save(self):
        if not self.path:
            return
        try:
            with open(self.path, "w") as fh:
                json.dump(dict(spent=self.spent, started=self.started, began=self.began,
                               carried=self.carried), fh)
        except OSError:
            pass


def breakdown(spent, tools, session_ms=0):
    """{stage: seconds} for a task, every stage of STAGES that took any time:
    dev-team's stages as clocked, the session's time split by ``tools`` with
    the rest of it the model's. With no session on the clock (a write-up that
    has only the result event), the session time is the result's."""
    session = spent.get(SESSION) or (session_ms or 0) / 1000.0
    out = {s: spent[s] for s in HARNESS if spent.get(s)}
    for stage, seconds in tools.items():
        stage = stage if stage in IN_SESSION else "other tools"
        out[stage] = out.get(stage, 0.0) + seconds
    model = session - sum(v for s, v in out.items() if s not in HARNESS)
    if model > 0:
        out[MODEL] = model
    return {s: out[s] for s in STAGES if out.get(s, 0) >= 0.5}


def total(stages):
    return sum(stages.values())


def describe(stages, limit=None):
    """'model 13m 47s (44%), game probes 6m 01s (19%), ...', longest first."""
    whole = total(stages) or 1.0
    parts = sorted(stages.items(), key=lambda kv: -kv[1])
    shown = parts[:limit] if limit else parts
    text = [f"{s} {describe_time(v * 1000)} ({100 * v / whole:.0f}%)" for s, v in shown]
    if len(parts) > len(shown):
        rest = sum(v for _s, v in parts[len(shown):])
        text.append(f"{len(parts) - len(shown)} more {describe_time(rest * 1000)}")
    return ", ".join(text)
