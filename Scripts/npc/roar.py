"""A roar: the wanderer stops, faces the player, and plays its roar clip and
one of its voices. The hunt's first pass is one (npc/stalk.py), and so are
the two a wendigo held off by fire gives (npc/ward.py).

The clip is the creature's row of forest_generator/npc_stalk.NPC_STALK_ROAR,
played into the upper-body slot the swing uses, on every machine's copy of
the body (npc/body_fx.py's Multicast_Clip; the voice is its Multicast_Voice). What makes it stand for the length of the roar is the caller's: a time
it stores, and a Branch on it that succeeds the step without a move order.
"""

from forest_generator.npc_stalk import NPC_STALK_ROAR_BLEND_S
from npc.graph import _log, _mesh_object
from uebp.graph import _assets, _connect, _pin, then
from npc.paths import MELEE_SLOT, VOICES_VAR
from Sound.play import _author_random_sound
from npc.body_fx import _author_clip, heard_by_all
from npc.strafe import _author_facing
from uebp.nodes.actor import FN_STOP_MOVEMENT


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

    # On every copy of the body, as the swing is (npc/melee.py), and into the
    # same upper-body slot: the legs stand, the chest and arms roar.
    if roar_anim:
        step = _author_clip(g.ed, g.keep, step, roar_anim, NPC_STALK_ROAR_BLEND_S, MELEE_SLOT)
    sound, step = _author_random_sound(g.ed, VOICES_VAR, pins["self_loc"], step,
                                       play=heard_by_all(g.ed))
    g.made.extend(sound)
    return step
