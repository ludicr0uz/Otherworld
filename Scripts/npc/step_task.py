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

from npc.graph import _log
from uebp.graph import (
    BEL, BGE, _assets, _connect, _create_blueprint, _name_literal, _node, _palette, _pin,
    _set, else_, out, then)
from uebp.layout import arrange
from npc.paths import STEP_EVENT_PREFIX, STEP_RESULT_VAR, STEP_VAR
from uebp.nodes.ai import FN_FINISH_EXECUTE
from uebp.nodes.math import FN_EQ_NAME
from uebp.nodes.palette import NODE_EVENT_EXECUTE_AI

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
    eas = _assets()
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
    execute = _palette(ed, NODE_EVENT_EXECUTE_AI)
    cast = _palette(ed, f"Utilities|Casting|CastTo{ai_bp.get_name()}")
    _connect(out(execute, "OwnerController"), _pin(cast, "Object"))
    _connect(then(execute), _pin(cast, "execute"))
    ctrl = _cast_out(cast)

    done = _node(ed, FN_FINISH_EXECUTE)
    result = ed.add_get_member_variable_node(STEP_RESULT_VAR, class_path)
    _connect(ctrl, _pin(result, "self"))
    _connect(out(result, STEP_RESULT_VAR), _pin(done, "bSuccess"))
    failed = _node(ed, FN_FINISH_EXECUTE)
    _set(failed, "bSuccess", False)
    _connect(out(cast, "CastFailed"), _pin(failed, "execute"))

    step = ed.add_get_member_variable_node(STEP_VAR)
    step_out = out(step, STEP_VAR)
    prev = then(cast)
    for name in steps:
        same = _node(ed, FN_EQ_NAME)
        _connect(step_out, _pin(same, "A"))
        _connect(_name_literal(ed, name), _pin(same, "B"))
        which = ed.add_branch_node()
        _connect(out(same), _pin(which, "Condition"))
        _connect(prev, _pin(which, "execute"))
        call = _event_call(ed, class_path, f"{STEP_EVENT_PREFIX}{name}")
        _connect(ctrl, _pin(call, "self"))
        _connect(then(which), BEL.find_execute_pin(call))
        _connect(then(call), _pin(done, "execute"))
        prev = else_(which)
    _connect(prev, _pin(failed, "execute"))

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{path} failed to compile")
    if ed.list_nodes_with_errors():
        raise RuntimeError(f"{path} has nodes with errors")
    _assets().save_loaded_asset(bp)
    _log(f"built {path} ({len(steps)} steps)")
    return BEL.generated_class(bp)
