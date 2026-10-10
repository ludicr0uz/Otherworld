"""Two players reach for one item and exactly one gets it (task M23): the
pick-up, the drop and the loot window's take are the server's.

    a placed item   the hat lying in the level is the server's actor on every
                    machine: the server's replicates, and each client's own
                    copy of it has become that one
    E, both         both clients stand in reach of the hat, rest the reticle
                    on it and press E when the server says: one has a hat,
                    the other none, and no machine shows one left lying there
    the drop        the client that got it asks to drop it (AskDrop): the
                    server sets its own actor down, replicated, and both
                    clients see it where the server has it
    one frame       the server runs both players' Server_Take of it in one
                    frame: one has it
    the loot        the server kills a wanderer that carries one thing; both
                    clients open their loot window on the body and take the
                    row when the server says: one gets it, the body is empty
                    on every machine, and the loser's window shows no row
    one frame       a second body: a take from out of reach and a take of an
                    item the row does not hold are refused, then both
                    players' AskLootTake in one frame: one gets it

InteractForced and DropForced stand in for the keys, and the HUD's LootOpen
and LootTakeRequested for the window's. Single player's checks are
probe_pickup, probe_pickup_weapon_slot, probe_asks and probe_corpse_loot,
which go through the same events. Join order varies, so a player is known by
its player id.
"""

SYSTEMS = ('net',)

import math
import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.ask_consts import ASK_LOOT_TAKE
from combat.game_state import DAMAGED_BY_PLAYER_VAR
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.record_vars import DropForced
from combat.slot_tuning import HAS_ROOM_VAR, SLOT_VAR
from combat.strike_vars import SERVER_TAKE
from loot.consts import LOOT_RADIUS
from combat.tuning import INTERACT_RADIUS
from combat.weapon_component import vars as WV
from combat.weapon_component.dead import OWNER_DEAD_VAR
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from graphics_menu.loot_consts import LOOT_OPEN_VAR, LOOT_TAKE_VAR, LOOT_TARGET_VAR
from loot.consts import LOOT_CHANCES_VAR, LOOT_TAKE_REACH_CM, LOOT_VAR
from probes.probe_chop_tree import _flat, _items

RUNS_ON = ("server", "client")
HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in (INTERACT_FORCED_VAR, DropForced)]
            + [(HEALTH_BP_PATH, v) for v in (HV.Health, DAMAGED_BY_PLAYER_VAR,
                                             LOOT_CHANCES_VAR)]
            + [(HUD_BP_PATH, LOOT_OPEN_VAR), (HUD_BP_PATH, LOOT_TAKE_VAR)])

WAIT = 40.0
HAT = "BP_Hat_C"
SPARE_HEALTH = 100000.0
SAME_PLACE_CM = 25.0      # a client's copy of an item, from the server's
STOOD_CM = 80.0           # a client is where the server stood it
BACK_CM, ASIDE_CM = 110.0, 45.0   # where the two stand, off the item
BESIDE_CM = 90.0          # and off a body


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _vec(v):
    return [v.x, v.y, v.z]


def _wc(p, actor):
    return p.component(actor, WEAPON_COMP_CLASS_PATH)


def _hats(p, wc):
    return [i for i in p.get(wc, WV.Inventory)
            if unreal.SystemLibrary.is_valid(i) and i.get_class().get_name() == HAT]


def _lying(p, name=HAT):
    """The items of that class this machine shows lying in the world."""
    return [a for a in _items(p, name)
            if p.get(a, IV.Dropped) and not a.get_editor_property("hidden")]


def _carried(p, wc):
    return len([i for i in p.get(wc, WV.Inventory) if unreal.SystemLibrary.is_valid(i)])


def _bodies(p):
    """The dead wanderers of this world, as health components."""
    cls = p.load_class(HEALTH_CLASS_PATH)
    found = [a.get_component_by_class(cls) for a in
             unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Character)]
    return [h for h in found if h and p.get(h, HV.DespawnOnDeath) and p.get(h, HV.Dead)]


def _stand(pawn, at, yaw=0.0):
    pawn.set_actor_location_and_rotation(
        at + unreal.Vector(0.0, 0.0, 100.0), unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0),
        False, True)


def _posts(p, key):
    return [p.posted(f"client {n}", key) for n in (1, 2)]


