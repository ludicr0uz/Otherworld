"""Who is nearby: builds BPL_Players, the function library a world actor or a
wanderer asks instead of GetPlayerPawn(0), and the fragments that call it.

On a server player 0 is whoever joined first, so "the player" is no one in
particular. A graph outside what a player owns says which player it means:

    living_players          every living player's pawn (an exec call: the
                            array is made once and read as often as wanted)
    each_living_player      the same, in a ForEach: what happens to everyone
                            (the night's cold, a campfire's warmth)
    nearest_living_player   the one nearest a point, or none (pure: asked
                            again at each read, as GetPlayerPawn was)

A player is living while their pawn exists and their PlayerState does not
say PlayerDead (combat/death.py writes it on the server; it replicates), so
the answer is the same on every machine that has the pawn. The players are
the GameState's PlayerArray, which a client has too.

Which player a wanderer hunts is the nearest, asked afresh at every read;
choosing one and keeping them is task M27's.

build_weapons_and_combat.py calls build_players() after build_state().
"""

import unreal

from net import players_consts as P
from net import state_consts as S
from uebp.graph import (
    BEL, BGE, _assets, _connect, _float_type, _loose_pin, _must_load, _node, _palette,
    _pin, _struct_type, else_, out, then)
from uebp.layout import arrange
from uebp.nodes.actor import FN_ACTOR_LOC, FN_PLAYER_STATE_PAWN
from uebp.nodes.array import FN_ARR_ADD
from uebp.nodes.math import FN_DISTANCE, FN_LESS_FF, FN_NOT, FN_OR
from uebp.nodes.palette import MACRO_FOR_EACH, NODE_CAST_PLAYER_STATE
from uebp.nodes.system import FN_GET_GAME_STATE, FN_IS_VALID

GAME_STATE_CLASS_PATH = "/Script/Engine.GameStateBase"
PLAYER_ARRAY_PROP = "PlayerArray"
FOUND_LOCAL = "Found"
BEST_LOCAL = "Best"
BEST_GAP_LOCAL = "BestGap"


def _create_library(path):
    eas = _assets()
    if eas.does_asset_exist(path):
        existing = eas.load_asset(path)
        if existing:
            return existing
    package_path, asset_name = path.rsplit("/", 1)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, package_path, unreal.Blueprint, unreal.BlueprintFunctionLibraryFactory())
    if not bp:
        raise RuntimeError(f"could not create the function library {path}")
    return bp


def _function(bp, name, inputs, outputs, locals_):
    """The graph editor of function ``name``, emptied down to its entry and
    result nodes: ``(ed, {input: entry pin}, the result node)``.

    A rebuild keeps the graph and its signature and wipes what is between.
    Removing the graph and making it again names the new one ``<name>_0``
    (the compiled class still holds the old function), and a compile between
    the two would leave every caller in the game without it for a moment.
    """
    if name in [str(g) for g in BEL.list_graph_names(bp)]:
        ed = BGE.get_graph_editor_by_name(bp, name)
        ed.remove_nodes([n for n in ed.list_all_nodes()
                         if not isinstance(n, unreal.K2Node_FunctionTerminator)])
        entry = ed.list_nodes_of_class(unreal.K2Node_FunctionEntry)[0]
        result = ed.list_nodes_of_class(unreal.K2Node_FunctionResult)[0]
        pins = {i: _pin(entry, i, is_input=False) for i, _t in inputs}
    else:
        ed = BGE.create_and_edit_function_graph(bp, name)
        if not ed:
            raise RuntimeError(f"could not create the function {name}")
        pins = {i: ed.add_graph_input_parameter(i, t) for i, t in inputs}
        result = None
        for o, t in outputs:
            result = ed.add_graph_output_parameter(o, t)
    have = [str(n) for n in ed.list_local_variable_names()]
    for local, t in locals_:
        if local not in have and not ed.add_local_variable(local, t):
            raise RuntimeError(f"could not declare the local {local}")
    return ed, pins, result


def _for_each(ed, array, in_execs):
    """ForEachLoop over ``array``: (the element pin, the body's exec, the
    exec after the last one, the node)."""
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _connect(array, _loose_pin(loop, "Array"))
    for e in in_execs:
        _connect(e, _loose_pin(loop, "Exec"))
    return (_loose_pin(loop, "ArrayElement", is_input=False),
            _loose_pin(loop, "LoopBody", is_input=False),
            _loose_pin(loop, "Completed", is_input=False), loop)


def _branch(ed, condition, in_execs):
    b = ed.add_branch_node()
    _connect(condition, _pin(b, "Condition"))
    for e in in_execs:
        _connect(e, _pin(b, "execute"))
    return b


def _call(ed, fn, **inputs):
    n = _node(ed, fn)
    for name, pin in inputs.items():
        _connect(pin, _pin(n, name))
    return n


