"""Each client's HUD bars follow its own character, not player 0's.

    python3 Scripts/dev/uepy.py --net --clients 2 --windowed --probe Scripts/probes/probe_net_hud_own_pawn.py
    python3 Scripts/dev/uepy.py --net --clients 2 --probe <this>   # -nullrhi: the probe draws the HUD

The HUD asks for its owning pawn (``FN_GET_OWNING_PAWN``), never
GetPlayerPawn(0). Each client holds two characters, its own and the other
player's. It writes health, hunger and stamina onto both, a share of its own
on its own (no two clients alike) and another on the other's, and its bars
must show its own.

Health and hunger do not replicate yet (M14, M26), so each client writes
its own copies of those. Stamina is the server's (M12: the movement
component, combat/player_move.py; the weapon component's Stamina on the
owning client is a copy of it), so the server writes each player's, and
holds it there, and it reaches that client's bar as a correction. What the check
cannot show on a client is the old fault itself: a client has one controller,
so its player 0 is its own player. The rule is held by the verifier
(net/owner_checks.py); this is the positive case, on a real client's screen.
"""

import time

import unreal

from combat import health_vars as HV
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.weapon_component import vars as WV
from graphics_menu import umg_consts as C
from survival import component_vars as UV
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH

RUNS_ON = ("server", "client")

WRITABLE = [(HEALTH_BP_PATH, HV.Health), (SURVIVAL_BP_PATH, UV.Hunger),
            (WEAPON_COMP_BP_PATH, WV.Stamina)]

WAIT = 30.0             # wall seconds any one step may take
OTHERS = 0.95           # the share written onto the other player's character
NEAR = 0.01
# The client predicts a refill the server (which holds the bar still for this
# run) corrects, so its bar stands a little over the server's.
STAMINA_NEAR = 0.2
MOVE = unreal.OtherworldMovementLibrary


def share_of(client):
    """The share of each bar client ``client`` gives its own character: no
    two alike, none full and none near ``OTHERS``."""
    return 0.2 * client


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _drawn(hud):
    """One HUD frame. A -nullrhi client draws none of its own, so the probe
    calls the event; a rendered one is given the time to draw."""
    if "-nullrhi" in unreal.SystemLibrary.get_command_line().lower():
        hud.call_method("ReceiveDrawHUD", (1920, 1080))
    yield 0.3


def _characters(p, mine):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), mine.get_class())
            if a != mine]


def _write(p, pawn, share):
    health = p.component(pawn, HEALTH_CLASS_PATH)
    survival = p.component(pawn, SURVIVAL_CLASS_PATH)
    weapon = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    p.set(health, HV.Health, share * p.get(health, HV.MaxHealth))
    p.set(survival, UV.Hunger, share * p.get(survival, UV.MaxHunger))
    p.set(weapon, WV.Stamina, share * p.get(weapon, WV.MaxStamina))
    return round(p.get(health, HV.Health))


def _player_id(pawn):
    state = pawn.get_editor_property("player_state") if pawn else None
    # The id the server gave the player, replicated: the same on both machines.
    return state.get_editor_property("player_id") if state else None


def probe_server(p):
    """Give each player the stamina its client expects, and hold it there."""
    yield from _await(lambda: len(p.players()) >= p.clients
                      and all(c.get_controlled_pawn() for c in p.players()))
    pawns = [c.get_controlled_pawn() for c in p.players()]
    names = [f"client {i}" for i in range(1, p.clients + 1)]
    yield from _await(lambda: all(p.posted(n, "player id") is not None for n in names))
    whose = {p.posted(n, "player id"): i for i, n in enumerate(names, 1)}
    written = []
    for pawn in pawns:
        client, move = whose.get(_player_id(pawn)), MOVE.get_otherworld_movement(pawn)
        if client is None or move is None:
            continue
        p.set(move, "stamina_regen_per_second", 0.0)
        MOVE.set_stamina(pawn, share_of(client) * move.get_editor_property("max_stamina"))
        written.append(client)
    p.check("the server wrote each player's stamina: it is the server's to write",
            sorted(written) == list(range(1, p.clients + 1)), f"{written} of {whose}")
    p.post("stamina")
    yield from _await(lambda: all(p.posted(n, "bars") is not None for n in names))


def probe_client(p):
    yield from _await(lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
                      and p.pawn() is not None)
    hud, mine = p.hud(), p.pawn()
    if not hud or not mine:
        p.check(f"{p.where} has a HUD and a pawn", False, f"{hud}, {mine}")
        return
    yield from _await(lambda: _player_id(mine) is not None)
    p.post("player id", _player_id(mine))
    yield from _await(lambda: p.get(hud, C.GAME_STARTED_VAR)
                      and len(_characters(p, mine)) >= p.clients - 1)
    others = _characters(p, mine)
    p.check(f"{p.where} holds the other players' characters beside its own, and its "
            f"HUD's owning pawn is its own",
            len(others) == p.clients - 1 and hud.get_owning_pawn() == mine,
            f"own {mine.get_name()}, others {[a.get_name() for a in others]}, "
            f"owning {hud.get_owning_pawn().get_name() if hud.get_owning_pawn() else None}")

    want = share_of(p.client)
    for other in others:
        _write(p, other, OTHERS)
    hp = _write(p, mine, want)
    # Its own stamina is the server's write, arriving as a correction.
    move = MOVE.get_otherworld_movement(mine)
    full = move.get_editor_property("max_stamina")
    yield from _await(lambda: p.posted("server", "stamina")
                      and move.get_editor_property("stamina") < (want + STAMINA_NEAR) * full)
    yield from _drawn(hud)
    ui = p.get(hud, "UiHud")
    bar = ui.get_editor_property(C.HP_BAR).get_editor_property("percent")
    num = str(ui.get_editor_property(C.HP_NUM).get_text())
    food = ui.get_editor_property(C.stat_bar("Hunger")).get_editor_property("percent")
    run = ui.get_editor_property(C.STAMINA_BAR).get_editor_property("percent")
    p.check(f"{p.where}'s HP bar and number are its own character's ({want:.0%}, {hp}), "
            f"not the other's ({OTHERS:.0%})",
            abs(bar - want) < NEAR and num == str(hp), f"bar {bar:.2f}, '{num}'")
    p.check(f"{p.where}'s hunger bar is its own character's ({want:.0%})",
            abs(food - want) < NEAR, f"{food:.2f}")
    p.check(f"{p.where}'s stamina bar is its own character's (from {want:.0%}, refilling), "
            f"not the other's ({OTHERS:.0%})",
            want - NEAR < run < want + STAMINA_NEAR, f"{run:.2f}")
    p.post("bars", [round(bar, 2), round(food, 2)])

    # --- and the other client's bars are not these ----------------------------
    names = [f"client {i}" for i in range(1, p.clients + 1) if i != p.client]
    yield from _await(lambda: all(p.posted(n, "bars") is not None for n in names))
    theirs = {n: p.posted(n, "bars") for n in names}
    p.check(f"{p.where}'s bars are not another client's: each screen is about its "
            f"own character",
            all(v is not None and v != [round(bar, 2), round(food, 2)]
                for v in theirs.values()), f"own {[round(bar, 2), round(food, 2)]}, {theirs}")
