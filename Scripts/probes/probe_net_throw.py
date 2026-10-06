"""The throw and the take are the server's (task M20): client 1 throws its axe
into a tree, every machine sees it lodged there, and client 2 takes it out.

    server     refuses a throw that starts 10 m from the thrower; clears the
               wanderers; finds a trunk (probe_throw_strike's spot) and stands
               client 1 in front of it
    client 1   brings its axe to hand, rests the reticle on the trunk, holds
               the throw key and clicks: its own hand lets go and asks
               Server_Throw. It posts once the server's record has taken the
               axe out of its inventory
    server     its own axe actor left client 1's inventory, flew and is in the
               trunk: Dropped, Lodged, InWorld, replicated, off the ground
    client 1,  each see one axe in the trunk, where the server has it: the
    client 2   server's actor, sent to them
    server     stands client 2 at the trunk
    client 2   presses E: Server_Take. It posts once the record has put a
               second axe in its inventory, and sees none left in the tree
    server     the same actor is in client 2's inventory, out of the world;
               a second take of it is refused; a throw asked for at ten times
               the item's speed leaves at the item's own
    client 1   sees no axe in the tree, and has none

ThrowKeyForced, ThrowClickForced and InteractForced stand in for the keys.
Single player's check is probes/probe_throw_strike.py, which throws the same
blade at the same kind of trunk through the same events.
"""

import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.strike_vars import SERVER_TAKE, SERVER_THROW, THROW_SPEED_SLACK
from combat.throw_tuning import LODGE_MAX_HEIGHT_CM, THROW_SPEED_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR)
from combat.weapon_component.throw_flight import THROWN_VAR, THROW_VELOCITY_VAR
from probes.probe_chop_tree import CLEAR_CM, _flat, _items, _trees
from probes.probe_hot_blade import _wanderers
from probes.probe_throw_strike import AXE, ON_GROUND_CM, _launch, _reticle_on, _spot

RUNS_ON = ("server", "client")
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (THROW_FORCED_VAR, THROW_CLICK_FORCED_VAR, INTERACT_FORCED_VAR,
             WV.EquippedIndex)] + [(HEALTH_BP_PATH, HV.Health)]

WAIT = 30.0
SPARE_HEALTH = 100000.0
SAME_PLACE_CM = 15.0      # a client's copy of the lodged axe, from the server's
STOOD_CM = 60.0           # a client is where the server stood it
CHEST_UP_CM = 110.0       # where on the trunk the reticle is put


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    return lambda: ready() or time.time() > until


def _vec(v):
    return [v.x, v.y, v.z]


def _players(p):
    cls = p.load_class(HEALTH_CLASS_PATH)
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), unreal.Character)
        if a.get_component_by_class(cls)
        and not p.get(a.get_component_by_class(cls), HV.DespawnOnDeath)]


def _nearest(actors, point):
    at = unreal.Vector(*point)
    return min(actors, key=lambda a: (a.get_actor_location() - at).length(), default=None)


def _axes(p, wc):
    return [i for i in p.get(wc, "Inventory") if i.get_class().get_name() == AXE]


