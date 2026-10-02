import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

import _paths  # noqa: F401

from uepylib import inbox


def dead_pid():
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


class InboxTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def beat(self, pid=None, age=0.0, busy=None, serving=False):
        with open(os.path.join(self.dir, "heartbeat"), "w") as fh:
            json.dump({"pid": pid or os.getpid(), "time": time.time() - age,
                       "project": "P.uproject", "busy": busy, "serving": serving}, fh)

    def test_a_busy_listener_is_alive_however_old_its_beat(self):
        self.beat(age=600, busy="job1")
        self.assertIsNotNone(inbox.heartbeat(self.dir))

    def test_a_busy_listener_that_died_is_not(self):
        self.beat(pid=dead_pid(), age=600, busy="job1")
        self.assertIsNone(inbox.heartbeat(self.dir))

    def test_no_heartbeat(self):
        self.assertIsNone(inbox.heartbeat(self.dir))

    def test_fresh_heartbeat_of_a_live_process(self):
        self.beat()
        self.assertEqual(inbox.heartbeat(self.dir)["pid"], os.getpid())

    def test_stale_heartbeat(self):
        self.beat(age=inbox.EDITOR_FRESH_SECONDS + 1)
        self.assertIsNone(inbox.heartbeat(self.dir))
        self.assertIsNotNone(inbox.heartbeat(self.dir, fresh=inbox.GAME_FRESH_SECONDS))

    def test_a_serving_loop_may_be_silent_for_longer(self):
        # It collects garbage between jobs, which after a big build takes a while.
        self.beat(age=inbox.EDITOR_FRESH_SECONDS + 5, serving=True)
        self.assertIsNotNone(inbox.heartbeat(self.dir))
        self.beat(age=inbox.SERVING_FRESH_SECONDS + 1, serving=True)
        self.assertIsNone(inbox.heartbeat(self.dir))

    def test_fresh_heartbeat_of_a_dead_process(self):
        # A killed game leaves a beat that is still "fresh" for a while.
        self.beat(pid=dead_pid())
        self.assertIsNone(inbox.heartbeat(self.dir))

    def test_send_writes_a_whole_request(self):
        result_path = inbox.send(self.dir, "code", "x = 1", allow_pie=True)
        request = result_path[: -len(".result")] + ".request"
        with open(request) as fh:
            self.assertEqual(json.load(fh), {"kind": "code", "value": "x = 1",
                                             "allow_pie": True})
        self.assertFalse(any(n.endswith(".tmp") for n in os.listdir(self.dir)))

    def test_nothing_listening_returns_none(self):
        self.assertIsNone(inbox.run_inbox([("code", "x")], lambda r: None, self.dir))

    def test_round_trip_through_a_fake_listener(self):
        self.beat()
        stop = threading.Event()

        def listener():
            while not stop.is_set():
                for name in os.listdir(self.dir):
                    if name.endswith(".request"):
                        os.remove(os.path.join(self.dir, name))
                        out = os.path.join(self.dir, name.replace(".request", ".result"))
                        with open(out, "w") as fh:
                            json.dump({"success": True, "output": "[VERIFY] 1 passed, 0 failed",
                                       "seconds": 0.5}, fh)
                time.sleep(0.01)

        thread = threading.Thread(target=listener)
        thread.start()
        got = []
        try:
            ok = inbox.run_inbox([("code", "a"), ("file", "/x/b.py")], got.append, self.dir)
        finally:
            stop.set()
            thread.join()
        self.assertTrue(ok)
        self.assertEqual([r.label for r in got], ["<statement>", "b.py"])
        self.assertTrue(all(r.ok and r.seconds == 0.5 for r in got))

    def test_a_listener_that_dies_takes_its_job_back(self):
        self.beat()

        def die():
            time.sleep(0.2)
            os.remove(os.path.join(self.dir, "heartbeat"))

        threading.Thread(target=die).start()
        got = []
        ok = inbox.run_inbox([("code", "a")], got.append, self.dir, timeout=5)
        self.assertFalse(ok)
        self.assertFalse(got[0].ok)
        self.assertEqual([n for n in os.listdir(self.dir) if n.endswith(".request")], [])

    def test_a_watch_ends_the_wait_and_takes_the_job_back(self):
        self.beat(age=600, busy="job1")          # alive and busy: would wait for ever
        calls = []

        def watch():
            calls.append(1)
            return "the editor crashed" if len(calls) > 3 else None

        result, why = inbox.run_job(self.dir, "code", "a", timeout=5, watch=watch)
        self.assertIsNone(result)
        self.assertEqual(why, "the editor crashed")
        self.assertEqual([n for n in os.listdir(self.dir) if n.endswith(".request")], [])

    def test_a_result_that_is_there_beats_the_watch(self):
        self.beat()
        real_send = inbox.send

        def send_and_answer(directory, kind, value, allow_pie=False):
            path = real_send(directory, kind, value, allow_pie)
            with open(path, "w") as fh:
                json.dump({"success": True, "output": "done", "seconds": 1.0}, fh)
            return path

        inbox.send = send_and_answer
        try:
            result, why = inbox.run_job(self.dir, "file", "/x/b.py", watch=lambda: "crashed")
        finally:
            inbox.send = real_send
        self.assertEqual((result.label, result.ok, result.text, why), ("b.py", True, "done", ""))

    def test_a_timeout_takes_the_job_back(self):
        self.beat(age=600, busy="job1")
        result, why = inbox.run_job(self.dir, "code", "a", timeout=0.2)
        self.assertIsNone(result)
        self.assertIn("timed out", why)
        self.assertEqual([n for n in os.listdir(self.dir) if n.endswith(".request")], [])


if __name__ == "__main__":
    unittest.main()
