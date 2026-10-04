"""fit -- the mannequin's skeleton, sized to one body.

The skeleton a bound body carries has the mannequin's bones, the mannequin's
parents and -- this is the point -- the mannequin's reference ROTATIONS, every
one of them, so that a clip's rotations mean on this body what they mean on
the mannequin.  What is the body's own is where the joints are: each bone's
reference TRANSLATION.  A mesh may differ from its skeleton asset in those,
and with the skeleton's translation retargeting on "Skeleton" (the mannequin's
setting for everything but the root and the pelvis) a clip then plays this
body's proportions and not Manny's.

Where each joint goes, the body already posed like the mannequin (repose.py):

    limbs, clavicles, head           on the Meshy joint that is that joint
    pelvis                           where the mannequin keeps it: between the
                                     hip joints, not on Meshy's Hips (below)
    spine_01..05, neck_02            along Meshy's spine and neck lines, at
                                     the mannequin's own spacing
    twist bones                      where they sit along their limb, by ratio
    fingers and metacarpals          the mannequin's hand, scaled as a whole
                                     to this hand's length
    ik_ bones                        on the bone each one shadows
    anything else                    the mannequin's offset, at body scale
"""

from asset_pipeline.mannequin_bind import ref_skeleton
from asset_pipeline.mannequin_bind.bone_map import (
    HANDS, LANDMARKS, LIMBS, MANNEQUIN_NECK_LINE, MANNEQUIN_SPINE_LINE,
    MESHY_NECK_LINE, MESHY_SPINE_LINE, finger_bone)
from asset_pipeline.mannequin_bind.xform import (
    add, dot, length, lerp, scale, sub, turn)

# THE PELVIS IS NOT MESHY'S HIPS
# -----------------------------
# Meshy sets its Hips joint high -- 9.5 cm over the hip joints on
# adventurer_03, where the mannequin's pelvis is 2.4 over them -- and the
# pelvis is the one bone whose TRANSLATION a clip drives on a bound body (the
# skeleton plays it "animation scaled": the clip's pelvis height times this
# mesh's reference pelvis height over the mannequin's).  With the pelvis on
# Meshy's joint that ratio was 1.06 on a body whose legs are 0.92 of the
# mannequin's, and in the editor the body stood 11 cm off the ground in MM_Idle
# (first import, 2026-10-03: ankle at 20.4 cm against 14.3 at rest).  A pelvis
# is a pivot and a height; nothing is skinned differently for moving it, since
# its reference rotation is the mannequin's wherever it sits.  So it goes where
# the mannequin's is: over the middle of the hip joints by the mannequin's own
# offset.

# A mannequin finger's last bone has no child to end it; the fingertip is
# taken this share of the bone before it further on.
TIP_SHARE = 0.9
# A hand outside this range of the mannequin's size is not a hand read right.
HAND_SCALE_RANGE = (0.6, 1.5)
# Two mannequin bones this close are the same place (an ik_ bone on its twin).
SAME_PLACE_CM = 0.01


def _along(line, share):
    """The point ``share`` of the way along a polyline, by length."""
    spans = [length(sub(b, a)) for a, b in zip(line, line[1:])]
    left = share * sum(spans)
    for (a, b), span in zip(zip(line, line[1:]), spans):
        if left <= span or (a, b) == (line[-2], line[-1]):
            return lerp(a, b, left / span if span > 1e-9 else 0.0)
        left -= span
    return line[-1]


def _shares(points):
    """Each interior point's share of a polyline's length."""
    spans = [length(sub(b, a)) for a, b in zip(points, points[1:])]
    total, run, out = sum(spans), 0.0, []
    for span in spans[:-1]:
        run += span
        out.append(run / total)
    return out


def mannequin_hand_length(mann, s):
    """Wrist to the tip of the middle finger, along the joints."""
    chain = [mann.pos(f"hand_{s}")] + [mann.pos(finger_bone("middle", j, s))
                                       for j in (1, 2, 3)]
    spans = [length(sub(b, a)) for a, b in zip(chain, chain[1:])]
    return sum(spans) + TIP_SHARE * spans[-1]


def hand_scale(mann, s, wrist, finger, hand_verts):
    """This hand's length over the mannequin's: the furthest its vertices
    reach from the wrist along the finger direction."""
    reach = sorted(dot(sub(v, wrist), finger) for v in hand_verts)
    got = reach[int(0.995 * (len(reach) - 1))]
    ratio = got / mannequin_hand_length(mann, s)
    lo, hi = HAND_SCALE_RANGE
    if not lo <= ratio <= hi:
        raise ValueError(f"hand_{s}: {got:.1f} cm long, {ratio:.2f}x the "
                         "mannequin's; that is not a hand read right")
    return ratio


def fit(mann, joints, hand_scales):
    """The fitted skeleton.  ``joints`` is {Meshy bone: position} with the
    body in the mannequin's pose; ``hand_scales`` is {suffix: ratio}."""
    place = {m: joints[b] for b, m in LANDMARKS.items()}
    hips = lerp(place["thigh_l"], place["thigh_r"], 0.5)
    over = sub(mann.pos("pelvis"), lerp(mann.pos("thigh_l"), mann.pos("thigh_r"), 0.5))
    place["pelvis"] = add(hips, over)

    body_spine = [place["pelvis"]] + [joints[b] for b in MESHY_SPINE_LINE[1:]]
    mann_spine = [mann.pos(b) for b in MANNEQUIN_SPINE_LINE]
    for bone, share in zip(MANNEQUIN_SPINE_LINE[1:-1], _shares(mann_spine)):
        place[bone] = _along(body_spine, share)
    body_neck = [joints[b] for b in MESHY_NECK_LINE]
    mann_neck = [mann.pos(b) for b in MANNEQUIN_NECK_LINE]
    for bone, share in zip(MANNEQUIN_NECK_LINE[1:-1], _shares(mann_neck)):
        place[bone] = _along(body_neck, share)

    # How long each limb segment is here against the mannequin's.
    ratio = {}
    for _b, (_c, m_bone, m_child, _upper) in LIMBS.items():
        ratio[m_bone] = (length(sub(place[m_child], place[m_bone]))
                         / length(sub(mann.pos(m_child), mann.pos(m_bone))))
    stature = place["pelvis"][2] / mann.pos("pelvis")[2]
    under_hand = {}
    for s in HANDS.values():
        for bone in mann.descendants(f"hand_{s}"):
            under_hand[bone] = hand_scales[s]

    for i, name in enumerate(mann.names):
        if name in place:
            continue
        p = mann.parents[i]
        if p < 0:
            place[name] = mann.comp_t[i]
            continue
        parent = mann.names[p]
        if name.startswith("ik_"):
            twin = next((n for n in mann.names
                         if n in place and not n.startswith("ik_")
                         and length(mann.pos(n)) > SAME_PLACE_CM
                         and length(sub(mann.pos(n), mann.comp_t[i])) < SAME_PLACE_CM),
                        None)
            if twin:
                place[name] = place[twin]
                continue
        by = under_hand.get(name, ratio.get(parent, stature))
        place[name] = add(place[parent],
                          turn(mann.comp_q[p], scale(mann.local_t[i], by)))

    fitted = ref_skeleton.from_component(
        mann.names, mann.parents, mann.comp_q, [place[n] for n in mann.names])
    info = {"limb_ratio": ratio, "stature": stature, "hand_scale": dict(hand_scales)}
    return fitted, info
