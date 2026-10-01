"""verify.pickup -- the pick-up (weapon_component/pickup.py): one press takes
one item, the candidate in reach nearest AimPoint. The loop only remembers the
best candidate; the take runs once, off the loop's Completed.

That a pick-up joins the inventory without switching to it is
verify/weapon_inputs.py's.
"""

from combat.tuning import INVENTORY_SIZE, PICKUP_RADIUS
from combat.verify.common import BEL, PIN, by_pins, check, num_pin, pin_value
from combat.verify.fixtures import w, wg
from combat.weapon_component.pickup import (
    PICKUP_FORCED_VAR, PICK_BEST_VAR, PICK_GAP_VAR, PICK_NO_GAP,
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


def check_pickup_state():
    gap = w.get_editor_property(PICK_GAP_VAR)
    check("the pick-up starts idle: no candidate kept, no probe pressing the "
          "key, and a gap no candidate can exceed",
          w.get_editor_property(PICK_BEST_VAR) is None
          and w.get_editor_property(PICKUP_FORCED_VAR) is False
          and isinstance(gap, float) and abs(gap - PICK_NO_GAP) < 1.0,
          f"{PICK_GAP_VAR}={gap!r}")

    presses = [n for n in wg if _title(n) == f"Set {PICKUP_FORCED_VAR}"]
    check(f"a press spends {PICKUP_FORCED_VAR}, so a probe's press is one press",
          len(presses) == 1 and pin_value(presses[0], PICKUP_FORCED_VAR) == "false"
          and [pin for _n, pin in _exec_from(presses[0])] == ["then"],
          f"{len(presses)} write(s)")


def check_pickup_picks_one():
    reach = [n for n in by_pins(wg, "A", "B")
             if num_pin(n, "B") == PICKUP_RADIUS
             and any({"V1", "V2"} <= {str(PIN.get_pin_name(p))
                                      for p in BEL.list_input_pins(s)}
                     for s in _sources(n, "A"))]
    check(f"a candidate lies within {PICKUP_RADIUS:.0f} cm of the player",
          len(reach) == 1, f"{len(reach)} reach test(s)")

    gaps = _aim_gaps()
    ranks = [n for n in by_pins(wg, "A", "B")
             if _reads(n, "B", PICK_GAP_VAR)
             and any(s in gaps for s in _sources(n, "A"))]
    check("candidates are ranked by their distance to AimPoint, the reticle's "
          f"point: nearer than {PICK_GAP_VAR} wins",
          len(ranks) == 1, f"{len(ranks)} comparison(s), {len(gaps)} gap(s)")

    keeps = [n for n in wg if _title(n) == f"Set {PICK_BEST_VAR}"]
    kept = [n for n in keeps if _sources(n, PICK_BEST_VAR)]
    forgot = [n for n in keeps if not _sources(n, PICK_BEST_VAR)]
    check("each press forgets the last candidate before it searches",
          len(forgot) == 1 and len(kept) == 1,
          f"{len(forgot)} clear(s), {len(kept)} keep(s)")
    if len(kept) != 1:
        return

    after = _then(kept[0])
    check("the loop only remembers the nearest: it writes the candidate and "
          "its gap and stops there",
          len(after) == 1 and _title(after[0]) == f"Set {PICK_GAP_VAR}"
          and any(s in gaps for s in _sources(after[0], PICK_GAP_VAR))
          and not _then(after[0]),
          ", ".join(_title(n) for n in after))


def check_pickup_takes_once():
    adds = by_pins(wg, "TargetArray", "NewItem")
    takes = [a for a in adds if _reads(a, "NewItem", PICK_BEST_VAR)]
    looped = [a for a in adds
              if any("Cast" in _title(s) for s in _sources(a, "NewItem"))]
    check(f"the take adds {PICK_BEST_VAR} to the inventory, and nothing adds "
          "a loop's own element",
          len(takes) == 1 and not looped,
          f"{len(takes)} take(s), {len(looped)} add(s) inside a loop")
    if len(takes) != 1:
        return

    # Backwards from the add: Set Dropped <- Branch(room) <- Branch(found)
    # <- the loop's Completed.
    flags = [n for n, _pin in _exec_from(takes[0])]
    check("the taken item stops being Dropped",
          len(flags) == 1 and _title(flags[0]) == "Set Dropped"
          and pin_value(flags[0], "Dropped") == "false"
          and _reads(flags[0], "self", PICK_BEST_VAR),
          ", ".join(_title(n) for n in flags))
    if len(flags) != 1:
        return
    rooms = _exec_from(flags[0])
    fits = [c for n, _pin in rooms for c in _sources(n, "Condition")]
    check(f"...only while fewer than {INVENTORY_SIZE} are carried",
          len(rooms) == 1 and rooms[0][1] == "then" and len(fits) == 1
          and num_pin(fits[0], "B") == float(INVENTORY_SIZE),
          f"{len(rooms)} gate(s)")
    if len(rooms) != 1:
        return
    founds = _exec_from(rooms[0][0])
    valid = [c for n, _pin in founds for c in _sources(n, "Condition")]
    check(f"...and only when a candidate was kept ({PICK_BEST_VAR} is valid)",
          len(founds) == 1 and founds[0][1] == "then" and len(valid) == 1
          and _reads(valid[0], "Object", PICK_BEST_VAR),
          f"{len(founds)} gate(s)")
    if len(founds) != 1:
        return
    entries = _exec_from(founds[0][0])
    check("the take runs once per press: off the loop's Completed, not its body",
          [pin for _n, pin in entries] == ["Completed"],
          str([pin for _n, pin in entries]))


def run():
    check_pickup_state()
    check_pickup_picks_one()
    check_pickup_takes_once()
