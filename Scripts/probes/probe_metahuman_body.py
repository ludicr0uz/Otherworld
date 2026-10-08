"""The MetaHuman body follows the mannequin in the running game.

The player's mannequin is hidden and still runs ABP_Unarmed; the MetaHuman
body hangs under it wearing ABP_MetaHuman_Retarget (combat/metahuman_body.py)
and should land on the same pose every frame: head over head, hands on hands,
feet on feet, within the proportion difference of two different men. The
face and the clothing should follow the body. Measured standing, then in a
fall (the jump clip), then dead, when the mannequin's ragdoll should carry
the MetaHuman down with it.
"""

import unreal

from combat import health_vars as HV
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH

WRITABLE = [(HEALTH_BP_PATH, HV.Health)]
DROP_CM = 900.0
# A MetaHuman limb ends where the mannequin's does, give or take the two
# bodies' proportions: the retargeter scales, it does not pin.
FOLLOW_CM = 12.0
# A garment is skinned to the body's bones and should sit on them.
GARMENT_CM = 1.5
BONES = ("head", "hand_l", "hand_r", "foot_l", "foot_r", "pelvis", "spine_05")


def _comp(actor, name):
    for c in actor.get_components_by_class(unreal.ActorComponent):
        if c.get_name() == name:
            return c
    return None


def _gap(a, b, bone):
    return (a.get_socket_location(bone) - b.get_socket_location(bone)).length()


def _follow(p, label, mannequin, body, face, torso, legs, feet):
    gaps = {b: _gap(mannequin, body, b) for b in BONES}
    p.note(f"{label}: MetaHuman to mannequin, cm: "
           + ", ".join(f"{b} {g:.1f}" for b, g in gaps.items()))
    worst = max(gaps.items(), key=lambda kv: kv[1])
    p.check(f"{label}: the MetaHuman body is on the mannequin's pose "
            f"(every bone within {FOLLOW_CM:.0f} cm)", worst[1] < FOLLOW_CM,
            f"worst {worst[0]} {worst[1]:.1f} cm")
    p.check(f"{label}: the face is on the body's head",
            _gap(body, face, "head") < 1.0, f"{_gap(body, face, 'head'):.1f} cm")
    for name, comp, bones in (("hoodie", torso, ("spine_02", "spine_04", "upperarm_l", "hand_l")),
                              ("jeans", legs, ("pelvis", "thigh_l", "calf_l", "foot_l")),
                              ("shoes", feet, ("calf_l", "foot_l", "ball_l", "foot_r"))):
        gaps = {b: _gap(body, comp, b) for b in bones}
        worst = max(gaps.items(), key=lambda kv: kv[1])
        p.check(f"{label}: the {name} are on the body (within {GARMENT_CM:.0f} cm)",
                worst[1] < GARMENT_CM,
                ", ".join(f"{b} {g:.1f}" for b, g in gaps.items()))


def probe(p):
    yield 0.5
    player = p.pawn()
    mannequin = player.get_editor_property("mesh")
    body, face, torso, legs, feet = (_comp(player, n)
                                     for n in ("Body", "Face", "Torso", "Legs", "Feet"))
    p.check("the player has Body, Face and Torso components",
            all(c is not None for c in (body, face, torso)))
    if not all(c is not None for c in (body, face, torso)):
        return
    # The garments tick only when rendered (the MetaHuman component sets
    # that at BeginPlay, as the sample does) and a headless game renders
    # nothing: posed always, here, so they can be measured.
    for comp in (torso, legs, feet):
        comp.set_editor_property(
            "visibility_based_anim_tick_option",
            unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
            unreal.PropertyAccessChangeNotifyMode.NEVER)
    p.note(f"mannequin {mannequin.get_skeletal_mesh_asset().get_name()} "
           f"visible={mannequin.is_visible()}, body "
           f"{body.get_skeletal_mesh_asset().get_name()} visible={body.is_visible()}")
    p.check("the mannequin is hidden and the MetaHuman body is drawn",
            not mannequin.is_visible() and body.is_visible())
    inst = body.get_anim_instance()
    p.check("the body runs ABP_MetaHuman_Retarget",
            inst is not None and inst.get_class().get_name() == "ABP_MetaHuman_Retarget_C",
            inst.get_class().get_name() if inst else "no anim instance")
    finst = face.get_anim_instance()
    p.check("the face runs Face_AnimBP",
            finst is not None and finst.get_class().get_name() == "Face_AnimBP_C",
            finst.get_class().get_name() if finst else "no anim instance")
    for name in ("Torso", "Legs", "Feet"):
        pp = _comp(player, name).get_post_process_instance()
        p.note(f"{name} post-process anim: {pp.get_class().get_name() if pp else None}")
    yield 1.0
    _follow(p, "standing", mannequin, body, face, torso, legs, feet)

    at = player.get_actor_location()
    player.set_actor_location(unreal.Vector(at.x, at.y, at.z + DROP_CM), False, True)
    move = player.get_component_by_class(unreal.CharacterMovementComponent)
    yield lambda: move.is_falling()
    yield 0.45
    _follow(p, "falling", mannequin, body, face, torso, legs, feet)
    yield lambda: not move.is_falling()
    yield 1.0
    _follow(p, "landed", mannequin, body, face, torso, legs, feet)

    health = p.component(player, HEALTH_CLASS_PATH)
    p.set(health, HV.Health, 0.0)
    yield 0.9
    ground = player.get_actor_location().z - player.get_component_by_class(
        unreal.CapsuleComponent).get_scaled_capsule_half_height()
    p.note(f"dead: mannequin simulating {mannequin.is_any_simulating_physics()}, "
           f"body simulating {body.is_any_simulating_physics()}, head over the "
           f"ground: mannequin {mannequin.get_socket_location('head').z - ground:.0f}, "
           f"MetaHuman {body.get_socket_location('head').z - ground:.0f}")
    _follow(p, "dead", mannequin, body, face, torso, legs, feet)
