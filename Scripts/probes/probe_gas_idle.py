"""The skeleton bridge, proven on one idle: the player's hidden mesh as the
Game Animation Sample's UEFN mannequin, playing the sample's standing idle,
with the MetaHuman following it.

The game does not wear this yet (asset_pipeline/build_gas_bridge.py builds
the pieces, Scripts/asset_pipeline/CLAUDE.md "The skeleton bridge" says why
this bridge). So the probe puts it on the live player for the run: the Mesh
component takes SKM_UEFN_Mannequin and ABP_GasIdle, the Body component takes
ABP_MetaHuman_Retarget_UEFN, and it reads what the hidden mesh plays, that
its pose is a frame of that clip, and how far the MetaHuman stands from it,
by probe_metahuman_body's own measure and tolerance. Then it puts the
mannequin back and checks the body is on it again.
"""

SYSTEMS = ('animation',)

import unreal

from asset_pipeline.gas_bridge_paths import (
    ABP_GAS_IDLE, ABP_RETARGET_UEFN, HIDDEN_MESH_GAS, IDLE_CLIP,
)
from asset_pipeline.gas_idle_abp import playing
from asset_pipeline.rig_util import _bone_world
from probes.metahuman_follow import BONES, FOLLOW_CM, _comp, _follow, _gap

# The live pose against the clip's own frames: the limbs' ends, in the
# mesh's space. An idle barely moves, so some frame is within this of it.
CLIP_BONES = ("head", "hand_l", "hand_r", "foot_l", "foot_r")
CLIP_CM = 2.0
CLIP_STEP_S = 0.1
# The reference pose is an A-pose and the idle hangs its arms: the hands of
# a mesh that plays nothing are further than this from the clip's.
UNPOSED_CM = 10.0
# The retarget pose is aligned chain to chain (build_gas_bridge.py), fingers
# too: a finger chain turned the wrong way shows at its tip.
FINGERTIPS = ("thumb_03_l", "index_03_l", "pinky_03_l",
              "thumb_03_r", "index_03_r", "pinky_03_r")
COMPONENT = unreal.RelativeTransformSpace.RTS_COMPONENT
NEVER = unreal.PropertyAccessChangeNotifyMode.NEVER


def _class(pkg):
    return unreal.load_class(None, f"{pkg}.{pkg.rsplit('/', 1)[1]}_C")


def _in_mesh(comp, bone):
    return comp.get_socket_transform(bone, COMPONENT).translation


def _clip_gap(comp, clip):
    """(cm, s): how far the component's pose is from the clip's nearest
    frame, the worst of CLIP_BONES, and when that frame is."""
    live = {b: _in_mesh(comp, b) for b in CLIP_BONES}
    best = (1e9, 0.0)
    for i in range(int(clip.get_play_length() / CLIP_STEP_S)):
        t = i * CLIP_STEP_S
        worst = max((live[b] - _bone_world(clip, b, t)).length() for b in CLIP_BONES)
        best = min(best, (worst, t))
    return best


