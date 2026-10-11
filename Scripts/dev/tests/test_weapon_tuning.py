"""combat/gun_tuning.csv against what the builders bake from it: every cell of
a gun's row is the number gun_rows.gun_row() hands weapon_specs, every cell of
the knife's and the axe's is melee_tuning's, and a cell or a row the CSV lacks
falls back the way gun_tuning.read_table says. Pure, so a wrong number fails
here in seconds rather than in a launch.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import csv
import os
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401

from combat import gun_rows as R
from combat import gun_tuning as T
from combat import melee_tuning as M
from combat.throw_tuning import THROW_DAMAGE_COLUMN
from combat.tuning import COMBAT

GUNS = tuple(R.GUN_DEFAULTS)
MINIMUM = {s[0]: s[4] for s in T.TUNE_STATS}
KIND = {s[0]: s[5] for s in T.TUNE_STATS}


def _cells(path=T.CSV_PATH):
    """{weapon: {column: number}} read off the file itself, not through
    read_table: every cell that is not empty."""
    with open(path, newline="") as f:
        return {row[T.WEAPON_COLUMN]: {c: float(v) for c, v in row.items()
                                       if c != T.WEAPON_COLUMN and v.strip()}
                for row in csv.DictReader(f)}


def _under_minimum(table):
    """["<weapon>.<column> = v, under its minimum m"] for every such cell."""
    return [f"{weapon}.{col} = {value:g}, under its minimum {MINIMUM[col]:g}"
            for weapon, row in table.items() for col, value in row.items()
            if value < MINIMUM[col]]


class TheTable(unittest.TestCase):
    """gun_tuning.csv as it is tracked."""

    def setUp(self):
        self.cells = _cells()

    def test_a_row_for_every_weapon_and_no_other(self):
        self.assertEqual(tuple(self.cells), GUNS + T.MELEE_WEAPONS,
                         "gun_tuning.csv: one row per gun, then the knife and the axe")

    def test_each_row_holds_its_own_columns_and_no_other(self):
        for weapon, row in self.cells.items():
            with self.subTest(weapon=weapon):
                self.assertEqual(
                    set(row), set(T.columns_of(weapon)),
                    f"{weapon}: its cells are not gun_tuning.columns_of({weapon!r})")

    def test_no_cell_is_under_its_minimum(self):
        self.assertEqual(_under_minimum(self.cells), [])

    def test_read_table_reads_every_cell(self):
        table = T.read_table()
        for weapon, row in self.cells.items():
            for col, value in row.items():
                with self.subTest(weapon=weapon, column=col):
                    self.assertEqual(table[weapon][col], KIND[col](value),
                                     f"{weapon}.{col}: read_table against the CSV's cell")
                    self.assertIs(type(table[weapon][col]), KIND[col],
                                  f"{weapon}.{col}: read as its TUNE_STATS kind")


class Guns(unittest.TestCase):
    """What a gun is built with is its row."""

    def test_every_gun_column_is_the_rows_cell(self):
        cells = _cells()
        for gun in GUNS:
            built = R.gun_row(gun)
            for col in T.GUN_COLUMNS:
                with self.subTest(gun=gun, column=col):
                    self.assertEqual(built[col], cells[gun][col],
                                     f"{gun}.{col}: built with {built[col]!r}, "
                                     f"gun_tuning.csv says {cells[gun][col]:g}")

    def test_every_gun_has_a_default_for_every_column(self):
        for gun in GUNS:
            with self.subTest(gun=gun):
                self.assertEqual(set(R.gun_row(gun, tuned={})), set(T.GUN_COLUMNS),
                                 f"{gun}: gun_rows' defaults against GUN_COLUMNS")

    def test_the_sights_timing_defaults_the_same_on_every_gun(self):
        # The zoom's speed, the zoom-in's length and the raise's (ads.py,
        # seat.py) are per gun on the GUN SETTINGS tab, and every gun starts
        # on COMBAT's one number for each.
        want = {"ads_zoom_speed": COMBAT.ads_interp_speed,
                "ads_zoom_in_s": COMBAT.ads_zoom_in_s,
                "ads_raise_s": COMBAT.ads_raise_s}
        for col in want:
            self.assertIn(col, T.GUN_COLUMNS, f"{col}: a gun's column")
            self.assertNotIn(col, T.MELEE_COLUMNS, f"{col}: not a melee weapon's")
        for gun in GUNS:
            with self.subTest(gun=gun):
                row = R.gun_row(gun, tuned={})
                self.assertEqual({c: row[c] for c in want}, want,
                                 f"{gun}: its sights timing defaults are COMBAT's")

    def test_weapon_specs_builds_from_gun_row(self):
        # weapon_specs imports unreal, so it is read, not run: its rows hold
        # no tunable number of their own, only gun_row()'s.
        path = os.path.join(os.path.dirname(T.CSV_PATH), "weapon_specs.py")
        with open(path) as f:
            source = f.read()
        self.assertIn('spec.update(gun_row(spec["display"], tuned))', source,
                      "weapon_specs._weapon_specs no longer lays gun_row() over its rows")
        for col in ("damage", "pellets", "magazine", "interval", "reload_s"):
            self.assertNotIn(f" {col}=", source,
                             f"weapon_specs: a literal {col}= beside gun_rows' table")


class Melee(unittest.TestCase):
    """What the knife and the axe are built with is their rows."""

    def test_melee_specs_is_the_rows(self):
        cells = _cells()
        specs = dict(M.melee_specs())
        self.assertEqual(tuple(specs), T.MELEE_WEAPONS)
        for weapon in T.MELEE_WEAPONS:
            for col in T.MELEE_COLUMNS:
                with self.subTest(weapon=weapon, column=col):
                    self.assertEqual(specs[weapon][col], cells[weapon][col],
                                     f"{weapon}.{col}: melee_specs against gun_tuning.csv")

    def test_throw_damage_is_the_rows_cell(self):
        cells = _cells()
        for weapon in T.MELEE_WEAPONS:
            with self.subTest(weapon=weapon):
                self.assertEqual(M.throw_damage(weapon), cells[weapon][THROW_DAMAGE_COLUMN],
                                 f"{weapon}: throw_damage against the row's throw_damage")

    def test_a_head_hit_is_worth_more_than_the_throw(self):
        self.assertGreater(COMBAT.head_multiplier, 1.0,
                           "COMBAT.head_multiplier: a head hit is worth more than a body hit")
        self.assertLess(COMBAT.limb_multiplier, 1.0,
                        "COMBAT.limb_multiplier: a limb hit is worth less than a body hit")
        for weapon, row in _cells().items():
            if weapon in T.MELEE_WEAPONS:
                thrown = row[THROW_DAMAGE_COLUMN]
                with self.subTest(weapon=weapon):
                    self.assertGreater(thrown * COMBAT.head_multiplier, thrown,
                                       f"{weapon}: a thrown head hit against its throw damage")

    def test_a_melee_weapon_with_no_row_keeps_its_defaults(self):
        with mock.patch.object(M, "read_table", lambda: {}):
            self.assertEqual(dict(M.melee_specs()), M.MELEE_DEFAULTS)


class Fallbacks(unittest.TestCase):
    """read_table on a table that is not whole."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "gun_tuning.csv")

    def _table(self, text):
        with open(self.path, "w") as f:
            f.write(text)
        return T.read_table(self.path)

    def test_no_file_is_no_table(self):
        self.assertEqual(T.read_table(self.path), {})

    def test_a_weapon_with_no_row_keeps_every_default(self):
        tuned = self._table("weapon,damage\nPistol,31\n")
        self.assertNotIn("Rifle", tuned)
        self.assertEqual(R.gun_row("Rifle", tuned), R.gun_row("Rifle", {}),
                         "Rifle: no row in the CSV, so gun_rows' defaults")

    def test_a_missing_column_keeps_its_default(self):
        tuned = self._table("weapon,damage\nPistol,31\n")
        built, default = R.gun_row("Pistol", tuned), R.gun_row("Pistol", {})
        self.assertEqual(built["damage"], 31.0, "Pistol.damage: the CSV's cell")
        for col in T.GUN_COLUMNS:
            if col != "damage":
                with self.subTest(column=col):
                    self.assertEqual(built[col], default[col],
                                     f"Pistol.{col}: no column in the CSV, so the default")

    def test_an_empty_cell_keeps_its_default(self):
        tuned = self._table("weapon,damage,range\nPistol,,7000\n")
        self.assertEqual(tuned, {"Pistol": {"range": 7000.0}})
        self.assertEqual(R.gun_row("Pistol", tuned)["damage"],
                         R.GUN_DEFAULTS["Pistol"]["damage"])

    def test_a_column_that_is_no_stat_is_not_read(self):
        self.assertEqual(self._table("weapon,damage,weight\nPistol,31,4\n"),
                         {"Pistol": {"damage": 31.0}})

    def test_an_int_column_is_rounded(self):
        self.assertEqual(self._table("weapon,magazine\nPistol,7.6\n"),
                         {"Pistol": {"magazine": 8}})

    def test_a_cell_that_is_no_number_raises(self):
        with self.assertRaises(ValueError):
            self._table("weapon,damage\nPistol,lots\n")

    def test_a_cell_under_its_minimum_is_read_and_named(self):
        # read_table holds no minimum (the page's Left never steps under it),
        # so a hand edit is read as written: the check above is what fails it.
        tuned = self._table("weapon,pellets,interval\nShotgun,0,0.85\nPistol,1,0.01\n")
        self.assertEqual(tuned["Shotgun"]["pellets"], 0)
        self.assertEqual(_under_minimum(tuned),
                         ["Shotgun.pellets = 0, under its minimum 1",
                          "Pistol.interval = 0.01, under its minimum 0.02"])


if __name__ == "__main__":
    unittest.main()