def _in_world(p):
    """The axes this machine shows lying or lodged in the world."""
    return [a for a in _items(p, AXE)
            if p.get(a, IV.Dropped) and not a.get_editor_property("hidden")]


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield _await(lambda: p.posted("client 1", "pos") and p.posted("client 2", "pos"))
    if not (p.posted("client 1", "pos") and p.posted("client 2", "pos")):
        p.check("both clients said where they stand", False, "no post")
        return
    players = _players(p)
    one = _nearest(players, p.posted("client 1", "pos"))
    two = _nearest(players, p.posted("client 2", "pos"))
    wc1 = p.component(one, WEAPON_COMP_CLASS_PATH)
    wc2 = p.component(two, WEAPON_COMP_CLASS_PATH)
    for body in players:
        p.set(p.component(body, HEALTH_CLASS_PATH), HV.Health, SPARE_HEALTH)
    for ctrl in _wanderers(p):
        pawn = ctrl.get_controlled_pawn()
        if pawn:
            pawn.destroy_actor()

    # --- a throw from where the thrower is not is refused ------------------------
    carried = len(list(p.get(wc1, "Inventory")))
    far = one.get_actor_location() + one.get_actor_forward_vector() * 1000.0
    wc1.call_method(SERVER_THROW, (far, unreal.Vector(500.0, 0.0, 300.0)))
    yield 0.2
    p.check("Server_Throw from 10 m off the thrower is refused: nothing leaves the hand",
            len(list(p.get(wc1, "Inventory"))) == carried and p.get(wc1, THROWN_VAR) is None,
            f"{carried} -> {len(list(p.get(wc1, 'Inventory')))} carried")

    # --- the tree ---------------------------------------------------------------
    axe = (_axes(p, wc1) or [None])[0]
    lying = [a.get_actor_location() for a in _items(p) if p.get(a, IV.Dropped)]
    here = one.get_actor_location()
    spot = base = None
    for _comp, _index, base in sorted(_trees(p), key=lambda t: (t[2] - here).length())[:60]:
        if any(_flat(at - base) < CLEAR_CM for at in lying):
            continue
        spot = _spot(p, one, base)
        if spot:
            break
    p.check("the server has client 1's axe and found a trunk to throw it at",
            axe is not None and spot is not None, f"axe {axe}, spot {spot}")
    if axe is None or spot is None:
        return
    at, yaw, near, ground, _view = spot
    turn = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    one.set_actor_location_and_rotation(at, turn, False, True)
    # Client 2 well clear of the throw, behind the thrower.
    two.set_actor_location_and_rotation(
        at - unreal.MathLibrary.get_forward_vector(turn) * 300.0, turn, False, True)
    p.post("stand", [_vec(at), yaw, _vec(base)])

    yield _await(lambda: p.posted("client 1", "thrown"), 60.0)
    if not p.posted("client 1", "thrown"):
        p.check("client 1 threw its axe", False, "no post")
        return
    yield _await(lambda: p.get(wc1, THROWN_VAR) is None and p.get(axe, IV.Dropped), 10.0)
    yield 0.3
    rest = axe.get_actor_location()
    p.check("the server's axe left client 1's inventory: thrown by the server, at "
            "client 1's ask", axe not in list(p.get(wc1, "Inventory")),
            str([i.get_class().get_name() for i in p.get(wc1, "Inventory")]))
    p.check("...and is in the trunk on the server: a pick-up, Lodged, off the ground",
            bool(p.get(axe, IV.Dropped)) and bool(p.get(axe, IV.Lodged))
            and ON_GROUND_CM < rest.z - ground < LODGE_MAX_HEIGHT_CM + 30.0
            and _flat(rest - base) < 120.0,
            f"Dropped {p.get(axe, IV.Dropped)}, Lodged {p.get(axe, IV.Lodged)}, "
            f"{rest.z - ground:.0f} cm up, {_flat(rest - base):.0f} cm from the tree's middle")
    p.check("...an actor of the world's: InWorld, and replicated",
            bool(p.get(axe, IV.InWorld)) and bool(axe.get_editor_property("replicates")),
            f"InWorld {p.get(axe, IV.InWorld)}, replicates {axe.get_editor_property('replicates')}")
    p.post("lodged", _vec(rest))

    yield _await(lambda: p.posted("client 1", "seen") and p.posted("client 2", "seen"))
    two.set_actor_location_and_rotation(near, turn, False, True)
    p.post("reach", _vec(near))
    yield _await(lambda: p.posted("client 2", "taken"), 60.0)
    if not p.posted("client 2", "taken"):
        p.check("client 2 took the axe", False, "no post")
        return
    yield 0.3
    p.check("the same axe is in client 2's inventory on the server, out of the world",
            axe in list(p.get(wc2, "Inventory")) and not p.get(axe, IV.Dropped)
            and not p.get(axe, IV.InWorld) and not p.get(axe, IV.Lodged)
            and axe not in list(p.get(wc1, "Inventory")),
            f"Dropped {p.get(axe, IV.Dropped)}, InWorld {p.get(axe, IV.InWorld)}, "
            f"client 2 carries {[i.get_class().get_name() for i in p.get(wc2, 'Inventory')]}")

    # --- what is not lying there cannot be taken ------------------------------------
    had = len(list(p.get(wc1, "Inventory")))
    wc1.call_method(SERVER_TAKE, (axe,))
    yield 0.2
    p.check("Server_Take of an item that is not Dropped is refused: client 1 cannot "
            "take the axe out of client 2's bag",
            len(list(p.get(wc1, "Inventory"))) == had and axe in list(p.get(wc2, "Inventory")),
            f"client 1 carried {had}, now {len(list(p.get(wc1, 'Inventory')))}")

    # --- the speed is the item's own ---------------------------------------------
    held = p.get(wc2, "Held")
    if held is not None:
        top = float(p.get(held, THROW_SPEED_VAR))
        start = _launch(two.get_actor_location(), yaw + 180.0)
        wc2.call_method(SERVER_THROW, (start, unreal.MathLibrary.get_forward_vector(
            unreal.Rotator(pitch=20.0, yaw=yaw + 180.0, roll=0.0)) * top * 10.0))
        speed = p.get(wc2, THROW_VELOCITY_VAR).length()
        p.check("Server_Throw asked for at ten times the item's speed leaves at the "
                "item's own", p.get(wc2, THROWN_VAR) == held
                and speed <= top * THROW_SPEED_SLACK + 1.0,
                f"{speed:.0f} cm/s, the item's {top:.0f}")
    p.post("judged")


