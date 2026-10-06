"""DrawHUD: the title's two mode pages, and what the menu says about the mode.

  author_mode_pages    MenuPage on a page: its panel in the rows' place, the
                       caret (Up/Down round the rows and BACK, the cursor),
                       Enter or a click raising PageClick for Tick, BACK and
                       Escape back to the menu's rows
        Single Player  its row reads continue game while a saved profile
                       exists, new game otherwise
        Multiplayer    the address row shows the saved address and takes
                       typing while the caret is on it; the status line says
                       a join is under way, or why the last one ended
  author_mode_hidden   on the menu's own rows: both panels collapsed
  author_mode_words    the menu's rows: single player (resume in play),
                       multiplayer (from the title only), save and exit
                       (leave server as a client), and the mode under the title

DrawHUD, like the settings page's keys: the title is a paused world. What a
taken row does is Tick's (mode_tick.py).
"""

from uebp.graph import _connect, _loose_pin, _node, _pin, out, then
from graphics_menu.cursor import ROW, author_back_row, author_row_cursor
from graphics_menu.cursor_consts import PAGE_CLICK_VAR
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.loot_find import put
from graphics_menu.menu_nav import _emit_row_nav
from graphics_menu.mode_consts import (
    ADDRESS_CARET, ADDRESS_ERASE_KEY, ADDRESS_MAX, CONNECTING_PREFIX, CONNECTING_SUFFIX,
    LEAVE_ROW_LABEL, MULTI_ADDRESS_ROW, MULTI_STATUS, PAGES, SINGLE, SINGLE_START_ROW,
    AddressChars, AddressKeys)
from graphics_menu.mode_session import address, put_address, session, sget
from graphics_menu.profile_consts import (
    EXIT_ACTION, EXIT_ROW_LABEL, PROFILE_SLOT, PROFILE_USER_INDEX)
from graphics_menu.settings_rows import PAGE_TITLE
from graphics_menu.ui_graph import mark_rows, member, part, row_at, row_value, set_shown, set_text
from graphics_menu.umg_consts import (
    CONTINUE_ROW_LABEL, GAME_STARTED_VAR, MODE_MULTI_TEXT, MODE_SINGLE_TEXT, PAUSE_ACCEPT_KEY,
    PAUSE_MODE, PAUSE_ROW_ACTIONS, PAUSE_START_ROW, RESUME_ROW_LABEL, ROW_CARET, ROW_LABEL,
    ROW_VALUE, SINGLE_ROW_LABEL, START_ROW_LABEL, TITLE_ACTIONS, TITLE_ONLY, WBP_MENU_ROW,
    WBP_PAUSE_MENU)
from net import session_consts as S
from uebp.nodes.actor import FN_GET_OWNING_PC, FN_WAS_PRESSED
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.math import FN_EQ_II, FN_GE_II, FN_LESS_II, FN_SELECT_FF, FN_SELECT_STR
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import (
    FN_CONCAT, FN_IS_STANDALONE, FN_SAVE_EXISTS, FN_STR_LEFT_CHOP, FN_STR_LEN)
from uebp.nodes.umg import FN_SET_OPACITY
from graphics_menu import hud_vars as MV


def _caret(ed, made):
    return _get(ed, MV.MenuRow, made)


def _author_keys(ed, page, rows, back, in_execs, made):
    """The page's caret and what takes a row. Returns the exec tails."""
    pc = out(_call(ed, FN_GET_OWNING_PC, made))
    hovered = author_row_cursor(ed, rows, len(page.labels), in_execs, row_var=MV.MenuRow,
                                click=(PAGE_CLICK_VAR, ROW))
    moved, nav = _emit_row_nav(ed, pc, page.back_row, hovered, row_var=MV.MenuRow)
    made += nav
    enter = _call(ed, FN_WAS_PRESSED, made, self=pc, Key=PAUSE_ACCEPT_KEY)
    take, idle = _branch(ed, out(enter), list(moved), made)
    taken = put(ed, PAGE_CLICK_VAR, _caret(ed, made), [take], made)
    # After the rows' own Enter: on BACK that raised a PageClick no row has,
    # and this lowers MenuPage.
    backed = author_back_row(ed, back, MV.MenuRow, page.back_row, MV.MenuPage,
                             [taken, idle], closed=PAGE_TITLE)
    flow = mark_rows(ed, rows, len(page.labels), _caret(ed, made), backed)
    on_back = _call(ed, FN_GE_II, made, A=_caret(ed, made), B=page.back_row)
    lit = _call(ed, FN_SELECT_FF, made, A=1.0, B=0.0)
    _connect(out(on_back), _loose_pin(lit, "bPickA"))
    fade = _call(ed, FN_SET_OPACITY, made, self=member(ed, back, WBP_MENU_ROW, ROW_CARET),
                 InOpacity=out(lit))
    _connect(flow, _pin(fade, "execute"))
    return [then(fade)]


