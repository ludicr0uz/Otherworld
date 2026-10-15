"""combat/gun_tuning_take.py: a packaged build's GUN SETTINGS save is taken
back over gun_tuning.csv only when its header is this project's, and what
moved is reported cell by cell.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import os
import tempfile
import unittest

import _paths  # noqa: F401

from combat import gun_tuning as T
from combat import gun_tuning_take as K


class TakeTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.old = os.path.join(self.dir.name, "old.csv")
        self.new = os.path.join(self.dir.name, "new.csv")
        T.write_table([("Pistol", {"damage": 26.0, "magazine": 8}),
                       ("Knife", {"throw_damage": 40.0})], self.old)

    def test_the_header_is_the_writer_s(self):
        self.assertEqual(K.header_problem(self.old), "")
        self.assertEqual(K.HEADER, ",".join((T.WEAPON_COLUMN,) + T.TUNE_COLUMNS))

    def test_a_tuned_cell_is_taken_and_reported(self):
        T.write_table([("Pistol", {"damage": 27.0, "magazine": 8}),
                       ("Knife", {"throw_damage": 40.0})], self.new)
        moved = K.take(self.new, self.old)
        self.assertEqual(moved, [("Pistol", "damage", 26.0, 27.0)])
        self.assertEqual(open(self.old).read(), open(self.new).read())

    def test_an_older_table_is_refused_and_nothing_copied(self):
        before = open(self.old).read()
        with open(self.new, "w") as f:
            f.write("weapon,damage\nPistol,99\n")
        with self.assertRaises(ValueError):
            K.take(self.new, self.old)
        self.assertEqual(open(self.old).read(), before)

    def test_the_newest_save_is_the_one_found(self):
        a, b = os.path.join(self.dir.name, "a.csv"), os.path.join(self.dir.name, "b.csv")
        for p, t in ((a, 100), (b, 200)):
            open(p, "w").close()
            os.utime(p, (t, t))
        self.assertEqual(K.newest([a, b, os.path.join(self.dir.name, "none")]), b)
        self.assertIsNone(K.newest([]))

    def test_the_mac_container_is_where_the_build_saves(self):
        paths = K.saved_copies(home="/h", local_app_data="C:/L")
        self.assertIn("/h/Library/Containers/com.YourCompany.Otherworld/Data/Library/"
                      "Application Support/Epic/Otherworld/Saved/Tuning/gun_tuning.csv", paths)
        self.assertTrue(paths[-1].endswith(os.path.join("Otherworld", "Saved", "Tuning",
                                                        "gun_tuning.csv")))


if __name__ == "__main__":
    unittest.main()
