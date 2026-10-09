"""The player's crouch, prone and guard poses: procedural bone turns in the
player's anim BP, blended in by four weights the weapon component writes.

WHY PROCEDURAL
--------------
There is no guard clip. The crouch and the crawl now have clips (the
Quaternius Universal Animation Library's, stance_clips.py) wherever the rig
has them retargeted (PlayerSkin.stance_clips); the mannequin fallback, and an
adventurer before import_quaternius.py has run, still pose both here. What
the AnimGraph can take is Transform (Modify) Bone nodes (aim_pitch.py does
the same for the sights' pitch), so each pose is a handful of them, every one
with its Alpha driven by one weight:

    PoseCrouch  hips down, thighs forward, shins back, feet flat again, the
                back leaning forward and the chest back upright
    PoseProne   hips tipped face down and lowered to the ground, the chest
                propped up, the arms and head brought back level
    GuardArms   empty hands, a pistol or a consumable: both arms up, fists in
                front of the face (upper arms and forearms REPLACED)
    GuardGun    a two-handed gun: the chest turns left and leans back so the
                gun comes up across the body; the neck turns back, so the head
                keeps looking ahead

A weight of 0 skips its nodes entirely, so standing costs nothing.

WITH THE CLIPS the crouch is all clip, and the prone is the crawl with its
hips lifted, since the clip's lie under the feet's root:

    PoseProne     to PRONE_HIPS_CM, lying still
    ProneMoving   PoseProne x Move, a product rather than a variable: 15 cm
                  more while crawling, because the kick drops the knees 28 cm
                  under the hips

Move is clamp(GroundSpeed / MOVE_FULL_CM_S, 0, 1), the same the clips'
still-or-walking blends read (stance_clips.py). A held gun needs nothing more:
the aim layer blends in mesh space over four spine joints (anim_blueprint.py),
so the chest comes out propped between the crawl's face-down one and the
aim's upright one, and the arms and head keep the aim's level. Tipping it
further (as the procedural prone does to a standing chest) drove the
shoulders into the ground: the hands measured 2 cm up in game, against 33
without it (probes/probe_stance_clips.py).

HOW THE ANGLES ARE STATED
-------------------------
Every turn is component-space and is built here from what it should DO --
"swing the thigh's downward line forward by 72 degrees" -- as the rotation
between two directions (_between), then handed to the node as a rotator. The
component's frame is the body's (the mesh is yawed 270, PlayerSkin.mesh_yaw):
forward is +Y, left is +X, up is +Z. Nothing depends on a bone's local axes,
so the same table poses the mannequin fallback.

The crouch's hip drop is not a guess either: the two leg turns are replayed
on the skeleton's own leg, and the hips go down by exactly as much as that
lifted the foot, so the feet stay on the ground.

Two kinds of turn keep a held gun in both hands: one bone (the chest) turned
alone, since both arms hang off it; or both clavicles turned about the
left-right axis, since the two pivots then lie on the axis line.

WHERE IT SITS
-------------
Between the aim pitch's LocalToComponent and its two spine ModifyBones:

    LocalToComponent -> guard (arms, gun) -> crouch -> prone -> AimPitch x2
        -> ComponentToLocal -> Output

The guard comes first so the prone's hip turn carries the guarded arms with
it; the aim pitch comes last so it pitches whatever the body is doing. Run
after patch_aim_pitch, which owns the space conversions around it. A node of
this module is recognised by its driven Alpha (the aim pitch's is a literal).
"""

from uebp.vars import declare
from combat import anim_vars as AN
import math

import unreal

from asset_pipeline.rig_util import _bone_world

from combat.aim_pitch import MODIFY_BONE_CLASS, _feeding_all, _nodes_of
from combat.log import _log
from uebp.graph import (
    BEL, BGE, PIN, _assets, _connect, _node, _palette, _pin, _set, out,
)
from uebp.layout import arrange
from uebp.nodes.math import FN_CLAMP, FN_MAKE_ROT, FN_MAKE_VECTOR, FN_MUL_FF
from uebp.nodes.palette import NODE_MODIFY_BONE

