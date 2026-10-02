"""The M panel's tuning tabs, in the order of their rows in the panel. One
list for what treats them alike: wbp_tune lays each out, and the panel's
DrawHUD fragment hides its own rows while any of them is open.

Constants only. Each tab's names are its own module's (tune_tab.TuneTab).
"""

from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.player_tune_consts import PLAYER_TAB
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.world_tune_consts import WORLD_TAB

TABS = (GUN_TAB, MONSTER_TAB, WORLD_TAB, PLAYER_TAB, GFX_TAB)


def other_open_vars(tab):
    """The open flags opening ``tab`` lowers: every other tab's."""
    return tuple(t.open_var for t in TABS if t is not tab)
