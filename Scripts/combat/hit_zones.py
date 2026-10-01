"""Head and limb hit boxes: which bones count as which zone for a given
physics asset, and installing those tables (and Visibility-blocking
collision) on a character.
"""

import unreal

from combat.graph import _component_object, _find_handle, _handles, _log
from combat.tuning import COMBAT


# --- hit boxes ---------------------------------------------------------------
# A zone is a root bone plus everything under it in the skeleton, so the tables
# are derived from each character's own mesh at build time (hit_zones) and
# never typed out here. What a zone is WORTH is combat tuning and lives on
# COMBAT; which bones are in one is a fact about a rig and lives below.
#
# Zone roots by ROLE, with the candidate bone names each rig might use.
#
# Two skeletons reach this code and they share almost no bone names: Epic's
# mannequin (head, upperarm_l, thigh_l) and Meshy's Mixamo-style creature rig
# (Head, LeftArm, LeftUpLeg). A single hardcoded list meant the creatures could
# not be shot at all -- and because the weapons script is not re-run by a level
# rebuild, that only surfaced the next time somebody ran it, a long way from the
# change that caused it.
#
# Resolved against the bodies the physics asset actually has, so a rig only
# needs to match ONE candidate per role, and a third creature family is a few
# more names here rather than a second copy of this function.
HEAD_CANDIDATES = ("head", "Head")
LIMB_CANDIDATES = (
    ("upperarm_l", "LeftArm"),
    ("upperarm_r", "RightArm"),
    ("thigh_l", "LeftUpLeg"),
    ("thigh_r", "RightUpLeg"),
)
HEAD_BONES_VAR = "HeadBones"
LIMB_BONES_VAR = "LimbBones"
HEAD_MULT_VAR = "HeadMultiplier"
LIMB_MULT_VAR = "LimbMultiplier"
# The bone the current pellet struck, on the weapon component. A variable
# because it is written on three different exec arms (struck a body, threaded
# between the limbs, hit something that is not a Character) and read by one.
HIT_BONE_VAR = "HitBone"
# Where the current pellet landed, on the weapon component: the trace's own
# hit, moved onto the struck body once the body trace finds one. The capsule
# stands up to 25 cm off the skin, and blood belongs on the skin.
HIT_POINT_VAR = "HitPoint"


def make_shootable(bp):
    """Let a Visibility trace hit this character's capsule.

    This is the bug that made the NPC unkillable. UE's stock `Pawn` profile sets
    Visibility to **Ignore** (and `CharacterMesh` does too), while the pellets
    trace on TraceTypeQuery1, which *is* Visibility -- so every shot passed
    straight through the NPC and no hit was ever registered. Nothing logs this:
    the trace simply reports no hit, exactly as it would for a genuine miss.

    The capsule alone is made to block, not the skeletal mesh: it is what the
    aim trace and the reticle rest on. It only stops the pellet, though. Whether
    the pellet struck the character is the physics bodies' answer (the fire
    graph's hit-zone trace), and hit_bodies.py fits those to the model.

    Setting a single channel response switches the profile off its preset and
    onto "Custom", which is expected.
    """
    capsule = _find_handle(bp, "CapsuleComponent")
    if not capsule:
        _log(f"note: {bp.get_name()} has no CapsuleComponent — not made shootable")
        return
    obj = _component_object(capsule)
    obj.set_collision_response_to_channel(
        unreal.CollisionChannel.ECC_VISIBILITY, unreal.CollisionResponseType.ECR_BLOCK)
    got = obj.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)
    if got != unreal.CollisionResponseType.ECR_BLOCK:
        raise RuntimeError(
            f"{bp.get_name()}'s capsule still ignores Visibility ({got}) — "
            "shots would pass through it")
    _log(f"{bp.get_name()}: capsule now blocks Visibility (shootable)")


def hit_zones(mesh_asset):
    """(head, limbs, body): the physics-asset bodies of a mesh, by zone.

    Only bones with a body can ever come back from a trace, so the tables list
    exactly those. The physics asset's SkeletalBodySetups are protected from
    Python, but every body is one end of a constraint, and the constraints are
    readable. The zone test walks the real skeleton (BoneIsChildOf on a
    transient component), so a renamed or re-parented bone moves with it rather
    than falling out of a hand-written list.
    """
    pa = mesh_asset.get_editor_property("physics_asset")
    if not pa:
        raise RuntimeError(f"{mesh_asset.get_name()} has no physics asset — "
                           "there are no bodies for a hit to land on")
    bodies = set()
    for constraint in pa.get_constraints(False):
        ends = unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names(constraint)
        bodies.update(str(n) for n in ends if isinstance(n, unreal.Name))
    bodies.discard("None")

    probe = unreal.SkeletalMeshComponent()
    probe.set_skeletal_mesh_asset(mesh_asset)

    def under(bone, roots):
        return any(bone == root or probe.bone_is_child_of(bone, root) for root in roots)

    # FName comparison is case-insensitive, so "head" already finds "Head";
    # the pairs that actually differ are the limbs.
    lower = {b.lower(): b for b in bodies}

    def resolve(candidates, role):
        for c in candidates:
            if c.lower() in lower:
                return lower[c.lower()]
        raise RuntimeError(
            f"{pa.get_name()} has no body for {role} (tried {list(candidates)}) "
            "— that zone could never be hit. Add this rig's bone name to "
            "HEAD_CANDIDATES / LIMB_CANDIDATES.")

    head_roots = (resolve(HEAD_CANDIDATES, "the head"),)
    limb_roots = tuple(resolve(c, f"limb {i + 1}")
                       for i, c in enumerate(LIMB_CANDIDATES))
    head = sorted(b for b in bodies if under(b, head_roots))
    limbs = sorted(b for b in bodies if under(b, limb_roots))
    return head, limbs, sorted(bodies - set(head) - set(limbs))


def install_hit_zones(bp, health_handle):
    """Write this character's own hit-box tables onto its HealthComponent.

    Per character, on the component template -- the same place DespawnOnDeath
    goes -- because the tables describe *this* skeleton; a character with a
    different rig gets different bones with no change to the graph.
    """
    mesh = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            mesh = obj
            break
    if mesh is None:
        raise RuntimeError(f"{bp.get_name()} has no SkeletalMeshComponent to zone")
    # K2_LineTraceComponent walks the mesh's physics bodies, and a mesh with
    # collision off never creates them: every hit would be a body hit and
    # nothing would say so.
    if mesh.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION:
        raise RuntimeError(f"{bp.get_name()}'s mesh has no collision — "
                           "it has no physics bodies to tell head from leg")
    head, limbs, body = hit_zones(mesh.get_editor_property("skeletal_mesh_asset"))
    comp = _component_object(health_handle)
    comp.set_editor_property(HEAD_BONES_VAR, [unreal.Name(b) for b in head])
    comp.set_editor_property(LIMB_BONES_VAR, [unreal.Name(b) for b in limbs])
    got = ([str(b) for b in comp.get_editor_property(HEAD_BONES_VAR)],
           [str(b) for b in comp.get_editor_property(LIMB_BONES_VAR)])
    if got != (head, limbs):
        raise RuntimeError(f"{bp.get_name()}'s hit-box tables did not stick: {got}")
    _log(f"{bp.get_name()}: hit boxes — head {head} x{COMBAT.head_multiplier}, "
         f"limbs {len(limbs)} bodies x{COMBAT.limb_multiplier}, body {body} x1.0")
