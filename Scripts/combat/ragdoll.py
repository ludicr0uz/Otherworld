"""Ragdolls: the joint-limit table, the planner that turns a physics asset
into limits, and tune_ragdolls().
"""

import math

import unreal

from combat.log import _log
from uebp.graph import _assets


# --- dying: the collapse, and how long a corpse lies there -------------------
# EVERYTHING that dies in this game collapses the same way, and it collapses
# physically rather than by playing a clip. There is no death animation in this
# project and no honest way to make one here:
#
#   * the creatures come from Meshy, whose rigging step generates a walk and a
#     run and nothing else -- there is no clip in assets/cache/meshy that ends
#     on the ground, and none among the 21 retargeted per creature;
#   * Epic's own MM_Death_* set, which the player used to play, is six
#     one-second STAGGERS. Measured off the assets: every one of them ends with
#     the pelvis at 83-88 cm and both feet on the floor, i.e. still standing,
#     having travelled 1.5-2 m backwards. They are hit reactions authored to be
#     blended into a ragdoll, not collapses.
#
# That measurement is the whole diagnosis of "he gets up right away": the
# player staggered for 1.1 s, the dynamic montage blended out, and the
# locomotion state machine underneath it had him standing again well before the
# 2.2 s pause.
#
# A ragdoll needs no asset at all. Every character here already carries a
# physics asset -- PA_Mannequin, SKM_Zombie01_PhysicsAsset,
# SKM_Wendigo01_PhysicsAsset -- and it is not optional: install_hit_zones reads
# the head and limb tables off those bodies, so a rig that could not ragdoll
# could not be shot in the head either. The fall is different every time, it is
# plausible on a slope, and there is nothing to retarget.
#
# SetAllBodiesSimulatePhysics, not SetSimulatePhysics: the latter is not even a
# UFunction on SkeletalMeshComponent (checked -- the node does not exist), and
# on a PrimitiveComponent it would simulate the one root body, which is a
# creature-shaped rigid brick falling over rather than a ragdoll.
RAGDOLL_PROFILE = "Ragdoll"
# How far each joint of a ragdoll may bend, keyed by the joint's CHILD bone with
# Left/Right stripped -- Meshy's names, the only rigs this is applied to (see
# tune_ragdolls).
#
#   flex   (least, most) degrees about the joint's hinge axis, measured from
#          anatomical straight, positive being the way the joint really folds:
#          toward `toward` (a knee folds its shin BACK, an elbow its hand
#          FORWARD, a hip its thigh forward, an ankle its toes down).
#   side   +/- degrees of side-bend (abduction, a spine leaning sideways).
#   twist  +/- degrees about the bone itself.
#   hinge  the joint is a hinge (knee, elbow): its flex is measured from where
#          the reference pose really has it -- a Meshy elbow is already bent
#          60-90 deg in the bind pose -- instead of being taken as zero.
#
# Two things made corpses land in "completely unnatural" shapes even after the
# importer's uniform 45/45/45 cones were replaced:
#   1. Every range was centred on the bind pose, so a knee that could fold
#      60 deg forward could fold 60 deg backwards too, and an elbow bent 70 deg
#      in the bind pose could straighten and keep going to 140 deg of
#      hyperextension. Epic's PA_Mannequin avoids this by rotating the
#      parent-side constraint frame so the range sits off-centre; ragdoll_plan()
#      does the same (PriAxis2/SecAxis2 on the template's DefaultInstance --
#      AngularRotationOffset only exists for PhysicsConstraintComponents).
#   2. The importer's limits are SOFT at stiffness 50 / damping 5, which a
#      falling body pushes straight through. RAGDOLL_LIMIT_SPRING is
#      PA_Mannequin's own: 500/50 for ball joints and 1000/100 for hinges.
#
# The numbers are human ranges of motion trimmed toward PA_Mannequin's (a ragdoll
# with a full human range looks looser than a person, because nothing in it
# resists as muscle does).
RAGDOLL_JOINTS = {
    "spine":    dict(flex=(-10.0, 20.0), side=10.0, twist=10.0, toward="forward"),
    "neck":     dict(flex=(-20.0, 35.0), side=15.0, twist=25.0, toward="forward"),
    "head":     dict(flex=(-20.0, 30.0), side=15.0, twist=30.0, toward="forward"),
    "shoulder": dict(flex=(-10.0, 10.0), side=10.0, twist=5.0,  toward="forward"),
    "arm":      dict(flex=(-40.0, 90.0), side=40.0, twist=35.0, toward="forward"),
    "forearm":  dict(flex=(0.0, 135.0),  side=5.0,  twist=10.0, toward="forward",
                     hinge=True),
    "hand":     dict(flex=(-40.0, 40.0), side=20.0, twist=15.0, toward="forward"),
    "upleg":    dict(flex=(-20.0, 100.0), side=30.0, twist=20.0, toward="forward"),
    "leg":      dict(flex=(0.0, 135.0),  side=3.0,  twist=5.0,  toward="back",
                     hinge=True),
    "foot":     dict(flex=(-20.0, 40.0), side=10.0, twist=10.0, toward="down"),
    "toebase":  dict(flex=(-10.0, 30.0), side=5.0,  twist=5.0,  toward="up"),
}
# Soft-limit (stiffness, damping) for ball joints and for hinges.
RAGDOLL_LIMIT_SPRING = {False: (500.0, 50.0), True: (1000.0, 100.0)}
# Every mesh under here got its physics asset from the importer
# (import_characters._ensure_physics). Epic's PA_Mannequin is hand-tuned and a
# stock asset, and is left alone.
RAGDOLL_MESH_ROOT = "/Game/Sourced/Characters"


