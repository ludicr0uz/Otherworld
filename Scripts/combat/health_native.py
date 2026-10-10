"""BP_HealthComponent's native parent (task W3): the reparent onto
OtherworldHealthComponent (C++, Source/Otherworld; uebp/nodes/health.py has
its nodes), and what a component built before it must lose first.

The base holds Health and Dead (RepNotify), HitCount and LastHitFrom
(replicated), the blow's other stamps, TakeHit and Die
(combat/health_vars.NATIVE has the names). A Blueprint variable, event or
function graph named as one of them fails the compile once the parent has
it, so each goes before the reparent; the graphs that read and write them by
name then find the base's (the builders author them anew).
"""

import unreal

from combat import health_vars as HV
from combat.damage import DIE, TAKE_HIT
from combat.log import _log
from uebp.graph import BEL
from uebp.nodes.health import HEALTH_BASE_CLASS

# The base's functions: a custom event of the graph may not share a name.
NATIVE_FUNCTIONS = (TAKE_HIT, DIE)
# The function graph a Blueprint RepNotify Health had: the base's notify
# has the name now.
RETIRED_GRAPHS = ("OnRep_Health", "OnRep_Dead")


def base_class():
    cls = unreal.load_class(None, HEALTH_BASE_CLASS)
    if cls is None:
        raise RuntimeError(f"{HEALTH_BASE_CLASS} is not loaded: compile the Otherworld "
                           "module (Source/CLAUDE.md)")
    return cls


def is_native(bp):
    return BEL.get_blueprint_parent_class(bp) == base_class()


def reparent(bp, ed):
    """Make ``bp`` a child of the native base, keeping every variable the
    base does not hold itself. Before the graph is authored: the blow's and
    the death's nodes are the base's."""
    parent = base_class()
    if is_native(bp):
        return
    for name in NATIVE_FUNCTIONS:
        old = ed.find_event_node(name)
        if old:
            ed.remove_nodes([old])
    for name in RETIRED_GRAPHS:
        graph = BEL.find_graph(bp, name)
        if graph:
            BEL.remove_graph(bp, graph)
    before = {str(v) for v in BEL.list_member_variable_names(bp)}
    for var in HV.NATIVE:
        if str(var) in before:
            ed.remove_member_variable(str(var))
    BEL.reparent_blueprint(bp, parent)
    if BEL.get_blueprint_parent_class(bp) != parent:
        raise RuntimeError(f"{bp.get_name()} did not take {HEALTH_BASE_CLASS}")
    after = {str(v) for v in BEL.list_member_variable_names(bp)}
    native = {str(v) for v in HV.NATIVE}
    lost = before - native - after
    if lost or after & native:
        raise RuntimeError(f"{bp.get_name()} after the reparent: lost {sorted(lost)}, "
                           f"still its own {sorted(after & native)}")
    _log(f"BP_HealthComponent: reparented onto {parent.get_name()}")
