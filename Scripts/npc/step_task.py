"""BTT_<controller>_Step: the one task class a wanderer's behaviour tree uses.

Each node in the tree is an instance of it with its Step set (and its node
name, which is what the tree editor and debugger show). On execute it calls
that step's event on its controller, then finishes with the controller's
StepResult:

    ExecuteAI -> Cast OwnerController to <controller>
                   -> [Step == "Pulse"?] yes -> BT_Pulse -> FinishExecute(StepResult)
                      no -> [Step == "Chase"?] ...
                      none matched, or the cast failed -> FinishExecute(false)

One class per controller, because each controller is its own Blueprint (not a
child of a shared one) and a cast is the only typed way to reach its events.
"""

import unreal

from npc.graph import (
    BEL, BGE, _asset_sub, _at, _connect, _create_blueprint, _log,
    _name_literal, _node, _palette, _pin, _set,
)
from npc.nodes import FN_EQ_NAME, FN_FINISH_EXECUTE, NODE_EVENT_EXECUTE_AI
from npc.paths import STEP_EVENT_PREFIX, STEP_RESULT_VAR, STEP_VAR

PIN = unreal.BlueprintGraphPinLibrary


def _cast_out(cast):
    """The cast's typed output ("AsBP Forest Wanderer AI Zombie")."""
    for p in BEL.list_output_pins(cast):
        if str(PIN.get_pin_name(p)).startswith("As"):
            return p
    raise RuntimeError(f"no As<class> pin on {BEL.get_node_title(cast)}")


def _event_call(ed, class_path, event):
    """A call to one of the controller's custom events."""
    for sep in (":", "."):
        n = ed.add_call_function_node(f"{class_path}{sep}{event}")
        if n and BEL.list_all_pins(n):
            return n
        if n:
            ed.remove_nodes([n])
    raise RuntimeError(f"{class_path} has no event {event}")


def clear_step_task(path):
    """Empty an existing step task's graph and compile it, before its
    controller's events are wiped: otherwise the controller's compile
    recompiles this dependent against events that are gone, and logs an
    error per call node."""
    eas = _asset_sub()
    if not eas.does_asset_exist(path):
        return
    bp = eas.load_asset(path)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    ed.remove_nodes(ed.list_all_nodes())
    BEL.compile_blueprint(bp)


def build_step_task(ai_bp, path, steps):
    """Create or rebuild the step task for ``ai_bp``; returns its class.

    ``steps`` is every step name the tree may give a node.
    """
    bp = _create_blueprint(path, unreal.BTTask_BlueprintBase)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    ed.remove_nodes(ed.list_all_nodes())
    ed.remove_member_variable(STEP_VAR)
    if not ed.add_member_variable(STEP_VAR, BEL.get_basic_type_by_name("name")):
        raise RuntimeError(f"could not declare {STEP_VAR}")
    BEL.set_blueprint_variable_instance_editable(bp, STEP_VAR, True)

    ai_class = BEL.generated_class(ai_bp)
    class_path = ai_class.get_path_name()
    execute = _palette(ed, NODE_EVENT_EXECUTE_AI, 0.0, 0.0)
    cast = _at(_palette(ed, f"Utilities|Casting|CastTo{ai_bp.get_name()}"), 300, 0)
    _connect(_pin(execute, "OwnerController", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(execute), _pin(cast, "execute"))
    ctrl = _cast_out(cast)

    done = _at(_node(ed, FN_FINISH_EXECUTE), 1400, -300)
    result = _at(ed.add_get_member_variable_node(STEP_RESULT_VAR, class_path), 1100, -200)
    _connect(ctrl, _pin(result, "self"))
    _connect(_pin(result, STEP_RESULT_VAR, is_input=False), _pin(done, "bSuccess"))
    failed = _at(_node(ed, FN_FINISH_EXECUTE), 1400, 300 + 300 * len(steps))
    _set(failed, "bSuccess", "false")
    _connect(_pin(cast, "CastFailed", is_input=False), _pin(failed, "execute"))

    step = _at(ed.add_get_member_variable_node(STEP_VAR), 300, 300)
    step_out = _pin(step, STEP_VAR, is_input=False)
    prev = BEL.find_then_pin(cast)
    for i, name in enumerate(steps):
        y = 300 * i
        same = _at(_node(ed, FN_EQ_NAME), 500, y + 150)
        _connect(step_out, _pin(same, "A"))
        _connect(_name_literal(ed, name, 300, y + 250), _pin(same, "B"))
        which = _at(ed.add_branch_node(), 800, y)
        _connect(_pin(same, "ReturnValue", is_input=False), _pin(which, "Condition"))
        _connect(prev, _pin(which, "execute"))
        call = _at(_event_call(ed, class_path, f"{STEP_EVENT_PREFIX}{name}"), 1100, y)
        _connect(ctrl, _pin(call, "self"))
        _connect(BEL.find_then_pin(which), BEL.find_execute_pin(call))
        _connect(BEL.find_then_pin(call), _pin(done, "execute"))
        prev = BEL.find_else_pin(which)
    _connect(prev, _pin(failed, "execute"))

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{path} failed to compile")
    if ed.list_nodes_with_errors():
        raise RuntimeError(f"{path} has nodes with errors")
    _asset_sub().save_loaded_asset(bp)
    _log(f"built {path} ({len(steps)} steps)")
    return BEL.generated_class(bp)
