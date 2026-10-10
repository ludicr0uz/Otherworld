"""The MetaHuman body follows the mannequin in the running game.

The player's mannequin is hidden and runs the game's animation (the
motion matching on the UEFN mannequin, or ABP_Unarmed: combat/skin.py); the
MetaHuman body hangs under it wearing that skin's retargeting anim Blueprint
(combat/metahuman_body.py) and should land on the same pose every frame: head over head, hands on hands,
feet on feet, within the proportion difference of two different men. The
face should follow the body, and the three garment components are there
but bare (the body starts in its underwear). Measured standing, then in a
fall (the jump clip), then dead, when the mannequin's ragdoll should carry
the MetaHuman down with it.
"""

SYSTEMS = ('animation',)

import unreal

from asset_pipeline.metahuman_paths import ABP_RETARGET
from combat import health_vars as HV
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from combat.skin import skin_of_mesh

from probes.metahuman_follow import _comp, _follow, _undressed

WRITABLE = [(HEALTH_BP_PATH, HV.Health)]
DROP_CM = 900.0


def probe(p):
    yield 0.5
    player = p.pawn()
    mannequin = player.get_editor_property("mesh")
    body, face, torso, legs, feet = (_comp(player, n)
                                     for n in ("Body", "Face", "Torso", "Legs", "Feet"))
    p.check("the player has Body, Face, Torso, Legs and Feet components",
            all(c is not None for c in (body, face, torso, legs, feet)))
    if not all(c is not None for c in (body, face, torso, legs, feet)):
        return
    _undressed(p, torso, legs, feet)
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
    # The retargeter whose source rig is on the worn mesh's skeleton.
    skin = skin_of_mesh(mannequin.get_skeletal_mesh_asset().get_path_name())
    want = (getattr(skin, "retarget", None) or ABP_RETARGET).rsplit("/", 1)[1]
    p.check(f"the body runs {want}",
            inst is not None and inst.get_class().get_name() == f"{want}_C",
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
