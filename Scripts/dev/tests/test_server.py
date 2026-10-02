import json
import os
import shutil
import subprocess
import tempfile
import time
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

    def beat(self, **fields):
        with open(os.path.join(self.dir, "heartbeat"), "w") as fh:
            json.dump(dict({"pid": os.getpid(), "time": time.time()}, **fields), fh)

    def test_up_means_the_serve_loop_is_beating(self):
        # A beat from the Slate-tick listener came before serve() existed, and
        # the first job sent on the strength of it was the false alarm.
        self.beat()
        self.assertIsNone(server._serving(self.dir))
        self.assertFalse(server._wait_for_beat(self.dir, lambda: True, 0.3))
        self.beat(serving=True)
        self.assertTrue(server._wait_for_beat(self.dir, lambda: True, 0.3))

    def test_waiting_ends_when_the_editor_does(self):
        started = time.time()
        self.assertFalse(server._wait_for_beat(self.dir, lambda: False, 30))
        self.assertLess(time.time() - started, 5)

    def test_discard_kills_an_editor_that_no_longer_answers(self):
        proc = subprocess.Popen(["sleep", "60"])
        with open(os.path.join(self.dir, server.PID), "w") as fh:
            fh.write(str(proc.pid))
        self.beat(pid=proc.pid, serving=True)
        self.assertEqual(server.discard(self.dir, is_server=lambda pid, d: True), proc.pid)
        self.assertIsNotNone(proc.wait(timeout=5))
        self.assertEqual(os.listdir(self.dir), [])      # no beat or pid left to trust

    def test_discard_leaves_a_pid_that_is_not_its_editor(self):
        # A pid file outlives its process; the number may be someone else's now.
        proc = subprocess.Popen(["sleep", "60"])
        try:
            with open(os.path.join(self.dir, server.PID), "w") as fh:
                fh.write(str(proc.pid))
            self.assertIsNone(server.discard(self.dir))          # "sleep" is no editor
            self.assertIsNone(proc.poll())
        finally:
            proc.kill()
            proc.wait()

    def test_discard_with_nothing_recorded(self):
        self.assertIsNone(server.discard(self.dir))

    def test_the_serving_editor_is_told_not_to_listen_on_the_tick(self):
        seen = {}

        class Proc(object):
            pid = 4242

            def poll(self):
                return 0                         # "exited": ensure gives up at once

        def popen(cmd, **kwargs):
            seen["env"], seen["cmd"] = kwargs["env"], cmd
            return Proc()

        with mock.patch.object(server.subprocess, "Popen", popen), \
                mock.patch.object(server, "editor_cmd", lambda engine: "/E/UnrealEditor-Cmd"), \
                mock.patch.object(server, "uproject", lambda: "/P/P.uproject"), \
                mock.patch.object(server, "log", lambda msg: None):
            self.assertFalse(server.ensure("/E", self.dir, boot_timeout=5))
        self.assertEqual(seen["env"]["UEPY_SERVING"], "1")
        self.assertEqual(seen["env"]["UEPY_INBOX_DIR"], self.dir)
        self.assertNotIn(server.BOOTING, os.listdir(self.dir))


if __name__ == "__main__":
    unittest.main()
