"""The server's population budget (task M29): its numbers in the monster
tuning table make a budget, for every creature.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import unittest

import _paths  # noqa: F401

from forest_generator import npc_placement as N
from forest_generator import npc_population as P
from net.relevancy_consts import CHARACTER, M_TO_CM
from npc import monster_tuning as M

COLUMNS = ("pop_per_player", "pop_server_cap", "pop_despawn_cm")


class PopulationBudget(unittest.TestCase):
    def test_columns_are_in_the_table_and_the_csv(self):
        for column in COLUMNS:
            self.assertIn(column, M.MONSTER_COLUMNS)
        table = M.read_table()
        for variant in N.NPC_VARIANTS:
            for column in COLUMNS:
                self.assertIn(column, table[variant.key], f"{variant.key} lacks {column}")

    def test_one_player_meets_the_level_s_pack(self):
        self.assertEqual(sum(P.NPC_POP_PER_PLAYER.values()), N.NPC_COUNT)
        for index in range(1, N.NPC_COUNT + 1):
            self.assertIn(N.variant_for_index(index).key, P.NPC_POP_PER_PLAYER)

    def test_each_creature_s_numbers_make_a_budget(self):
        for variant in N.NPC_VARIANTS:
            spec = M.monster_specs(variant.key)
            self.assertGreaterEqual(spec["pop_per_player"], 0.0)
            self.assertGreaterEqual(spec["pop_server_cap"], spec["pop_per_player"])
            # Removed where no client is sent it, and beyond where one appears.
            self.assertGreater(spec["pop_despawn_cm"], CHARACTER.cull_m * M_TO_CM)
            self.assertGreater(spec["pop_despawn_cm"], N.NPC_SPAWN_MAX_DISTANCE_CM)

    def test_the_tab_cannot_step_the_range_inside_the_band(self):
        floor = {s[0]: s[4] for s in M.MONSTER_STATS}["pop_despawn_cm"]
        self.assertGreater(floor, N.NPC_SPAWN_MAX_DISTANCE_CM)


if __name__ == "__main__":
    unittest.main()
