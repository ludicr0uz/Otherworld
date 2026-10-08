"""The three menu screens' layouts: WBP_PauseMenu (the menu: the game opens
on it and M brings it up), WBP_MainMenu (its settings page, and the legal
notice) and WBP_DeathMenu.

Every menu line is a WBP_MenuRow whose label is set here, in the designer, so
what each screen says can be read (and changed) in the UMG editor. The HUD
graph writes only what changes: which row the caret is on, the value column,
the first row's words (new game, or resume in play), the death screen's
score, and which settings hint shows.
"""

import unreal

from uebp.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.wbp_legal import author_legal_notice
from graphics_menu.wbp_modes import author_mode_pages
from graphics_menu.wbp_tune import author_tune_widgets
from graphics_menu.umg_consts import (
    COL_CARET, COL_DEATH_HINT, COL_DEATH_TEXT, COL_DEATH_TITLE, COL_HINT,
    COL_MAIN_HINT, COL_ROW, COL_TITLE, DEATH_HINT, DEATH_HINT_LINE,
    DEATH_HINT_FONT, DEATH_PANEL_SIZE, DEATH_PLAYER_SCORE, DEATH_SCORE, DEATH_SCORE_FONT, DEATH_TITLE,
    DEATH_TITLE_FONT, HINT_CAPTURE, HINT_CAPTURE_TEXT, HINT_IDLE, HINT_IDLE_TEXT,
    PAUSE_HINT, PAUSE_HINT_FONT, PAUSE_MODE, PAUSE_MODE_FONT, PAUSE_PANEL, PAUSE_POS,
    PAUSE_ROW_LABEL_W,
    PAUSE_ROW_LABELS,
    PAUSE_ROW_SCALE, PAUSE_ROWS, PAUSE_TITLE, PAUSE_TITLE_FONT, PAUSE_W, ROW_COLOR_VAR,
    ROW_GAP, ROW_LABEL_W, ROW_TEXT_VAR, ROW_WIDTH_VAR, SET_HINT_FONT, SET_TITLE_FONT,
    SETTINGS_BACK, SETTINGS_PANEL, SETTINGS_PANEL_W, SETTINGS_ROW_LABELS, SETTINGS_ROWS_BOX,
    SETTINGS_TITLE_TEXT, WBP_DEATH_MENU, WBP_MAIN_MENU,
    WBP_MENU_ROW, WBP_PAUSE_MENU,
)
from graphics_menu.settings_rows import BACK_LABEL

CENTRE = ((0.5, 0.5), (0.5, 0.5), (0.0, 0.0))


def _rows(bp, parent, box, labels, width, col, scale=None):
    """A named stack of WBP_MenuRows, one per label, optionally scaled up."""
    if scale:
        parent = U.scaled(bp, parent, f"{box}Scale", scale)
        U.pad(parent, h="Center")
    stack = U.add(bp, unreal.VerticalBox, box, parent, variable=True)
    row_class = BEL.generated_class(_must_load(WBP_MENU_ROW))
    for i, label in enumerate(labels):
        row = U.add(bp, row_class, f"{box}{i}", stack)
        row.set_editor_property(ROW_TEXT_VAR, label)
        row.set_editor_property(ROW_WIDTH_VAR, float(width))
        row.set_editor_property(ROW_COLOR_VAR, U.slate_colour(col))
        U.pad(row, bottom=ROW_GAP)
    return stack


def _line(bp, parent, name, label, size, col, bold=False, top=0.0, bottom=0.0,
          variable=False, centred=True):
    t = U.text(bp, parent, name, label, size, col, variable=variable, bold=bold)
    U.pad(t, top=top, bottom=bottom, h="Center" if centred else None)
    return t


