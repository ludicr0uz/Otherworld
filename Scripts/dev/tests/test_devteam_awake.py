import os
import stat
import tempfile
import unittest

import _paths  # noqa: F401

from devteam import awake


class AwakeTest(unittest.TestCase):

    def fake_tool(self, body):
        """A stand-in caffeinate on disk, returning its name on PATH."""
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: os.system(f"rm -rf '{d}'"))
        path = os.path.join(d, "fakecaf")
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\n" + body + "\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def test_hold_runs_and_stops_the_tool(self):
        tool = self.fake_tool("sleep 60")
        said = []
        with awake.hold(say=said.append, tool=tool) as proc:
            self.assertIsNotNone(proc)
            self.assertIsNone(proc.poll())
            self.assertTrue(said and "holding" in said[0])
        self.assertIsNotNone(proc.poll())

    def test_tool_gets_our_pid(self):
        tool = self.fake_tool('echo "$@" > "$0.args"')
        with awake.hold(say=lambda _m: None, tool=tool) as proc:
            proc.wait(timeout=5)
        with open(tool + ".args") as fh:
            self.assertEqual(fh.read().split(), ["-i", "-w", str(os.getpid())])

    def test_without_the_tool(self):
        said = []
        with awake.hold(say=said.append, tool="/nonexistent/caffeinate") as proc:
            self.assertIsNone(proc)
        self.assertEqual(len(said), 1)
        self.assertIn("may sleep", said[0])


if __name__ == "__main__":
    unittest.main()
