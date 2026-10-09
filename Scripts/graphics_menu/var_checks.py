"""The verifier's check of the menu's Blueprints against their variable tables
(uebp/verify_vars.py): each row declared with its type, default and
replication, and nothing beside them. One ``check_table`` per Blueprint.

The HUD's table is the join of every fragment's (hud_vars.py's groups, each
fragment's constants module, one ``tab_table`` per tuning tab). A tab's
arrays have no default in a row: they start at the built tables, which each
tab's own section checks.
"""

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import dev_consts as DC
from graphics_menu import gfx_tune_consts as GC
from graphics_menu import hud_vars as MV
from graphics_menu import inv_consts as IC
from graphics_menu import loot_consts as LC
from graphics_menu import mode_consts as MC
from graphics_menu import profile_consts as PC
from graphics_menu import sound_tune_consts as SC
from graphics_menu import tune_keep_consts as KC
from graphics_menu import umg_consts as UC
from graphics_menu import wear_consts as WC
from graphics_menu import world_tune_consts as WT
from graphics_menu.tune_tab import tab_table
from graphics_menu.tune_tabs import TABS
from net import session_consts as S
from uebp.verify_vars import check_table

# An earlier build's, which no table names: declare() removes nothing.
HUD_LEFT = ("GrassQualityApplied",)


def hud_table():
    table = (MV.TABLE + MV.PANEL + MV.DIFFICULTY + MV.FPS + CC.TABLE + DC.TABLE
             + GC.GFX_TUNE_TABLE + IC.CARRY_TABLE + IC.DRAG_TABLE + LC.TABLE + MC.TABLE
             + PC.HUD_TABLE + SC.SOUND_TUNE_TABLE + UC.SCREEN_TABLE + WC.TABLE
             + WT.WORLD_TUNE_TABLE)
    for tab in TABS:
        table += tab_table(tab)
    return table


def check_var_tables(check):
    check_table(unreal.load_asset(UC.HUD_BP_PATH), hud_table(), check, others=HUD_LEFT)
    for path, table in ((GC.TUNER_BP_PATH, GC.TUNER_TABLE),
                        (GC.GFX_SAVE_BP_PATH, GC.GFX_SAVE_FIELDS),
                        (KC.TUNE_SAVE_BP_PATH, KC.TUNE_SAVE_FIELDS),
                        (PC.PROFILE_BP_PATH, PC.PROFILE_TABLE),
                        (UC.WBP_MENU_ROW, UC.ROW_TABLE),
                        (UC.WBP_INVENTORY_SLOT, UC.SLOT_TABLE),
                        (S.GAME_INSTANCE_BP_PATH, S.TABLE)):
        check_table(unreal.load_asset(path), table, check)
