"""The combat side of it: the inventory size, the use event, the HP drain."""

from combat.paths import HEALTH_BP_PATH, WEAPON_COMP_BP_PATH
from combat.tuning import (
    CONSUME_EVENT_TAG, DEBUFF_DRAIN_HP_PER_S, HEALTH_DRAIN_TAG, INVENTORY_SIZE,
)
from combat.verify.common import (
    by_pins, check, graph, in_pins, load, num_pin, pin_value,
)


def run():
    check("the inventory holds 10", INVENTORY_SIZE == 10)
    wg = graph(load(WEAPON_COMP_BP_PATH)).list_all_nodes()
    rooms = [n for n in by_pins(wg, "A", "B") if pin_value(n, "B") == str(INVENTORY_SIZE)]
    check("pick-up refuses past INVENTORY_SIZE", len(rooms) >= 1)
    sends = by_pins(wg, "Actor", "EventTag", "Payload")
    check("the fire key can send exactly one use event", len(sends) == 1, str(len(sends)))
    if sends:
        check(f"...tagged {CONSUME_EVENT_TAG}",
              pin_value(sends[0], "EventTag") == f'(TagName="{CONSUME_EVENT_TAG}")')

    hg = graph(load(HEALTH_BP_PATH)).list_all_nodes()
    counts = by_pins(hg, "GameplayTag")
    check(f"the health component counts {HEALTH_DRAIN_TAG}",
          [pin_value(n, "GameplayTag") for n in counts]
          == [f'(TagName="{HEALTH_DRAIN_TAG}")'])
    rates = [n for n in by_pins(hg, "A", "B")
             if num_pin(n, "B") is not None
             and abs(num_pin(n, "B") - DEBUFF_DRAIN_HP_PER_S) < 1e-6]
    check(f"...and drains {DEBUFF_DRAIN_HP_PER_S} HP/s per stack", len(rates) == 1,
          str(len(rates)))
    sets = [n for n in hg if str(n.get_class().get_name()) == "K2Node_VariableSet"]
    prev = [n for n in sets if "PrevHealth" in in_pins(n)]
    check("...lowering PrevHealth with Health, so a drain is not a hit",
          len(prev) >= 2, str(len(prev)))

