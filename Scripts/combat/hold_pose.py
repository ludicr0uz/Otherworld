"""The hold poses: A_HoldItem (food and water carried in the right hand),
A_HoldKnife (the knife up, ready to fight), A_HoldTorch (the stick carried
as a torch) and A_WardTorch (it held out at a creature), AnimSequences keyed
here for whatever body the player wears.

WHY NOT THE PISTOL'S POSE
-------------------------
An item's AimPose is the ready pose the slot holds while it is in hand
(weapon_component/inventory.py). The knife and the consumables used to borrow
the pistol's, MF_Pistol_Idle_ADS: both arms out at eye level, sighting down a
mushroom. No clip of a carry or a knife stance exists on this machine, so the
two poses are keyed the way knife_anim.py keys the slash.

HOW THEY ARE MADE
-----------------
Each starts from the skin's standing idle (arms hanging) at its first frame,
and sets arm bones to directions in the body's component frame (forward +Y,
left +X, up +Z; body_pose.py), exactly as body_pose's guard does: the bone's
line to its child is swung onto the wanted direction by the shortest turn,
so the palm keeps facing the thigh. The right hand then takes the pistol
pose's orientation in the body and its fingers, closed round a grip: the item
stands upright and faces ahead in the fist, and grip._grip_rotation and
_grip_location solve against these poses to the pistol's own answer (a hand
left on the turned forearm rolled the fist ~90 deg and put the canteen's neck
across the fingers).

    A_HoldItem   the right upper arm hangs, the forearm comes forward at the
                 waist: an item carried in front, the left arm at the side
    A_HoldKnife  a fighting stance: the right elbow before the ribs, the
                 forearm rising so the knife is at the chest, blade up; the
                 left fist up before the chin as a guard
    A_HoldTorch  the stick carried as a torch: the right elbow out from the
                 ribs, the forearm rising, so the fist is at the shoulder
                 and the fire beside the head, clear of the face
    A_WardTorch  the torch held out (the use key, weapon_component/torch.py):
                 the right arm straight ahead at the shoulder's height, the
                 fire at arm's length between the player and what they face

Constant clips (a held pose, as the ADS poses are). The slash
(knife_anim.py) is keyed off A_HoldKnife, so it starts and ends in it.
"""

import unreal

from asset_pipeline.rig_util import mesh_ref_pose, visible_bone_xf
from combat.body_pose import CLAVICLE_DIR, _between, _conj, _mul, _norm
from combat.log import _log
from uebp.graph import _assets
from combat.paths import (
    HOLD_ITEM_ANIM_PATH, HOLD_KNIFE_ANIM_PATH, HOLD_TORCH_ANIM_PATH,
    WARD_TORCH_ANIM_PATH,
)

FPS = 30
FRAMES = 30

# {role: direction of the bone's line to its child}, body frame. Roles are
# PlayerSkin.pose_bones'; a role left out keeps the idle's. Each turned arm
# starts at its clavicle, put straight out to the side as body_pose's guard
# puts it (CLAVICLE_DIR), so the arm starts where the shoulder is on any rig.
CLAVICLE_R = (-CLAVICLE_DIR[0], CLAVICLE_DIR[1], CLAVICLE_DIR[2])
HOLD_ITEM_DIRS = {
    "clavicle_r": CLAVICLE_R,
    "upperarm_r": (-0.10, 0.20, -0.97),
    "forearm_r": (0.15, 0.92, -0.36),
}
HOLD_KNIFE_DIRS = {
    "clavicle_r": CLAVICLE_R,
    "clavicle_l": CLAVICLE_DIR,
    "upperarm_r": (-0.20, 0.45, -0.87),
    "forearm_r": (0.10, 0.88, 0.46),
    "upperarm_l": (0.10, 0.50, -0.86),
    "forearm_l": (-0.20, 0.40, 0.89),
}
HOLD_TORCH_DIRS = {
    "clavicle_r": CLAVICLE_R,
    "upperarm_r": (-0.45, 0.35, -0.82),
    "forearm_r": (-0.15, 0.55, 0.82),
}
WARD_TORCH_DIRS = {
    "clavicle_r": CLAVICLE_R,
    "upperarm_r": (-0.10, 0.99, 0.10),
    "forearm_r": (0.05, 0.98, 0.20),
}
CHILD = {"clavicle": "upperarm", "upperarm": "forearm", "forearm": "hand"}

HOLD_POSES = ((HOLD_ITEM_ANIM_PATH, HOLD_ITEM_DIRS),
              (HOLD_KNIFE_ANIM_PATH, HOLD_KNIFE_DIRS),
              (HOLD_TORCH_ANIM_PATH, HOLD_TORCH_DIRS),
              (WARD_TORCH_ANIM_PATH, WARD_TORCH_DIRS))


def _q(rot):
    return (rot.x, rot.y, rot.z, rot.w)


def _shown(anim, mesh, ref):
    """{bone: (location, quat, local Transform)}, component space, at the
    clip's first frame as SHOWN on ``mesh``: a retargeted clip drops the
    tracks that repeat the reference pose (the idle's arms among them), and
    the mesh fills them."""
    xf = visible_bone_xf(anim, mesh, ref)
    out = {}
    for bone, (_rest, parent) in ref.items():
        t = xf(bone)
        local = t.make_relative(xf(parent)) if parent else t
        out[bone] = ((t.translation.x, t.translation.y, t.translation.z),
                     _q(t.rotation), local)
    return out


