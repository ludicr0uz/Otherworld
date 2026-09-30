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


if __name__ == "__main__":
    unittest.main()
