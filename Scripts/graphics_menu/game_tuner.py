"""Builds /Game/UI/BP_GameTuner, the component of BP_OtherworldGameState that
applies the gameplay tuning tables where the game is run (task M32), and
hangs it on the GameState.

A server has no HUD, and the tabs' applies are the HUD's. This is the same
four applies on the machine that owns the game:

    BeginPlay, with authority   GameState.DevTuning := ServerAllowsDevTuning
                                (the native switch: single player always, a
                                server only when started with -AllowDevTuning)
    Tick, with authority
      each gameplay table       its inbox on the GameState (state_consts.TUNED,
                                written by a client's AskTune) is not empty:
                                of this table's length -> this table := it,
                                Touched; either way the inbox is emptied
      guns touched              every player character's carried weapons take
                                the table (tune_tick.author_onto_pawn)
      monsters touched          every live controller its creature's row
      world touched             the cycle the lengths and switches, and the
                                clock when the hour moved (the tab's own rule)
      player touched            every player character's weapon component the
                                speeds and the stamina rates

In single player the HUD owns the game, keeps the tables and applies them
itself: no inbox is ever written, so this graph idles past its four length
tests. A client's copy does nothing (the authority switch). A length that is
not the table's is a client of another build, or a made-up call: dropped.

Applying every Tick once touched is the HUD's rule too, and for the same
reason: it reaches the gun picked up, the wanderer spawned and the player
who joined after the table came.
"""

import unreal

from combat.log import _log
from combat.melee_tuning import melee_specs
from combat.paths import CHARACTER_CLASS_PATH
from graphics_menu import monster_tune_tick, player_tune_tick, tune_tick, world_tune_tick
from graphics_menu.dev_guns import _branch, _call, _class_literal, _get, _setter
from graphics_menu.game_tuner_consts import (
    GAME_TUNER_BP_PATH, GAME_TUNER_COMPONENT, GAME_TUNER_TABLE, GAMEPLAY_TABS)
from graphics_menu.loot_find import put
from graphics_menu.player_tune_consts import PLAYER_TAB
from graphics_menu.tune_consts import GUN_TAB
from net import state_consts as S
from net.state_graph import game_state
from uebp.graph import (
    BEL, BGE, _add_component, _apply_defaults, _assets, _connect, _create_blueprint,
    _drop_components, _events, _loose_pin, _must_load, _node, _pin, _root_handle, out, then)
from uebp.layout import arrange
from uebp.nodes.array import FN_ARR_CLEAR, FN_ARR_LEN
from uebp.nodes.level import FN_SERVER_ALLOWS_DEV_TUNING
from uebp.nodes.math import FN_EQ_II, FN_GREATER_II
from uebp.nodes.palette import MACRO_FOR_EACH, MACRO_SWITCH_AUTHORITY_COMP
from uebp.nodes.system import FN_ALL_ACTORS
from uebp.vars import declare, defaults


def tuner_defaults():
    """The built tables, as the HUD's tabs hold them; nothing touched."""
    built = {**tune_tick.tune_defaults(), **monster_tune_tick.monster_tune_defaults(),
             **world_tune_tick.world_tune_defaults(), **player_tune_tick.player_tune_defaults()}
    plain = defaults(GAME_TUNER_TABLE)
    return {var: built.get(var, plain.get(var)) for var in GAME_TUNER_TABLE}


def _owned(ed, in_execs):
    """Switch Has Authority: (Authority, Remote)."""
    switch = ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP)
    if not switch:
        raise RuntimeError("could not create the Switch Has Authority macro node")
    for e in in_execs:
        _connect(e, _pin(switch, "execute"))
    return out(switch, "Authority"), out(switch, "Remote")


def _author_begin(ed, begin):
    mine, _remote = _owned(ed, [then(begin)])
    got = game_state(ed, [mine])
    allows = _node(ed, FN_SERVER_ALLOWS_DEV_TUNING)
    write = ed.add_set_member_variable_node(S.DevTuning, S.GAME_STATE_CLASS_PATH)
    _connect(got.pin, _pin(write, "self"))
    _connect(out(allows), _pin(write, S.DevTuning))
    _connect(got.then, _pin(write, "execute"))
    ed.add_comment_to_nodes(
        "May the gameplay tables be tuned in this game? Single player: always. "
        "A server: only when started with -AllowDevTuning. Replicated, so every "
        "client's tabs know (tune_mode.py).", [write] + got.nodes)


