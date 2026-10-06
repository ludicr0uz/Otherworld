"""The inventory is the server's, and each client's is a picture of it (M18).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_inventory.py

The server issues the loadout and writes it down as the record
(combat/record_vars.py: a row per item, its class, slot and rounds), which
replicates to the owning client; everyone else is told the class in hand.

    everyone   its own character carries the six issued items in their
               slots; on a client they are made from the record, row for row
    a client   another player's character here holds one item: the hand's
    client 1   asks for a move (the axe, to another bag slot), for a slot
               (the pistol to hand: the shotgun goes home to the primary) and
               for a move no rule allows (the matches into the primary slot)
    the server its copy of that character agrees after each, the record with
               it, and the refused move moved nothing; nobody else's changed
    client 2   sees the pistol in client 1's hand

Single player (`--game`) asks the same of the one character: the asks are
plain calls there, and the record is written just the same.

A client's asks go through SlotForced and MoveForcedFrom/To, which the
component's Tick turns into the Server events where the keys are read: a
Blueprint Server event called from Python is not sent.
"""

import time

import unreal

from combat import ask_consts as AC
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.record_vars import FORCED, HandClass, InvClass, InvLoaded, InvReserve, InvSlot
from combat.slot_tuning import (
    BAG_FIRST, HAND, PISTOL_SLOT, PRIMARY, SLOT_VAR, STARTER_HAND_FROM, STARTER_SLOTS)

RUNS_ON = ("server", "client", "standalone")
# A client asks through the component's own graph (context.ask_slot).
WRITABLE = [(WEAPON_COMP_BP_PATH, str(v)) for v in FORCED]
WAIT_S = 20.0
AXE_FROM, AXE_TO = BAG_FIRST, BAG_FIRST + 5
MATCHES_SLOT = BAG_FIRST + 1
STARTERS = ("Shotgun", "Pistol", "Knife", "Axe", "Matches", "Stick")


def _await(cond, seconds=WAIT_S):
    end = time.time() + seconds
    return lambda: cond() or time.time() > end


def _comp(p, actor):
    return p.component(actor, WEAPON_COMP_CLASS_PATH)


def _name(cls):
    return cls.get_name().replace("BP_", "").replace("_C", "") if cls else None


def _carried(p, comp):
    """{item name: (slot, loaded, reserve)} off the item actors."""
    return {_name(i.get_class()): (p.get(i, SLOT_VAR), p.get(i, "Loaded"), p.get(i, "Reserve"))
            for i in p.get(comp, "Inventory") if i}


def _record(p, comp):
    """The same off the record's four arrays."""
    cols = [list(p.get(comp, v)) for v in (InvClass, InvSlot, InvLoaded, InvReserve)]
    if len({len(c) for c in cols}) != 1:
        return {"torn": [len(c) for c in cols]}
    return {_name(c): (s, l, r) for c, s, l, r in zip(*cols)}


def _slots(carried):
    return {k: v[0] for k, v in carried.items()}


def _held(p, comp):
    held = p.get(comp, "Held")
    return _name(held.get_class()) if held else None


def _issued(carried):
    return _slots(carried) == dict(zip(STARTERS, STARTER_SLOTS))


def _others(p):
    mine = p.pawn()
    found = unreal.GameplayStatics.get_all_actors_of_class(mine.get_world(), mine.get_class())
    return [a for a in found if a != mine]


def probe_server(p):
    comps = [_comp(p, pc.get_controlled_pawn()) for pc in p.players()]
    yield _await(lambda: all(len(_record(p, c)) == len(STARTERS) for c in comps))
    start = [_carried(p, c) for c in comps]
    p.check(f"the server issued each of the {p.clients} players the six items, in their "
            "slots", all(_issued(c) for c in start), f"{[_slots(c) for c in start]}")
    p.check("and wrote each down: the record's rows are the items' class, slot and rounds",
            all(_record(p, c) == s for c, s in zip(comps, start)),
            f"{[_record(p, c) for c in comps]}")
    p.check("with the class in hand, which everyone else is told (the shotgun)",
            all(_name(p.get(c, HandClass)) == "Shotgun" for c in comps),
            f"{[_name(p.get(c, HandClass)) for c in comps]}")
    p.post("ready")

    yield _await(lambda: p.posted("client 1", "moved"))
    yield 0.3
    now = [_carried(p, c) for c in comps]
    moved = [i for i, c in enumerate(now) if c.get("Axe", (None,))[0] == AXE_TO]
    p.check(f"client 1's move is the server's: one character's axe is in slot {AXE_TO}, "
            "and its record says so", len(moved) == 1
            and _record(p, comps[moved[0]]) == now[moved[0]],
            f"{[_slots(c).get('Axe') for c in now]}")
    p.check("and nobody else's inventory changed",
            all(c == s for i, (c, s) in enumerate(zip(now, start)) if i not in moved),
            f"{len(now) - len(moved)} other(s)")
    if not moved:
        return
    one = comps[moved[0]]

    yield _await(lambda: p.posted("client 1", "held"))
    yield 0.3
    got = _carried(p, one)
    p.check("client 1's slot request is the server's: the pistol in hand, the shotgun "
            "home in the primary slot, HandClass the pistol",
            _held(p, one) == "Pistol" and got["Pistol"][0] == HAND
            and got["Shotgun"][0] == PRIMARY and _name(p.get(one, HandClass)) == "Pistol",
            f"held {_held(p, one)}, {_slots(got)}")

    yield _await(lambda: p.posted("client 1", "asked the refused"))
    yield 0.6
    after = _carried(p, one)
    p.check("the server refuses a move no rule allows (the matches into the primary "
            "slot): nothing moved", after == got, f"{_slots(after)}")
    p.post("refused")


