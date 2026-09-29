"""finger_rig -- give a Meshy humanoid fingers: 15 bones per hand, skinned.

Meshy's rigger returns 24 bones and nothing below the wrist, and its endpoint
takes a mesh and a height and nothing else, so there is no asking it for hands.
A hand that is one bone cannot hold anything: every retargeted clip left the
fingers flat in the bind pose, and the player held a rifle in an open palm.

So the fingers are added here, in the editor, after import:

  * **Bones** go in through ``SkeletonModifier``.  Adding leaves is a
    compatible change, so the commit merges them into the creature's own
    skeleton without the merge-options dialog a restructure would raise.
  * **Where they go** is the mannequin's own finger layout, carried across in
    the hand frame palm_twist.hand_frame() measures -- finger direction, palm
    normal, and their cross product for the thumb side -- and stretched to this
    hand's measured length, width and thickness.  The frame is the same one the
    palm-roll calibration aligns in the retargeter, so a thumb placed on the
    mannequin's side of that frame is on the side the retargeted clip curls.
    It cannot come from the mesh alone: at Meshy's 30k triangles the fingers
    are a mitten, and a histogram across the hand finds no gaps to split on.
  * **Weights** are transferred from the mannequin's hand.  Each Meshy vertex
    the hand bone moves is mapped into the mannequin's hand, and its share of
    the hand is re-split the way its nearest mannequin neighbours are split
    between hand, metacarpals and fingers.  Whatever else moves it -- the
    forearm near the wrist -- is left exactly as Meshy skinned it.

Runs on every retarget and converges: missing bones are added, present ones
moved to the current layout, and the weights re-split from the same per-hand
totals.  A re-import brings back the 24-bone mesh and this puts the fingers
back.  One thing does not converge: moving a bone that already exists updates
the mesh but not the skeleton's copy, so after a layout change SK_<Creature>
keeps the old finger rest pose.  Nothing reads it (the clips carry every
track, and everything here reads the mesh's pose); a fresh import is exact.
"""

import math

import unreal

from asset_pipeline.palm_twist import _descendants, hand_frame
from asset_pipeline.retarget_paths import MANNEQUIN_MESH
from asset_pipeline.rig_chains import (
    FINGER_JOINTS, FINGERS, HANDS, mannequin_finger_bone, meshy_finger_bone,
    meshy_finger_bones,
)
from asset_pipeline.rig_util import _bone_names, _load, _log, mesh_ref_pose

# Nearest mannequin vertices blended per Meshy vertex.  One gives hard seams
# where neighbouring mannequin fingers meet; many smears a finger into the next.
TRANSFER_NEIGHBOURS = 6
# Percentiles bounding the width and thickness of a hand cloud, so a stray
# vertex (a wrist strap, a claw) does not set the scale.
EXTENT_PCT = (0.02, 0.98)
# Influence limit applied after the transfer, matching the engine default.
MAX_INFLUENCES = 8


def _skinned(mesh):
    """(bone order, [(vertex id, position, {bone: weight})]) for every vertex.

    Read through a DynamicMesh because SkinWeightModifier has no positions.
    Its ids are the mesh description's for the first N vertices, which is all
    SkinWeightModifier addresses; the few it appends past N (split seams) are
    dropped here.  _check_ids() asserts the two agree before anything is written.
    """
    order = _bone_names(mesh)
    dm = unreal.DynamicMesh()
    dm, _ = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
        mesh, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD())
    out = []
    for i in range(dm.get_vertex_count()):
        _d, w, ok = dm.get_vertex_bone_weights(i)
        if not ok or not w:
            continue
        pt, _ = dm.get_vertex_position(i)
        weights = {}
        for x in w:
            name = order[x.get_editor_property("bone_index")]
            weights[name] = weights.get(name, 0.0) + x.get_editor_property("weight")
        out.append((i, pt, weights))
    return order, out


class _Frame:
    """A hand's frame and extent: wrist, finger axis f, thumb side t, palm p.

    ``to_local``/``to_world`` convert between world positions and (a, b, c)
    along those axes.  ``scale`` holds the extents one hand is stretched by to
    lie over another.
    """

    def __init__(self, mesh, hand, cloud):
        f, p = hand_frame(mesh, hand)
        self.wrist = mesh_ref_pose(mesh)[hand][0].translation
        self.f, self.p = f, p
        t = p.cross(f)
        self.t = t * (1.0 / t.length())
        loc = sorted(self.to_local(pt) for pt in cloud)
        a = sorted(x[0] for x in loc)
        b = sorted(x[1] for x in loc)
        c = sorted(x[2] for x in loc)
        lo, hi = (int(q * (len(loc) - 1)) for q in EXTENT_PCT)
        self.length = a[hi]
        self.b0, self.width = (b[lo] + b[hi]) * 0.5, b[hi] - b[lo]
        self.c0, self.thick = (c[lo] + c[hi]) * 0.5, c[hi] - c[lo]

    def to_local(self, pt):
        d = pt - self.wrist
        return (d.dot(self.f), d.dot(self.t), d.dot(self.p))

    def to_world(self, abc):
        a, b, c = abc
        return self.wrist + self.f * a + self.t * b + self.p * c

    def carry(self, abc, onto):
        """(a, b, c) in this hand, as the same place in ``onto``."""
        a, b, c = abc
        return (a * onto.length / self.length,
                onto.b0 + (b - self.b0) * onto.width / self.width,
                onto.c0 + (c - self.c0) * onto.thick / self.thick)