def _author_single(ed, rows, in_execs, made):
    """The row's words. The save is looked for every frame, not once: a
    profile is written and deleted while the HUD lives (save and exit, a
    death), and a file's existence is cheap beside a frame."""
    row, found, missing = row_at(ed, rows, SINGLE_START_ROW, in_execs)
    text = member(ed, row, WBP_MENU_ROW, ROW_LABEL)
    exists = _call(ed, FN_SAVE_EXISTS, made, SlotName=PROFILE_SLOT,
                   UserIndex=PROFILE_USER_INDEX)
    _connect(found, _pin(exists, "execute"))
    saved, fresh = _branch(ed, out(exists), [then(exists)], made)
    return [set_text(ed, text, CONTINUE_ROW_LABEL, [saved]),
            set_text(ed, text, START_ROW_LABEL, [fresh]), missing]


def _author_typing(ed, in_execs, made):
    """While the caret is on the address row: each key of AddressKeys that
    went down adds its character, Backspace takes the last one off. The
    address is BP_Settings', saved when a join is asked for."""
    on_row = _call(ed, FN_EQ_II, made, A=_caret(ed, made), B=MULTI_ADDRESS_ROW)
    typing, idle = _branch(ed, out(on_row), in_execs, made)
    pc = out(_call(ed, FN_GET_OWNING_PC, made))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(_get(ed, AddressKeys, made), _loose_pin(loop, "Array"))
    _connect(typing, _loose_pin(loop, "Exec"))
    hit = _call(ed, FN_WAS_PRESSED, made, self=pc,
                Key=_loose_pin(loop, "ArrayElement", is_input=False))
    # A first: a comparison's B takes no literal until its A is typed.
    room = _call(ed, FN_LESS_II, made,
                 A=out(_call(ed, FN_STR_LEN, made, S=address(ed, made))), B=ADDRESS_MAX)
    pressed, _not = _branch(ed, out(hit), [_loose_pin(loop, "LoopBody", is_input=False)], made)
    fits, _full = _branch(ed, out(room), [pressed], made)
    char = _node(ed, FN_ARR_GET)
    made.append(char)
    _connect(_get(ed, AddressChars, made), _loose_pin(char, "TargetArray"))
    _connect(_loose_pin(loop, "ArrayIndex", is_input=False), _loose_pin(char, "Index"))
    longer = _call(ed, FN_CONCAT, made, A=address(ed, made),
                   B=_loose_pin(char, "Item", is_input=False))
    put_address(ed, out(longer), [fits], made)

    erase = _call(ed, FN_WAS_PRESSED, made, self=pc, Key=ADDRESS_ERASE_KEY)
    back, kept = _branch(ed, out(erase), [_loose_pin(loop, "Completed", is_input=False)], made)
    shorter = _call(ed, FN_STR_LEFT_CHOP, made, SourceString=address(ed, made), Count=1)
    return [put_address(ed, out(shorter), [back], made), kept, idle]


def _author_multi(ed, rows, in_execs, made):
    """The address, typed and shown, and the status line."""
    flow = _author_typing(ed, in_execs, made)
    on_row = _call(ed, FN_EQ_II, made, A=_caret(ed, made), B=MULTI_ADDRESS_ROW)
    marked = _call(ed, FN_CONCAT, made, A=address(ed, made), B=ADDRESS_CARET)
    shown = _call(ed, FN_SELECT_STR, made, A=out(marked), B=address(ed, made))
    _connect(out(on_row), _loose_pin(shown, "bPickA"))
    flow = row_value(ed, rows, MULTI_ADDRESS_ROW, out(shown), flow)

    status = part(ed, WBP_PAUSE_MENU, MULTI_STATUS)
    gi, ok, failed = session(ed, flow, made)
    joining, told = _branch(ed, sget(ed, gi, S.Connecting, made), [ok], made)
    where = _call(ed, FN_CONCAT, made, A=CONNECTING_PREFIX, B=sget(ed, gi, S.JoinAddress, made))
    saying = _call(ed, FN_CONCAT, made, A=out(where), B=CONNECTING_SUFFIX)
    return [set_text(ed, status, out(saying), [joining]),
            set_text(ed, status, sget(ed, gi, S.NetReason, made), [told]), failed]


