"""BP_OtherworldGameInstance: the session's state, kept across travel.

    NetworkError(FailureType)  NetReason := what the player is told (one line
                               per ENetworkFailure, session_consts.NET_REASONS),
                               Connecting := false, JoinAddress := ""
    TravelError(FailureType)   the same, the reason being the engine's name
                               for the failure

Each sets the reason only while there is none: one failed join can raise
both, and the first is the cause. The menu clears it when the next join
starts (graphics_menu/mode_tick.py).

A GameInstance because it is the one object a failed join or a dropped
session leaves standing: the engine tells it (these two events), then loads
the title's level again, and the new HUD reads the reason off it. Nothing
here asks which mode this is: a single-player game raises neither event.

build_graphics_menu.py builds it, before the HUD that casts to it;
`DefaultEngine.ini` names it (session_consts.GAME_INSTANCE_INI).
"""

import unreal

from uebp.graph import (
    BEL, BGE, _apply_defaults, _connect, _create_blueprint, _loose_pin, _node, _palette,
    _pin, _set, else_, out, then)
from uebp.layout import arrange
from uebp.nodes.palette import (
    NODE_ENUM_TO_STRING, NODE_EVENT_NETWORK_ERROR, NODE_EVENT_TRAVEL_ERROR,
    NODE_SWITCH_NET_FAILURE)
from uebp.nodes.system import FN_CONCAT, FN_STR_EMPTY
from uebp.vars import declare, defaults
from net import session_consts as S

FAILURE_PIN = "FailureType"


def _put(ed, var, value, in_execs):
    n = ed.add_set_member_variable_node(var)
    if isinstance(value, (str, bool)):
        _set(n, var, value)
    else:
        _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    return then(n)


def _unreasoned(ed, event):
    """The exec that runs off ``event`` while NetReason is still empty."""
    reason = ed.add_get_member_variable_node(S.NetReason)
    empty = _node(ed, FN_STR_EMPTY)
    _connect(out(reason, S.NetReason), _pin(empty, "InString"))
    first = ed.add_branch_node()
    _connect(out(empty), _pin(first, "Condition"))
    _connect(then(event), _pin(first, "execute"))
    return then(first), else_(first)


def _author_ended(ed, in_execs):
    """No join is under way and no server is the session's any more."""
    flow = _put(ed, S.Connecting, False, in_execs)
    return _put(ed, S.JoinAddress, "", [flow])


def _author_network_error(ed):
    event = _palette(ed, NODE_EVENT_NETWORK_ERROR)
    fresh, told = _unreasoned(ed, event)
    switch = _palette(ed, NODE_SWITCH_NET_FAILURE)
    _connect(_loose_pin(event, FAILURE_PIN, is_input=False), _loose_pin(switch, "Selection"))
    _connect(fresh, _pin(switch, "execute"))
    tails = [told]
    for pin in BEL.list_output_pins(switch):
        name = str(unreal.BlueprintGraphPinLibrary.get_pin_name(pin))
        tails.append(_put(ed, S.NetReason, S.NET_REASONS.get(name, S.REASON_OTHER), [pin]))
    _author_ended(ed, tails)
    ed.add_comment_to_nodes(
        "A connection failed or dropped: the reason the title's Multiplayer "
        "page shows, kept here because the HUD that would show it is about "
        "to be replaced by the title level's.", [event, switch])


def _author_travel_error(ed):
    event = _palette(ed, NODE_EVENT_TRAVEL_ERROR)
    fresh, told = _unreasoned(ed, event)
    named = _palette(ed, NODE_ENUM_TO_STRING)
    _connect(_loose_pin(event, FAILURE_PIN, is_input=False), _pin(named, "Enumerator"))
    text = _node(ed, FN_CONCAT)
    _set(text, "A", S.REASON_TRAVEL)
    _connect(out(named), _pin(text, "B"))
    _author_ended(ed, [_put(ed, S.NetReason, out(text), [fresh]), told])
    ed.add_comment_to_nodes(
        "A travel failed (an address that is no server, a level this game "
        "does not have): the engine's name for it is the reason.", [event, named, text])


def build_game_instance():
    """Create (or rebuild) BP_OtherworldGameInstance. Returns the Blueprint."""
    bp = _create_blueprint(S.GAME_INSTANCE_BP_PATH, unreal.GameInstance)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{S.GAME_INSTANCE_BP_PATH} has no EventGraph")
    ed.remove_nodes(ed.list_all_nodes())
    declare(ed, S.TABLE)
    _author_network_error(ed)
    _author_travel_error(ed)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_OtherworldGameInstance failed to compile")
    _apply_defaults(bp, defaults(S.TABLE))
    return bp
