"""The probe half of the gate: a named probe set (Scripts/probes/sets.py), run
beside the verifier sweep.

Each launch is one ``uepy.py`` run (``--game`` for the single-player probes,
``--net --clients N`` for the networked ones) and its ``[probe]`` lines are read
back into rows shaped like a verifier's (``ok``, ``passed``, ``failed``,
``failures``), labelled ``probe:<name>``. They go into the same baseline table
and the same comparison (``gate.regressions``): a probe that newly fails, or
fails more checks than before, fails the task. A probe that gave no result is a
failed row, not a missing one, so a launch that dies fails every probe in it.
"""

import os
import re
import subprocess
import sys

PREFIX = "probe:"
PER_PROBE_SECONDS = 30
# Probes that share a boot share its world: one that leaves the player dead or
# the slots moved fails the next. A probe that fails in its batch is run once
# more alone, and the solo verdict is the row (at most this many per launch).
MAX_RERUNS = 8
LINE = re.compile(r"^\[probe\] (ok  |FAIL)\s+(\S+?)(?: @ \S+(?: \d+)?)?\s+(\d+)/(\d+) checks passed")
CHECK_FAIL = re.compile(r"^\s+FAIL (.+)$")
NO_RESULT = re.compile(r"^\[probe\] FAIL\s+(\S+)(?: @ .*?)?:")


def launches(probe_set):
    """[(label, uepy flags, [probe names])] for the non-empty parts of a set."""
    out = []
    if probe_set.get("game"):
        out.append(("game", ["--game"], probe_set["game"]))
    if probe_set.get("title"):
        out.append(("title", ["--game", "--title"], probe_set["title"]))
    if probe_set.get("net"):
        out.append(("net", ["--net", "--clients", str(probe_set.get("clients") or 2)],
                    probe_set["net"]))
    return out


def labels(probe_set):
    """The row labels of a set, sorted (none for no set)."""
    return sorted(PREFIX + n for _l, _f, names in launches(probe_set or {}) for n in names)


def parse_output(text, names):
    """{PREFIX+name: row} from a launch's output. ``names`` are the probes it
    was asked to run; any with no [probe] line gets a failed row."""
    rows, last = {}, None
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            ok, name, passed, total = m.group(1).strip() == "ok", m.group(2), int(m.group(3)), int(m.group(4))
            row = rows.setdefault(PREFIX + name, {"ok": True, "passed": 0, "failed": 0, "failures": []})
            row["ok"] = row["ok"] and ok
            row["passed"] += passed
            row["failed"] += total - passed
            last = row
            if not ok and total == passed:
                row["failed"] += 1                         # an error with every check passing
                row["failures"].append("the probe raised")
            continue
        m = NO_RESULT.match(line)
        if m:
            row = rows.setdefault(PREFIX + m.group(1), {"ok": True, "passed": 0, "failed": 0, "failures": []})
            row.update(ok=False, failed=row["failed"] + 1)
            row["failures"].append(line[len("[probe] FAIL"):].strip()[:200])
            last = None
            continue
        m = CHECK_FAIL.match(line)
        if m and last is not None:
            last["failures"].append(m.group(1)[:200])
    for name in names:
        rows.setdefault(PREFIX + name, {"ok": False, "passed": 0, "failed": 1,
                                        "failures": ["no result: the launch never reported it"]})
    return rows


def run_launch(root, flags, names, log_path):
    probes_dir = os.path.join(root, "Scripts", "probes")
    cmd = [sys.executable, os.path.join(root, "Scripts", "dev", "uepy.py"), *flags]
    for n in names:
        cmd += ["--probe", os.path.join(probes_dir, n + ".py")]
    budget = PER_PROBE_SECONDS * len(names) + 120
    cmd += ["--seconds", str(budget)]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=budget + 300)
        text = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        text = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
    with open(log_path, "a") as log:
        log.write(f"=== {' '.join(flags)}: {len(names)} probe(s)\n{text}\n")
    return text


def rerun_alone(root, flags, rows, names, log_path):
    """Replace the rows of the probes that failed in a batch with their solo run."""
    failed = [n for n in names if not rows[PREFIX + n]["ok"]][:MAX_RERUNS]
    for name in failed:
        solo = parse_output(run_launch(root, flags, [name], log_path), [name])
        rows[PREFIX + name] = solo[PREFIX + name]
    return failed


def run_probes(root, probe_set, log_path):
    """Run a set. Returns {PREFIX+name: row} for every probe in it."""
    rows = {}
    for _label, flags, names in launches(probe_set):
        batch = parse_output(run_launch(root, flags, names, log_path), names)
        rerun_alone(root, flags, batch, names, log_path)
        rows.update(batch)
    return rows
