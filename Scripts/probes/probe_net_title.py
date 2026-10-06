"""The two modes from one title, in one process: join a server through the
Multiplayer page, leave it with Leave Server, then start a single-player game.

    python3 Scripts/dev/uepy.py --net --title --windowed --clients 1 \\
        --probe-timeout 240 --probe Scripts/probes/probe_net_title.py

``--title``: the client starts alone on the level, on the real title, and
this probe joins the server through the menu. ``--windowed``: what the menu
says is DrawHUD's, which a -nullrhi client never runs (those checks are
noted, not made, without it).

  client 1   the title: Single Player and Multiplayer, its first two rows
             Multiplayer: the address typed, Join Server, "connecting to ..."
             on the server: no title, in play, nothing paused; the menu says
             MULTIPLAYER and its exit row Leave Server
             Leave Server: back on the title, alone, no reason to show, the
             single-player profile's file untouched
             Single Player, New Game: a game, alone, in the same process
  server     has the player while they are on it, and not after they leave

The client's world and HUD are new after each travel: every step asks again
(probes/title.py).
"""

import os

import unreal

from graphics_menu import hud_vars as MV
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.profile_consts import EXIT_ACTION, EXIT_ROW_LABEL
from graphics_menu.settings_rows import PAGE_TITLE
from net import session_consts as S
from probes import title as T

RUNS_ON = ("server", "client 1")
WRITABLE = list(T.WRITABLE)
TRAVEL_S = 90.0
EXIT_ROW = C.PAUSE_ROW_ACTIONS.index(EXIT_ACTION)
MULTI_ROW = C.PAUSE_ROW_ACTIONS.index(C.MULTI_ACTION)


def probe_server(p):
    # boot.py starts this once the client's player has joined.
    pawns = [c.get_controlled_pawn() for c in p.players()]
    p.check("the server has the player who joined from the title, with a pawn",
            len(pawns) == 1 and bool(pawns[0]), f"{len(pawns)} player(s)")
    p.post("seen")
    yield from T.wait(lambda: p.posted("client 1", "left"), 3 * TRAVEL_S)
    yield from T.wait(lambda: len(p.players()) == 0, 20.0)
    p.check("...and no longer has them once they leave",
            bool(p.posted("client 1", "left")) and len(p.players()) == 0,
            f"{len(p.players())} player(s)")


def _frames(n=4):
    """A few rendered frames, for DrawHUD to write what the menu says."""
    left = [n]

    def done():
        left[0] -= 1
        return left[0] <= 0
    return done


def _shown(p, label, read, want):
    """A check of what the menu shows; a note where no HUD is drawn."""
    if not T.drawn(p):
        p.note(f"not drawn here (run --windowed): {label}")
        return
    got = read()
    p.check(label, got == want, f"{got!r}")


def probe_client(p):
    yield from T.wait(lambda: T.on_title(p), 20.0)
    if not T.on_title(p):
        p.check("the client opens on the title (run with uepy.py --net --title)", False,
                "no paused title: the client joined from the command line")
        return
    pid, gi, own = os.getpid(), T.session(p), T.address(p)
    profile = T.profile_file()
    try:
        yield from _both_modes(p, gi, profile)
    finally:
        if p.world() and p.hud():
            T.restore_address(p, own)
    p.check("...all in one process", os.getpid() == pid and T.session(p) == gi, f"pid {pid}")


