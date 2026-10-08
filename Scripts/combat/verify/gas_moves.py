"""verify.gas_moves -- the moves the Game Animation Sample ships beyond the
walk and the run (task G5; combat/gas_moves_tuning.py has the three
switches): the crouch as the sample's Stance, the slide as a state of the
movement component posed by the sample's loop, and traversal as the sample's
own component on the player, behind the jump key. Each section checks its
switch both ways: on, that the wiring is there; off, that none of it is.

What they do in a game is probes/probe_gas_traversal.py's.
"""

import unreal

from combat import gas_moves_tuning as T
from combat.gas_locomotion import enum_values, graphs, slot_in_line
from combat.gas_locomotion_consts import (
    ABP_LOCOMOTION, OFFSET_ROOT_CLASS, SKELETON, SLOT_CLASS, SLOT_NAME, TRAVERSING,
)
from combat.gas_traversal_slot import (
    FALSE_PIN, SLOT_IN_S, SLOT_OUT_S, TRUE_PIN, traversal_branches,
)
from combat.gas_moves import crouch_on, slide_on, traversal_on
from combat.gas_traversal import (
    GUARD_TITLE, LEDGE_REACH_CM, TRAVERSAL_CLASS, between, jump_event, jump_nodes,
    properties_sources, server_event,
)
from combat.player_move import slide_numbers
from combat.player_pace import movement_of
from combat.skin import player_skin
from combat.tuning import COMBAT
from combat.verify.common import check, component_template, graph, load, num_pin
from combat.verify.fixtures import char, wc
from combat.weapon_component.stance import CROUCH_FORCED_VAR
from uebp import net
from uebp.graph import BEL, BGE, PIN, _assets
from uebp.nodes.guard import GUARD_CLASS


def _class(node):
    return node.get_class().get_name()


def _title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ")


def _flat(node):
    return _title(node).replace(" ", "")


def _up(pin):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]


def _down(node, pin="then"):
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_output_pin(node, pin))]


def check_crouch():
    bp = load(ABP_LOCOMOTION)
    _anim, _events, properties = graphs(bp)
    nodes = properties.list_all_nodes()
    casts = [n for n in nodes if _flat(n) == "BytetoEnumE_Stance"]
    reads = [n for n in nodes if _flat(n) == "GetStance"]
    if not crouch_on():
        check("the crouch is the weapon layers' two clips (GAS_CROUCH off): the motion "
              "matching is told no stance", not casts and not reads, f"{len(casts)} casts")
        return
    values = enum_values(bp)["Stance"]
    picks = [n for c in casts for n in _up(BEL.find_input_pin(c, "Byte"))]
    picks = [n for p in picks for n in _up(BEL.find_input_pin(p, "InInt"))]
    check("the motion matching's Stance is Crouch while the movement component says the "
          "character is crouched and not prone (GetStance == 1), else Stand: the sample's "
          "crouch set plays, on every machine",
          len(casts) == 1 and len(reads) == 1 and len(picks) == 1
          and num_pin(picks[0], "A") == values["CROUCH"]
          and num_pin(picks[0], "B") == values["STAND"]
          and any(num_pin(e, "B") == 1 for e in _up(BEL.find_input_pin(picks[0], "bPickA"))),
          f"{len(casts)} casts, {len(reads)} reads, {len(picks)} picks")


