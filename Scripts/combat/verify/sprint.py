"""verify.sprint -- the sprint's latch (weapon_component/sprint.py): a sprint
that runs Stamina out stays off until the key is let go.

Without it, a held sprint at zero Stamina flipped Sprinting every frame (stop,
regen a sliver, start, drain it), and the aim, gated on NOT Sprinting, flipped
with it: the screen twitched with an aim key held. The speed, the drain and
the fire gate are checked in verify/weapon_inputs.py.

Its numbers (player_tuning.csv through COMBAT): the jog on the character, the
sprint's speed and the stamina's two rates as variables the graph reads.

And its direction (sprint_tuning.py): only while the player steers within 60
degrees of the way the character faces.
"""

from combat.player_tuning import (
    JOG_SPEED, SPRINT_DURATION, SPRINT_SPEED, STAMINA_RECHARGE, cms, table,
)
from combat.verify.fixtures import char, w, wg
from combat.verify.common import (
    BEL, PIN, cdo, check, has_in_pin, in_pins, num_pin, out_pins, pin_value,
)
from combat.sprint_tuning import (
    SPRINT_AHEAD_VAR, SPRINT_CONE_HALF_ANGLE_DEG, SPRINT_CONE_MIN_DOT,
    SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from combat.tuning import COMBAT
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


def _and_terms(nodes):
    """The inputs of a chain of ANDs, flattened: key AND fresh AND ahead is
    two nodes deep."""
    terms = []
    for f in (f for n in nodes for f in _feeders(n, "A", "B")):
        is_and = "AND" in _title(f).upper() and in_pins(f) >= {"A", "B"}
        terms += _and_terms([f]) if is_and else [f]
    return terms


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
    terms = _and_terms(gate)
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


def check_sprint_forward():
    value = w.get_editor_property(SPRINT_AHEAD_VAR)
    check(f"{SPRINT_AHEAD_VAR} starts False", value is False, repr(value))
    check(f"the sprint's cone is {SPRINT_CONE_HALF_ANGLE_DEG:.0f} deg either "
          f"side of forward (a dot of {SPRINT_CONE_MIN_DOT})",
          SPRINT_CONE_HALF_ANGLE_DEG == 60.0 and SPRINT_CONE_MIN_DOT == 0.5,
          f"{SPRINT_CONE_HALF_ANGLE_DEG}, {SPRINT_CONE_MIN_DOT}")
    stores = [n for n in wg if has_in_pin(n, SPRINT_AHEAD_VAR)]
    marks = [n for n in wg if has_in_pin(n, "Sprinting")]
    check(f"{SPRINT_AHEAD_VAR} is written once a frame",
          len(stores) == 1, f"{len(stores)} writes")
    if len(stores) != 1 or len(marks) != 1:
        return

    tests = _feeders(stores[0], SPRINT_AHEAD_VAR)
    dots = [f for n in tests for f in _feeders(n, "A")]
    check("...as a dot product no less than the cone's edge",
          len(tests) == 1 and ">=" in _title(tests[0])
          and num_pin(tests[0], "B") == SPRINT_CONE_MIN_DOT
          and len(dots) == 1 and "Dot" in _title(dots[0]),
          str([_title(n) for n in tests + dots]))
    sides = [f for n in dots for f in _feeders(n, "A", "B")]
    steers = [f for n in sides if "Normal" in _title(n)
              for f in _feeders(n, "A")]
    check("...of the way the player steers, normalised, with the way the "
          "character faces",
          any("LastMovementInput" in _title(n).replace(" ", "") for n in steers)
          and any("Forward" in _title(n) for n in sides),
          str([_title(n) for n in sides + steers]))
    check("Sprinting needs it: sideways and backwards the key does nothing",
          stores[0] in _and_terms(_feeders(marks[0], "Sprinting")),
          str([_title(n) for n in _and_terms(_feeders(marks[0], "Sprinting"))]))
    # The latch is the key's and the stamina's: turning away must not spend it.
    latches = [n for n in wg if has_in_pin(n, SPRINT_SPENT_VAR)]
    check("...and the latch does not read it, so turning back resumes",
          len(latches) == 1 and stores[0] not in _and_terms(
              _feeders(latches[0], SPRINT_SPENT_VAR)))


def check_sprint_rates():
    tuned = table()
    jog = cdo(char).get_editor_property("character_movement").get_editor_property(
        "max_walk_speed")
    check(f"the player jogs at player_tuning.csv's {tuned[JOG_SPEED]:g} m/s: the "
          f"character's own MaxWalkSpeed, which BeginPlay caches as BaseSpeed",
          abs(jog - cms(tuned[JOG_SPEED])) < 1e-3
          and abs(COMBAT.jog_speed_cms - jog) < 1e-3, f"{jog} cm/s")
    full = COMBAT.max_stamina
    for var, want, words in (
            (SPRINT_SPEED_VAR, cms(tuned[SPRINT_SPEED]),
             f"sprints at {tuned[SPRINT_SPEED]:g} m/s"),
            (STAMINA_DRAIN_VAR, full / tuned[SPRINT_DURATION],
             f"a full bar sprints for {tuned[SPRINT_DURATION]:g} s"),
            (STAMINA_REGEN_VAR, full / tuned[STAMINA_RECHARGE],
             f"an empty one refills in {tuned[STAMINA_RECHARGE]:g} s")):
        value = w.get_editor_property(var)
        check(f"...{words} ({var}, a float)",
              isinstance(value, float) and abs(value - want) < 1e-6, repr(value))
    # Variables, not literals: the PLAYER TUNING tab writes them in play.
    selects = [n for n in wg if in_pins(n) >= {"A", "B", "bPickA"}]
    speed = [n for n in selects
             if {_title(f) for f in _feeders(n, "A", "B")}
             == {f"Get {SPRINT_SPEED_VAR}", "Get BaseSpeed"}]
    check("the sprint picks SprintSpeed or BaseSpeed, both read off the component",
          len(speed) == 1, f"{len(speed)} of {len(selects)} selects")
    rate = [n for n in selects
            if f"Get {STAMINA_REGEN_VAR}" in {_title(f) for f in _feeders(n, "B")}
            and any(f"Get {STAMINA_DRAIN_VAR}" in {_title(g) for g in _feeders(f, "A")}
                    and num_pin(f, "B") == -1.0 for f in _feeders(n, "A"))]
    check("...and the stamina's rate is minus the drain or the regen, both variables",
          len(rate) == 1, f"{len(rate)} of {len(selects)} selects")


def run():
    check_sprint_latch()
    check_sprint_forward()
    check_sprint_rates()
