import contextlib
import io
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

import _paths

sys.path.insert(0, _paths.DEV)
import uepy  # noqa: E402
from uepylib import detach  # noqa: E402

FAKE = "import sys, time\ntime.sleep(float(sys.argv[1]))\nprint('report line')\nsys.exit(int(sys.argv[2]))\n"


class DetachTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.script = os.path.join(self.tmp, "fake.py")
        with open(self.script, "w") as fh:
            fh.write(FAKE)
        self.root = os.path.join(self.tmp, "detached")

    def quiet(self, fn, *a, **k):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            r = fn(*a, **k)
        return r, out.getvalue()

    def test_start_returns_at_once_and_wait_prints_report(self):
        t0 = time.time()
        run, _ = self.quiet(detach.start, ["1", "0"], self.root, self.script)
        self.assertLess(time.time() - t0, 0.8)
        self.assertEqual(detach.state(run), "running")
        code, out = self.quiet(detach.wait, run, 20, 0.1)
        self.assertEqual(code, 0)
        self.assertIn("report line", out)
        self.assertEqual(detach.state(run), "done")

    def test_wait_returns_the_runs_exit_code(self):
        run, _ = self.quiet(detach.start, ["0", "3"], self.root, self.script)
        code, _ = self.quiet(detach.wait, run, 20, 0.1)
        self.assertEqual(code, 3)

    def test_second_start_refuses_while_one_runs(self):
        run, _ = self.quiet(detach.start, ["2", "0"], self.root, self.script)
        again, _ = self.quiet(detach.start, ["0", "0"], self.root, self.script)
        self.assertIsNone(again)
        self.quiet(detach.wait, run, 20, 0.1)
        time.sleep(1.1)  # a new stamp
        third, _ = self.quiet(detach.start, ["0", "0"], self.root, self.script)
        self.assertIsNotNone(third)
        self.quiet(detach.wait, third, 20, 0.1)

    def test_wait_times_out(self):
        run, _ = self.quiet(detach.start, ["5", "0"], self.root, self.script)
        code, _ = self.quiet(detach.wait, run, 0.3, 0.1)
        self.assertEqual(code, 1)
        self.quiet(detach.wait, run, 20, 0.1)

    def test_dead_run_without_result_fails_fast(self):
        run = os.path.join(self.root, "x")
        os.makedirs(run)
        with open(os.path.join(run, "pid"), "w") as fh:
            fh.write("999999")
        code, _ = self.quiet(detach.wait, run, 20, 0.1)
        self.assertEqual(code, 1)
        self.assertEqual(detach.state(run), "dead")

    def test_status_lists_runs(self):
        run, _ = self.quiet(detach.start, ["0", "0"], self.root, self.script)
        self.quiet(detach.wait, run, 20, 0.1)
        _, out = self.quiet(detach.status, self.root)
        self.assertIn(run, out)
        self.assertIn("done (exit 0)", out)

    def test_cli_detach_needs_game_or_net(self):
        with mock.patch.object(sys, "argv", ["uepy.py", "--detach"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                uepy.main()


if __name__ == "__main__":
    unittest.main()