def _both(p, key, seconds=WAIT):
    yield from _await(lambda: all(v is not None for v in _posts(p, key)), seconds)
    return all(v is not None for v in _posts(p, key))


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    if not (yield from _both(p, "id")):
        p.check("both clients said who they are", False, "no post")
        return
    by_id = {c.player_state.player_id: c.get_controlled_pawn()
             for c in p.players() if c.player_state}
    pawns = [by_id.get(i) for i in _posts(p, "id")]
    p.check("the server has both players' characters", all(pawns), str(sorted(by_id)))
    if not all(pawns):
        return
    wcs = [_wc(p, a) for a in pawns]
    for a in pawns:
        p.set(p.component(a, HEALTH_CLASS_PATH), HV.Health, SPARE_HEALTH)
    wanderers = _wanderers(p)
    for npc in wanderers[2:]:
        npc.destroy_actor()

    ok = yield from _server_loot(p, pawns, wcs, wanderers[:2])
    ok = ok and (yield from _server_items(p, pawns, wcs))
    p.post("judged", bool(ok))


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls
             if "ForestWandererAI" in c.get_class().get_name()]
    return [x for x in pawns if x is not None
            and not p.get(p.component(x, HEALTH_CLASS_PATH), HV.Dead)]


def _kill(p, npc, at):
    """``npc`` stood at ``at`` and killed by a player, with its loot roll
    forced: it carries one thing. Returns its health component."""
    npc.set_actor_location(at + unreal.Vector(0.0, 0.0, 100.0), False, True)
    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, LOOT_CHANCES_VAR, [1.0])
    p.set(health, DAMAGED_BY_PLAYER_VAR, True)
    p.set(health, HV.Health, 0.0)
    yield from _await(lambda: p.get(health, HV.Dead) and len(p.get(health, LOOT_VAR)) > 0, 10.0)
    return health


def _server_loot(p, pawns, wcs, wanderers):
    if len(wanderers) < 2:
        p.check("the server has two wanderers to kill", False, str(len(wanderers)))
        return False
    here = pawns[0].get_actor_location()
    ahead = pawns[0].get_actor_forward_vector()
    body = yield from _kill(p, wanderers[0], here + ahead * 400.0 - unreal.Vector(0, 0, 90.0))
    rows = [c.get_name() for c in p.get(body, LOOT_VAR)]
    p.check("the server's body carries one thing", len(rows) == 1, str(rows))
    if len(rows) != 1:
        return False
    at = body.get_owner().get_actor_location()
    p.post("body", _vec(at))
    if not (yield from _both(p, "rest")):
        p.check("both clients found the body", False, "no post")
        return False
    for pawn, rest, side in zip(pawns, _posts(p, "rest"), (-1.0, 1.0)):
        _stand(pawn, unreal.Vector(*rest) + unreal.Vector(-BESIDE_CM, side * ASIDE_CM, 0.0))
    p.post("beside")
    had = [_carried(p, wc) for wc in wcs]
    if not (yield from _both(p, "open")):
        p.check("both clients opened their loot window on the body", False, "no post")
        return False
    p.post("go-loot")
    yield from _both(p, "loot-got", 20.0)
    yield 0.3
    gained = [_carried(p, wc) - n for wc, n in zip(wcs, had)]
    # What the server's own gates read when the takes arrived: on record,
    # for a run where neither client gets the row.
    p.note("the server's gates: " + "; ".join(
        f"{(body.get_owner().get_actor_location() - pawn.get_actor_location()).length():.0f} cm "
        f"off (reach {LOOT_TAKE_REACH_CM:.0f}), OwnerDead {p.get(wc, OWNER_DEAD_VAR)}, room "
        f"{p.get(wc, HAS_ROOM_VAR)}"
        for pawn, wc in zip(pawns, wcs)))
    p.check("both clients take the body's one row at once: on the server one of them "
            "has it and the body carries nothing", sorted(gained) == [0, 1]
            and len(p.get(body, LOOT_VAR)) == 0, f"gained {gained}, the body {rows} -> "
            f"{[c.get_name() for c in p.get(body, LOOT_VAR)]}")
    p.check("...and the clients agree: one bag is one item fuller, by the server's record",
            sorted(v or 0 for v in _posts(p, "loot-got")) == [0, 1],
            str(_posts(p, "loot-got")))

    # --- a second body, the takes run by the server in one frame -------------------
    far = wanderers[1].get_actor_location()
    second = yield from _kill(p, wanderers[1], far - unreal.Vector(0, 0, 90.0))
    kinds = list(p.get(second, LOOT_VAR))
    gap = (second.get_owner().get_actor_location() - pawns[0].get_actor_location()).length()
    if not kinds:
        p.check("the second body carries something", False, "no loot")
        return False
    had = [_carried(p, wc) for wc in wcs]
    if gap > LOOT_TAKE_REACH_CM:
        wcs[0].call_method(ASK_LOOT_TAKE, (second, 0, kinds[0]))
        p.check(f"a take asked from {gap / 100.0:.0f} m off the body is refused",
                _carried(p, wcs[0]) == had[0] and len(p.get(second, LOOT_VAR)) == len(kinds),
                f"{had[0]} -> {_carried(p, wcs[0])} carried")
    for pawn, side in zip(pawns, (-1.0, 1.0)):
        _stand(pawn, second.get_owner().get_actor_location()
               + unreal.Vector(-BESIDE_CM, side * ASIDE_CM, -90.0))
    yield 0.3
    wcs[0].call_method(ASK_LOOT_TAKE, (second, 0, unreal.Character.static_class()))
    p.check("a take of an item the row does not hold is refused: what another "
            "player's take moved up into the row is not taken instead",
            _carried(p, wcs[0]) == had[0] and len(p.get(second, LOOT_VAR)) == len(kinds),
            f"{had[0]} -> {_carried(p, wcs[0])} carried")
    for wc in wcs:
        wc.call_method(ASK_LOOT_TAKE, (second, 0, kinds[0]))
    yield 0.2
    gained = [_carried(p, wc) - n for wc, n in zip(wcs, had)]
    p.check("both players' takes of one row in one frame: the first has it, the "
            "second nothing", gained == [1, 0] and len(p.get(second, LOOT_VAR)) == len(kinds) - 1,
            f"gained {gained}, {len(p.get(second, LOOT_VAR))} row(s) left")
    for npc in _wanderers(p):
        npc.destroy_actor()
    return True


