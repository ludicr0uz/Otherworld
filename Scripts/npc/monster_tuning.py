"""The monster tuning table: monster_tuning.csv beside this module, one row per
creature (NPC_VARIANTS' keys).

The CSV is the tracked copy of every number the in-game MONSTER TUNING tab
(the M panel's [N] tab, graphics_menu/monster_tune_*.py) can change. That tab's
save (graphics_menu/monster_tune_save.py) writes it, and monster_specs() lays
it over the literals in forest_generator/npc_agro.py and npc_placement.py. The
NPC builder bakes monster_specs() into each creature's controller as the
defaults of its Tune* variables (npc/tuned.py), which is what every graph
reads, so a value tuned in a game and saved lands in the Blueprints the next
time build_npc_blueprints.py runs, then build_graphics_menu.py (the HUD's
copy of the table), and git shows what moved.

A column or row the CSV lacks falls back to the literal. Pure Python (no
unreal import): the game's save imports it too.
"""

import csv
import os

from forest_generator.npc_agro import agro_for
from forest_generator.npc_placement import (
    NPC_ACCEPTANCE_RADIUS_CM, NPC_MELEE_DAMAGE, NPC_MELEE_INTERVAL_S,
    NPC_MELEE_RANGE_CM, NPC_RUN_SPEED_CMS, NPC_VARIANTS,
)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monster_tuning.csv")
CREATURE_COLUMN = "creature"

# One per tunable number, in the tab's row order and the CSV's column order:
# (CSV column, the controller's variable, the tab's label, step, minimum).
# Left/Right on the tab move a value one step and never under its minimum.
# Every stat is a float. The melee range's minimum keeps it above the chase's
# acceptance radius, or a wanderer would park out of its own reach.
MONSTER_STATS = (
    ("vision_range_cm", "TuneSightRange", "aggro range (cm)", 100.0, 0.0),
    ("vision_half_angle_deg", "TuneSightHalfAngle", "aggro cone (deg each side)", 5.0, 0.0),
    ("hearing_scale", "TuneHearing", "hearing x", 0.1, 0.0),
    ("touch_range_cm", "TuneTouchRange", "touch range (cm)", 25.0, 0.0),
    ("patrol_radius_cm", "TunePatrolRadius", "patrol radius (cm)", 250.0, 100.0),
    ("patrol_speed_scale", "TunePatrolSpeed", "patrol speed x run", 0.05, 0.05),
    ("patrol_repick_min_s", "TunePatrolRepickMin", "new patrol point min (s)", 0.5, 0.5),
    ("patrol_repick_max_s", "TunePatrolRepickMax", "new patrol point max (s)", 0.5, 0.5),
    ("run_speed_cms", "TuneRunSpeed", "run speed (cm/s)", 25.0, 50.0),
    ("melee_damage", "TuneMeleeDamage", "damage per hit", 1.0, 0.0),
    ("melee_range_cm", "TuneMeleeRange", "melee range (cm)", 10.0,
     NPC_ACCEPTANCE_RADIUS_CM + 10.0),
    ("melee_interval_s", "TuneMeleeInterval", "between swings (s)", 0.1, 0.1),
    ("health", "TuneHealth", "health", 10.0, 10.0),
)
MONSTER_COLUMNS = tuple(s[0] for s in MONSTER_STATS)
TUNED_VAR = {s[0]: s[1] for s in MONSTER_STATS}


def _variant(key):
    for v in NPC_VARIANTS:
        if v.key == key:
            return v
    raise KeyError(f"no creature {key!r} in NPC_VARIANTS")


def stock_run_speed(key):
    """The creature's run speed as its pawn Blueprint is built (the pawn's
    MaxWalkSpeed before the level's per-instance gait). TuneRunSpeed is
    applied as TuneRunSpeed / this, times what the pawn actually has."""
    return NPC_RUN_SPEED_CMS * _variant(key).speed_scale


def stock_specs(key):
    """{column: value} from the literals alone, before the CSV."""
    a = agro_for(key)
    return {
        "vision_range_cm": a.vision_range_cm,
        "vision_half_angle_deg": a.vision_half_angle_deg,
        "hearing_scale": a.hearing_scale,
        "touch_range_cm": a.touch_range_cm,
        "patrol_radius_cm": a.patrol_radius_cm,
        "patrol_speed_scale": a.patrol_speed_scale,
        "patrol_repick_min_s": a.patrol_repick_min_s,
        "patrol_repick_max_s": a.patrol_repick_max_s,
        "run_speed_cms": stock_run_speed(key),
        "melee_damage": NPC_MELEE_DAMAGE,
        "melee_range_cm": NPC_MELEE_RANGE_CM,
        "melee_interval_s": NPC_MELEE_INTERVAL_S,
        "health": _variant(key).health,
    }


def read_table(path=CSV_PATH):
    """{creature: {column: value}} for every non-empty cell; {} with no file."""
    if not os.path.exists(path):
        return {}
    table = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (row.pop(CREATURE_COLUMN, "") or "").strip()
            if key:
                table[key] = {c: float(v) for c, v in row.items()
                              if c in TUNED_VAR and (v or "").strip()}
    return table


def monster_specs(key, path=CSV_PATH):
    """{column: value} for creature ``key``: the CSV's row over the literals.
    What the builder bakes, and what the HUD's table starts from."""
    return {**stock_specs(key), **read_table(path).get(key, {})}


def format_value(value):
    """No float noise: 0.1 stepped three times reads 0.3."""
    return f"{round(float(value), 6):g}"


def write_table(rows, path=CSV_PATH):
    """rows: [(creature, {column: value})], in the order the CSV lists them."""
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((CREATURE_COLUMN,) + MONSTER_COLUMNS)
        for key, values in rows:
            out.writerow([key] + [format_value(values[c]) for c in MONSTER_COLUMNS])
