"""A menu on a client is an overlay: the shared world does not stop for it.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_menu_overlay.py

Client 1 opens the M menu. While it is open the server's world time keeps
advancing (and so does the client's own: neither is paused), and the menu
holds client 1's character still, on the client and on the server. Then the
title, which is the same menu held open: its first row starts the game with
the world still running, and gives the walk back. Shut, the character walks
again and the server sees it go. Pausing is single player's alone
(`net/pause.py`; `probe_main_menu.py` is that half).

No key can be pressed here: M flips MenuOpen, so the probe writes it, and a
row is taken by writing PauseClick, as `probe_menu_cursor.py` does.

The fire press is held by DrawHUD while the cursor shows
(`cursor.author_hold_fire`), and a -nullrhi client never draws: that check is
made only where the HUD is drawn (`--windowed`), and noted as not made
otherwise.

The steps go round the board (probes/net.py):

    client 1   "menu-open"   where its character stands
    server     "ran"         its world time at both ends of the wait
    client 1   "started"     the title's first row taken
    client 1   "walked"      where it stopped, the menu shut
    server     "saw-walk"
"""

import time

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu import cursor_consts as CC
from graphics_menu.mode_consts import SINGLE, SINGLE_START_ROW
from graphics_menu import hud_vars as MV
from graphics_menu import umg_consts as C

RUNS_ON = ("server", "client")

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (MV.MenuOpen, C.GAME_STARTED_VAR, CC.PAUSE_CLICK_VAR,
                                       MV.MenuPage, CC.PAGE_CLICK_VAR)]
WRITABLE += [(WEAPON_COMP_BP_PATH, CC.TRIGGER_SPENT_VAR)]

WAIT = 30.0             # wall seconds any one step may take
UNDER_MENU_S = 1.5      # wall seconds the menu stays open while the clocks are read
RAN_MIN_S = 0.75        # ... and the least game time that must pass in them
STILL_CM = 10.0         # a held character moves less than this
WALK_CM = 300.0         # how far the freed character walks
WALK_MIN_CM = 150.0     # ... and the least that counts as having walked
NEAR_CM = 60.0          # two machines agree on a place within this


def _await(ready, seconds=WAIT):
    """Yield until ``ready()`` or ``seconds`` of wall time: the check after it
    says which, where a bare wait would time the whole probe out."""
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _xyz(actor):
    v = actor.get_actor_location()
    return [v.x, v.y, v.z]


