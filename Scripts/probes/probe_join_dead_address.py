"""A join to an address where no server listens returns the player to the
title, with the reason on the Multiplayer page.

    python3 Scripts/dev/uepy.py --game --title --probe-timeout 150 \\
        --probe Scripts/probes/probe_join_dead_address.py

The real title (``--title``), its Multiplayer row, an address nothing answers
on, and Join Server.

  Join Server      the GameInstance notes the session: Connecting, the address
  while it waits   the title still stands, paused, on the Multiplayer page
  the failure      the engine gives the join up (its connection timeout, 20 s),
                   tells the GameInstance why, and opens the title's level
                   again: a new title, on the Multiplayer page, the caret on
                   Join Server, the reason kept for its status line
  from that title  Single Player starts a game: the failure left nothing behind
  the address      is BP_Settings', saved as the join was asked for (the next
                   title has it); the probe puts the player's own back

The waits are on the wall clock: game time stands still on a paused title.
"""

import time

from graphics_menu import hud_vars as MV
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.settings_rows import PAGE_TITLE
from net import session_consts as S
from probes import title as T

WRITABLE = list(T.WRITABLE)
# Loopback, a port nothing listens on.
DEAD_ADDRESS = "127.0.0.1:17999"
FAIL_WITHIN_S = 90.0


def probe(p):
    yield from T.wait(lambda: T.on_title(p))
    if not T.on_title(p):
        p.check("the game opens on the title (run with uepy.py --game --title)", False,
                "no paused title: -nomenu is on the command line")
        return
    gi = T.session(p)
    p.check("the game's GameInstance is the session's",
            gi.get_class().get_path_name() == S.GAME_INSTANCE_CLASS_PATH,
            gi.get_class().get_path_name())
    own = T.address(p)
    try:
        yield from _join_and_fail(p, gi)
    finally:
        T.restore_address(p, own)


def _join_and_fail(p, gi):
    hud = p.hud()
    yield from T.take_row(p, C.MULTI_ACTION, lambda: p.get(hud, MV.MenuPage) == MC.PAGE_MULTI)
    p.check("the Multiplayer row opens its page, the caret on the address",
            p.get(hud, MV.MenuPage) == MC.PAGE_MULTI
            and p.get(hud, MV.MenuRow) == MC.MULTI_ADDRESS_ROW and T.on_title(p),
            f"page {p.get(hud, MV.MenuPage)}, row {p.get(hud, MV.MenuRow)}")
    T.type_address(p, DEAD_ADDRESS)
    yield from T.take_page_row(p, MC.MULTI_JOIN_ROW, lambda: p.get(gi, S.Connecting))
    p.check("Join Server notes the session: connecting, to the typed address",
            p.get(gi, S.Connecting) is True
            and str(p.get(gi, S.JoinAddress)) == DEAD_ADDRESS
            and str(p.get(gi, S.NetReason)) == "",
            f"connecting {p.get(gi, S.Connecting)}, to {p.get(gi, S.JoinAddress)!r}")
    yield from T.wait(lambda: False, 1.0)
    # Not T.on_title: with a join pending the engine already answers "not
    # standalone" for this world (its net mode is derived from the pending
    # game), though it is the same paused title.
    p.check("while it waits the title stands, paused, on the Multiplayer page",
            p.hud() == hud and T.paused(p) and p.get(hud, C.GAME_STARTED_VAR) is False
            and p.get(hud, MV.MenuPage) == MC.PAGE_MULTI,
            f"same HUD {p.hud() == hud}, paused {T.paused(p)}, "
            f"page {p.get(hud, MV.MenuPage)}")
    p.note(f"IsStandalone while the join is pending: {T.alone(p)}")

    began = time.time()
    yield from T.wait(lambda: not p.get(gi, S.Connecting), FAIL_WITHIN_S)
    reason = str(p.get(gi, S.NetReason))
    p.check("the join fails with a reason for the player",
            p.get(gi, S.Connecting) is False and reason in S.NET_REASONS.values(),
            f"{reason!r} after {time.time() - began:.0f} s")
    # The engine opens the title's level again: a new world, a new HUD.
    yield from T.wait(lambda: T.on_title(p) and p.hud() != hud, 60.0)
    back = p.hud()
    p.check("...and the player is returned to the title: a new one, paused, alone",
            T.on_title(p) and back != hud and T.session(p) == gi)
    p.check("...on its Multiplayer page, the caret on Join Server, the reason "
            "still the session's and no server its",
            p.get(back, MV.MenuPage) == MC.PAGE_MULTI
            and p.get(back, MV.MenuRow) == MC.MULTI_JOIN_ROW
            and str(p.get(gi, S.NetReason)) == reason
            and str(p.get(gi, S.JoinAddress)) == "",
            f"page {p.get(back, MV.MenuPage)}, row {p.get(back, MV.MenuRow)}, "
            f"reason {str(p.get(gi, S.NetReason))!r}")
    p.check("the address typed is remembered: the join saved it to the settings",
            T.address(p) == DEAD_ADDRESS, T.address(p))

    # --- that title is a title: single player starts from it -------------------
    p.set(back, MV.MenuPage, PAGE_TITLE)        # BACK
    yield from T.take_row(p, C.START_ACTION,
                          lambda: p.get(back, MV.MenuPage) == MC.PAGE_SINGLE)
    yield from T.take_page_row(p, MC.SINGLE_START_ROW, lambda: T.in_play(p))
    p.check("from that title Single Player starts a game, alone and unpaused",
            T.in_play(p) and T.alone(p) and not T.paused(p),
            f"in play {T.in_play(p)}, paused {T.paused(p)}")