POSE_CROUCH = AN.PoseCrouch
POSE_PRONE = AN.PoseProne
GUARD_ARMS = AN.GuardArms
GUARD_GUN = AN.GuardGun
POSE_WEIGHTS = AN.POSE_WEIGHTS
# How fast a weight follows its target (FInterpTo speed, 1/s): a stance or a
# guard settles in about a fifth of a second.
POSE_BLEND_SPEED = 12.0
# The kneel over a body being searched (stance_clips.py blends the clip in by
# PoseKneel and holds it at KneelTime; pose_weights.py writes both). Not one
# of POSE_WEIGHTS: no ModifyBone reads it, and going down on a knee takes
# longer than a guard does: about half a second.
POSE_KNEEL = AN.PoseKneel
KNEEL_TIME = AN.KneelTime
KNEEL_BLEND_SPEED = 5.0
# The stretch of the kneel clip in which the body is down and the hands work
# (it kneels before it, and stands after): KneelTime runs up and back down it.
KNEEL_FROM_S, KNEEL_TO_S = 1.0, 3.9

# Crouch: the thigh swings forward of hanging straight down by the first, the
# shin back by the second -- a squat with the knees over the toes. The hip
# drop follows from the leg (see _crouch_legs). The lower spine leans forward
# for balance and the chest leans back by as much, so the arms stay level.
CROUCH_THIGH_DEG = 90.0
CROUCH_SHIN_DEG = 45.0
CROUCH_LEAN_DEG = 20.0
# Prone: the hips' height above the ground, lying (half a torso's depth), and
# how far the chest is propped up off the ground.
PRONE_HIPS_CM = 16.0
PRONE_CHEST_LIFT_DEG = 30.0
# With the crawl clip: its hips are lifted from where the clip has them
# (crawl_hips_z: measured off the worn body's own retargeted clip, -7.5 on the
# dressed adventurer, -8.0 on the one in boxers) to PRONE_HIPS_CM lying still
# and this much higher crawling, where the kick drops the knees 28 cm under
# the hips: they then just clear the ground.
PRONE_CRAWL_LIFT_CM = 15.0
# A weight that is not a variable (see WITH THE CLIPS above).
PRONE_MOVING = "ProneMoving"
# The ground speed (cm/s) at which the walking clips have fully taken over
# from the still ones: a crawl is 120 and a crouched walk 270, so either is all
# walk once under way, and a stop settles back within a step.
MOVE_FULL_CM_S = 60.0
GROUND_SPEED = AN.GroundSpeed
# The fists-up guard, as the LEFT arm's directions in the body frame
# (+X left, +Y forward, +Z up); the right arm mirrors X. The elbow hangs in
# front of the ribs and the forearm rises to put the fist before the chin.
# The clavicle first, straight out to the side: a generated body's shoulders
# sit where its rigger put them (the adventurer in boxers has them 13 cm
# behind the spine, its clavicles 39 degrees back), and an arm turned from
# there falls short of the face. On a rig whose clavicles already point
# sideways it changes next to nothing.
CLAVICLE_DIR = (1.0, 0.0, 0.0)
GUARD_UPPERARM_DIR = (-0.05, 0.45, -0.89)
GUARD_FOREARM_DIR = (-0.10, 0.40, 0.91)
# The two-handed guard: the chest turns left by this, then leans back by this.
GUARD_GUN_TURN_DEG = 60.0
GUARD_GUN_LEAN_DEG = 15.0

UP, DOWN, FORWARD = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)
ADDITIVE = unreal.BoneModificationMode.BMM_ADDITIVE
REPLACE = unreal.BoneModificationMode.BMM_REPLACE
IGNORE = unreal.BoneModificationMode.BMM_IGNORE


# ─── quaternion arithmetic, (x, y, z, w), the engine's convention ───────────

def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _mul(a, b):
    """a * b: turn by b, then by a (FQuat's order)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _conj(q):
    return (-q[0], -q[1], -q[2], q[3])


def _turn(q, v):
    x, y, z, _w = _mul(_mul(q, (v[0], v[1], v[2], 0.0)), _conj(q))
    return (x, y, z)


def _between(a, b):
    """The shortest turn taking direction ``a`` onto direction ``b``."""
    a, b = _norm(a), _norm(b)
    dot = max(-1.0, min(1.0, sum(p * q for p, q in zip(a, b))))
    axis = _cross(a, b)
    if math.sqrt(sum(c * c for c in axis)) < 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    axis, half = _norm(axis), math.acos(dot) / 2.0
    s = math.sin(half)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(half))


def _swing(start, end_dir, deg):
    """Turn ``start`` by ``deg`` towards ``end_dir`` (both unit, orthogonal)."""
    r = math.radians(deg)
    return _between(start, tuple(math.cos(r) * s + math.sin(r) * e
                                 for s, e in zip(start, end_dir)))


def _rotator(q):
    r = unreal.Quat(*q).rotator()
    return (r.pitch, r.yaw, r.roll)


# ─── the plan: which bone turns how, under which weight ─────────────────────

def _ref(skeleton):
    """{bone: (location, quat)} in component space, the skeleton's reference."""
    pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    out = {}
    for b in unreal.AnimPoseExtensions.get_bone_names(pose):
        t = unreal.AnimPoseExtensions.get_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD)
        loc, rot = t.translation, t.rotation
        out[str(b)] = ((loc.x, loc.y, loc.z), (rot.x, rot.y, rot.z, rot.w))
    return out


