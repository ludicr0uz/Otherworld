"""verify.interact -- the interact key (weapon_component/interact.py): one
press keeps one target, the candidate in reach nearest AimPoint. A walk only
remembers the best candidate; nothing is done to one inside it.

What is done to the target after the search is its kind's: an item is picked
up (verify/pickup.py), a campfire heats the blade in hand (verify/heat.py).
"""

from combat.tuning import BIND_VARS, INTERACT_KEY, INTERACT_RADIUS
from combat.verify.common import BEL, PIN, by_pins, check, num_pin, pin_value
from combat.verify.fixtures import w, wg
from combat.weapon_component.interact import (
    INTERACT_FORCED_VAR, INTERACT_GAP_VAR, INTERACT_NO_GAP, INTERACT_TARGET_VAR,
    KINDS, RETIRED_VARS,
)


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _sources(node, pin):
    """The nodes wired into one of ``node``'s input pins."""
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))]


def _reads(node, pin, var):
    return any(_title(n) == f"Get {var}" for n in _sources(node, pin))


def _exec_from(node):
    """(node, pin name) of every exec output wired into ``node``."""
    return [(PIN.get_owning_node(q), str(PIN.get_pin_name(q)))
            for q in PIN.list_connected_pins(BEL.find_execute_pin(node))]


def _then(node):
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_then_pin(node))]


def _aim_gaps():
    """Vector_Distance nodes measuring something against AimPoint."""
    return [n for n in by_pins(wg, "V1", "V2")
            if _reads(n, "V1", "AimPoint") or _reads(n, "V2", "AimPoint")]


def _has(obj, name):
    try:
        obj.get_editor_property(name)
    except Exception:
        return False
    return True


def check_interact_state():
    check(f"the interact key is a bind of its own, {INTERACT_KEY} by default",
          ("KeyInteract", INTERACT_KEY) in BIND_VARS, str(BIND_VARS))
    left = [v for v in RETIRED_VARS if _has(w, v)]
    check("nothing is left of the key's names as the pick-up key",
          not left, ", ".join(left))

    gap = w.get_editor_property(INTERACT_GAP_VAR)
    check("interact starts idle: no target kept, no probe pressing the key, "
          "and a gap no candidate can exceed",
          w.get_editor_property(INTERACT_TARGET_VAR) is None
          and w.get_editor_property(INTERACT_FORCED_VAR) is False
          and isinstance(gap, float) and abs(gap - INTERACT_NO_GAP) < 1.0,
          f"{INTERACT_GAP_VAR}={gap!r}")

    presses = [n for n in wg if _title(n) == f"Set {INTERACT_FORCED_VAR}"]
    check(f"a press spends {INTERACT_FORCED_VAR}, so a probe's press is one press",
          len(presses) == 1 and pin_value(presses[0], INTERACT_FORCED_VAR) == "false"
          and [pin for _n, pin in _exec_from(presses[0])] == ["then"],
          f"{len(presses)} write(s)")


def check_interact_keeps_one():
    reach = [n for n in by_pins(wg, "A", "B")
             if num_pin(n, "B") == INTERACT_RADIUS
             and any({"V1", "V2"} <= {str(PIN.get_pin_name(p))
                                      for p in BEL.list_input_pins(s)}
                     for s in _sources(n, "A"))]
    # One offer per kind of thing the key acts on (interact.KINDS).
    kinds = len(KINDS)
    check(f"a candidate of each of the {kinds} kinds lies within "
          f"{INTERACT_RADIUS:.0f} cm of the player",
          len(reach) == kinds, f"{len(reach)} reach test(s)")

    gaps = _aim_gaps()
    ranks = [n for n in by_pins(wg, "A", "B")
             if _reads(n, "B", INTERACT_GAP_VAR)
             and any(s in gaps for s in _sources(n, "A"))]
    check("candidates are ranked by their distance to AimPoint, the reticle's "
          f"point: nearer than {INTERACT_GAP_VAR} wins",
          len(ranks) == kinds, f"{len(ranks)} comparison(s), {len(gaps)} gap(s)")

    keeps = [n for n in wg if _title(n) == f"Set {INTERACT_TARGET_VAR}"]
    kept = [n for n in keeps if _sources(n, INTERACT_TARGET_VAR)]
    forgot = [n for n in keeps if not _sources(n, INTERACT_TARGET_VAR)]
    check("each press forgets the last target before it searches, and each "
          "kind's walk keeps in one place",
          len(forgot) == 1 and len(kept) == kinds,
          f"{len(forgot)} clear(s), {len(kept)} keep(s)")

    for keep in kept:
        after = _then(keep)
        check("a walk only remembers the nearest: it writes the candidate and "
              "its gap and stops there",
              len(after) == 1 and _title(after[0]) == f"Set {INTERACT_GAP_VAR}"
              and any(s in gaps for s in _sources(after[0], INTERACT_GAP_VAR))
              and not _then(after[0]),
              ", ".join(_title(n) for n in after))


def run():
    check_interact_state()
    check_interact_keeps_one()
