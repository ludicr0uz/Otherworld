"""The gun tuning table: gun_tuning.csv beside this module, one row per gun.

The CSV is the tracked copy of every number the in-game GUN SETTINGS page (the
M panel's gun tuning tab, graphics_menu/tune_*.py) can change. It is written by that
page's save (graphics_menu/tune_save.py) and read by weapon_specs._weapon_specs(),
which lays each row over the literals there. So a value tuned in a game and
saved lands in the Blueprints the next time build_weapons_and_combat.py runs,
and git shows what moved.

A column or row the CSV lacks falls back to the literal in weapon_specs /
tuning.py. Pure Python (no unreal import): the game's save imports it too.

The melee weapons have rows as well (MELEE_WEAPONS, under the guns), read by
melee_tuning.py for the knife's and the axe's builders. Not every column is
every weapon's: columns_of() says which are, and a cell outside them is empty
in the CSV, a dash on the page, and never written onto the weapon.
"""

import csv
import os

from combat.sway_tuning import SWAY_RATE_COLUMN, SWAY_RATE_VAR
from combat.throw_tuning import THROW_DAMAGE_COLUMN, THROW_PITCH_COLUMN

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gun_tuning.csv")


# One per tunable number, in the page's row order and the CSV's column order:
# (spec column, BP_WeaponItem variable, the page's label, step, minimum, kind).
# Left/Right on the page move a value by one step and never under its minimum.
# An int is held as a float on the page (its step and minimum are whole) and
# rounded when it is written onto a gun.
TUNE_STATS = (
    ("damage", "Damage", "damage", 1.0, 0.0, float),
    ("pellets", "PelletCount", "pellets", 1.0, 1.0, int),
    ("range", "WeaponRange", "range (cm)", 250.0, 250.0, float),
    ("interval", "FireInterval", "fire interval (s)", 0.01, 0.02, float),
    ("reload_s", "ReloadSeconds", "reload (s)", 0.1, 0.0, float),
    ("magazine", "MagazineSize", "magazine", 1.0, 1.0, int),
    ("ads_zoom", "AdsZoom", "sights zoom", 0.1, 1.0, float),
    ("shot_volume", "ShotVolume", "heard at (cm)", 250.0, 0.0, float),
    ("spread", "SpreadDegrees", "spread (deg)", 0.1, 0.0, float),
    ("spread_shoulder", "SpreadShoulderScale", "spread x shoulder", 0.05, 0.0, float),
    ("spread_crouch", "SpreadCrouchScale", "spread x crouch", 0.05, 0.0, float),
    ("spread_prone", "SpreadProneScale", "spread x prone", 0.05, 0.0, float),
    ("pellet_spread", "PelletSpreadDegrees", "pellet pattern (deg)", 0.25, 0.0, float),
    ("recoil", "RecoilPitch", "recoil up (deg)", 0.05, 0.0, float),
    ("recoil_yaw", "RecoilYaw", "recoil side (deg)", 0.01, 0.0, float),
    ("recoil_shoulder", "RecoilShoulderScale", "recoil x shoulder", 0.05, 0.0, float),
    ("recoil_sights", "RecoilSightsScale", "recoil x sights", 0.05, 0.0, float),
    ("recoil_crouch", "RecoilCrouchScale", "recoil x crouch", 0.05, 0.0, float),
    ("recoil_prone", "RecoilProneScale", "recoil x prone", 0.05, 0.0, float),
    # How fast the sights wander down them: the sway's clock rate (sway_tuning.py).
    (SWAY_RATE_COLUMN, SWAY_RATE_VAR, "sway rate", 0.05, 0.0, float),
    # How far a throw of this gun is tipped up from the view (throw_tuning.py).
    (THROW_PITCH_COLUMN, "ThrowArcDegrees", "throw arc (deg)", 1.0, 0.0, float),
    # What a throw of it takes off a body it strikes (a melee weapon's alone:
    # a gun's stays 0, which is what keeps a thrown gun from wounding).
    (THROW_DAMAGE_COLUMN, "ThrowDamage", "throw damage", 1.0, 0.0, float),
)
TUNE_COLUMNS = tuple(s[0] for s in TUNE_STATS)
WEAPON_COLUMN = "weapon"

# The melee weapons' rows, by DisplayName (knife.py, axe.py), and the only
# columns that are theirs: the throw. The slash is COMBAT's (tuning.py).
MELEE_WEAPONS = ("Knife", "Axe")
MELEE_COLUMNS = (THROW_PITCH_COLUMN, THROW_DAMAGE_COLUMN)
GUN_COLUMNS = tuple(c for c in TUNE_COLUMNS if c != THROW_DAMAGE_COLUMN)


def columns_of(weapon):
    """The columns that are this weapon's own."""
    return MELEE_COLUMNS if weapon in MELEE_WEAPONS else GUN_COLUMNS


def _cell(text, kind):
    return kind(round(float(text))) if kind is int else float(text)


def read_table(path=CSV_PATH):
    """{gun: {column: value}} for every non-empty cell; {} with no file."""
    if not os.path.exists(path):
        return {}
    kinds = {s[0]: s[5] for s in TUNE_STATS}
    table = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            gun = (row.pop(WEAPON_COLUMN, "") or "").strip()
            if gun:
                table[gun] = {c: _cell(v, kinds[c]) for c, v in row.items()
                              if c in kinds and (v or "").strip()}
    return table


def format_value(value, kind):
    """How a number is written: ints bare, floats without float noise
    (0.1 stepped three times reads 0.3, not 0.30000000000000004)."""
    if kind is int:
        return str(int(round(value)))
    return f"{round(float(value), 6):g}"


def write_table(rows, path=CSV_PATH):
    """rows: [(weapon, {column: value})], in the order the CSV lists them.
    A column the weapon's values lack (not its own: columns_of) is left empty."""
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((WEAPON_COLUMN,) + TUNE_COLUMNS)
        for gun, values in rows:
            out.writerow([gun] + [format_value(values[c], kind) if c in values else ""
                                  for c, _v, _l, _s, _m, kind in TUNE_STATS])