def check_slide():
    movement = movement_of(char)
    got = {name: movement.get_editor_property(name) for name in slide_numbers()}
    check(f"the movement component's slide is {'on' if slide_on() else 'off'} "
          "(gas_moves_tuning.GAS_SLIDE, on the motion-matching body)",
          got == slide_numbers(), str(got))
    check(f"...{T.SLIDE_SECONDS:g} s long, from a sprint going at least "
          f"{T.SLIDE_MIN_START_SCALE:g} of its speed",
          abs(movement.get_editor_property("slide_seconds") - T.SLIDE_SECONDS) < 1e-4
          and abs(movement.get_editor_property("slide_min_start_speed")
                  - T.SLIDE_MIN_START_SCALE * COMBAT.sprint_speed_cms) < 1e-3
          and 0.0 < T.SLIDE_MIN_START_SCALE < 1.0)
    nodes = graph(wc).list_all_nodes()
    asks = [n for n in nodes if _flat(n) == "RequestSlide"]
    reads = [n for n in nodes if _flat(n) == "IsSliding"]
    declared = _has_var(load(player_skin().anim_bp), T.POSE_SLIDE)
    if not slide_on():
        check("...and nothing asks for one or poses one",
              not asks and not reads and not declared,
              f"{len(asks)} asks, {len(reads)} reads, {T.POSE_SLIDE}: {declared}")
        return
    gates = [g for a in asks for g in _up(BEL.find_input_pin(a, "execute"))]
    conds = [c for g in gates if _class(g) == "K2Node_IfThenElse"
             for c in _up(BEL.find_input_pin(g, "Condition"))]
    ands = [n for c in conds for p in BEL.list_input_pins(c) for n in _up(p)]
    feeds = {_title(n) for n in ands}
    press = {_flat(n) for o in ands if _title(o) == "OR Boolean"
             for p in BEL.list_input_pins(o) for n in _up(p)}
    check("the crouch key pressed in a sprint asks the movement for a slide: one "
          "RequestSlide, behind a Branch on (the key just pressed OR the probe's "
          f"{CROUCH_FORCED_VAR}) AND Sprinting",
          len(asks) == 1 and len(conds) == 1 and "Get Sprinting" in feeds
          and f"Get{CROUCH_FORCED_VAR}" in press
          and any("WasInputKeyJustPressed" in f for f in press),
          f"{sorted(feeds)} <- {sorted(press)}")
    spends = [n for n in nodes if _title(n) == f"Set {CROUCH_FORCED_VAR}"]
    check(f"...and {CROUCH_FORCED_VAR} is spent after the slide's Branch has read it, so "
          "a probe's press is one press",
          len(spends) == 1
          and {_flat(n) for n in _up(BEL.find_input_pin(spends[0], "execute"))}
          == {"RequestSlide", "Branch"}, str([_title(n) for n in spends]))
    check(f"...and {T.POSE_SLIDE} on the weapon layers eases to the movement's own "
          "IsSliding (another player's copy and the server's slide with it)",
          len(reads) == 1 and declared, f"{len(reads)} reads, declared: {declared}")
    clip = load(T.SLIDE_CLIP)
    check("the slide's clip is the sample's loop, on the body's skeleton, holding its own "
          "root (force_root_lock: a sequence player keeps it in place)",
          clip is not None and clip.get_editor_property("force_root_lock")
          and clip.get_editor_property("skeleton").get_path_name().split(".")[0]
          == SKELETON, str(clip))


def _has_var(bp, name):
    try:
        unreal.get_default_object(BEL.generated_class(bp)).get_editor_property(name)
        return True
    except Exception:
        return False