def _both_modes(p, gi, profile):
    hud = p.hud()
    yield _frames()
    p.check("the client opens on the title: paused, alone, in no session",
            T.on_title(p) and str(p.get(gi, S.JoinAddress)) == "")
    _shown(p, "the title's first two rows are Single Player and Multiplayer",
           lambda: [T.row_text(p, C.PAUSE_ROWS, i) for i in (C.PAUSE_START_ROW, MULTI_ROW)],
           [C.SINGLE_ROW_LABEL, C.MULTI_ROW_LABEL])

    # --- Multiplayer: the address, the join ------------------------------------
    yield from T.take_row(p, C.MULTI_ACTION, lambda: p.get(hud, MV.MenuPage) == MC.PAGE_MULTI)
    T.type_address(p, p.net.address)
    yield _frames()
    _shown(p, "the Multiplayer page shows the address on its row, the caret after it",
           lambda: T.row_text(p, MC.MULTI.rows_box, MC.MULTI_ADDRESS_ROW, C.ROW_VALUE),
           p.net.address + MC.ADDRESS_CARET)
    yield from T.take_page_row(p, MC.MULTI_JOIN_ROW, lambda: p.get(gi, S.Connecting))
    p.check("Join Server notes the session: connecting, to the server's address",
            p.get(gi, S.Connecting) is True
            and str(p.get(gi, S.JoinAddress)) == p.net.address,
            f"to {str(p.get(gi, S.JoinAddress))!r}")
    if p.world() and p.hud() == hud:
        yield _frames(2)
    if p.world() and p.hud() == hud and p.get(gi, S.Connecting):
        _shown(p, "...and the page says so while the title waits",
               lambda: T.menu_text(p, MC.MULTI_STATUS),
               MC.CONNECTING_PREFIX + p.net.address + MC.CONNECTING_SUFFIX)

    # --- on the server ---------------------------------------------------------
    yield from T.wait(lambda: T.in_play(p) and not T.alone(p), TRAVEL_S)
    joined = bool(p.world()) and T.in_play(p) and not T.alone(p)
    p.check("the client is on the server: no title, in play from BeginPlay, "
            "nothing paused", joined and not T.paused(p) and p.hud() != hud,
            f"in play {joined}")
    if not joined:
        return
    p.check("...the join over, the session the server's address, no reason",
            p.get(gi, S.Connecting) is False
            and str(p.get(gi, S.JoinAddress)) == p.net.address
            and str(p.get(gi, S.NetReason)) == "")
    yield from T.wait(lambda: p.posted("server", "seen"), 30.0)
    p.check("the server has this player", bool(p.posted("server", "seen")))

    hud = p.hud()
    p.set(hud, MV.MenuOpen, True)
    yield _frames()
    p.check("the menu up as a client pauses nothing", not T.paused(p))
    _shown(p, "the menu says which mode this is, and its exit row reads Leave Server",
           lambda: [T.menu_text(p, C.PAUSE_MODE), T.row_text(p, C.PAUSE_ROWS, EXIT_ROW),
                    T.row_text(p, C.PAUSE_ROWS, C.PAUSE_START_ROW),
                    T.row_text(p, C.PAUSE_ROWS, MULTI_ROW, C.ROW_VALUE)],
           [C.MODE_MULTI_TEXT, MC.LEAVE_ROW_LABEL, C.RESUME_ROW_LABEL, C.TITLE_ONLY])

    # --- Leave Server ----------------------------------------------------------
    yield from T.take_row(p, EXIT_ACTION, lambda: T.on_title(p), TRAVEL_S)
    left = T.on_title(p)
    p.check("Leave Server returns to the title: alone, paused, a new HUD",
            left and p.hud() != hud, f"on the title {left}")
    if not left:
        return
    p.post("left")
    hud = p.hud()
    p.check("...on its own rows, with no reason to show and no server its session",
            p.get(hud, MV.MenuPage) == PAGE_TITLE and str(p.get(gi, S.NetReason)) == ""
            and str(p.get(gi, S.JoinAddress)) == "",
            f"page {p.get(hud, MV.MenuPage)}, reason {str(p.get(gi, S.NetReason))!r}")
    p.check("...and the single-player profile's file is as it was: neither read "
            "into the server's character nor written", T.profile_file() == profile,
            f"{profile} -> {T.profile_file()}")
    p.check("the address joined is remembered in the settings",
            T.address(p) == p.net.address, T.address(p))

    # --- Single Player, from the same title ------------------------------------
    yield from T.take_row(p, C.START_ACTION, lambda: p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE)
    yield _frames()
    _shown(p, "the Single Player page's row reads new game, or continue game "
           "with a saved profile",
           lambda: T.row_text(p, MC.SINGLE.rows_box, MC.SINGLE_START_ROW),
           C.CONTINUE_ROW_LABEL if profile[0] else C.START_ROW_LABEL)
    yield from T.take_page_row(p, MC.SINGLE_START_ROW, lambda: T.in_play(p))
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    yield from T.wait(lambda: unreal.GameplayStatics.get_time_seconds(p.world()) > t0 + 0.2)
    p.check("from the same title a single-player game starts: alone, unpaused, "
            "time running, the same HUD",
            T.in_play(p) and T.alone(p) and not T.paused(p) and p.hud() == hud
            and unreal.GameplayStatics.get_time_seconds(p.world()) > t0,
            f"in play {T.in_play(p)}, alone {T.alone(p)}, paused {T.paused(p)}")
    p.set(hud, MV.MenuOpen, True)
    yield _frames()
    _shown(p, "...and its menu says SINGLE PLAYER, the exit row Save and Exit",
           lambda: [T.menu_text(p, C.PAUSE_MODE), T.row_text(p, C.PAUSE_ROWS, EXIT_ROW)],
           [C.MODE_SINGLE_TEXT, EXIT_ROW_LABEL])
    p.set(hud, MV.MenuOpen, False)
