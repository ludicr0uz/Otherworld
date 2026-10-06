"""A wanderer the player killed is counted on the player's PlayerState, and
the HUD's corner reads it there; one that died unshot is not counted.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_kill_credit.py

The single-player half of "where state lives" (net/state_consts.py): the
death graph (combat/death.py) writes NpcKillCount onto a PlayerState, behind
the authority switch, and nothing on the GameMode. probe_net_player_state.py
is the half with a server.

Whose PlayerState is the blow's instigator's (combat/damage.py), so the kill
here is a blow: the wanderer's TakeHit, naming the player's controller. The
death nobody caused is still Health written to 0, as the world-floor net does.
"""

import unreal

from combat import health_vars as HV
from combat.damage import TAKE_HIT
from combat.game_state import DAMAGED_BY_PLAYER_VAR, KILL_COUNT_VAR
from combat.paths import GAME_MODE_BP_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH
from graphics_menu import umg_consts as C
from graphics_menu.hud_stats import KILLS_PREFIX
from net.state_consts import GAME_STATE_CLASS_PATH, PLAYER_STATE_CLASS_PATH

WRITABLE = [(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, DAMAGED_BY_PLAYER_VAR)]


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls
             if "ForestWandererAI" in c.get_class().get_name()]
    return [x for x in pawns if x is not None
            and not p.get(p.component(x, HEALTH_CLASS_PATH), "Dead")]


def _kill(p, npc, by_player):
    health = p.component(npc, HEALTH_CLASS_PATH)
    if by_player:
        health.call_method(TAKE_HIT, (float(p.get(health, HV.Health)), unreal.Vector(1, 0, 0),
                                      p.controller(), p.pawn()))
    else:
        p.set(health, DAMAGED_BY_PLAYER_VAR, False)
        p.set(health, HV.Health, 0.0)
    yield lambda: p.get(health, "Dead")
    yield 0.3


def _corner(p):
    hud = p.hud()
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    return str(p.get(hud, "UiHud").get_editor_property(C.KILLS).get_text())


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    yield lambda: len(_wanderers(p)) >= 2
    mine, state, mode = p.player_state(), p.game_state(), p.game_mode()
    cls = lambda o: o.get_class().get_path_name() if o else None     # noqa: E731
    p.check("single player has the same PlayerState and GameState a server gives a "
            "client, and its GameMode",
            cls(mine) == PLAYER_STATE_CLASS_PATH and cls(state) == GAME_STATE_CLASS_PATH
            and bool(mode) and cls(mode).startswith(GAME_MODE_BP_PATH),
            f"{cls(mine)}, {cls(state)}, {cls(mode)}")
    p.check("the player starts with no kills", p.get(mine, KILL_COUNT_VAR) == 0
            and _corner(p) == f"{KILLS_PREFIX}0", _corner(p))

    shot, fell = _wanderers(p)[:2]
    yield from _kill(p, shot, True)
    p.check("a wanderer the player killed is one kill on the player's PlayerState",
            p.get(mine, KILL_COUNT_VAR) == 1, str(p.get(mine, KILL_COUNT_VAR)))
    p.check("...and the HUD's corner reads it there", _corner(p) == f"{KILLS_PREFIX}1",
            _corner(p))
    yield from _kill(p, fell, False)
    p.check("a wanderer that died unshot is nobody's kill",
            p.get(mine, KILL_COUNT_VAR) == 1 and _corner(p) == f"{KILLS_PREFIX}1",
            f"{p.get(mine, KILL_COUNT_VAR)}, '{_corner(p)}'")
