"""Networked Blueprints: RPC custom events, replicated variables, and actors
and components that replicate.

A custom event's net flags (``K2Node_Event.FunctionFlags``) and a variable's
replication (its property flags and OnRep function) are not reachable from
Python, so these go through ``UOtherworldBlueprintNetLibrary``, the
editor-only C++ module in ``Source/OtherworldEditor``. Each setter here reads
its write back and raises: a flag that silently did not land is an RPC that
runs on the wrong machine. CLAUDE.md beside this file is the guide.

Single player is the standalone net mode of the same graph: there a Server
or Multicast event simply runs locally, so nothing here needs a second,
offline copy of a Blueprint.
"""

import unreal

from uebp.graph import BEL, BGE, _component_object, _find_handle

# How an event replicates: the names of EOtherworldRpc's entries.
LOCAL, MULTICAST, SERVER, CLIENT = "NOT_REPLICATED", "MULTICAST", "SERVER", "CLIENT"
# How a variable replicates: the names of EOtherworldVarReplication's entries.
NONE, REPLICATED, REP_NOTIFY = "NONE", "REPLICATED", "REP_NOTIFY"


def _lib():
    lib = getattr(unreal, "OtherworldBlueprintNetLibrary", None)
    if lib is None:
        raise RuntimeError("the OtherworldEditor module is not loaded: compile the editor "
                           "target (Source/CLAUDE.md) and restart the editor")
    return lib


def _name(value):
    """An enum value as the name of its entry (``"SERVER"``)."""
    return value.name if hasattr(value, "name") else str(value).rsplit(".", 1)[-1]


# ─── RPCs: custom events ─────────────────────────────────────────────────────

def custom_event(ed, name, params=()):
    """A custom event in an event graph. ``params``: ``(name, pin type)``
    pairs, the pin type a ``uebp.vars`` spec (``FLOAT``) or a resolved one.
    Each becomes an output pin of the event, read with ``out(event, name)``.
    """
    node = ed.add_custom_event_node(name)
    if not node:
        raise RuntimeError(f"could not add the custom event {name!r} (not an event graph?)")
    if ed.find_event_node(name) != node:
        # An invalid or taken name is not an error to the engine: it keeps a
        # generated one (CustomEvent_0), and a call by name then finds nothing.
        raise RuntimeError(f"the custom event did not take the name {name!r}: "
                           "it is taken or not valid")
    for param, pin_type in params:
        resolved = pin_type() if callable(pin_type) else pin_type
        if not _lib().add_custom_event_parameter(node, param, resolved):
            raise RuntimeError(f"could not add the parameter {param!r} to {name}")
    return node


def set_rpc(event, kind, reliable):
    """Make a custom event run on the server, the owning client or everyone."""
    lib = _lib()
    if not lib.set_custom_event_rpc(event, getattr(unreal.OtherworldRpc, kind), reliable):
        raise RuntimeError(f"{event.get_name()} is not a custom event of this Blueprint")
    got = event_rpc(event)
    if got != (kind, reliable and kind != LOCAL):
        raise RuntimeError(f"net flags did not stick: {got!r}, wanted {(kind, reliable)!r}")
    return event


def server_event(ed, name, params=(), reliable=True):
    """An event the owning client calls and the server runs (Run on Server)."""
    return set_rpc(custom_event(ed, name, params), SERVER, reliable)


def client_event(ed, name, params=(), reliable=True):
    """An event the server calls and the owning client runs (Run on Owning Client)."""
    return set_rpc(custom_event(ed, name, params), CLIENT, reliable)


def multicast_event(ed, name, params=(), reliable=False):
    """An event the server calls and every machine runs. Unreliable unless
    asked: a multicast is mostly cosmetic (a sound, an effect) and a reliable
    one that is called often fills the channel."""
    return set_rpc(custom_event(ed, name, params), MULTICAST, reliable)


def event_rpc(event):
    """``(kind, reliable)`` as written on a custom event node."""
    found = _lib().get_custom_event_rpc(event)
    if not found:
        raise RuntimeError(f"{event.get_name()} is not a custom event")
    kind, reliable = found
    return _name(kind), bool(reliable)