# ─── the clients ─────────────────────────────────────────────────────────────

def probe_client(p):
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    yield 0.5
    p.post("pos", _vec(mine.get_actor_location()))
    yield _await(lambda: p.posted("server", "stand"), 60.0)
    if not p.posted("server", "stand"):
        p.check(f"{p.where} was told where to stand", False, "no post")
        return
    at, yaw, base = p.posted("server", "stand")
    at, base = unreal.Vector(*at), unreal.Vector(*base)
    mine_axes = len(_axes(p, wc))

    if p.client == 1:
        yield _await(lambda: (mine.get_actor_location() - at).length() < STOOD_CM, 10.0)
        p.check("client 1 stands where the server put it",
                (mine.get_actor_location() - at).length() < STOOD_CM,
                f"{(mine.get_actor_location() - at).length():.0f} cm off")
        axe = _axes(p, wc)[0]
        p.hold(wc, list(p.get(wc, "Inventory")).index(axe))
        yield _await(lambda: p.get(wc, "Held") is not None
                     and p.get(wc, "Held").get_class().get_name() == AXE, 10.0)
        yield 0.3
        target = unreal.Vector(base.x, base.y, mine.get_actor_location().z + 20.0)
        off = yield from _reticle_on(p, wc, mine, target, 0.0, yaw)
        p.set(wc, THROW_FORCED_VAR, True)
        yield _await(lambda: p.get(wc, THROW_AIMING_VAR), 5.0)
        yield 0.1
        p.set(wc, THROW_CLICK_FORCED_VAR, True)
        yield _await(lambda: not p.get(wc, THROW_AIMING_VAR), 5.0)
        p.set(wc, THROW_CLICK_FORCED_VAR, False)
        yield _await(lambda: len(_axes(p, wc)) < mine_axes, 10.0)
        p.set(wc, THROW_FORCED_VAR, False)
        p.check("client 1's throw takes the axe out of its own inventory: the "
                "server's record says so", len(_axes(p, wc)) == mine_axes - 1,
                f"{mine_axes} -> {len(_axes(p, wc))} axe(s); the reticle was {off:.0f} cm "
                "off the trunk")
        p.post("thrown")

    yield _await(lambda: p.posted("server", "lodged"), 90.0)
    if not p.posted("server", "lodged"):
        return
    rest = unreal.Vector(*p.posted("server", "lodged"))
    yield _await(lambda: any((a.get_actor_location() - rest).length() < SAME_PLACE_CM
                             for a in _in_world(p)), 10.0)
    seen = _in_world(p)
    gap = min(((a.get_actor_location() - rest).length() for a in seen), default=-1.0)
    p.check(f"{p.where} sees one axe in the trunk, where the server has it: the "
            "server's actor, sent to it", len(seen) == 1 and 0.0 <= gap < SAME_PLACE_CM
            and bool(p.get(seen[0], IV.Lodged)) and not seen[0].has_authority(),
            f"{len(seen)} axe(s) in the world, the nearest {gap:.0f} cm from the server's")
    p.post("seen")

    if p.client == 2:
        yield _await(lambda: p.posted("server", "reach"))
        near = unreal.Vector(*p.posted("server", "reach"))
        yield _await(lambda: (mine.get_actor_location() - near).length() < STOOD_CM, 10.0)
        yield from _reticle_on(p, wc, mine, rest, 0.0, yaw)
        p.set(wc, INTERACT_FORCED_VAR, True)
        yield _await(lambda: len(_axes(p, wc)) > mine_axes, 10.0)
        p.check("client 2's E takes the axe client 1 threw: a second axe in its own "
                "inventory, by the server's record", len(_axes(p, wc)) == mine_axes + 1,
                f"{mine_axes} -> {len(_axes(p, wc))} axe(s), "
                f"{(mine.get_actor_location() - rest).length():.0f} cm from it")
        p.post("taken")

    yield _await(lambda: p.posted("client 2", "taken"), 90.0)
    yield _await(lambda: not _in_world(p), 10.0)
    p.check(f"{p.where} sees no axe left in the tree once it is taken",
            not _in_world(p), f"{len(_in_world(p))} still shown")
    if p.client == 1:
        p.check("...and client 1 has none: its axe is client 2's now",
                len(_axes(p, wc)) == mine_axes - 1, f"{len(_axes(p, wc))} axe(s)")
    yield _await(lambda: p.posted("server", "judged"), 30.0)