def probe_client(p):
    own = _comp(p, p.pawn())
    yield _await(lambda: len(_carried(p, own)) == len(STARTERS)
                 and len(_others(p)) >= p.clients - 1)
    yield 0.5
    start = _carried(p, own)
    p.check("this client's character carries the six issued items in their slots, made "
            "from the record it was sent", _issued(start) and _record(p, own) == start,
            f"{_slots(start)}; record {_slots(_record(p, own))}")
    p.check("and holds the shotgun", _held(p, own) == "Shotgun", str(_held(p, own)))
    theirs = [_comp(p, a) for a in _others(p)]
    yield _await(lambda: all(_held(p, c) for c in theirs), 5.0)
    p.check("another player's character here carries one item, the one in its hand, "
            "and none of its record", len(theirs) == p.clients - 1
            and all(_slots(_carried(p, c)) == {"Shotgun": HAND} and _record(p, c) == {}
                    for c in theirs), f"{[_slots(_carried(p, c)) for c in theirs]}")

    if p.client != 1:
        yield _await(lambda: p.posted("client 1", "held"))
        yield _await(lambda: any(_held(p, c) == "Pistol" for c in theirs), 5.0)
        p.check("client 1 brought its pistol to hand, and this client sees it there",
                sorted(_held(p, c) for c in theirs)
                == sorted(["Pistol"] + ["Shotgun"] * (p.clients - 2)),
                f"{[_held(p, c) for c in theirs]}")
        p.check("its own inventory untouched", _carried(p, own) == start,
                f"{_slots(_carried(p, own))}")
        return

    yield _await(lambda: p.posted("server", "ready"))
    yield from _asks(p, own, start)
    p.post("asked the refused")
    yield _await(lambda: p.posted("server", "refused"))
    yield 0.3
    got = _slots(_carried(p, own))
    p.check("the refused move moved nothing here either",
            got["Matches"] == MATCHES_SLOT and got["Shotgun"] == PRIMARY, f"{got}")


def _asks(p, own, start):
    """The move, the slot request and the move that is refused; posts each."""
    p.ask_move(own, AXE_FROM, AXE_TO)
    yield _await(lambda: _slots(_carried(p, own)).get("Axe") == AXE_TO, 5.0)
    got = _carried(p, own)
    p.check(f"{AC.ASK_MOVE}({AXE_FROM}, {AXE_TO}) moves the axe to that bag slot, and "
            "nothing else", _slots(got) == {**_slots(start), "Axe": AXE_TO}
            and _record(p, own) == got, f"{_slots(got)}")
    p.post("moved")

    p.ask_slot(own, PISTOL_SLOT)
    yield _await(lambda: _held(p, own) == "Pistol", 5.0)
    got = _carried(p, own)
    p.check(f"{AC.ASK_SLOT}({PISTOL_SLOT}) brings the pistol to hand, the shotgun going "
            "home to the primary slot", _held(p, own) == "Pistol"
            and got["Pistol"][0] == HAND and got["Shotgun"][0] == STARTER_HAND_FROM,
            f"held {_held(p, own)}, {_slots(got)}")
    p.check("the rounds came with them (the record's Loaded and Reserve)",
            all(got[k][1:] == start[k][1:] for k in start), f"{got}")
    p.post("held")

    p.ask_move(own, MATCHES_SLOT, PRIMARY)


def probe(p):
    """Single player: the same asks, served by the one machine."""
    own = _comp(p, p.pawn())
    yield _await(lambda: len(_record(p, own)) == len(STARTERS))
    start = _carried(p, own)
    p.check("standalone: the six issued items in their slots, and the record written "
            "from them", _issued(start) and _record(p, own) == start,
            f"{_slots(start)}; record {_slots(_record(p, own))}")
    yield from _asks(p, own, start)
    yield 0.5
    got = _slots(_carried(p, own))
    p.check("the move no rule allows (the matches into the primary slot) is refused",
            got["Matches"] == MATCHES_SLOT and got["Shotgun"] == PRIMARY, f"{got}")
    p.check("and the record is still the items", _record(p, own) == _carried(p, own),
            f"{_slots(_record(p, own))}")
