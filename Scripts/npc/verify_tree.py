"""Checks for the wanderers' Blackboard, Behavior Trees, step tasks and step
events (npc/tree.py, step_task.py, steps.py), read back off the saved assets.
Run through Scripts/verify_npc_blueprints.py, after npc/verify.py's run().

What it proves: possession starts this controller's own tree; the tree holds
the priorities (Pulse first, Hunt only while the Blackboard says Aggro, the
senses in the order hurt, sight, touch, sound, the patrol last); every step
the tree names is an event on the controller; and every exit of every step
writes StepResult, which is what the task finishes with; and every step but
Pulse starts at the alive gate (npc/corpse.py), so a dead pawn's step does
nothing. That the gate shuts in the game is probes/probe_dead_no_actions.py.

A stalker's tree (forest_generator/npc_stalk.NPC_STALK_ROAR) has one more
step, Stalk, ahead of Chase in a selector of the two; want_steps() is the
order for a given controller.

A creature afraid of fire (forest_generator/npc_ward.NPC_WARD_FEARS) has a
Ward step ahead of all of that, in a selector with the attack: a pass on
which fire holds it off never reaches the Swing.
"""

import unreal

from forest_generator.npc_placement import NPC_REPATH_SECONDS, NPC_VARIANTS
from forest_generator.npc_stalk import NPC_STALK_ROAR
from forest_generator.npc_ward import NPC_WARD_FEARS
from npc.paths import (
    AI_BP_PATH, BB_AGGRO_KEY, BB_PATH, BB_REASON_KEY, SENSE_STEPS, STEP_CHASE,
    STEP_EVENT_PREFIX, STEP_PRESENT, STEP_PULSE, STEP_RESULT_VAR, STEP_STALK,
    STEP_STROLL, STEP_SWING, STEP_VAR, STEP_WARD, step_task_path, tree_path,
)
from npc.verify import BEL, PIN, _close, _drivers, _ins, _lit, _sources, _title, check

def stalks(ai_path):
    """Is this the controller of a creature that hunts before it chases?"""
    return any(v.ai_blueprint == ai_path and v.key in NPC_STALK_ROAR
               for v in NPC_VARIANTS)


def warded(ai_path):
    """Is this the controller of a creature that fire holds off?"""
    return any(v.ai_blueprint == ai_path and v.key in NPC_WARD_FEARS
               for v in NPC_VARIANTS)


def want_steps(ai_path):
    """The order a pre-order walk of this controller's tree meets the steps
    in: the priorities."""
    return ([STEP_PULSE] + [STEP_WARD] * warded(ai_path)
            + [STEP_STALK] * stalks(ai_path)
            + [STEP_CHASE, STEP_SWING, STEP_PRESENT]
            + [name for _, name in SENSE_STEPS] + [STEP_STROLL])


def _load(path):
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    return eas.load_asset(path) if eas.does_asset_exist(path) else None


def check_blackboard():
    bb = _load(BB_PATH)
    check(f"{BB_PATH.rsplit('/', 1)[-1]} exists", bb is not None)
    if not bb:
        return
    kinds = {str(k.get_editor_property("entry_name")):
             k.get_editor_property("key_type").get_class().get_name()
             for k in bb.get_editor_property("keys")}
    check(f"the Blackboard holds {BB_AGGRO_KEY} (bool) and {BB_REASON_KEY} (string)",
          kinds.get(BB_AGGRO_KEY) == "BlackboardKeyType_Bool"
          and kinds.get(BB_REASON_KEY) == "BlackboardKeyType_String", f"{kinds}")


# ─── The tree ────────────────────────────────────────────────────────────────

def _walk(node, decorators=(), under=()):
    """Pre-order: (node, its decorators, the composites above it)."""
    yield node, list(decorators), under
    if isinstance(node, unreal.BTCompositeNode):
        for child in node.get_editor_property("children"):
            sub = (child.get_editor_property("child_composite")
                   or child.get_editor_property("child_task"))
            yield from _walk(sub, child.get_editor_property("decorators"),
                             under + ((node, list(decorators)),))


def _gates_on_aggro(decorators):
    return any(isinstance(d, unreal.BTDecorator_Blackboard)
               and str(d.get_editor_property("blackboard_key")
                       .get_editor_property("selected_key_name")) == BB_AGGRO_KEY
               and d.get_editor_property("basic_operation") == unreal.BasicKeyOperation.SET
               for d in decorators)


