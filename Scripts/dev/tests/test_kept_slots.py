import os
import tempfile
import unittest

import _paths  # noqa: F401

from probes import kept_slots

SLOTS = ("A", "B")


class KeptSlotsTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def _write(self, name, text):
        with open(os.path.join(self.dir, name), "w") as f:
            f.write(text)

    def _read(self, name):
        path = os.path.join(self.dir, name)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return f.read()

    def test_a_run_starts_without_the_developers_saves_and_gives_them_back(self):
        self._write("A.sav", "mine")
        kept_slots.set_aside(self.dir, SLOTS)
        self.assertIsNone(self._read("A.sav"))
        self._write("A.sav", "a probe's")
        self._write("B.sav", "a probe's")
        kept_slots.put_back(self.dir, SLOTS)
        self.assertEqual(self._read("A.sav"), "mine")
        self.assertIsNone(self._read("B.sav"))
        self.assertEqual(sorted(os.listdir(self.dir)), ["A.sav"])

    def test_a_probes_saves_are_cleared_for_the_next_probe(self):
        kept_slots.set_aside(self.dir, SLOTS)
        self._write("B.sav", "a probe's")
        kept_slots.clear(self.dir, SLOTS)
        self.assertEqual(os.listdir(self.dir), [])

    def test_a_killed_runs_leftovers_do_not_replace_what_was_set_aside(self):
        self._write("A.sav", "mine")
        kept_slots.set_aside(self.dir, SLOTS)
        self._write("A.sav", "a dead probe's")      # the run was killed here
        kept_slots.set_aside(self.dir, SLOTS)
        self.assertIsNone(self._read("A.sav"))
        kept_slots.put_back(self.dir, SLOTS)
        self.assertEqual(self._read("A.sav"), "mine")

    def test_other_files_are_left_alone(self):
        self._write("Settings.sav", "binds")
        kept_slots.set_aside(self.dir, SLOTS)
        kept_slots.put_back(self.dir, SLOTS)
        self.assertEqual(self._read("Settings.sav"), "binds")


if __name__ == "__main__":
    unittest.main()