def _author_living(bp, pawn_type):
    """LivingPlayers() -> Players: each PlayerState of the GameState whose pawn
    exists and which does not say PlayerDead. A PlayerState of another class
    has no such flag, and its pawn counts."""
    pawns = BEL.get_array_type(pawn_type)
    ed, _pins, result = _function(bp, P.LIVING_FN, (), [(P.PLAYERS_PIN, pawns)],
                                  [(FOUND_LOCAL, pawns)])

    def found():
        return out(ed.add_get_local_variable_node(FOUND_LOCAL), FOUND_LOCAL)

    state = _node(ed, FN_GET_GAME_STATE)
    # No GameState yet (a client's first frames): no one.
    there = _branch(ed, out(_call(ed, FN_IS_VALID, Object=out(state))),
                    [ed.find_graph_entry_pin()])
    players = ed.add_get_member_variable_node(PLAYER_ARRAY_PROP, GAME_STATE_CLASS_PATH)
    _connect(out(state), _pin(players, "self"))
    one, body, done, _loop = _for_each(ed, out(players, PLAYER_ARRAY_PROP), [then(there)])

    pawn = _node(ed, FN_PLAYER_STATE_PAWN)
    _connect(one, _pin(pawn, "self"))
    has_pawn = _branch(ed, out(_call(ed, FN_IS_VALID, Object=out(pawn))), [body])
    cast = _palette(ed, NODE_CAST_PLAYER_STATE)
    _connect(one, _pin(cast, "Object"))
    _connect(then(has_pawn), _pin(cast, "execute"))
    dead = ed.add_get_member_variable_node(S.Dead, S.PLAYER_STATE_CLASS_PATH)
    _connect(_loose_pin(cast, "AsBPOtherworldPlayerState", is_input=False), _pin(dead, "self"))
    alive = _branch(ed, out(_call(ed, FN_NOT, A=out(dead, S.Dead))), [then(cast)])
    add = _node(ed, FN_ARR_ADD)
    _connect(found(), _pin(add, "TargetArray"))
    _connect(out(pawn), _pin(add, "NewItem"))
    _connect(then(alive), _pin(add, "execute"))
    _connect(out(cast, "CastFailed"), _pin(add, "execute"))

    _connect(found(), _pin(result, P.PLAYERS_PIN))
    _connect(done, _pin(result, "execute"))
    _connect(else_(there), _pin(result, "execute"))
    arrange(ed)


def _author_nearest(bp, pawn_type):
    """NearestLivingPlayer(Point) -> Player: the living player whose pawn is
    nearest Point, or none. Pure."""
    ed, pins, result = _function(
        bp, P.NEAREST_FN, [(P.POINT_PIN, _struct_type(unreal.Vector.static_struct()))],
        [(P.PLAYER_PIN, pawn_type)], [(BEST_LOCAL, pawn_type), (BEST_GAP_LOCAL, _float_type())])
    ed.set_is_pure_function(True)
    point = pins[P.POINT_PIN]

    def best():
        return out(ed.add_get_local_variable_node(BEST_LOCAL), BEST_LOCAL)

    living = _node(ed, P.FN_LIVING_PLAYERS)
    _connect(ed.find_graph_entry_pin(), _pin(living, "execute"))
    one, body, done, _loop = _for_each(ed, out(living, P.PLAYERS_PIN), [then(living)])

    gap = _call(ed, FN_DISTANCE, V1=point, V2=out(_call(ed, FN_ACTOR_LOC, self=one)))
    gap_now = ed.add_get_local_variable_node(BEST_GAP_LOCAL)
    nearer = _call(ed, FN_LESS_FF, A=out(gap), B=out(gap_now, BEST_GAP_LOCAL))
    first = _call(ed, FN_NOT, A=out(_call(ed, FN_IS_VALID, Object=best())))
    better = _branch(ed, out(_call(ed, FN_OR, A=out(first), B=out(nearer))), [body])
    # The gap first: it is read off the same pure chain the Branch just read.
    keep_gap = ed.add_set_local_variable_node(BEST_GAP_LOCAL)
    _connect(out(gap), _pin(keep_gap, BEST_GAP_LOCAL))
    _connect(then(better), _pin(keep_gap, "execute"))
    keep = ed.add_set_local_variable_node(BEST_LOCAL)
    _connect(one, _pin(keep, BEST_LOCAL))
    _connect(then(keep_gap), _pin(keep, "execute"))

    _connect(best(), _pin(result, P.PLAYER_PIN))
    _connect(done, _pin(result, "execute"))
    arrange(ed)


def build_players():
    """Create (or rebuild) BPL_Players. Returns the Blueprint."""
    _must_load(S.PLAYER_STATE_BP_PATH)    # the cast exists only for a loaded class
    bp = _create_library(P.PLAYERS_BP_PATH)
    pawn_type = BEL.get_object_reference_type(unreal.Pawn)
    _author_living(bp, pawn_type)
    if not BEL.compile_blueprint(bp):     # NearestLivingPlayer calls the compiled one
        raise RuntimeError(f"{P.PLAYERS_BP_PATH} failed to compile")
    _author_nearest(bp, pawn_type)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{P.PLAYERS_BP_PATH} failed to compile")
    _assets().save_loaded_asset(bp)
    return bp


# --- calling it -------------------------------------------------------------

def living_players(ed, in_execs):
    """Call LivingPlayers: ``(node, the Players array pin)``. Go on from
    ``then(node)``."""
    _must_load(P.PLAYERS_BP_PATH)
    node = _node(ed, P.FN_LIVING_PLAYERS)
    for e in in_execs:
        _connect(e, _pin(node, "execute"))
    return node, out(node, P.PLAYERS_PIN)


def each_living_player(ed, in_execs):
    """Every living player in turn: ``(pawn pin, the body's exec, the exec
    after the last, the nodes made)``."""
    node, players = living_players(ed, in_execs)
    one, body, done, loop = _for_each(ed, players, [then(node)])
    return one, body, done, [node, loop]


def nearest_living_player(ed, point):
    """The pure NearestLivingPlayer node for ``point`` (a vector pin); the
    pawn is ``player_pin(node)``. None while no player lives: check it in a
    Branch of its own before anything reads off it."""
    _must_load(P.PLAYERS_BP_PATH)
    node = _node(ed, P.FN_NEAREST_LIVING_PLAYER)
    _connect(point, _pin(node, P.POINT_PIN))
    return node


def player_pin(node):
    return out(node, P.PLAYER_PIN)