def _server_items(p, pawns, wcs):
    hats = [a for a in _items(p, HAT) if p.get(a, IV.Dropped)]
    p.check("the level's hat lies in the server's world: Dropped, InWorld and "
            "replicated, by its own Tick",
            len(hats) == 1 and bool(p.get(hats[0], IV.InWorld))
            and bool(hats[0].get_editor_property("replicates")),
            f"{len(hats)} hat(s)" + (f", InWorld {p.get(hats[0], IV.InWorld)}, replicates "
                                     f"{hats[0].get_editor_property('replicates')}" if hats else ""))
    if len(hats) != 1:
        return False
    hat = hats[0]
    at = hat.get_actor_location()
    p.post("hat", _vec(at))
    if not (yield from _both(p, "hat-seen")):
        return False
    for pawn, side in zip(pawns, (-1.0, 1.0)):
        _stand(pawn, at + unreal.Vector(-BACK_CM, side * ASIDE_CM, 0.0))
    p.post("reach")
    if not (yield from _both(p, "aimed")):
        p.check("both clients rested the reticle on the hat", False, "no post")
        return False
    p.post("go-hat")
    yield from _both(p, "hat-got", 20.0)
    yield 0.3
    # The hat was the level's: the take destroyed it and put a fresh hat of its
    # class in the winner's bag (task A2, pickup.py), which is the one actor the
    # rest of this step follows.
    fresh = [[i for i in p.get(wc, WV.Inventory) if i.get_class().get_name() == HAT
              and not unreal.OtherworldNetLibrary.is_level_actor(i)] for wc in wcs]
    holds = [bool(c) for c in fresh]
    p.check("both clients press E on the hat at once: on the server one of them "
            "carries a fresh hat of its class, the level's actor is gone, and none lies "
            "in the world",
            sorted(holds) == [False, True] and len(_lying(p)) == 0
            and len([a for a in _lying(p) if a == hat]) == 0,
            f"carried by {holds}, {len(_lying(p))} lying")
    hat = next((c[0] for c in fresh if c), hat)
    p.check("...and the clients agree: one has a hat, the other none",
            sorted(v or 0 for v in _posts(p, "hat-got")) == [0, 1], str(_posts(p, "hat-got")))
    if sorted(holds) != [False, True]:
        return False

    # --- the winner drops it ---------------------------------------------------------
    winner = holds.index(True)
    p.post("drop", winner + 1)
    yield from _await(lambda: p.get(hat, IV.Dropped), 20.0)
    yield 0.3
    down = hat.get_actor_location()
    off = _flat(down - pawns[winner].get_actor_location())
    p.check("the winner's drop is the server's: its own hat actor is out of the "
            "inventory and lies on the ground ahead, Dropped, InWorld, replicated",
            bool(p.get(hat, IV.Dropped)) and bool(p.get(hat, IV.InWorld))
            and bool(hat.get_editor_property("replicates"))
            and hat not in list(p.get(wcs[winner], WV.Inventory)) and 30.0 < off < 250.0,
            f"Dropped {p.get(hat, IV.Dropped)}, InWorld {p.get(hat, IV.InWorld)}, "
            f"{off:.0f} cm from the player")
    p.post("down", _vec(down))
    if not (yield from _both(p, "down-seen")):
        return False

    # --- both takes in one frame -------------------------------------------------------
    for pawn, side in zip(pawns, (-1.0, 1.0)):
        _stand(pawn, down + unreal.Vector(-BACK_CM, side * ASIDE_CM, 0.0))
    yield 0.3
    for wc in wcs:
        wc.call_method(SERVER_TAKE, (hat,))
    holds = [hat in list(p.get(wc, WV.Inventory)) for wc in wcs]
    p.check("both players' Server_Take of the hat in one frame: the first has it, "
            "the second nothing", holds == [True, False] and not p.get(hat, IV.Dropped),
            f"carried by {holds}")
    p.post("taken")
    yield from _both(p, "hat-final", 20.0)
    p.check("...and each client's bag says so: one hat between them",
            _posts(p, "hat-final") == [1, 0], str(_posts(p, "hat-final")))
    return True


