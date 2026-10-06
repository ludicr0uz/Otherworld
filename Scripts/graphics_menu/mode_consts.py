"""The title's two mode pages, Single Player and Multiplayer: their numbers,
rows, widgets, words and the HUD's variables for them. Constants only:
wbp_modes.py lays them out, mode_draw.py shows them, mode_tick.py serves
their rows, and net/session_consts.py names the session they start.

A page is one of MenuPage's values, like the settings page: it stands in the
menu's rows' place, MenuRow is its caret, and its BACK row, drawn on top, is
its last number (settings_rows.py says why). A row taken (Enter on it, or a
click) raises PageClick for Tick, as PauseClick is raised for the menu's own.
"""

from collections import namedtuple

from uebp.vars import STRING, Var, array, struct
from graphics_menu.settings_rows import PAGE_SETTINGS
from graphics_menu.umg_consts import MODE_MULTI_TEXT, MODE_SINGLE_TEXT, START_ROW_LABEL

PAGE_SINGLE = PAGE_SETTINGS + 1
PAGE_MULTI = PAGE_SINGLE + 1


class Page(namedtuple("Page", "page panel title back rows_box labels")):
    """One page: MenuPage's value, its widgets in WBP_PauseMenu, its title and
    its rows' labels, top to bottom under BACK."""

    @property
    def back_row(self):
        return len(self.labels)


# Single Player: today's entry exactly. The HUD writes the row's words:
# continue game while a saved profile exists, new game otherwise.
SINGLE = Page(PAGE_SINGLE, "SinglePanel", MODE_SINGLE_TEXT, "SingleBack", "SingleRows",
              (START_ROW_LABEL,))
SINGLE_START_ROW = 0
# Multiplayer: the server's address, typed on the row itself, and the join.
MULTI = Page(PAGE_MULTI, "MultiPanel", MODE_MULTI_TEXT, "MultiBack", "MultiRows",
             ("Server Address", "Join Server"))
MULTI_ADDRESS_ROW, MULTI_JOIN_ROW = 0, 1
PAGES = (SINGLE, MULTI)

# In play as a client of a server the menu's save-and-exit row is this instead:
# back to the title, the single-player profile neither read nor written.
LEAVE_ROW_LABEL = "Leave Server"

# Under the Multiplayer page's rows: that a join is under way, or why the
# last one failed or the last session dropped (the GameInstance's NetReason).
MULTI_STATUS = "MultiStatus"
CONNECTING_PREFIX, CONNECTING_SUFFIX = "connecting to ", " ..."
MULTI_HINT = "type the address  ·  ENTER or click selects"
# After the address while the caret is on its row: this is where typing goes.
ADDRESS_CARET = "_"
ADDRESS_MAX = 64

# What the address row types: a key, and the character it adds. Letters for a
# host's name, digits and dots for its number, the colon before the port
# (on the semicolon's key, with or without Shift). Backspace takes one off.
# None of them is a key the page itself uses (the arrows, Enter, Escape).
ADDRESS_KEYS = (tuple((chr(c), chr(c).lower()) for c in range(ord("A"), ord("Z") + 1))
                + tuple(zip(("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
                             "Eight", "Nine"), "0123456789"))
                + (("Period", "."), ("Semicolon", ":"), ("Colon", ":"), ("Hyphen", "-")))
ADDRESS_ERASE_KEY = "BackSpace"
# The HUD's copies of that table, walked by one ForEachLoop (as KeyPool is).
AddressKeys = Var("AddressKeys", array(struct("/Script/InputCore.Key")))
AddressChars = Var("AddressChars", array(STRING))
TABLE = (AddressKeys, AddressChars)
