"""BP_TuneSave: what a tuning tab keeps between sessions (tune_keep.py). Its
path, its two fields, and the slots.

One class for every kept tab, one slot a tab (tune_tab.TuneTab.keep_slot), so
a tab's save is read and written without the others'.

Constants only.
"""

from uebp.vars import FLOAT, Var, array
from graphics_menu.gfx_tune_consts import GFX_SAVE_SLOT
from graphics_menu.tune_tabs import TABS

TUNE_SAVE_BP_PATH = "/Game/UI/BP_TuneSave"
TUNE_SAVE_CLASS_PATH = f"{TUNE_SAVE_BP_PATH}.BP_TuneSave_C"
TUNE_SAVE_USER_INDEX = 0
# The tab's table as it stood, and the built table it was nudged away from. A
# save is read back only while that is still this build's: a CSV that changed
# since (or another table size) is newer than the save, and wins.
# Not BP_GraphicsSave's names: the verifier finds a field's nodes by title.
TUNE_SAVE_TABLE_FIELD = Var("KeptTable", array(FLOAT))
TUNE_SAVE_BUILT_FIELD = Var("KeptBuilt", array(FLOAT))
TUNE_SAVE_FIELDS = (TUNE_SAVE_TABLE_FIELD, TUNE_SAVE_BUILT_FIELD)   # tune_keep.py declares them

KEPT_TABS = tuple(t for t in TABS if t.kept)
TUNE_SAVE_SLOTS = tuple(t.keep_slot for t in KEPT_TABS)
# Every slot the tabs keep something in, the graphics tab's own included.
KEPT_SLOTS = (GFX_SAVE_SLOT,) + TUNE_SAVE_SLOTS