# ─── the clients ─────────────────────────────────────────────────────────────

def _reticle_on(p, wc, target):
    """Turn the view until the reticle rests on ``target``, a point on the
    ground, or beside it (the view is over the shoulder, and the aim's trace
    starts ahead of the player). Returns how far the reticle's point is from
    it, in cm."""
    cam = unreal.GameplayStatics.get_player_camera_manager(p.pawn(), 0)
    for _ in range(4):
        to = target - cam.get_camera_location()
        p.controller().set_control_rotation(unreal.Rotator(
            pitch=math.degrees(math.atan2(to.z, _flat(to))),
            yaw=math.degrees(math.atan2(to.y, to.x)), roll=0.0))
        yield 0.15
    return (p.get(wc, "AimPoint") - target).length()


def _stood(p, at, seconds=10.0):
    yield from _await(lambda: _flat(p.pawn().get_actor_location() - at) < STOOD_CM
                      + BACK_CM + ASIDE_CM, seconds)
    yield 0.3


def probe_client(p):
    mine = p.pawn()
    wc = _wc(p, mine)
    yield from _await(lambda: p.get(wc, "Held") is not None
                      and p.player_state() is not None)
    p.post("id", p.player_state().player_id)
    yield from _client_loot(p, wc)
    yield from _client_items(p, wc)
    yield from _await(lambda: p.posted("server", "judged") is not None, 30.0)


def _client_loot(p, wc):
    hud = p.hud()
    yield from _await(lambda: p.posted("server", "body") is not None, 60.0)
    if p.posted("server", "body") is None:
        return
    at = unreal.Vector(*p.posted("server", "body"))

    def found():
        near = [h for h in _bodies(p)
                if _flat(h.get_owner().get_actor_location() - at) < 300.0]
        return near[0] if near and len(p.get(near[0], LOOT_VAR)) == 1 else None
    yield from _await(lambda: found() is not None, 20.0)
    body = found()
    p.check(f"{p.where} sees the body and the one thing the server put on it",
            body is not None, f"{len(_bodies(p))} dead wanderer(s)")
    if body is None:
        return
    yield 1.0           # the ragdoll comes to rest
    rest = body.get_owner().get_component_by_class(
        unreal.SkeletalMeshComponent).get_world_location()
    p.post("rest", _vec(rest))
    yield from _await(lambda: p.posted("server", "beside") is not None
                      and p.get(hud, LOOT_TARGET_VAR) == body)
    # Where the two stand when the window is asked: a miss here has been
    # intermittent (2 of 4 runs on 2026-10-07), so the distance is on record.
    _pawn_at = p.pawn().get_actor_location()
    _mesh_at = body.get_owner().get_component_by_class(
        unreal.SkeletalMeshComponent).get_world_location()
    p.note(f"{p.where} stands {(_pawn_at - _mesh_at).length():.0f} cm from the body's mesh "
           f"(reach {LOOT_RADIUS:.0f}); mesh z {_mesh_at.z:.0f}, rest z {rest.z:.0f}; "
           f"LootTarget {p.get(hud, LOOT_TARGET_VAR)}")
    p.check(f"stood beside it, {p.where}'s loot window finds the body",
            p.get(hud, LOOT_TARGET_VAR) == body, str(p.get(hud, LOOT_TARGET_VAR)))
    had = _carried(p, wc)
    p.set(hud, LOOT_OPEN_VAR, True)
    yield 0.3
    p.post("open")
    yield from _await(lambda: p.posted("server", "go-loot") is not None)
    p.set(hud, LOOT_TAKE_VAR, True)
    yield from _await(lambda: len(p.get(body, LOOT_VAR)) == 0, 15.0)
    yield 1.0           # the record, if the item was this client's
    got = _carried(p, wc) - had
    p.check(f"{p.where}'s window shows the row gone, whoever took it: its copy of "
            "the body carries nothing, and the window is still open on it",
            len(p.get(body, LOOT_VAR)) == 0 and bool(p.get(hud, LOOT_OPEN_VAR))
            and not p.get(hud, LOOT_TAKE_VAR), f"{len(p.get(body, LOOT_VAR))} row(s)")
    p.check(f"...and {p.where}'s bag holds what the server gave it: "
            + ("the item" if got else "nothing more"), got in (0, 1), f"{got:+d}")
    p.post("loot-got", got)
    p.set(hud, LOOT_OPEN_VAR, False)


