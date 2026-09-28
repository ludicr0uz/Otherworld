"""Small graph fragments shared by the weapon component's modules: reading a
weapon property, trace defaults, the muzzle location.
"""

from combat.graph import _at, _connect, _node, _pin, _set
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
