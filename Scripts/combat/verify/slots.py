"""verify.slots -- the inventory's slots (slot_tuning.py,
weapon_component/slot_sync.py, slot_moves.py): each item's Slot and
WeaponKind, the component's slot variables and number keys, the issued
items' slots, the sync before the refresh, and the keys' asks.

Checked on the defaults and the wiring; probes/probe_slots.py moves items
about in a game.
"""

from combat.paths import AXE_BP_PATH, ITEM_BP_PATH, KNIFE_BP_PATH
from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, BAG_SIZE, HAND, HAND_FROM_VAR, HAS_ROOM_VAR, LONG_GUN, MELEE_KIND, MELEE_SLOT,
    MOVE_DST_VAR, MOVE_FROM_VAR, MOVE_SRC_VAR, MOVE_TO_VAR, NEXT_REQUEST_VAR, NO_REQUEST, NOT_A_WEAPON, PISTOL_KIND, PISTOL_SLOT,
    PRIMARY, SECONDARY, SLOT_COUNT, SLOT_ITEMS_VAR, SLOT_KEYS, SLOT_REQUEST_VAR, SLOT_VAR,
    STARTER_HAND_FROM, STARTER_SLOTS, UNPLACED, USE_FIT_VAR, USE_FREE_VAR, USE_REQUEST_VAR,
    USE_WANT_VAR, WEAPON_KIND_VAR, fits,
)
from combat.ask_consts import ASK_MOVE, ASK_NEXT, ASK_SLOT, FROM_PARAM, SLOT_PARAM, TO_PARAM
from combat.wear_tuning import CLOTHING_SLOT_VAR, WEAR_REQUEST_VAR
from combat.record_vars import FORCED, NO_ASK, MoveForcedFrom, MoveForcedTo, SlotForced
from combat.verify.common import (
    BEL, PIN, before_marks, by_pins, cdo, check, in_pins, load, num_pin, pin_value)
from combat.verify.fixtures import _is_exec, wc_cdo, wg
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
    begin = [n for n in sets if any("Add" == _title(f) for f in before_marks(_exec_feeders(n)))
             and pin_value(n, SLOT_VAR) not in (str(UNPLACED),)
             # a literal: the take-off and the dragged wear write a wired one
             and not _feeders(n, SLOT_VAR)]
    got = sorted(int(float(pin_value(n, SLOT_VAR) or 0)) for n in begin)
    check(f"BeginPlay gives each issued item its slot ({len(STARTER_CLASS_VARS)}: the "
          "shotgun in hand, the pistol and the knife in theirs, the rest in the bag)",
          len(STARTER_SLOTS) == len(STARTER_CLASS_VARS) and got == sorted(STARTER_SLOTS),
          str(got))


