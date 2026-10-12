"""What a wanderer is heard and seen to do on every machine (npc/body_fx.py,
task M27): the body's two Multicast events, and that no controller plays a
sound or a clip of its own, which only the server would hear or see.

That a client's copy of a wanderer plays them is
probes/probe_net_npc_target.py's (its VoicesPlayed and ClipsPlayed).
"""

import unreal

from forest_generator.npc_placement import NPC_VARIANTS
from npc import body_vars as BV
from npc.paths import AI_BP_PATH, NPC_BP_PATH
from npc.verify import BEL, PIN, _drivers, _feeders, _ins, _title, _titled, check
from npc.verify_stalk_cover import _titles
from uebp import net


def _event(nodes, name):
    return [n for n in nodes if n.get_class().get_name() == "K2Node_CustomEvent"
            and _title(n).split(" ")[0] == name]


def check_body():
    tag = NPC_BP_PATH.rsplit("/", 1)[-1]
    bp = unreal.load_asset(NPC_BP_PATH)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    for name, params, count, plays in (
            (BV.VOICE_EVENT, BV.VOICE_PARAMS, BV.VoicesPlayed, "PlaySoundAtLocation"),
            (BV.CLIP_EVENT, BV.CLIP_PARAMS, BV.ClipsPlayed,
             "PlaySlotAnimationAsDynamicMontage")):
        check(f"{tag}: {name} is a Multicast, unreliable (a lost one loses a "
              f"sound or the sight of a swing, never the blow)",
              net.compiled_rpc(bp, name) == (net.MULTICAST, False),
              f"{net.compiled_rpc(bp, name)}")
        events, played = _event(nodes, name), _titled(nodes, plays)
        counted = [d for p in played for d in _drivers(p)]
        check(f"{tag}: ...it counts itself in {count}, then {plays} with what "
              f"the server sent ({', '.join(p for p, _ in params)})",
              len(events) == 1 and len(played) == 1 and len(counted) == 1
              and _title(counted[0]) == f"Set {count}" and _drivers(counted[0]) == events
              and all(_feeders(played[0], p) == events for p, _ in params))
    slot = _titled(nodes, "PlaySlotAnimationAsDynamicMontage")
    check(f"{tag}: ...the clip into this body's own mesh's AnimInstance",
          len(slot) == 1 and _titles(_feeders(slot[0], "self")) == {"GetAnimInstance"}
          and all(_titles(_feeders(a, "self")) == {"Get Mesh"}
                  for a in _feeders(slot[0], "self")))


def check_controller(path):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.load_asset(path)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    own = sorted({_title(n) for n in nodes
                  if _title(n) in ("PlaySoundAtLocation", "PlaySlotAnimationAsDynamicMontage",
                                   "GetAnimInstance")})
    check(f"{tag}: plays no sound and no clip of its own (the controller is the "
          f"server's alone: a client would hear and see nothing)", not own, f"{own}")
    tells = [n for n in nodes if _title(n) in (BV.VOICE_EVENT, BV.CLIP_EVENT)]
    voices = [n for n in tells if {"Sound", "Location"} <= _ins(n)]
    clips = [n for n in tells if {"Asset", "SlotNodeName"} <= _ins(n)]
    check(f"{tag}: every voice and clip goes to its body's Multicast, on the "
          f"pawn cast to {NPC_BP_PATH.rsplit('/', 1)[-1]}",
          len(voices) >= 3 and len(clips) >= 1 and len(voices) + len(clips) == len(tells)
          and all(_titles(_feeders(t, "self")) == {BV.BODY_CAST_TITLE}
                  and _feeders(t, "self") == _drivers(t) for t in tells),
          f"{len(voices)} voice(s), {len(clips)} clip(s)")
    after = [PIN.get_owning_node(q) for t in tells
             for c in _drivers(t)
             for q in PIN.list_connected_pins(BEL.find_output_pin(c, "CastFailed"))]
    check(f"{tag}: ...and a pawn of another class goes on without one (the "
          f"cast's failure is wired on, so the step still ends)",
          len(after) == len(tells) and all(_title(n) == "Branch" for n in after))


def run():
    check_body()
    for path in [AI_BP_PATH] + [variant.ai_blueprint for variant in NPC_VARIANTS]:
        check_controller(path)