def check_traversal_component():
    """The sample's component as patched: it stays patched whatever the
    switch says (it is how it runs on any Character)."""
    if not _assets().does_asset_exist(T.TRAVERSAL_BP):
        return
    bp = load(T.TRAVERSAL_BP)
    events = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tries = BGE.get_graph_editor_by_name(bp, T.TRY_GRAPH)
    sources = properties_sources(events) + properties_sources(tries)
    fed = [sorted(str(PIN.get_pin_name(p)).split("_")[0]
                  for p in BEL.list_input_pins(src) if PIN.list_connected_pins(p))
           for _put, src in sources if src is not None]
    messages = [n for ed in (events, tries) for n in ed.list_all_nodes()
                if _class(n) == "K2Node_Message" and T.PROPERTIES_MESSAGE in _title(n)]
    check("the traversal component reads any Character: both writes of "
          f"{T.PROPERTIES_VAR} are a struct made from the owner (the capsule, the mesh, "
          "the MotionWarping component, the gait, the mode, the speed), and no call "
          "through the sample's pawn interface is left",
          len(sources) == 2 and not messages
          and all(_class(src) == "K2Node_MakeStruct" for _put, src in sources)
          and all(f == sorted(T.TRAVERSAL_FIELDS) for f in fed), str(fed))
    # A rebuild that walked upstream through an exec pin once took these out.
    begins = [n for n in events.list_all_nodes() if _class(n) == "K2Node_Event"
              and "BeginPlay" in _flat(n)]
    entries = [n for n in tries.list_all_nodes() if _class(n) == "K2Node_FunctionEntry"]
    check(f"...and the graphs are whole after a rebuild: BeginPlay still runs the read, "
          f"and {T.TRY_GRAPH}'s entry still leads into its body",
          len(begins) == 1 and len(entries) == 1
          and [_flat(n) for n in _down(begins[0])] == ["CastToCharacter"]
          and len(_down(entries[0])) == 1
          and all(len(_up(BEL.find_input_pin(put, "execute"))) == 1 for put, _src in sources),
          f"{[_title(n) for b in begins for n in _down(b)]}, "
          f"{[_title(n) for e in entries for n in _down(e)]}")
    event = server_event(events)
    first = _down(event)
    allow = first[0] if len(first) == 1 and _title(first[0]) == GUARD_TITLE else None
    named = allow is not None and \
        str(PIN.get_pin_value(BEL.find_input_pin(allow, "Name"))) == T.SERVER_EVENT
    guards = [n for n in _up(BEL.find_input_pin(allow, "self"))] if allow else []
    asked = any(str(PIN.get_pin_value(BEL.find_input_pin(g, "ComponentClass"))) == GUARD_CLASS
                for g in guards)
    check(f"its Server event ({T.SERVER_EVENT}) asks the player's RPC guard first, by "
          "its own name (no row in the table: the default rate)",
          net.event_rpc(event)[0] == net.SERVER and named and asked,
          f"first: {[_title(n) for n in first]}")
    gate = _down(allow)[0] if allow else None
    reach = _down(gate)[0] if gate is not None and _class(gate) == "K2Node_IfThenElse" else None
    cond = _up(BEL.find_input_pin(reach, "Condition")) if reach is not None \
        and _class(reach) == "K2Node_IfThenElse" else []
    check(f"...then refuses a ledge further than {LEDGE_REACH_CM:g} cm from the server's "
          "copy of the character, and only then tells the clients",
          len(cond) == 1 and num_pin(cond[0], "B") == LEDGE_REACH_CM
          and [_flat(n) for n in _down(reach)] == ["PerformTraversalAction_Clients"],
          str([_title(n) for n in cond]))


def check_traversal_slot():
    bp = load(ABP_LOCOMOTION)
    anim, _events, properties = graphs(bp)
    branches = traversal_branches(anim)
    writes = [n for n in properties.list_all_nodes() if _title(n) == f"Set {TRAVERSING}"]
    if not traversal_on():
        check("no traversal: the sample's montage slot is out of the pose line, and "
              f"nothing writes or reads {TRAVERSING}",
              not branches and not writes and not slot_in_line(anim),
              f"{len(branches)} branches, {len(writes)} writes")
        return
    branch = branches[0] if len(branches) == 1 else None
    arm = {name: _up(BEL.find_input_pin(branch, name)) if branch else []
           for name in (TRUE_PIN, FALSE_PIN)}
    slot = arm[TRUE_PIN][0] if len(arm[TRUE_PIN]) == 1 else None
    under = _up(BEL.find_input_pin(slot, "Source")) if slot is not None else []
    check("the sample's montage slot is in the pose line only while a traversal plays: "
          f"one blend by {TRAVERSING} in front of the root's offset, the slot on its "
          "true arm over the same pose its false arm takes (the weapon layers' poses "
          "play in a slot of the same name, and here they would be the whole body's)",
          branch is not None and slot is not None and _class(slot) == SLOT_CLASS
          and SLOT_NAME in _title(slot) and len(under) == 1 and len(arm[FALSE_PIN]) == 1
          and under[0].get_name() == arm[FALSE_PIN][0].get_name()
          and [_class(n) for n in _down(branch, "Pose")] == [OFFSET_ROOT_CLASS],
          f"{len(branches)} branches; true <- {[_title(n) for n in arm[TRUE_PIN]]}")
    if branch is not None:
        times = list(branch.get_editor_property("node").get_editor_property("blend_time"))
        check(f"...into the slot at once and back out over {SLOT_OUT_S:g} s",
              [round(t, 3) for t in times] == [SLOT_IN_S, SLOT_OUT_S], str(times))
    gates = [g for w in writes for g in _up(BEL.find_input_pin(w, "execute"))]
    check(f"...and {TRAVERSING} is the pawn's traversal component's {T.DOING_VAR}, "
          "copied each update behind an IsValid",
          len(writes) == 1 and len(gates) == 1 and _class(gates[0]) == "K2Node_IfThenElse"
          and [_flat(n) for n in _up(BEL.find_input_pin(gates[0], "Condition"))] == ["IsValid"]
          and [_title(n) for n in _up(BEL.find_input_pin(writes[0], TRAVERSING))]
          == [f"Get {T.DOING_VAR}"], f"{len(writes)} writes")