def _mannequin_hand(man, suffix, hand):
    """The mannequin hand: vertex positions, each one's split of the hand
    between hand_l, metacarpals and fingers, and finger bone -> (finger, joint).
    """
    family, _order = _descendants(man, hand)
    rename = {mannequin_finger_bone(f, j, suffix): (f, j)
              for f in FINGERS for j in range(1, FINGER_JOINTS + 1)}
    _order, verts = _skinned(man)
    cloud, shares = [], []
    for _i, pt, w in verts:
        mine = {b: x for b, x in w.items() if b in family}
        total = sum(mine.values())
        if total < 0.5:
            continue
        cloud.append(pt)
        shares.append({b: x / total for b, x in mine.items()})
    return cloud, shares, rename


def _layout(man, man_frame, frame, suffix, side, hand_bone):
    """Global transforms of the finger bones, parent-first.

    The knuckle is the mannequin's carried into this hand by the stretched map,
    so it lands inside the hand.  The segments beyond it are NOT stretched:
    they are the mannequin's segment vectors under one uniform scale, because
    stretching length, width and thickness by different amounts bends a finger
    relative to the palm -- on the thick-handed wendigo it curled every bind
    finger ~35 degrees past the mannequin's, and the retargeter preserves that.
    Orientation follows the rest of the Meshy rig: Y down the bone, Z off the
    palm.
    """
    pose = mesh_ref_pose(man)
    s = frame.length / man_frame.length
    out = []
    for f in FINGERS:
        src = [man_frame.to_local(
            pose[mannequin_finger_bone(f, j, suffix)][0].translation)
            for j in range(1, FINGER_JOINTS + 1)]
        pts = [frame.to_world(man_frame.carry(src[0], frame))]
        for a, b in zip(src, src[1:]):
            pts.append(pts[-1] + frame.f * ((b[0] - a[0]) * s)
                       + frame.t * ((b[1] - a[1]) * s)
                       + frame.p * ((b[2] - a[2]) * s))
        for j, pt in enumerate(pts):
            nxt = pts[j + 1] - pt if j + 1 < len(pts) else pt - pts[j - 1]
            rot = unreal.MathLibrary.make_rot_from_yz(nxt, frame.p)
            out.append((meshy_finger_bone(f, j + 1, side),
                        hand_bone if j == 0 else meshy_finger_bone(f, j, side),
                        unreal.Transform(location=pt, rotation=rot)))
    return out


def _place_bones(mesh, bones, add):
    """Add (or, when ``add`` is False, move) the finger bones, then commit.

    Moving rather than skipping is what lets a change to the layout reach a
    mesh that already has fingers.  False if nothing needed to change.
    """
    mod = unreal.SkeletonModifier()
    if not mod.set_skeletal_mesh(mesh):
        raise RuntimeError(f"{mesh.get_name()}: SkeletonModifier refused the mesh")
    if not add and all(
            (mod.get_bone_transform(n, True).translation - xf.translation).length()
            < 0.05 for n, _p, xf in bones):
        return False
    globals_ = {}
    for name, parent, xf in bones:
        parent_xf = globals_.get(parent) or mod.get_bone_transform(parent, True)
        local = xf.make_relative(parent_xf)
        ok = (mod.add_bone(name, parent, local) if add
              else mod.set_bone_transform(name, local, False))
        if not ok:
            raise RuntimeError(f"{mesh.get_name()}: could not place {name}")
        globals_[name] = xf
    # Read back before committing: a local/global mix-up would put every finger
    # in the wrong place and still commit cleanly.
    for name, _parent, xf in bones:
        got = mod.get_bone_transform(name, True).translation
        if (got - xf.translation).length() > 0.05:
            raise RuntimeError(f"{name} landed at {got}, wanted {xf.translation}")
    if not mod.commit_skeleton_to_skeletal_mesh():
        raise RuntimeError(f"{mesh.get_name()}: skeleton commit failed")
    return True


def _side_bones(side, hand):
    """The hand bone and its 15 fingers: what the hand's weight is split over."""
    return {hand} | {meshy_finger_bone(f, j, side) for f in FINGERS
                     for j in range(1, FINGER_JOINTS + 1)}


