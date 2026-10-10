import os
import shutil
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401

from uepylib import inbox, warm
from uepylib.targets import TargetResult


class CpuTest(unittest.TestCase):

    def test_ps_time_formats(self):
        self.assertEqual(warm.parse_cpu("  0:12.34\n"), 12.34)
        self.assertEqual(warm.parse_cpu("1:02:03.5"), 3723.5)
        self.assertEqual(warm.parse_cpu("2-00:00:01"), 2 * 86400 + 1)
        self.assertIsNone(warm.parse_cpu(""))
        self.assertIsNone(warm.parse_cpu("TIME"))


class WatchTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.now, self.used = 1000.0, 5.0
        self.log("boot noise\n=== Critical error: === from an earlier life\n")
        self.watch = warm.Watch(self.dir, 77, clock=lambda: self.now, cpu=lambda pid: self.used)

    def log(self, text):
        with open(os.path.join(self.dir, warm.LOG), "a") as fh:
            fh.write(text)

    def after(self, seconds, cpu=0.0):
        self.now += seconds
        self.used += cpu
        return self.watch()

    def test_only_what_the_log_gained_since_the_job_counts(self):
        self.assertIsNone(self.after(2))

    def test_a_critical_error_in_the_log_is_a_crash(self):
        self.log("LogPython: building\n")
        self.assertIsNone(self.after(2, cpu=2))
        self.log("[2026.10.01][151]LogMac: === Critical error: ===\nSIGSEGV\n")
        self.assertIn("crashed", self.after(2))

    def test_a_fatal_error_on_the_game_thread_is_a_crash(self):
        # It never writes the critical-error mark, and spins in appError.
        self.log("LogMac: Error: appError called: Fatal error: [File:Casts.cpp] [Line: 10]\n")
        self.assertIn("crashed", self.after(2, cpu=2))

    def test_the_mark_may_arrive_in_two_reads(self):
        self.log("LogMac: === Critical")
        self.assertIsNone(self.after(2))
        self.log(" error: ===\n")
        self.assertIn("crashed", self.after(2))

    def test_no_cpu_and_no_log_for_long_enough_is_a_hang(self):
        steps = int(warm.STALL_SECONDS / warm.SAMPLE_EVERY)
        for _ in range(steps - 1):
            self.assertIsNone(self.after(warm.SAMPLE_EVERY))
        self.assertIn("hung", self.after(warm.SAMPLE_EVERY))

    def test_a_working_editor_is_not_hung_however_quiet_its_log(self):
        for _ in range(int(warm.STALL_SECONDS / warm.SAMPLE_EVERY) * 3):
            self.assertIsNone(self.after(warm.SAMPLE_EVERY, cpu=8))

    def test_a_logging_editor_is_not_hung_however_little_cpu_it_uses(self):
        for _ in range(int(warm.STALL_SECONDS / warm.SAMPLE_EVERY) * 3):
            self.log("LogPython: waiting on a download\n")
            self.assertIsNone(self.after(warm.SAMPLE_EVERY))

    def test_a_cpu_reading_that_cannot_be_had_is_not_a_hang(self):
        self.watch.cpu = lambda pid: None
        for _ in range(int(warm.STALL_SECONDS / warm.SAMPLE_EVERY) * 3):
            self.assertIsNone(self.after(warm.SAMPLE_EVERY))


class RunTest(unittest.TestCase):
    """warm.run against a scripted editor: each entry of ``script`` is what
    the next job does -- a TargetResult's text, or a reason it was lost."""

    def setUp(self):
        self.boots, self.discards, self.sent, self.reported = 0, 0, [], []
        self.script = []
        self.can_boot = True

        def ensure(engine, directory, boot_timeout):
            self.boots += 1
            return self.can_boot

        def discard(directory):
            self.discards += 1

        def run_job(directory, kind, value, allow_pie=False, timeout=None, watch=None):
            self.sent.append(value)
            outcome = self.script.pop(0)
            if isinstance(outcome, str):
                return None, outcome
            return TargetResult(os.path.basename(value), True, 1.0, "ok"), ""

        for target, name, fake in ((warm.server, "ensure", ensure),
                                   (warm.server, "discard", discard),
                                   (warm.inbox, "run_job", run_job),
                                   (warm.inbox, "heartbeat", lambda d: {"pid": 1, "project": "P"}),
                                   (warm, "log", lambda msg: None)):
            patcher = mock.patch.object(target, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_targets(self, *names):
        targets = [("file", f"/s/{n}") for n in names]
        outcome = warm.run("/E", "/d", targets, self.reported.append,
                           make_watch=lambda d, pid: None)
        return outcome, targets

    def test_a_clean_run_boots_once(self):
        self.script = [True, True]
        outcome, left = self.run_targets("a.py", "b.py")
        self.assertTrue(outcome)
        self.assertEqual((self.boots, self.discards, left), (1, 0, []))
        self.assertEqual([r.label for r in self.reported], ["a.py", "b.py"])

    def test_a_target_whose_editor_dies_runs_again_in_a_fresh_one(self):
        self.script = [True, inbox.DIED, True, True]
        outcome, _left = self.run_targets("a.py", "b.py", "c.py")
        self.assertTrue(outcome)
        # a.py is not rebuilt: what it wrote is on disk for the fresh editor.
        self.assertEqual(self.sent, ["/s/a.py", "/s/b.py", "/s/b.py", "/s/c.py"])
        self.assertEqual((self.boots, self.discards), (2, 1))
        self.assertTrue(all(r.ok for r in self.reported))
        self.assertEqual(len(self.reported), 3)          # the lost attempt is not reported

    def test_each_target_gets_its_own_second_chance(self):
        self.script = ["the warm editor crashed", True, "the warm editor hung", True]
        outcome, _left = self.run_targets("a.py", "b.py")
        self.assertTrue(outcome)
        self.assertEqual(self.boots, 3)

    def test_a_target_that_takes_two_editors_down_fails(self):
        self.script = [inbox.DIED, inbox.DIED]
        outcome, left = self.run_targets("a.py", "b.py")
        self.assertFalse(outcome)
        self.assertEqual((self.boots, self.discards), (2, 2))
        self.assertEqual(self.sent, ["/s/a.py", "/s/a.py"])       # b.py is not attempted
        self.assertFalse(self.reported[0].ok)
        self.assertIn("twice", self.reported[0].text)
        self.assertEqual(left, [("file", "/s/b.py")])

    def test_a_timeout_is_not_retried_but_its_editor_is_killed(self):
        self.script = ["timed out after 1800s"]
        outcome, _left = self.run_targets("a.py")
        self.assertFalse(outcome)
        self.assertEqual((self.boots, self.discards, len(self.sent)), (1, 1, 1))

    def test_no_editor_leaves_the_rest_for_a_cold_run(self):
        self.can_boot = False
        outcome, left = self.run_targets("a.py", "b.py")
        self.assertIsNone(outcome)
        self.assertEqual(len(left), 2)
        self.assertEqual(self.reported, [])


if __name__ == "__main__":
    unittest.main()
