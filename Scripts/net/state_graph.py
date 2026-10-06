"""How a graph reaches state: the casts every reader and writer shares.

Each fragment returns a ``Got``: the typed object pin, the exec to go on
from when it is there, the exec pins for when it is not, and the nodes made
(for a caller's comment box). Read the object only down ``then``: a client
has no PlayerState or GameState for its first frames, and a Get through a
failed cast is an "Accessed None".

    game_state          the world's shared state, on any machine
    owned_game_state    the same, where this machine may write it
    player_state_of     a controller's or a pawn's player state
    owner_player_state  a component's: its owning pawn's
    first_player_state  player 0's (see the note on it)
    server_game_mode    the GameMode, behind the authority switch: the one
                        way a graph that can run on a client reaches it
                        (state_checks.check_no_client_game_mode)
"""

from collections import namedtuple

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from uebp.nodes.actor import FN_GET_OWNER, FN_HAS_AUTHORITY
from uebp.nodes.palette import (
    MACRO_SWITCH_AUTHORITY, MACRO_SWITCH_AUTHORITY_COMP, NODE_CAST_GAME_MODE,
    NODE_CAST_GAME_STATE, NODE_CAST_PAWN, NODE_CAST_PLAYER_STATE)
from uebp.nodes.system import FN_GET_GAME_MODE, FN_GET_GAME_STATE, FN_GET_PLAYER_STATE

Got = namedtuple("Got", "pin then fails nodes")

PAWN_CLASS_PATH = "/Script/Engine.Pawn"
CONTROLLER_CLASS_PATH = "/Script/Engine.Controller"
PLAYER_STATE_PROP = "PlayerState"


def _cast(ed, palette, as_name, source, in_execs):
    cast = _palette(ed, palette)
    _connect(source, _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    return cast, _loose_pin(cast, as_name, is_input=False)


def game_state(ed, in_execs, world=None):
    """GetGameState, cast to BP_OtherworldGameState. ``world``: a world
    context pin, for a graph that has to name one (an ability)."""
    get = _node(ed, FN_GET_GAME_STATE)
    if world is not None:
        _connect(world, _pin(get, "WorldContextObject"))
    cast, pin = _cast(ed, NODE_CAST_GAME_STATE, "AsBPOtherworldGameState", out(get), in_execs)
    return Got(pin, then(cast), [out(cast, "CastFailed")], [get, cast])


def owned_game_state(ed, in_execs):
    """The game state where this machine has authority over it (the server,
    and single player): the only place a write to it means anything. A
    client's copy is the server's to change."""
    got = game_state(ed, in_execs)
    owns = _node(ed, FN_HAS_AUTHORITY)
    _connect(got.pin, _pin(owns, "self"))
    mine = ed.add_branch_node()
    _connect(out(owns), _pin(mine, "Condition"))
    _connect(got.then, _pin(mine, "execute"))
    return Got(got.pin, then(mine), got.fails + [else_(mine)], got.nodes + [owns, mine])


def player_state_of(ed, holder, holder_class_path, in_execs):
    """``holder``'s PlayerState (a pawn pin with PAWN_CLASS_PATH, a controller
    pin with CONTROLLER_CLASS_PATH), cast to BP_OtherworldPlayerState."""
    prop = ed.add_get_member_variable_node(PLAYER_STATE_PROP, holder_class_path)
    _connect(holder, _pin(prop, "self"))
    cast, pin = _cast(ed, NODE_CAST_PLAYER_STATE, "AsBPOtherworldPlayerState",
                      out(prop, PLAYER_STATE_PROP), in_execs)
    return Got(pin, then(cast), [out(cast, "CastFailed")], [prop, cast])


def owner_player_state(ed, in_execs):
    """A component's: the player state of the pawn that owns it. Fails for a
    pawn no player has (a wanderer)."""
    owner = _node(ed, FN_GET_OWNER)
    as_pawn, pawn = _cast(ed, NODE_CAST_PAWN, "AsPawn", out(owner), in_execs)
    got = player_state_of(ed, pawn, PAWN_CLASS_PATH, [then(as_pawn)])
    return Got(got.pin, got.then, [out(as_pawn, "CastFailed")] + got.fails,
               [owner, as_pawn] + got.nodes)


def first_player_state(ed, in_execs):
    """Player 0's, by the GameState's list. Right in single player; on a
    server it is whoever joined first, so nothing may keep it once the thing
    it stands in for exists (a kill's is the instigator, task M14)."""
    get = _node(ed, FN_GET_PLAYER_STATE)
    _set(get, "PlayerStateIndex", 0)
    cast, pin = _cast(ed, NODE_CAST_PLAYER_STATE, "AsBPOtherworldPlayerState",
                      out(get), in_execs)
    return Got(pin, then(cast), [out(cast, "CastFailed")], [get, cast])


def server_game_mode(ed, in_execs, component=True):
    """The GameMode, where there is one: Switch Has Authority, then the cast.
    ``fails`` is the cast's failure and the switch's Remote arm. ``component``:
    the graph is a component's (it asks its owner), not an actor's."""
    switch = ed.add_macro_node(
        MACRO_SWITCH_AUTHORITY_COMP if component else MACRO_SWITCH_AUTHORITY)
    for e in in_execs:
        _connect(e, _pin(switch, "execute"))
    get = _node(ed, FN_GET_GAME_MODE)
    cast, pin = _cast(ed, NODE_CAST_GAME_MODE, "AsBPThirdPersonGameMode", out(get),
                      [out(switch, "Authority")])
    return Got(pin, then(cast), [out(cast, "CastFailed"), out(switch, "Remote")],
               [switch, get, cast])