def check_sync():
    # The sync's, and the one a dead player's shed gear empties the slots
    # with, once (weapon_component/shed.py, verify/player_death.py).
    resizes = [n for n in by_pins(wg, "TargetArray", "Size")
               if any(_title(f) == f"Get {SLOT_ITEMS_VAR}" for f in _feeders(n, "TargetArray"))]
    check(f"the sync sizes {SLOT_ITEMS_VAR} to {SLOT_COUNT} every Tick (and the shed "
          f"gear of a dead player, to the same)",
          len(resizes) == 2
          and all(num_pin(n, "Size") == float(SLOT_COUNT) for n in resizes),
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
    # Through the record (weapon_component/record.py), which the server writes
    # between the two.
    raised = [n for n in wg if _title(n) == "Set NeedsRefresh" and any(
        any("Not Equal" in _title(c) or "!=" in _title(c) for c in _feeders(b, "Condition"))
        for b in _exec_feeders(n))]
    refresh = [n for n in raised if gate and gate[0] in _reach(n)]
    check("the sync runs into the refresh (by way of the record), raising it when the "
          "hand slot's item is not Held",
          len(gate) == 1 and len(refresh) == 1, f"{len(gate)} gate(s), "
          f"{len(raised)} raise(s), {len(refresh)} reaching it")


def _reach(node, limit=400):
    """Every node an exec output of ``node`` reaches."""
    seen, todo = [], [node]
    while todo and len(seen) < limit:
        cur = todo.pop()
        for p in BEL.list_output_pins(cur):
            if not _is_exec(p):
                continue
            for q in PIN.list_connected_pins(p):
                n = PIN.get_owning_node(q)
                if n not in seen:
                    seen.append(n)
                    todo.append(n)
    return seen


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


def _calls(name):
    return [n for n in wg if _title(n).replace(" ", "") == name and "self" in in_pins(n)]


def check_keys():
    asked = {}
    for n in _calls(ASK_SLOT):
        if _feeders(n, SLOT_PARAM):
            continue
        for b in _exec_feeders(n):
            for poll in _feeders(b, "Condition"):
                for k in _feeders(poll, "Key"):
                    asked[_title(k).replace("Get ", "")] = int(float(
                        pin_value(n, SLOT_PARAM) or 0))
    want = {v: s for v, _k, s in SLOT_KEYS}
    check(f"each number key asks for its slot ({ASK_SLOT}, a Server event): 1-4 the "
          "weapon slots, 5-9 the bag's first five", asked == want, str(asked))
    nexts = [k for n in _calls(ASK_NEXT) for b in _exec_feeders(n)
             for poll in _feeders(b, "Condition") for k in _feeders(poll, "Key")]
    check(f"Q asks for the bag's next item ({ASK_NEXT}), and no key writes a request "
          "itself: the server's copy is asked",
          [_title(k) for k in nexts] == ["Get KeySwitch"]
          and not [n for n in wg if _title(n) == f"Set {SLOT_REQUEST_VAR}"
                   and pin_value(n, SLOT_REQUEST_VAR) not in ("", str(NO_REQUEST))
                   and not _feeders(n, SLOT_REQUEST_VAR)],
          str([_title(k) for k in nexts]))
    forced = {ASK_SLOT: [_title(f) for n in _calls(ASK_SLOT) for f in _feeders(n, SLOT_PARAM)],
              ASK_MOVE: [_title(f) for n in _calls(ASK_MOVE)
                         for pin in (FROM_PARAM, TO_PARAM) for f in _feeders(n, pin)]}
    check("a probe's forced slot and move ask as the keys and the HUD do "
          f"({', '.join(map(str, FORCED))})",
          forced == {ASK_SLOT: [f"Get {SlotForced}"],
                     ASK_MOVE: [f"Get {MoveForcedFrom}", f"Get {MoveForcedTo}"]}
          and all(wc_cdo.get_editor_property(str(v)) == NO_ASK for v in FORCED), str(forced))
    spans = [(num_pin(w, "FirstIndex"), num_pin(w, "LastIndex"))
             for w in by_pins(wg, "FirstIndex", "LastIndex")]
    spans = [s for s in spans if s == (1.0, float(BAG_SIZE))]
    raised = [n for n in wg if _title(n) == f"Set {NEXT_REQUEST_VAR}"]
    check(f"Q raises {NEXT_REQUEST_VAR}, which is lowered as it is served, and the search "
          f"it starts steps round the bag's {BAG_SIZE} slots, not the weapon slots",
          sorted(pin_value(n, NEXT_REQUEST_VAR) for n in raised) == [str(NO_REQUEST), "1"]
          and len(spans) == 1, f"{[pin_value(n, NEXT_REQUEST_VAR) for n in raised]}, {spans}")
    check(f"{NEXT_REQUEST_VAR} starts at {NO_REQUEST}: no request",
          wc_cdo.get_editor_property(NEXT_REQUEST_VAR) == NO_REQUEST)


def check_use_request():
    """use_request.py: the I panel's right click, served into the requests
    the Tick already serves."""
    rest = {v: wc_cdo.get_editor_property(v) for v in (
        USE_REQUEST_VAR, USE_WANT_VAR, USE_FREE_VAR, USE_FIT_VAR)}
    check(f"{USE_REQUEST_VAR} and its scratch start at {NO_REQUEST}: no request",
          all(v == NO_REQUEST for v in rest.values()), str(rest))
    copies = [n for n in wg if _title(n) == f"Set {USE_WANT_VAR}"]
    check(f"the use is copied ({USE_WANT_VAR}) off {USE_REQUEST_VAR} and the request lowered",
          [_title(f) for n in copies for f in _feeders(n, USE_WANT_VAR)] == [f"Get {USE_REQUEST_VAR}"]
          and [pin_value(n, USE_REQUEST_VAR) for n in wg if _title(n) == f"Set {USE_REQUEST_VAR}"
               and not _feeders(n, USE_REQUEST_VAR)] == [str(NO_REQUEST)],
          str(len(copies)))
    raised = {v: [_title(f) for n in wg if _title(n) == f"Set {v}"
                  for f in _feeders(n, v) if _title(f) == f"Get {USE_WANT_VAR}"]
              for v in (WEAR_REQUEST_VAR, SLOT_REQUEST_VAR, MOVE_FROM_VAR)}
    check("it raises a wear (a garment), a slot request (a weapon slot's item, or "
          "anything but a weapon: to hand) or a move (a weapon in the hand or the bag), "
          "each off the copy, and nothing else",
          {v: len(r) for v, r in raised.items()}
          == {WEAR_REQUEST_VAR: 1, SLOT_REQUEST_VAR: 1, MOVE_FROM_VAR: 1}, str(raised))
    moves = [n for n in wg if _title(n) == f"Set {MOVE_TO_VAR}"
             and any(_title(f) == "SelectInt" for f in _feeders(n, MOVE_TO_VAR))]
    picks = [sorted(_title(g) for pin in ("A", "B") for g in _feeders(s, pin))
             for n in moves for s in _feeders(n, MOVE_TO_VAR)]
    check(f"the weapon's slot is the first free one it fits ({USE_FREE_VAR}), else the "
          f"first it fits at all ({USE_FIT_VAR}: a long gun's the primary, which the "
          "move then swaps)",
          picks == [[f"Get {USE_FIT_VAR}", f"Get {USE_FREE_VAR}"]], str(picks))
    spans = [(num_pin(w, "FirstIndex"), num_pin(w, "LastIndex"))
             for w in by_pins(wg, "FirstIndex", "LastIndex")]
    check(f"...searched over the weapon slots alone ({PRIMARY}..{MELEE_SLOT})",
          (float(PRIMARY), float(MELEE_SLOT)) in spans, str(spans))
    gates = [n for n in wg if "Condition" in in_pins(n)
             for c in _feeders(n, "Condition")
             for a in _feeders(c, "A") if _title(a) == f"Get {CLOTHING_SLOT_VAR}"
             and any(_title(i) == "Get" for i in _feeders(a, "self"))]
    check("a garment is told by its ClothingSlot, read off the slot's item",
          len(gates) == 1, str(len(gates)))


def check_drag_to_hand():
    """slot_moves._author_slot_move: a drag onto the hand the swap refuses."""
    raised = [n for n in wg if _title(n) == f"Set {SLOT_REQUEST_VAR}"
              and [_title(f) for f in _feeders(n, SLOT_REQUEST_VAR)] == [f"Get {MOVE_SRC_VAR}"]]
    gates = [[_title(a) for c in _feeders(b, "Condition") for a in _feeders(c, "A")]
             for n in raised for b in _exec_feeders(n)]
    check("a drag onto the hand, whose item does not fit the slot it came from, asks "
          f"for that slot as its key does ({SLOT_REQUEST_VAR} off {MOVE_SRC_VAR}, behind "
          f"a Branch on {MOVE_DST_VAR}): the hand's item goes home",
          gates == [[f"Get {MOVE_DST_VAR}"]], str(gates))


def run():
    check_drag_to_hand()
    check_slot_rule()
    check_item_slots()
    check_component_slots()
    check_starter_slots()
    check_sync()
    check_weapon_slot_first()
    check_keys()
    check_use_request()
