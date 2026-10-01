"""verify.sprint -- the sprint's latch (weapon_component/sprint.py): a sprint
that runs Stamina out stays off until the key is let go.

Without it, a held sprint at zero Stamina flipped Sprinting every frame (stop,
regen a sliver, start, drain it), and the aim, gated on NOT Sprinting, flipped
with it: the screen twitched with an aim key held. The speed, the drain and
the fire gate are checked in verify/weapon_inputs.py.
"""

from combat.verify.fixtures import w, wg
from combat.verify.common import (
    BEL, PIN, check, has_in_pin, in_pins, num_pin, out_pins, pin_value,
)
from combat.weapon_component.sprint import SPRINT_SPENT_VAR


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, *pins):
    return [PIN.get_owning_node(q)
            for pin in pins if has_in_pin(node, pin)
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))]


def _is_zero(node, pin):
    """An unconnected pin holding 0: a literal 0 reads back as an empty string
    once the Blueprint is loaded from disk, and as "0.0" in the editor that
    authored it."""
    return (not _feeders(node, pin)
            and (num_pin(node, pin) == 0.0 or pin_value(node, pin) == ""))


def _is_sprint_poll(node):
    return (in_pins(node) == {"self", "Key"}
            and "IsInputKeyDown" in _title(node)
            and any("Get KeySprint" in _title(f) for f in _feeders(node, "Key")))


def check_sprint_latch():
    value = w.get_editor_property(SPRINT_SPENT_VAR)
    check(f"{SPRINT_SPENT_VAR} starts False", value is False, repr(value))
    latches = [n for n in wg if has_in_pin(n, SPRINT_SPENT_VAR)]
    marks = [n for n in wg if has_in_pin(n, "Sprinting")]
    check("a spent sprint is latched by exactly one write, and Sprinting by one",
          len(latches) == 1 and len(marks) == 1,
          f"{len(latches)} and {len(marks)} writes")
    if len(latches) != 1 or len(marks) != 1:
        return

    held = _feeders(latches[0], SPRINT_SPENT_VAR)
    halves = [f for n in held for f in _feeders(n, "A", "B")]
    check("...the latch holds only while the sprint key does, so letting go "
          "clears it",
          len(held) == 1 and "AND" in _title(held[0]).upper()
          and any(_is_sprint_poll(n) for n in halves),
          str([_title(n) for n in held + halves]))
    kept = [f for n in halves if "OR" in _title(n).upper()
            for f in _feeders(n, "A", "B")]
    check("...and is set by Stamina running out, then keeps itself",
          any(SPRINT_SPENT_VAR in out_pins(n) for n in kept)
          and any(_is_zero(n, "B") and "<=" in _title(n)
                  and any("Stamina" in out_pins(f) for f in _feeders(n, "A"))
                  for n in kept),
          str([_title(n) for n in kept]))

    gate = _feeders(marks[0], "Sprinting")
    terms = [f for n in gate for f in _feeders(n, "A", "B")]
    check("Sprinting = key held AND NOT spent, read off the latch's own write",
          len(gate) == 1 and "AND" in _title(gate[0]).upper()
          and any(_is_sprint_poll(n) for n in terms)
          and any(f == latches[0] for n in terms if "NOT" in _title(n).upper()
                  for f in _feeders(n, "A")),
          str([_title(n) for n in gate + terms]))
    # A Stamina test straight on Sprinting is the flicker: only the latch
    # remembers that the sprint ran out.
    check("...with no Stamina test of its own to flip it frame by frame",
          not any("Stamina" in out_pins(f)
                  for n in terms for f in _feeders(n, "A", "B")),
          str([_title(n) for n in terms]))
    # The exec order is the point: this frame's Sprinting reads this frame's latch.
    after = [PIN.get_owning_node(q)
             for q in PIN.list_connected_pins(BEL.find_then_pin(latches[0]))]
    check("...and the latch is written first, on the same exec chain",
          after == [marks[0]], str([_title(n) for n in after]))


def run():
    check_sprint_latch()
