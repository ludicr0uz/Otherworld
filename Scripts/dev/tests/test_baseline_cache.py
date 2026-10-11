"""The on-disk baseline cache (keyed and scoped by the files a suite reads)
and the gate's warm/cold sweep switch."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from devteam import baseline_cache, gate  # noqa: E402

ROWS = {"verify_x.py": {"label": "verify_x.py", "ok": True, "passed": 3, "failed": 0}}
FILES = {"Scripts/combat/axe.py": "a1", "Scripts/graphics_menu/tune_tab.py": "m1",
         "docs/notes.md": "d1", "Scripts/dev/tasks.md": "t1"}


class BaselineCache(unittest.TestCase):
    def test_second_run_on_unchanged_tree_hits(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(baseline_cache.load(root, FILES))
            baseline_cache.save(root, FILES, ROWS)
            self.assertEqual(baseline_cache.load(root, FILES), (ROWS, []))
            self.assertEqual(baseline_cache.exact(root, FILES), ROWS)

    def test_a_change_no_suite_reads_is_the_same_tree(self):
        with tempfile.TemporaryDirectory() as root:
            baseline_cache.save(root, FILES, ROWS)
            moved = dict(FILES, **{"docs/notes.md": "d2", "Scripts/dev/tasks.md": "t2",
                                   "Scripts/probes/probe_x.py": "p1", "CLAUDE.md": "c1"})
            self.assertEqual(baseline_cache.load(root, moved), (ROWS, []))

    def test_a_change_a_suite_reads_names_its_paths(self):
        with tempfile.TemporaryDirectory() as root:
            baseline_cache.save(root, FILES, ROWS)
            moved = dict(FILES, **{"Scripts/combat/axe.py": "a2", "docs/notes.md": "d2"})
            self.assertEqual(baseline_cache.load(root, moved), (ROWS, ["Scripts/combat/axe.py"]))
            self.assertIsNone(baseline_cache.exact(root, moved))
            gone = {p: h for p, h in FILES.items() if p != "Scripts/graphics_menu/tune_tab.py"}
            self.assertEqual(baseline_cache.load(root, gone)[1], ["Scripts/graphics_menu/tune_tab.py"])

    def test_an_entry_older_than_a_day_is_a_miss(self):
        with tempfile.TemporaryDirectory() as root:
            baseline_cache.save(root, FILES, ROWS, now=1000.0)
            self.assertEqual(baseline_cache.load(root, FILES, now=1000.0 + 23 * 3600), (ROWS, []))
            self.assertIsNone(baseline_cache.load(root, FILES, now=1000.0 + 25 * 3600))
            self.assertIsNone(baseline_cache.exact(root, FILES, now=1000.0 + 25 * 3600))

    def test_failed_sweep_and_corrupt_file_are_not_cached(self):
        with tempfile.TemporaryDirectory() as root:
            baseline_cache.save(root, FILES, None)
            self.assertFalse(os.path.exists(baseline_cache.path(root)))
            os.makedirs(os.path.dirname(baseline_cache.path(root)))
            with open(baseline_cache.path(root), "w") as fh:
                fh.write("{nope")
            self.assertIsNone(baseline_cache.load(root, FILES))


class SweepMode(unittest.TestCase):
    def _cmd_env(self, serve, suites=None):
        with mock.patch.object(gate.subprocess, "run") as run, \
                mock.patch.object(gate, "sweep_targets", return_value=["/r/t.py", "/r/u.py"]):
            gate.run_sweep(tempfile.gettempdir(), os.devnull, serve, suites)
        return run.call_args.args[0], run.call_args.kwargs["env"]

    def test_after_sweep_is_cold(self):
        cmd, env = self._cmd_env(None)
        self.assertIn("--cold", cmd)
        self.assertIsNone(env)
        self.assertEqual(cmd[-2:], ["/r/t.py", "/r/u.py"])

    def test_before_sweep_is_warm(self):
        cmd, env = self._cmd_env("/tmp/serve")
        self.assertNotIn("--cold", cmd)
        self.assertEqual(env["UEPY_SERVE"], "/tmp/serve")

    def test_a_scoped_sweep_runs_the_named_suites_only(self):
        cmd, _env = self._cmd_env(None, {"u.py"})
        self.assertEqual(cmd[-1], "/r/u.py")
        self.assertNotIn("/r/t.py", cmd)

    def test_table_reports_duration(self):
        out = gate.table(ROWS, ROWS, {"baseline": "cached", "after": "90s (cold)"})
        self.assertIn("Sweep time: baseline cached, after 90s (cold)", out)


if __name__ == "__main__":
    unittest.main()