def _author_take(ed, state, tab, inbox, in_execs, made):
    """One table's inbox (see the module docstring). Returns the exec tails."""
    def box():
        return _get(ed, inbox, made, S.GAME_STATE_CLASS_PATH, state)
    size = out(_call(ed, FN_ARR_LEN, made, TargetArray=box()))
    some = _call(ed, FN_GREATER_II, made, A=size, B=0)
    come, none = _branch(ed, out(some), in_execs, made)
    own = _call(ed, FN_ARR_LEN, made, TargetArray=_get(ed, tab.values_var, made))
    fits = _call(ed, FN_EQ_II, made, A=size, B=out(own))
    take, odd = _branch(ed, out(fits), [come], made)
    flow = put(ed, tab.values_var, box(), [take], made)
    flow = _setter(ed, tab.touched_var, "true", [flow], made)
    clear = _call(ed, FN_ARR_CLEAR, made, TargetArray=box())
    for e in (flow, odd):
        _connect(e, _pin(clear, "execute"))
    return [then(clear), none]


def _author_players(ed, touched_var, onto, in_execs, made):
    """``touched_var``: ``onto(pawn, execs)`` for every player character.
    Returns the exec tails."""
    go, idle = _branch(ed, _get(ed, touched_var, made), in_execs, made)
    find = _call(ed, FN_ALL_ACTORS, made)
    _class_literal(find, "ActorClass", CHARACTER_CLASS_PATH)
    _connect(go, _pin(find, "execute"))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(out(find, "OutActors"), _loose_pin(loop, "Array"))
    _connect(then(find), _loose_pin(loop, "Exec"))
    onto(_loose_pin(loop, "ArrayElement", is_input=False),
         [_loose_pin(loop, "LoopBody", is_input=False)])
    return [_loose_pin(loop, "Completed", is_input=False), idle]


def _author_tick(ed, tick):
    made = []
    mine, _remote = _owned(ed, [then(tick)])
    got = game_state(ed, [mine])
    made += got.nodes
    flow = [got.then]
    if len(S.TUNED) != len(GAMEPLAY_TABS):
        raise RuntimeError("one inbox per gameplay table")
    for tab, inbox in zip(GAMEPLAY_TABS, S.TUNED):
        flow = _author_take(ed, got.pin, tab, inbox, flow, made)
    guns = len(tune_tick.tune_table()[0]) - len(melee_specs())
    flow = _author_players(
        ed, GUN_TAB.touched_var,
        lambda pawn, execs: tune_tick.author_onto_pawn(ed, pawn, execs, made, guns), flow, made)
    flow = monster_tune_tick._author_apply(ed, flow, made)
    flow = world_tune_tick._author_apply(ed, flow, made)
    _author_players(
        ed, PLAYER_TAB.touched_var,
        lambda pawn, execs: player_tune_tick.author_onto_pawn(ed, pawn, execs, made), flow, made)
    ed.add_comment_to_nodes(
        "The gameplay tables where the game is run. A client's tab sends its table "
        "(AskTune) into the GameState's inbox; this takes it and applies it as the "
        "HUD's tabs do in single player: guns and speeds onto every player, a "
        "creature's row onto every controller, the world's onto the cycle.", made[:1])


def install_game_tuner():
    """BP_OtherworldGameState's GameTuner component."""
    bp = _must_load(S.GAME_STATE_BP_PATH)
    _drop_components(bp, {GAME_TUNER_COMPONENT})
    _add_component(bp, _root_handle(bp), BEL.generated_class(_must_load(GAME_TUNER_BP_PATH)),
                   GAME_TUNER_COMPONENT)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_OtherworldGameState failed to compile with its tuner")
    _assets().save_loaded_asset(bp)


def build_game_tuner(rebuild=True):
    bp = _create_blueprint(GAME_TUNER_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    declare(ed, GAME_TUNER_TABLE)
    _author_begin(ed, begin)
    _author_tick(ed, tick)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GameTuner failed to compile")
    _apply_defaults(bp, tuner_defaults())       # recompiles and saves
    install_game_tuner()
    _log(f"built {GAME_TUNER_BP_PATH}, {GAME_TUNER_COMPONENT} on {S.GAME_STATE_BP_PATH}")
    return bp
