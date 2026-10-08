"""The world's fires are the server's (task M25): the chop, the campfire, the
lit stick, the hot blade and the cauterised bleed happen once, on the server,
and everyone sees them.

    server     stands client 1 at a tree and client 2 behind it, and judges
               each step client 1 posts
    client 1   presses the use key on the stick with no fire near: the
               server's stick stays a stick
    client 1   swings the axe at the trunk CHOPS_PER_WOOD times: the server
               leaves one piece of wood, which both clients see lying there;
               E takes it into the server's bag
    client 1   strikes the matches: the server spends ITS wood and spawns one
               campfire, which client 2 sees where the server put it; the
               server's Temperature of both players rises beside it
    client 1   presses the use key on the stick: the server's stick is Lit,
               client 1's picture of it burns (the record), and so does
               client 2's copy of client 1's hand (HandLit)
    server     wounds client 1, and calls Server_Cauterize as a client with a
               cold blade would: the bleed stays
    client 1   presses E on the fire with the knife in hand: the server's
               knife is Hot, client 1's picture glows, and client 2's copy
    client 1   presses the use key: the server's bleed is gone
    client 1   sets the burning stick down: client 2 sees it lying there,
               still burning (the item's own Lit, replicated)

KnifeQueued, FireForced, SightsForced and InteractForced stand in for the
keys. The fire's rate is raised and the night's cold switched off for the
run, as probes/probe_campfire.py does. Single player's checks are
probe_campfire.py, probe_chop_tree.py, probe_lit_stick.py and
probe_hot_blade.py, through the same events.
"""

import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.chop_tuning import CHOP_COUNT_VAR, CHOPS_PER_WOOD
from combat.fire_vars import SERVER_CAUTERIZE
from combat.heat_tuning import COOL_VAR, HOT_VAR
from combat.light_tuning import CAMPFIRE_AHEAD_CM
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, ITEM_BP_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH)
from combat.record_vars import DropForced, SlotForced
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.slot_tuning import HAND
from combat.torch_tuning import BURN_OUT_VAR, LIT_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.knife import KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_chop_tree import CLEAR_CM, _flat, _items, _stand, _trees
from probes.probe_hot_blade import _bleeds, _wanderers, _wound
from survival import component_vars as UV
from survival.campfire import WARM_RATE_VAR
from survival.paths import (
    CAMPFIRE_BP_PATH, CAMPFIRE_CLASS_PATH, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH)
from survival.tuning import CAMPFIRE_WARM_RADIUS_CM
from world.day_night_blueprint import NIGHT_COLD_VAR
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH

RUNS_ON = ("server", "client")
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (KNIFE_QUEUED_VAR, FIRE_FORCED_VAR, SIGHTS_FORCED_VAR, INTERACT_FORCED_VAR,
              SlotForced, DropForced, WV.EquippedIndex)]
            + [(ITEM_BP_PATH, v) for v in (COOL_VAR, BURN_OUT_VAR)]
            + [(HEALTH_BP_PATH, HV.Health), (SURVIVAL_BP_PATH, UV.Temperature),
               (CAMPFIRE_BP_PATH, WARM_RATE_VAR), (DAY_NIGHT_BP_PATH, NIGHT_COLD_VAR)])

WAIT = 30.0
SPARE_HEALTH = 100000.0
RATE = 20.0               # the fire's, for the run: 1 a second does not show
COOL = 50.0               # a Temperature with room to rise
WATCH = 0.5
BEHIND_CM = 150.0         # client 2, behind client 1: inside the fire's radius
SEEN_CM = 60.0            # how far a client's copy may stand from the server's
AXE, KNIFE, STICK, MATCHES, WOOD = (
    "BP_Axe_C", "BP_Knife_C", "BP_Stick_C", "BP_Matches_C", "BP_Wood_C")


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    return lambda: ready() or time.time() > until


def _vec(v):
    return [v.x, v.y, v.z]


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _name(item):
    return item.get_class().get_name() if item is not None else None


def _players(p):
    cls = p.load_class(HEALTH_CLASS_PATH)
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), unreal.Character)
        if a.get_component_by_class(cls)
        and not p.get(a.get_component_by_class(cls), HV.DespawnOnDeath)]


def _nearest(actors, point):
    at = unreal.Vector(*point)
    return min(actors, key=lambda a: (a.get_actor_location() - at).length(), default=None)


def _bag(p, wc):
    return [_name(i) for i in p.get(wc, "Inventory")]


def _fires(p):
    return list(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(CAMPFIRE_CLASS_PATH)))