def author_mode_pages(ed, in_execs):
    """MenuPage is neither the menu's rows nor the settings page: the page it
    names, shown and worked; the other collapsed. Returns the exec tails."""
    made, flow, tails = [], list(in_execs), []
    for page in PAGES:
        panel = part(ed, WBP_PAUSE_MENU, page.panel)
        on = _call(ed, FN_EQ_II, made, A=_get(ed, MV.MenuPage, made), B=page.page)
        here, other = _branch(ed, out(on), flow, made)
        rows = part(ed, WBP_PAUSE_MENU, page.rows_box)
        back = part(ed, WBP_PAUSE_MENU, page.back)
        keyed = _author_keys(ed, page, rows, back, [set_shown(ed, panel, True, [here])], made)
        tails += (_author_single if page is SINGLE else _author_multi)(ed, rows, keyed, made)
        flow = [set_shown(ed, panel, False, [other])]
    ed.add_comment_to_nodes(
        "The title's mode pages, in the menu's rows' place: Single Player "
        "(continue game or new game) and Multiplayer (the server's address, "
        "typed on its row, the join, and why the last one ended). MenuRow is "
        "the caret; Enter or a click raises PageClick, served by Tick; BACK "
        "or Escape returns to the rows.", made[:2])
    return tails + flow


def author_mode_hidden(ed, in_execs):
    """On the menu's own rows no page shows. Returns the then pin."""
    flow = list(in_execs)
    for page in PAGES:
        flow = [set_shown(ed, part(ed, WBP_PAUSE_MENU, page.panel), False, flow)]
    return flow[0]


def author_mode_words(ed, rows, in_execs, made):
    """What the menu's rows say about the mode. Returns the exec tails."""
    def words(action, widget, in_execs):
        row, found, missing = row_at(ed, rows, PAUSE_ROW_ACTIONS.index(action), in_execs)
        return member(ed, row, WBP_MENU_ROW, widget), found, missing

    def started(in_execs):
        return _branch(ed, _get(ed, GAME_STARTED_VAR, made), in_execs, made)

    def alone(in_execs):
        return _branch(ed, out(_call(ed, FN_IS_STANDALONE, made)), in_execs, made)

    # The first row: the Single Player page from the title, resume in play.
    text, found, missing = row_at(ed, rows, PAUSE_START_ROW, in_execs)
    text = member(ed, text, WBP_MENU_ROW, ROW_LABEL)
    playing, title = started([found])
    flow = [set_text(ed, text, RESUME_ROW_LABEL, [playing]),
            set_text(ed, text, SINGLE_ROW_LABEL, [title]), missing]
    # The rows that only the title serves say so in play.
    for action in TITLE_ACTIONS:
        text, found, missing = words(action, ROW_VALUE, flow)
        playing, title = started([found])
        flow = [set_text(ed, text, TITLE_ONLY, [playing]),
                set_text(ed, text, "", [title]), missing]
    # Save and exit is single player's; a client leaves its server instead.
    text, found, missing = words(EXIT_ACTION, ROW_LABEL, flow)
    single, client = alone([found])
    flow = [set_text(ed, text, EXIT_ROW_LABEL, [single]),
            set_text(ed, text, LEAVE_ROW_LABEL, [client]), missing]
    # The mode, under the menu's title, once a game is in play.
    mode = part(ed, WBP_PAUSE_MENU, PAUSE_MODE)
    playing, title = started(flow)
    single, client = alone([playing])
    return [set_text(ed, mode, MODE_SINGLE_TEXT, [single]),
            set_text(ed, mode, MODE_MULTI_TEXT, [client]),
            set_text(ed, mode, "", [title])]
