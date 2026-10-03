#!/usr/bin/env python3
"""rig_compat.py -- can one generated rig stand in for another? Host-side.

No editor and no credits: it reads the rest pose out of each rigged GLB's JSON
chunk (skeleton_probe.glb_json) and compares a candidate with a reference.

    python3 Scripts/asset_pipeline/rig_compat.py adventurer_02            # against its
                                                 # spec's compatible_with
    python3 Scripts/asset_pipeline/rig_compat.py adventurer_02 adventurer_01
    python3 Scripts/asset_pipeline/rig_compat.py --table adventurer_01    # every cached rig

Meshy's rigger takes a mesh and a height and nothing else, so nothing said in
a prompt reaches the skeleton (combat/skin.py). What comes back has had the
same bone names every time, and a different rest pose every time. So a body
meant to replace another is checked after it is generated, not asked for.

Three verdicts:

    compatible   within NORMALISE_* of the reference: swaps in as it is
    normalise    same bones, a pose or proportion past NORMALISE_*: the import
                 steps driven by ``compatible_with`` absorb it (retarget pose
                 alignment, the reference's physics bodies, fitted capsules)
    fail         a bone missing, renamed or re-parented, or a proportion past
                 FAIL_*: nothing downstream absorbs it. Generate again.

What is measured, per segment (a bone's line to one child), in a BODY frame
built from the rig itself (up: hips to head; left: right thigh to left thigh),
so two exports with different axes or a different lean compare alike:

    length   as a share of the rig's stature (feet to head joint), as a ratio
             to the reference's
    angle    between the segment's direction and the reference's
    own      the part of that angle the segment's own bone adds, past what its
             parent segment already turned: it names the bone that differs
             rather than every bone hanging off it
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asset_pipeline.skeleton_probe import (             # noqa: E402
    CACHE_ROOT, glb_json,
)

# ── Tolerances ───────────────────────────────────────────────────────────────
# From the five rigs cached on 2026-10-03, each against adventurer_01
# (``--table adventurer_01`` prints it; worst segment per group):
#
#                    arms            clavicles       legs            spine
#                    angle  length   angle  length   angle  length   angle  length
#   adventurer_01     0.0   1.00      0.0   1.00      0.0   1.00      0.0   1.00
#   adventurer_02    24.6   0.83     39.4   1.48      4.3   1.19      6.4   1.58
#   adventurer_03    11.1   0.83     24.7   1.27      6.6   1.18     22.5   1.50
#   zombie_01        35.6   1.05      2.9   0.98     10.9   1.18      1.0   0.83
#   wendigo_01       55.7   1.56     22.3   1.20     57.6   1.48     49.9   4.55
#
# adventurer_02 is the body that did NOT swap in as generated (its clavicles
# run 39 degrees behind adventurer_01's, and its hold poses fell short by up to
# 10 cm); the wendigo is not a man. So the first line is drawn well under
# adventurer_02 and the second between it and the wendigo. adventurer_03 was
# generated after the lines were drawn, read "normalise", and swapped in.
#
# Past these a rig needs the import-time normalising:
NORMALISE_ANGLE_DEG = 10.0
NORMALISE_LENGTH = 0.10          # |ratio - 1|
# Past these it is not the same kind of body. Arms and legs are what the
# retargeter's chains and the hand IK can stretch over; the clavicle and the
# spine joints are placed by the rigger more freely (a spine joint 58% longer
# on a body that then swapped in after normalising), so they get more room.
FAIL_ANGLE_DEG = {"arms": 60.0, "clavicles": 60.0, "legs": 20.0, "spine": 30.0}
FAIL_LENGTH = {"arms": 0.25, "clavicles": 0.80, "legs": 0.30, "spine": 0.80}

# segment -> group. A segment is "<bone>><child>"; one not listed (the head's
# helper joints, a toe) is compared for hierarchy only.
_SIDE = ("Left", "Right")
GROUPS = {}
for _s in _SIDE:
    GROUPS[f"{_s}Shoulder>{_s}Arm"] = "clavicles"
    GROUPS[f"{_s}Arm>{_s}ForeArm"] = "arms"
    GROUPS[f"{_s}ForeArm>{_s}Hand"] = "arms"
    GROUPS[f"{_s}UpLeg>{_s}Leg"] = "legs"
    GROUPS[f"{_s}Leg>{_s}Foot"] = "legs"
for _a, _b in (("Hips", "Spine02"), ("Spine02", "Spine01"), ("Spine01", "Spine"),
               ("Spine", "neck"), ("neck", "Head")):
    GROUPS[f"{_a}>{_b}"] = "spine"
GROUP_ORDER = ("arms", "clavicles", "legs", "spine")

# The bones the body frame and the stature are read from.
FRAME_BONES = ("Hips", "Head", "LeftUpLeg", "RightUpLeg", "LeftFoot", "RightFoot")

VERDICTS = ("compatible", "normalise", "fail")


# ── vectors and quaternions, as tuples ───────────────────────────────────────

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _len(v):
    return math.sqrt(_dot(v, v))


def _unit(v):
    n = _len(v)
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-9 else (0.0, 0.0, 0.0)


def _angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(_unit(a), _unit(b))))))


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _qrot(q, v):
    x, y, z, w = q
    t = _cross((x, y, z), v)
    t = (2 * t[0], 2 * t[1], 2 * t[2])
    c = _cross((x, y, z), t)
    return (v[0] + w * t[0] + c[0], v[1] + w * t[1] + c[1], v[2] + w * t[2] + c[2])


def _qbetween(a, b):
    """The shortest turn taking unit ``a`` onto unit ``b``."""
    c = _cross(a, b)
    w = 1.0 + _dot(a, b)
    n = math.sqrt(_dot(c, c) + w * w)
    if n < 1e-9:                      # opposite: any half turn; never met here
        return (1.0, 0.0, 0.0, 0.0)
    return (c[0] / n, c[1] / n, c[2] / n, w / n)


# ── a rig, read out of a GLB's JSON ──────────────────────────────────────────

def rig_from_doc(doc):
    """{bone: (parent or None, world position)} for the first skin's joints,
    in the rest pose. Pure: ``doc`` is a glTF JSON document."""
    nodes = doc.get("nodes", [])
    parent = {}
    for i, node in enumerate(nodes):
        for child in node.get("children", []):
            parent[child] = i
    cache = {}

    def world(i):
        if i not in cache:
            node = nodes[i]
            t = tuple(node.get("translation", (0.0, 0.0, 0.0)))
            r = tuple(node.get("rotation", (0.0, 0.0, 0.0, 1.0)))
            s = tuple(node.get("scale", (1.0, 1.0, 1.0)))
            if i in parent:
                pt, pr, ps = world(parent[i])
                moved = _qrot(pr, (t[0] * ps[0], t[1] * ps[1], t[2] * ps[2]))
                cache[i] = ((pt[0] + moved[0], pt[1] + moved[1], pt[2] + moved[2]),
                            _qmul(pr, r), (ps[0] * s[0], ps[1] * s[1], ps[2] * s[2]))
            else:
                cache[i] = (t, r, s)
        return cache[i]

    skins = doc.get("skins", [])
    joints = set(skins[0].get("joints", [])) if skins else set()
    rig = {}
    for i in sorted(joints):
        name = nodes[i].get("name", f"node{i}")
        p = parent.get(i)
        rig[name] = (nodes[p].get("name", f"node{p}") if p in joints else None,
                     world(i)[0])
    return rig


def rigged_glb(spec_id):
    """The cached rigged GLB of a spec: the character itself, whose node
    transforms are the rest pose (the animation exports carry the same)."""
    rig_dir = os.path.join(CACHE_ROOT, spec_id, "rigged")
    if not os.path.isdir(rig_dir):
        return None
    glbs = sorted(f for f in os.listdir(rig_dir) if f.lower().endswith(".glb"))
    plain = [f for f in glbs if "rigged_character" in f]
    pick = plain or [f for f in glbs if "armature" in f] or glbs
    return os.path.join(rig_dir, pick[0]) if pick else None


def load_rig(spec_id):
    path = rigged_glb(spec_id)
    if not path:
        raise FileNotFoundError(
            f"no rigged GLB cached for {spec_id} under {CACHE_ROOT}")
    return rig_from_doc(glb_json(path))


# ── measuring ────────────────────────────────────────────────────────────────

def _body_frame(rig):
    """(left, forward, up) unit axes and the stature, from the rig itself."""
    pos = {b: rig[b][1] for b in FRAME_BONES}
    feet = tuple((a + b) / 2.0 for a, b in zip(pos["LeftFoot"], pos["RightFoot"]))
    up = _unit(_sub(pos["Head"], pos["Hips"]))
    across = _sub(pos["LeftUpLeg"], pos["RightUpLeg"])
    left = _unit(_sub(across, tuple(c * _dot(across, up) for c in up)))
    forward = _cross(left, up)
    stature = _dot(_sub(pos["Head"], feet), up)
    return (left, forward, up), stature


def segments(rig):
    """{"<bone>><child>": (unit direction in the body frame, length / stature,
    parent segment or None)}."""
    axes, stature = _body_frame(rig)
    out = {}
    for child, (bone, at) in rig.items():
        if bone is None:
            continue
        line = _sub(at, rig[bone][1])
        grand = rig[bone][0]
        out[f"{bone}>{child}"] = (
            _unit(tuple(_dot(line, axis) for axis in axes)),
            _len(line) / stature,
            f"{grand}>{bone}" if grand is not None else None)
    return out


def compare(rig, reference):
    """The report: hierarchy problems, one row per grouped segment, the worst
    per group, and the verdict. Pure."""
    problems = []
    for bone, (parent, _at) in reference.items():
        if bone not in rig:
            problems.append(f"{bone}: missing (the reference has it under "
                            f"{parent or 'the root'})")
        elif rig[bone][0] != parent:
            problems.append(f"{bone}: parented to {rig[bone][0] or 'the root'}, "
                            f"the reference's is under {parent or 'the root'}")
    for bone in rig:
        if bone not in reference:
            problems.append(f"{bone}: not in the reference")
    report = {"problems": problems, "rows": [], "worst": {}, "flags": [],
              "verdict": "fail" if problems else "compatible"}
    if problems or any(b not in rig or b not in reference for b in FRAME_BONES):
        return report

    mine, theirs = segments(rig), segments(reference)
    for seg, group in GROUPS.items():
        if seg not in mine or seg not in theirs:
            continue
        (d, n, up_seg), (rd, rn, _r) = mine[seg], theirs[seg]
        angle = _angle(d, rd)
        own = angle
        if up_seg in mine and up_seg in theirs and _len(mine[up_seg][0]) > 0:
            carried = _qrot(_qbetween(theirs[up_seg][0], mine[up_seg][0]), rd)
            own = _angle(d, carried)
        ratio = n / rn if rn > 1e-9 else float("inf")
        row = {"segment": seg, "bone": seg.split(">")[0], "group": group,
               "angle": angle, "own": own, "length": ratio}
        report["rows"].append(row)
        worst = report["worst"].setdefault(group, {"angle": 0.0, "length": 1.0})
        worst["angle"] = max(worst["angle"], angle)
        if abs(ratio - 1.0) > abs(worst["length"] - 1.0):
            worst["length"] = ratio

        level = "compatible"
        off = abs(ratio - 1.0)
        if angle > FAIL_ANGLE_DEG[group] or off > FAIL_LENGTH[group]:
            level = "fail"
        elif angle > NORMALISE_ANGLE_DEG or off > NORMALISE_LENGTH:
            level = "normalise"
        if level != "compatible":
            what = []
            if own > NORMALISE_ANGLE_DEG:
                what.append(f"rests {own:.1f} deg off the reference's")
            elif angle > NORMALISE_ANGLE_DEG:
                what.append(f"carried {angle:.1f} deg off by the bones above it")
            if off > NORMALISE_LENGTH:
                what.append(f"is {ratio:.2f}x the reference's length")
            report["flags"].append({"bone": row["bone"], "segment": seg,
                                    "group": group, "level": level,
                                    "what": ", ".join(what)})
        if VERDICTS.index(level) > VERDICTS.index(report["verdict"]):
            report["verdict"] = level
    return report


def summary(report):
    """What task.json keeps: the verdict, the worst per group, the flags."""
    return {"verdict": report["verdict"], "problems": report["problems"],
            "worst": {g: {k: round(v, 3) for k, v in w.items()}
                      for g, w in report["worst"].items()},
            "flags": [f"{f['bone']} ({f['level']}): {f['what']}"
                      for f in report["flags"]]}


def check(spec_id, reference_id):
    """Compare two cached rigs; returns the report."""
    report = compare(load_rig(spec_id), load_rig(reference_id))
    report["id"], report["reference"] = spec_id, reference_id
    return report


# ── printing ─────────────────────────────────────────────────────────────────

def print_report(report):
    print(f"{report['id']} against {report['reference']}: "
          f"{report['verdict'].upper()}")
    for line in report["problems"]:
        print(f"  hierarchy: {line}")
    if report["rows"]:
        print(f"  {'segment':<28s} {'angle':>6s} {'own':>6s} {'length':>7s}")
        for row in report["rows"]:
            print(f"  {row['segment']:<28s} {row['angle']:6.1f} {row['own']:6.1f} "
                  f"{row['length']:7.2f}")
    for flag in report["flags"]:
        print(f"  {flag['level']:<9s} {flag['bone']}: {flag['what']}")


def print_table(reference_id):
    print(f"against {reference_id} (worst segment per group: angle deg, length ratio)")
    print(f"  {'':<16s}" + "".join(f"{g:>16s}" for g in GROUP_ORDER) + "   verdict")
    for sid in sorted(os.listdir(CACHE_ROOT)):
        if sid.startswith("_") or not rigged_glb(sid):
            continue
        report = check(sid, reference_id)
        cells = "".join(
            f"{report['worst'][g]['angle']:9.1f} {report['worst'][g]['length']:6.2f}"
            if g in report["worst"] else f"{'-':>16s}" for g in GROUP_ORDER)
        print(f"  {sid:<16s}{cells}   {report['verdict']}")


def _reference_for(spec_id):
    from asset_pipeline import catalog
    return catalog.by_id(spec_id).compatible_with


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("id", help="spec id of the rig to check")
    ap.add_argument("reference", nargs="?", help="spec id to check it against; "
                    "default is the spec's compatible_with")
    ap.add_argument("--table", action="store_true",
                    help="every cached rig against <id>")
    args = ap.parse_args(argv)
    if args.table:
        print_table(args.id)
        return 0
    reference = args.reference or _reference_for(args.id)
    if not reference:
        print(f"{args.id} names no compatible_with and no reference was given")
        return 2
    report = check(args.id, reference)
    print_report(report)
    return 1 if report["verdict"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
