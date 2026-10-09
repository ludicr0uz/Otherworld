"""Everyone who was started is in the game: the first check of a network run.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_join.py

On the server: one joined player per client, each possessing a pawn of its
own. On each client: it is a client of that server, its one local
controller possesses a pawn, and it has no title menu: it joined with the
server's address, and nothing on its command line skips the menu (the
harness gives a client no -nomenu), so that is the game's own rule
(graphics_menu/mode_tick.py). A pawn can arrive a moment after its controller,
so each side waits for it before it reports.
"""

SYSTEMS = ('net',)

import unreal

from graphics_menu.umg_consts import GAME_STARTED_VAR

RUNS_ON = ("server", "client")

PAWN_WAIT = 20.0    # wall seconds a pawn may take to follow its controller


def _pawn(controller):
    return controller.get_controlled_pawn() if controller else None


def _await(p, ready):
    """Yield until ``ready()``, or PAWN_WAIT wall seconds: the check that
    follows reports which, where a bare wait would time the whole probe out."""
    import time
    until = time.time() + PAWN_WAIT
    yield lambda: ready() or time.time() > until


def probe_server(p):
    yield from _await(p, lambda: len(p.players()) >= p.clients
                      and all(_pawn(c) for c in p.players()))
    players = p.players()
    pawns = [_pawn(c) for c in players]
    p.check(f"the server has {p.clients} joined player(s)", len(players) == p.clients,
            f"{len(players)} player controller(s)")
    p.check("each player possesses a pawn", players and all(pawns),
            ", ".join(f"{c.get_name()} -> {pawn.get_name() if pawn else 'no pawn'}"
                      for c, pawn in zip(players, pawns)))
    p.check("no two players share a pawn",
            len({pawn.get_name() for pawn in pawns if pawn}) == len(players),
            f"{len(pawns)} pawn(s)")
    p.check("the server is a dedicated server",
            unreal.SystemLibrary.is_dedicated_server(p.world()), p.where)


def probe_client(p):
    yield from _await(p, lambda: _pawn(p.controller()))
    controller = p.controller()
    pawn = _pawn(controller)
    p.check(f"{p.where} is a client of the server",
            not unreal.SystemLibrary.is_server(p.world()), p.net.address)
    p.check(f"{p.where} controls a pawn", bool(pawn),
            f"{controller.get_name() if controller else 'no controller'} -> "
            f"{pawn.get_name() if pawn else 'no pawn'}")
    p.check(f"{p.where}'s controller is its own", bool(controller)
            and controller.is_local_player_controller(), "local player controller")
    p.check(f"{p.where} sees one local player", len(p.players()) == 1,
            f"{len(p.players())} controller(s) on this client")
    yield from _await(p, lambda: p.hud() and p.get(p.hud(), GAME_STARTED_VAR))
    line = unreal.SystemLibrary.get_command_line()
    p.check(f"{p.where} skipped the title: in play, unpaused, with no -nomenu "
            f"on its command line",
            bool(p.hud()) and p.get(p.hud(), GAME_STARTED_VAR) is True
            and not unreal.GameplayStatics.is_game_paused(p.world())
            and "-nomenu" not in line,
            f"-nomenu given: {'-nomenu' in line}")
