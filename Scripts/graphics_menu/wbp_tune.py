"""WBP_PauseMenu's tuning panels, one per TuneTab (tune_tab.py): GUN, MONSTER,
WORLD, PLAYER and GRAPHICS SETTINGS. Only one is open at a time, and an open one stands
in place of the M panel's own rows (menu_screens.author_pause_menu).

  where the M panel is   the tab's panel: a title, row_count WBP_MenuRows (the
  (TUNE_POS), or the     subject, then one per stat, each labelled in the
  bottom-right corner    designer; the HUD writes the value column and the
  (tab.corner)           caret), "saved to ..." after a save, the keys' hint,
                         a save row if the tab has one (tab.save_widget:
                         GRAPHICS SETTINGS's SAVE DEFAULT), and BACK, a row
                         of its own under the list

A tab with visible_rows keeps its list in a ScrollBox that many rows high:
the bar always shows, and the HUD scrolls the caret's row into view
(tune_draw.py). Nothing here is hit-testable, so the bar is a picture of
where the list is, not a handle.

Starts collapsed; tune_draw.py shows it while the tab is open and writes the rows.
"""

import unreal

from combat.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.settings_rows import BACK_LABEL
from graphics_menu.tune_consts import (
    TUNE_CORNER_MARGIN, TUNE_CORNER_PADDING, TUNE_HINT_FONT, TUNE_PANEL_W, TUNE_POS, TUNE_ROW_H,
    TUNE_ROW_LABEL_W, TUNE_TITLE_FONT,
)
from graphics_menu.umg_consts import (
    COL_CARET, COL_HINT, COL_ROW, COL_TITLE, PANEL_PADDING, ROW_COLOR_VAR, ROW_TEXT_VAR,
    ROW_WIDTH_VAR, WBP_MENU_ROW,
)
from graphics_menu.tune_tabs import TABS


def author_tune_widgets(bp, root):
    for tab in TABS:
        _author_tab(bp, root, tab)


def _row(bp, parent, name, label, width, variable=False):
    row = U.add(bp, BEL.generated_class(_must_load(WBP_MENU_ROW)), name, parent,
                variable=variable)
    row.set_editor_property(ROW_TEXT_VAR, label)
    row.set_editor_property(ROW_WIDTH_VAR, width)
    row.set_editor_property(ROW_COLOR_VAR, U.slate_colour(COL_ROW))
    return row


def _list(bp, stack, tab):
    """The box the rows go in: a plain stack, or a scrolling window."""
    if not tab.visible_rows:
        return U.add(bp, unreal.VerticalBox, tab.rows_box, stack, variable=True)
    window = U.sized(bp, stack, f"{tab.rows_box}Window", h=tab.visible_rows * TUNE_ROW_H)
    rows = U.add(bp, unreal.ScrollBox, tab.rows_box, window, variable=True)
    rows.set_editor_property("always_show_scrollbar", True)
    # The HUD moves it (ScrollWidgetIntoView), never the user: no bounce.
    rows.set_editor_property("allow_overscroll", False)
    return rows


def _author_tab(bp, root, tab):
    outer, stack = U.panel(bp, root, tab.panel, "T_UI_Panel",
                           min_w=tab.panel_w or TUNE_PANEL_W, variable=True,
                           padding=TUNE_CORNER_PADDING if tab.corner else PANEL_PADDING)
    if tab.corner:
        U.at(outer, (1.0, 1.0), (1.0, 1.0), tuple(-m for m in TUNE_CORNER_MARGIN))
    else:
        U.at(outer, (0.0, 0.0), (0.0, 0.0), TUNE_POS)
    title = U.text(bp, stack, tab.title_widget, tab.title_text,
                   tab.title_font or TUNE_TITLE_FONT, COL_TITLE, bold=True)
    U.pad(title, bottom=6.0 if tab.corner else 10.0)
    rows = _list(bp, stack, tab)
    width = tab.label_w or TUNE_ROW_LABEL_W
    for i, label in enumerate(tab.row_labels):
        row = _row(bp, rows, f"{tab.rows_box}{i}", label, width)
        # The subject row stands apart from the stats under it; in a
        # scrolling list every row is the window's row height.
        U.pad(row, bottom=8.0 if i == 0 and not tab.visible_rows else 0.0)
    saved = U.text(bp, stack, tab.saved_text, tab.saved_words, TUNE_HINT_FONT,
                   COL_CARET, variable=True)
    U.pad(saved, top=6.0)
    U.hide(saved)
    # A variable: a click on the hint line saves (tune_draw.py).
    hint = U.text(bp, stack, tab.hint_widget, tab.hint_text, TUNE_HINT_FONT, COL_HINT,
                  variable=True)
    U.pad(hint, top=6.0)
    if tab.save_widget:
        # The save, as a row of its own: Enter on it or a click (tune_tick.py,
        # tune_draw.py). Such a tab's hint is only words.
        save = _row(bp, stack, tab.save_widget, tab.save_label, width, variable=True)
        U.pad(save, top=8.0)
    # BACK: the caret's last stop. Enter on it or a click shuts the tab.
    back = _row(bp, stack, tab.back_widget, BACK_LABEL, width, variable=True)
    U.pad(back, top=8.0)
    U.hide(outer)
