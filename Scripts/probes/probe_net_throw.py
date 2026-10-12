"""The throw and the take are the server's (task M20): client 1 throws its axe
into a tree, every machine sees it lodged there, and client 2 takes it out.

    server     refuses a throw that starts 10 m from the thrower; clears the
               wanderers; finds a trunk (probe_throw_strike's spot) and stands
               client 1 in front of it
    client 1   brings its axe to hand, rests the reticle on the trunk and
               holds the throw key
    server     empties its own copy of client 1's hand, so the next throw is
               one it refuses
    client 1   clicks: its stand-in leaves on the click, the server refuses,
               and the axe is in its hand again, one axe shown on every frame
    server     gives the hand back
    client 1   clicks again: its own hand lets go and asks Server_Throw. It
               posts once the server's record has taken the axe out of its
               inventory
    server     its own axe actor left client 1's inventory, flew and is in the
               trunk: Dropped, Lodged, InWorld, replicated, off the ground
    client 1,  each see one axe in the trunk, where the server has it: the
    client 2   server's actor, sent to them. And each flew it there itself
               (task R2, probes/throw_watch.py): a stand-in of its own, shown
               within 100 ms of the release (client 1's from its own click),
               on the curve to 30 cm every frame and never still in the air,
               one axe shown on every frame until a second after the rest
    server     stands client 2 at the trunk
    client 2   presses E: Server_Take. It posts once the record has put a
               second axe in its inventory, and sees none left in the tree
    server     the same actor is in client 2's inventory, out of the world;
               a second take of it is refused; a throw asked for at ten times
               the item's speed leaves at the item's own, and flies a second
    client 1   sees no axe in the tree, and has none
    client 1,  never showed the server's own actor in the air: not the axe,
    client 2   and not that last item, of whose launch no client is told (the
               probe's Python made the throw, and under it no event leaves the
               machine): hidden until it rests

ThrowKeyForced, ThrowClickForced and InteractForced stand in for the keys.
Single player's check is probes/probe_throw_strike.py, which throws the same
blade at the same kind of trunk through the same events.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # the axe is thrown at a tree and the 50 m level's nearest is 17 m off
SYSTEMS = ('net', 'throw')

import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.strike_vars import SERVER_TAKE, SERVER_THROW, THROW_SPEED_SLACK
from combat.throw_tuning import (
    LODGE_MAX_HEIGHT_CM, THROW_GRAVITY_Z, THROW_MAX_FLIGHT_S, THROW_SPEED_VAR)
from combat.weapon_component import vars as WV
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR)
from combat.weapon_component.throw_flight import THROWN_VAR, THROW_VELOCITY_VAR
from probes.probe_chop_tree import CLEAR_CM, _flat, _items, _trees
from probes.probe_hot_blade import _wanderers
from probes.probe_throw_strike import AXE, ON_GROUND_CM, _launch, _reticle_on, _spot
from probes import throw_watch as TW

RUNS_ON = ("server", "client")
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (THROW_FORCED_VAR, THROW_CLICK_FORCED_VAR, INTERACT_FORCED_VAR,
             WV.EquippedIndex, WV.Held)] + [(HEALTH_BP_PATH, HV.Health)]

WAIT = 30.0
SPARE_HEALTH = 100000.0
SAME_PLACE_CM = 15.0      # a client's copy of the lodged axe, from the server's
STOOD_CM = 60.0           # a client is where the server stood it
CHEST_UP_CM = 110.0       # where on the trunk the reticle is put
FLIGHT_PLACES = 5         # a client's stand-in in the air, seen at this many places
SEEN_S = 0.1              # a client shows the throw this soon after the server's release
OFF_CURVE_CM = 30.0       # ...and never further than this from the server's curve
AFTER_REST_S = 1.0        # one axe is shown until this long after the rest


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


def _watching(p, sample, ready, seconds=WAIT):
    """``ready`` awaited, with ``sample()`` taken every frame of the wait."""
    done = _await(ready, seconds)

    def poll():
        sample()
        return done()
    return poll


def _flying(p):
    """The server's items this client shows in the air: sent to it, of the
    world's, not yet lying, and not hidden."""
    return [a for a in _items(p)
            if not a.has_authority() and not a.get_editor_property("hidden")
            and p.get(a, IV.InWorld) and not p.get(a, IV.Dropped)]


def _watch(p, wc, name=AXE):
    """Every frame's pictures of the ``name`` that ``wc``'s owner throws."""
    return TW.Watch(p, wc, name, lambda: _items(p, name),
                    lambda: unreal.GameplayStatics.get_time_seconds(p.world()),
                    WV.ThrowFlyer, WV.ThrowStopped, WV.ThrowEnded, IV.InWorld)


def _other_wc(p, mine):
    """The weapon component of this client's copy of the other player."""
    others = [a for a in _players(p) if a != mine]
    return p.component(others[0], WEAPON_COMP_CLASS_PATH) if others else None