def check_traversal_player():
    parts = {name: component_template(char, name)
             for name in (T.TRAVERSAL_COMPONENT, T.WARP_COMPONENT)}
    ed = graph(char)
    key, jump = jump_nodes(ed)
    mine = between(ed)
    if not traversal_on():
        check("no traversal (GAS_TRAVERSAL off, or no motion-matching body): the player "
              "has neither component and the jump key runs Jump alone",
              not any(parts.values()) and not mine,
              f"{[k for k, v in parts.items() if v]}, {len(mine)} nodes")
        return
    check(f"the player has the sample's traversal component ({T.TRAVERSAL_COMPONENT}), "
          f"which replicates, and a MotionWarping component ({T.WARP_COMPONENT})",
          all(parts.values())
          and parts[T.TRAVERSAL_COMPONENT].get_class().get_path_name() == TRAVERSAL_CLASS
          and parts[T.WARP_COMPONENT].get_class().get_path_name() == T.WARP_CLASS
          and net.replicates(char, T.TRAVERSAL_COMPONENT),
          str({k: v.get_class().get_name() if v else None for k, v in parts.items()}))
    tries = [n for n in mine if _flat(n) == T.TRY_GRAPH]
    gates = [n for n in mine if _class(n) == "K2Node_IfThenElse"]
    calls = _down(key, "Started")
    event = jump_event(ed)
    first = _down(event) if event is not None else []
    check(f"the jump key calls {T.JUMP_EVENT} (a probe's press of it), which tries a "
          "traversal first: Branch (on the ground, standing, not already in one) -> "
          "TryTraversalAction -> Branch -> Jump only when the check or the montage "
          "choice failed",
          len(calls) == 1 and _flat(calls[0]) == T.JUMP_EVENT
          and len(tries) == 1 and len(gates) == 2 and len(first) == 1
          and _class(first[0]) == "K2Node_IfThenElse"
          and [n.get_name() for n in _down(first[0])] == [tries[0].get_name()]
          and [n.get_name() for n in _down(first[0], "else")] == [jump.get_name()]
          and [n.get_name() for g in gates if g.get_name() != first[0].get_name()
               for n in _down(g)] == [jump.get_name()],
          f"{len(tries)} tries, {len(gates)} branches")
    asks = [n for t in tries for p in BEL.list_input_pins(t) for n in _up(p)
            if _class(n) == "K2Node_MakeStruct"]
    sweep = {str(PIN.get_pin_name(p)).split("_")[0]: PIN.get_pin_value(p)
             for a in asks for p in BEL.list_input_pins(a)}
    check(f"...sweeping {T.TRACE_NEAR_CM:g} to {T.TRACE_FAR_CM:g} cm ahead by speed, "
          f"radius {T.TRACE_RADIUS_CM:g}, half height {T.TRACE_HALF_HEIGHT_CM:g} (the "
          "sample's own numbers on the ground)",
          len(asks) == 1
          and abs(float(sweep.get("TraceRadius") or 0) - T.TRACE_RADIUS_CM) < 1e-4
          and abs(float(sweep.get("TraceHalfHeight") or 0) - T.TRACE_HALF_HEIGHT_CM) < 1e-4,
          str({k: v for k, v in sweep.items() if k.startswith("Trace")}))
    check("the block it climbs and the montage chooser are here",
          _assets().does_asset_exist(T.BLOCK_BP)
          and _assets().does_asset_exist(T.MONTAGE_CHOOSER))


def run():
    if not player_skin().gas and not _assets().does_asset_exist(ABP_LOCOMOTION):
        return
    if _assets().does_asset_exist(ABP_LOCOMOTION):
        check_crouch()
    check_slide()
    check_traversal_component()
    if _assets().does_asset_exist(ABP_LOCOMOTION):
        check_traversal_slot()
    check_traversal_player()
