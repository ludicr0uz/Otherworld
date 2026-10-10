"""The two modes on BeginPlay and Tick: which process shows a title, what the
title's Multiplayer rows do, and how a client leaves its server.

    BeginPlay   standalone: the title, as ever. If the session ended without
                the player leaving it (a join failed, the server dropped
                them), the title opens on the Multiplayer page, where the
                reason shows.
                a client of a server: no title, the game is in play. It is
                already connected, whether it joined from the title or with
                an address on the command line.
    Tick, title the Multiplayer row opens its page; Join Server saves the
                address, notes the session and opens the server (the title
                stands, saying so, until the server's level replaces it);
                leaving the page gives a join up
    Tick, play  as a client: the menu's exit row is save and exit there
                too, the same row asking the same 15 s countdown of the
                weapon component (save_exit.author_exit_row). What leaving
                is differs: once the countdown is due the session is
                cleared and the engine's disconnect returns the process to
                the title. Nothing of the single-player profile runs there
                (author_mode_in_play): no load, no save, no wipe on death.

The mode is asked with IsStandalone, and only for what
`serversupportsysdesign.md` 4.8 lists: the title, and the character's save.
"""

from uebp.graph import _connect, _loose_pin, _palette, _pin, out, then
from combat.ask_consts import EXIT_DUE_VAR
from combat.paths import WEAPON_COMP_CLASS_PATH
from graphics_menu.cursor_consts import PAGE_CLICK_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.menu_nav import pause_row_taken
from graphics_menu.mode_consts import MULTI, MULTI_JOIN_ROW, PAGE_MULTI
from graphics_menu.mode_session import address, session, settings, sget, sput
from graphics_menu.profile_consts import EXIT_LEAVING_VAR
from graphics_menu.save_exit import author_exit_row
from graphics_menu.settings_input import _emit_save
from graphics_menu.umg_consts import GAME_STARTED_VAR, MULTI_ACTION
from net import session_consts as S
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN
from uebp.nodes.palette import NODE_CAST_WEAPON
from uebp.nodes.math import FN_AND, FN_EQ_II, FN_NOT, FN_OR
from uebp.nodes.system import (
    FN_CONSOLE, FN_IS_STANDALONE, FN_OPEN_LEVEL, FN_STR_EMPTY, FN_STR_TO_NAME)
from graphics_menu import hud_vars as MV


def _then(node, in_execs):
    for e in in_execs:
        _connect(e, _pin(node, "execute"))
    return then(node)


def _alone(ed, in_execs, made):
    return _branch(ed, out(_call(ed, FN_IS_STANDALONE, made)), in_execs, made)


def _filled(ed, text, made):
    return out(_call(ed, FN_NOT, made, A=out(_call(ed, FN_STR_EMPTY, made, InString=text))))


def page_row_taken(ed, page, row, made):
    """Row ``row`` of ``page`` was taken (Enter on it, or a click): a bool
    pin. PageClick is the row's number for the one Tick after DrawHUD raised
    it, and MenuPage says whose row it is."""
    here = _call(ed, FN_EQ_II, made, A=_get(ed, MV.MenuPage, made), B=page.page)
    hit = _call(ed, FN_EQ_II, made, A=_get(ed, PAGE_CLICK_VAR, made), B=row)
    return out(_call(ed, FN_AND, made, A=out(here), B=out(hit)))


def _author_ended(ed, gi, in_execs, made):
    flow = sput(ed, gi, S.JoinAddress, "", in_execs, made)
    return sput(ed, gi, S.Connecting, False, [flow], made)


def author_mode_begin(ed, in_execs):
    """BeginPlay (see the module docstring). Returns ``(title, client)``:
    the execs that go on to the title, and those of a connected client,
    which has none."""
    made = []
    alone, joined = _alone(ed, in_execs, made)
    gi, ok, failed = session(ed, [joined], made)
    client = [sput(ed, gi, S.Connecting, False, [ok], made), failed]

    gi, ok, failed = session(ed, [alone], made)
    ended = _call(ed, FN_OR, made, A=_filled(ed, sget(ed, gi, S.NetReason, made), made),
                  B=_filled(ed, sget(ed, gi, S.JoinAddress, made), made))
    back, clean = _branch(ed, out(ended), [ok], made)
    flow = _setter(ed, MV.MenuPage, PAGE_MULTI, [back], made)
    flow = _setter(ed, MV.MenuRow, MULTI_JOIN_ROW, [flow], made)
    told, untold = _branch(ed, _filled(ed, sget(ed, gi, S.NetReason, made), made), [flow], made)
    closed = sput(ed, gi, S.NetReason, S.REASON_CLOSED, [untold], made)
    ended = _author_ended(ed, gi, [told, closed], made)
    ed.add_comment_to_nodes(
        "Which process shows a title. Standalone does; and if the session "
        "ended without the player leaving it (the GameInstance still names a "
        "server, or holds a reason), the title opens on the Multiplayer page, "
        "which shows why. A client of a server is already connected, from the "
        "title or from an address on the command line: no title, in play.", made[:2])
    return [ended, clean, failed], client


