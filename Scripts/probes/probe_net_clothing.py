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
    client 2    sees it (K5): the record is the owner's alone, but the classes
                worn go to everyone else beside HandClass (WornClasses), and
                its copy of client 1's character is drawn by them
                (view_worn.py, wear_draw.py). With the jacket worn that copy's
                Torso has the hoodie, shown and on the body's bones; taken
                off, Torso is bare and hidden. It wears nothing itself
    the server  draws no one: its copy's garment components stay bare

    ... --net --clients 2 --title --probe Scripts/probes/probe_net_clothing.py

On the title each client joins when its probe does: client 1 at once, and
client 2 LATE, once the jacket is worn. The late joiner sees the hoodie on
client 1 as soon as it sees client 1, and then sees it taken off.

Single player (`--game`) does the same on the one machine: the asks are plain
calls there.

A client's asks go through FireForced, WearForced, TakeOffForced and
DropForced, which the component's Tick turns into the Server events where the
keys are read: a Blueprint Server event called from Python is not sent.
"""

SYSTEMS = ('net', 'clothing')

import os
import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.ask_consts import ASK_DROP, ASK_TAKE_OFF, ASK_WEAR
from asset_pipeline.metahuman_paths import CLOTHING
from combat.metahuman_body import BODY
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.record_vars import FORCED
from combat.slot_tuning import BAG_FIRST, BAG_LAST, SLOT_COUNT, SLOT_VAR, UNPLACED
from combat.strike_vars import SERVER_TAKE
from combat.wear_tuning import SERVER_WEAR, WEAR_SLOTS, WORN_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_chop_tree import _items
from probes.probe_clothing_draw import BARE, FOLLOW_CM, TORSO, _gap, _skeletal, bare, dress
from probes.probe_hot_blade import _wanderers
from probes.probe_net_late_join import JOIN_S, SPARE_HEALTH

RUNS_ON = ("server", "client", "standalone")
WRITABLE = ([(WEAPON_COMP_BP_PATH, str(v)) for v in FORCED + (FIRE_FORCED_VAR,)]
            + [(HEALTH_BP_PATH, HV.Health)])
WAIT = 20.0
# uepy.py --title: client 2 joins late (see the docstring).
TITLE = bool(os.environ.get("UEPY_TITLE"))
HOODIE = (CLOTHING[TORSO], True)
# Client 1 does nothing more after a step until client 2 has looked at what
# the step named here left ({client 1's step: client 2's look}). On the title
# client 2 joins with the jacket on, and client 1 keeps it on until it looked.
HOLD = ({"refused": "drag", "off": "off"} if TITLE
        else {"key": "key", "drag": "drag", "off": "off"})
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
    body = wc.get_owner()
    p.check("...and drawn on its own body: Torso has the hoodie and shows",
            dress(body)[TORSO] == HOODIE, str(dress(body)))

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
    p.check("...and Torso is bare and hidden again", bare(body), str(dress(body)))

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
    # The level's wanderers would kill client 1 within seconds of its join,
    # long before the late joiner has looked; a destroyed one is replaced
    # 10 s on, which it must outlive too.
    yield from _await(lambda: p.players() and p.players()[0].get_controlled_pawn(), 30.0)
    for c in p.players():
        if c.get_controlled_pawn():
            p.set(p.component(c.get_controlled_pawn(), HEALTH_CLASS_PATH), HV.Health,
                  SPARE_HEALTH)
    for ctrl in _wanderers(p):
        if ctrl.get_controlled_pawn():
            ctrl.get_controlled_pawn().destroy_actor()
    yield from _await(lambda: p.posted("client 1", "id") is not None, JOIN_S + 60.0)
    players = lambda: {c.player_state.player_id: c.get_controlled_pawn()
                       for c in p.players() if c.player_state}
    # On the title the server's probe starts with the first controller.
    yield from _await(lambda: players().get(p.posted("client 1", "id")))
    by_id = players()
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
        yield from _await(lambda: p.posted("client 1", step) is not None, 200.0)
        yield 0.3
        got = _worn(p, wc)
        p.check(f"after client 1's '{step}' the server's copy wears {WANT[step] or 'nothing'}"
                ", its item actors and its record alike",
                got == _want(step) and _worn_record(p, wc) == got,
                f"worn {got}, record {_worn_record(p, wc)}")
        p.check("...and the dedicated server draws none of it: its copy's garment "
                "components are bare", bare(pawn), str(dress(pawn)))
        p.post(f"worn-{step}", got)
    p.check("nobody else wears anything",
            all(_worn(p, c) == NOTHING and _worn_record(p, c) == NOTHING for c in others),
            f"{len(others)} other(s)")
    hats = [a for a in _items(p, "BP_Hat_C") if p.get(a, IV.Dropped)]
    p.check("the dropped hat is the server's actor, lying in the world, replicated",
            len(hats) == 1 and bool(p.get(hats[0], IV.InWorld)),
            f"{len(hats)} hat(s)")
    p.post("done")
    yield from _await(lambda: p.posted("client 2", "judged") is not None, 60.0)


# ─── a client ────────────────────────────────────────────────────────────────

def _on_server(p):
    """This client's pawn is one a server gave it. Not the late-join probe's
    test: while the join is pending the title's world already says it is no
    longer standalone, with the title's pawn still in it."""
    pawn = p.pawn()
    return bool(pawn) and not pawn.has_authority()


