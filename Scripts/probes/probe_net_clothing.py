"""Clothing is the server's, and the owning client's worn slots are a picture
of it (M24).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_clothing.py

Wearing and taking off are Server events on the weapon component
(combat/weapon_component/wear.py, wear_drag.py: Server_Wear, AskWear,
AskTakeOff); what is worn is the server's item actors, written down as
the record (combat/record_vars.py), which goes to the owning client and
which that client's Worn is made from (view_worn.py).

    the server  gives client 1's character the level's hat and jacket (its own
                Server_Take), and after each thing client 1 does says what
                its copy of that character wears
    client 1    brings the hat to hand and presses the fire key; drags the
                jacket's slot onto the worn grid (AskWear); asks to wear the
                axe and to take off a slot nothing is worn in (both refused);
                takes the jacket off into the bag (AskTakeOff); drags the hat
                out of the inventory (AskDrop of a worn slot). After each its
                own worn slots are what the server says
    client 2    is told none of it: its copy of client 1's character wears
                nothing, and nor does its own

Single player (`--game`) does the same on the one machine: the asks are plain
calls there.

A client's asks go through FireForced, WearForced, TakeOffForced and
DropForced, which the component's Tick turns into the Server events where the
keys are read: a Blueprint Server event called from Python is not sent.
"""

import time

import unreal

from combat import item_vars as IV
from combat.ask_consts import ASK_DROP, ASK_TAKE_OFF, ASK_WEAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.record_vars import FORCED
from combat.slot_tuning import BAG_FIRST, BAG_LAST, SLOT_COUNT, SLOT_VAR, UNPLACED
from combat.strike_vars import SERVER_TAKE
from combat.wear_tuning import SERVER_WEAR, WEAR_SLOTS, WORN_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_chop_tree import _items

RUNS_ON = ("server", "client", "standalone")
WRITABLE = [(WEAPON_COMP_BP_PATH, str(v)) for v in FORCED + (FIRE_FORCED_VAR,)]
WAIT = 20.0
HAT, JACKET = WEAR_SLOTS.index("hat"), WEAR_SLOTS.index("jacket")
GLOVES = WEAR_SLOTS.index("gloves")
NOTHING = [None] * len(WEAR_SLOTS)
STEPS = ("key", "drag", "refused", "off", "drop")
# What is worn after each step.
WANT = {
    "key": {HAT: "Hat"},
    "drag": {HAT: "Hat", JACKET: "Jacket"},
    "refused": {HAT: "Hat", JACKET: "Jacket"},
    "off": {HAT: "Hat"},
    "drop": {},
}


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _wc(p, actor):
    return p.component(actor, WEAPON_COMP_CLASS_PATH)


def _name(obj):
    """An item's, or a class's, short name ("Hat"); None for nothing."""
    if not obj or not unreal.SystemLibrary.is_valid(obj):
        return None
    cls = obj if isinstance(obj, unreal.Class) else obj.get_class()
    return cls.get_name().replace("BP_", "").replace("_C", "")


def _row(names):
    """Padded to the eight slots: Worn is only as long as the last slot worn."""
    names = list(names)
    return names + [None] * (len(WEAR_SLOTS) - len(names))


def _worn(p, wc):
    return _row(_name(i) for i in p.get(wc, WORN_VAR))


def _worn_record(p, wc):
    part = wc.get_owner().get_component_by_class(unreal.OtherworldInventoryRecordComponent)
    return _row(_name(c) for c in part.get_editor_property("record").get_editor_property("worn"))


def _want(step):
    return [WANT[step].get(i) for i in range(len(WEAR_SLOTS))]


def _bag(p, wc):
    """{item name: its slot code} off the item actors."""
    return {_name(i): p.get(i, SLOT_VAR) for i in p.get(wc, WV.Inventory) if _name(i)}


def _give(p, pawn, wc, names):
    """The level's garments of those names into the character's bag, by the
    take itself, called where it runs. Returns what the bag then holds."""
    for name in names:
        lying = [a for a in _items(p, f"BP_{name}_C") if p.get(a, IV.Dropped)]
        if not lying:
            continue
        lying[0].set_actor_location(pawn.get_actor_location(), False, True)
        wc.call_method(SERVER_TAKE, (lying[0],))
    yield 0.3
    return _bag(p, wc)