def _lying(p, name):
    """The items of a class this machine shows lying in the world."""
    return [a for a in _items(p, name)
            if p.get(a, IV.Dropped) and not a.get_editor_property("hidden")]


def _told(p, key, who="client 1", seconds=90.0):
    """Wait for a post; False (and a failed check) with none."""
    yield _await(lambda: p.posted(who, key), seconds)
    if not p.posted(who, key):
        p.check(f"{p.where} heard '{key}' from {who}", False, "no post")
        return False
    return True


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield _await(lambda: p.posted("client 1", "pos") and p.posted("client 2", "pos"))
    if not (p.posted("client 1", "pos") and p.posted("client 2", "pos")):
        p.check("both clients said where they stand", False, "no post")
        return
    players = _players(p)
    one = _nearest(players, p.posted("client 1", "pos"))
    two = _nearest(players, p.posted("client 2", "pos"))
    wc = p.component(one, WEAPON_COMP_CLASS_PATH)
    for body in players:
        p.set(p.component(body, HEALTH_CLASS_PATH), HV.Health, SPARE_HEALTH)
    for ctrl in _wanderers(p):
        pawn = ctrl.get_controlled_pawn()
        if pawn:
            pawn.destroy_actor()
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    if cycle is not None:
        p.set(cycle, NIGHT_COLD_VAR, 0.0)

    def held(name):
        return next((i for i in p.get(wc, "Inventory") if _name(i) == name), None)

    # --- the tree -----------------------------------------------------------------
    lying = [a.get_actor_location() for a in _items(p) if p.get(a, IV.Dropped)]
    here = one.get_actor_location()
    spot = None
    for _comp, _index, base in sorted(_trees(p), key=lambda t: (t[2] - here).length())[:60]:
        if any(_flat(at - base) < CLEAR_CM for at in lying):
            continue
        spot = _stand(p, one, base)
        if spot:
            break
    p.check("the server found a trunk to stand client 1 at", spot is not None)
    if spot is None:
        return
    at, yaw = spot[0], spot[1]
    turn = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    ahead = unreal.MathLibrary.get_forward_vector(turn)
    one.set_actor_location_and_rotation(at, turn, False, True)
    two.set_actor_location_and_rotation(at - ahead * BEHIND_CM, turn, False, True)
    p.post("stand", [_vec(at), yaw])

    # --- a stick with no fire near ---------------------------------------------------
    if not (yield from _told(p, "use cold")):
        return
    yield 0.3
    stick = held(STICK)
    p.check("client 1's use key on the stick with no campfire near: the server's "
            "stick is in its hand and stays a stick",
            _name(p.get(wc, "Held")) == STICK and not p.get(stick, LIT_VAR) and not _fires(p),
            f"{_name(p.get(wc, 'Held'))} in hand, Lit {p.get(stick, LIT_VAR)}")
    p.post("chop")

    # --- the chop --------------------------------------------------------------------
    if not (yield from _told(p, "chopped")):
        return
    yield _await(lambda: len(_lying(p, WOOD)) == 1, 5.0)
    wood = _lying(p, WOOD)
    p.check(f"client 1's {CHOPS_PER_WOOD} blows of the axe leave one piece of wood on the "
            "server, the world's (InWorld), and the count starts over",
            len(wood) == 1 and bool(p.get(wood[0], IV.InWorld))
            and p.get(wc, CHOP_COUNT_VAR) == 0,
            f"{len(wood)} lying, ChopCount {p.get(wc, CHOP_COUNT_VAR)}")
    if len(wood) != 1:
        return
    p.post("wood", _vec(wood[0].get_actor_location()))
    if not (yield from _told(p, "took")):
        return
    p.check("client 1's E takes it into the server's bag",
            _bag(p, wc).count(WOOD) == 1 and not _lying(p, WOOD), str(_bag(p, wc)))
    p.post("light")

    # --- the campfire ----------------------------------------------------------------
    if not (yield from _told(p, "struck")):
        return
    yield _await(lambda: len(_fires(p)) >= 1, 5.0)
    fires = _fires(p)
    p.check("client 1's strike of the matches lights one campfire on the server, and "
            "spends the server's wood", len(fires) == 1 and WOOD not in _bag(p, wc),
            f"{len(fires)} fire(s), bag {_bag(p, wc)}")
    if len(fires) != 1:
        return
    fire = fires[0]
    off = _flat(fire.get_actor_location() - (one.get_actor_location() + ahead * CAMPFIRE_AHEAD_CM))
    p.check(f"...{CAMPFIRE_AHEAD_CM:.0f} cm in front of the server's copy of client 1",
            off < 30.0, f"{off:.0f} cm off")
    p.check("...a replicated actor", bool(fire.get_editor_property("replicates")))
    p.set(fire, WARM_RATE_VAR, RATE)
    p.post("fire", _vec(fire.get_actor_location()))
    yield _await(lambda: p.posted("client 1", "saw fire") and p.posted("client 2", "saw fire"))

    # --- and its warmth: the server's Temperature of both players ----------------------
    gaps, gained = {}, {}
    survivals = {"client 1": p.component(one, SURVIVAL_CLASS_PATH),
                 "client 2": p.component(two, SURVIVAL_CLASS_PATH)}
    for who, body in (("client 1", one), ("client 2", two)):
        gaps[who] = (body.get_actor_location() - fire.get_actor_location()).length()
        p.set(survivals[who], UV.Temperature, COOL)
    t0 = _now(p)
    yield WATCH
    dt = _now(p) - t0
    for who, survival in survivals.items():
        gained[who] = p.get(survival, UV.Temperature) - COOL
    p.check("client 2 stands within the fire client 1 lit and warms at it: the "
            "server's Temperature of client 2 rises at the fire's rate",
            gaps["client 2"] < CAMPFIRE_WARM_RADIUS_CM and dt > 0.0
            and abs(gained["client 2"] - RATE * dt) <= 0.3 * RATE * dt + 1e-3,
            f"{gaps['client 2']:.0f} cm away: +{gained['client 2']:.3f} in {dt:.3f} s, "
            f"{RATE:g} a second wants {RATE * dt:.3f}")
    p.check("...and so does client 1's",
            abs(gained["client 1"] - RATE * dt) <= 0.3 * RATE * dt + 1e-3,
            f"{gaps['client 1']:.0f} cm away: +{gained['client 1']:.3f}")
    p.post("warmed")

    # --- the stick, lit -----------------------------------------------------------------
    if not (yield from _told(p, "use lit")):
        return
    stick = held(STICK)
    yield _await(lambda: bool(p.get(stick, LIT_VAR)), 5.0)
    p.check("client 1's use key on the stick beside the fire: the server's stick is "
            "Lit, on the server's clock",
            bool(p.get(stick, LIT_VAR)) and p.get(stick, BURN_OUT_VAR) > _now(p),
            f"Lit {p.get(stick, LIT_VAR)}, {p.get(stick, BURN_OUT_VAR) - _now(p):.0f} s left")
    p.set(stick, BURN_OUT_VAR, _now(p) + 600.0)   # past the end of the run
    p.post("stick lit")
    yield _await(lambda: p.posted("client 1", "saw lit") and p.posted("client 2", "saw lit"))

    # --- a bleed, and a blade that is not hot ------------------------------------------
    asc = unreal.AbilitySystemLibrary.get_ability_system_component(one)
    _wound(p, asc)
    yield 0.2
    wc.call_method(SERVER_CAUTERIZE)
    yield 0.2
    p.check("Server_Cauterize with no hot blade in the server's hand seals nothing: "
            "the server reads its own item", _bleeds(p, asc) == (1, 1), str(_bleeds(p, asc)))
    p.post("bleeding")

    # --- the knife, heated ---------------------------------------------------------------
    if not (yield from _told(p, "heat")):
        return
    knife = held(KNIFE)
    yield _await(lambda: bool(p.get(knife, HOT_VAR)), 5.0)
    p.check("client 1's E on the fire with the knife in hand: the server's knife is "
            "Hot, on the server's clock",
            _name(p.get(wc, "Held")) == KNIFE and bool(p.get(knife, HOT_VAR))
            and p.get(knife, COOL_VAR) > _now(p),
            f"{_name(p.get(wc, 'Held'))} in hand, Hot {p.get(knife, HOT_VAR)}")
    p.set(knife, COOL_VAR, _now(p) + 600.0)
    p.post("knife hot")
    yield _await(lambda: p.posted("client 1", "saw hot") and p.posted("client 2", "saw hot"))
    p.post("seal")

    # --- the cauterised bleed -------------------------------------------------------------
    if not (yield from _told(p, "sealed")):
        return
    yield _await(lambda: _bleeds(p, asc) == (0, 0), 5.0)
    p.check("client 1's use key on the hot knife: the bleed is off the server's "
            "ability system", _bleeds(p, asc) == (0, 0), str(_bleeds(p, asc)))
    p.post("drop")

    # --- the burning stick, set down --------------------------------------------------------
    if not (yield from _told(p, "dropped")):
        return
    yield _await(lambda: len(_lying(p, STICK)) == 1, 5.0)
    down = _lying(p, STICK)
    p.check("the burning stick client 1 sets down lies on the server, still burning",
            len(down) == 1 and bool(p.get(down[0], LIT_VAR)) and bool(p.get(down[0], IV.InWorld)),
            f"{len(down)} lying")
    p.post("stick down", _vec(down[0].get_actor_location()) if down else [0.0, 0.0, 0.0])
    yield _await(lambda: p.posted("client 2", "saw stick"), 30.0)
    p.post("judged")