def _check_flight(p, what, frames, launch, rest, rested, since=None, count=True):
    """A client flew ``what`` itself: the checks of task R2 over its frames.
    ``launch`` is the server's (t, start, velocity), ``rest`` where its item
    came to lie and ``rested`` when; ``since`` the wall clock the count of
    items shown starts at (the first stand-in's, if none)."""
    t0, start, velocity = launch
    first = TW.first_wall(frames, TW.STANDIN)
    p.check(f"{p.where} shows {what} within {SEEN_S * 1000:.0f} ms of the server's "
            "release: a stand-in of its own, flown here",
            first is not None and first - t0 < SEEN_S,
            "never shown" if first is None else f"{(first - t0) * 1000:.0f} ms after it")
    if first is None:
        return
    off = TW.worst_off(frames, start, velocity, THROW_GRAVITY_Z, THROW_MAX_FLIGHT_S, rest)
    seen = TW.places(frames)
    p.check(f"...on the server's curve every frame, never more than {OFF_CURVE_CM:g} cm "
            "off it", off <= OFF_CURVE_CM, f"{off:.1f} cm at worst, over {seen} place(s)")
    p.check("...and never still in the air", TW.stalls(frames) == 0,
            f"{TW.stalls(frames)} frame(s) it did not move")
    if not count:
        return
    wrong = TW.miscounts(frames, first if since is None else since, rested + AFTER_REST_S)
    last = frames[-1][2]
    lies = (len(last) == 1 and last[0][0] == TW.WORLD
            and (unreal.Vector(*last[0][1]) - unreal.Vector(*rest)).length() < SAME_PLACE_CM)
    p.check(f"...one {what} shown on every frame from the release to "
            f"{AFTER_REST_S:g} s after the rest, and at the end the server's own, where "
            "the server has it",
            not wrong and lies and frames[-1][0] >= rested + AFTER_REST_S,
            f"{len(wrong)} frame(s) of another count {wrong[:4]}, at the end {last}")


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

    # --- a throw the server refuses: its own copy of the hand is empty -----------
    yield _await(lambda: p.posted("client 1", "aimed"), 60.0)
    # Emptied after every frame: the request is served at the head of the next,
    # before the server's own Tick can put the axe back in the hand.
    barred = time.time()

    def bar():
        p.set(wc1, WV.Held, None)
        if time.time() > barred + 0.2 and not p.posted("server", "barred"):
            p.post("barred")
    yield _watching(p, bar, lambda: p.posted("client 1", "refused") is not None, 30.0)
    p.check("the throw client 1 predicted with the server's hand empty is refused: "
            "the server threw nothing",
            axe in list(p.get(wc1, "Inventory")) and p.get(wc1, THROWN_VAR) is None
            and not p.get(axe, IV.InWorld), f"Thrown {p.get(wc1, THROWN_VAR)}")
    p.set(wc1, WV.Held, axe)
    yield 0.1
    p.post("open")

    # --- the throw: when it leaves on the server, and on what curve ------------------
    def release():
        if not p.posted("server", "release") and p.get(wc1, THROWN_VAR) is not None:
            p.post("release", [time.time(), _vec(p.get(wc1, WV.ThrowStart)),
                               _vec(p.get(wc1, THROW_VELOCITY_VAR))])
    yield _watching(p, release, lambda: p.posted("client 1", "thrown"), 60.0)
    if not p.posted("client 1", "thrown"):
        p.check("client 1 threw its axe", False, "no post")
        return
    yield _await(lambda: p.get(wc1, THROWN_VAR) is None and p.get(axe, IV.Dropped), 10.0)
    rested = time.time()
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
    p.post("lodged", [_vec(rest), rested])

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
        p.post("free", [time.time(), _vec(p.get(wc2, WV.ThrowStart)),
                        _vec(p.get(wc2, THROW_VELOCITY_VAR))])
        # It flies free for a second, away from the tree.
        yield _await(lambda: p.get(wc2, THROWN_VAR) is None, 10.0)
        p.post("free rest", [_vec(held.get_actor_location()), time.time()])
        yield AFTER_REST_S + 1.0
    p.post("judged", held is not None)


# ─── the clients ─────────────────────────────────────────────────────────────

def _armed(p):
    """This client's own character, once it has one (a join under packet loss
    can leave it a spectator for seconds)."""
    pawn = p.pawn()
    try:
        return pawn is not None and p.component(pawn, WEAPON_COMP_CLASS_PATH) is not None
    except LookupError:
        return False