def compiled_rpc(bp, name):
    """``(kind, reliable)`` of a function on the Blueprint's compiled class."""
    found = _lib().get_compiled_function_rpc(BEL.generated_class(bp), name)
    if not found:
        raise RuntimeError(f"{bp.get_name()} compiled no function {name!r}")
    kind, reliable = found
    return _name(kind), bool(reliable)


# ─── Replicated variables ────────────────────────────────────────────────────

def _set_replication(bp, var, kind, condition):
    lib = _lib()
    condition = condition or unreal.LifetimeCondition.COND_NONE
    if not lib.set_variable_replication(bp, var, getattr(unreal.OtherworldVarReplication, kind),
                                        condition):
        raise RuntimeError(f"{bp.get_name()} declares no variable {var!r}")
    want = (kind, f"OnRep_{var}" if kind == REP_NOTIFY else "None", _name(condition))
    got = variable_replication(bp, var)
    if got != want:
        raise RuntimeError(f"replication of {var} did not stick: {got!r}, wanted {want!r}")


def replicate(bp, var, condition=None):
    """Mark a member variable Replicated. ``condition``: an
    ``unreal.LifetimeCondition`` (``COND_OWNER_ONLY``), none by default.
    Declare the variable first: re-declaring one drops its replication."""
    _set_replication(bp, var, REPLICATED, condition)


def rep_notify(bp, var, condition=None):
    """Mark a member variable RepNotify and return the graph editor of its
    ``OnRep_<var>`` function, created empty if the Blueprint has none. The
    engine calls it on a client when the value arrives; in Blueprint a set on
    the server (and so in single player) calls it there too."""
    _set_replication(bp, var, REP_NOTIFY, condition)
    ed = BGE.get_graph_editor_by_name(bp, f"OnRep_{var}")
    if not ed:
        raise RuntimeError(f"{bp.get_name()} has no OnRep_{var} graph")
    return ed


def unreplicate(bp, var):
    """Stop replicating a member variable. Its OnRep graph, if any, stays."""
    _set_replication(bp, var, NONE, None)


def variable_replication(bp, var):
    """``(kind, OnRep function name, condition)`` as declared on the Blueprint."""
    found = _lib().get_variable_replication(bp, var)
    if not found:
        raise RuntimeError(f"{bp.get_name()} declares no variable {var!r}")
    kind, on_rep, condition = found
    return _name(kind), str(on_rep), _name(condition)


def compiled_replication(bp, var):
    """``(kind, OnRep function name)`` of a property on the compiled class."""
    found = _lib().get_compiled_property_replication(BEL.generated_class(bp), var)
    if not found:
        raise RuntimeError(f"{bp.get_name()} compiled no property {var!r}")
    kind, on_rep = found
    return _name(kind), str(on_rep)


# ─── Actors and components that replicate ────────────────────────────────────

def _write_replicates(target, on, what):
    target.set_editor_property("replicates", on)
    if bool(target.get_editor_property("replicates")) != on:
        raise RuntimeError(f"replicates did not stick on {what}")


def replicate_actor(bp, on=True):
    """Make an actor Blueprint replicate (its class default; nothing is
    compiled or saved here). Without it the actor exists only on the machine
    that spawned it, and none of its RPCs or variables cross the network."""
    _write_replicates(unreal.get_default_object(BEL.generated_class(bp)), on, bp.get_name())


def replicate_component(bp, component=None, on=True):
    """Make a component replicate: the one named ``component`` among an actor
    Blueprint's own components, or, with no name, a component Blueprint's
    class default. Its owner must replicate too."""
    if component is None:
        target = unreal.get_default_object(BEL.generated_class(bp))
    else:
        handle = _find_handle(bp, component)
        if not handle:
            raise RuntimeError(f"{bp.get_name()} has no component {component!r}")
        target = _component_object(handle)
    _write_replicates(target, on, f"{bp.get_name()}.{component or 'self'}")


def replicates(bp, component=None):
    """Whether the actor Blueprint, or the component, replicates by default."""
    if component is None:
        return bool(unreal.get_default_object(BEL.generated_class(bp))
                    .get_editor_property("replicates"))
    return bool(_component_object(_find_handle(bp, component)).get_editor_property("replicates"))
