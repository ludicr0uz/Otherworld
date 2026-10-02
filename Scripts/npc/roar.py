"""A roar: the wanderer stops, faces the player, and plays its roar clip and
one of its voices. The hunt's first pass is one (npc/stalk.py), and so are
the two a wendigo held off by fire gives (npc/ward.py).

The clip is the creature's row of forest_generator/npc_stalk.NPC_STALK_ROAR,
played through the pawn's own AnimInstance into the upper-body slot the swing
uses. What makes it stand for the length of the roar is the caller's: a time
it stores, and a Branch on it that succeeds the step without a move order.
"""

from forest_generator.npc_stalk import NPC_STALK_ROAR_BLEND_S
from npc.graph import (
    BEL, _asset_sub, _connect, _log, _loose_pin, _mesh_object, _palette, _pin, out,
)
from npc.nodes import (
    FN_ANIM_INSTANCE, FN_PLAY_SLOT, FN_STOP_MOVEMENT, NODE_CAST_CHARACTER,
)
from npc.paths import CHARACTER_CLASS_PATH, MELEE_SLOT, VOICES_VAR
from npc.sound import _author_random_sound
from npc.strafe import _author_facing


def roar_object(roar_anim):
    """The roar clip as an object path, or None when the asset pipeline has
    not produced it (asset_pipeline/import_mixamo.py): the wendigo then
    stands and roars with its voice alone."""
    if roar_anim and _asset_sub().does_asset_exist(roar_anim):
        return _mesh_object(roar_anim)
    _log(f"note: no roar clip at {roar_anim} -- run "
         f"Scripts/asset_pipeline/import_mixamo.py. The roar is sound only.")
    return None


def _author_bellow(g, exec_in, pins, roar_anim, x0, y0):
    """Stop, face the player, play the roar clip (``roar_anim``:
    roar_object()'s answer) and a voice. ``pins`` has the caller's
    ``self_pawn``, ``self_loc`` and ``player``. Returns the exec pin it ends
    on."""
    halt = g.call(FN_STOP_MOVEMENT, x0, y0)
    _connect(exec_in, _pin(halt, "execute"))
    watch, step = _author_facing(g.ed, [BEL.find_then_pin(halt)], pins["player"],
                                 x0 + 260, y0)
    g.made.extend(watch)

    # Through the pawn's own AnimInstance, as the swing is (npc/melee.py), and
    # into the same upper-body slot: the legs stand, the chest and arms roar.
    as_char = g.keep(_palette(g.ed, NODE_CAST_CHARACTER), x0 + 1960, y0)
    _connect(pins["self_pawn"], _pin(as_char, "Object"))
    _connect(step, _pin(as_char, "execute"))
    voiced = [_pin(as_char, "CastFailed", is_input=False)]
    if roar_anim:
        mesh = g.keep(g.ed.add_get_member_variable_node("Mesh", CHARACTER_CLASS_PATH),
                      x0 + 1960, y0 + 300)
        _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))
        anim = g.call(FN_ANIM_INSTANCE, x0 + 2200, y0 + 300)
        _connect(_pin(mesh, "Mesh", is_input=False), _pin(anim, "self"))
        roar = g.call(FN_PLAY_SLOT, x0 + 2460, y0, Asset=roar_anim,
                      SlotNodeName=MELEE_SLOT, BlendInTime=NPC_STALK_ROAR_BLEND_S,
                      BlendOutTime=NPC_STALK_ROAR_BLEND_S)
        _connect(out(anim), _pin(roar, "self"))
        _connect(BEL.find_then_pin(as_char), _pin(roar, "execute"))
        voiced.append(BEL.find_then_pin(roar))
    else:
        voiced.append(BEL.find_then_pin(as_char))
    join = g.branch(None, voiced, x0 + 2860, y0)
    sound, step = _author_random_sound(g.ed, VOICES_VAR, pins["self_loc"],
                                       BEL.find_then_pin(join), x0 + 3120, y0)
    g.made.extend(sound)
    return step
