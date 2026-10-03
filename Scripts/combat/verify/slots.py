"""verify.slots -- the inventory's slots (slot_tuning.py,
weapon_component/slot_sync.py, slot_moves.py): each item's Slot and
WeaponKind, the component's slot variables and number keys, the issued
items' slots, the sync before the refresh, and the keys' requests.

Checked on the defaults and the wiring; probes/probe_slots.py moves items
about in a game.
"""

from combat.paths import AXE_BP_PATH, ITEM_BP_PATH, KNIFE_BP_PATH
from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, HAND, HAND_FROM_VAR, HAS_ROOM_VAR, LONG_GUN, MELEE_KIND, MELEE_SLOT,
    MOVE_FROM_VAR, MOVE_TO_VAR, NO_REQUEST, NOT_A_WEAPON, PISTOL_KIND, PISTOL_SLOT,
    PRIMARY, SECONDARY, SLOT_COUNT, SLOT_ITEMS_VAR, SLOT_KEYS, SLOT_REQUEST_VAR, SLOT_VAR,
    STARTER_HAND_FROM, STARTER_SLOTS, UNPLACED, WEAPON_KIND_VAR, fits,
)
from combat.verify.common import BEL, PIN, by_pins, cdo, check, load, num_pin, pin_value
from combat.verify.fixtures import wc_cdo, wg
from combat.weapon_component.inventory import STARTER_CLASS_VARS
from combat.weapon_specs import _weapon_specs


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _exec_feeders(node):
    p = BEL.find_execute_pin(node)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def check_slot_rule():
    """The rule itself, in Python (the graphs' fits() is the same)."""
    table = {(LONG_GUN, PRIMARY): True, (LONG_GUN, SECONDARY): True,
             (LONG_GUN, PISTOL_SLOT): False, (PISTOL_KIND, PISTOL_SLOT): True,
             (PISTOL_KIND, PRIMARY): False, (MELEE_KIND, MELEE_SLOT): True,
             (MELEE_KIND, SECONDARY): False, (NOT_A_WEAPON, PRIMARY): False,
             (NOT_A_WEAPON, MELEE_SLOT): False, (NOT_A_WEAPON, HAND): True,
             (NOT_A_WEAPON, BAG_FIRST): True, (LONG_GUN, SLOT_COUNT - 1): True,
             (LONG_GUN, SLOT_COUNT): False}
    wrong = {k: v for k, v in table.items() if fits(*k) != v}
    check("only a weapon fits a weapon slot (a long gun the primary or the secondary, "
          "the pistol its own, a blade the melee); the hand and the bag take anything",
          not wrong, str(wrong))


def check_item_slots():
    item = cdo(load(ITEM_BP_PATH))
    check(f"BP_WeaponItem starts {SLOT_VAR} = UNPLACED and {WEAPON_KIND_VAR} = NOT_A_WEAPON",
          item.get_editor_property(SLOT_VAR) == UNPLACED
          and item.get_editor_property(WEAPON_KIND_VAR) == NOT_A_WEAPON,
          f"{item.get_editor_property(SLOT_VAR)}, {item.get_editor_property(WEAPON_KIND_VAR)}")
    kinds = {s["display"]: cdo(load(s["path"])).get_editor_property(WEAPON_KIND_VAR)
             for s in _weapon_specs()}
    want = {d: (PISTOL_KIND if d == "Pistol" else LONG_GUN) for d in kinds}
    check("the pistol belongs in the pistol slot, every other gun in the primary",
          kinds == want, str(kinds))
    blades = [cdo(load(p)).get_editor_property(WEAPON_KIND_VAR)
              for p in (KNIFE_BP_PATH, AXE_BP_PATH)]
    check("the knife and the axe belong in the melee slot", blades == [MELEE_KIND] * 2,
          str(blades))


def check_component_slots():
    items = wc_cdo.get_editor_property(SLOT_ITEMS_VAR)
    check(f"the weapon component has {SLOT_ITEMS_VAR}, an array the sync fills",
          items is not None, repr(items))
    for var in (SLOT_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR):
        check(f"{var} starts at {NO_REQUEST}: no request",
              wc_cdo.get_editor_property(var) == NO_REQUEST,
              repr(wc_cdo.get_editor_property(var)))
    check(f"{HAND_FROM_VAR} starts at the primary slot (the issued shotgun's)",
          wc_cdo.get_editor_property(HAND_FROM_VAR) == STARTER_HAND_FROM)
    check(f"{HAS_ROOM_VAR} exists, true until the first sync",
          wc_cdo.get_editor_property(HAS_ROOM_VAR) is True)
    keys = [wc_cdo.get_editor_property(v).export_text() for v, _k, _s in SLOT_KEYS]
    check("1-9 are the slot keys", keys == [k for _v, k, _s in SLOT_KEYS], str(keys))


