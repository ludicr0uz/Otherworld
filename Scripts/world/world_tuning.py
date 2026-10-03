"""The world tuning table: world_tuning.csv beside this module, one row per
setting (``setting,value``).

The CSV is the tracked copy of the numbers the in-game WORLD SETTINGS tab (the
M panel's world tuning tab, graphics_menu/world_tune_*.py) saves: the day's and the
night's lengths, how fast the night cools the player, and whether an item
lying on the ground glimmers (1 on, 0 off). world_config lays it over its literals, and
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
# An on/off row: the tab's cells are numbers, so it steps between 0 and 1
# (its maximum is what stops Right at "on").
ITEM_HIGHLIGHT_ROW = ("item_highlight", "ItemHighlight",
                      "item highlight (1 on, 0 off)", 1.0, 0.0)
WORLD_STATS = (
    TIME_OF_DAY_ROW,
    ("day_length_s", "DayLengthSeconds", "day length (s)", 30.0, 30.0),
    ("night_length_s", "NightLengthSeconds", "night length (s)", 30.0, 30.0),
    ("night_temperature_drop_per_s", "NightTemperatureDropPerSecond",
     "night cold (temp/s)", 0.01, 0.0),
    ITEM_HIGHLIGHT_ROW,
)
# Each row's maximum. Only the on/off row has a real one.
NO_MAX = 1.0e9
WORLD_MAXS = tuple(1.0 if s is ITEM_HIGHLIGHT_ROW else NO_MAX for s in WORLD_STATS)
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
