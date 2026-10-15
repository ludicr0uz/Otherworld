"""combat/player_tuning: the PLAYER SETTINGS tab's table, and the sights'
two timings in it (the zoom-in before the cut, the gun's raise), which go
down to 0 and are what COMBAT builds the weapon component with."""

import os
import tempfile
import unittest

import _paths  # noqa: F401

from combat import player_tuning as P
from combat.tuning import COMBAT


class SightTimings(unittest.TestCase):
    def _row(self, col):
        return next(s for s in P.PLAYER_STATS if s[0] == col)

    def test_the_sights_rows_go_down_to_zero(self):
        for col in (P.SIGHT_ZOOM_IN, P.SIGHT_RAISE):
            with self.subTest(col=col):
                _col, _label, step, minimum, _default = self._row(col)
                self.assertEqual(minimum, 0.0)
                self.assertGreater(step, 0.0)

    def test_the_stamina_rows_stay_off_zero(self):
        # per_second divides by them.
        for col in (P.SPRINT_DURATION, P.STAMINA_RECHARGE):
            self.assertGreater(self._row(col)[3], 0.0)

    def test_combat_builds_with_the_tables_timings(self):
        built = P.table()
        self.assertEqual(COMBAT.ads_zoom_in_s, built[P.SIGHT_ZOOM_IN])
        self.assertEqual(COMBAT.ads_raise_s, built[P.SIGHT_RAISE])

    def test_a_zero_survives_the_csv(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "player_tuning.csv")
            values = {s[0]: s[4] for s in P.PLAYER_STATS}
            values[P.SIGHT_ZOOM_IN] = 0.0
            values[P.SIGHT_RAISE] = 0.0
            P.write_table(values, path)
            back = P.table(path)
        self.assertEqual(back[P.SIGHT_ZOOM_IN], 0.0)
        self.assertEqual(back[P.SIGHT_RAISE], 0.0)


if __name__ == "__main__":
    unittest.main()
