"""verify.wear -- putting a garment on and taking one off.

Mirrors weapon_component/wear.py: the wear behind the Consumable tap, and the
take-off the I panel asks for (TakeOffSlot); wear_drag.py's WearRequest; and
drop_request.py's DropRequest (an item dragged out of the inventory). Checked on the wiring and the
defaults; probes/probe_clothing.py runs both in a game.
"""

from combat.paths import ITEM_BP_PATH
from combat.slot_tuning import (
    DROP_ITEM_VAR, DROP_REQUEST_VAR, DROP_WANT_VAR, NO_REQUEST, SLOT_VAR,
)
from combat.verify.common import BEL, PIN, cdo, check, in_pins, load, pin_value
from combat.verify.fixtures import wc_cdo, wg
from combat.wear_tuning import (
    CLOTHING_SLOT_VAR, NOT_CLOTHING, TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_ITEM_VAR,
    WEAR_REQUEST_VAR, WORN_VAR,
)
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.wear import WEAR_SLOT_VAR


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _chain(node, limit=40):
    """The node and every one reached by `then` pins from it."""
    seen, cur = [node], node
    while len(seen) < limit:
        then = BEL.find_then_pin(cur)
        nxt = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(then)] if then else []
        if not nxt:
            break
        cur = nxt[0]
        seen.append(cur)
    return seen


def _in_order(titles, wanted):
    """Each of ``wanted`` (substrings) found in ``titles``, in that order."""
    at = 0
    for w in wanted:
        hits = [i for i, t in enumerate(titles) if i >= at and w in t]
        if not hits:
            return False
        at = hits[0] + 1
    return True


def _gated_on(var):
    """Branches whose condition is GreaterEqual(Get <var>, 0)."""
    out = []
    for b in wg:
        if b.get_class().get_name() != "K2Node_IfThenElse":
            continue
        for ge in _feeders(b, "Condition"):
            # "" too: a literal equal to its pin's default reads back empty
            # once the graph is loaded from disk (CLAUDE.md).
            if "B" in in_pins(ge) and pin_value(ge, "B") in ("0", "") and any(
                    _title(f) == f"Get {var}" for f in _feeders(ge, "A")):
                out.append(b)
    return out


def check_wear_state():
    item = cdo(load(ITEM_BP_PATH))
    check(f"BP_WeaponItem.{CLOTHING_SLOT_VAR} starts at {NOT_CLOTHING}: no item is a garment "
          f"unless its builder says so",
          item.get_editor_property(CLOTHING_SLOT_VAR) == NOT_CLOTHING)
    worn = wc_cdo.get_editor_property(WORN_VAR)
    check(f"the weapon component has {WORN_VAR}, an empty array the wear grows",
          worn is not None and len(worn) == 0, repr(worn))
    for var in (TAKE_OFF_VAR, TAKE_OFF_TO_VAR, WEAR_REQUEST_VAR, WEAR_SLOT_VAR):
        check(f"{var} starts at {NOT_CLOTHING}",
              wc_cdo.get_editor_property(var) == NOT_CLOTHING,
              repr(wc_cdo.get_editor_property(var)))


def check_wear():
    gates = [b for b in _gated_on(CLOTHING_SLOT_VAR) if any(
        "Consumable" in str(PIN.get_pin_name(p)) for f in _feeders(b, "execute")
        for up in _feeders(f, "execute") for g in _feeders(up, "Condition")
        for p in BEL.list_output_pins(g))]
    check(f"one Branch on Held.{CLOTHING_SLOT_VAR} >= 0, behind the Consumable tap",
          len(_gated_on(CLOTHING_SLOT_VAR)) == 1 and len(gates) == 1,
          f"{len(_gated_on(CLOTHING_SLOT_VAR))} gates, {len(gates)} behind the tap")
    if not gates:
        return
    titles = [_title(n) for n in _chain(
        PIN.get_owning_node(PIN.list_connected_pins(BEL.find_then_pin(gates[0]))[0]))]
    check("...whose true arm wears it: stored, out of the bag, the old one back in, "
          "into Worn, hidden, out of the hand, re-equipped and the press spent",
          _in_order(titles, [f"Set {WEAR_ITEM_VAR}", f"Set {WEAR_SLOT_VAR}", "Remove",
                             "Add", "Set Array Elem", "Hidden", "Set Held",
                             "Set EquippedIndex", "Set NeedsRefresh",
                             f"Set {TRIGGER_SPENT}"]), str(titles))
    sets = [n for n in wg if "bSizeToFit" in in_pins(n)
            and any(_title(f) == f"Get {WORN_VAR}" for f in _feeders(n, "TargetArray"))]
    check(f"{WORN_VAR} is written four times (the wear, the dragged wear, the take-off, "
          "the drag out of the inventory), the wears' grown to fit",
          len(sets) == 4 and sorted(pin_value(n, "bSizeToFit") or "false" for n in sets)
          == ["false", "false", "true", "true"], str([pin_value(n, "bSizeToFit") for n in sets]))


