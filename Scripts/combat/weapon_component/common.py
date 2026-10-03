"""Small graph fragments shared by the weapon component's modules: reading a
weapon property, trace defaults, the muzzle location, and _G, the placed-and-
kept node shapes the newer fragments (wear.py, slot_*.py) are written in.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import FN_GET_TRANSFORM, FN_TRANSFORM_LOC
from combat.paths import ITEM_CLASS_PATH


# ─── BP_WeaponComponent ──────────────────────────────────────────────────────

AIM_LOOPS = 9999          # PlaySlotAnimation has no "loop forever"; 9999 x 8 s
                          # is about a day, which outlasts any play session.
AIM_BLEND = 0.25


def _prop(ed, name, self_pin, x, y, class_path=ITEM_CLASS_PATH):
    """Read a variable off another object: Get <name> with its self pin driven.

    A data output pin takes any number of links, so one Held getter can feed
    every one of these.
    """
    n = _at(ed.add_get_member_variable_node(name, class_path), x, y)
    _connect(self_pin, _pin(n, "self"))
    return _pin(n, name, is_input=False), n


def _trace_defaults(node):
    """The settings every trace in this file shares.

    No trace draws itself any more. DrawDebugType is an enum *literal* on the
    pin, and an enum pin cannot be driven by a variable, so a trace that draws
    only in debug mode is not expressible here at all -- the pellet tracer is a
    separate DrawDebugLine behind a Branch instead (see _author_fire).
    """
    _set(node, "TraceChannel", "TraceTypeQuery1")   # Visibility
    _set(node, "bTraceComplex", "false")
    # Ignores the pawn this component hangs off. The weapon actor is separate
    # and *not* ignored, but every one of its parts is NoCollision, so a pellet
    # cannot hit the gun it came out of.
    _set(node, "bIgnoreSelf", "true")
    _set(node, "DrawDebugType", "None")


def _muzzle_location(ed, held, x, y):
    """World position of the held weapon's barrel tip, as a pure sub-graph.

    Pure, so it can be shared: the aim resolve and the pellet loop must agree on
    where the gun is, and the cheapest way to guarantee that is for them to read
    the same nodes rather than each build their own copy.
    """
    xform = _at(_node(ed, FN_GET_TRANSFORM), x, y)
    _connect(held, _pin(xform, "self"))
    off_pin, _off = _prop(ed, "MuzzleOffset", held, x, y + 140)
    at = _at(_node(ed, FN_TRANSFORM_LOC), x + 260, y)
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(at, "T"))
    _connect(off_pin, _pin(at, "Location"))
    return _pin(at, "ReturnValue", is_input=False)


class _G:
    """The few node shapes this file is made of, each placed and kept."""

    def __init__(self, ed):
        self.ed, self.made = ed, []

    def keep(self, n, x, y):
        self.made.append(_at(n, x, y))
        return n

    def get(self, var, x, y):
        n = self.keep(self.ed.add_get_member_variable_node(var), x, y)
        return _pin(n, var, is_input=False)

    def put(self, var, value, execs, x, y):
        """Set ``var`` to a pin, or to a literal string. Returns its then pin."""
        n = self.keep(self.ed.add_set_member_variable_node(var), x, y)
        if isinstance(value, str):
            _set(n, var, value)
        elif value is not None:
            _connect(value, _pin(n, var))
        for e in execs:
            _connect(e, _pin(n, "execute"))
        return BEL.find_then_pin(n)

    def call(g, fn, x, y, execs=(), **inputs):
        n = g.keep(_node(g.ed, fn), x, y)
        for name, value in inputs.items():
            if isinstance(value, (str, int)):
                _set(n, name, value)
            else:
                _connect(value, _loose_pin(n, name))
        for e in execs:
            _connect(e, _pin(n, "execute"))
        return n

    def iget(self, item, var, x, y, class_path=ITEM_CLASS_PATH):
        """Read ``var`` off another object (an item, by default)."""
        n = self.keep(self.ed.add_get_member_variable_node(var, class_path), x, y)
        _connect(item, _pin(n, "self"))
        return _pin(n, var, is_input=False)

    def iput(self, item, var, value, execs, x, y, class_path=ITEM_CLASS_PATH):
        """Set ``var`` on another object to a pin or a literal string."""
        n = self.keep(self.ed.add_set_member_variable_node(var, class_path), x, y)
        _connect(item, _pin(n, "self"))
        if isinstance(value, str):
            _set(n, var, value)
        else:
            _connect(value, _pin(n, var))
        for e in execs:
            _connect(e, _pin(n, "execute"))
        return BEL.find_then_pin(n)

    def branch(self, cond, execs, x, y):
        br = self.keep(self.ed.add_branch_node(), x, y)
        _connect(cond, _pin(br, "Condition"))
        for e in execs:
            _connect(e, _pin(br, "execute"))
        return BEL.find_then_pin(br), BEL.find_else_pin(br)