def _dist(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def _crouch_legs(ref, bones, thigh, calf):
    """(hip drop, feet ahead of the hips) in cm, for the crouch's leg turns.

    Replayed on the skeleton's own leg rather than taken from the textbook
    L1 (1 - cos A) + L2 (1 - cos S): a reference leg is never quite straight,
    and the formula left the feet 4 cm in the air. Averaged over both legs.
    """
    drops, leads = [], []
    for side in "lr":
        hip, knee, ankle = (ref[bones[f"{k}_{side}"]][0]
                            for k in ("thigh", "calf", "foot"))
        knee2 = tuple(h + o for h, o in zip(hip, _turn(thigh, tuple(
            k - h for k, h in zip(knee, hip)))))
        ankle2 = tuple(k + o for k, o in zip(knee2, _turn(_mul(calf, thigh), tuple(
            a - k for a, k in zip(ankle, knee)))))
        drops.append(ankle2[2] - ankle[2])
        leads.append(ankle2[1] - ankle[1])
    return sum(drops) / 2.0, sum(leads) / 2.0


def _guard_arm(ref, bones, side):
    """The three REPLACE rotations that put one arm in the fists-up guard."""
    mirror = 1.0 if side == "l" else -1.0
    out = []
    for role, child, want in (("clavicle", "upperarm", CLAVICLE_DIR),
                              ("upperarm", "forearm", GUARD_UPPERARM_DIR),
                              ("forearm", "hand", GUARD_FOREARM_DIR)):
        at, rot = ref[bones[f"{role}_{side}"]]
        along = _norm(tuple(c - p for c, p in zip(ref[bones[f"{child}_{side}"]][0], at)))
        target = (want[0] * mirror, want[1], want[2])
        out.append((bones[f"{role}_{side}"], REPLACE, _mul(_between(along, target), rot)))
    return out


def pose_plan(skin, ref):
    """[(weight, bone, rotation mode, quat or None, translation or None)], in
    chain order. Pure: the verifier recomputes it and compares the graph."""
    b = skin.pose_bones
    steps = []
    for bone, mode, q in _guard_arm(ref, b, "l") + _guard_arm(ref, b, "r"):
        steps.append((GUARD_ARMS, bone, mode, q, None))

    chest_turn = _between(FORWARD, (math.sin(math.radians(GUARD_GUN_TURN_DEG)),
                                    math.cos(math.radians(GUARD_GUN_TURN_DEG)), 0.0))
    ahead = _turn(chest_turn, FORWARD)
    chest = _mul(_swing(ahead, UP, GUARD_GUN_LEAN_DEG), chest_turn)
    steps.append((GUARD_GUN, skin.aim_bones[-1], ADDITIVE, chest, None))
    steps.append((GUARD_GUN, b["neck"], ADDITIVE, _conj(chest), None))

    if skin.stance_clips:
        return steps + _prone_on_clip(b, crawl_hips_z(skin))

    thigh = _swing(DOWN, FORWARD, CROUCH_THIGH_DEG)
    # The shin, carried forward by the thigh, swings back to S behind vertical.
    shin = math.radians(CROUCH_SHIN_DEG)
    calf = _between(_turn(thigh, DOWN), (0.0, -math.sin(shin), -math.cos(shin)))
    # The hips go down until the feet are back on the ground, and back by half
    # the feet's lead, so the feet and the hips straddle the capsule's centre.
    drop, lead = _crouch_legs(ref, b, thigh, calf)
    steps.append((POSE_CROUCH, b["hips"], IGNORE, None, (0.0, -lead / 2.0, -drop)))
    lean = _swing(UP, FORWARD, CROUCH_LEAN_DEG)
    steps.append((POSE_CROUCH, b["spine"], ADDITIVE, lean, None))
    steps.append((POSE_CROUCH, skin.aim_bones[-1], ADDITIVE, _conj(lean), None))
    for side in "lr":
        steps.append((POSE_CROUCH, b[f"thigh_{side}"], ADDITIVE, thigh, None))
        steps.append((POSE_CROUCH, b[f"calf_{side}"], ADDITIVE, calf, None))
        steps.append((POSE_CROUCH, b[f"foot_{side}"], ADDITIVE,
                      _conj(_mul(calf, thigh)), None))

    hips_z = ref[b["hips"]][0][2]
    steps.append((POSE_PRONE, b["hips"], ADDITIVE, _between(UP, FORWARD),
                  (0.0, 0.0, PRONE_HIPS_CM - hips_z)))
    steps.append((POSE_PRONE, b["spine"], ADDITIVE,
                  _swing(FORWARD, UP, PRONE_CHEST_LIFT_DEG), None))
    level = _swing(FORWARD, UP, 90.0 - PRONE_CHEST_LIFT_DEG)
    for bone in (b["clavicle_l"], b["clavicle_r"], b["neck"]):
        steps.append((POSE_PRONE, bone, ADDITIVE, level, None))
    return steps


def crawl_hips_z(skin):
    """Where the crawl clip carries the hips (cm, component space): the middle
    of what they sweep through the stroke, read off the worn body's own clip."""
    clip = unreal.EditorAssetLibrary.load_asset(skin.prone_crawl)
    if clip is None:
        raise RuntimeError(f"could not load the crawl clip {skin.prone_crawl}")
    length = clip.get_editor_property("sequence_length")
    zs = [_bone_world(clip, skin.pose_bones["hips"], length * i / 16.0).z
          for i in range(17)]
    return round((min(zs) + max(zs)) / 2.0, 2)


def _prone_on_clip(b, hips_z):
    """The prone's corrections on the crawl clip (stance_clips.py): lift the
    hips onto the ground, and higher while crawling."""
    return [(POSE_PRONE, b["hips"], IGNORE, None,
              (0.0, 0.0, PRONE_HIPS_CM - hips_z)),
             (PRONE_MOVING, b["hips"], IGNORE, None, (0.0, 0.0, PRONE_CRAWL_LIFT_CM))]


# ─── authoring ───────────────────────────────────────────────────────────────

def _mine(ed):
    """This module's ModifyBones: the ones whose Alpha is driven."""
    return [n for n in _nodes_of(ed, MODIFY_BONE_CLASS)
            if PIN.list_connected_pins(_pin(n, "Alpha"))]


def _downstream(pose_out):
    fed = PIN.list_connected_pins(pose_out)
    return fed[0] if fed else None


def _remove_previous(ed, start_out):
    """Take out an earlier run's chain and join its two ends again."""
    mine = _mine(ed)
    if not mine:
        return
    names = {n.get_name() for n in mine}
    nxt = _downstream(start_out)
    while nxt is not None and PIN.get_owning_node(nxt).get_name() in names:
        nxt = _downstream(out(PIN.get_owning_node(nxt), "Pose"))
    ed.remove_nodes(mine + _feeding_all(mine))
    if nxt is None:
        raise RuntimeError("an earlier body-pose chain fed nothing; refusing to "
                           "guess where the pose goes")
    _connect(start_out, nxt)


def _modify_bone(ed, step, weight_pins):
    weight, bone, mode, quat, move = step
    mb = _palette(ed, NODE_MODIFY_BONE)
    inner = mb.get_editor_property("node")
    ref = unreal.BoneReference()
    ref.set_editor_property("bone_name", bone)
    inner.set_editor_property("bone_to_modify", ref)
    inner.set_editor_property("rotation_mode", mode)
    inner.set_editor_property("rotation_space", unreal.BoneControlSpace.BCS_COMPONENT_SPACE)
    inner.set_editor_property("translation_mode", ADDITIVE if move else IGNORE)
    inner.set_editor_property("translation_space",
                              unreal.BoneControlSpace.BCS_COMPONENT_SPACE)
    mb.set_editor_property("node", inner)
    back = mb.get_editor_property("node")
    if (str(back.get_editor_property("bone_to_modify").get_editor_property("bone_name"))
            != bone or back.get_editor_property("rotation_mode") != mode):
        raise RuntimeError(f"the ModifyBone on {bone} did not keep its settings")

    _connect(weight_pins[weight], _pin(mb, "Alpha"))
    if quat is not None:
        rot = _node(ed, FN_MAKE_ROT)
        pitch, yaw, roll = _rotator(quat)
        _set(rot, "Pitch", round(pitch, 4))
        _set(rot, "Yaw", round(yaw, 4))
        _set(rot, "Roll", round(roll, 4))
        _connect(out(rot), _pin(mb, "Rotation"))
    if move is not None:
        vec = _node(ed, FN_MAKE_VECTOR)
        for axis, value in zip("XYZ", move):
            _set(vec, axis, round(value, 3))
        _connect(out(vec), _pin(mb, "Translation"))
    return mb


def move_alpha(ed):
    """clamp(GroundSpeed / MOVE_FULL_CM_S, 0, 1), as a pin."""
    speed = ed.add_get_member_variable_node(GROUND_SPEED)
    scaled = _node(ed, FN_MUL_FF)
    _connect(out(speed, GROUND_SPEED), _pin(scaled, "A"))
    _set(scaled, "B", 1.0 / MOVE_FULL_CM_S)
    clamp = _node(ed, FN_CLAMP)
    _connect(out(scaled), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", 1.0)
    return out(clamp)


def _prone_moving(ed, prone_pin):
    """ProneMoving: PoseProne x Move."""
    move = move_alpha(ed)
    product = _node(ed, FN_MUL_FF)
    _connect(move, _pin(product, "A"))
    _connect(prone_pin, _pin(product, "B"))
    return out(product)


def patch_body_pose(skin):
    """Insert the guard, crouch and prone poses before the aim pitch in
    ``skin``'s anim BP. Re-running replaces the previous chain."""
    bp = _assets().load_asset(skin.anim_bp)
    if not bp:
        raise RuntimeError(f"could not load {skin.anim_bp}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    to_cs = _nodes_of(ed, "AnimGraphNode_LocalToComponentSpace") if ed else []
    if len(to_cs) != 1:
        raise RuntimeError(f"{skin.anim_bp}: expected the aim pitch's one "
                           f"LocalToComponent, found {len(to_cs)} -- run "
                           "patch_aim_pitch first")
    start_out = out(to_cs[0], "ComponentPose")
    skeleton = bp.get_editor_property("target_skeleton")
    ref = _ref(skeleton)
    wanted = set(skin.pose_bones.values()) | {skin.aim_bones[-1]}
    missing = sorted(b for b in wanted if b not in ref)
    if missing:
        raise RuntimeError(f"{skeleton.get_name()} has no {missing}")

    _remove_previous(ed, start_out)
    declare(ed, AN.POSE)
    tail = _downstream(start_out)
    if tail is None:
        raise RuntimeError("the LocalToComponent feeds nothing")
    PIN.break_pin_links(start_out)

    plan = pose_plan(skin, ref)
    # Only the weights the plan reads: with the stance clips nothing reads
    # PoseCrouch here, and a getter feeding nothing would be left behind by
    # every rerun (_remove_previous finds nodes by what they feed).
    used = {step[0] for step in plan} | ({POSE_PRONE} if skin.stance_clips else set())
    weight_pins, made = {}, []
    for name in (w for w in POSE_WEIGHTS if w in used):
        get = ed.add_get_member_variable_node(name)
        weight_pins[name] = out(get, name)
        made.append(get)
    if skin.stance_clips:
        weight_pins[PRONE_MOVING] = _prone_moving(ed, weight_pins[POSE_PRONE])
    pose = start_out
    for step in plan:
        mb = _modify_bone(ed, step, weight_pins)
        _connect(pose, _pin(mb, "ComponentPose"))
        pose = out(mb, "Pose")
        made.append(mb)
    _connect(pose, tail)
    ed.add_comment_to_nodes(
        "The procedural poses, each weight (0..1, written by BP_WeaponComponent) "
        f"driving its ModifyBones' Alpha: {GUARD_ARMS} fists up, {GUARD_GUN} "
        f"the gun across the body, {POSE_CROUCH}, {POSE_PRONE} (with the stance "
        f"clips: the crawl's lift, more by {PRONE_MOVING} while crawling). "
        "See Scripts/combat/body_pose.py.", made)

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{skin.anim_bp} failed to compile after the body poses")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: {len(plan)} ModifyBones for "
         f"{', '.join(POSE_WEIGHTS)} before the aim pitch")
    return bp
