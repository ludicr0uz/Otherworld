"""A late joiner's world is the server's (task A2): client 2 joins after
client 1 took the level's hat and lit a campfire, and sees no hat and the
fire.

    python3 Scripts/dev/uepy.py --net --title --clients 2 --probe-timeout 420 \\
        --probe Scripts/probes/probe_net_late_join.py

``--title``: each client starts alone on its level and joins when its probe
says (boot.py starts the server's probe with the first player). Client 1
joins at once; client 2 joins LATE_S after the server says the take and the
fire are done.

    server     with client 1's character: Server_Take of the level's hat (a
               level actor: destroyed, a fresh hat in the bag), stands it at a
               trunk; once client 1 has cut wood, Server_Take of it, the
               matches to hand, Server_Light: one campfire, replicated and
               dormant; posts "done"; once client 2 joins, stands it by the fire
    client 1   joins; faces the trunk when told, three swings of the axe
               (KnifeQueued, as probe_net_campfire.py: the server's own sweep
               needs the owner's facing); sees no hat and the fire
    client 2   waits LATE_S after "done", joins, is stood by the fire: no hat
               in its world (the engine told it of the destroyed level actor),
               one fire where the server put it, and client 1's character

The hat and the fire are what M23 and M25 proved for players who were there
(probe_net_take.py, probe_net_campfire.py); this is the one who was not.
"""

import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.chop_tuning import CHOPS_PER_WOOD
from combat.fire_vars import SERVER_LIGHT
from combat.paths import (
    CHARACTER_CLASS_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH)
from combat.record_vars import SlotForced
from combat.slot_tuning import SLOT_VAR, UNPLACED
from combat.strike_vars import SERVER_TAKE
from combat.weapon_component import vars as WV
from combat.weapon_component.knife import KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR
from probes.probe_campfire import MATCHES
from probes.probe_chop_tree import AXE, WOOD, _flat, _items, _stand, _trees
from probes.probe_hot_blade import _wanderers
from survival.paths import CAMPFIRE_CLASS_PATH

RUNS_ON = ("server", "client")
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in (KNIFE_QUEUED_VAR, SlotForced, WV.EquippedIndex)]
            + [(HEALTH_BP_PATH, HV.Health)])
SPARE_HEALTH = 100000.0   # a wanderer that comes back must not kill the player mid-probe

HAT = "BP_Hat_C"
LATE_S = 20.0          # how long after the take and the fire client 2 joins
JOIN_S = 90.0          # a join, wall seconds
WAIT = 20.0
NEAR_CM = 100.0        # the fire is where the server put it within this
BESIDE_CM = 300.0      # where client 2 is stood from the fire


def _await(ready, seconds=WAIT):
    until = time.time() + seconds

    def done():
        try:
            return ready() or time.time() > until
        except Exception:       # a world or a pawn mid-travel
            return time.time() > until
    yield done


def _vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _name(obj):
    return obj.get_class().get_name() if obj else None


def _bag(p, wc):
    return [_name(i) for i in p.get(wc, WV.Inventory)]


def _held(p, wc):
    return _name(p.get(wc, WV.Held))


def _to_hand(p, wc, name):
    """Ask for the carried item's slot (AskSlot takes the slot code, not the
    bag index); wait for it in hand."""
    item = next(i for i in p.get(wc, WV.Inventory) if _name(i) == name)
    p.ask_slot(wc, p.get(item, SLOT_VAR))
    yield from _await(lambda: _held(p, wc) == name, 8.0)


def _lying(p, name):
    return [a for a in _items(p, name) if p.get(a, IV.Dropped)]


def _in_world(p, name):
    """Actors of the class that are the level's or lie there: not a client's
    picture of a carried one (view.py), which is an actor of the class too."""
    return [a for a in _items(p, name) if _level_actor(a) or p.get(a, IV.Dropped)]


def _fires(p):
    return list(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(CAMPFIRE_CLASS_PATH)))


def _bodies(p):
    return list(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(CHARACTER_CLASS_PATH)))


def _level_actor(a):
    return bool(unreal.OtherworldNetLibrary.is_level_actor(a))


def _joined(p):
    world = p.world()
    return bool(world) and not unreal.SystemLibrary.is_standalone(world) and p.pawn() is not None