def _ragdoll_role(bone):
    """RAGDOLL_JOINTS key for a joint's child bone, or None."""
    b = bone.lower()
    for side in ("left", "right"):
        if b.startswith(side):
            b = b[len(side):]
            break
    if b.startswith("spine"):
        return "spine"
    return b if b in RAGDOLL_JOINTS else None


def _v_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _v_norm(a):
    n = _v_dot(a, a) ** 0.5
    return tuple(x / n for x in a) if n > 1e-6 else None


def _v_rotate(v, axis, degrees):
    """v rotated about the unit `axis` by `degrees`, right-handed (Rodrigues)."""
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    k = _v_dot(axis, v) * (1.0 - c)
    ax = _v_cross(axis, v)
    return tuple(v[i] * c + ax[i] * s + axis[i] * k for i in range(3))


def _v_signed_angle(a, b, axis):
    """Degrees from a to b about `axis`, both projected onto its plane."""
    def flat(v):
        return tuple(x - _v_dot(v, axis) * y for x, y in zip(v, axis))
    a, b = flat(a), flat(b)
    return math.degrees(math.atan2(_v_dot(_v_cross(a, b), axis), _v_dot(a, b)))


def ragdoll_plan(mesh_asset):
    """[joint dict] for every constraint of a mesh's ragdoll. See RAGDOLL_JOINTS.

    Each joint gets its own constraint frames, built from the reference pose
    rather than from the bones' axes (Meshy's bones point every which way):

      ball joint  frame X along the bone (twist), Y the flex axis (swing2),
                  Z the side-bend axis (swing1).
      hinge       frame X the flex axis (twist, the one axis Chaos lets
                  swing furthest), Y along the bone, Z the side-bend axis.

    The flex axis is the one that swings the bone's far end toward the
    role's `toward` -- for an elbow already bent in the bind pose, the plane
    the bend is in. Both frames start identical in the reference pose, then
    the parent's frame is turned about the flex axis by the middle of the
    flex range: Chaos's limits are +/- about where the two frames agree, so
    that puts the agreeing pose mid-range and makes the range one-sided.

    Every dict: constraint (accessor), template (PhysicsConstraintTemplate),
    child, parent, role, hinge, rest (bind-pose flex, degrees), centre, flex
    half-range, limits (swing1, swing2, twist), and the four frame axes in
    each body's own space (pri1, sec1, pri2, sec2) plus their world versions
    (world1, world2), the world flex axis (axis) and both bodies' bind-pose
    rotations (rot1, rot2), for the verifier.
    """
    def vec(v):
        return (v.x, v.y, v.z)

    def sub(a, b):
        return tuple(x - y for x, y in zip(a, b))

    pa = mesh_asset.get_editor_property("physics_asset")
    skeleton = mesh_asset.get_editor_property("skeleton")
    if not pa or not skeleton:
        return []
    pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    names = [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(pose)]
    xf = {n: unreal.AnimPoseExtensions.get_bone_pose(
        pose, n, unreal.AnimPoseSpaces.WORLD) for n in names}
    pos = {n: vec(t.translation) for n, t in xf.items()}
    probe = unreal.SkeletalMeshComponent()
    probe.set_skeletal_mesh_asset(mesh_asset)
    parent = {n: str(probe.get_parent_bone(n)) for n in names}

    # Which way the body faces: up crossed with its left (every Left*/Right*
    # pair averaged), checked against the way the toes point.
    pairs = [sub(pos[n], pos["Right" + n[4:]]) for n in names
             if n.startswith("Left") and "Right" + n[4:] in pos]
    left = _v_norm(tuple(sum(c) for c in zip(*pairs))) if pairs else None
    if left is None:
        raise RuntimeError(f"{mesh_asset.get_name()} has no Left/Right bone "
                           "pairs to find its sides from")
    up = (0.0, 0.0, 1.0)
    forward = _v_norm(_v_cross(up, left))
    if "LeftToeBase" in pos and "LeftFoot" in pos and _v_dot(
            sub(pos["LeftToeBase"], pos["LeftFoot"]), forward) <= 0:
        raise RuntimeError(f"{mesh_asset.get_name()}: its toes point backwards "
                           f"of the forward {forward} worked out from its sides")
    toward = {"forward": forward, "back": tuple(-x for x in forward),
              "up": up, "down": (0.0, 0.0, -1.0)}

    # One constraint template per accessor, found by name (the physics
    # asset's ConstraintSetup array is protected; its entries are not).
    accessors = pa.get_constraints(False)
    templates = {}
    i = 0
    while len(templates) < len(accessors) and i < 4 * len(accessors) + 16:
        t = unreal.find_object(pa, f"PhysicsConstraintTemplate_{i}")
        i += 1
        if t is not None:
            di = t.get_editor_property("DefaultInstance")
            templates[str(di.get_editor_property("constraint_bone1"))] = t

    def along_of(bone):
        kids = [pos[n] for n in names if parent[n] == bone]
        if kids:
            return _v_norm(sub(tuple(sum(c) / len(kids) for c in zip(*kids)),
                               pos[bone]))
        return _v_norm(sub(pos[bone], pos[parent[bone]]))

    plan = []
    for constraint in accessors:
        ends = [str(n) for n in unreal.ConstraintInstanceBlueprintLibrary
                .get_attached_body_names(constraint) if isinstance(n, unreal.Name)]
        child = ends[-1] if ends else None
        role = _ragdoll_role(child) if child in pos else None
        if role is None or child not in templates:
            _log(f"note: {pa.get_name()}: no ragdoll limits for joint {ends} "
                 "-- left as imported")
            continue
        body_parent = str(templates[child].get_editor_property("DefaultInstance")
                          .get_editor_property("constraint_bone2"))
        spec = RAGDOLL_JOINTS[role]
        hinge = bool(spec.get("hinge"))
        along = along_of(child)
        goal = toward[spec["toward"]]
        axis = _v_norm(_v_cross(along, goal)) or _v_norm(_v_cross(along, up))
        rest = 0.0
        if hinge:
            # The proximal segment runs from the parent body to this joint.
            upper = _v_norm(sub(pos[child], pos[body_parent]))
            bent = _v_norm(_v_cross(upper, along))
            if bent and math.degrees(math.acos(max(-1.0, min(1.0, _v_dot(
                    upper, along))))) > 20.0:
                # Bent enough in the bind pose to show its own hinge plane;
                # flexing moves the far end away from the upper segment,
                # which is the sense of upper x along.
                axis = bent
            rest = _v_signed_angle(upper, along, axis)
        lo, hi = spec["flex"]
        half = (hi - lo) / 2.0
        centre = (hi + lo) / 2.0 - rest
        side_axis = _v_norm(_v_cross(along, axis))
        if hinge:
            x1, y1 = axis, _v_norm(_v_cross(side_axis, axis))
            limits = (spec["side"], spec["twist"], half)
        else:
            x1, y1 = along, axis
            limits = (spec["side"], half, spec["twist"])
        x2, y2 = _v_rotate(x1, axis, centre), _v_rotate(y1, axis, centre)

        def local(bone, v):
            return vec(xf[bone].rotation.unrotate_vector(unreal.Vector(*v)))

        swing1, swing2, twist = limits
        plan.append(dict(
            constraint=constraint, template=templates[child], child=child,
            parent=body_parent, role=role, hinge=hinge, rest=rest,
            centre=centre, half=half, axis=axis,
            limits=(round(swing1, 3), round(swing2, 3), round(twist, 3)),
            pri1=local(child, x1), sec1=local(child, y1),
            pri2=local(body_parent, x2), sec2=local(body_parent, y2),
            world1=(x1, y1), world2=(x2, y2),
            rot1=xf[child].rotation, rot2=xf[body_parent].rotation))
    return plan


