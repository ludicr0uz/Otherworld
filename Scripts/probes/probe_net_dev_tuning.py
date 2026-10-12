"""The dev tabs by mode (M32): a client's gameplay tables are the server's, and
move only on a server started with -AllowDevTuning.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_dev_tuning.py
    python3 Scripts/dev/uepy.py --net --clients 2 --server-arg AllowDevTuning --probe Scripts/probes/probe_net_dev_tuning.py

One file, both cases: the server says which it is (its command line), and
every check after that is the case's own. Single player, where the tables
are the player's own as they always were, is probe_dev_tuning_single.py.

    the server      GameState.DevTuning is the switch, and each client has it
    client 1        the four gameplay tabs' hint lines, drawn by hand (a
                    -nullrhi client never draws): their own words where the
                    server allows tuning, READ_ONLY_HINT where it does not;
                    the sound tab's is its own either way
                    one nudge up on PLAYER SETTINGS' jog speed (the HUD's
                    TuneRow / TuneNudge written, a probe having no keyboard)
        refused     the cell, and the client's own speed, stay; AskTune sent
                    past the menu, as the wire carries it, is refused by the
                    server too
        allowed     the cell and the client's own speed move; the server's
                    tuner takes the table and every player's speed on the
                    server is the new one, client 2's as well; then the same
                    AskTune past the menu lands, which is what makes its
                    refusal above mean something
                    one nudge on the sound tab moves its cell in both cases:
                    that table is this machine's
"""

SYSTEMS = ('net', 'menu')

import time

import unreal

from combat.ask_consts import ASK_TUNE, TUNE_TABLES
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.player_tuning import JOG_SPEED, PLAYER_STATS, cms
from combat.sprint_tuning import BASE_SPEED_VAR
from graphics_menu import hud_vars as MV
from graphics_menu.game_tuner_consts import GAME_TUNER_CLASS_PATH, GAMEPLAY_TABS
from graphics_menu.player_tune_consts import PLAYER_TAB
from graphics_menu.sound_tune_consts import SOUND_TAB
from graphics_menu.tune_tab import READ_ONLY_HINT
from net import state_consts as S

RUNS_ON = ("server", "client")

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TABS = (*GAMEPLAY_TABS, SOUND_TAB)
WRITABLE = [(HUD_BP_PATH, v) for v in (
    MV.MenuOpen, *(t.open_var for t in TABS),
    *(v for t in (PLAYER_TAB, SOUND_TAB) for v in (t.row_var, t.nudge_var)))]

SWITCH = "-AllowDevTuning"
WAIT = 30.0             # wall seconds any one step may take
REFUSED_S = 3.0         # ... and how long a refusal is watched for a change
JOG = [s[0] for s in PLAYER_STATS].index(JOG_SPEED)
JOG_STEP = PLAYER_STATS[JOG][2]
CHEAT_MPS = 9.0         # the jog speed asked for past the menu


def _ask_past_menu(wc, cells):
    """AskTune(the player table, ``cells`` with CHEAT_MPS for the jog) as a
    client's wire sends it (Source/CLAUDE.md, SendServerEvent: call_method
    would run it here). Returns (the net driver took it, the table sent)."""
    table = cells[:JOG] + [CHEAT_MPS] + cells[JOG + 1:]
    took = unreal.OtherworldNetLibrary.send_server_event(
        wc, ASK_TUNE, [str(TUNE_TABLES.index(PLAYER_TAB.gameplay)),
                       "(" + ",".join(f"{v:.6f}" for v in table) + ")"])
    return took, table


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _speeds(p, pawns):
    return [round(float(p.get(p.component(a, WEAPON_COMP_CLASS_PATH), BASE_SPEED_VAR)), 2)
            for a in pawns]


def _cells(holder, tab):
    return [float(v) for v in holder.get_editor_property(tab.values_var)]


# ─── the server ─────────────────────────────────────────────────────────────

def probe_server(p):
    state = p.game_state()
    allowed = bool(p.get(state, S.DevTuning))
    asked = SWITCH.lower() in unreal.SystemLibrary.get_command_line().lower()
    p.check("the server's GameState.DevTuning is its -AllowDevTuning switch",
            allowed == asked, f"DevTuning {allowed}, switch {asked}")
    p.note("the server allows tuning" if allowed else "the server refuses tuning")
    tuner = p.component(state, GAME_TUNER_CLASS_PATH)
    pawns = [pc.get_controlled_pawn() for pc in p.players()]
    before, table = _speeds(p, pawns), _cells(tuner, PLAYER_TAB)
    p.check("every player has a pawn on the server, at one jog speed",
            len(pawns) == p.clients and len(set(before)) == 1, str(before))
    p.post("allowed", allowed)

    yield from _await(lambda: p.posted("client 1", "nudged") is not None)
    sent = p.posted("client 1", "nudged")
    if sent is None:
        p.check("client 1 nudged its player tab", False, "it never said so")
        return
    if allowed:
        want = round(cms(sent[JOG]), 2)
        yield from _await(lambda: _speeds(p, pawns) == [want] * len(pawns))
        p.check("allowed: the server's tuner took the client's player table",
                _cells(tuner, PLAYER_TAB) == sent, f"{_cells(tuner, PLAYER_TAB)} for {sent}")
        p.check("...and every player's jog speed on the server is the tuned one",
                _speeds(p, pawns) == [want] * len(pawns) and want != before[0],
                f"{before} -> {_speeds(p, pawns)}, wanted {want}")
        p.post("took")
        yield from _await(lambda: p.posted("client 1", "asked") is not None)
        cheat = round(cms(CHEAT_MPS), 2)
        yield from _await(lambda: _speeds(p, pawns) == [cheat] * len(pawns))
        p.check("...and an AskTune sent past the menu lands the same way",
                _speeds(p, pawns) == [cheat] * len(pawns), str(_speeds(p, pawns)))
        p.check("...its inbox emptied",
                all(len(p.get(state, var)) == 0 for var in S.TUNED))
    else:
        yield from _await(lambda: _speeds(p, pawns) != before, REFUSED_S)
        p.check("refused: no player's jog speed moved on the server, the menu's "
                "nudge and an AskTune sent past it alike",
                _speeds(p, pawns) == before, f"{before} -> {_speeds(p, pawns)}")
        p.check("...the tuner's table is as it was, and nothing waits in an inbox",
                _cells(tuner, PLAYER_TAB) == table
                and all(len(p.get(state, var)) == 0 for var in S.TUNED),
                str(_cells(tuner, PLAYER_TAB)))
    p.post("done")