def _join(p):
    """Leave the title for the server; wait until this process is on it."""
    world = p.world()
    unreal.GameplayStatics.set_game_paused(world, False)
    unreal.GameplayStatics.open_level(world, p.net.address, True, "")
    yield from _await(_joined, JOIN_S)
    p.check(f"{p.where} joined the server from the title", _joined(p))
    return _joined(p)


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    # boot.py starts this once the first player has joined (--title).
    yield from _await(lambda: p.players() and p.players()[0].get_controlled_pawn(), 30.0)
    one = p.players()[0].get_controlled_pawn()
    wc = p.component(one, WEAPON_COMP_CLASS_PATH)
    # A destroyed wanderer is replaced 10 s on: the player must outlive one.
    p.set(p.component(one, HEALTH_CLASS_PATH), HV.Health, SPARE_HEALTH)
    for ctrl in _wanderers(p):
        pawn = ctrl.get_controlled_pawn()
        if pawn:
            pawn.destroy_actor()

    # --- the level's hat ----------------------------------------------------------
    hats = _lying(p, HAT)
    p.check("the level's hat lies in the server's world, a level actor",
            len(hats) == 1 and _level_actor(hats[0]), f"{len(hats)} lying")
    if len(hats) != 1:
        return
    hat_at = hats[0].get_actor_location()
    hats[0].set_actor_location(one.get_actor_location(), False, True)
    wc.call_method(SERVER_TAKE, (hats[0],))
    yield 0.5
    carried = [i for i in p.get(wc, WV.Inventory) if _name(i) == HAT]
    p.check(f"{SERVER_TAKE} of the level's hat: a fresh hat is in the bag, not the "
            "level's, and the level's actor is gone from the server's world",
            len(carried) == 1 and not _level_actor(carried[0]) and len(_items(p, HAT)) == 1,
            f"{len(carried)} carried, {len(_items(p, HAT))} in the world, "
            f"level actor {bool(carried) and _level_actor(carried[0])}")

    # --- a trunk, and the wood ------------------------------------------------------
    here = one.get_actor_location()
    spot = None
    for _comp, _index, base in sorted(_trees(p), key=lambda t: (t[2] - here).length())[:60]:
        spot = _stand(p, one, base)
        if spot:
            break
    p.check("the server found a trunk to stand client 1 at", spot is not None)
    if spot is None:
        return
    at, yaw = spot[0], spot[1]
    turn = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    one.set_actor_location_and_rotation(at, turn, False, True)
    p.post("stand", [_vec(at), yaw])
    # Three -nullrhi processes share the cores: the client's steps are slow.
    yield from _await(lambda: p.posted("client 1", "chopped"), 150.0)
    yield from _await(lambda: len(_lying(p, WOOD)) >= 1, 5.0)
    wood = _lying(p, WOOD)
    p.check(f"client 1's {CHOPS_PER_WOOD} blows of the axe at the trunk leave one piece "
            "of wood on the server", len(wood) == 1, f"{len(wood)} lying, {_held(p, wc)} in hand")
    if len(wood) != 1:
        return
    wood[0].set_actor_location(one.get_actor_location(), False, True)
    wc.call_method(SERVER_TAKE, (wood[0],))
    yield 0.5
    p.check("...taken into the bag", WOOD in _bag(p, wc), str(_bag(p, wc)))

    # --- the fire -----------------------------------------------------------------------
    yield from _to_hand(p, wc, MATCHES)
    wc.call_method(SERVER_LIGHT)
    yield from _await(lambda: len(_fires(p)) >= 1, 5.0)
    fires = _fires(p)
    dormant = (fires and fires[0].get_editor_property("net_dormancy")
               == unreal.NetDormancy.DORM_DORMANT_ALL)
    p.check(f"{SERVER_LIGHT} with the matches in hand lights one campfire: a replicated "
            "actor, dormant from its spawn",
            len(fires) == 1 and bool(fires[0].get_editor_property("replicates")) and dormant,
            f"{len(fires)} fire(s), dormant {dormant}")
    if len(fires) != 1:
        return
    fire_at = fires[0].get_actor_location()
    p.post("done", {"hat": _vec(hat_at), "fire": _vec(fire_at)})

    # --- the late joiner --------------------------------------------------------------------
    yield from _await(lambda: len(p.players()) >= 2 and p.players()[1].get_controlled_pawn(),
                      LATE_S + JOIN_S)
    p.check("client 2 joined after the take and the fire", len(p.players()) >= 2)
    if len(p.players()) < 2:
        return
    two = p.players()[1].get_controlled_pawn()
    p.set(p.component(two, HEALTH_CLASS_PATH), HV.Health, SPARE_HEALTH)
    two.set_actor_location(fire_at + unreal.Vector(BESIDE_CM, 0.0, 50.0), False, True)
    p.post("beside")
    yield from _await(lambda: p.posted("client 2", "judged"), 150.0)
    p.check("client 2 judged its world", bool(p.posted("client 2", "judged")))