# ─── the clients ─────────────────────────────────────────────────────────────

def _hold(p, wc, name):
    bag = _bag(p, wc)
    if name in bag:
        p.hold(wc, bag.index(name))
    yield _await(lambda: _name(p.get(wc, "Held")) == name, 10.0)
    yield 0.3


def _press(p, wc, var, seconds=0.2):
    p.set(wc, var, True)
    yield seconds
    p.set(wc, var, False)
    yield 0.1


def _sees(p, actors, spot):
    """Wait for one of ``actors()`` within SEEN_CM of ``spot``; how far the
    nearest is, or None with none."""
    at = unreal.Vector(*spot)
    gap = lambda: min(((a.get_actor_location() - at).length() for a in actors()),
                      default=None)
    yield _await(lambda: gap() is not None and gap() < SEEN_CM, 10.0)
    return gap()


def probe_client(p):
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    yield 0.5
    p.post("pos", _vec(mine.get_actor_location()))
    if not (yield from _told(p, "stand", "server", 60.0)):
        return
    if p.client == 1:
        yield from _client_one(p, mine, wc)
    else:
        yield from _client_two(p, mine)
    yield _await(lambda: p.posted("server", "judged"), 60.0)


def _client_two(p, mine):
    """The onlooker: what client 1 did, as this machine is told it."""
    def theirs():
        others = [a for a in _players(p) if a != mine]
        return p.component(others[0], WEAPON_COMP_CLASS_PATH) if others else None

    def in_hand():
        wc = theirs()
        return p.get(wc, "Held") if wc is not None else None

    if not (yield from _told(p, "wood", "server", 120.0)):
        return
    gap = yield from _sees(p, lambda: _lying(p, WOOD), p.posted("server", "wood"))
    p.check("client 2 sees the wood client 1 cut, where the server left it",
            gap is not None and gap < SEEN_CM, f"{gap} cm off")

    if not (yield from _told(p, "fire", "server", 120.0)):
        return
    gap = yield from _sees(p, lambda: _fires(p), p.posted("server", "fire"))
    p.check("client 2 sees client 1's campfire, where the server lit it",
            gap is not None and gap < SEEN_CM and len(_fires(p)) == 1,
            f"{gap} cm off, {len(_fires(p))} fire(s)")
    p.check("...and no wood lying: client 1 took it", not _lying(p, WOOD),
            str(len(_lying(p, WOOD))))
    p.post("saw fire")

    if not (yield from _told(p, "stick lit", "server", 120.0)):
        return
    yield _await(lambda: _name(in_hand()) == STICK and bool(p.get(in_hand(), LIT_VAR)), 10.0)
    p.check("client 2's copy of client 1 holds a burning stick (HandLit)",
            _name(in_hand()) == STICK and bool(p.get(in_hand(), LIT_VAR)),
            f"{_name(in_hand())} in hand")
    p.post("saw lit")

    if not (yield from _told(p, "knife hot", "server", 120.0)):
        return
    yield _await(lambda: _name(in_hand()) == KNIFE and bool(p.get(in_hand(), HOT_VAR)), 10.0)
    p.check("client 2's copy of client 1 holds a hot knife (HandHot)",
            _name(in_hand()) == KNIFE and bool(p.get(in_hand(), HOT_VAR)),
            f"{_name(in_hand())} in hand")
    p.post("saw hot")

    if not (yield from _told(p, "stick down", "server", 120.0)):
        return
    burning = lambda: [a for a in _lying(p, STICK) if p.get(a, LIT_VAR)]
    gap = yield from _sees(p, burning, p.posted("server", "stick down"))
    p.check("client 2 sees the stick client 1 set down, still burning: the item's "
            "own Lit replicates", gap is not None and gap < SEEN_CM, f"{gap} cm off")
    p.post("saw stick")


