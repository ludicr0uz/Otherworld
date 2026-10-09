"""verify.var_tables -- BP_DayNightCycle's variables against the table its
builder declares from (uebp/verify_vars.py): each row declared with its type
and world_config's default, none replicated, and nothing beside them.
"""

from combat.verify.common import check, load
from world import day_night_vars as DV
from world.paths import DAY_NIGHT_BP_PATH
from uebp.verify_vars import check_table


def run():
    check_table(load(DAY_NIGHT_BP_PATH), DV.TABLE, check)
