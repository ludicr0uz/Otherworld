"""The grip nudges: Content/Tuning/grip_nudges.csv, one row per held item.

A row is six numbers laid over the place the item's Grip component gives it
in the hand (grip_handle.py): x, y, z in centimetres and pitch, yaw, roll in
degrees, in the grip socket's frame. The item turns about the socket (the
hand) by the rotation and then moves by the position:

    seat under the socket = inverse(Grip) * nudge

A row of zeros, or no row, changes nothing. The rows are keyed by the item's
Blueprint name (BP_Knife), which is what the game can read off a live item on
any machine.

WHO READS IT
------------
The running game, not the build: UOtherworldGripLibrary (C++,
Source/Otherworld/Public/OtherworldGripLibrary.h) reads the file the first
time an item is seated, on the server, a client and the title alike, so a
number edited here is a relaunch and no build, and a rebuild or a new ready
pose keeps it. The file lives under Content/ because that is what a packaged
build can carry loose (DefaultGame.ini, DirectoriesToAlwaysStageAsNonUFS).

WHO WRITES IT
-------------
A person, in a text editor; and the GUN SETTINGS tab's grip rows
(graphics_menu/grip_tune.py), through the same C++ library, on the frame a
value changes. This module is the format in Python, for the tests, the probe
and whoever reads the table from a script. Pure Python (no unreal import).
"""

import csv
import os

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Content", "Tuning", "grip_nudges.csv")

ITEM_COLUMN = "item"
# One per number of a row, in the CSV's column order and the tab's row order:
# (column, the tab's label, step). The C++ reads them by position.
GRIP_STATS = (
    ("x", "grip x (cm)", 0.1),
    ("y", "grip y (cm)", 0.1),
    ("z", "grip z (cm)", 0.1),
    ("pitch", "grip pitch (deg)", 1.0),
    ("yaw", "grip yaw (deg)", 1.0),
    ("roll", "grip roll (deg)", 1.0),
)
GRIP_COLUMNS = tuple(s[0] for s in GRIP_STATS)
# A nudge is signed, and a tab's cell never goes under its minimum.
GRIP_MIN = -1000.0
ZERO = dict.fromkeys(GRIP_COLUMNS, 0.0)


def row_of(blueprint_path):
    """An item's row name: its Blueprint's name (/Game/Weapons/BP_Knife ->
    BP_Knife), as UOtherworldGripLibrary::GripRowOf names a live one."""
    return blueprint_path.rsplit("/", 1)[-1].split(".")[0]


def read_table(path=CSV_PATH):
    """{item: {column: value}}, every column of every row (an empty or
    missing cell is 0); {} with no file. A row named twice is its last."""
    if not os.path.exists(path):
        return {}
    table = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            item = (row.get(ITEM_COLUMN) or "").strip()
            if item:
                table[item] = {c: float((row.get(c) or "").strip() or 0.0)
                               for c in GRIP_COLUMNS}
    return table


def format_value(value):
    """How a number is written, as the C++ writes it: at most six decimals,
    no float noise (0.1 stepped three times reads 0.3), no minus zero."""
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def write_table(rows, path=CSV_PATH):
    """rows: [(item, {column: value})], in the order the CSV lists them. A
    column a row's values lack is written 0."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((ITEM_COLUMN,) + GRIP_COLUMNS)
        for item, values in rows:
            out.writerow([item] + [format_value(values.get(c, 0.0)) for c in GRIP_COLUMNS])


def is_zero(values):
    return all(float(values.get(c, 0.0)) == 0.0 for c in GRIP_COLUMNS)
