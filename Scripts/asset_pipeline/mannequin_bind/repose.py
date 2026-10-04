"""repose -- turn the body's limbs onto the mannequin's lines.

WHY THE MESH MOVES AND NOT THE BONES
------------------------------------
A clip is a local rotation per bone, and what a rotation does depends on the
pose it is applied over.  The mannequin's clips are keyed over the mannequin's
reference pose.  A body bound to the mannequin's skeleton in its OWN pose --
arms a little higher, elbows straighter -- carries that difference into every
frame of every clip: it is the retarget-pose problem (retarget_rig.py), moved
from the retargeter into the mesh.

So before it is bound the body is put in the mannequin's pose, by its own rig:
each limb bone is turned so that the line to its child lies along the
mannequin's, and the vertices follow through Meshy's weights exactly as they
would in a clip.  After that the mannequin's reference rotations are true of
this body, and no clip needs correcting.

WHAT IS TURNED
--------------
    upper arm, forearm, thigh, calf   swung the shortest way onto the line
    hand    its whole frame (hand_frame.py): finger direction onto the
            mannequin's and palm onto the mannequin's palm.  The part of that
            turn that is a roll about the forearm is not made at the wrist: it
            is spread down the forearm, none at the elbow and all of it at the
            wrist, the way a forearm pronates.  Generated bodies come palms
            forward and the mannequin's face its thighs, so the roll is around
            130 degrees -- at one joint that is a wrung wrist.
    foot    turned about the vertical only, toes onto the mannequin's heading,
            and it does NOT inherit the calf's turn: a foot that followed the
            shin would stand on its edge
    trunk, neck, head, clavicles      left alone.  Where a rigger sets a spine
            or a clavicle joint inside a torso is its choice, not the body's
            posture, and turning the mesh to agree with it would bend a chest
            that was standing straight.

A child starts from its parent's turn, so a limb moves as one piece and each
joint adds only what its own segment is off by.
"""

from dataclasses import dataclass, field

from asset_pipeline.mannequin_bind import hand_frame, lbs
from asset_pipeline.mannequin_bind.bone_map import FEET, HANDS, LIMBS
from asset_pipeline.mannequin_bind.xform import (
    IDENTITY, add, angle_deg, axis_angle, conj, dot, frame_turn, mul, qnorm,
    sub, swing, turn, unit)

# How many steps the forearm's roll is spread over.  Neighbouring steps differ
# by a fifth of the roll, about 25 degrees: a blend of two rotations that
# close loses a few percent of the forearm's girth, where a blend across the
# whole roll would pinch it to a waist.
TWIST_STEPS = 6


@dataclass
class Repose:
    rot: dict                    # Meshy bone -> its turn from the rest pose
    joints: dict                 # Meshy bone -> where its joint ends up
    turned: dict = field(default_factory=dict)   # bone -> degrees it added
    hands: dict = field(default_factory=dict)    # suffix -> hand measurements
    twists: dict = field(default_factory=dict)   # forearm bone -> (axis, degrees)
    notes: list = field(default_factory=list)


def _step(bone, k):
    return f"{bone}#{k}"


def split_twist(q, axis):
    """``q`` as (swing, degrees of twist about ``axis``): q = swing * twist."""
    along = dot(q[:3], axis)
    twist = qnorm((axis[0] * along, axis[1] * along, axis[2] * along, q[3]))
    if twist[3] < 0:
        twist = tuple(-c for c in twist)
    degrees = angle_deg(twist) * (1.0 if dot(twist[:3], axis) >= 0 else -1.0)
    return mul(q, conj(twist)), degrees


def graded(body, pose):
    """(weights, moves) for skinning the repose: a forearm that rolls is
    split into TWIST_STEPS steps along its length, each rolled a share more."""
    moves = {b: lbs.about(pose.rot[b], body.joints[b], pose.joints[b])
             for b in body.bones}
    if not pose.twists:
        return body.weights, moves
    ends = {}
    for bone, (axis, degrees) in pose.twists.items():
        child = LIMBS[bone][0]
        ends[bone] = (body.joints[bone], sub(body.joints[child], body.joints[bone]))
        for k in range(TWIST_STEPS):
            share = k / (TWIST_STEPS - 1.0)
            q = mul(axis_angle(axis, degrees * share), pose.rot[bone])
            moves[_step(bone, k)] = lbs.about(q, body.joints[bone], pose.joints[bone])
    weights = []
    for v, w in zip(body.verts, body.weights):
        if not any(b in w for b in ends):
            weights.append(w)
            continue
        new = {}
        for b, share in w.items():
            if b not in ends:
                new[b] = new.get(b, 0.0) + share
                continue
            start, line = ends[b]
            u = max(0.0, min(1.0, dot(sub(v, start), line) / dot(line, line)))
            at = u * (TWIST_STEPS - 1.0)
            k = min(int(at), TWIST_STEPS - 2)
            new[_step(b, k)] = share * (1.0 - (at - k))
            new[_step(b, k + 1)] = share * (at - k)
        weights.append(new)
    return weights, moves


def solve(body, mann):
    """The turn of every Meshy bone that puts the body in the mannequin's pose."""
    out = Repose(rot={}, joints={})
    by_side = {s: bone for bone, s in HANDS.items()}
    frames, notes = hand_frame.body_frames(body, by_side["l"], by_side["r"])
    out.notes += notes
    for bone in body.bones:
        parent = body.parents[bone]
        if parent is None:
            out.joints[bone] = body.joints[bone]
            base = IDENTITY
        else:
            out.joints[bone] = add(out.joints[parent], turn(
                out.rot[parent], sub(body.joints[bone], body.joints[parent])))
            base = out.rot[parent]

        if bone in LIMBS:
            child, m_bone, m_child, _upper = LIMBS[bone]
            have = turn(base, sub(body.joints[child], body.joints[bone]))
            want = sub(mann.pos(m_child), mann.pos(m_bone))
            own = swing(have, want)
        elif bone in HANDS:
            s = HANDS[bone]
            finger, palm, ids = frames[bone]
            want_finger, want_palm = hand_frame.mannequin_frame(mann, s)
            whole = frame_turn(turn(base, finger), turn(base, palm),
                               want_finger, want_palm)
            # The forearm's line after its own swing: the mannequin's.
            forearm = body.parents[bone]
            axis = unit(sub(mann.pos(LIMBS[forearm][2]), mann.pos(LIMBS[forearm][1])))
            own, roll = split_twist(whole, axis)
            out.twists[forearm] = (axis, roll)
            # The hand takes the whole roll (it is the forearm's last step)
            # and then its own bend at the wrist.
            base = mul(axis_angle(axis, roll), base)
            out.hands[s] = {"finger": finger, "palm": palm, "ids": ids,
                            "roll_deg": roll, "bend_deg": angle_deg(own)}
        elif bone in FEET:
            toe, s = FEET[bone]
            have = sub(body.joints[toe], body.joints[bone])
            want = sub(mann.pos(f"ball_{s}"), mann.pos(f"foot_{s}"))
            own = swing((have[0], have[1], 0.0), (want[0], want[1], 0.0))
            base = IDENTITY
        else:
            own = IDENTITY
        out.rot[bone] = mul(own, base)
        if own is not IDENTITY:
            out.turned[bone] = angle_deg(own)
    return out


def apply(body, pose):
    """(vertices, normals, tangents) of the body in the mannequin's pose."""
    weights, moves = graded(body, pose)
    return (lbs.points(body.verts, weights, moves),
            lbs.directions(body.normals, weights, moves),
            lbs.directions(body.tangents, weights, moves))
