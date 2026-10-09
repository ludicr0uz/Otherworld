"""Each client's HUD reads its own state, off what the server replicates.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_player_state.py
    python3 Scripts/dev/uepy.py --net --clients 2 --windowed --probe <this>   # the engine draws the HUD

A client has no GameMode. What its HUD shows lives where it can read it
(net/state_consts.py): the kills and "is dead" on its own PlayerState, debug
mode on the GameState. The server writes a different kill count onto each
player's PlayerState, turns debug mode on, and then marks client 1 dead; each
client's HUD must show its own count, the shared flag, and the death menu on
client 1 alone.

The steps go round the board (probes/net.py):

    each client  "id"      its PlayerState's player id (the one name the
                           server and a client share for a player)
    server       "set"     the counts written, debug mode on
    each client  "seen"    its HUD's corner
    server       "dead"    client 1's PlayerDead written
    each client  "done"

With -nullrhi clients the probe calls DrawHUD itself (the engine draws none);
with --windowed the engine does, and "zero HUD errors" means something.
"""

SYSTEMS = ('net',)

import time

import unreal

from combat.game_state import DEBUG_MODE_VAR, KILL_COUNT_VAR, PLAYER_DEAD_VAR
from graphics_menu import hud_vars as MV
from graphics_menu import umg_consts as C
from graphics_menu.hud_stats import KILLS_PREFIX
from net.state_consts import (
    GAME_STATE_BP_PATH, GAME_STATE_CLASS_PATH, PLAYER_STATE_BP_PATH, PLAYER_STATE_CLASS_PATH)

RUNS_ON = ("server", "client")

WRITABLE = [(PLAYER_STATE_BP_PATH, KILL_COUNT_VAR), (PLAYER_STATE_BP_PATH, PLAYER_DEAD_VAR),
            (GAME_STATE_BP_PATH, DEBUG_MODE_VAR)]

WAIT = 30.0             # wall seconds any one step may take
SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE
DEAD_CLIENT = 1


def kills_of(client):
    """What the server gives client ``client``: no two alike, none zero."""
    return 10 * client + 3


def _await(ready, seconds=WAIT):
    """Yield until ``ready()`` or ``seconds`` of wall time: the check after it
    says which, where a bare wait would time the whole probe out."""
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _is(obj, class_path):
    return bool(obj) and obj.get_class().get_path_name() == class_path


def _client_names(p):
    return [f"client {i}" for i in range(1, p.clients + 1)]


# ─── The server ──────────────────────────────────────────────────────────────

def probe_server(p):
    names = _client_names(p)
    yield from _await(lambda: len(p.players()) >= p.clients
                      and all(p.posted(n, "id") is not None for n in names))
    states = {c.player_state.player_id: c.player_state
              for c in p.players() if c.player_state}
    ids = {n: p.posted(n, "id") for n in names}
    p.check("the server holds a BP_OtherworldPlayerState for each client, found by "
            "the player id the client posted",
            len(states) == p.clients and all(i in states for i in ids.values())
            and all(_is(s, PLAYER_STATE_CLASS_PATH) for s in states.values()),
            f"posted {ids}; the server's {sorted(states)}")
    mode, state = p.game_mode(), p.game_state()
    p.check("the server has the GameMode, and its GameState is BP_OtherworldGameState",
            bool(mode) and _is(state, GAME_STATE_CLASS_PATH),
            f"{mode.get_name() if mode else None}, {state.get_name() if state else None}")
    if not all(i in states for i in ids.values()) or not state:
        return
    for client, name in enumerate(names, 1):
        p.set(states[ids[name]], KILL_COUNT_VAR, kills_of(client))
    p.set(state, DEBUG_MODE_VAR, True)
    p.post("set", {n: kills_of(i) for i, n in enumerate(names, 1)})

    yield from _await(lambda: all(p.posted(n, "seen") is not None for n in names))
    p.check("every client reported its HUD's corner",
            all(p.posted(n, "seen") is not None for n in names),
            str({n: p.posted(n, "seen") for n in names}))
    p.set(states[ids[f"client {DEAD_CLIENT}"]], PLAYER_DEAD_VAR, True)
    p.post("dead")
    yield from _await(lambda: all(p.posted(n, "done") is not None for n in names))
    p.check("every client finished", all(p.posted(n, "done") is not None for n in names))