def _client_one(p, mine, wc):
    """The player who does it all, by the keys' stand-ins."""
    at, yaw = p.posted("server", "stand")
    at = unreal.Vector(*at)
    turn = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    yield _await(lambda: (mine.get_actor_location() - at).length() < 100.0, 10.0)
    p.controller().set_control_rotation(turn)
    yield 0.5

    # --- the stick, with no fire near ---
    yield from _hold(p, wc, STICK)
    yield from _press(p, wc, SIGHTS_FORCED_VAR)
    yield 0.3
    p.check("client 1's stick is not lit with no campfire near",
            _name(p.get(wc, "Held")) == STICK and not p.get(p.get(wc, "Held"), LIT_VAR),
            _name(p.get(wc, "Held")))
    p.post("use cold")

    # --- the chop ---
    if not (yield from _told(p, "chop", "server")):
        return
    yield from _hold(p, wc, AXE)
    p.controller().set_control_rotation(turn)
    for _ in range(CHOPS_PER_WOOD):
        yield _await(lambda: _now(p) >= p.get(wc, NEXT_KNIFE_VAR), 5.0)
        p.set(wc, KNIFE_QUEUED_VAR, True)
        yield _await(lambda: not p.get(wc, KNIFE_QUEUED_VAR), 5.0)
        yield 0.6
    p.post("chopped")
    if not (yield from _told(p, "wood", "server")):
        return
    gap = yield from _sees(p, lambda: _lying(p, WOOD), p.posted("server", "wood"))
    p.check("client 1 sees the wood it cut, where the server left it",
            gap is not None and gap < SEEN_CM, f"{gap} cm off")
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield _await(lambda: WOOD in _bag(p, wc), 10.0)
    p.check("...and E takes it: the wood is in client 1's bag, by the record",
            _bag(p, wc).count(WOOD) == 1, str(_bag(p, wc)))
    p.post("took")

    # --- the campfire ---
    if not (yield from _told(p, "light", "server")):
        return
    yield from _hold(p, wc, MATCHES)
    yield from _press(p, wc, FIRE_FORCED_VAR, 0.1)
    yield _await(lambda: WOOD not in _bag(p, wc), 10.0)
    p.check("client 1 strikes the matches: the wood is out of its bag, by the "
            "record, and the matches stay in hand",
            WOOD not in _bag(p, wc) and _name(p.get(wc, "Held")) == MATCHES,
            f"{_bag(p, wc)}, {_name(p.get(wc, 'Held'))} in hand")
    p.post("struck")
    if not (yield from _told(p, "fire", "server")):
        return
    gap = yield from _sees(p, lambda: _fires(p), p.posted("server", "fire"))
    p.check("client 1 sees its campfire, where the server lit it",
            gap is not None and gap < SEEN_CM and len(_fires(p)) == 1,
            f"{gap} cm off, {len(_fires(p))} fire(s)")
    p.post("saw fire")

    # --- the stick, lit ---
    if not (yield from _told(p, "warmed", "server")):
        return
    yield from _hold(p, wc, STICK)
    yield from _press(p, wc, SIGHTS_FORCED_VAR)
    p.post("use lit")
    yield _await(lambda: bool(p.get(p.get(wc, "Held"), LIT_VAR)), 10.0)
    p.check("client 1's own stick burns: its picture is told by its row of the record (lit)",
            _name(p.get(wc, "Held")) == STICK and bool(p.get(p.get(wc, "Held"), LIT_VAR)),
            _name(p.get(wc, "Held")))
    if not (yield from _told(p, "stick lit", "server")):
        return
    p.post("saw lit")

    # --- the knife, heated, and the bleed ---
    if not (yield from _told(p, "bleeding", "server")):
        return
    yield from _hold(p, wc, KNIFE)
    p.set(wc, INTERACT_FORCED_VAR, True)
    p.post("heat")
    yield _await(lambda: bool(p.get(p.get(wc, "Held"), HOT_VAR)), 10.0)
    p.check("client 1's own knife glows: its picture is told by its row of the record (hot)",
            _name(p.get(wc, "Held")) == KNIFE and bool(p.get(p.get(wc, "Held"), HOT_VAR)),
            _name(p.get(wc, "Held")))
    if not (yield from _told(p, "knife hot", "server")):
        return
    p.post("saw hot")
    if not (yield from _told(p, "seal", "server")):
        return
    yield from _press(p, wc, SIGHTS_FORCED_VAR)
    p.post("sealed")

    # --- the burning stick, set down ---
    if not (yield from _told(p, "drop", "server")):
        return
    yield from _hold(p, wc, STICK)
    p.ask_drop(wc, HAND)
    yield _await(lambda: STICK not in _bag(p, wc), 10.0)
    p.check("client 1 sets the burning stick down: it is out of its bag",
            STICK not in _bag(p, wc), str(_bag(p, wc)))
    p.post("dropped")
