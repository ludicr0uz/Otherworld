"""Who is nearby is asked of every living player, never of player 0.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_living_players.py
    python3 Scripts/dev/uepy.py --game --probe <this>     # single player: one player

The world's own actors and the wanderers ask BPL_Players (net/players.py)
instead of GetPlayerPawn(0). Where the graphs run, the server and a
single-player game, this calls the library's two functions and watches one
actor that uses them:

  - LivingPlayers is every player's pawn, one per player;
  - NearestLivingPlayer, asked at each player's own place, is that player
    (on a server the second player is as near to themselves as the first);
  - a player whose PlayerState says PlayerDead is not living: asked at their
    place, the nearest is another player, or no one when there is none;
  - the night's cold (world/night_cold.py) falls on every player: at midnight
    each one's Temperature drops, the second player's as well as player 0's,
    and a dead player's holds.

Nothing spawns here, so the campfire, the ammunition box and a dead
wanderer's replacement are held by the verifiers' checks of their graphs.
"""

SYSTEMS = ('net',)

import unreal

from net import players_consts as P
from net import state_consts as S
from survival import component_vars as UV
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from world import world_config as cfg
from world.day_night_blueprint import NIGHT_COLD_VAR
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world import day_night_vars as DV

RUNS_ON = ("server", "standalone")

WRITABLE = [(DAY_NIGHT_BP_PATH, DV.Clock), (DAY_NIGHT_BP_PATH, NIGHT_COLD_VAR),
            (S.PLAYER_STATE_BP_PATH, S.Dead), (SURVIVAL_BP_PATH, UV.Temperature)]

RATE = 20.0
SETTLE = 0.1
WATCH = 0.3
WARM = 80.0             # a Temperature with room to fall


def _library(p):
    return unreal.get_default_object(p.load_class(P.PLAYERS_CLASS_PATH))


def _living(p):
    return list(_library(p).call_method(P.LIVING_FN, (p.world(),)))


def _nearest(p, point):
    return _library(p).call_method(P.NEAREST_FN, (point, p.world()))


def _name(a):
    return a.get_name() if a else "no one"


def probe(p):
    yield lambda: all(c.get_controlled_pawn() for c in p.players())
    yield 0.3
    pawns = [c.get_controlled_pawn() for c in p.players()]
    states = [c.player_state for c in p.players()]
    count = max(p.clients, 1)

    living = _living(p)
    p.check(f"LivingPlayers is every player's pawn: {count}",
            len(pawns) == count and len(living) == count
            and {a.get_name() for a in living} == {a.get_name() for a in pawns},
            f"{[_name(a) for a in living]} of {[_name(a) for a in pawns]}")
    own = [_nearest(p, a.get_actor_location()) for a in pawns]
    p.check("NearestLivingPlayer, asked at each player's place, is that player",
            all(got and got.get_name() == a.get_name() for got, a in zip(own, pawns)),
            f"{[_name(a) for a in own]}")

    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    survivals = [p.component(a, SURVIVAL_CLASS_PATH) for a in pawns]
    p.set(cycle, NIGHT_COLD_VAR, RATE)
    p.set(cycle, "Clock", cfg.DAY_LENGTH_S + cfg.NIGHT_LENGTH_S / 2)
    yield SETTLE
    for s in survivals:
        p.set(s, "Temperature", WARM)
    yield WATCH
    lost = [WARM - p.get(s, "Temperature") for s in survivals]
    p.check("midnight: the cold falls on every player, not on player 0 alone",
            all(x > 0 for x in lost), f"lost {[round(x, 3) for x in lost]}")

    # The last player dies (their PlayerState says so, as combat/death.py writes it).
    p.set(states[-1], S.Dead, True)
    yield SETTLE
    living = _living(p)
    there = _nearest(p, pawns[-1].get_actor_location())
    others = pawns[:-1]
    p.check("a player whose PlayerState says PlayerDead is not living",
            {a.get_name() for a in living} == {a.get_name() for a in others},
            f"{[_name(a) for a in living]}")
    p.check("...asked at their place, the nearest is another player"
            + ("" if others else ": no one, there being no other"),
            (there is None) if not others
            else bool(there) and there.get_name() in {a.get_name() for a in others},
            _name(there))
    for s in survivals:
        p.set(s, "Temperature", WARM)
    yield WATCH
    lost = [WARM - p.get(s, "Temperature") for s in survivals]
    p.check("...and the cold falls on the living only",
            lost[-1] == 0.0 and all(x > 0 for x in lost[:-1]),
            f"lost {[round(x, 3) for x in lost]}")
    p.set(states[-1], S.Dead, False)
    p.set(cycle, NIGHT_COLD_VAR, cfg.NIGHT_TEMPERATURE_DROP_PER_S)
