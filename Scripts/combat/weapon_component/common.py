"""Small graph fragments shared by the weapon component's modules: reading a
weapon property, trace defaults and the muzzle location.
"""

from uebp.graph import _connect, _node, _pin, _set, out
from combat.paths import ITEM_CLASS_PATH
from uebp.nodes.actor import FN_GET_TRANSFORM
from uebp.nodes.math import FN_TRANSFORM_LOC
from combat import item_vars as IV


# ─── BP_WeaponComponent ──────────────────────────────────────────────────────

AIM_LOOPS = 9999          # PlaySlotAnimation has no "loop forever"; 9999 x 8 s
                          # is about a day, which outlasts any play session.
AIM_BLEND = 0.25


def _prop(ed, name, self_pin, class_path=ITEM_CLASS_PATH):
    """Read a variable off another object: Get <name> with its self pin driven.

    A data output pin takes any number of links, so one Held getter can feed
    every one of these.
    """
    n = ed.add_get_member_variable_node(name, class_path)
    _connect(self_pin, _pin(n, "self"))
    return out(n, name), n


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


def _muzzle_location(ed, held):
    """World position of the held weapon's barrel tip, as a pure sub-graph.

    Pure, so it can be shared: the aim resolve and the pellet loop must agree on
    where the gun is, and the cheapest way to guarantee that is for them to read
    the same nodes rather than each build their own copy.
    """
    xform = _node(ed, FN_GET_TRANSFORM)
    _connect(held, _pin(xform, "self"))
    off_pin, _off = _prop(ed, IV.MuzzleOffset, held)
    at = _node(ed, FN_TRANSFORM_LOC)
    _connect(out(xform), _pin(at, "T"))
    _connect(off_pin, _pin(at, "Location"))
    return out(at)
