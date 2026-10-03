"""A roar: the wanderer stops, faces the player, and plays its roar clip and
one of its voices. The hunt's first pass is one (npc/stalk.py), and so are
the two a wendigo held off by fire gives (npc/ward.py).

The clip is the creature's row of forest_generator/npc_stalk.NPC_STALK_ROAR,
played through the pawn's own AnimInstance into the upper-body slot the swing
uses. What makes it stand for the length of the roar is the caller's: a time
it stores, and a Branch on it that succeeds the step without a move order.
"""

from forest_generator.npc_stalk import NPC_STALK_ROAR_BLEND_S
from npc.graph import _log, _mesh_object
from uebp.graph import _assets, _connect, _loose_pin, _palette, _pin, out, then
from npc.paths import CHARACTER_CLASS_PATH, MELEE_SLOT, VOICES_VAR
from npc.sound import _author_random_sound
from npc.strafe import _author_facing
from uebp.nodes.actor import FN_ANIM_INSTANCE, FN_PLAY_SLOT, FN_STOP_MOVEMENT
from uebp.nodes.palette import NODE_CAST_CHARACTER


def roar_object(roar_anim):
    """The roar clip as an object path, or None when the asset pipeline has
    not produced it (asset_pipeline/import_mixamo.py): the wendigo then
    stands and roars with its voice alone."""
    if roar_anim and _assets().does_asset_exist(roar_anim):
        return _mesh_object(roar_anim)
    _log(f"note: no roar clip at {roar_anim} -- run "
         f"Scripts/asset_pipeline/import_mixamo.py. The roar is sound only.")
    return None


def _author_bellow(g, exec_in, pins, roar_anim):
    """Stop, face the player, play the roar clip (``roar_anim``:
    roar_object()'s answer) and a voice. ``pins`` has the caller's
    ``self_pawn``, ``self_loc`` and ``player``. Returns the exec pin it ends
    on."""
    halt = g.call(FN_STOP_MOVEMENT)
    _connect(exec_in, _pin(halt, "execute"))
    watch, step = _author_facing(g.ed, [then(halt)], pins["player"])
    g.made.extend(watch)

    # Through the pawn's own AnimInstance, as the swing is (npc/melee.py), and
    # into the same upper-body slot: the legs stand, the chest and arms roar.
    as_char = g.keep(_palette(g.ed, NODE_CAST_CHARACTER))
    _connect(pins["self_pawn"], _pin(as_char, "Object"))
    _connect(step, _pin(as_char, "execute"))
    voiced = [out(as_char, "CastFailed")]
    if roar_anim:
        mesh = g.keep(g.ed.add_get_member_variable_node("Mesh", CHARACTER_CLASS_PATH))
        _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))
        anim = g.call(FN_ANIM_INSTANCE)
        _connect(out(mesh, "Mesh"), _pin(anim, "self"))
        roar = g.call(FN_PLAY_SLOT, Asset=roar_anim,
                      SlotNodeName=MELEE_SLOT, BlendInTime=NPC_STALK_ROAR_BLEND_S,
                      BlendOutTime=NPC_STALK_ROAR_BLEND_S)
        _connect(out(anim), _pin(roar, "self"))
        _connect(then(as_char), _pin(roar, "execute"))
        voiced.append(then(roar))
    else:
        voiced.append(then(as_char))
    join = g.branch(None, voiced)
    sound, step = _author_random_sound(g.ed, VOICES_VAR, pins["self_loc"], then(join))
    g.made.extend(sound)
    return step