def _steps(p, wc, said):
    """What client 1 (or single player) does, a step at a time. After each,
    ``said(step)`` is a generator that returns what the server says is worn
    (None in single player), which this machine's worn slots are checked
    against."""
    def settle(step):
        yield from _await(lambda: _worn(p, wc) == _want(step), 8.0)
        yield 0.3
        told = yield from said(step)
        return _worn(p, wc), told

    def agree(step, label, extra, detail=lambda: ""):
        # ``extra`` and ``detail`` are read once the step has settled.
        got, told = yield from settle(step)
        p.check(label, got == _want(step) and extra(), f"worn {got}, {detail()}")
        if told is not None:
            p.check("...and the server's copy wears the same",
                    told == got, f"server {told}, here {got}")

    # --- the fire key, the hat in hand -------------------------------------------
    p.ask_slot(wc, _bag(p, wc)["Hat"])
    yield from _await(lambda: _name(p.get(wc, WV.Held)) == "Hat", 8.0)
    held = _name(p.get(wc, WV.Held))
    p.set(wc, FIRE_FORCED_VAR, True)
    yield 0.15
    p.set(wc, FIRE_FORCED_VAR, False)
    yield from agree("key", f"the fire key with the hat in hand ({SERVER_WEAR}): the hat "
                     "is worn, out of the bag and out of the hand",
                     lambda: held == "Hat" and "Hat" not in _bag(p, wc)
                     and _name(p.get(wc, WV.Held)) != "Hat",
                     lambda: f"held {held} then {_name(p.get(wc, WV.Held))}")

    # --- a drag onto the worn grid ------------------------------------------------
    p.ask_wear(wc, _bag(p, wc)["Jacket"])
    yield from agree("drag", f"{ASK_WEAR}(the jacket's slot): the jacket is worn too, out "
                     "of the bag", lambda: "Jacket" not in _bag(p, wc),
                     lambda: f"bag {_bag(p, wc)}")

    # --- what the server refuses --------------------------------------------------
    bag = _bag(p, wc)
    p.ask_wear(wc, bag["Axe"])
    yield 0.6
    p.ask_take_off(wc, GLOVES, UNPLACED)
    yield 0.6
    yield from agree("refused", f"{ASK_WEAR}(the axe's slot) and {ASK_TAKE_OFF}(a slot "
                     "nothing is worn in) are refused: nothing moved",
                     lambda: _bag(p, wc) == bag, lambda: f"bag {_bag(p, wc)}")

    # --- off, into the bag ---------------------------------------------------------
    p.ask_take_off(wc, JACKET, UNPLACED)
    yield from _await(lambda: "Jacket" in _bag(p, wc), 8.0)
    yield from agree("off", f"{ASK_TAKE_OFF}(jacket): the jacket is back in a bag slot, "
                     "the hat still worn",
                     lambda: BAG_FIRST <= _bag(p, wc).get("Jacket", UNPLACED) <= BAG_LAST,
                     lambda: f"jacket in slot {_bag(p, wc).get('Jacket')}")

    # --- out of the inventory, onto the ground ------------------------------------
    p.ask_drop(wc, SLOT_COUNT + HAT)
    lying = lambda: [a for a in _items(p, "BP_Hat_C")
                     if p.get(a, IV.Dropped) and not a.get_editor_property("hidden")]
    yield from _await(lambda: _worn(p, wc) == _want("drop") and len(lying()) == 1, 8.0)
    yield from agree("drop", f"{ASK_DROP}(the worn hat): nothing is worn, and the hat "
                     "lies on the ground",
                     lambda: len(lying()) == 1 and "Hat" not in _bag(p, wc),
                     lambda: f"{len(lying())} hat(s) lying")


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield from _await(lambda: p.posted("client 1", "id") is not None)
    by_id = {c.player_state.player_id: c.get_controlled_pawn()
             for c in p.players() if c.player_state}
    pawn = by_id.get(p.posted("client 1", "id"))
    p.check("the server has client 1's character", bool(pawn), str(sorted(by_id)))
    if not pawn:
        return
    wc = _wc(p, pawn)
    others = [_wc(p, a) for a in by_id.values() if a != pawn]
    bag = yield from _give(p, pawn, wc, ("Hat", "Jacket"))
    p.check("the server gave client 1 the level's hat and jacket, into the bag; nothing "
            "is worn yet, and the record says so",
            "Hat" in bag and "Jacket" in bag and _worn(p, wc) == NOTHING
            and _worn_record(p, wc) == NOTHING, f"{bag}")
    p.post("given")

    for step in STEPS:
        yield from _await(lambda: p.posted("client 1", step) is not None, 40.0)
        yield 0.3
        got = _worn(p, wc)
        p.check(f"after client 1's '{step}' the server's copy wears {WANT[step] or 'nothing'}"
                ", its item actors and its record alike",
                got == _want(step) and _worn_record(p, wc) == got,
                f"worn {got}, record {_worn_record(p, wc)}")
        p.post(f"worn-{step}", got)
    p.check("nobody else wears anything",
            all(_worn(p, c) == NOTHING and _worn_record(p, c) == NOTHING for c in others),
            f"{len(others)} other(s)")
    hats = [a for a in _items(p, "BP_Hat_C") if p.get(a, IV.Dropped)]
    p.check("the dropped hat is the server's actor, lying in the world, replicated",
            len(hats) == 1 and bool(p.get(hats[0], IV.InWorld)),
            f"{len(hats)} hat(s)")
    p.post("done")


