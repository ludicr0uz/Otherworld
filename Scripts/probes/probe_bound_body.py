"""The worn body's bones in the running game: standing, falling and dead.

A body's bones are a fixed length. A clip turns them; nothing in this game is
meant to stretch one. So each bone's distance to its parent is measured
standing, again in a fall (the body is lifted and dropped: MM_Fall_Loop), and
again as a corpse, and any bone whose length changed is named with by how
much. Written for a body bound to the mannequin's skeleton
(asset_pipeline/mannequin_bind), where the anim blueprint is the mannequin's
own and its Control Rig knows the mannequin's proportions, not this body's.

The player dies here; no profile is on disk for death to delete when this
was written, and a run that has one should set it aside first
(probe_dead_no_actions.py does).
"""

SYSTEMS = ('animation',)

import unreal

from combat import health_vars as HV
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH

WRITABLE = [(HEALTH_BP_PATH, HV.Health)]
DROP_CM = 900.0
STRETCHED_CM = 0.5


def _lengths(mesh):
    """{bone: cm to its parent} as the body is posed now."""
    out = {}
    for i in range(mesh.get_num_bones()):
        bone = mesh.get_bone_name(i)
        parent = mesh.get_parent_bone(bone)
        if str(parent) in ("", "None"):
            continue
        out[str(bone)] = (mesh.get_socket_location(bone)
                          - mesh.get_socket_location(parent)).length()
    return out


def _span(mesh, a, b):
    return (mesh.get_socket_location(a) - mesh.get_socket_location(b)).length()


def _shape(mesh):
    return {"pelvis to head": _span(mesh, "pelvis", "head"),
            "pelvis to spine_05": _span(mesh, "pelvis", "spine_05"),
            "shoulder to shoulder": _span(mesh, "upperarm_l", "upperarm_r"),
            "clavicle to clavicle": _span(mesh, "clavicle_l", "clavicle_r")}


def _report(p, label, now, rest, shape, rest_shape):
    off = sorted(((now[b] - rest[b], b) for b in rest
                  # The pelvis's distance to the root is its height: a clip's.
                  if abs(now[b] - rest[b]) > STRETCHED_CM
                  and not b.startswith("ik_") and b != "pelvis"),
                 key=lambda t: -abs(t[0]))
    p.note(f"{label}: " + ", ".join(f"{k} {v:.1f} (standing {rest_shape[k]:.1f})"
                                    for k, v in shape.items()))
    p.note(f"{label}: {len(off)} bones changed length: "
           + ", ".join(f"{b} {d:+.1f}" for d, b in off[:14]))
    p.check(f"{label}: no bone is stretched (within {STRETCHED_CM} cm of its "
            "standing length)", not off, f"{len(off)} bones, worst "
            + (f"{off[0][1]} {off[0][0]:+.1f} cm" if off else "-"))


def probe(p):
    yield 0.5
    player = p.pawn()
    mesh = player.get_editor_property("mesh")
    mesh.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)
    asset = mesh.get_skeletal_mesh_asset()
    physics = asset.get_editor_property("physics_asset")
    p.note(f"worn {asset.get_path_name().split('.')[0]} on "
           f"{mesh.get_anim_instance().get_class().get_name()}, physics "
           f"{physics.get_name() if physics else None}")
    yield 1.0
    rest, rest_shape = _lengths(mesh), _shape(mesh)
    p.note("standing: " + ", ".join(f"{k} {v:.1f}" for k, v in rest_shape.items()))

    at = player.get_actor_location()
    player.set_actor_location(unreal.Vector(at.x, at.y, at.z + DROP_CM), False, True)
    move = player.get_component_by_class(unreal.CharacterMovementComponent)
    yield lambda: move.is_falling()
    yield 0.45
    p.check("the body is falling when it is measured", move.is_falling())
    _report(p, "falling", _lengths(mesh), rest, _shape(mesh), rest_shape)
    yield lambda: not move.is_falling()
    yield 1.0
    _report(p, "landed", _lengths(mesh), rest, _shape(mesh), rest_shape)

    health = p.component(player, HEALTH_CLASS_PATH)
    p.set(health, HV.Health, 0.0)
    # The game pauses a little over two seconds after a death, and a paused
    # game's clock stops: everything is measured before that.
    for wait in (0.3, 0.6, 0.9):
        yield wait
        heights = {b: mesh.get_socket_location(b).z for b in
                   ("head", "pelvis", "hand_l", "hand_r", "foot_l", "foot_r")}
        ground = player.get_actor_location().z - player.get_component_by_class(
            unreal.CapsuleComponent).get_scaled_capsule_half_height()
        p.note(f"dead +{wait}: simulating {mesh.is_any_simulating_physics()}, profile "
               f"{mesh.get_collision_profile_name()}, heights over the ground "
               + ", ".join(f"{b} {z - ground:.0f}" for b, z in heights.items()))
    _report(p, "dead", _lengths(mesh), rest, _shape(mesh), rest_shape)