def check_take_off():
    gates = _gated_on(TAKE_OFF_VAR)
    check(f"one Branch serves {TAKE_OFF_VAR} >= 0", len(gates) == 1, str(len(gates)))
    if not gates:
        return
    titles = [_title(n) for n in _chain(
        PIN.get_owning_node(PIN.list_connected_pins(BEL.find_then_pin(gates[0]))[0]))]
    check(f"...copied, lowered (and {TAKE_OFF_TO_VAR} with it), then Worn[slot] back into "
          f"the bag (behind its valid index, a garment there and room), given its slot, "
          f"the worn slot emptied and the hand re-equipped",
          _in_order(titles, [f"Set {WEAR_SLOT_VAR}", f"Set {TAKE_OFF_VAR}",
                             f"Set {TAKE_OFF_TO_VAR}", "Branch", "Branch", "Branch", "Add",
                             f"Set {SLOT_VAR}", "Set Array Elem", "Set NeedsRefresh"]),
          str(titles))
    # (The Ask event's Set is fed by its parameter: verify/asks.py.)
    lowered = [n for n in wg if _title(n) == f"Set {TAKE_OFF_VAR}" and not _feeders(n, TAKE_OFF_VAR)]
    check(f"...and {TAKE_OFF_VAR} is lowered to {NOT_CLOTHING}, by that one Set",
          len(lowered) == 1 and pin_value(lowered[0], TAKE_OFF_VAR) == str(NOT_CLOTHING),
          str([pin_value(n, TAKE_OFF_VAR) for n in lowered]))


def check_wear_request():
    gates = _gated_on(WEAR_REQUEST_VAR)
    check(f"one Branch serves {WEAR_REQUEST_VAR} >= 0 (a drag onto the worn grid)",
          len(gates) == 1, str(len(gates)))
    if not gates:
        return
    titles = [_title(n) for n in _chain(
        PIN.get_owning_node(PIN.list_connected_pins(BEL.find_then_pin(gates[0]))[0]))]
    check("...the slot's item stored and the request lowered, then a garment out of "
          "Inventory, the old one back in the slot it left, into Worn, hidden, "
          "unplaced and the hand re-equipped",
          _in_order(titles, [f"Set {WEAR_ITEM_VAR}", f"Set {WEAR_REQUEST_VAR}", "Branch",
                             f"Set {WEAR_SLOT_VAR}", "Branch", "Remove", "Add",
                             f"Set {SLOT_VAR}", "Set Array Elem", "Hidden",
                             f"Set {SLOT_VAR}", "Set NeedsRefresh"]), str(titles))
    # (The Ask event's Set is fed by its parameter: verify/asks.py.)
    lowered = [n for n in wg if _title(n) == f"Set {WEAR_REQUEST_VAR}" and not _feeders(n, WEAR_REQUEST_VAR)]
    check(f"...and {WEAR_REQUEST_VAR} is lowered to {NOT_CLOTHING}, by that one Set",
          len(lowered) == 1 and pin_value(lowered[0], WEAR_REQUEST_VAR) == str(NOT_CLOTHING),
          str([pin_value(n, WEAR_REQUEST_VAR) for n in lowered]))


def check_drop_request():
    gates = _gated_on(DROP_REQUEST_VAR)
    check(f"one Branch serves {DROP_REQUEST_VAR} >= 0 (a drag out of the inventory)",
          len(gates) == 1, str(len(gates)))
    if not gates:
        return
    titles = [_title(n) for n in _chain(
        PIN.get_owning_node(PIN.list_connected_pins(BEL.find_then_pin(gates[0]))[0]))]
    check("...the request copied and lowered, the slot's item stored and taken out of "
          "Inventory, then set down: Dropped, detached, shown, traced onto the ground, "
          "unplaced and the hand re-equipped",
          _in_order(titles, [f"Set {DROP_WANT_VAR}", f"Set {DROP_REQUEST_VAR}",
                             f"Set {DROP_ITEM_VAR}", "Branch", f"Set {DROP_ITEM_VAR}",
                             "Branch", "Remove", "Branch", "Set Dropped", "Detach",
                             "Hidden", "Line Trace", "Branch", "Set Actor Location",
                             f"Set {SLOT_VAR}", "Set NeedsRefresh"]), str(titles))
    # (The Ask event's Set is fed by its parameter: verify/asks.py.)
    lowered = [n for n in wg if _title(n) == f"Set {DROP_REQUEST_VAR}" and not _feeders(n, DROP_REQUEST_VAR)]
    check(f"...and {DROP_REQUEST_VAR} is lowered to {NO_REQUEST}, by that one Set",
          len(lowered) == 1 and pin_value(lowered[0], DROP_REQUEST_VAR) == str(NO_REQUEST),
          str([pin_value(n, DROP_REQUEST_VAR) for n in lowered]))
    stored = [n for n in wg if _title(n) == f"Set {DROP_ITEM_VAR}"]
    check(f"...{DROP_ITEM_VAR} is cleared, then stored off SlotItems or off {WORN_VAR}: "
          "three Sets",
          len(stored) == 3 and sorted(len(_feeders(n, DROP_ITEM_VAR)) for n in stored)
          == [0, 1, 1], str(len(stored)))


def run():
    check_wear_state()
    check_wear()
    check_take_off()
    check_wear_request()
    check_drop_request()