# ─── the clients ─────────────────────────────────────────────────────────────

def _client_one(p):
    if not (yield from _join(p)):
        return
    yield from _await(lambda: p.posted("server", "stand"), 60.0)
    if not p.posted("server", "stand"):
        p.check("the server said where to stand", False, "no post")
        return
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    # The bag is the record's picture: its items have slots once it has arrived.
    settled = lambda: (p.get(wc, WV.Held) is not None and AXE in _bag(p, wc)
                       and all(p.get(i, SLOT_VAR) != UNPLACED for i in p.get(wc, WV.Inventory)))
    yield from _await(settled, 20.0)
    p.check("client 1's bag is the record's picture, every item in a slot", settled(),
            f"held {_held(p, wc)}, slots "
            f"{[(_name(i), p.get(i, SLOT_VAR)) for i in p.get(wc, WV.Inventory)]}")
    yield 0.5
    p.controller().set_control_rotation(
        unreal.Rotator(pitch=0.0, yaw=p.posted("server", "stand")[1], roll=0.0))
    p.hold(wc, _bag(p, wc).index(AXE))
    yield from _await(lambda: _held(p, wc) == AXE, 10.0)
    p.check("client 1 brought the axe to hand", _held(p, wc) == AXE,
            f"{_held(p, wc)} in hand, bag {_bag(p, wc)}")
    yield 0.3
    sent = 0
    for _ in range(CHOPS_PER_WOOD):
        yield from _await(lambda: _now(p) >= p.get(wc, NEXT_KNIFE_VAR), 5.0)
        p.set(wc, KNIFE_QUEUED_VAR, True)
        yield from _await(lambda: not p.get(wc, KNIFE_QUEUED_VAR), 5.0)
        sent += not p.get(wc, KNIFE_QUEUED_VAR)
        yield 0.6
    p.check(f"client 1's {CHOPS_PER_WOOD} queued swings were each sent",
            sent == CHOPS_PER_WOOD, f"{sent} sent")
    p.post("chopped")
    yield from _await(lambda: p.posted("server", "done"), 120.0)
    if not p.posted("server", "done"):
        p.check("the server did the take and the fire", False, "no post")
        return
    fire = unreal.Vector(*p.posted("server", "done")["fire"])
    yield from _await(lambda: not _in_world(p, HAT) and len(_fires(p)) == 1, 10.0)
    p.check("client 1, there for both: no hat lying in its world (the level's was "
            "destroyed; the one it carries is the record's picture), and the fire where "
            "the server put it",
            not _in_world(p, HAT) and len(_fires(p)) == 1
            and _flat(_fires(p)[0].get_actor_location() - fire) < NEAR_CM,
            f"{len(_in_world(p, HAT))} hat(s) in the world of {len(_items(p, HAT))}, "
            f"{len(_fires(p))} fire(s)")
    p.post("seen")
    yield from _await(lambda: p.posted("client 2", "judged"), LATE_S + JOIN_S + 60.0)


def _client_two(p):
    yield from _await(lambda: p.posted("server", "done"), 300.0)
    if not p.posted("server", "done"):
        p.check("the server did the take and the fire", False, "no post")
        return
    p.check("client 2 is still alone on its title while client 1 plays",
            unreal.SystemLibrary.is_standalone(p.world()))
    # Game time stands still on the paused title: the wait is wall time.
    yield from _await(lambda: False, LATE_S)
    if not (yield from _join(p)):
        return
    yield from _await(lambda: p.posted("server", "beside"), 30.0)
    fire = unreal.Vector(*p.posted("server", "done")["fire"])
    yield from _await(lambda: _flat(p.pawn().get_actor_location() - fire) < BESIDE_CM * 2, 10.0)
    yield from _await(lambda: len(_fires(p)) == 1 and len(_bodies(p)) >= 2, 10.0)
    hats = _items(p, HAT)
    p.check("the late joiner has no hat in its world at all: the engine told it of the "
            "destroyed level actor", not hats, f"{len(hats)} hat(s)")
    fires = _fires(p)
    p.check("...and one campfire, where the server put it",
            len(fires) == 1 and _flat(fires[0].get_actor_location() - fire) < NEAR_CM,
            f"{len(fires)} fire(s)")
    p.check("...and client 1's character, within the cull distance",
            len(_bodies(p)) >= 2, f"{len(_bodies(p))} bodies")
    p.post("judged")


def probe_client(p):
    if p.client == 1:
        yield from _client_one(p)
    else:
        yield from _client_two(p)
