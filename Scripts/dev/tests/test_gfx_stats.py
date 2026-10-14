"""graphics_menu/gfx_stats.py: the engine quality groups as rows, and a row
from before them read as today's. Every preset is still what one engine
quality level made it (0, 2, 3, 3 in each group, and that level's shadow
numbers of BaseScalability.ini), in the table's defaults and in the tracked
CSV alike, and migrate_row (the rule gfx_save's load follows in the HUD's
graph) spreads an old row's engine quality over the new rows and moves no
other number.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import unittest

import _paths  # noqa: F401

from graphics_menu import gfx_stats as GS

LEVELS = (0, 2, 3, 3)
GROUPS = [s for s in GS.GFX_STATS if s.how == GS.GROUP]


def _legacy(level, base=100.0):
    """An old row: engine quality `level`, every other cell its own index."""
    row = [base + i for i in range(GS.LEGACY_STAT_COUNT)]
    row[GS.LEGACY_LEVEL_INDEX] = float(level)
    return row


class GroupRows(unittest.TestCase):
    def test_ten_groups_each_zero_to_three(self):
        self.assertEqual(len(GROUPS), 10)
        self.assertEqual(len({s.target for s in GROUPS}), 10)
        for s in GROUPS:
            self.assertEqual((s.lo, s.hi, s.step), (0, 3, 1), s.column)
            self.assertEqual(tuple(s.defaults), LEVELS, s.column)

    def test_no_engine_quality_row(self):
        self.assertNotIn(GS.LEGACY_LEVEL_COLUMN, GS.GFX_COLUMNS)

    def test_shadow_rows_default_to_their_level(self):
        for column, by_level in GS.SHADOW_BY_LEVEL.items():
            stat = GS.GFX_STATS[GS.index_of(column)]
            self.assertEqual(stat.how, GS.CVAR, column)
            self.assertEqual(tuple(stat.defaults), tuple(by_level[lv] for lv in LEVELS), column)
            self.assertLessEqual(stat.lo, min(by_level), column)
            self.assertGreaterEqual(stat.hi, max(by_level), column)

    def test_csv_presets_are_one_level(self):
        rows = GS.preset_rows()
        self.assertEqual(len(rows), len(GS.PRESET_LABELS))
        for row, level in zip(rows, LEVELS):
            self.assertEqual(len(row), GS.STAT_COUNT)
            for s in GROUPS:
                self.assertEqual(row[GS.index_of(s.column)], level, s.column)
            for column, by_level in GS.SHADOW_BY_LEVEL.items():
                self.assertEqual(row[GS.index_of(column)], by_level[level], column)


class Migration(unittest.TestCase):
    def test_every_stat_has_a_source(self):
        sources = GS.legacy_sources()
        self.assertEqual(len(sources), GS.STAT_COUNT)
        self.assertTrue(all(0 <= i < GS.LEGACY_STAT_COUNT for i in sources))
        self.assertEqual(len(GS.by_level_values()),
                         len(GS.BY_LEVEL_COLUMNS) * GS.LEVEL_COUNT)

    def test_engine_quality_is_spread(self):
        for level in range(GS.LEVEL_COUNT):
            new = GS.migrate_row(_legacy(level))
            for s in GROUPS:
                self.assertEqual(new[GS.index_of(s.column)], level, s.column)
            for column, by_level in GS.SHADOW_BY_LEVEL.items():
                self.assertEqual(new[GS.index_of(column)], by_level[level], column)

    def test_other_numbers_keep_their_column(self):
        new = GS.migrate_row(_legacy(2))
        for i, column in enumerate(GS.LEGACY_COLUMNS):
            if column != GS.LEGACY_LEVEL_COLUMN:
                self.assertEqual(new[GS.index_of(column)], 100.0 + i, column)

    def test_a_level_out_of_range_is_clamped(self):
        top = GS.migrate_row(_legacy(9))
        for column, by_level in GS.SHADOW_BY_LEVEL.items():
            self.assertEqual(top[GS.index_of(column)], by_level[-1], column)


if __name__ == "__main__":
    unittest.main()
