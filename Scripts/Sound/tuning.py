"""The sound tuning table: sound_tuning.csv beside this module, one row per
sound (``sound,volume``).

The CSV is the tracked copy of the numbers the in-game SOUND SETTINGS tab (the
menu's sound tuning row, graphics_menu/sound_tune_*.py) saves: how loud each
sound of the game is, as a multiplier (1 = as recorded, 0 = silent, at most
VOLUME_MAX).

A "sound" is what the player hears as one thing: the footsteps are six
takes and one row. The rows are the areas' (catalog.SOUND_STATS: CSV sound,
the tab's label, its SoundWaves, the volume with no CSV), and which takes is
the selection's business (Scripts/Sound/sound_candidates/selection.py). Each
has a SoundClass of its own (mix.py gives it to the sound's waves), and the HUD sets that class's volume in the game's
sound mix (graphics_menu/sound_tune_tick.py), so no call site carries a
volume and a sound played from anywhere takes its row.
"""

import csv
import os

from Sound.catalog import SOUND_STATS

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sound_tuning.csv")
SOUND_COLUMN, VOLUME_COLUMN = "sound", "volume"

# 4 is the engine's own ceiling: a source's final volume is clamped to its
# MAX_VOLUME (AudioDefines.h), so a row past it would change nothing.
VOLUME_STEP, VOLUME_MIN, VOLUME_MAX = 0.05, 0.0, 4.0
FOOTSTEPS = "footsteps"
SAVED_COLUMNS = tuple(s[0] for s in SOUND_STATS)


def class_name(sound):
    """The sound's SoundClass asset: footsteps -> A_Class_Footsteps."""
    return "A_Class_" + "".join(w.capitalize() for w in sound.split("_"))


def read_table(path=CSV_PATH):
    """{sound: volume} for every known, non-empty row; {} with no file."""
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as f:
        return {row[SOUND_COLUMN].strip(): float(row[VOLUME_COLUMN])
                for row in csv.DictReader(f)
                if (row.get(SOUND_COLUMN) or "").strip() in SAVED_COLUMNS
                and (row.get(VOLUME_COLUMN) or "").strip()}


def table(path=CSV_PATH):
    """Every sound: the CSV's volume, else the default."""
    saved = read_table(path)
    return {s[0]: float(saved.get(s[0], s[3])) for s in SOUND_STATS}


def format_value(value):
    """No float noise: 0.05 stepped twenty times reads 1."""
    return f"{round(float(value), 6):g}"


def write_table(values, path=CSV_PATH):
    """values: {sound: volume} for every SAVED_COLUMNS sound."""
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((SOUND_COLUMN, VOLUME_COLUMN))
        for col in SAVED_COLUMNS:
            out.writerow((col, format_value(values[col])))
