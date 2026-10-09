"""uepylib/probe_level.py: which level a probe launch boots."""
import os
import tempfile
import unittest

from _paths import *  # noqa: F401,F403  (puts Scripts/dev on sys.path)
from uepylib import game, probe_level


class ProbeLevelTest(unittest.TestCase):
    def _probe(self, tmp, name, body):
        path = os.path.join(tmp, name)
        with open(path, "w") as fh:
            fh.write(body)
        return path

    def test_groups_by_declared_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._probe(tmp, "a.py", "def probe(p):\n    yield 0\n")
            b = self._probe(tmp, "b.py", 'LEVEL = "/Game/Maps/Lvl_Forest_200m"  # why\n')
            c = self._probe(tmp, "c.py", "SYSTEMS = ()\n")
            self.assertEqual(probe_level.by_level([a, b, c]),
                             [(probe_level.PROBE_MAP, [a, c]), ("/Game/Maps/Lvl_Forest_200m", [b])])

    def test_explicit_map_wins_and_no_probe_keeps_old_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = self._probe(tmp, "b.py", 'LEVEL = "/Game/Maps/Lvl_Forest_200m"\n')
            self.assertEqual(probe_level.by_level([b], "/Game/Maps/X"), [("/Game/Maps/X", [b])])
        self.assertEqual(probe_level.by_level([]), [(game.DEFAULT_MAP, [])])


if __name__ == "__main__":
    unittest.main()