def build_main_menu():
    bp = U.widget_blueprint(WBP_MAIN_MENU)
    root = U.add(bp, unreal.CanvasPanel, "Root")

    settings, stack = U.panel(bp, root, SETTINGS_PANEL, "T_UI_Panel",
                              min_w=SETTINGS_PANEL_W, variable=True)
    # Where the menu is: the page stands in its place.
    U.at(settings, (0.0, 0.0), (0.0, 0.0), PAUSE_POS)
    _line(bp, stack, "SettingsTitle", SETTINGS_TITLE_TEXT, SET_TITLE_FONT, COL_TITLE,
          bold=True, bottom=18.0, centred=False)
    # BACK: the page's top row, a variable of its own outside the rows' box
    # (settings_rows.py says why its number is still the last).
    back = U.add(bp, BEL.generated_class(_must_load(WBP_MENU_ROW)), SETTINGS_BACK, stack,
                 variable=True)
    back.set_editor_property(ROW_TEXT_VAR, BACK_LABEL)
    back.set_editor_property(ROW_WIDTH_VAR, float(ROW_LABEL_W))
    back.set_editor_property(ROW_COLOR_VAR, U.slate_colour(COL_ROW))
    U.pad(back, bottom=ROW_GAP)
    _rows(bp, stack, SETTINGS_ROWS_BOX, SETTINGS_ROW_LABELS, ROW_LABEL_W, COL_ROW)
    _line(bp, stack, HINT_IDLE, HINT_IDLE_TEXT, SET_HINT_FONT, COL_MAIN_HINT,
          top=4.0, variable=True, centred=False)
    capture = _line(bp, stack, HINT_CAPTURE, HINT_CAPTURE_TEXT, SET_HINT_FONT,
                    COL_CARET, top=4.0, variable=True, centred=False)
    # The menu opens on its own rows; the HUD shows this page in their place.
    U.hide(capture)
    U.hide(settings)
    author_legal_notice(bp, root)
    return U.compile_and_save(bp)


def build_pause_menu():
    bp = U.widget_blueprint(WBP_PAUSE_MENU)
    root = U.add(bp, unreal.CanvasPanel, "Root")
    # A variable: the HUD collapses it while the settings page or a tuning tab
    # is open in its place.
    outer, stack = U.panel(bp, root, PAUSE_PANEL, "T_UI_Panel", min_w=PAUSE_W,
                           variable=True)
    U.at(outer, (0.0, 0.0), (0.0, 0.0), PAUSE_POS)
    _line(bp, stack, "PauseTitle", PAUSE_TITLE, PAUSE_TITLE_FONT, COL_TITLE, bold=True,
          bottom=2.0, centred=False)
    # Which mode the game in play is; the HUD writes it, empty on the title.
    _line(bp, stack, PAUSE_MODE, "", PAUSE_MODE_FONT, COL_HINT, bottom=12.0,
          variable=True, centred=False)
    rows = _rows(bp, stack, PAUSE_ROWS, PAUSE_ROW_LABELS, PAUSE_ROW_LABEL_W, COL_ROW,
                 PAUSE_ROW_SCALE)
    U.pad(rows.get_parent(), h="Left")
    _line(bp, stack, "PauseHint", PAUSE_HINT, PAUSE_HINT_FONT, COL_HINT, top=6.0,
          centred=False)
    author_tune_widgets(bp, root)
    author_mode_pages(bp, root)
    return U.compile_and_save(bp)


def build_death_menu():
    bp = U.widget_blueprint(WBP_DEATH_MENU)
    root = U.add(bp, unreal.CanvasPanel, "Root")
    outer, stack = U.panel(bp, root, "Panel", "T_UI_PanelDeath", *DEATH_PANEL_SIZE)
    U.at(outer, *CENTRE)
    _line(bp, stack, "DeathTitle", DEATH_TITLE, DEATH_TITLE_FONT, COL_DEATH_TITLE,
          bold=True, top=18.0, bottom=18.0)
    _line(bp, stack, DEATH_SCORE, "", DEATH_SCORE_FONT, COL_DEATH_TEXT, bottom=6.0,
          variable=True)
    _line(bp, stack, DEATH_PLAYER_SCORE, "", DEATH_SCORE_FONT, COL_DEATH_TEXT, bottom=28.0,
          variable=True)
    _line(bp, stack, DEATH_HINT_LINE, DEATH_HINT, DEATH_HINT_FONT, COL_DEATH_HINT,
          variable=True)
    return U.compile_and_save(bp)
