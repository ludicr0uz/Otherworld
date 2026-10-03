"""The monster tuning table: monster_tuning.csv beside this module, one row per
creature (NPC_VARIANTS' keys).

The CSV is the tracked copy of every number the in-game MONSTER SETTINGS tab
(the M panel's monster tuning tab, graphics_menu/monster_tune_*.py) can change. That tab's
save (graphics_menu/monster_tune_save.py) writes it, and monster_specs() lays
it over the literals in forest_generator/npc_agro.py and npc_placement.py. The
NPC builder bakes monster_specs() into each creature's controller as the
defaults of its Tune* variables (npc/tuned.py), which is what every graph
reads, so a value tuned in a game and saved lands in the Blueprints the next
time build_npc_blueprints.py runs, then build_graphics_menu.py (the HUD's
copy of the table), and git shows what moved.

The "hunt:" rows are how a wendigo stalks (forest_generator/npc_stalk.py) and
the "fire:" rows what a burning stick does to it (npc_ward.py). Every
creature has the columns, since the tab is one table, but only the graphs of
one that hunts (NPC_STALK_ROAR) or fears fire (NPC_WARD_FEARS) read them: on
the zombie they change nothing.

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
from forest_generator.npc_stalk import (
    NPC_STALK_CATCH_UP_CM, NPC_STALK_CHARGE_CM, NPC_STALK_FLED_CM,
    NPC_STALK_HIDE_MAX_S, NPC_STALK_HIDE_MIN_S, NPC_STALK_RUN_SCALE, NPC_STALK_TURN_MAX_S,
    NPC_STALK_TURN_MIN_S,
)
from forest_generator.npc_ward import (
    NPC_WARD_FLEE_S, NPC_WARD_HALF_ANGLE_DEG, NPC_WARD_HOLD_S, NPC_WARD_RANGE_CM,
    NPC_WARD_RING_CM, NPC_WARD_SPEED_SCALE, NPC_WARD_TURN_FLOOR_S,
    NPC_WARD_TURN_MAX_S, NPC_WARD_TURN_MIN_S,
)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monster_tuning.csv")
CREATURE_COLUMN = "creature"

# One per tunable number, in the tab's row order and the CSV's column order:
# (CSV column, the controller's variable, the tab's label, step, minimum).
# Left/Right on the tab move a value one step and never under its minimum.
# Every stat is a float. The melee range's minimum keeps it above the chase's
# acceptance radius, or a wanderer would park out of its own reach. The hunt's
# and the fire's rows (see the module docstring) come last; a turn is never
# under NPC_WARD_TURN_FLOOR_S apart.
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
    ("stalk_charge_cm", "TuneStalkCharge", "hunt: charge from (cm)", 50.0, 300.0),
    ("stalk_catch_up_cm", "TuneStalkCatchUp", "hunt: run straight beyond (cm)",
     500.0, 2000.0),
    ("stalk_fled_cm", "TuneStalkFled", "hunt: charge if they run off (cm)", 100.0, 300.0),
    ("stalk_run_scale", "TuneStalkSpeed", "hunt: speed x run", 0.05, 0.5),
    ("stalk_hide_min_s", "TuneStalkHideMin", "hunt: behind a tree min (s)", 0.25, 0.0),
    ("stalk_hide_max_s", "TuneStalkHideMax", "hunt: behind a tree max (s)", 0.25, 0.0),
    ("stalk_turn_min_s", "TuneStalkTurnMin", "hunt: turns round min (s)", 0.5,
     NPC_WARD_TURN_FLOOR_S),
    ("stalk_turn_max_s", "TuneStalkTurnMax", "hunt: turns round max (s)", 0.5,
     NPC_WARD_TURN_FLOOR_S),
    ("ward_range_cm", "TuneWardRange", "fire: holds it off within (cm)", 50.0, 100.0),
    ("ward_half_angle_deg", "TuneWardHalfAngle", "fire: cone (deg each side)", 5.0, 5.0),
    ("ward_ring_cm", "TuneWardRing", "fire: circles at (cm)", 25.0, 100.0),
    ("ward_speed_scale", "TuneWardSpeed", "fire: circling speed x run", 0.05, 0.05),
    ("ward_turn_min_s", "TuneWardTurnMin", "fire: turns round min (s)", 0.5,
     NPC_WARD_TURN_FLOOR_S),
    ("ward_turn_max_s", "TuneWardTurnMax", "fire: turns round max (s)", 0.5,
     NPC_WARD_TURN_FLOOR_S),
    ("ward_hold_s", "TuneWardHold", "fire: gives up after (s)", 1.0, 1.0),
    ("ward_flee_s", "TuneWardFlee", "fire: runs away for (s)", 1.0, 0.0),
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
        "stalk_charge_cm": NPC_STALK_CHARGE_CM,
        "stalk_catch_up_cm": NPC_STALK_CATCH_UP_CM,
        "stalk_fled_cm": NPC_STALK_FLED_CM,
        "stalk_run_scale": NPC_STALK_RUN_SCALE,
        "stalk_hide_min_s": NPC_STALK_HIDE_MIN_S,
        "stalk_hide_max_s": NPC_STALK_HIDE_MAX_S,
        "stalk_turn_min_s": NPC_STALK_TURN_MIN_S,
        "stalk_turn_max_s": NPC_STALK_TURN_MAX_S,
        "ward_range_cm": NPC_WARD_RANGE_CM,
        "ward_half_angle_deg": NPC_WARD_HALF_ANGLE_DEG,
        "ward_ring_cm": NPC_WARD_RING_CM,
        "ward_speed_scale": NPC_WARD_SPEED_SCALE,
        "ward_turn_min_s": NPC_WARD_TURN_MIN_S,
        "ward_turn_max_s": NPC_WARD_TURN_MAX_S,
        "ward_hold_s": NPC_WARD_HOLD_S,
        "ward_flee_s": NPC_WARD_FLEE_S,
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
