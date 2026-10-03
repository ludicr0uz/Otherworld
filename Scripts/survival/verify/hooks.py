"""The combat side of it: the inventory size, the use event, the HP drain."""

from combat.paths import HEALTH_BP_PATH, WEAPON_COMP_BP_PATH
from combat.tuning import CONSUME_EVENT_TAG, HEALTH_DRAINS, INVENTORY_SIZE
from combat.slot_tuning import BAG_SIZE, HAS_ROOM_VAR
from combat.verify.common import (
    BEL, PIN, by_pins, check, graph, in_pins, load, num_pin, pin_value,
)


def run():
    check("the backpack holds 10", INVENTORY_SIZE == BAG_SIZE == 10)
    wg = graph(load(WEAPON_COMP_BP_PATH)).list_all_nodes()
    rooms = [n for n in by_pins(wg, "Condition")
             if any(f"Get {HAS_ROOM_VAR}" == str(BEL.get_node_title(PIN.get_owning_node(q)))
                    for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Condition")))]
    check(f"pick-up refuses with no room ({HAS_ROOM_VAR}: no free bag slot, no empty hand)",
          len(rooms) >= 1)
    sends = by_pins(wg, "Actor", "EventTag", "Payload")
    check("the fire key can send exactly one use event", len(sends) == 1, str(len(sends)))
    if sends:
        check(f"...tagged {CONSUME_EVENT_TAG}",
              pin_value(sends[0], "EventTag") == f'(TagName="{CONSUME_EVENT_TAG}")')

    hg = graph(load(HEALTH_BP_PATH)).list_all_nodes()
    counts = by_pins(hg, "GameplayTag")
    for tag, hp_per_s in HEALTH_DRAINS:
        mine = [n for n in counts if pin_value(n, "GameplayTag") == f'(TagName="{tag}")']
        check(f"the health component counts {tag}", len(mine) == 1, str(len(mine)))
        rates = [n for n in by_pins(hg, "A", "B")
                 if num_pin(n, "B") is not None
                 and abs(num_pin(n, "B") - hp_per_s) < 1e-6]
        check(f"...and drains {hp_per_s:g} HP/s per stack", len(rates) == 1,
              str(len(rates)))
    check("...and counts no other tag", len(counts) == len(HEALTH_DRAINS),
          str([pin_value(n, "GameplayTag") for n in counts]))
    sets = [n for n in hg if str(n.get_class().get_name()) == "K2Node_VariableSet"]
    prev = [n for n in sets if "PrevHealth" in in_pins(n)]
    check("...lowering PrevHealth with Health, so a drain is not a hit",
          len(prev) >= 2, str(len(prev)))

