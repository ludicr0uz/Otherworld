"""hand_frame -- which way a hand points and which face of it is the palm.

Read off the vertices, as palm_twist.py reads it in the editor and for the
same reason: Meshy's hand is a leaf bone, so nothing in the skeleton says
where the palm is.

    finger direction   wrist to the centroid of the hand's vertices
    palm normal        the cloud's thinnest axis -- and which of its two faces
                       is the palm is decided by the THUMB

A flat axis has no sign, and the sign is the whole answer: taken the wrong way
the palm is turned through the back of the hand.  The thumb settles it,
because a hand has a handedness: looking at the back of a right hand with the
fingers pointing away, the thumb is on the left, and no pose changes that.  So
the thumb's side (the side of the wrist-to-centroid line the cloud reaches
furthest on: 9-11 cm against 6-8 on the four bodies cached on 2026-10-03) and
the finger direction give the palm by a cross product, one way round for a
left hand and the other for a right.

The rule is checked against the mannequin, where the palm is known from the
joints (the side the fingers curl to): test_mannequin_bind.py.  It is NOT the
cloud's skew along the flat axis, which palm_twist.py signs by: on all four
cached bodies the skew points out of the back of the hand.  That costs
nothing where both rigs are signed by the same rule and compared, and it
would cost a half turn here, where the mannequin's palm is the real one.
Those bodies stand palms forward and up, the anatomical position, whatever
their prompts said about palms down: about 130 degrees of forearm turn from
the mannequin's.

The mannequin has no vertices here, only joints: wrist to the middle of the
knuckle line, and the normal of the knuckle plane on the side its fingers
curl to.
"""

from asset_pipeline.mannequin_bind.bone_map import KNUCKLE_FINGERS, finger_bone
from asset_pipeline.mannequin_bind.xform import cross, dot, scale, sub, unit
from combat.capsule_fit import principal_axes

# The thumb's side must reach this many times further from the hand's line
# than the other side for it to be believed.
THUMB_TRUSTED = 1.2


def _centroid(pts):
    return tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))


def palm_from_thumb(finger, thumb, right):
    """The palm's normal from the finger direction and the thumb's side.
    In Unreal's left-handed space (X is the body's left) -- which is the only
    space this is called in -- so the cross products are the mirror of the
    ones a right-hand rule gives."""
    return unit(cross(finger, thumb) if right else cross(thumb, finger))


def _frame(body, bone, right):
    ids = [i for i, w in enumerate(body.weights)
           if w.get(bone, 0.0) > 0.0 and max(w, key=w.get) == bone]
    if len(ids) < 32:
        raise ValueError(f"{bone} leads only {len(ids)} vertices: no hand to read")
    pts = [body.verts[i] for i in ids]
    wrist = body.joints[bone]
    finger = unit(sub(_centroid(pts), wrist))
    _long, _mid, flat = principal_axes(pts)
    across = unit(cross(flat, finger))
    reach = [dot(sub(p, wrist), across) for p in pts]
    plus, minus = max(reach), -min(reach)
    thumb = across if plus >= minus else scale(across, -1.0)
    sure = max(plus, minus) / max(min(plus, minus), 1e-6)
    palm = palm_from_thumb(finger, thumb, right)
    # The cloud's own flat axis is the better normal; the thumb only signs it.
    normal = flat if dot(flat, palm) >= 0 else scale(flat, -1.0)
    return finger, normal, ids, sure, thumb


def body_frames(body, left, right):
    """{bone: (finger direction, palm normal, vertex ids)} for a body's two
    hands, and a list of what should be looked at."""
    out, notes, thumbs = {}, [], {}
    for bone, is_right in ((left, False), (right, True)):
        finger, normal, ids, sure, thumb = _frame(body, bone, is_right)
        out[bone] = (finger, normal, ids)
        thumbs[bone] = thumb
        if sure < THUMB_TRUSTED:
            notes.append(
                f"{bone}: the thumb's side reaches only {sure:.2f}x the other "
                f"(under {THUMB_TRUSTED}); which face is the palm is a guess")
    a, b = thumbs[left], thumbs[right]
    if dot((-a[0], a[1], a[2]), b) < 0.0:
        notes.append(f"{left} and {right} are not mirror images by their "
                     "thumbs: one palm is likely read wrong")
    return out, notes


def mannequin_frame(mann, s):
    """(finger direction, palm normal) of a mannequin hand, from its joints."""
    wrist = mann.pos(f"hand_{s}")
    knuckles = [mann.pos(finger_bone(f, 1, s)) for f in KNUCKLE_FINGERS]
    tips = [mann.pos(finger_bone(f, 3, s)) for f in KNUCKLE_FINGERS]
    forward = sub(_centroid(knuckles), wrist)
    normal = cross(forward, sub(knuckles[-1], knuckles[0]))
    if dot(normal, sub(_centroid(tips), _centroid(knuckles))) < 0:
        normal = scale(normal, -1.0)
    return unit(forward), unit(normal)
