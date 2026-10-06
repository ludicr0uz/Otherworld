"""A dead player's respawn, where death is not the end of the game: on a
server. Standalone never reaches it (death.py: its death pauses the world,
deletes the profile and goes back to the title, the mode table's death row).

    not standalone --> the server (the GameMode behind its switch)
        --> Delay(PlayerRespawnWait) --> RespawnFor = the body's controller,
                                         if it has one
        --> its PlayerState's PlayerDead = false
        --> UnPossess --> the GameMode: RestartPlayerAtPlayerStart(controller,
                              a random one of the level's PlayerStarts)
        --> the body: CORPSE_SECONDS of lifespan

The body is not destroyed and not reused: the controller lets go of it and
is given a new pawn, so the corpse lies where it fell, holding what the
player carried (weapon_component/shed.py put it there), and the new pawn's
own BeginPlay issues the starting inventory on every machine, as a first
join's does. The health component is the body's, so the wait is a latent
action on a component that outlives it: the lifespan is given only after
the respawn.

UnPossess first: RestartPlayerAtPlayerStart spawns no pawn for a controller
that still has one. And not RestartPlayer: GameModeBase sends a controller
back to its StartSpot, always the start it first spawned at.

The start is drawn once (the random index is pure and has one reader), on
the server, among every PlayerStart in the level. A level with none falls
back on RestartPlayer, the engine's own choice.
"""

from combat import health_vars as HV
from combat.death import CORPSE_SECONDS
from combat.game_state import PLAYER_DEAD_VAR
from net.state_consts import PLAYER_STATE_CLASS_PATH
from net.state_graph import CONTROLLER_CLASS_PATH, player_state_of, server_game_mode
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _palette, _pin, out, then
from uebp.nodes.actor import (
    FN_GET_CONTROLLER, FN_GET_OWNER, FN_LIFESPAN, FN_RESTART_AT_START, FN_RESTART_PLAYER,
    FN_UNPOSSESS)
from uebp.nodes.array import FN_ARR_GET, FN_ARR_LEN
from uebp.nodes.math import FN_GE_II, FN_RAND_INT, FN_SUB_II
from uebp.nodes.palette import NODE_CAST_PAWN
from uebp.nodes.system import FN_ALL_ACTORS, FN_DELAY, FN_IS_VALID

PLAYER_START_CLASS_PATH = "/Script/Engine.PlayerStart"


def author_player_respawn(ed, exec_ins):
    """The respawn (see the module docstring). ``exec_ins``: the death path's
    exits outside standalone, on any machine."""
    g = _G(ed)
    server = server_game_mode(ed, exec_ins)
    g.made.extend(server.nodes)
    wait = g.call(FN_DELAY, [server.then], Duration=g.get(HV.PlayerRespawnWait))

    body = out(g.call(FN_GET_OWNER))
    as_pawn = g.keep(_palette(ed, NODE_CAST_PAWN))
    _connect(body, _pin(as_pawn, "Object"))
    _connect(then(wait), _pin(as_pawn, "execute"))
    # Kept in a variable: GetController is pure, asked again at every read,
    # and answers None once the controller has let go of the body.
    kept = g.put(HV.RespawnFor, out(g.call(
        FN_GET_CONTROLLER, self=_loose_pin(as_pawn, "AsPawn", is_input=False))), [then(as_pawn)])
    who = g.get(HV.RespawnFor)
    # A player who left the server while dead has no controller to respawn.
    here, gone = g.branch(out(g.call(FN_IS_VALID, Object=who)), [kept])

    state = player_state_of(ed, who, CONTROLLER_CLASS_PATH, [here])
    g.made.extend(state.nodes)
    alive = g.iput(state.pin, PLAYER_DEAD_VAR, "false", [state.then], PLAYER_STATE_CLASS_PATH)

    starts = g.call(FN_ALL_ACTORS, [alive, *state.fails])
    _pin(starts, "ActorClass").set_pin_value(PLAYER_START_CLASS_PATH)
    spots = out(starts, "OutActors")
    free = g.call(FN_UNPOSSESS, [then(starts)], self=who)
    count = g.call(FN_ARR_LEN, TargetArray=spots)
    some, none = g.branch(out(g.call(FN_GE_II, A=out(count), B=1)), [then(free)])
    last = g.call(FN_SUB_II, A=out(count), B=1)
    draw = g.call(FN_RAND_INT, Max=out(last))      # Min is the pin's own 0
    spot = g.call(FN_ARR_GET, TargetArray=spots, Index=out(draw))
    at_start = g.call(FN_RESTART_AT_START, [some], self=server.pin, NewPlayer=who,
                      StartSpot=out(spot, "Item"))
    anywhere = g.call(FN_RESTART_PLAYER, [none], self=server.pin, NewPlayer=who)

    g.call(FN_LIFESPAN, [then(at_start), then(anywhere), gone], self=body,
           InLifespan=str(CORPSE_SECONDS))
    ed.add_comment_to_nodes(
        "A dead player on a server (never in standalone): after PlayerRespawnWait the "
        "controller lets go of the body and the GameMode gives it a new pawn at a random "
        "PlayerStart, with the starting inventory its BeginPlay issues. PlayerDead is "
        f"lowered, and the body lies {CORPSE_SECONDS:.0f} s more, holding what the player "
        "carried (player_respawn.py).", g.made)
