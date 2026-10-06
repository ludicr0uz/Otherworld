"""The local gate: whose keys this Tick may read (net/CLAUDE.md, "Input").

    Tick --> dead gate --> owner is a Pawn, its controller a PlayerController,
                           and that controller is this machine's?
               yes --> LocalPC = it, LocalInput = true
                       --> once (LocalReady): what BeginPlay could not ask a
                           controller for yet (the look scales, the listener)
                       --> the keys, the view, the trigger, the actions
               no  --> LocalPC = none, LocalInput = false --> none of those

A component ticks on every machine that has its character: the player's own,
the server, and every other client. Only the first has that player's keys.
The Tick used to poll GetPlayerController(0), which on a client is the local
player whichever character the component is on: one press of fire fired every
character that client could see, each on its own copy.

So every poll in the Tick is made on LocalPC and stands behind this gate or
behind ``_author_local_only``, the same question asked again further down
the chain (of LocalInput, which this gate wrote this frame). What runs on
every copy is what follows from state: the pose, the slots, the equip.

A controller that is not a PlayerController is not local input either: an AI
controller is "local" to the server by the engine's own answer.

Once rather than at BeginPlay, because a pawn has no controller at BeginPlay
unless it was possessed before the world began (a client's arrives by
replication, a respawned pawn's after it is spawned).
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from Sound.sound_world import _author_listener_at_character
from uebp.nodes.actor import (
    FN_GET_CONTROLLER, FN_GET_PITCH_SCALE, FN_GET_YAW_SCALE, FN_IS_LOCAL_CONTROLLER)
from uebp.nodes.palette import NODE_CAST_CHAR, NODE_CAST_PAWN, NODE_CAST_PLAYER_CONTROLLER
from combat.weapon_component import vars as WV

PC_CLASS_PATH = "/Script/Engine.PlayerController"


def local_pc(ed):
    """The pin every poll's self is: this machine's controller of the owner.
    None off the local arm, so read it only behind the gate."""
    return out(ed.add_get_member_variable_node(WV.LocalPC), WV.LocalPC)


def _flag(ed, var, value, execs, made):
    n = ed.add_set_member_variable_node(var)
    made.append(n)
    _set(n, var, value)
    for e in execs:
        _connect(e, _pin(n, "execute"))
    return then(n)


def _author_local_gate(ed, owner_out, exec_in):
    """See the module docstring. Returns (local, remote): the exec a locally
    controlled owner's Tick carries on from, and everyone else's."""
    made = []
    as_pawn = _palette(ed, NODE_CAST_PAWN)
    _connect(owner_out, _pin(as_pawn, "Object"))
    _connect(exec_in, _pin(as_pawn, "execute"))
    ctrl = _node(ed, FN_GET_CONTROLLER)
    _connect(_loose_pin(as_pawn, "AsPawn", is_input=False), _pin(ctrl, "self"))
    as_pc = _palette(ed, NODE_CAST_PLAYER_CONTROLLER)
    _connect(out(ctrl), _pin(as_pc, "Object"))
    _connect(then(as_pawn), _pin(as_pc, "execute"))
    pc = _loose_pin(as_pc, "AsPlayerController", is_input=False)
    here = _node(ed, FN_IS_LOCAL_CONTROLLER)
    _connect(pc, _pin(here, "self"))
    mine = ed.add_branch_node()
    _connect(out(here), _pin(mine, "Condition"))
    _connect(then(as_pc), _pin(mine, "execute"))
    made += [as_pawn, ctrl, as_pc, here, mine]

    keep_pc = ed.add_set_member_variable_node(WV.LocalPC)
    _connect(pc, _pin(keep_pc, WV.LocalPC))
    _connect(then(mine), _pin(keep_pc, "execute"))
    made.append(keep_pc)
    local = _flag(ed, WV.LocalInput, True, [then(keep_pc)], made)

    # Not this machine's: the pin left empty writes None.
    drop_pc = ed.add_set_member_variable_node(WV.LocalPC)
    for fail in (_pin(as_pawn, "CastFailed", is_input=False),
                 _pin(as_pc, "CastFailed", is_input=False), else_(mine)):
        _connect(fail, _pin(drop_pc, "execute"))
    made.append(drop_pc)
    remote = _flag(ed, WV.LocalInput, False, [then(drop_pc)], made)

    ed.add_comment_to_nodes(
        "The local gate: keys are read only on the machine whose player "
        "controls this character. LocalPC is that controller (every poll's "
        "self), LocalInput the answer for the gates further down. On the "
        "server and on another player's client neither the keys nor the view "
        "run.",
        made)
    return _author_local_once(ed, owner_out, local), remote


def _author_local_once(ed, owner_out, exec_in):
    """The first local frame: the controller's own look scales, cached for
    the scope's slowdown (ads.py), and the listener pinned to the character
    (Sound/sound_world.py). Returns the exec every local frame leaves by."""
    made = []
    ready = ed.add_get_member_variable_node(WV.LocalReady)
    first = ed.add_branch_node()
    _connect(out(ready, WV.LocalReady), _pin(first, "Condition"))
    _connect(exec_in, _pin(first, "execute"))
    done = _flag(ed, WV.LocalReady, True, [else_(first)], made)
    made += [ready, first]

    # The pitch scale is why this is a cache and not a constant: the engine
    # ships it NEGATIVE (-2.5), so a literal would have a one-in-two chance of
    # inverting the player's vertical look, and only after aiming once.
    pc = local_pc(ed)
    flow = done
    for fn, var in ((FN_GET_YAW_SCALE, WV.BaseYawScale),
                    (FN_GET_PITCH_SCALE, WV.BasePitchScale)):
        now = _node(ed, fn)
        _connect(pc, _pin(now, "self"))
        keep = ed.add_set_member_variable_node(var)
        _connect(out(now), _pin(keep, var))
        _connect(flow, _pin(keep, "execute"))
        made += [now, keep]
        flow = then(keep)

    cast = _palette(ed, NODE_CAST_CHAR)
    _connect(owner_out, _pin(cast, "Object"))
    _connect(flow, _pin(cast, "execute"))
    made.append(cast)
    heard = _author_listener_at_character(
        ed, _loose_pin(cast, "AsBPThirdPersonCharacter", is_input=False), pc, then(cast))

    # One setter every way out runs into, so the Tick hangs off a single pin.
    out_n = ed.add_set_member_variable_node(WV.LocalReady)
    _set(out_n, WV.LocalReady, True)
    for e in (then(first), heard, _pin(cast, "CastFailed", is_input=False)):
        _connect(e, _pin(out_n, "execute"))
    made.append(out_n)
    ed.add_comment_to_nodes(
        "Once, on the first frame this character is the local player's: its "
        "controller's look scales are cached and the listener is pinned to "
        "the capsule. Not at BeginPlay, where a pawn may have no controller "
        "yet.",
        made)
    return then(out_n)


def _author_local_only(ed, exec_ins):
    """The same question further down the chain. Returns (local, remote)."""
    asked = ed.add_get_member_variable_node(WV.LocalInput)
    gate = ed.add_branch_node()
    _connect(out(asked, WV.LocalInput), _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))
    ed.add_comment_to_nodes(
        "Local input only (local.py): the trigger, the action keys and the "
        "HUD's requests run where this character is the local player's.",
        [asked, gate])
    return then(gate), else_(gate)
