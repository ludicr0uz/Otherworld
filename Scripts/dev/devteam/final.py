"""The run's one probe sweep: a probe set run after the last task, not after each.

The gate's probe half cost a run 41% of its time (a SMOKE sweep is about twenty
minutes once the probes that fail in their batch are re-run alone) and failed
tasks that changed only Markdown. So a task's gate is the verifiers alone
(``--gate-probes none``), and the probes are swept once a run, after the last
task (``--final-probes``, SMOKE). What newly fails there is written to
progress.md as its own section, with the commits it covers, and counts against
the run's exit code; it fails no task, because it cannot say which one.

What "newly" is measured against: the run's own baseline sweep, before the
first task, when ``--check-baseline`` asks for one (or the cache holds one
for this tree); otherwise the latest recorded result of each probe
(devteam/probe_record.py), from whichever earlier run or gate last ran it.
"""

import os
import time

from devteam import baseline_cache, gate, probe_gate, probe_record, work
from devteam.accounting import git_head
from devteam.trace import shown, step

HEADING = "## Final probes"


def union(a, b):
    """One probe set holding both (either may be None)."""
    a, b = a or {}, b or {}
    out = {kind: list(dict.fromkeys((a.get(kind) or []) + (b.get(kind) or [])))
           for kind in ("game", "title", "net")}
    out["clients"] = max(a.get("clients") or 2, b.get("clients") or 2)
    return out


def for_task(rows, probe_set):
    """The rows of the run's baseline a task's gate holds: the verifiers' and
    its own probe set's, not the final set's."""
    keep = set(probe_gate.labels(probe_set))
    return {l: r for l, r in rows.items() if not l.startswith(probe_gate.PREFIX) or l in keep}


def section(status, name, commits, body, problems=(), against="the run's first baseline"):
    """The final sweep's part of progress.md."""
    text = f"\n{HEADING}: {status}\n\nSet: {name}, against {against}.\n" \
           f"Commits: {commits}\n\n{body}\n"
    if problems:
        text += "\n### Regressions\n\n" + "\n".join(f"- {p}" for p in problems) + "\n"
    return text


class Finale:
    """``begin`` before the first task, ``seen`` after each, ``finish`` at the end."""

    def __init__(self, args, run_dir, progress):
        self.name, self.final_set, self.task_set = args.final_probes, args.final_set, args.probe_set
        self.check = getattr(args, "check_baseline", False)
        self.log = os.path.join(run_dir, "final-sweeps.txt")
        self.progress = progress
        self.begun, self.first, self.head, self.state, self.last = False, None, None, None, None
        self.against = "the run's first baseline"

    def begin(self, cache, pauser=None):
        """Settle the run's "before" once, before the first task: the cached
        baseline of this tree if there is one; else a baseline sweep (the
        verifiers, and the task set's and the final set's probes) when
        --check-baseline asked for one, whose verifier share goes into
        ``cache`` for the first task's gate; else the probes' recorded results."""
        if self.begun:
            return
        self.begun = True
        both = union(self.task_set, self.final_set)
        ran = probe_gate.labels(both)
        self.head, self.state = git_head(work.ROOT), work.tree_state()
        rows = baseline_cache.load(work.ROOT, self.state, ran)
        if rows:
            step("gate: the run's baseline from the cache (tree unchanged)")
        elif self.check:
            step(f"gate: sweeping the run's baseline -- the verifiers and {len(ran)} probe(s) "
                 f"({self.name}); the final probes are compared with it")
            rows = work.sweep("run baseline", self.log, pauser, both, warm=True)
            baseline_cache.save(work.ROOT, self.state, rows, ran)
        else:
            labels = probe_gate.labels(self.final_set)
            record = probe_record.load(work.ROOT)
            self.first = probe_record.as_rows(record, labels)
            held = probe_record.describe(record, labels)
            self.against = (f"the {held} "
                            f"({os.path.relpath(probe_record.path(work.ROOT), work.ROOT)})")
            step(f"gate: no baseline sweep (--check-baseline runs one); the final probes "
                 f"({self.name}) are compared with the {held}")
            return
        if rows:
            self.first = rows
            cache[self.state] = for_task(rows, self.task_set)

    def seen(self, state, swept):
        """A task's after-sweep, and the tree it was of."""
        self.last = (state, swept)

    def _write(self, status, commits, body, problems=()):
        print(f"\ndev-team: final probes ({self.name}) {status}"
              + "".join(f"\n  - {p[:200]}" for p in problems))
        with open(self.progress, "a") as f:
            f.write(section(status, self.name, commits, body, problems, self.against))

    def finish(self):
        """The one sweep. False when a probe regressed, or it could not run."""
        if not self.begun:
            return True
        head, state = git_head(work.ROOT), work.tree_state()
        commits = f"{self.head}..{head}" if head != self.head else f"none (still {head})"
        labels = probe_gate.labels(self.final_set)
        if self.first is None:
            self._write("not run", commits, "The run's first baseline failed to sweep, "
                        "so there is nothing to compare with.")
            return True
        if state == self.state:
            self._write("not run", commits, "The tree is as the run found it.")
            return True
        last = self.last[1] if self.last and self.last[0] == state else None
        started = time.time()
        if last and all(l in last for l in labels):
            rows, took = {l: last[l] for l in labels}, "the last task's after-sweep"
        else:
            if not work.close_editors():
                self._write("FAILED", commits, "An editor of this project is still running.")
                return False
            step(f"gate: final probes ({self.name}) starting, {len(labels)} probe(s)  "
                 f"(log: {shown(self.log, work.ROOT)})")
            rows = work.probes(self.final_set, self.log)
            took = f"{time.time() - started:.0f}s"
        before = {l: self.first[l] for l in labels if l in self.first}
        problems = gate.regressions(before, rows, gate.load_known(), labels)
        self._write("FAILED" if problems else "ok", commits,
                    gate.table(before, rows, {"final": took}, labels), problems)
        if last:
            # The next run's first baseline, if it starts from this tree.
            both = probe_gate.labels(union(self.task_set, self.final_set))
            baseline_cache.save(work.ROOT, state, {**last, **rows}, both)
        return not problems