# ─── a client ────────────────────────────────────────────────────────────────

def probe_client(p):
    mine = p.pawn()
    wc = _wc(p, mine)
    yield from _await(lambda: p.get(wc, WV.Held) is not None
                      and p.player_state() is not None)
    if p.client == 1:
        p.post("id", p.player_state().player_id)
        yield from _await(lambda: p.posted("server", "given") is not None, 60.0)
        yield from _await(lambda: {"Hat", "Jacket"} <= set(_bag(p, wc)), 8.0)
        p.check("client 1's bag holds the hat and the jacket the server gave it, and "
                "it wears nothing", {"Hat", "Jacket"} <= set(_bag(p, wc))
                and _worn(p, wc) == NOTHING, f"{_bag(p, wc)}")

        def said(step):
            p.post(step)
            yield from _await(lambda: p.posted("server", f"worn-{step}") is not None)
            return p.posted("server", f"worn-{step}")

        yield from _steps(p, wc, said)
        p.check("its worn slots are a picture of the record it was sent, and it has "
                "authority over none of it", _worn_record(p, wc) == _worn(p, wc)
                and not mine.has_authority(), f"record {_worn_record(p, wc)}")
        return

    yield from _await(lambda: p.posted("server", "worn-drag") is not None, 90.0)
    yield 0.5
    cls = mine.get_class()
    theirs = [_wc(p, a) for a in
              unreal.GameplayStatics.get_all_actors_of_class(p.world(), cls) if a != mine]
    p.check("client 2 is told nothing of what client 1 wears (the record is the "
            "owner's): its copy of that character wears nothing",
            len(theirs) == p.clients - 1
            and all(_worn(p, c) == NOTHING and _worn_record(p, c) == NOTHING for c in theirs),
            f"{[_worn(p, c) for c in theirs]}")
    p.check("and client 2 wears nothing itself", _worn(p, wc) == NOTHING, f"{_worn(p, wc)}")
    yield from _await(lambda: p.posted("server", "done") is not None, 90.0)


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    mine = p.pawn()
    wc = _wc(p, mine)
    yield from _await(lambda: p.get(wc, WV.Held) is not None)
    bag = yield from _give(p, mine, wc, ("Hat", "Jacket"))
    p.check("standalone: the level's hat and jacket are in the bag, nothing worn",
            "Hat" in bag and "Jacket" in bag and _worn(p, wc) == NOTHING, f"{bag}")

    def said(step):
        yield 0.1
        p.check(f"standalone, '{step}': the record is what is worn",
                _worn_record(p, wc) == _worn(p, wc), f"record {_worn_record(p, wc)}")
        return None

    yield from _steps(p, wc, said)