def check_tree(ai_path):
    tag = tree_path(ai_path).rsplit("/", 1)[-1]
    bt = _load(tree_path(ai_path))
    check(f"{tag} exists", bt is not None)
    if not bt:
        return
    check(f"{tag}: reads BB_ForestWanderer",
          bt.get_editor_property("blackboard_asset") == _load(BB_PATH))
    root = bt.get_editor_property("root_node")
    check(f"{tag}: the root is a selector", isinstance(root, unreal.BTComposite_Selector))
    if not root:
        return
    walked = list(_walk(root))
    task = _load(step_task_path(ai_path))
    task_class = BEL.generated_class(task) if task else None
    steps = [(n, d, up) for n, d, up in walked
             if task_class and n.get_class() == task_class]
    order = [str(n.get_editor_property(STEP_VAR)) for n, _, _ in steps]
    want = want_steps(ai_path)
    check(f"{tag}: the steps, in priority order: {', '.join(want)}",
          order == want, f"{order}")
    check(f"{tag}: every task in the tree is the controller's step task",
          all(n.get_class() == task_class for n, _, _ in walked
              if isinstance(n, unreal.BTTaskNode)
              and not isinstance(n, unreal.BTTask_Wait)))

    def above(step):
        return [up for n, _, up in steps if str(n.get_editor_property(STEP_VAR)) == step]

    hunting = ([STEP_WARD] * warded(ai_path) + [STEP_STALK] * stalks(ai_path)
               + [STEP_CHASE, STEP_SWING])
    hunt = [up for s in hunting for up in above(s)]
    check(f"{tag}: {', '.join(hunting[:-1])} and {hunting[-1]} run only under the "
          f"Blackboard's '{BB_AGGRO_KEY} is set'",
          len(hunt) == len(hunting)
          and all(any(_gates_on_aggro(d) for _, d in up) for up in hunt))
    if stalks(ai_path):
        over = [up[-1][0] for s in (STEP_STALK, STEP_CHASE) for up in above(s)]
        check(f"{tag}: Stalk and Chase share one selector, Stalk first: Chase "
              f"runs on the pass Stalk fails",
              len(over) == 2 and over[0] == over[1]
              and isinstance(over[0], unreal.BTComposite_Selector)
              and order.index(STEP_CHASE) == order.index(STEP_STALK) + 1)
    if warded(ai_path):
        # Ward's own selector, and the same one as seen from each attack step.
        over = [up[-1][0] for up in above(STEP_WARD)]
        inner = [[c for c, _ in up] for s in hunting[1:] for up in above(s)]
        check(f"{tag}: Ward and the attack share one selector, Ward first: held "
              f"off by fire, the pass never reaches {', '.join(hunting[1:])}",
              len(over) == 1 and isinstance(over[0], unreal.BTComposite_Selector)
              and order[1] == STEP_WARD and len(inner) == len(hunting) - 1
              and all(over[0] in up and any(
                  isinstance(c, unreal.BTComposite_Sequence)
                  for c in up[up.index(over[0]) + 1:]) for up in inner))
    calm = [up for s in [STEP_PRESENT, STEP_STROLL] + [n for _, n in SENSE_STEPS]
            for up in above(s)]
    check(f"{tag}: ...and nothing else does (notice and patrol are not gated on it)",
          calm and not any(_gates_on_aggro(d) for up in calm for _, d in up))
    senses = [up[-1][0] for _, n in SENSE_STEPS for up in above(n)]
    check(f"{tag}: the senses share one selector: the first that fires wins",
          len({s.get_name() for s in senses}) == 1
          and isinstance(senses[0], unreal.BTComposite_Selector))
    pulse = above(STEP_PULSE)
    check(f"{tag}: Pulse opens every pass (first child of the first sequence)",
          isinstance(walked[1][0], unreal.BTComposite_Sequence)
          and walked[2][0] in [n for n, _, _ in steps]
          and str(walked[2][0].get_editor_property(STEP_VAR)) == STEP_PULSE
          and len(pulse) == 1)
    waits = [n.get_editor_property("wait_time").get_editor_property("default_value")
             for n, _, _ in walked if isinstance(n, unreal.BTTask_Wait)]
    check(f"{tag}: every Wait is the {NPC_REPATH_SECONDS} s re-path beat",
          len(waits) == 3 and all(_close(w, NPC_REPATH_SECONDS) for w in waits),
          f"{waits}")


