"""A probe sweep on its own: ``dev-team probes run [SET]`` (FULL unless named).

Probes are not part of a task's gate or a run's end unless a run asks for
them (``--probes``): over three days they cost 21 hours of launches and found
three defects, while the verifiers found more in a few minutes a task. So a
sweep of them runs apart, nightly, by this command. It closes the editors,
runs the set's launches (devteam/probe_gate), writes every probe's result to
the record (Saved/DevTeam/probe_status.json, ``dev-team probes`` lists it)
and a report under Saved/DevTeam/probes-<stamp>/, and prints what newly
fails against what the record held before.

Exit code 0 when nothing newly fails (a probe failing on record, no worse,
and a known failure do not count), 1 when one does, 2 when the sweep could
not run.
"""

import datetime
import os
import time

from devteam import gate, probe_gate, probe_record, work
from devteam.trace import shown, step
from probes import sets

DEFAULT_SET = "FULL"


def report(name, before, rows, labels, took, against):
    """The sweep's report: the table against the record, then the regressions."""
    problems = gate.regressions(before, rows, gate.load_known(), labels)
    failing = sorted(l for l in labels if not (rows.get(l) or {}).get("ok"))
    text = (f"# Probe sweep: {name}, {'FAILED' if problems else 'ok'}\n\n"
            f"Against {against}.\n\n{gate.table(before, rows, {'probes': took}, labels)}\n")
    if failing:
        text += "\n## Failing\n\n" + "".join(
            f"- {l}: {gate.describe(rows.get(l))}"
            + "".join(f"\n  - {f[:200]}" for f in (rows.get(l) or {}).get("failures") or [])
            + "\n" for l in failing)
    if problems:
        text += "\n## Newly failing\n\n" + "\n".join(f"- {p}" for p in problems) + "\n"
    return text, problems


def run(name=DEFAULT_SET, root=None, log_root=None):
    """The whole command. Returns the exit code."""
    root, log_root = root or work.ROOT, log_root or work.LOG_ROOT
    try:
        probe_set = sets.resolve(name)
    except ValueError as err:
        print(f"dev-team: {err}")
        return 2
    labels = probe_gate.labels(probe_set)
    record = probe_record.load(root)
    before = probe_record.as_rows(record, labels)
    against = f"the {probe_record.describe(record, labels)}"
    if not work.close_editors():
        print("dev-team: probes not run -- an editor of this project is still running")
        return 2
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(log_root, f"probes-{stamp}")
    os.makedirs(run_dir, exist_ok=True)
    log = os.path.join(run_dir, "sweeps.txt")
    step(f"probes: {name} starting, {len(labels)} probe(s), {against}  "
         f"(log: {shown(log, root)})", indent="")
    started = time.time()
    rows = work.probes(probe_set, log)
    took = f"{time.time() - started:.0f}s"
    text, problems = report(name, before, rows, labels, took, against)
    path = os.path.join(run_dir, "report.md")
    with open(path, "w") as fh:
        fh.write(text)
    failing = sum(1 for l in labels if not (rows.get(l) or {}).get("ok"))
    print(f"dev-team: probes {name} {'FAILED' if problems else 'ok'} in {took}: "
          f"{len(labels) - failing} of {len(labels)} passing, {len(problems)} newly failing"
          f"  (report: {shown(path, root)})"
          + "".join(f"\n  - {p[:200]}" for p in problems))
    return 1 if problems else 0
