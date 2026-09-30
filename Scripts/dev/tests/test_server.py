import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401

from uepylib import paths, server


class ServeInboxTest(unittest.TestCase):

    def test_uepy_serve_redirects_the_editor_inbox(self):
        with mock.patch.dict(os.environ, {"UEPY_SERVE": "/x/Saved/uepy/devteam"}):
            self.assertEqual(paths.serve_inbox(), "/x/Saved/uepy/devteam")
            self.assertEqual(paths.editor_inbox(), "/x/Saved/uepy/devteam")

    def test_without_it_the_editor_inbox_is_saved_uepy(self):
        env = {k: v for k, v in os.environ.items() if k != "UEPY_SERVE"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(paths.serve_inbox())
            self.assertTrue(paths.editor_inbox().endswith(os.path.join("Saved", "uepy")))


class ServerTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_one_caller_boots_at_a_time(self):
        self.assertTrue(server._claim_boot(self.dir))
        # The lock names this (live) process: a second caller must wait.
        self.assertFalse(server._claim_boot(self.dir))

    def test_a_lock_left_by_a_dead_caller_is_taken_over(self):
        proc = subprocess.Popen(["true"])
        proc.wait()
        with open(os.path.join(self.dir, server.BOOTING), "w") as fh:
            fh.write(str(proc.pid))
        self.assertTrue(server._claim_boot(self.dir))

    def test_stop_with_nothing_running(self):
        self.assertFalse(server.stop(self.dir))

    def test_stop_asks_first(self):
        # A stand-in server: exits once the stop file appears.
        stop_file = os.path.join(self.dir, server.STOP)
        proc = subprocess.Popen(["/bin/sh", "-c", f'while [ ! -e "{stop_file}" ]; do sleep 0.05; done'])
        with open(os.path.join(self.dir, server.PID), "w") as fh:
            fh.write(str(proc.pid))
        with mock.patch.object(server.inbox, "pid_alive", lambda pid: proc.poll() is None):
            self.assertTrue(server.stop(self.dir, seconds=10))
        self.assertEqual(proc.wait(timeout=5), 0)     # exited on request, not killed


if __name__ == "__main__":
    unittest.main()