def probe_client(p):
    yield _await(lambda: _armed(p), 60.0)
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
    # Client 1 throws: its own component here, its copy's on client 2.
    watch = _watch(p, wc if p.client == 1 else _other_wc(p, mine))
    clicked = None
    aloft = []

    def sample():
        watch.sample()
        aloft.extend(_flying(p))

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
        p.post("aimed")
        yield _await(lambda: p.posted("server", "barred"), 30.0)
        yield from _refused(p, wc, axe, mine_axes)
        p.post("refused")
        yield _await(lambda: p.posted("server", "open"), 30.0)
        yield _await(lambda: p.get(wc, THROW_AIMING_VAR), 10.0)
        yield 0.1
        clicked = time.time()
        p.set(wc, THROW_CLICK_FORCED_VAR, True)
        yield _watching(p, sample, lambda: not p.get(wc, THROW_AIMING_VAR), 5.0)
        p.set(wc, THROW_CLICK_FORCED_VAR, False)
        yield _watching(p, sample, lambda: len(_axes(p, wc)) < mine_axes, 10.0)
        p.set(wc, THROW_FORCED_VAR, False)
        p.check("client 1's throw takes the axe out of its own inventory: the "
                "server's record says so", len(_axes(p, wc)) == mine_axes - 1,
                f"{mine_axes} -> {len(_axes(p, wc))} axe(s); the reticle was {off:.0f} cm "
                "off the trunk")
        p.post("thrown")

    yield _watching(p, sample, lambda: p.posted("server", "lodged"), 90.0)
    if not p.posted("server", "lodged"):
        return
    at_rest, rested = p.posted("server", "lodged")
    rest = unreal.Vector(*at_rest)
    yield _watching(p, sample,
                    lambda: time.time() > rested + AFTER_REST_S + 0.3, 10.0)
    yield _await(lambda: any((a.get_actor_location() - rest).length() < SAME_PLACE_CM
                             for a in _in_world(p)), 10.0)
    if p.posted("server", "release"):
        _check_flight(p, "the axe client 1 threw", watch.frames,
                      p.posted("server", "release"), at_rest, rested, since=clicked)
    if p.client == 1 and watch.frames:
        first = next((at for _w, _t, shown, _f in watch.frames
                      for kind, at in shown if kind == TW.STANDIN), None)
        start = unreal.Vector(*p.posted("server", "release")[1]) \
            if p.posted("server", "release") else None
        gap = (unreal.Vector(*first) - start).length() if first and start else -1.0
        p.check("...client 1's own leaves its hand on its click, not on the server's "
                "word: first shown at the start of the curve",
                0.0 <= gap < 100.0, f"{gap:.0f} cm from the start")
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

    yield _watching(p, sample, lambda: p.posted("client 2", "taken"), 90.0)
    yield _watching(p, sample, lambda: not _in_world(p), 10.0)
    p.check(f"{p.where} sees no axe left in the tree once it is taken",
            not _in_world(p), f"{len(_in_world(p))} still shown")
    if p.client == 1:
        p.check("...and client 1 has none: its axe is client 2's now",
                len(_axes(p, wc)) == mine_axes - 1, f"{len(_axes(p, wc))} axe(s)")
    # The server's last throw is made by this probe's Python, under which no
    # event leaves the machine (the editor's script guard makes every call
    # local), so no client is told of its launch: it is the case of a launch
    # that never came, and the item's copy must still not be seen in the air.
    yield _watching(p, sample, lambda: p.posted("server", "judged") is not None, 30.0)
    p.check(f"{p.where} never showed the server's own actor in the air, in either "
            "throw: not the axe it flew a stand-in for, and not the last item, whose "
            "launch it was never told of", not aloft and len(watch.frames) > FLIGHT_PLACES,
            f"shown in the air {len(aloft)} time(s) over {len(watch.frames)} frame(s)")


def _refused(p, wc, axe, mine_axes):
    """Client 1 clicks while the server's copy of its hand is empty: the
    stand-in it predicts is taken back, and the axe is in its hand."""
    watch = _watch(p, wc)
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield _watching(p, watch.sample, lambda: p.get(wc, WV.ThrowFlyer) is not None, 5.0)
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    yield _watching(p, watch.sample, lambda: p.get(wc, WV.ThrowFlyer) is None, 10.0)
    yield _watching(p, watch.sample, lambda: False, 0.5)
    flew = TW.places(watch.frames)
    p.check("client 1's click flies its stand-in at once, before the server has "
            "answered", flew >= 1, f"shown at {flew} place(s)")
    held = p.get(wc, "Held")
    p.check("...and the server's refusal takes it back: no stand-in, the axe shown "
            "in the hand again and still carried",
            p.get(wc, WV.ThrowFlyer) is None and held == axe
            and not held.get_editor_property("hidden") and len(_axes(p, wc)) == mine_axes,
            f"stand-in {p.get(wc, WV.ThrowFlyer)}, Held {held}, "
            f"{len(_axes(p, wc))} of {mine_axes} axe(s)")
    wrong = TW.miscounts(watch.frames)
    p.check("...one axe shown on every frame of it: in the hand, in the air, in the "
            "hand", not wrong, f"{len(wrong)} frame(s) of another count {wrong[:4]}")
