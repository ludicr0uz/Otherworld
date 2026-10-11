"""probes/starter_bare.py: which launches keep the starting garment."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from probes import starter_bare  # noqa: E402


class StarterBare(unittest.TestCase):
    def _file(self, text):
        fd, path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_declared_only_when_true_at_module_level(self):
        self.assertTrue(starter_bare.declared(self._file("STARTER_WORN = True\n")))
        self.assertFalse(starter_bare.declared(self._file("STARTER_WORN = False\n")))
        self.assertFalse(starter_bare.declared(self._file("LEVEL = '/Game/Maps/X'\n")))
        self.assertFalse(starter_bare.declared(self._file("def f():\n    STARTER_WORN = True\n")))
        self.assertFalse(starter_bare.declared("/no/such/probe.py"))

    def test_a_launch_is_bare_unless_every_probe_declares_it(self):
        keeps, plain = self._file("STARTER_WORN = True\n"), self._file("X = 1\n")
        self.assertTrue(starter_bare.bare([]))
        self.assertTrue(starter_bare.bare([plain]))
        self.assertTrue(starter_bare.bare([keeps, plain]))
        self.assertFalse(starter_bare.bare([keeps]))

    def test_the_probes_of_the_starting_garment_declare_it(self):
        probes = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "probes")
        for name in ("probe_starter_pants.py", "probe_title_figure.py"):
            self.assertTrue(starter_bare.declared(os.path.join(probes, name)), name)


if __name__ == "__main__":
    unittest.main()
