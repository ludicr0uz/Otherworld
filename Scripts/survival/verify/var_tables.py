"""verify.var_tables -- the survival Blueprints' variables against the tables
their builders declare from (uebp/verify_vars.py): each row declared with its
type, default and replication, and nothing beside them.
"""

from combat.verify.common import check, load
from survival import campfire_vars as FIRE
from survival import component_vars as UV
from survival import consumable_vars as CV
from survival.paths import CAMPFIRE_BP_PATH, CONSUMABLE_BP_PATH, SURVIVAL_BP_PATH
from uebp.verify_vars import check_table

TABLES = (
    (SURVIVAL_BP_PATH, UV.STATS + UV.TABLE + UV.LINKS),
    (CONSUMABLE_BP_PATH, CV.TABLE),
    (CAMPFIRE_BP_PATH, FIRE.TABLE),
)


def run():
    for path, table in TABLES:
        check_table(load(path), table, check)
