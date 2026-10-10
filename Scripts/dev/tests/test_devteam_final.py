"""The run's one probe sweep (devteam/final.py), the comparison narrowed to the
labels both sweeps ran, and dev-team's loop with the gate on and every launch
stubbed."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401

from devteam import baseline_cache, final, gate, probe_gate, probe_record
from test_devteam import load_cli, row

SET = {"game": ["probe_a"], "title": [], "net": ["probe_net_b"], "clients": 2}
LABELS = ["probe:probe_a", "probe:probe_net_b"]


def sweep_rows(probe_set=None, failing=()):
    rows = {"verify_x.py": row("verify_x.py", 5, 0)}
    for label in probe_gate.labels(probe_set):
        rows[label] = row(label, 3, 1 if label in failing else 0,
                          ["check z"] if label in failing else [])
    return rows


class NarrowedComparison(unittest.TestCase):
    def test_a_probe_row_of_another_set_is_not_a_regression(self):
        before, after = sweep_rows(SET), sweep_rows()
        self.assertEqual(len(gate.regressions(before, after)), 2)      # same set: it went missing
        self.assertEqual(gate.regressions(before, after, probes=[]), [])
        self.assertEqual(gate.not_rerun(before, after, []), LABELS)

    def test_a_row_both_sweeps_hold_is_still_compared(self):
        before = sweep_rows(SET)
        after = {**sweep_rows(), "probe:probe_a": row("probe:probe_a", 2, 1, ["check z"])}
        problems = gate.regressions(before, after, probes=["probe:probe_a"])
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("probe:probe_a: 2/3 FAILED"))

    def test_a_missing_verifier_or_asked_for_probe_is_still_reported(self):
        before = sweep_rows(SET)
        self.assertIn("verify_x.py: did not report", gate.regressions(before, {}, probes=[])[0])
        problems = gate.regressions(before, sweep_rows(), probes=["probe:probe_a"])
        self.assertEqual(len(problems), 1)
        self.assertIn("probe:probe_a: did not report", problems[0])

    def test_the_table_says_which_rows_were_not_rerun(self):
        out = gate.table(sweep_rows(SET), sweep_rows(), probes=[])
        self.assertIn("| probe:probe_a | 3/3 | not re-run |", out)
        self.assertIn("| verify_x.py | 5/5 | 5/5 |", out)
        self.assertIn("Not re-run: 2 probe row(s)", out)
        same = gate.table(sweep_rows(SET), sweep_rows(SET), probes=LABELS)
        self.assertNotIn("not re-run", same.lower())
        self.assertIn("| probe:probe_a | 3/3 | missing |", gate.table(sweep_rows(SET), sweep_rows()))


class CacheKey(unittest.TestCase):
    def test_the_key_takes_the_probe_set(self):
        state = ("abc", "")
        self.assertNotEqual(baseline_cache.key(state), baseline_cache.key(state, LABELS))
        self.assertEqual(baseline_cache.key(state, LABELS), baseline_cache.key(state, LABELS[::-1]))
        self.assertNotEqual(baseline_cache.key(state, LABELS[:1]), baseline_cache.key(state, LABELS))

    def test_a_baseline_of_one_set_is_not_reused_under_another(self):
        with tempfile.TemporaryDirectory() as root:
            baseline_cache.save(root, ("abc", ""), sweep_rows(SET), LABELS)
            self.assertIsNone(baseline_cache.load(root, ("abc", "")))
            self.assertIsNone(baseline_cache.load(root, ("abc", ""), LABELS[:1]))
            self.assertEqual(baseline_cache.load(root, ("abc", ""), LABELS), sweep_rows(SET))

    def test_a_cache_written_before_the_set_was_in_the_key_misses(self):
        import hashlib
        import json
        old = hashlib.sha1(b"abc\0\0").hexdigest()          # key(state) as it was
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.dirname(baseline_cache.path(root)))
            with open(baseline_cache.path(root), "w") as fh:
                json.dump({"key": old, "rows": sweep_rows(SET)}, fh)
            self.assertIsNone(baseline_cache.load(root, ("abc", "")))


class Pieces(unittest.TestCase):
    def test_union_and_for_task(self):
        both = final.union({"game": ["a"], "net": ["n"], "clients": 3}, SET)
        self.assertEqual(both, {"game": ["a", "probe_a"], "title": [],
                                "net": ["n", "probe_net_b"], "clients": 3})
        self.assertEqual(final.union(None, SET)["net"], ["probe_net_b"])
        self.assertEqual(sorted(final.for_task(sweep_rows(SET), None)), ["verify_x.py"])
        self.assertEqual(sorted(final.for_task(sweep_rows(SET), {"game": ["probe_a"]})),
                         ["probe:probe_a", "verify_x.py"])


class GatedRun(unittest.TestCase):
    """Two tasks through dev-team's loop with the gate on: sessions, sweeps,
    probe launches, editors and git stubbed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path = os.path.join(self.tmp, "tasks.md")
        with open(self.path, "w") as fh:
            fh.write("- [ ] a\n- [ ] b\n")
        self.cli = load_cli()
        self.commit = 0             # the stub tree: one commit per task
        self.sweeps, self.probe_runs = [], []

    def run_cli(self, *flags, failing=(), commits=True):
        def state():
            return (f"c{self.commit}", "")

        def run_one(task, n, total, args, _run_dir, _progress, cache, *_rest):
            baseline = cache.get(state())
            if baseline is None:                # as work.run_one: sweep its own
                baseline = sweep_rows(args.probe_set)
            self.commit += commits
            ran = probe_gate.labels(args.probe_set)
            after = sweep_rows(args.probe_set)
            return True, ["report"], {}, gate.table(baseline, after, probes=ran), after

        def sweep(label, _log, _pauser=None, probe_set=None, **_how):
            self.sweeps.append((label, probe_gate.labels(probe_set)))
            return sweep_rows(probe_set)

        def run_probes(_root, probe_set, _log):
            self.probe_runs.append(probe_gate.labels(probe_set))
            return {l: r for l, r in sweep_rows(probe_set, failing).items()
                    if l.startswith(probe_gate.PREFIX)}

        out = io.StringIO()
        logs = os.path.join(self.tmp, "logs")
        argv = ["dev-team", "-t", self.path, "--no-triage", *flags]
        with mock.patch.multiple(self.cli, run_one=run_one, close_editors=lambda: True,
                                 git_head=lambda root: None, tree_state=state,
                                 LOG_ROOT=logs, ROOT=self.tmp), \
                mock.patch.multiple(final.work, sweep=sweep, tree_state=state,
                                    close_editors=lambda: True, ROOT=self.tmp), \
                mock.patch.object(final, "git_head", lambda root: f"c{self.commit}"), \
                mock.patch.object(final.probe_gate, "run_probes", run_probes), \
                mock.patch.object(self.cli.sets, "resolve", lambda name: dict(SET)), \
                mock.patch.object(self.cli.limits, "wait", lambda *a, **k: None), \
                mock.patch.object(self.cli.server, "stop", lambda serve_dir: False), \
                mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stop:
            self.cli.main()
        progress = ""
        if os.path.isdir(logs):
            run = sorted(d for d in os.listdir(logs) if os.path.isdir(os.path.join(logs, d)))[-1]
            with open(os.path.join(logs, run, "progress.md")) as fh:
                progress = fh.read()
        return stop.exception.code, out.getvalue(), progress

    def again(self, *flags, moved=True, **how):
        """A second run, on a fresh queue (its logs are named by the second),
        from a tree that moved on meanwhile unless ``moved`` is False."""
        shutil.rmtree(os.path.join(self.tmp, "logs"))
        with open(self.path, "w") as fh:
            fh.write("- [ ] c\n")
        self.commit += moved
        return self.run_cli(*flags, **how)

    def test_no_probe_rows_per_task_and_one_final_section(self):
        code, out, progress = self.run_cli("--check-baseline")
        self.assertEqual(code, 0)
        self.assertIn("probes per task: none; final probes: SMOKE, against a baseline sweep", out)
        self.assertRegex(out, r"\d\d:\d\d:\d\d  gate: sweeping the run's baseline -- "
                              r"the verifiers and 2 probe\(s\) \(SMOKE\)")
        tasks, last = progress.split(final.HEADING)[0], progress.split(final.HEADING)[1:]
        self.assertEqual(len(last), 1)
        self.assertEqual(tasks.count("### Verifier gate"), 2)
        self.assertNotIn("probe:", tasks)
        self.assertTrue(last[0].startswith(": ok\n"))
        self.assertIn("against the run's first baseline", last[0])
        self.assertIn("Commits: c0..c2", last[0])
        self.assertIn("| probe:probe_a | 3/3 | 3/3 |", last[0])
        self.assertNotIn("verify_x.py", last[0])
        # One baseline with the probes, one probe sweep at the end, none between.
        self.assertEqual(self.sweeps, [("run baseline", LABELS)])
        self.assertEqual(self.probe_runs, [LABELS])

    def test_by_default_the_record_is_the_before_and_no_baseline_is_swept(self):
        code, out, progress = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("against each probe's recorded result (--check-baseline sweeps one", out)
        self.assertIn("gate: no baseline sweep (--check-baseline runs one); the final probes "
                      "(SMOKE) are compared with the probe record, which holds no result "
                      "for any of the 2 probe(s)", out)
        self.assertEqual(self.sweeps, [])
        self.assertEqual(self.probe_runs, [LABELS])
        last = progress.split(final.HEADING)[1]
        self.assertTrue(last.startswith(": ok\n"))
        self.assertIn("against the probe record, which holds no result", last)
        self.assertIn("| probe:probe_a | missing | 3/3 |", last)
        # The final sweep is on record now, and the next run compares with it.
        record = probe_record.load(self.tmp)
        self.assertEqual(sorted(record), ["probe_a", "probe_net_b"])
        self.assertEqual((record["probe_a"]["head"], record["probe_a"]["ok"],
                          record["probe_a"]["passed"]), ("c2", True, 3))
        code, out, progress = self.again()
        self.assertEqual(code, 0)
        self.assertIn("compared with the recorded results of 2 of 2 probe(s), from "
                      f"{record['probe_a']['when']} at commit c2", out)
        self.assertIn("| probe:probe_a | 3/3 | 3/3 |", progress.split(final.HEADING)[1])
        self.assertEqual(self.sweeps, [])

    def test_a_final_regression_fails_the_run_and_no_task(self):
        self.run_cli()                                  # puts the probes on record
        code, out, progress = self.again(failing=("probe:probe_net_b",))
        self.assertEqual(code, 1)
        self.assertEqual(progress.count(": done"), 1)
        self.assertIn(final.HEADING + ": FAILED", progress)
        self.assertIn("- probe:probe_net_b: 3/4 FAILED (was 3/3)", progress)
        self.assertEqual(out.count("       done  "), 1)
        with open(self.path) as fh:
            self.assertEqual(fh.read(), "- [x] c\n")
        self.assertFalse(probe_record.load(self.tmp)["probe_net_b"]["ok"])

    def test_a_failing_probe_with_no_record_is_reported_as_new(self):
        code, _out, progress = self.run_cli(failing=("probe:probe_net_b",))
        self.assertEqual(code, 1)
        self.assertIn("- probe:probe_net_b: 3/4 FAILED (new)", progress)

    def test_the_next_run_s_baseline_is_cached_under_both_sets(self):
        self.run_cli()
        self.sweeps.clear()
        _code, out, _progress = self.again("--check-baseline", moved=False)
        self.assertEqual(self.sweeps, [])               # the first baseline: from the cache
        self.assertIn("the run's baseline from the cache (tree unchanged)", out)
        self.assertEqual(len(self.probe_runs), 2)

    def test_the_terminal_output_is_kept_in_run_log(self):
        _code, out, _progress = self.run_cli()
        logs = os.path.join(self.tmp, "logs")
        run = os.listdir(logs)[0]
        with open(os.path.join(logs, run, "run.log")) as fh:
            kept = fh.read()
        self.assertIn(f"run {run} -- logs in", out)
        self.assertTrue(out.endswith(kept))             # from the loop on: every line
        self.assertIn("[1/2] ", kept)
        self.assertRegex(kept, r"\[1/2\] \d\d:\d\d:\d\d  a\n")
        self.assertIn("dev-team: finished", kept)
        self.assertIs(sys.stdout, sys.__stdout__)       # put back

    def test_dev_team_probes_lists_the_record(self):
        self.run_cli(failing=("probe:probe_net_b",))
        out = io.StringIO()
        with mock.patch.multiple(self.cli, ROOT=self.tmp), \
                mock.patch.object(sys, "argv", ["dev-team", "probes"]), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stop:
            self.cli.main()
        self.assertEqual(stop.exception.code, 0)
        self.assertIn("2 probe(s) on record in Saved/DevTeam/probe_status.json", out.getvalue())
        self.assertRegex(out.getvalue(), r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d  +c2  ok   probe_a  3/3\n")
        self.assertIn("FAIL probe_net_b  3/4  -- check z", out.getvalue())
        out = io.StringIO()
        with mock.patch.multiple(self.cli, ROOT=self.tmp), \
                mock.patch.object(sys, "argv", ["dev-team", "probes", "NET"]), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            self.cli.main()
        self.assertNotIn("probe_a ", out.getvalue())
        self.assertIn("probe_net_b", out.getvalue())
        with mock.patch.multiple(self.cli, ROOT=os.path.join(self.tmp, "empty")), \
                mock.patch.object(sys, "argv", ["dev-team", "probes"]), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stop:
            self.cli.main()
        self.assertEqual(stop.exception.code, 1)

    def test_gate_probes_on_every_task_need_no_second_sweep(self):
        code, _out, progress = self.run_cli("--gate-probes", "SMOKE")
        self.assertEqual(code, 0)
        self.assertEqual(self.probe_runs, [])           # the last after-sweep held them
        self.assertIn("the last task's after-sweep", progress)
        self.assertIn("| probe:probe_a | 3/3 | 3/3 |", progress.split(final.HEADING)[0])

    def test_no_final_probes_and_an_unchanged_tree(self):
        _code, _out, progress = self.run_cli("--final-probes", "none")
        self.assertNotIn(final.HEADING, progress)
        self.assertEqual(self.sweeps, [])

    def test_an_unchanged_tree_is_not_swept(self):
        code, _out, progress = self.run_cli(commits=False)
        self.assertEqual(code, 0)
        self.assertIn(final.HEADING + ": not run", progress)
        self.assertIn("Commits: none (still c0)", progress)
        self.assertEqual(self.probe_runs, [])


class Record(unittest.TestCase):
    """devteam/probe_record: one entry per probe, the latest run of it."""

    def test_update_keeps_the_latest_of_each_probe_and_no_verifier(self):
        import datetime
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(probe_record.load(root), {})
            t1 = datetime.datetime(2026, 10, 10, 9, 0, 0)
            probe_record.update(root, sweep_rows(SET), "abc1234", when=t1)
            rows = {"probe:probe_a": row("probe:probe_a", 2, 1, ["check y"])}
            probe_record.update(root, rows, "def5678", dirty=True,
                                when=t1 + datetime.timedelta(hours=1))
            record = probe_record.load(root)
            self.assertEqual(sorted(record), ["probe_a", "probe_net_b"])
            self.assertEqual(record["probe_a"], {
                "when": "2026-10-10 10:00:00", "head": "def5678", "dirty": True,
                "ok": False, "passed": 2, "failed": 1, "failures": ["check y"]})
            self.assertEqual((record["probe_net_b"]["when"], record["probe_net_b"]["head"],
                              record["probe_net_b"]["ok"]), ("2026-10-10 09:00:00", "abc1234", True))
            self.assertEqual(probe_record.as_rows(record, LABELS + ["probe:none", "verify_x.py"]),
                             {"probe:probe_a": {"ok": False, "passed": 2, "failed": 1,
                                                "failures": ["check y"]},
                              "probe:probe_net_b": {"ok": True, "passed": 3, "failed": 0,
                                                    "failures": []}})
            self.assertEqual(probe_record.describe(record, LABELS + ["probe:none"]),
                             "recorded results of 2 of 3 probe(s), from 2026-10-10 09:00:00 "
                             "to 2026-10-10 10:00:00 at commits abc1234, def5678")
            self.assertEqual(probe_record.listing(record), [
                "  2026-10-10 09:00:00    abc1234  ok   probe_net_b  3/3",
                "  2026-10-10 10:00:00    def5678+ FAIL probe_a  2/3  -- check y"])
            self.assertEqual(len(probe_record.listing(record, "net")), 1)

    def test_a_corrupt_record_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.dirname(probe_record.path(root)))
            with open(probe_record.path(root), "w") as fh:
                fh.write("[1, 2")
            self.assertEqual(probe_record.load(root), {})
            self.assertEqual(probe_record.describe({}, LABELS),
                             "probe record, which holds no result for any of the 2 probe(s)")


if __name__ == "__main__":
    unittest.main()