def _client_items(p, wc):
    mine = p.pawn()
    yield from _await(lambda: p.posted("server", "hat") is not None, 90.0)
    if p.posted("server", "hat") is None:
        return
    at = unreal.Vector(*p.posted("server", "hat"))
    yield from _await(lambda: len(_lying(p)) == 1 and not _lying(p)[0].has_authority(), 15.0)
    seen = _lying(p)
    gap = min(((a.get_actor_location() - at).length() for a in seen), default=-1.0)
    p.check(f"{p.where} sees the level's hat where the server has it, and its copy "
            "is the server's actor: it has no authority over it",
            len(seen) == 1 and 0.0 <= gap < SAME_PLACE_CM and not seen[0].has_authority()
            and bool(p.get(seen[0], IV.InWorld)),
            f"{len(seen)} hat(s), {gap:.0f} cm off"
            + (f", authority {seen[0].has_authority()}" if seen else ""))
    p.post("hat-seen")

    yield from _await(lambda: p.posted("server", "reach") is not None)
    yield from _stood(p, at)
    off = yield from _reticle_on(p, wc, at)
    reach = (mine.get_actor_location() - at).length()
    aim = p.get(wc, "AimPoint")
    nearest = min(_lying(p, None), key=lambda a: (a.get_actor_location() - aim).length(),
                  default=None)
    p.check(f"{p.where} stands in reach of the hat, and of everything lying there "
            "the hat is nearest the reticle: E is for it",
            nearest is not None and nearest.get_class().get_name() == HAT
            and reach < INTERACT_RADIUS,
            f"the reticle {off:.0f} cm off, the hat {reach:.0f} cm away, nearest "
            f"{nearest.get_class().get_name() if nearest else None}")
    p.post("aimed")
    yield from _await(lambda: p.posted("server", "go-hat") is not None)
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield from _await(lambda: not _lying(p), 15.0)
    yield 1.0           # the record, if the hat is this client's
    p.check(f"{p.where} sees no hat left lying there, whoever took it",
            not _lying(p), f"{len(_lying(p))} still shown")
    p.post("hat-got", len(_hats(p, wc)))

    # --- the drop ---------------------------------------------------------------------
    yield from _await(lambda: p.posted("server", "drop") is not None)
    if p.posted("server", "drop") == p.client and _hats(p, wc):
        p.ask_drop(wc, p.get(_hats(p, wc)[0], SLOT_VAR))
        yield from _await(lambda: not _hats(p, wc), 15.0)
        p.check(f"{p.where}'s drop takes the hat out of its bag: the server's record "
                "says so", not _hats(p, wc), f"{len(_hats(p, wc))} hat(s)")
    yield from _await(lambda: p.posted("server", "down") is not None)
    if p.posted("server", "down") is None:
        return
    down = unreal.Vector(*p.posted("server", "down"))
    yield from _await(lambda: any((a.get_actor_location() - down).length() < SAME_PLACE_CM
                                  for a in _lying(p)), 15.0)
    seen = _lying(p)
    gap = min(((a.get_actor_location() - down).length() for a in seen), default=-1.0)
    p.check(f"{p.where} sees the dropped hat where the server set it down: one, "
            "the server's actor", len(seen) == 1 and 0.0 <= gap < SAME_PLACE_CM
            and not seen[0].has_authority(), f"{len(seen)} hat(s), {gap:.0f} cm off")
    p.post("down-seen")

    yield from _await(lambda: p.posted("server", "taken") is not None)
    yield from _await(lambda: not _lying(p), 15.0)
    yield 1.0
    p.check(f"{p.where} sees no hat lying there once the server gave it to one of them",
            not _lying(p), f"{len(_lying(p))} still shown")
    p.post("hat-final", len(_hats(p, wc)))