def check_starter_slots():
    sets = [n for n in wg if _title(n) == f"Set {SLOT_VAR}"]
    begin = [n for n in sets if any("Add" == _title(f) for f in _exec_feeders(n))
             and pin_value(n, SLOT_VAR) not in (str(UNPLACED),)
             # a literal: the take-off and the dragged wear write a wired one
             and not _feeders(n, SLOT_VAR)]
    got = sorted(int(float(pin_value(n, SLOT_VAR) or 0)) for n in begin)
    check(f"BeginPlay gives each issued item its slot ({len(STARTER_CLASS_VARS)}: the "
          "shotgun in hand, the pistol and the knife in theirs, the rest in the bag)",
          len(STARTER_SLOTS) == len(STARTER_CLASS_VARS) and got == sorted(STARTER_SLOTS),
          str(got))


def check_sync():
    resizes = [n for n in by_pins(wg, "TargetArray", "Size")]
    check(f"the sync sizes {SLOT_ITEMS_VAR} to {SLOT_COUNT} every Tick",
          len(resizes) == 1 and num_pin(resizes[0], "Size") == float(SLOT_COUNT),
          str([pin_value(n, "Size") for n in resizes]))
    finds = [n for n in by_pins(wg, "TargetArray", "ItemToFind")
             if any(_title(a) == f"Get {SLOT_ITEMS_VAR}"
                    for g in _feeders(n, "ItemToFind") for a in _feeders(g, "TargetArray"))]
    fed = [s for f in finds for q in PIN.list_connected_pins(BEL.find_output_pin(f, "ReturnValue"))
           for s in [PIN.get_owning_node(q)] if _title(s) == "Set EquippedIndex"]
    check("EquippedIndex is found from the hand slot's item (-1 for empty hands)",
          len(fed) == 1, f"{len(finds)} Find node(s), {len(fed)} feeding EquippedIndex")
    rooms = [n for n in wg if _title(n) == f"Set {HAS_ROOM_VAR}"]
    check(f"{HAS_ROOM_VAR} is written once, by the sync", len(rooms) == 1, str(len(rooms)))
    gate = [n for n in wg if _title(n) == "Branch"
            and any(_title(f) == "Get NeedsRefresh" for f in _feeders(n, "Condition"))]
    into = [f for g in gate for f in _exec_feeders(g)]
    refresh = [f for f in into if _title(f) == "Set NeedsRefresh" and any(
        any("Not Equal" in _title(c) or "!=" in _title(c) for c in _feeders(b, "Condition"))
        for b in _exec_feeders(f))]
    check("the sync runs into the refresh, raising it when the hand slot's item is not Held",
          len(gate) == 1 and len(refresh) == 1, f"{len(gate)} gate(s), "
          f"{[_title(f) for f in into]}")


def _exec_from(node):
    """(node, pin name) of every exec output wired into ``node``."""
    return [(PIN.get_owning_node(q), str(PIN.get_pin_name(q)))
            for q in PIN.list_connected_pins(BEL.find_execute_pin(node))]


def check_weapon_slot_first():
    """An UNPLACED weapon is offered its weapon slots before the bag: the
    sync's bag search runs only off the miss of a search of the four."""
    loops = by_pins(wg, "FirstIndex", "LastIndex")
    span = lambda n: (num_pin(n, "FirstIndex"), num_pin(n, "LastIndex"))
    after = []
    for bag in (n for n in loops if span(n) == (float(BAG_FIRST), float(BAG_LAST))):
        for miss, pin in _exec_from(bag):
            if pin != "else" or _title(miss) != "Branch":
                continue
            after += [w for w, wpin in _exec_from(miss)
                      if wpin == "Completed" and w in loops
                      and span(w) == (float(PRIMARY), float(MELEE_SLOT))]
    check("the sync offers an UNPLACED item a free weapon slot it fits before the bag "
          "(a looted weapon goes to its own slot): the bag is searched off that "
          "search's miss", len(after) == 1, f"{len(after)} such search(es)")


def check_keys():
    asked = {}
    for n in wg:
        if _title(n) != f"Set {SLOT_REQUEST_VAR}" or not pin_value(n, SLOT_REQUEST_VAR):
            continue
        for b in _exec_feeders(n):
            for poll in _feeders(b, "Condition"):
                for k in _feeders(poll, "Key"):
                    asked[_title(k).replace("Get ", "")] = int(float(
                        pin_value(n, SLOT_REQUEST_VAR)))
    want = {v: s for v, _k, s in SLOT_KEYS}
    check("each number key asks for its slot: 1-4 the weapon slots, 5-9 the bag's first five",
          asked == want, str(asked))


def run():
    check_slot_rule()
    check_item_slots()
    check_component_slots()
    check_starter_slots()
    check_sync()
    check_weapon_slot_first()
    check_keys()
