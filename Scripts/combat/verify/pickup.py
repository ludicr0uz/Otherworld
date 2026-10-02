"""verify.pickup -- the pick-up (weapon_component/pickup.py), interact's item
kind: the target interact kept, cast to an item, is taken into the bag once,
after the search, while there is room.

How the target is chosen is verify/interact.py's. That a pick-up joins the
inventory without switching to it is verify/weapon_inputs.py's.
"""

from combat.tuning import INVENTORY_SIZE
from combat.verify.common import by_pins, check, num_pin, pin_value
from combat.verify.fixtures import wg
from combat.verify.interact import _exec_from, _reads, _sources, _title
from combat.weapon_component.interact import INTERACT_TARGET_VAR


def _target_as_item(node, pin):
    """Is ``pin`` fed by a cast of InteractTarget, not of a loop's element?"""
    casts = [s for s in _sources(node, pin) if "Cast" in _title(s)]
    return len(casts) == 1 and _reads(casts[0], "Object", INTERACT_TARGET_VAR)


def check_pickup_takes_once():
    adds = by_pins(wg, "TargetArray", "NewItem")
    takes = [a for a in adds if _target_as_item(a, "NewItem")]
    looped = [a for a in adds if a not in takes
              and any("Cast" in _title(s) for s in _sources(a, "NewItem"))]
    check(f"the take adds {INTERACT_TARGET_VAR}, cast to an item, to the "
          "inventory, and nothing adds a loop's own element",
          len(takes) == 1 and not looped,
          f"{len(takes)} take(s), {len(looped)} add(s) inside a loop")
    if len(takes) != 1:
        return

    # Backwards from the add: Detach <- Set Dropped <- Branch(room)
    # <- Cast(target) <- Branch(found) <- the loop's Completed.
    looses = [n for n, _pin in _exec_from(takes[0])]
    check("the taken item is detached from whatever it was left in (a body a "
          "thrown blade struck), staying where it is",
          len(looses) == 1 and "detachfromactor" in _title(looses[0]).replace(" ", "").lower()
          and _target_as_item(looses[0], "self")
          and all(pin_value(looses[0], r) == "KeepWorld"
                  for r in ("LocationRule", "RotationRule", "ScaleRule")),
          ", ".join(_title(n) for n in looses))
    if len(looses) != 1:
        return
    flags = [n for n, _pin in _exec_from(looses[0])]
    check("the taken item stops being Dropped",
          len(flags) == 1 and _title(flags[0]) == "Set Dropped"
          and pin_value(flags[0], "Dropped") == "false"
          and _target_as_item(flags[0], "self"),
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
    casts = _exec_from(rooms[0][0])
    check(f"...only when the target is an item ({INTERACT_TARGET_VAR}'s cast "
          "took it)",
          len(casts) == 1 and casts[0][1] == "then" and "Cast" in _title(casts[0][0])
          and _reads(casts[0][0], "Object", INTERACT_TARGET_VAR),
          ", ".join(f"{_title(n)}.{pin}" for n, pin in casts))
    if len(casts) != 1:
        return
    founds = _exec_from(casts[0][0])
    valid = [c for n, _pin in founds for c in _sources(n, "Condition")]
    check(f"...and only when a target was kept ({INTERACT_TARGET_VAR} is valid)",
          len(founds) == 1 and founds[0][1] == "then" and len(valid) == 1
          and _reads(valid[0], "Object", INTERACT_TARGET_VAR),
          f"{len(founds)} gate(s)")
    if len(founds) != 1:
        return
    entries = _exec_from(founds[0][0])
    check("the take runs once per press: off the loop's Completed, not its body",
          [pin for _n, pin in entries] == ["Completed"],
          str([pin for _n, pin in entries]))


def run():
    check_pickup_takes_once()