def _join(p):
    """Leave the title for the server. p.world() finds a world by its path,
    and the title's has the server's path: it is collected here, or it is
    found for as long as a minute after the travel."""
    unreal.GameplayStatics.set_game_paused(p.world(), False)
    unreal.GameplayStatics.open_level(p.world(), p.net.address, True, "")
    tried = [time.time()]

    def joined():
        try:
            if _on_server(p):
                return True
        except Exception:       # a world or a pawn mid-travel
            pass
        if time.time() - tried[0] > 2.0:
            tried[0] = time.time()
            unreal.SystemLibrary.collect_garbage()
        return False
    yield from _await(joined, JOIN_S)
    p.check(f"{p.where} joined the server from the title", _on_server(p))
    return _on_server(p)


def _theirs(p):
    """The other players' characters on this machine."""
    mine = p.pawn()
    if not mine:
        return []
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), mine.get_class())
            if a != mine]


def _sees(p, step, label):
    """Client 2, once the server has said ``step`` is done: its copy of client
    1's character wears what the server's does, by the classes it was sent.
    Returns that character."""
    yield from _await(lambda: p.posted("server", f"worn-{step}") is not None, 90.0)
    want = _want(step)
    yield from _await(lambda: len(_theirs(p)) == 1 and _worn(p, _wc(p, _theirs(p)[0])) == want)
    yield 0.5
    theirs = _theirs(p)
    got = [_worn(p, _wc(p, a)) for a in theirs]
    p.check(f"client 2, after '{step}': {label}", len(theirs) == 1 and got == [want],
            f"{got}")
    return theirs[0] if theirs else None


def _client_two(p):
    mine = p.pawn()
    wc = _wc(p, mine)
    if not TITLE:
        yield from _sees(p, "key", "its copy of client 1's character wears the hat, "
                         "which draws nothing")
        p.check("...and nothing is drawn on it yet", all(bare(a) for a in _theirs(p)),
                str([dress(a) for a in _theirs(p)]))
        p.post("saw-key")
    one = yield from _sees(p, "drag", "its copy of client 1's character wears the hat "
                           "and the jacket" + (", joined after both were worn" if TITLE else ""))
    if not one:
        return
    yield from _await(lambda: dress(one)[TORSO] == HOODIE, 8.0)
    seen = dress(one)
    p.check("...and client 2 sees the hoodie on client 1's Torso, shown, Legs and Feet bare",
            seen == {**{n: BARE for n in CLOTHING}, TORSO: HOODIE}, str(seen))
    torso, body = _skeletal(one, TORSO), _skeletal(one, BODY)
    yield 0.5
    gap = _gap(torso, body) if torso and body else -1.0
    p.check(f"...on the body's bones: its spine and its forearm within {FOLLOW_CM:.0f} cm",
            0.0 <= gap < FOLLOW_CM, f"{gap:.2f} cm")
    p.check("...and the record itself is still the owner's alone",
            _worn_record(p, _wc(p, one)) == NOTHING, str(_worn_record(p, _wc(p, one))))
    p.post("saw-drag")
    yield from _sees(p, "off", "the jacket is off its copy of client 1's character")
    yield from _await(lambda: bare(one), 8.0)
    p.check("...and client 2 sees the hoodie gone: Torso is bare and hidden", bare(one),
            str(dress(one)))
    p.post("saw-off")
    yield from _sees(p, "drop", "its copy of client 1's character wears nothing")
    p.check("client 2 wears nothing itself, and nothing is drawn on it",
            _worn(p, wc) == NOTHING and bare(mine), f"{_worn(p, wc)} {dress(mine)}")
    p.post("judged")
    yield from _await(lambda: p.posted("server", "done") is not None, 90.0)


def probe_client(p):
    if TITLE:
        if p.client != 1:
            # Wall time: game time stands still on the paused title.
            yield from _await(lambda: p.posted("server", "worn-drag") is not None, 150.0)
            if p.posted("server", "worn-drag") is None:
                p.check("the server said the jacket is worn", False, "no post")
                return
        if not (yield from _join(p)):
            return
    mine = p.pawn()
    wc = _wc(p, mine)
    yield from _await(lambda: p.get(wc, WV.Held) is not None
                      and p.player_state() is not None)
    if p.client != 1:
        yield from _client_two(p)
        return
    p.post("id", p.player_state().player_id)
    yield from _await(lambda: p.posted("server", "given") is not None, 60.0)
    yield from _await(lambda: {"Hat", "Jacket"} <= set(_bag(p, wc)), 8.0)
    p.check("client 1's bag holds the hat and the jacket the server gave it, and "
            "it wears nothing", {"Hat", "Jacket"} <= set(_bag(p, wc))
            and _worn(p, wc) == NOTHING, f"{_bag(p, wc)}")

    def said(step):
        p.post(step)
        yield from _await(lambda: p.posted("server", f"worn-{step}") is not None)
        if step in HOLD and p.clients > 1:
            yield from _await(lambda: p.posted("client 2", f"saw-{HOLD[step]}") is not None,
                              150.0)
        return p.posted("server", f"worn-{step}")

    yield from _steps(p, wc, said)
    p.check("its worn slots are a picture of the record it was sent, and it has "
            "authority over none of it", _worn_record(p, wc) == _worn(p, wc)
            and not mine.has_authority(), f"record {_worn_record(p, wc)}")


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
