"""Debug mode's pellet tracer: the line a pellet flew, drawn in the world.

    [DebugMode?] --> DrawDebugLine(TraceStart -> where it stopped)
                 --> DrawDebugPoint(where it stopped)

Both ends are read off the pellet trace's own hit result, never off the nodes
that fed the trace. The trace's End is a chain of pure nodes with a random
cone in it, and a pure node re-evaluates for every reader: a tracer wired to
that End drew a second, different pellet -- the shotgun's lines were not the
lines its pellets took. The hit result is the output of a node that ran, so
it is the same answer however often it is read.

A pellet that connected stops at the impact and is drawn in the hit colour;
one that did not runs to the end of the weapon's range in the miss colour.
"""

from combat.game_state import (
    DEBUG_MODE_VAR, TRACE_DEBUG_SECONDS, TRACER_HIT_COLOR, TRACER_MISS_COLOR,
    TRACER_POINT_SIZE, TRACER_THICKNESS,
)
from combat.graph import BEL, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import (
    FN_DRAW_LINE, FN_DRAW_POINT, FN_SELECT_COLOR, FN_SELECT_VECTOR,
)


def _author_tracer(ed, trace, brk):
    """Draw the pellet ``trace`` just made, if debug mode is on.

    ``brk`` is the Break of its hit result. Returns ``(nodes, exec tails)``;
    the tails carry on whether or not anything was drawn.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    seen = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR))
    showing = keep(ed.add_branch_node())
    _connect(_pin(seen, DEBUG_MODE_VAR, is_input=False), _pin(showing, "Condition"))
    _connect(BEL.find_then_pin(trace), _pin(showing, "execute"))
    connected = _pin(trace, "ReturnValue", is_input=False)

    stop = keep(_node(ed, FN_SELECT_VECTOR))
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(stop, "A"))
    _connect(_loose_pin(brk, "TraceEnd", is_input=False), _pin(stop, "B"))
    _connect(connected, _pin(stop, "bPickA"))
    colour = keep(_node(ed, FN_SELECT_COLOR))
    _set(colour, "A", TRACER_HIT_COLOR)
    _set(colour, "B", TRACER_MISS_COLOR)
    _connect(connected, _pin(colour, "bPickA"))

    line = keep(_node(ed, FN_DRAW_LINE))
    _connect(_loose_pin(brk, "TraceStart", is_input=False), _pin(line, "LineStart"))
    _connect(_pin(stop, "ReturnValue", is_input=False), _pin(line, "LineEnd"))
    _connect(_pin(colour, "ReturnValue", is_input=False), _pin(line, "LineColor"))
    _set(line, "Duration", TRACE_DEBUG_SECONDS)
    _set(line, "Thickness", TRACER_THICKNESS)
    _connect(BEL.find_then_pin(showing), _pin(line, "execute"))

    point = keep(_node(ed, FN_DRAW_POINT))
    _connect(_pin(stop, "ReturnValue", is_input=False), _pin(point, "Position"))
    _connect(_pin(colour, "ReturnValue", is_input=False), _pin(point, "PointColor"))
    _set(point, "Size", TRACER_POINT_SIZE)
    _set(point, "Duration", TRACE_DEBUG_SECONDS)
    _connect(BEL.find_then_pin(line), _pin(point, "execute"))

    return made, [BEL.find_then_pin(point), BEL.find_else_pin(showing)]
