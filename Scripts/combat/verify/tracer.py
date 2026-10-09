"""verify.tracer -- debug mode's pellet tracer (weapon_component/tracer.py).

What it guards: the line is the one the pellet flew. The trace's End is fed by
a pure random cone, so a tracer wired to it draws a second, different pellet;
the tracer has to read the trace's own hit result instead.
"""

from combat.game_state import (
    DEBUG_MODE_VAR, TRACE_DEBUG_SECONDS, TRACER_HIT_COLOR, TRACER_MISS_COLOR,
    TRACER_POINT_SIZE, TRACER_THICKNESS,
)
from combat.shot_vars import PELLET_FLEW
from combat.verify.anchor import event
from combat.verify.fixtures import wg
from combat.verify.common import BEL, PIN, by_pins, check, num_pin, pin_value


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _wired(node, pin_name):
    """The nodes wired straight into one input pin."""
    pin = BEL.find_input_pin(node, pin_name)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)] if pin else []


def _in_names(node):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(node)}


def _upstream(node):
    """The nodes re-evaluated when ``node`` reads its inputs: its pure
    dependencies, however far back, and the executed nodes they end at. A
    node with an exec pin ran once and holds its outputs, so the walk stops
    there."""
    seen, todo = {}, [node]
    while todo:
        n = todo.pop()
        if n is not node and "execute" in _in_names(n):
            continue
        for pin in BEL.list_input_pins(n):
            if str(PIN.get_pin_name(pin)) == "execute":
                continue
            for q in PIN.list_connected_pins(pin):
                src = PIN.get_owning_node(q)
                if src.get_path_name() not in seen:
                    seen[src.get_path_name()] = src
                    todo.append(src)
    return list(seen.values())


def _from_pellet(node, pin_name):
    """The PelletFlew parameters wired into one input pin ("?" for a link
    from anything else)."""
    flew = event(PELLET_FLEW)
    return [str(PIN.get_pin_name(q)) if PIN.get_owning_node(q) == flew else "?"
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin_name))]


def check_tracer():
    lines = by_pins(wg, "LineStart", "LineEnd")
    points = by_pins(wg, "Position", "PointColor")
    check("one tracer line and one point where the pellet stopped",
          len(lines) == 1 and len(points) == 1,
          f"{len(lines)} line(s), {len(points)} point(s)")
    if len(lines) != 1 or len(points) != 1:
        return
    line, point = lines[0], points[0]

    random = [_title(n) for n in _upstream(line) + _upstream(point)
              if "Random" in _title(n)]
    check("nothing the tracer reads is drawn at random -- a pure cone read "
          "again is a different pellet", not random, str(sorted(set(random))))
    # Both ends are PelletFlew's own parameters: the pellet is flown in C++
    # (FirePellets), which tells where it started and where it stopped.
    check("the line starts where the pellet did (PelletFlew's Start)",
          _from_pellet(line, "LineStart") == ["Start"], str(_from_pellet(line, "LineStart")))
    check("...and ends at the impact, or at the trace's end on a miss (its Stop)",
          _from_pellet(line, "LineEnd") == ["Stop"], str(_from_pellet(line, "LineEnd")))
    check("...the point sits on that same end",
          _from_pellet(point, "Position") == ["Stop"])

    tints = _wired(line, "LineColor")
    check("a pellet that connected is drawn in the hit colour, a miss in the other",
          len(tints) == 1 and pin_value(tints[0], "A") == TRACER_HIT_COLOR
          and pin_value(tints[0], "B") == TRACER_MISS_COLOR
          and _from_pellet(tints[0], "bPickA") == ["bStopped"]
          and [n.get_path_name() for n in _wired(point, "PointColor")]
          == [tints[0].get_path_name()],
          str([pin_value(t, "A") for t in tints]))
    check(f"the line is {TRACER_THICKNESS:g} thick, the point {TRACER_POINT_SIZE:g}, "
          f"both for {TRACE_DEBUG_SECONDS:g} s",
          num_pin(line, "Thickness") == TRACER_THICKNESS
          and num_pin(point, "Size") == TRACER_POINT_SIZE
          and num_pin(line, "Duration") == TRACE_DEBUG_SECONDS
          and num_pin(point, "Duration") == TRACE_DEBUG_SECONDS,
          f"{pin_value(line, 'Thickness')}, {pin_value(point, 'Size')}, "
          f"{pin_value(line, 'Duration')}, {pin_value(point, 'Duration')}")

    gates = _wired(line, "execute")
    check(f"both are drawn only behind the cached {DEBUG_MODE_VAR}",
          len(gates) == 1 and _title(gates[0]) == "Branch"
          and [_title(n) for n in _wired(gates[0], "Condition")]
          == [f"Get {DEBUG_MODE_VAR}"]
          and [str(PIN.get_pin_name(q)) for q in
               PIN.list_connected_pins(BEL.find_input_pin(line, "execute"))] == ["then"]
          and [n.get_path_name() for n in _wired(point, "execute")]
          == [line.get_path_name()],
          str([_title(n) for n in gates]))


def run():
    check_tracer()
