"""The world tuning table: world_tuning.csv beside this module, one row per
setting (``setting,value``).

The CSV is the tracked copy of the numbers the in-game WORLD TUNING tab (the
M panel's [O] tab, graphics_menu/world_tune_*.py) saves: the day's and the
night's lengths. world_config lays it over its literals, and
build_day_night.py bakes the result into BP_DayNightCycle's defaults, so a
length tuned in a game and saved lands in the Blueprint on the next build
and git shows what moved.

The tab's first row, the time of day, is live only: a level starts at a
random hour (world_config.RANDOM_START), so there is nothing to save.

Pure Python (no unreal import): world_config and the game's save import it.
"""

import csv
import os

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "world_tuning.csv")
SETTING_COLUMN, VALUE_COLUMN = "setting", "value"

# The tab's rows, in order: (CSV setting or None, BP_DayNightCycle's variable
# or None, the tab's label, step, minimum). The hour's minimum is below zero
# so Left keeps turning the clock back past midnight (the graph wraps it).
TIME_OF_DAY_ROW = ("", "", "time of day (h)", 0.5, -12.0)
WORLD_STATS = (
    TIME_OF_DAY_ROW,
    ("day_length_s", "DayLengthSeconds", "day length (s)", 30.0, 30.0),
    ("night_length_s", "NightLengthSeconds", "night length (s)", 30.0, 30.0),
)
SAVED_STATS = tuple(s for s in WORLD_STATS if s[0])
SAVED_COLUMNS = tuple(s[0] for s in SAVED_STATS)


def read_table(path=CSV_PATH):
    """{setting: value} for every known, non-empty setting; {} with no file."""
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as f:
        return {row[SETTING_COLUMN].strip(): float(row[VALUE_COLUMN])
                for row in csv.DictReader(f)
                if (row.get(SETTING_COLUMN) or "").strip() in SAVED_COLUMNS
                and (row.get(VALUE_COLUMN) or "").strip()}


def format_value(value):
    """No float noise: 30 stepped three times reads 90."""
    return f"{round(float(value), 6):g}"


def write_table(values, path=CSV_PATH):
    """values: {setting: value} for every SAVED_COLUMNS setting."""
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((SETTING_COLUMN, VALUE_COLUMN))
        for col in SAVED_COLUMNS:
            out.writerow((col, format_value(values[col])))
