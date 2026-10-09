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


def run_sweep(root, log_path, serve_dir=None):
    """Run the suite cold, or, given ``serve_dir``, in that warm serve editor
    (the before-sweep; the after-sweep stays cold). Returns {label: result dict}, or None if the sweep
    itself broke (no JSON came back); its output is appended to log_path."""
    targets = sweep_targets(root)
    fd, json_path = tempfile.mkstemp(prefix="devteam-sweep-", suffix=".json")
    os.close(fd)
    cmd = [sys.executable, os.path.join(root, "Scripts", "dev", "uepy.py"),
           *([] if serve_dir else ["--cold"]), "--summary", "--json", json_path, *targets]
    env = dict(os.environ, UEPY_SERVE=serve_dir) if serve_dir else None
    with open(log_path, "a") as log:
        subprocess.run(cmd, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
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


KNOWN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "known_failures.md")


def parse_known(text):
    """Rows of known_failures.md: ``target | check label | since DATE | why``.
    Returns [{target, check, since, why}]; blank, ``#`` and malformed lines are skipped."""
    rows = []
    for line in text.splitlines():
        parts = [x.strip() for x in line.split("|", 3)]
        if line.lstrip().startswith("#") or len(parts) < 4 or not parts[0] or not parts[1]:
            continue
        rows.append({"target": parts[0], "check": parts[1],
                     "since": parts[2].removeprefix("since").strip(), "why": parts[3]})
    return rows


def load_known(path=KNOWN_PATH):
    try:
        with open(path) as fh:
            return parse_known(fh.read())
    except OSError:
        return []


def _is_known(known, label, failure):
    name = label.removesuffix(".py")
    return any(k["target"].removesuffix(".py") == name and k["check"] in failure
               for k in known)


def known_report(known, after):
    """(still failing, fixed) lines for the listed checks of the verifiers in ``after``."""
    standing, fixed = [], []
    for k in known:
        row = next((r for l, r in (after or {}).items()
                    if l.removesuffix(".py") == k["target"].removesuffix(".py")), None)
        if row is None:
            continue                                        # a probe, or not swept
        if any(k["check"] in f for f in row.get("failures") or []):
            standing.append(f"known: {k['target']} | {k['check']} (since {k['since']})")
        else:
            fixed.append(f"fixed, remove the line: {k['target']} | {k['check']}")
    return standing, fixed


def regressions(before, after, known=()):
    """What got worse between two sweeps, one line each (empty: nothing).
    A failure listed in ``known`` is never a regression."""
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
        fails = a.get("failures") or []
        if known and fails and not (a.get("tracebacks") or a.get("errors")) \
                and len(fails) >= (a.get("failed") or 0) \
                and all(_is_known(known, label, f) for f in fails):
            continue                                        # only known failures
        if b is not None and not b.get("ok") and (a.get("failed") or 0) <= (b.get("failed") or 0):
            continue                                        # failing before, no worse
        first = "; ".join((a.get("failures") or a.get("tracebacks") or a.get("errors")
                           or ["no detail"])[:3])
        was = f" (was {describe(b)})" if b is not None else " (new)"
        problems.append(f"{label}: {describe(a)}{was} -- {first[:400]}")
    return problems


def table(before, after=None, times=None):
    """A Markdown table of one sweep, or of before -> after; ``times`` ({label:
    text}) adds a line of how long each sweep took."""
    labels = sorted(set(before or {}) | set(after or {}))
    if after is None:
        rows = ["| verifier | result |", "|---|---|"]
        rows += [f"| {l} | {describe((before or {}).get(l))} |" for l in labels]
    else:
        rows = ["| verifier | before | after |", "|---|---|---|"]
        rows += [f"| {l} | {describe((before or {}).get(l))} | {describe(after.get(l))} |"
                 for l in labels]
    if times:
        rows += ["", "Sweep time: " + ", ".join(f"{k} {v}" for k, v in times.items())]
    return "\n".join(rows)