def _author_open(ed, in_execs, made):
    """The Multiplayer row, on the title: its page, the caret on the address."""
    asked = _call(ed, FN_AND, made, A=pause_row_taken(ed, MULTI_ACTION, made),
                  B=out(_call(ed, FN_NOT, made, A=_get(ed, GAME_STARTED_VAR, made))))
    take, rest = _branch(ed, out(asked), in_execs, made)
    flow = _setter(ed, MV.MenuPage, PAGE_MULTI, [take], made)
    return [_setter(ed, MV.MenuRow, 0, [flow], made), rest]


def _author_join(ed, in_execs, made):
    """Join Server, with an address and no join under way: the address into
    the saved settings, the session noted, and the server opened. The title
    stays up, the page saying it is connecting, until the server's level
    replaces it or the GameInstance is told why not."""
    take, rest = _branch(ed, page_row_taken(ed, MULTI, MULTI_JOIN_ROW, made), in_execs, made)
    gi, ok, failed = session(ed, [take], made)
    idle = _call(ed, FN_NOT, made, A=sget(ed, gi, S.Connecting, made))
    ready = _call(ed, FN_AND, made, A=out(idle), B=_filled(ed, address(ed, made), made))
    go, not_now = _branch(ed, out(ready), [ok], made)
    saved, writer = _emit_save(ed, settings(ed, made), go)
    made.append(writer)
    flow = sput(ed, gi, S.NetReason, "", [saved], made)
    flow = sput(ed, gi, S.JoinAddress, address(ed, made), [flow], made)
    flow = sput(ed, gi, S.Connecting, True, [flow], made)
    where = _call(ed, FN_STR_TO_NAME, made, InString=sget(ed, gi, S.JoinAddress, made))
    opened = _then(_call(ed, FN_OPEN_LEVEL, made, LevelName=out(where)), [flow])
    return [opened, not_now, failed, rest]


def _author_give_up(ed, pc_out, in_execs, made):
    """A join under way and the player off the Multiplayer page (BACK, or
    Escape): the join is cancelled, and the title is a title again."""
    gi, ok, failed = session(ed, in_execs, made)
    away = _call(ed, FN_NOT, made, A=out(_call(
        ed, FN_EQ_II, made, A=_get(ed, MV.MenuPage, made), B=PAGE_MULTI)))
    left = _call(ed, FN_AND, made, A=sget(ed, gi, S.Connecting, made), B=out(away))
    stop, stay = _branch(ed, out(left), [ok], made)
    cancel = _call(ed, FN_CONSOLE, made, Command=S.CANCEL_COMMAND, SpecificPlayer=pc_out)
    return [_author_ended(ed, gi, [_then(cancel, [stop])], made), stay, failed]


def author_mode_rows_tick(ed, pc_out, in_play, on_title):
    """The Multiplayer row and its page's rows, on the title's Tick. Returns
    the exec tails, ``in_play`` among them."""
    made = []
    flow = _author_open(ed, on_title, made)
    flow = _author_join(ed, flow, made)
    flow = _author_give_up(ed, pc_out, flow, made)
    ed.add_comment_to_nodes(
        "Multiplayer, from the title: its row opens the page; Join Server "
        "saves the address and opens the server, the title standing until "
        "the server's level replaces it; leaving the page gives the join up.", made[:1])
    return flow + list(in_play)


def _weapon_component(ed, in_execs, made):
    """The owning pawn's weapon component, cast. Returns ``(pin, ok, failed)``."""
    comp = _call(ed, FN_GET_COMP, made, self=out(_call(ed, FN_GET_OWNING_PAWN, made)))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = _palette(ed, NODE_CAST_WEAPON)
    made.append(cast)
    _connect(out(comp), _pin(cast, "Object"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    return wc, _then(cast, in_execs), out(cast, "CastFailed")


def author_mode_in_play(ed, pc_out, in_execs):
    """A game in play, split by mode. Returns ``(single, client)``: the exec
    the single-player profile's fragment runs off (save and exit, the load,
    the wipe on death), and the tails of a client's, whose exit row asks the
    same countdown and, once it is due, leaves the server and touches none
    of the profile."""
    made = []
    single, client = _alone(ed, in_execs, made)
    wc, found, no_pawn = _weapon_component(ed, [client], made)
    flow = author_exit_row(ed, wc, [found], made)
    due = _get(ed, EXIT_DUE_VAR, made, WEAPON_COMP_CLASS_PATH, wc)
    fresh = _call(ed, FN_NOT, made, A=_get(ed, EXIT_LEAVING_VAR, made))
    go, stay = _branch(ed, out(_call(ed, FN_AND, made, A=due, B=out(fresh))), flow, made)
    flow = _setter(ed, EXIT_LEAVING_VAR, "true", [go], made)
    gi, ok, failed = session(ed, [flow], made)
    left = sput(ed, gi, S.NetReason, "", [_author_ended(ed, gi, [ok], made)], made)
    leave = _call(ed, FN_CONSOLE, made, Command=S.LEAVE_COMMAND, SpecificPlayer=pc_out)
    ed.add_comment_to_nodes(
        "The character's save is single player's: its fragment runs only in "
        "standalone. As a client of a server the menu's exit row asks the "
        "same countdown (save and exit), and once it is due the session is "
        "over on purpose (no reason to show) and the engine's disconnect "
        "returns this process to the title.", made[:1])
    return single, [_then(leave, [left, failed]), stay, no_pawn]