def _copy_of(src_path, dst_path):
    """The clip asset, a copy of ``src_path`` on first build. Reused afterwards
    (a just-written asset cannot be deleted in the same editor session),
    unless the worn skeleton changed under it."""
    eal = unreal.EditorAssetLibrary
    src = _assets().load_asset(src_path)
    if eal.does_asset_exist(dst_path):
        clip = _assets().load_asset(dst_path)
        if clip.get_editor_property("skeleton") == src.get_editor_property("skeleton"):
            return clip
        # Minutes per clip (the editor walks every reference to it):
        # asset_pipeline/swap_player_body.py clears these before the build.
        _log(f"note: {dst_path} is keyed on another body's skeleton: deleting "
             "it through the editor, which is slow")
        if not eal.delete_asset(dst_path):
            raise RuntimeError(f"{dst_path} is on another skeleton and could not "
                               "be deleted; restart the editor")
    clip = eal.duplicate_asset(src_path, dst_path)
    if clip is None:
        raise RuntimeError(f"could not copy {src_path} to {dst_path}")
    return clip


def hold_rotations(skin, dirs, comp):
    """{bone: new component-space quat} for the arm bones ``dirs`` names,
    against a component pose ``comp`` ({bone: (location, quat)}). Pure."""
    bones = skin.pose_bones
    out = {}
    for role, want in dirs.items():
        kind, side = role.rsplit("_", 1)
        bone, child = bones[role], bones[f"{CHILD[kind]}_{side}"]
        along = _norm(tuple(c - p for c, p in zip(comp[child][0], comp[bone][0])))
        out[bone] = _mul(_between(along, _norm(want)), comp[bone][1])
    return out


def _below(ref, bone, ancestor):
    parent = ref[bone][1]
    while parent:
        if parent == ancestor:
            return True
        parent = ref[parent][1]
    return False


def _local_rotations(skin, dirs, idle, pistol):
    """{bone: local Transform}: the idle's tracks, the turned arms, and the
    right hand's fingers as the pistol pose shows them."""
    mesh = _assets().load_asset(skin.mesh)
    ref = mesh_ref_pose(mesh)
    comp, fist = _shown(idle, mesh, ref), _shown(pistol, mesh, ref)
    turned = hold_rotations(skin, dirs, comp)
    hand = skin.pose_bones["hand_r"]
    # The hand keeps the pistol pose's orientation in the body: whatever it
    # holds stands upright and faces ahead, seated as the pistol's grip is.
    turned[hand] = fist[hand][1]
    fingers = {b for b in ref if _below(ref, b, hand)}
    # Track names are FNames and can come back in another case than the bones.
    by_lower = {b.lower(): b for b in ref}
    # ...and a track for a bone this mesh does not have (a corrective bone of
    # the mannequin's full skeleton, on a body bound to its simple mesh's 89)
    # is left out.
    keyed = ({by_lower[str(n).lower()]
              for n in idle.data_model_interface.get_bone_track_names()
              if str(n).lower() in by_lower}
             | set(turned) | fingers)
    out = {}
    for bone in keyed:
        parent = ref[bone][1]
        if bone in fingers:
            out[bone] = fist[bone][2]
            continue
        here = turned.get(bone, comp[bone][1])
        up = turned.get(parent, comp[parent][1]) if parent else (0.0, 0.0, 0.0, 1.0)
        local = comp[bone][2]
        out[bone] = unreal.Transform(location=local.translation,
                                     rotation=unreal.Quat(*_mul(_conj(up), here)).rotator(),
                                     scale=local.scale3d)
    return out


def _key_constant(clip, xfs):
    """Make ``clip`` a held pose: {track: local Transform}, the same on every
    frame, in place of whatever tracks it had; saved."""
    n = FRAMES + 1
    ctrl = clip.controller
    ctrl.open_bracket(unreal.Text("Key a hold pose"), False)
    ctrl.remove_all_bone_tracks(False)
    ctrl.set_frame_rate(unreal.FrameRate(FPS, 1), False)
    ctrl.set_number_of_frames(unreal.FrameNumber(FRAMES), False)
    for track, xf in sorted(xfs.items()):
        if not ctrl.add_bone_curve(track, False):
            raise RuntimeError(f"could not add a track for {track}")
        if not ctrl.set_bone_track_keys(track, [xf.translation] * n, [xf.rotation] * n,
                                        [xf.scale3d] * n, False):
            raise RuntimeError(f"could not key {track}")
    ctrl.close_bracket(False)
    _assets().save_loaded_asset(clip, False)


def _build_one(skin, path, dirs):
    idle = _assets().load_asset(skin.idle)
    pistol = _assets().load_asset(skin.aim_pistol)
    if idle is None or pistol is None:
        raise RuntimeError(f"could not load {skin.idle} or {skin.aim_pistol}")
    rots = _local_rotations(skin, dirs, idle, pistol)
    clip = _copy_of(skin.idle, path)
    _key_constant(clip, rots)
    _log(f"built {path} ({len(rots)} tracks off {skin.idle.rsplit('/', 1)[-1]}, "
         f"turned {sorted(dirs)})")
    return clip


def build_hold_poses(skin):
    """Key every hold pose (HOLD_POSES) for ``skin``'s body; returns
    {path: clip}."""
    return {path: _build_one(skin, path, dirs) for path, dirs in HOLD_POSES}
