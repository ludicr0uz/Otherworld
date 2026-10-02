"""The player tuning table: player_tuning.csv beside this module, one row per
setting (``setting,value``).

The CSV is the tracked copy of the numbers the in-game PLAYER TUNING tab (the
menu's player tuning row, graphics_menu/player_tune_*.py) saves: how fast the
player jogs and sprints, how long a full stamina bar sprints for and how long
an empty one takes to refill. tuning.py lays it over its literals, and
build_weapons_and_combat.py bakes the result into the character's walk speed
and BP_WeaponComponent's defaults, so a number tuned in a game and saved
lands in the Blueprints on the next build and git shows what moved.

The table is in a person's units (metres a second, seconds). The component
holds cm/s and stamina points a second: cms() and per_second() convert, and
the tab's graph does the same sums (player_tune_tick.py).

Pure Python (no unreal import): tuning.py and the game's save import it.
"""

import csv
import os

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "player_tuning.csv")
SETTING_COLUMN, VALUE_COLUMN = "setting", "value"

JOG_SPEED, SPRINT_SPEED = "jog_speed_mps", "sprint_speed_mps"
SPRINT_DURATION, STAMINA_RECHARGE = "sprint_duration_s", "stamina_recharge_s"

# The tab's rows, in order: (CSV setting, the tab's label, step, minimum,
# the value with no CSV). 8.33 s is the refill the bar has always had (100
# points at 12 a second); the sprint from full was 4 s before it was doubled.
PLAYER_STATS = (
    (JOG_SPEED, "jog speed (m/s)", 0.25, 0.5, 4.0),
    (SPRINT_SPEED, "sprint speed (m/s)", 0.25, 0.5, 6.0),
    (SPRINT_DURATION, "sprint from full (s)", 0.5, 0.5, 8.0),
    (STAMINA_RECHARGE, "recharge to full (s)", 0.5, 0.5, 8.33),
)
SAVED_COLUMNS = tuple(s[0] for s in PLAYER_STATS)
CM_PER_M = 100.0


def read_table(path=CSV_PATH):
    """{setting: value} for every known, non-empty setting; {} with no file."""
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as f:
        return {row[SETTING_COLUMN].strip(): float(row[VALUE_COLUMN])
                for row in csv.DictReader(f)
                if (row.get(SETTING_COLUMN) or "").strip() in SAVED_COLUMNS
                and (row.get(VALUE_COLUMN) or "").strip()}


def table(path=CSV_PATH):
    """Every setting: the CSV's value, else the default."""
    saved = read_table(path)
    return {s[0]: float(saved.get(s[0], s[4])) for s in PLAYER_STATS}


def cms(metres_per_second):
    return float(metres_per_second) * CM_PER_M


def per_second(max_stamina, seconds):
    """The stamina rate that crosses the whole bar in ``seconds``."""
    return float(max_stamina) / float(seconds)


def format_value(value):
    """No float noise: 0.25 stepped four times reads 1."""
    return f"{round(float(value), 6):g}"


def write_table(values, path=CSV_PATH):
    """values: {setting: value} for every SAVED_COLUMNS setting."""
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((SETTING_COLUMN, VALUE_COLUMN))
        for col in SAVED_COLUMNS:
            out.writerow((col, format_value(values[col])))