# ─── The controller's side ───────────────────────────────────────────────────

def _exits(start):
    """Every node reachable from ``start`` along exec wires that runs nothing
    after it."""
    seen, todo, leaves = set(), [start], []
    while todo:
        n = todo.pop()
        if n.get_path_name() in seen:
            continue
        seen.add(n.get_path_name())
        nxt = [PIN.get_owning_node(q) for p in BEL.list_output_pins(n)
               if "exec" in str(PIN.get_pin_type_display_string(p)).lower()
               for q in PIN.list_connected_pins(p)]
        if not nxt:
            leaves.append(n)
        todo += nxt
    return leaves


def _after(pin):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]


def _fails(nodes):
    """Is this one StepResult = false write, with nothing after it?"""
    return (len(nodes) == 1 and _title(nodes[0]) == f"Set {STEP_RESULT_VAR}"
            and _lit(nodes[0], STEP_RESULT_VAR) == "false"
            and not _after(BEL.find_then_pin(nodes[0])))


def _alive_gated(event):
    """event -> [pawn valid?] -> health cast -> [Dead or 0 HP?], both refusals
    failing the step without running anything."""
    first = _after(BEL.find_then_pin(event))
    if len(first) != 1 or _title(first[0]) != "Branch":
        return False
    cast = _after(BEL.find_then_pin(first[0]))
    if len(cast) != 1 or "Health" not in _title(cast[0]):
        return False
    gate = _after(BEL.find_then_pin(cast[0]))
    if len(gate) != 1 or _title(gate[0]) != "Branch":
        return False
    return ({"Get Dead", "Get Health"}
            <= {_title(f) for f in _sources(gate[0], "Condition")}
            and _fails(_after(BEL.find_then_pin(gate[0])))
            and _fails(_after(BEL.find_else_pin(first[0]))))


def check_controller_steps(ai_path):
    tag = ai_path.rsplit("/", 1)[-1]
    bp = _load(ai_path)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    runs = [n for n in nodes if "BTAsset" in _ins(n)]
    want = tree_path(ai_path).rsplit("/", 1)[-1]
    check(f"{tag}: possession runs {want}",
          len(runs) == 1 and _lit(runs[0], "BTAsset").endswith(f"{want}.{want}")
          and ["On Possess" in _title(d) for d in _drivers(runs[0])] == [True],
          f"{[_lit(n, 'BTAsset') for n in runs]}")
    check(f"{tag}: no Delay loop is left", not any(_title(n) == "Delay" for n in nodes))
    events = {_title(n).split(" ")[0]: n for n in nodes
              if n.get_class().get_name() == "K2Node_CustomEvent"}
    missing = [s for s in want_steps(ai_path)
               if f"{STEP_EVENT_PREFIX}{s}" not in events]
    check(f"{tag}: every step the tree names is an event here", not missing, f"{missing}")
    loose = sorted({f"{name}: {_title(leaf)}" for name, ev in events.items()
                    for leaf in _exits(ev)
                    if _title(leaf) != f"Set {STEP_RESULT_VAR}"})
    check(f"{tag}: every exit of every step writes {STEP_RESULT_VAR}", not loose,
          f"{loose[:4]}")
    pulse = f"{STEP_EVENT_PREFIX}{STEP_PULSE}"
    ungated = sorted(name for name, ev in events.items()
                     if name != pulse and not _alive_gated(ev))
    check(f"{tag}: every step but Pulse fails, doing nothing, for a pawn that is "
          f"gone, Dead or at 0 HP", not ungated and len(events) > 1, f"{ungated}")

    task = _load(step_task_path(ai_path))
    check(f"{tag}: its step task exists", task is not None)
    if not task:
        return
    ted = unreal.BlueprintGraphEditor.get_graph_editor_by_name(task, "EventGraph")
    check(f"{tag}: its step task compiles clean", not ted.list_nodes_with_errors())
    cdo = unreal.get_default_object(BEL.generated_class(task))
    check(f"{tag}: the task's {STEP_VAR} is a name",
          isinstance(cdo.get_editor_property(STEP_VAR), unreal.Name))


def run():
    check_blackboard()
    for path in [AI_BP_PATH] + [v.ai_blueprint for v in NPC_VARIANTS]:
        check_tree(path)
        check_controller_steps(path)