def tune_ragdolls():
    """Give every imported creature's ragdoll real joints. See RAGDOLL_JOINTS.

    Every skeletal mesh under RAGDOLL_MESH_ROOT, whether or not anything wears
    it yet: which creature is the player and which ten are wanderers is decided
    in other files, and all of them die.

    Written through set_editor_property on the template's DefaultInstance, not
    through ConstraintInstanceBlueprintLibrary: the frames are only reachable
    there, and the property-change notification is what copies the new limits
    into the template's transient DefaultProfile -- which is what Serialize
    writes to disk in place of DefaultInstance's own profile.
    """
    limited = unreal.AngularConstraintMotion.ACM_LIMITED
    eas = _assets()
    for path in sorted(eas.list_assets(RAGDOLL_MESH_ROOT, recursive=True)):
        mesh = eas.load_asset(path.split(".")[0])
        if not isinstance(mesh, unreal.SkeletalMesh):
            continue
        pa = mesh.get_editor_property("physics_asset")
        plan = ragdoll_plan(mesh)
        if not plan:
            continue
        pa.modify()
        for j in plan:
            t = j["template"]
            t.modify()
            di = t.get_editor_property("DefaultInstance")
            for key in ("pri1", "sec1", "pri2", "sec2"):
                di.set_editor_property(key[:3] + "_axis" + key[3],
                                       unreal.Vector(*j[key]))
            swing1, swing2, twist = j["limits"]
            stiffness, damping = RAGDOLL_LIMIT_SPRING[j["hinge"]]
            prof = di.get_editor_property("profile_instance")
            cone = prof.get_editor_property("cone_limit")
            cone.set_editor_properties({
                "swing1_motion": limited, "swing2_motion": limited,
                "swing1_limit_degrees": swing1, "swing2_limit_degrees": swing2,
                "soft_constraint": True, "stiffness": stiffness,
                "damping": damping})
            tw = prof.get_editor_property("twist_limit")
            tw.set_editor_properties({
                "twist_motion": limited, "twist_limit_degrees": twist,
                "soft_constraint": True, "stiffness": stiffness,
                "damping": damping})
            prof.set_editor_property("cone_limit", cone)
            prof.set_editor_property("twist_limit", tw)
            di.set_editor_property("profile_instance", prof)
            t.set_editor_property("DefaultInstance", di)
            got = unreal.ConstraintInstanceBlueprintLibrary.get_angular_limits(
                j["constraint"])[1:]
            if [round(got[k], 3) for k in (1, 3, 5)] != list(j["limits"]):
                raise RuntimeError(f"{pa.get_name()}: limits on {j['child']} did "
                                   f"not stick: {got}")
        eas.save_loaded_asset(pa)
        _log(f"{pa.get_name()}: {len(plan)} joints limited like a body -- "
             + ", ".join(f"{j['child']} flex {j['centre'] - j['half'] + j['rest']:.0f}"
                         f"..{j['centre'] + j['half'] + j['rest']:.0f}"
                         f" (bind {j['rest']:.0f})" for j in plan))