# ─── A client ────────────────────────────────────────────────────────────────

def _drawn(hud):
    """One HUD frame. A -nullrhi client draws none of its own, so the probe
    calls the event; a rendered one is given the time to draw."""
    if "-nullrhi" in unreal.SystemLibrary.get_command_line().lower():
        hud.call_method("ReceiveDrawHUD", (1920, 1080))
    yield 0.3


def _corner(p, hud):
    return str(p.get(hud, "UiHud").get_editor_property(C.KILLS).get_text())


def probe_client(p):
    yield from _await(lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
                      and _is(p.player_state(), PLAYER_STATE_CLASS_PATH)
                      and _is(p.game_state(), GAME_STATE_CLASS_PATH))
    hud, mine, state = p.hud(), p.player_state(), p.game_state()
    p.check(f"{p.where} has no GameMode, and has its own BP_OtherworldPlayerState and "
            f"the BP_OtherworldGameState",
            p.game_mode() is None and _is(mine, PLAYER_STATE_CLASS_PATH)
            and _is(state, GAME_STATE_CLASS_PATH),
            f"GameMode {p.game_mode()}, {mine.get_name() if mine else None}, "
            f"{state.get_name() if state else None}")
    if not hud or not mine or not state:
        return
    yield from _await(lambda: p.get(hud, C.GAME_STARTED_VAR))
    p.post("id", mine.player_id)

    want = kills_of(p.client)
    yield from _await(lambda: p.posted("server", "set") is not None
                      and p.get(mine, KILL_COUNT_VAR) == want
                      and p.get(state, DEBUG_MODE_VAR))
    p.check(f"{p.where}'s PlayerState holds the count the server gave it ({want})",
            p.get(mine, KILL_COUNT_VAR) == want, str(p.get(mine, KILL_COUNT_VAR)))
    yield from _drawn(hud)
    corner = _corner(p, hud)
    p.check(f"{p.where}'s HUD reads its own kill count: '{KILLS_PREFIX}{want}'",
            corner == f"{KILLS_PREFIX}{want}", f"'{corner}'")
    yield from _await(lambda: len(state.player_array) >= p.clients)
    others = {s.player_id: p.get(s, KILL_COUNT_VAR)
              for s in state.player_array if s and s != mine}
    p.check(f"{p.where} sees the other players' counts too, each its own and none "
            f"of them the one its HUD shows",
            len(others) == p.clients - 1 and want not in others.values()
            and all(v in [kills_of(i) for i in range(1, p.clients + 1)]
                    for v in others.values()), str(others))
    p.check(f"{p.where}'s HUD has the server's debug mode, off the GameState",
            p.get(state, DEBUG_MODE_VAR) is True and p.get(hud, MV.DebugOn) is True,
            f"GameState {p.get(state, DEBUG_MODE_VAR)}, HUD {p.get(hud, MV.DebugOn)}")
    p.post("seen", corner)

    # --- "is dead" is one player's: client DEAD_CLIENT's alone ----------------
    dying = p.client == DEAD_CLIENT
    yield from _await(lambda: p.posted("server", "dead") is not None
                      and (p.get(mine, PLAYER_DEAD_VAR) or not dying))
    yield 1.0           # long enough for a flag that was not meant for us to arrive
    yield from _drawn(hud)
    death = p.get(hud, "UiDeath")
    up = death.get_visibility() == SHOWN
    if dying:
        score = str(death.get_editor_property(C.DEATH_SCORE).get_text())
        p.check(f"{p.where} is dead on its PlayerState, and its HUD draws the death "
                f"menu with its own score",
                p.get(mine, PLAYER_DEAD_VAR) is True and up
                and score == f"{C.DEATH_SCORE_PREFIX}{want}",
                f"PlayerDead {p.get(mine, PLAYER_DEAD_VAR)}, menu up {up}, '{score}'")
    else:
        p.check(f"{p.where} is not dead: another player's death is not its own, and "
                f"its HUD plays on",
                p.get(mine, PLAYER_DEAD_VAR) is False and not up,
                f"PlayerDead {p.get(mine, PLAYER_DEAD_VAR)}, menu up {up}")
    p.post("done")