def probe(p):
    yield 0.5
    player = p.pawn()
    hidden = player.get_editor_property("mesh")
    body, face, torso, legs, feet = (_comp(player, n)
                                     for n in ("Body", "Face", "Torso", "Legs", "Feet"))
    p.check("the player has a MetaHuman body under its mesh",
            all(c is not None for c in (body, face, torso, legs, feet)))
    if body is None:
        return
    mesh, idle = unreal.load_asset(HIDDEN_MESH_GAS), unreal.load_asset(IDLE_CLIP)
    idle_abp, retarget_abp = _class(ABP_GAS_IDLE), _class(ABP_RETARGET_UEFN)
    p.check("the bridge is built (build_gas_bridge.py)",
            all(x is not None for x in (mesh, idle, idle_abp, retarget_abp)))
    if not all(x is not None for x in (mesh, idle, idle_abp, retarget_abp)):
        return
    for comp in (torso, legs, feet):        # as probe_metahuman_body: posed unseen
        comp.set_editor_property(
            "visibility_based_anim_tick_option",
            unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES, NEVER)
    was_mesh = hidden.get_skeletal_mesh_asset()
    was_anim = hidden.get_anim_instance().get_class()
    was_body_anim = body.get_anim_instance().get_class()
    yield 1.0
    before = {b: _gap(hidden, body, b) for b in BONES}
    p.note(f"before, on {was_mesh.get_name()} and {was_anim.get_name()}, cm: "
           + ", ".join(f"{b} {g:.1f}" for b, g in before.items()))

    unposed = (_in_mesh(hidden, "hand_r") - _bone_world(idle, "hand_r", 0.0)).length()
    hidden.set_skeletal_mesh_asset(mesh)
    hidden.set_anim_instance_class(idle_abp)
    body.set_anim_instance_class(retarget_abp)
    yield 1.0

    skeleton = hidden.get_skeletal_mesh_asset().get_editor_property("skeleton")
    p.check("the hidden mesh is on SK_UEFN_Mannequin, and still hidden",
            skeleton.get_name() == "SK_UEFN_Mannequin" and not hidden.is_visible(),
            f"{hidden.get_skeletal_mesh_asset().get_name()} on {skeleton.get_name()}")
    inst = hidden.get_anim_instance()
    name = inst.get_class().get_name() if inst else "no anim instance"
    clips = [c.split(".")[-1] for c in playing(unreal.load_asset(ABP_GAS_IDLE))]
    p.note(f"the hidden mesh runs {name}, whose graph plays {clips}")
    p.check("the hidden mesh's animation is the sample's standing idle",
            name == "ABP_GasIdle_C" and clips == [idle.get_name()],
            f"{name} plays {clips}")
    cm, at = _clip_gap(hidden, idle)
    p.check(f"its pose is a frame of that clip (limb ends within {CLIP_CM:.0f} cm)",
            cm < CLIP_CM, f"{cm:.2f} cm from the frame at {at:.1f} s")
    if was_mesh.get_editor_property("skeleton") == skeleton:
        # Since G3 the game wears the bridge itself: before the swap the
        # hidden mesh was already this mannequin, standing in the motion
        # matching's own pick of an idle.
        p.check("and the game's own mesh already stood in the sample's idle before the "
                f"swap (its hand within {UNPOSED_CM:.0f} cm of the clip's)",
                unposed <= UNPOSED_CM, f"{unposed:.1f} cm before the swap")
    else:
        p.check("and not a mesh that plays nothing (the mannequin's hand was "
                f"over {UNPOSED_CM:.0f} cm from the clip's)", unposed > UNPOSED_CM,
                f"{unposed:.1f} cm before the swap")
    binst = body.get_anim_instance()
    p.check("the body runs ABP_MetaHuman_Retarget_UEFN",
            binst is not None
            and binst.get_class().get_name() == "ABP_MetaHuman_Retarget_UEFN_C",
            binst.get_class().get_name() if binst else "no anim instance")
    _follow(p, "GAS idle", hidden, body, face, torso, legs, feet)
    tips = {b: _gap(hidden, body, b) for b in FINGERTIPS}
    worst = max(tips.items(), key=lambda kv: kv[1])
    p.check(f"GAS idle: the fingertips follow too (within {FOLLOW_CM:.0f} cm)",
            worst[1] < FOLLOW_CM, ", ".join(f"{b} {g:.1f}" for b, g in tips.items()))
    first = {b: body.get_socket_location(b) for b in ("hand_l", "hand_r")}
    yield 1.5
    moved = max((body.get_socket_location(b) - at_).length() for b, at_ in first.items())
    p.check("the body is posed every frame (the idle's breath moves its hands)",
            1e-3 < moved < FOLLOW_CM, f"{moved:.3f} cm in 1.5 s")

    hidden.set_skeletal_mesh_asset(was_mesh)
    hidden.set_anim_instance_class(was_anim)
    body.set_anim_instance_class(was_body_anim)
    yield 1.0
    _follow(p, "back on the mannequin", hidden, body, face, torso, legs, feet)
