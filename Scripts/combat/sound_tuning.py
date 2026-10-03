"""The sound tuning table: sound_tuning.csv beside this module, one row per
sound (``sound,volume``).

The CSV is the tracked copy of the numbers the in-game SOUND SETTINGS tab (the
menu's sound tuning row, graphics_menu/sound_tune_*.py) saves: how loud each
sound of the game is, as a multiplier (1 = as recorded, 0 = silent).

A "sound" is what the player hears as one thing: the footsteps are four
takes and one row. Each has a SoundClass of its own (sound_mix.py gives it
to the sound's waves), and the HUD sets that class's volume in the game's
sound mix (graphics_menu/sound_tune_tick.py), so no call site carries a
volume and a sound played from anywhere takes its row.

Pure Python (no unreal import): the game's save imports it.
"""

import csv
import os

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sound_tuning.csv")
SOUND_COLUMN, VOLUME_COLUMN = "sound", "volume"

VOLUME_STEP, VOLUME_MIN, VOLUME_MAX = 0.05, 0.0, 2.0
FOOTSTEPS = "footsteps"
# The footsteps were as loud as recorded and drowned the forest: under half.
FOOTSTEPS_VOLUME = 0.4


def _takes(stem, count):
    return tuple(f"{stem}_{i:02d}" for i in range(1, count + 1))


# The tab's rows, in order: (CSV sound, the tab's label, its SoundWaves, the
# volume with no CSV). Every wave of combat/audio.py is in exactly one row
# (sound_mix.build_sound_mix raises on one that is not).
SOUND_STATS = (
    (FOOTSTEPS, "footsteps", _takes("A_Footstep", 4), FOOTSTEPS_VOLUME),
    ("shotgun_shot", "shotgun shot", ("A_ShotgunFire",), 1.0),
    ("pistol_shot", "pistol shot", ("A_PistolFire",), 1.0),
    ("smg_shot", "SMG shot", ("A_SMGFire",), 1.0),
    ("rifle_shot", "rifle shot", ("A_RifleFire",), 1.0),
    ("sniper_shot", "sniper shot", ("A_SniperFire",), 1.0),
    ("dry_fire", "dry fire", ("A_DryFire",), 1.0),
    ("shotgun_reload", "shotgun reload", ("A_ReloadShotgun",), 1.0),
    ("rifle_reload", "rifle reload", ("A_ReloadRifle",), 1.0),
    ("pistol_reload", "pistol reload", ("A_ReloadPistol",), 1.0),
    ("melee_hit", "melee hit", _takes("A_MeleeHit", 3), 1.0),
    ("zombie_growl", "zombie growl", _takes("A_ZombieGrowl", 3), 1.0),
    ("wendigo_roar", "wendigo roar", _takes("A_WendigoRoar", 3), 1.0),
)
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
