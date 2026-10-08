"""The guard at the head of every Server event (task A5): the one fragment
that asks the player's RPC guard (C++, UOtherworldRpcGuard; the numbers are
net/guard_consts.py's) whether the event may run.

A Blueprint RPC has no _Validate hook, so a Server event trusts whatever
arrives, as often as it arrives, unless its graph asks. Every Server event's
first node is author_guard's Allow, with the event's own name; the event's
body hangs off the arm it returns. In single player, and for a character the
server drives itself, the guard passes and counts nothing.

    author_allow(g, name, execs)       Allow(name): (the exec after it, its answer)
    author_guard(g, name, execs)       that and its Branch: (allowed, refused)
    author_aim_guard(g, aim, execs)    AimAllowed(aim): (allowed, refused)
"""

from uebp.graph import _connect, _pin, out, then
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNER
from uebp.nodes.guard import FN_GUARD_AIM_ALLOWED, FN_GUARD_ALLOW, GUARD_CLASS


def _guard(g):
    """The owner's guard component, as a pin."""
    comp = g.call(FN_GET_COMP, self=out(g.call(FN_GET_OWNER)))
    _pin(comp, "ComponentClass").set_pin_value(GUARD_CLASS)
    return out(comp)


def author_allow(g, name, execs):
    """``execs`` run Allow(name) on the owner's guard. Returns the exec pin
    after it and its answer, for an event that does something either way
    before it branches (the shot's AsksServed)."""
    asked = g.call(FN_GUARD_ALLOW, execs, Name=name)
    _connect(_guard(g), _pin(asked, "self"))
    return then(asked), out(asked)


def author_guard(g, name, execs):
    """``execs`` run Allow(name) on the owner's guard. Returns the exec pins
    (allowed, refused)."""
    flow, allowed = author_allow(g, name, execs)
    return g.branch(allowed, [flow])


def author_aim_guard(g, aim, execs):
    """``execs`` run AimAllowed(aim) on the owner's guard. Returns the exec
    pins (allowed, refused)."""
    asked = g.call(FN_GUARD_AIM_ALLOWED, execs, AimPoint=aim)
    _connect(_guard(g), _pin(asked, "self"))
    return g.branch(out(asked), [then(asked)])
