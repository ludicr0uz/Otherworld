"""BP_GameTuner's names: the component of the GameState that applies the
gameplay tables where the game is run (game_tuner.py; task M32).

Its variables are the gameplay tabs' own, under the HUD's names, so the
tabs' apply fragments author the same nodes in either graph: each tab's
table and its Touched flag, the guns' names, the world tab's Open flag
(never raised here: its apply runs while open or touched) and the hour it
last saw.

Constants only.
"""

from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.player_tune_consts import PLAYER_TAB
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.tune_tab import tab_table
from graphics_menu.world_tune_consts import WORLD_TAB, WORLD_TUNE_TABLE

GAME_TUNER_BP_PATH = "/Game/UI/BP_GameTuner"
GAME_TUNER_CLASS_PATH = f"{GAME_TUNER_BP_PATH}.BP_GameTuner_C"
GAME_TUNER_COMPONENT = "GameTuner"

# In combat/ask_consts.TUNE_TABLES' order, which is the GameState's inboxes'.
GAMEPLAY_TABS = (GUN_TAB, MONSTER_TAB, WORLD_TAB, PLAYER_TAB)


def _rows(tab, *names):
    wanted = {tab.touched_var, tab.values_var, *names}
    return tuple(var for var in tab_table(tab) if var in wanted)


GAME_TUNER_TABLE = (*_rows(GUN_TAB, GUN_TAB.names_var), *_rows(MONSTER_TAB),
                    *_rows(WORLD_TAB, WORLD_TAB.open_var), *WORLD_TUNE_TABLE,
                    *_rows(PLAYER_TAB))