def _transfer(man_cloud, man_shares, rename, man_frame, frame, side, hand, verts):
    """{vertex id: new weights} for every vertex the hand or its fingers move.

    The hand's share is its own weight plus any its fingers already carry, so
    a second run re-splits the same total rather than splitting a remainder.
    """
    man_local = [man_frame.to_local(pt) for pt in man_cloud]
    mine = _side_bones(side, hand)

    def meshy_name(bone):
        if bone in rename:
            f, j = rename[bone]
            return meshy_finger_bone(f, j, side)
        return hand          # hand_l itself, and the metacarpals the palm carries

    out = {}
    for vid, pt, w in verts:
        h = sum(x for b, x in w.items() if b in mine)
        if h <= 0.0:
            continue
        q = frame.carry(frame.to_local(pt), man_frame)
        near = sorted(
            ((a - q[0]) ** 2 + (b - q[1]) ** 2 + (c - q[2]) ** 2, k)
            for k, (a, b, c) in enumerate(man_local))[:TRANSFER_NEIGHBOURS]
        split, norm = {}, 0.0
        for d2, k in near:
            iw = 1.0 / (math.sqrt(d2) + 0.05)
            norm += iw
            for bone, share in man_shares[k].items():
                name = meshy_name(bone)
                split[name] = split.get(name, 0.0) + iw * share
        new = {b: x for b, x in w.items() if b not in mine}
        for name, x in split.items():
            new[name] = new.get(name, 0.0) + h * x / norm
        out[vid] = new
    return out


def _check_ids(swm, verts, mine):
    """The DynamicMesh's ids must be SkinWeightModifier's ids, or every weight
    below lands on some other vertex."""
    n = swm.get_num_vertices()
    bad = 0
    for vid, _pt, w in verts:
        h = sum(x for b, x in w.items() if b in mine)
        if vid >= n or h <= 0.0:
            continue
        got = sum(v for k, v in swm.get_vertex_weights(vid).items()
                  if str(k) in mine)
        if abs(got - h) > 0.02:
            bad += 1
    if bad:
        raise RuntimeError(f"{bad} hand vertices disagree between the "
                           "DynamicMesh and SkinWeightModifier -- ids do not match")


def ensure_fingers(mesh):
    """Give a Meshy mesh 30 skinned finger bones.

    Runs whole every time: bones are added if missing and moved if the layout
    changed, and the weights are re-split from the same hand totals, so the
    result depends on this file and the mesh, never on an earlier run.
    """
    want = meshy_finger_bones()
    have = set(_bone_names(mesh))
    present = [b for b in want if b in have]
    if present and len(present) != len(want):
        raise RuntimeError(f"{mesh.get_name()}: {len(present)} of {len(want)} "
                           "finger bones -- a half-built hand; re-import the mesh")

    man = _load(MANNEQUIN_MESH)
    _order, verts = _skinned(mesh)
    before = unreal.SkinWeightModifier()
    if not before.set_skeletal_mesh(mesh):
        raise RuntimeError(f"{mesh.get_name()}: SkinWeightModifier refused the mesh")
    verts = [v for v in verts if v[0] < before.get_num_vertices()]

    bones, weights = [], {}
    for suffix, side, man_hand, hand in HANDS:
        mine = _side_bones(side, hand)
        _check_ids(before, verts, mine)
        man_cloud, man_shares, rename = _mannequin_hand(man, suffix, man_hand)
        man_frame = _Frame(man, man_hand, man_cloud)
        cloud = [pt for _i, pt, w in verts
                 if sum(x for b, x in w.items() if b in mine) > 0.5]
        frame = _Frame(mesh, hand, cloud)
        _log(f"  {hand}: {frame.length:.1f} x {frame.width:.1f} x "
             f"{frame.thick:.1f} cm (mannequin {man_frame.length:.1f} x "
             f"{man_frame.width:.1f} x {man_frame.thick:.1f})")
        bones += _layout(man, man_frame, frame, suffix, side, hand)
        weights.update(_transfer(man_cloud, man_shares, rename, man_frame,
                                 frame, side, hand, verts))

    moved = _place_bones(mesh, bones, add=not present)

    # A fresh modifier: a skeleton commit rewrites the bone list the first one
    # was loaded against, and new bones are not in it.
    swm = unreal.SkinWeightModifier()
    swm.set_skeletal_mesh(mesh)
    names = {str(b) for b in swm.get_all_bone_names()}
    missing = [b for b in want if b not in names]
    if missing:
        raise RuntimeError(f"{mesh.get_name()}: committed but missing {missing}")
    for vid, w in weights.items():
        swm.set_vertex_weights(vid, w, True)
    swm.enforce_max_influences(MAX_INFLUENCES)
    swm.normalize_all_weights()
    if not swm.commit_weights_to_skeletal_mesh():
        raise RuntimeError(f"{mesh.get_name()}: weight commit failed")

    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh.get_editor_property("skeleton"))
    verb = "added" if not present else ("moved" if moved else "kept")
    _log(f"{mesh.get_name()}: {verb} {len(bones)} finger bones, "
         f"re-skinned {len(weights)} hand vertices")
