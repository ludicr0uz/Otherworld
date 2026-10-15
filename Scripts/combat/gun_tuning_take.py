"""Taking a packaged build's GUN SETTINGS save back into the project.

A packaged build has no Python, so the tab's Enter writes gun_tuning.csv into
the build's own Saved/Tuning/ (OtherworldTuningLibrary.SaveTuningCsv, C++) in
gun_tuning.write_table's format. This finds that file, refuses one whose
header is not this project's columns, says which cells moved, and copies it
over the tracked gun_tuning.csv, which the next build_weapons_and_combat.py
then build_graphics_menu.py bake in as the new defaults. Pure Python (no
unreal import); the entry point is Scripts/take_gun_tuning.py.
"""

import os
import shutil

from combat.gun_tuning import CSV_PATH, TUNE_COLUMNS, WEAPON_COLUMN, read_table

FILE = os.path.basename(CSV_PATH)
HEADER = ",".join((WEAPON_COLUMN,) + TUNE_COLUMNS)


def saved_copies(home=None, local_app_data=None):
    """Where a packaged build's save lands, by platform: the Mac app's
    sandbox container, the Mac without the sandbox, Windows."""
    home = home or os.path.expanduser("~")
    local_app_data = local_app_data or os.environ.get("LOCALAPPDATA", "")
    mac = os.path.join("Library", "Application Support", "Epic", "Otherworld", "Saved")
    places = [
        os.path.join(home, "Library", "Containers", "com.YourCompany.Otherworld", "Data", mac),
        os.path.join(home, mac),
    ]
    if local_app_data:
        places.append(os.path.join(local_app_data, "Otherworld", "Saved"))
    return [os.path.join(p, "Tuning", FILE) for p in places]


def newest(paths):
    """The most recently written of the paths that exist, or None."""
    found = [p for p in paths if os.path.isfile(p)]
    return max(found, key=os.path.getmtime) if found else None


def header_problem(path):
    """Why the file cannot stand in for gun_tuning.csv, or "" when it can."""
    with open(path, newline="") as f:
        first = f.readline().rstrip("\r\n")
    if first != HEADER:
        return (f"{path}'s header is not this project's columns (a build of an "
                f"older table?):\n  file:    {first}\n  project: {HEADER}")
    return ""


def changes(old_path, new_path):
    """[(weapon, column, old, new)] for every cell that differs, in the new
    file's order; a cell one file lacks reads None."""
    old, new = read_table(old_path), read_table(new_path)
    moved = []
    for weapon in list(new) + [w for w in old if w not in new]:
        a, b = old.get(weapon, {}), new.get(weapon, {})
        for col in TUNE_COLUMNS:
            if a.get(col) != b.get(col):
                moved.append((weapon, col, a.get(col), b.get(col)))
    return moved


def take(source, target=CSV_PATH):
    """Copy ``source`` over ``target`` once its header checks. Returns the
    cells that moved; raises ValueError on a header that does not."""
    problem = header_problem(source)
    if problem:
        raise ValueError(problem)
    moved = changes(target, source) if os.path.exists(target) else []
    shutil.copyfile(source, target)
    return moved
