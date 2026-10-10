"""verify.var_tables -- every combat Blueprint's variables against the tables
its builders declare from (uebp/verify_vars.py): each row declared with its
type, its default and its replication, and nothing beside them. One
``check_table`` per Blueprint, four check lines each; the sections that used
to re-state a variable by hand ("the PlayerState carries the kill counter",
"LastDamageTime is a float") no longer do.

TABLES is the join a Blueprint's fragments declare. A Blueprint the engine or
the sample shipped (the two anim blueprints) is checked open: the builders
only add to it. LEFT names the variables an earlier build declared and no
table names any more: ``declare`` re-declares its rows and removes nothing,
so they sit in the saved asset until a builder prunes them.
"""

from asset_pipeline.gas_paths import ABP as GAS_ABP_PATH
from combat import ammo_vars as AV
from combat import anim_vars as AN
from combat import burst_vars as BV
from combat import footstep_vars as FV
from combat import fx_vars as FX
from combat import game_mode_vars as GV
from combat import health_vars as HV
from combat import item_vars as IV
from combat import record_vars as RV
from combat import settings_vars as SV
from combat import shot_vars as SH
from combat import strike_vars as ST
from combat.gas_locomotion_consts import ADDED_VARS
from combat.paths import (
    ABP_PATH, AMMO_BP_PATH, BLOOD_BP_PATH, BULLET_IMPACT_BP_PATH, FOOTSTEP_BP_PATH,
    GAME_MODE_BP_PATH, HEALTH_BP_PATH, ITEM_BP_PATH, SETTINGS_BP_PATH, WEAPON_COMP_BP_PATH)
from combat.verify.common import check, load
from combat.weapon_component import look_vars as LV
from combat.weapon_component import vars as WV
from loot import consts as LOOT
from net import state_consts as NS
from uebp.verify_vars import check_table

# (Blueprint, its rows, the variables left beside them by an earlier build)
TABLES = (
    (WEAPON_COMP_BP_PATH, WV.CORE + FX.TABLE + LV.TABLE + RV.TABLE + SH.TABLE + ST.TABLE
     + WV.STATE, ("PoseSprinting",)),
    (ITEM_BP_PATH, IV.TABLE, ("LodgePitchDeg",)),
    (HEALTH_BP_PATH, HV.TABLE + HV.STATE + LOOT.TABLE, ()),
    (GAME_MODE_BP_PATH, GV.TABLE, ()),
    (FOOTSTEP_BP_PATH, FV.TABLE, ()),
    (AMMO_BP_PATH, AV.TABLE, ()),
    (BLOOD_BP_PATH, BV.TABLE, ("Jitter", "Origin")),
    (BULLET_IMPACT_BP_PATH, BV.TABLE, ()),
    (SETTINGS_BP_PATH, SV.TABLE, ()),
    (NS.PLAYER_STATE_BP_PATH, NS.PLAYER_TABLE, ()),
    (NS.GAME_STATE_BP_PATH, NS.GAME_TABLE, ()),
)
# Added to, not made: the stock anim blueprint and the sample's.
PATCHED = (
    (ABP_PATH, AN.AIM + AN.GROUND + AN.POSE + AN.SERVER + AN.SUPPORT),
    (GAS_ABP_PATH, AN.SERVER + ADDED_VARS),
)


def check_var_tables():
    for path, table, left in TABLES:
        check_table(load(path), table, check, others=left)
    for path, table in PATCHED:
        check_table(load(path), table, check, closed=False)


def run():
    check_var_tables()
