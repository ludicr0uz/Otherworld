"""The three menu screens' layouts: WBP_MainMenu (the title page and the
settings page), WBP_PauseMenu (the M panel) and WBP_DeathMenu.

Every menu line is a WBP_MenuRow whose label is set here, in the designer, so
what each screen says can be read (and changed) in the UMG editor. The HUD
graph writes only what changes: which row the caret is on, the value column,
the death screen's score, and which settings hint shows.
"""

import unreal

from combat.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.umg_consts import (
    COL_CARET, COL_DEATH_HINT, COL_DEATH_TEXT, COL_DEATH_TITLE, COL_GOLD, COL_HINT,
    COL_MAIN_HINT, COL_MAIN_SUB, COL_MAIN_TITLE, COL_ROW, COL_TITLE, DEATH_HINT,
    DEATH_HINT_FONT, DEATH_PANEL_SIZE, DEATH_SCORE, DEATH_SCORE_FONT, DEATH_TITLE,
    DEATH_TITLE_FONT, GAME_SUBTITLE, GAME_TITLE, HINT_CAPTURE, HINT_CAPTURE_TEXT,
    HINT_IDLE, HINT_IDLE_TEXT, MAIN_HINT, MAIN_HINT_FONT, MAIN_PANEL_SIZE,
    MAIN_ROW_LABEL_W, MAIN_ROW_SCALE, MAIN_SUB_FONT, MAIN_TITLE_FONT, MENU_ROWS,
    PAUSE_HINT, PAUSE_HINT_FONT, PAUSE_POS, PAUSE_ROW_LABEL_W, PAUSE_ROW_LABELS,
    PAUSE_ROW_SCALE, PAUSE_ROWS, PAUSE_TITLE, PAUSE_TITLE_FONT, PAUSE_W, ROW_COLOR_VAR,
    ROW_GAP, ROW_LABEL_W, ROW_TEXT_VAR, ROW_WIDTH_VAR, SET_HINT_FONT, SET_TITLE_FONT,
    SETTINGS_PANEL, SETTINGS_PANEL_W, SETTINGS_ROW_LABELS, SETTINGS_ROWS_BOX,
    SETTINGS_TITLE_TEXT, TITLE_PANEL, TITLE_ROWS, WBP_DEATH_MENU, WBP_MAIN_MENU,
    WBP_MENU_ROW, WBP_PAUSE_MENU,
)

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

    title, stack = U.panel(bp, root, TITLE_PANEL, "T_UI_Panel", *MAIN_PANEL_SIZE,
                           variable=True)
    U.at(title, *CENTRE)
    _line(bp, stack, "GameTitle", GAME_TITLE, MAIN_TITLE_FONT, COL_MAIN_TITLE, bold=True)
    _line(bp, stack, "GameSubtitle", GAME_SUBTITLE, MAIN_SUB_FONT, COL_MAIN_SUB,
          bottom=24.0)
    _rows(bp, stack, TITLE_ROWS, MENU_ROWS, MAIN_ROW_LABEL_W, COL_GOLD, MAIN_ROW_SCALE)
    _line(bp, stack, "MainHint", MAIN_HINT, MAIN_HINT_FONT, COL_MAIN_HINT, top=6.0)

    settings, stack = U.panel(bp, root, SETTINGS_PANEL, "T_UI_Panel",
                              min_w=SETTINGS_PANEL_W, variable=True)
    U.at(settings, *CENTRE)
    _line(bp, stack, "SettingsTitle", SETTINGS_TITLE_TEXT, SET_TITLE_FONT, COL_TITLE,
          bold=True, bottom=18.0, centred=False)
    _rows(bp, stack, SETTINGS_ROWS_BOX, SETTINGS_ROW_LABELS, ROW_LABEL_W, COL_ROW)
    _line(bp, stack, HINT_IDLE, HINT_IDLE_TEXT, SET_HINT_FONT, COL_MAIN_HINT,
          top=4.0, variable=True, centred=False)
    capture = _line(bp, stack, HINT_CAPTURE, HINT_CAPTURE_TEXT, SET_HINT_FONT,
                    COL_CARET, top=4.0, variable=True, centred=False)
    # The designer opens on the title page; the HUD picks the page per frame.
    U.hide(capture)
    U.hide(settings)
    return U.compile_and_save(bp)


def build_pause_menu():
    bp = U.widget_blueprint(WBP_PAUSE_MENU)
    root = U.add(bp, unreal.CanvasPanel, "Root")
    outer, stack = U.panel(bp, root, "Panel", "T_UI_Panel", min_w=PAUSE_W)
    U.at(outer, (0.0, 0.0), (0.0, 0.0), PAUSE_POS)
    _line(bp, stack, "PauseTitle", PAUSE_TITLE, PAUSE_TITLE_FONT, COL_TITLE, bold=True,
          bottom=18.0, centred=False)
    rows = _rows(bp, stack, PAUSE_ROWS, PAUSE_ROW_LABELS, PAUSE_ROW_LABEL_W, COL_ROW,
                 PAUSE_ROW_SCALE)
    U.pad(rows.get_parent(), h="Left")
    _line(bp, stack, "PauseHint", PAUSE_HINT, PAUSE_HINT_FONT, COL_HINT, top=6.0,
          centred=False)
    return U.compile_and_save(bp)


def build_death_menu():
    bp = U.widget_blueprint(WBP_DEATH_MENU)
    root = U.add(bp, unreal.CanvasPanel, "Root")
    outer, stack = U.panel(bp, root, "Panel", "T_UI_PanelDeath", *DEATH_PANEL_SIZE)
    U.at(outer, *CENTRE)
    _line(bp, stack, "DeathTitle", DEATH_TITLE, DEATH_TITLE_FONT, COL_DEATH_TITLE,
          bold=True, top=18.0, bottom=18.0)
    _line(bp, stack, DEATH_SCORE, "", DEATH_SCORE_FONT, COL_DEATH_TEXT, bottom=28.0,
          variable=True)
    _line(bp, stack, "DeathHint", DEATH_HINT, DEATH_HINT_FONT, COL_DEATH_HINT)
    return U.compile_and_save(bp)
