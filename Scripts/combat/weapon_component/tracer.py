"""Debug mode's pellet tracer: the line a pellet flew, drawn in the world.

    [DebugMode?] --> DrawDebugLine(TraceStart -> where it stopped)
                 --> DrawDebugPoint(where it stopped)

Both ends are the PelletFlew event's own parameters (the pellet is flown in
C++: OtherworldWeaponComponentBase), so the line drawn is the line the pellet
took. It used to be drawn off the trace node's hit result for the same reason:
the trace's End was a chain of pure nodes with a random cone in it, and a
tracer wired to that End drew a second, different pellet.

A pellet that connected stops at the impact and is drawn in the hit colour;
one that did not runs to the end of the weapon's range in the miss colour.
"""

from combat.game_state import (
    DEBUG_MODE_VAR, TRACE_DEBUG_SECONDS, TRACER_HIT_COLOR, TRACER_MISS_COLOR,
    TRACER_POINT_SIZE, TRACER_THICKNESS,
)
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from uebp.nodes.math import FN_SELECT_COLOR
from uebp.nodes.system import FN_DRAW_LINE, FN_DRAW_POINT


def _author_tracer(ed, flew):
    """Draw the pellet ``flew`` (the PelletFlew event node) tells of, if
    debug mode is on. Returns ``(nodes, exec tails)``; the tails carry on
    whether or not anything was drawn.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    seen = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR))
    showing = keep(ed.add_branch_node())
    _connect(out(seen, DEBUG_MODE_VAR), _pin(showing, "Condition"))
    _connect(then(flew), _pin(showing, "execute"))

    stop = out(flew, "Stop")
    colour = keep(_node(ed, FN_SELECT_COLOR))
    _set(colour, "A", TRACER_HIT_COLOR)
    _set(colour, "B", TRACER_MISS_COLOR)
    _connect(out(flew, "bStopped"), _pin(colour, "bPickA"))

    line = keep(_node(ed, FN_DRAW_LINE))
    _connect(out(flew, "Start"), _pin(line, "LineStart"))
    _connect(stop, _pin(line, "LineEnd"))
    _connect(out(colour), _pin(line, "LineColor"))
    _set(line, "Duration", TRACE_DEBUG_SECONDS)
    _set(line, "Thickness", TRACER_THICKNESS)
    _connect(then(showing), _pin(line, "execute"))

    point = keep(_node(ed, FN_DRAW_POINT))
    _connect(stop, _pin(point, "Position"))
    _connect(out(colour), _pin(point, "PointColor"))
    _set(point, "Size", TRACER_POINT_SIZE)
    _set(point, "Duration", TRACE_DEBUG_SECONDS)
    _connect(then(line), _pin(point, "execute"))
    return made, [then(point), else_(showing)]
