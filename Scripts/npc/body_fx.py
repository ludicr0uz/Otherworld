"""What a wanderer is heard and seen to do, on every machine (task M27): the
two Multicast events of BP_ForestWanderer, and the fragments a controller's
step calls them with.

The AI controller exists on the server alone, and so do its sound arrays and
its clips. A sound it played itself was heard by no client, and a swing it
played into its own copy of the body was seen by none. So the controller
picks the take or the clip, as it always did, and hands it to the body:

    Multicast_Voice(Sound, Location)   -> VoicesPlayed + 1
                                       -> PlaySoundAtLocation
    Multicast_Clip(Asset, SlotNodeName, BlendInTime, BlendOutTime)
                                       -> ClipsPlayed + 1
                                       -> Mesh's AnimInstance:
                                          PlaySlotAnimationAsDynamicMontage

Both are unreliable: a lost one loses a growl or the sight of a swing, never
the blow (the damage is the server's, in the step that called). The server
plays the clip too, as it did: its pose is what a shot is traced against.
In single player a Multicast is a plain call, once.

build_body_events() runs before the controllers are authored (their graphs
cast to this class and call its events) and before npc/character.py writes
the body's defaults.
"""

import unreal

from npc import body_vars as BV
from npc.graph import _log
from npc.paths import CHARACTER_CLASS_PATH, NPC_BP_PATH
from uebp import net
from uebp import props as EP
from uebp.graph import (
    BEL, BGE, _assets, _connect, _create_blueprint, _loose_pin, _must_load, _node,
    _palette, _pin, _set, out, then)
from uebp.layout import arrange
from uebp.nodes.actor import FN_ANIM_INSTANCE, FN_GET_PAWN, FN_PLAY_SLOT
from uebp.nodes.math import FN_ADD_II
from uebp.nodes.palette import NODE_CAST_WANDERER
from uebp.nodes.system import FN_PLAY_SOUND
from uebp.vars import declare

BODY_PIN = "AsBPForestWanderer"


def _count(ed, var, exec_in):
    """``var`` + 1; returns ``(nodes, the exec pin after)``."""
    now = ed.add_get_member_variable_node(var)
    more = _node(ed, FN_ADD_II)
    _connect(out(now, var), _pin(more, "A"))
    _set(more, "B", 1)
    keep = ed.add_set_member_variable_node(var)
    _connect(out(more), _pin(keep, var))
    _connect(exec_in, _pin(keep, "execute"))
    return [now, more, keep], then(keep)


def build_body_events():
    """Create BP_ForestWanderer if it is not there, and author its two
    Multicast events afresh. Returns the Blueprint, compiled and saved."""
    bp = _create_blueprint(NPC_BP_PATH, unreal.Character)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{NPC_BP_PATH} has no EventGraph")
    # Everything but the three placeholders a fresh Blueprint ships with.
    ed.remove_nodes([n for n in ed.list_all_nodes()
                     if not str(BEL.get_node_title(n)).startswith("Event ")])
    BEL.compile_blueprint(bp)       # the events' names are free again
    declare(ed, BV.TABLE)

    voice = net.multicast_event(ed, BV.VOICE_EVENT, BV.VOICE_PARAMS, reliable=False)
    made, step = _count(ed, BV.VoicesPlayed, then(voice))
    play = _node(ed, FN_PLAY_SOUND)
    for param, _type in BV.VOICE_PARAMS:
        _connect(out(voice, param), _pin(play, param))
    _connect(step, _pin(play, "execute"))
    ed.add_comment_to_nodes(
        f"{BV.VOICE_EVENT} (npc/body_fx.py): the server's controller picked one of "
        f"its takes; every machine that has this body plays it. Unreliable.",
        [voice, play] + made)

    clip = net.multicast_event(ed, BV.CLIP_EVENT, BV.CLIP_PARAMS, reliable=False)
    made, step = _count(ed, BV.ClipsPlayed, then(clip))
    mesh = ed.add_get_member_variable_node(EP.MESH, CHARACTER_CLASS_PATH)
    anim = _node(ed, FN_ANIM_INSTANCE)
    _connect(out(mesh, EP.MESH), _pin(anim, "self"))
    slot = _node(ed, FN_PLAY_SLOT)
    _connect(out(anim), _pin(slot, "self"))
    for param, _type in BV.CLIP_PARAMS:
        _connect(out(clip, param), _pin(slot, param))
    _connect(step, _pin(slot, "execute"))
    ed.add_comment_to_nodes(
        f"{BV.CLIP_EVENT} (npc/body_fx.py): the swing or the roar, into this "
        f"body's own slot on every machine, the server's included (its pose is "
        f"what a shot is traced against). Unreliable.", [clip, mesh, anim, slot] + made)

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{NPC_BP_PATH} failed to compile")
    _assets().save_loaded_asset(bp)
    _log(f"authored {BV.VOICE_EVENT} and {BV.CLIP_EVENT} on {NPC_BP_PATH}")
    return bp


# --- calling them, from a controller's graph ----------------------------------

def _body(ed, keep, exec_in):
    """The controller's pawn as a wanderer: ``(the body pin, the cast)``. A
    pawn of another class has neither event: go on from CastFailed too."""
    _must_load(NPC_BP_PATH)         # the cast exists only for a loaded class
    pawn = keep(_node(ed, FN_GET_PAWN))
    cast = keep(_palette(ed, NODE_CAST_WANDERER))
    _connect(out(pawn), _pin(cast, "Object"))
    for pin in (exec_in if isinstance(exec_in, (list, tuple)) else (exec_in,)):
        _connect(pin, _pin(cast, "execute"))
    return _loose_pin(cast, BODY_PIN, is_input=False), cast


def _join(ed, keep, execs):
    join = keep(ed.add_branch_node())
    _set(join, "Condition", True)
    for pin in execs:
        _connect(pin, _pin(join, "execute"))
    return then(join)


def heard_by_all(ed):
    """Sound/play.py's ``play``: the take goes to the body's Multicast_Voice
    in place of a PlaySoundAtLocation of the controller's own."""
    def play(sound, at, exec_in, keep):
        body, cast = _body(ed, keep, exec_in)
        tell = keep(_node(ed, BV.FN_MULTICAST_VOICE))
        _connect(body, _pin(tell, "self"))
        _connect(sound, _pin(tell, "Sound"))
        _connect(at, _pin(tell, "Location"))
        _connect(then(cast), _pin(tell, "execute"))
        return _join(ed, keep, [then(tell), out(cast, "CastFailed")])
    return play


def _author_clip(ed, keep, exec_in, asset, blend_s, slot):
    """Play ``asset`` (an object path) into ``slot`` on every copy of the
    body. Returns the exec pin after, reached whether or not the pawn is a
    wanderer."""
    body, cast = _body(ed, keep, exec_in)
    tell = keep(_node(ed, BV.FN_MULTICAST_CLIP))
    _connect(body, _pin(tell, "self"))
    _set(tell, "Asset", asset)
    _set(tell, "SlotNodeName", slot)
    _set(tell, "BlendInTime", blend_s)
    _set(tell, "BlendOutTime", blend_s)
    _connect(then(cast), _pin(tell, "execute"))
    return _join(ed, keep, [then(tell), out(cast, "CastFailed")])
