"""The on-disk baseline cache and the gate's warm/cold sweep switch."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from devteam import baseline_cache, gate  # noqa: E402

ROWS = {"verify_x.py": {"label": "verify_x.py", "ok": True, "passed": 3, "failed": 0}}


class BaselineCache(unittest.TestCase):
    def test_second_run_on_unchanged_tree_hits(self):
        with tempfile.TemporaryDirectory() as root:
            state = ("abc", " M a.py\n")
            self.assertIsNone(baseline_cache.load(root, state))
            baseline_cache.save(root, state, ROWS)
            self.assertEqual(baseline_cache.load(root, state), ROWS)

    def test_changed_tree_misses(self):
        with tempfile.TemporaryDirectory() as root:
            baseline_cache.save(root, ("abc", ""), ROWS)
            self.assertIsNone(baseline_cache.load(root, ("abd", "")))
            self.assertIsNone(baseline_cache.load(root, ("abc", " M a.py\n")))

    def test_failed_sweep_and_corrupt_file_are_not_cached(self):
        with tempfile.TemporaryDirectory() as root:
            baseline_cache.save(root, ("a", ""), None)
            self.assertFalse(os.path.exists(baseline_cache.path(root)))
            os.makedirs(os.path.dirname(baseline_cache.path(root)))
            with open(baseline_cache.path(root), "w") as fh:
                fh.write("{nope")
            self.assertIsNone(baseline_cache.load(root, ("a", "")))


class SweepMode(unittest.TestCase):
    def _cmd_env(self, serve):
        with mock.patch.object(gate.subprocess, "run") as run, \
                mock.patch.object(gate, "sweep_targets", return_value=["t.py"]):
            gate.run_sweep(tempfile.gettempdir(), os.devnull, serve)
        return run.call_args.args[0], run.call_args.kwargs["env"]

    def test_after_sweep_is_cold(self):
        cmd, env = self._cmd_env(None)
        self.assertIn("--cold", cmd)
        self.assertIsNone(env)

    def test_before_sweep_is_warm(self):
        cmd, env = self._cmd_env("/tmp/serve")
        self.assertNotIn("--cold", cmd)
        self.assertEqual(env["UEPY_SERVE"], "/tmp/serve")

    def test_table_reports_duration(self):
        out = gate.table(ROWS, ROWS, {"baseline": "cached", "after": "90s (cold)"})
        self.assertIn("Sweep time: baseline cached, after 90s (cold)", out)


if __name__ == "__main__":
    unittest.main()
