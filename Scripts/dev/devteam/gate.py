"""The verifier gate: the whole suite, run by dev-team before and after a task.

Before: the numbers go into the session's prompt, so the session starts from
a known baseline instead of spending turns (and a boot) establishing one.
After: the same sweep again; a verifier that newly fails -- or fails more
checks than before -- fails the task, whatever the session's report says.
The session is told this up front.

One cold boot runs every suite (``uepy.py --cold --summary --json``), so a
sweep costs about half a minute. A failure that was already there before the
task is reported but never blamed on it.
"""

import glob
import json
import os
import subprocess
import sys
import tempfile

# Scripts/verify_level.py predates the generated levels: it loads the retired
# /Game/Maps/Lvl_Forest and counts actors, with no pass/fail to gate on.
EXCLUDE = {"verify_level.py"}


def sweep_targets(root):
    tops = sorted(glob.glob(os.path.join(root, "Scripts", "verify_*.py")))
    levels = sorted(glob.glob(os.path.join(root, "Scripts", "generated_levels", "*",
                                           "verify_*.py")))
    return [p for p in tops + levels if os.path.basename(p) not in EXCLUDE]


def run_sweep(root, log_path):
    """Run the suite cold. Returns {label: result dict}, or None if the sweep
    itself broke (no JSON came back); its output is appended to log_path."""
    targets = sweep_targets(root)
    fd, json_path = tempfile.mkstemp(prefix="devteam-sweep-", suffix=".json")
    os.close(fd)
    cmd = [sys.executable, os.path.join(root, "Scripts", "dev", "uepy.py"),
           "--cold", "--summary", "--json", json_path, *targets]
    with open(log_path, "a") as log:
        subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL)
    try:
        with open(json_path) as fh:
            rows = json.load(fh)
    except (OSError, ValueError):
        return None
    finally:
        os.remove(json_path)
    return {row["label"]: row for row in rows} or None


def describe(row):
    if row is None:
        return "missing"
    if row.get("passed") is None:
        return "ok" if row.get("ok") else "FAILED (no counts)"
    total = row["passed"] + (row.get("failed") or 0)
    return f"{row['passed']}/{total}" + ("" if row.get("ok") else " FAILED")


def regressions(before, after):
    """What got worse between two sweeps, one line each (empty: nothing)."""
    if after is None:
        return ["the verifier sweep itself failed to run (see the sweep log)"]
    before = before or {}
    problems = []
    for label in sorted(set(before) | set(after)):
        b, a = before.get(label), after.get(label)
        if a is None:
            problems.append(f"{label}: did not report (it ran before the task)")
            continue
        if a.get("ok"):
            continue
        if b is not None and not b.get("ok") and (a.get("failed") or 0) <= (b.get("failed") or 0):
            continue                                        # failing before, no worse
        first = "; ".join((a.get("failures") or a.get("tracebacks") or a.get("errors")
                           or ["no detail"])[:3])
        was = f" (was {describe(b)})" if b is not None else " (new)"
        problems.append(f"{label}: {describe(a)}{was} -- {first[:400]}")
    return problems


def table(before, after=None):
    """A Markdown table of one sweep, or of before -> after."""
    labels = sorted(set(before or {}) | set(after or {}))
    if after is None:
        rows = ["| verifier | result |", "|---|---|"]
        rows += [f"| {l} | {describe((before or {}).get(l))} |" for l in labels]
    else:
        rows = ["| verifier | before | after |", "|---|---|---|"]
        rows += [f"| {l} | {describe((before or {}).get(l))} | {describe(after.get(l))} |"
                 for l in labels]
    return "\n".join(rows)
