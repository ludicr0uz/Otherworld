"""The Horde Survival level's difficulty (forest_generator/npc_horde.py): a
level every three minutes, 4 monsters at level 1 and 2 more each level, one
wendigo for every four levels, as the task asked."""

import unittest

import _paths  # noqa: F401

from forest_generator import npc_horde as H


class HordeDifficulty(unittest.TestCase):
    def test_a_level_every_three_minutes(self):
        self.assertEqual(H.horde_level(0.0), 1)
        self.assertEqual(H.horde_level(179.9), 1)
        self.assertEqual(H.horde_level(180.0), 2)
        self.assertEqual(H.horde_level(540.0), 4)

    def test_it_stops_at_the_top(self):
        self.assertEqual(H.horde_level(10 * 3600.0), H.HORDE_MAX_LEVEL)
        self.assertEqual(H.horde_level(-5.0), 1)

    def test_four_six_eight(self):
        self.assertEqual([H.horde_total(n) for n in (1, 2, 3, 4)], [4, 6, 8, 10])

    def test_no_wendigo_until_level_four(self):
        for level in (1, 2, 3):
            self.assertEqual(H.horde_wendigos(level), 0)
            self.assertEqual(H.horde_zombies(level), H.horde_total(level))

    def test_one_wendigo_for_nine_zombies(self):
        self.assertEqual((H.horde_zombies(4), H.horde_wendigos(4)), (9, 1))
        self.assertEqual((H.horde_zombies(8), H.horde_wendigos(8)), (16, 2))

    def test_the_top(self):
        top = H.HORDE_MAX_LEVEL
        self.assertEqual((H.horde_total(top), H.horde_wendigos(top)), (42, 5))


if __name__ == "__main__":
    unittest.main()
