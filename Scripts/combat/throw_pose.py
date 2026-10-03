"""A_ThrowReady: the arm cocked, ready to throw, which the player holds while
the throw key is down (weapon_component/throw_ready.py).

It is the throw's own clip (PlayerSkin.throw, Quaternius UAL2's OverhandThrow)
stopped at THROW_READY_S, where its hand is furthest back: every track of the
clip keyed to its value at that moment, on every frame. The click then plays
the clip on from that moment (throw_windup.py), so the arm goes forward out
of the pose it was waiting in, with no step between the two.

Sampled track by track, not as shown: the copy keeps the clip's own tracks,
so whatever the clip leaves to the mesh's reference pose the copy does too.

A skin with no throw clip (the mannequin) has no ready pose either: the
variable stays None and the arm stays where it was.
"""

import unreal

from combat.log import _log
from uebp.graph import _assets
from combat.hold_pose import _copy_of, _key_constant
from combat.paths import THROW_READY_ANIM_PATH
from combat.throw_tuning import THROW_READY_S


def build_throw_ready(skin):
    """Key A_ThrowReady for ``skin``; returns the clip, or None without a
    throw clip to take it from."""
    if not skin.throw:
        _log("note: no throw clip on this skin, so no ready-to-throw pose")
        return None
    src = _assets().load_asset(skin.throw)
    if src is None:
        raise RuntimeError(f"could not load {skin.throw}")
    lib = unreal.AnimationLibrary
    tracks = [str(n) for n in src.data_model_interface.get_bone_track_names()]
    # Read off the source before the copy is touched: on a rebuild the copy
    # already exists, and is re-keyed in place.
    xfs = {t: lib.get_bone_pose_for_time(src, t, THROW_READY_S, False) for t in tracks}
    clip = _copy_of(skin.throw, THROW_READY_ANIM_PATH)
    _key_constant(clip, xfs)
    _log(f"built {THROW_READY_ANIM_PATH} ({len(xfs)} tracks of "
         f"{skin.throw.rsplit('/', 1)[-1]} at {THROW_READY_S:.3f} s)")
    return clip