# ─── the clients ────────────────────────────────────────────────────────────

def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, "UiPause") is not None else None


def _nudge(p, hud, tab, row, step):
    p.set(hud, tab.row_var, row)
    p.set(hud, tab.nudge_var, step)
    yield from _await(lambda: p.get(hud, tab.nudge_var) == 0)
    yield 0.2           # the next Tick's apply


def _hint(p, hud, tab):
    """The tab's hint line as DrawHUD leaves it with the tab open."""
    for other in TABS:
        p.set(hud, other.open_var, other is tab)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    words = str(p.get(hud, "UiPause").get_editor_property(tab.hint_widget).get_text())
    p.set(hud, tab.open_var, False)
    return words


def probe_client(p):
    yield from _await(lambda: p.posted("server", "allowed") is not None)
    allowed = p.posted("server", "allowed")
    if allowed is None:
        p.check("the server said whether it allows tuning", False)
        return
    case = "allowed" if allowed else "refused"
    yield from _await(lambda: p.game_state() is not None
                      and bool(p.get(p.game_state(), S.DevTuning)) == allowed)
    p.check(f"{case}: this client's GameState.DevTuning is the server's",
            bool(p.get(p.game_state(), S.DevTuning)) == allowed)
    if p.client != 1:
        yield from _await(lambda: p.posted("server", "done") is not None, 3 * WAIT)
        return

    yield from _await(lambda: _live_hud(p) is not None)
    hud = _live_hud(p)
    if hud is None:
        p.check("client 1 has its HUD", False)
        return
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)

    p.set(hud, MV.MenuOpen, True)
    for tab in GAMEPLAY_TABS:
        words = _hint(p, hud, tab)
        p.check(f"{case}: {tab.title_text}: the hint line "
                + ("is its own" if allowed else "says it is read-only, and why"),
                words == (tab.hint_text if allowed else READ_ONLY_HINT), repr(words))
    words = _hint(p, hud, SOUND_TAB)
    p.check(f"{case}: SOUND SETTINGS' hint line is its own", words == SOUND_TAB.hint_text,
            repr(words))
    p.set(hud, MV.MenuOpen, False)

    cells, speed = _cells(hud, PLAYER_TAB), float(p.get(wc, BASE_SPEED_VAR))
    yield from _nudge(p, hud, PLAYER_TAB, 1 + JOG, 1)
    after, now = _cells(hud, PLAYER_TAB), float(p.get(wc, BASE_SPEED_VAR))
    if allowed:
        want = cells[:JOG] + [cells[JOG] + JOG_STEP] + cells[JOG + 1:]
        p.check("allowed: one nudge up moves the jog speed's cell by its step",
                after == want, f"{cells} -> {after}")
        p.check("...and this client's own jog speed with it",
                abs(now - cms(after[JOG])) < 0.01 and now != speed, f"{speed} -> {now}")
    else:
        p.check("refused: one nudge up moves no cell of the player table",
                after == cells, f"{cells} -> {after}")
        p.check("...nor this client's jog speed, and the table is not touched",
                now == speed and not p.get(hud, PLAYER_TAB.touched_var), f"{speed} -> {now}")
        took, _table = _ask_past_menu(wc, cells)
        p.check("...and an AskTune past the menu leaves this client for the server", took)

    sound = _cells(hud, SOUND_TAB)
    yield from _nudge(p, hud, SOUND_TAB, 1, 1)
    if _cells(hud, SOUND_TAB) == sound:         # the first sound stood at its maximum
        yield from _nudge(p, hud, SOUND_TAB, 1, -1)
    moved = _cells(hud, SOUND_TAB)
    p.check(f"{case}: a nudge on the sound tab moves its cell here, as in single player",
            moved[0] != sound[0] and moved[1:] == sound[1:], f"{sound[0]} -> {moved[0]}")

    p.post("nudged", after)
    if allowed:
        yield from _await(lambda: p.posted("server", "took") is not None)
        took, _table = _ask_past_menu(wc, after)
        p.check("allowed: an AskTune past the menu leaves this client for the server", took)
        p.post("asked")
    yield from _await(lambda: p.posted("server", "done") is not None, 3 * WAIT)
    p.check("the server finished its side", p.posted("server", "done") is not None)

