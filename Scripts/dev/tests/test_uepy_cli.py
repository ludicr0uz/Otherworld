import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import _paths

sys.path.insert(0, _paths.DEV)
import uepy  # noqa: E402

from uepylib.targets import TargetResult  # noqa: E402


class ReporterTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        patcher = mock.patch.object(uepy, "saved_uepy",
                                    lambda *parts: os.path.join(self.tmp, *parts))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp)

    def feed(self, reporter, *results):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            for r in results:
                reporter(r)
        return out.getvalue()

    def test_summary_mode_prints_one_line_per_passing_script(self):
        rep = uepy.Reporter(summary_mode=True, quiet=False)
        text = self.feed(rep, TargetResult("v.py", True, 1.0,
                                           "[VERIFY] PASS a\n" * 50 + "[VERIFY] 50 passed, 0 failed"))
        self.assertEqual(text.strip().splitlines(),
                         ["[uepy] ok    v.py  50/50 checks passed  (1.0s)"])
        self.assertTrue(rep.ok)

    def test_a_failed_check_fails_the_run_in_either_mode(self):
        for summary_mode in (True, False):
            rep = uepy.Reporter(summary_mode, quiet=False)
            text = self.feed(rep, TargetResult("v.py", True, 1.0, "[VERIFY] 1 passed, 1 failed"))
            self.assertFalse(rep.ok)
            self.assertIn("FAIL", text)

    def test_full_mode_prints_everything_and_quiet_filters(self):
        rep = uepy.Reporter(summary_mode=False, quiet=True)
        text = self.feed(rep, TargetResult("b.py", True, 1.0, "routine\nLogPython: Warning: kept"))
        self.assertNotIn("routine", text)
        self.assertIn("kept", text)

    def test_save_keeps_the_full_log_and_writes_json(self):
        rep = uepy.Reporter(summary_mode=True, quiet=False)
        self.feed(rep, TargetResult("v.py", True, 1.0, "[VERIFY] 3/4 checks passed\n[VERIFY] FAIL x"))
        json_path = os.path.join(self.tmp, "out.json")
        with contextlib.redirect_stdout(io.StringIO()):
            rep.save(json_path)
        (log_name,) = os.listdir(os.path.join(self.tmp, "runs"))
        with open(os.path.join(self.tmp, "runs", log_name)) as fh:
            self.assertIn("[VERIFY] FAIL x", fh.read())
        with open(json_path) as fh:
            (row,) = json.load(fh)
        self.assertEqual((row["label"], row["passed"], row["failed"], row["ok"]),
                         ("v.py", 3, 1, False))
        self.assertEqual(row["failures"], ["x"])


class WarmPathTest(unittest.TestCase):
    """main() under $UEPY_SERVE: the targets go to uepylib.warm, and whatever
    it could not run (no editor could be booted) goes to a cold run."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.script = os.path.join(self.tmp, "a.py")
        with open(self.script, "w") as fh:
            fh.write("pass\n")
        self.cold = []
        for target, name, fake in (
                (uepy, "saved_uepy", lambda *parts: os.path.join(self.tmp, *parts)),
                (uepy, "engine_dir", lambda override: "/E"),
                (uepy.cold, "run_cold", lambda engine, targets, report, timeout:
                    self.cold.append(list(targets)))):
            patcher = mock.patch.object(target, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def main(self, warm_run, *argv):
        env = dict(os.environ, UEPY_SERVE=os.path.join(self.tmp, "serve"))
        env.pop("UEPY_COLD", None)
        with mock.patch.object(uepy.warm, "run", warm_run), \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, "argv", ["uepy.py", *argv]), \
                contextlib.redirect_stdout(io.StringIO()):
            return uepy.main()

    def test_targets_run_in_the_warm_editor(self):
        seen = {}

        def warm_run(engine, directory, targets, report, allow_pie, boot_timeout):
            seen["directory"], seen["targets"] = directory, list(targets)
            report(TargetResult("a.py", True, 1.0, "fine"))
            del targets[:]
            return True

        self.assertEqual(self.main(warm_run, self.script), 0)
        self.assertEqual(seen["directory"], os.path.join(self.tmp, "serve"))
        self.assertEqual(seen["targets"], [("file", self.script)])
        self.assertEqual(self.cold, [])

    def test_a_target_lost_twice_fails_the_call(self):
        def warm_run(engine, directory, targets, report, allow_pie, boot_timeout):
            report(TargetResult("a.py", False, 0.0, "the warm editor died mid-run -- twice"))
            return False

        self.assertEqual(self.main(warm_run, self.script), 1)
        self.assertEqual(self.cold, [])

    def test_with_no_warm_editor_the_rest_runs_cold(self):
        self.assertEqual(self.main(lambda *a: None, self.script, "-c", "x = 1"), 0)
        self.assertEqual(self.cold, [[("file", self.script), ("code", "x = 1")]])


if __name__ == "__main__":
    unittest.main()