def _flat(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _paused(p):
    return unreal.GameplayStatics.is_game_paused(p.world())


def _push(p, me, seconds):
    """Walk input every frame for ``seconds``, as a held key gives it. Returns
    how far the character went."""
    start = _xyz(me)
    forward = me.get_actor_forward_vector()

    def pushing():
        me.add_movement_input(forward, 1.0)
        return _flat(_xyz(me), start) >= WALK_CM
    yield from _await(pushing, seconds)
    return _flat(_xyz(me), start)


def _nearest(p, place):
    """The server's character for the client that posted ``place``: join order
    says nothing, so it is the one standing there."""
    pawns = [c.get_controlled_pawn() for c in p.players()]
    return min((a for a in pawns if a), key=lambda a: _flat(_xyz(a), place), default=None)


def probe_server(p):
    yield from _await(lambda: p.posted("client 1", "menu-open"))
    place = p.posted("client 1", "menu-open")
    p.check("the server hears client 1 open its menu", bool(place))
    if not place:
        return
    who = _nearest(p, place)
    t0, w0 = _now(p), time.time()
    yield from _await(lambda: False, UNDER_MENU_S)
    t1, wall = _now(p), time.time() - w0
    p.check("the server's world time keeps advancing while a client's menu is open",
            t1 - t0 >= RAN_MIN_S, f"{t1 - t0:.2f} game s in {wall:.2f} wall s")
    p.check("...and the server's world is not paused", not _paused(p))
    p.check("...and that client's character stands still on the server",
            bool(who) and _flat(_xyz(who), place) < STILL_CM,
            f"{_flat(_xyz(who), place):.0f} cm from where it stood" if who else "no pawn")
    p.post("ran", [t0, t1])

    yield from _await(lambda: p.posted("client 1", "walked"))
    stopped = p.posted("client 1", "walked")
    yield from _await(lambda: bool(stopped) and bool(who)
                      and _flat(_xyz(who), stopped) < NEAR_CM, 5.0)
    p.check("the menu shut, the server sees the character walk again",
            bool(stopped) and bool(who) and _flat(_xyz(who), stopped) < NEAR_CM
            and _flat(stopped, place) >= WALK_MIN_CM,
            f"{_flat(_xyz(who), stopped):.0f} cm from where the client stopped, "
            f"{_flat(stopped, place):.0f} cm from the menu" if stopped and who else "nothing posted")
    p.post("saw-walk")


def _client_one(p, me, hud, pc):
    wc = p.component(me, WEAPON_COMP_CLASS_PATH)
    p.check(f"{p.where}: in play no menu is open and the walk is free",
            not p.get(hud, MV.MenuOpen) and not pc.is_move_input_ignored())

    # --- M: the menu, over a running world ----------------------------------
    p.set(hud, MV.MenuOpen, True)
    yield from _await(pc.is_move_input_ignored, 5.0)
    p.check(f"{p.where} opens the M menu: it takes the walk",
            p.get(hud, MV.MenuOpen) and pc.is_move_input_ignored())
    place = _xyz(me)
    p.post("menu-open", place)
    t0, w0 = _now(p), time.time()
    went = yield from _push(p, me, UNDER_MENU_S)
    t1, wall = _now(p), time.time() - w0
    p.check("...over a running world: the client's own time advances",
            t1 - t0 >= RAN_MIN_S, f"{t1 - t0:.2f} game s in {wall:.2f} wall s")
    p.check("...and the client is not paused", not _paused(p))
    p.check("...and the character takes no movement input while the menu is open",
            went < STILL_CM, f"{went:.1f} cm under {UNDER_MENU_S}s of walk input")
    if p.get(hud, CC.CURSOR_SHOWN_VAR):
        p.check("...nor fire input: the shown cursor keeps the fire press spent",
                p.get(wc, CC.TRIGGER_SPENT_VAR) is True, str(p.get(wc, CC.TRIGGER_SPENT_VAR)))
    else:
        p.note("the fire press's hold is DrawHUD's and this client draws no HUD: "
               "not checked here (run --windowed)")
    yield from _await(lambda: p.posted("server", "ran"))
    p.check("the server ran on under the open menu", bool(p.posted("server", "ran")),
            str(p.posted("server", "ran")))

    # --- the title: the same menu held open, and its first row --------------
    # A connected client has no title (mode_tick.py): this holds one up by
    # hand, as M5 did, to show the menu's own graph pauses nothing there.
    p.set(hud, C.GAME_STARTED_VAR, False)
    yield from _await(lambda: False, 0.3)
    p.check("the title on a client pauses nothing either",
            not _paused(p) and pc.is_move_input_ignored(), f"paused: {_paused(p)}")
    p.set(hud, CC.PAUSE_CLICK_VAR, C.PAUSE_START_ROW)
    yield from _await(lambda: p.get(hud, MV.MenuPage) == SINGLE.page, 5.0)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.set(hud, CC.PAGE_CLICK_VAR, SINGLE_START_ROW)
    yield from _await(lambda: p.get(hud, C.GAME_STARTED_VAR), 5.0)
    p.set(hud, CC.PAGE_CLICK_VAR, CC.NO_ROW)
    yield from _await(lambda: not pc.is_move_input_ignored(), 5.0)
    t2 = _now(p)
    yield from _await(lambda: False, 0.5)
    p.check("its first row, then the page's, start the game: the menu shut, the walk given back",
            p.get(hud, C.GAME_STARTED_VAR) and not p.get(hud, MV.MenuOpen)
            and not pc.is_move_input_ignored())
    p.check("...into a world that never stopped", not _paused(p) and _now(p) > t2,
            f"{_now(p) - t2:.2f} game s in the next half second")
    p.post("started")

    # --- shut: the character is the player's again --------------------------
    went = yield from _push(p, me, 12.0)
    yield from _await(lambda: False, 0.5)
    stopped = _xyz(me)
    p.check("the menu shut, the character walks", _flat(stopped, place) >= WALK_MIN_CM,
            f"{_flat(stopped, place):.0f} cm")
    p.post("walked", stopped)
    yield from _await(lambda: p.posted("server", "saw-walk"))
    p.check("the server saw it walk", bool(p.posted("server", "saw-walk")))


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None and p.hud() is not None)
    yield from _await(lambda: False, 0.5)
    me, hud, pc = p.pawn(), p.hud(), p.controller()
    p.check(f"{p.where} has its character and its HUD", bool(me) and bool(hud))
    if not (me and hud):
        return
    if p.client == 1:
        yield from _client_one(p, me, hud, pc)
        return
    # Everyone else only plays on: their world runs while client 1's menu is up.
    yield from _await(lambda: p.posted("client 1", "menu-open"))
    t0 = _now(p)
    yield from _await(lambda: p.posted("server", "ran"))
    p.check(f"{p.where} plays on while client 1's menu is open",
            not _paused(p) and _now(p) > t0, f"{_now(p) - t0:.2f} game s")
