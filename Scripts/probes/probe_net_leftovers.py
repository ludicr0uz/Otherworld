"""What is left in the world is there for a latecomer, and does not pile up
(task M31): client 2 joins after client 1's character set an item down,
lodged its axe in a tree and killed a wanderer, and sees all three; then the
server's cleanup rule takes them away.

    python3 Scripts/dev/uepy.py --net --title --clients 2 --probe-timeout 420 \\
        --probe Scripts/probes/probe_net_leftovers.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_net_leftovers.py

``--title``: each client starts alone on its level and joins when its probe
says (boot.py starts the server's probe with the first player). Client 1
joins at once; client 2 joins LATE_S after the server says the three are
done. The corpse lies CORPSE_SECONDS (60), so the kill comes last and the
join is soon after it.

    server     with client 1's character, as its Server events do: AskDrop of
               the matches (they lie at its feet), Server_Throw of the axe at
               a trunk (it lodges), a wanderer stood beside it and killed.
               Each is noted on the server's list of leftovers by its row of
               net/leftover_consts.py; the level's own items are not
    client 1   joins; sees the three
    client 2   waits LATE_S after "done", joins, is stood at the trunk: the
               matches on the ground, the axe in the bark and the wanderer
               dead and collapsed, each where the server has it
    server     the cleanup rule, with the lifetime and the cap brought down
               to what a probe can wait for (the same call a graph makes,
               with other numbers): the matches' lifetime runs out and they
               are destroyed; an item taken back is struck off the list and
               noted again when set down; with one more than the cap lying,
               the oldest (the axe in the tree) goes
    clients    each sees the matches gone, then the axe gone and the last
               item still lying

The item, the throw and the corpse are what M20, M23 and M14 proved for
players who were there (probe_net_take.py, probe_net_throw.py,
probe_net_health.py); this is the one who was not, and the rule.

In single player (the ``--game`` arm) nothing is noted and nothing is cleaned
up: an item set down has no lifetime, and the call that would give it one
does nothing.
"""

SYSTEMS = ('net',)

import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.death import CORPSE_SECONDS
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.record_vars import DropForced, SlotForced
from combat.slot_tuning import SLOT_VAR
from combat.strike_vars import SERVER_TAKE, SERVER_THROW
from combat.throw_tuning import LODGE_MAX_HEIGHT_CM, THROW_MELEE_PITCH_UP_DEG, THROW_SPEED_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.throw_flight import THROWN_VAR
from net.leftover_consts import CORPSE, ITEM
from probes.probe_campfire import MATCHES
from probes.probe_chop_tree import AXE, CLEAR_CM, _flat, _items, _trees
from probes.probe_hot_blade import _wanderers
from probes.probe_net_late_join import _await, _bag, _level_actor, _name, _to_hand, _vec
from probes.probe_throw_strike import ON_GROUND_CM, _dir, _launch, _spot

WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in (SlotForced, DropForced, WV.EquippedIndex)]
            + [(HEALTH_BP_PATH, HV.Health)])
LEFT = unreal.OtherworldLeftoverLibrary

SPARE_HEALTH = 100000.0   # a wanderer that comes later must not kill a player mid-probe
LATE_S = 5.0              # how long after the three client 2 joins (the corpse lies 60 s)
JOIN_S = 90.0             # a join, wall seconds
SAME_PLACE_CM = 25.0      # a client's copy of an item, from the server's
CORPSE_NEAR_CM = 400.0    # a client's copy of the corpse's capsule, from the server's
BESIDE_CM = 200.0         # where the wanderer is stood from client 1, and client 2 behind it
SHORT_S = 3.0             # the lifetime the probe gives the matches
NOT_NOTED = -1.0          # LeftLifetime of an actor that is not on the list


def _lying(p, name):
    """The items of the class this machine shows lying or lodged in the world."""
    return [a for a in _items(p, name)
            if p.get(a, IV.Dropped) and not a.get_editor_property("hidden")]


def _alive(actor):
    try:
        return bool(unreal.SystemLibrary.is_valid(actor))
    except Exception:       # a wrapper of a destroyed actor
        return False


def _noted(actor):
    return float(LEFT.left_lifetime(actor))


def _health(p, body):
    return p.component(body, HEALTH_CLASS_PATH)


def _corpses(p):
    """The wanderers' bodies this machine shows dead: (body, its health)."""
    out = []
    for body in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Character):
        health = body.get_component_by_class(p.load_class(HEALTH_CLASS_PATH))
        if health and p.get(health, HV.DespawnOnDeath) and p.get(health, HV.Dead):
            out.append((body, health))
    return out


def _bodies_seen(p, where):
    """What this machine has of the wanderers, for a failed check's text."""
    cls = p.load_class(HEALTH_CLASS_PATH)
    at = unreal.Vector(*where["corpse"])
    rows = []
    for body in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Character):
        health = body.get_component_by_class(cls)
        rows.append((round((body.get_actor_location() - at).length()),
                     body.get_class().get_name(), health is not None,
                     bool(health and p.get(health, HV.DespawnOnDeath)),
                     bool(health and p.get(health, HV.Dead))))
    return (f"pawn at {_vec(p.pawn().get_actor_location())}, corpse at {where['corpse']}, "
            f"{len(_items(p))} item(s), characters {sorted(rows)[:6]}")


def _spare(p, wc):
    """An item client 1 still carries that is neither in hand nor a blade."""
    held = p.get(wc, WV.Held)
    return next((i for i in p.get(wc, WV.Inventory)
                 if i != held and _name(i) not in (AXE, MATCHES)), None)


# ─── the server ──────────────────────────────────────────────────────────────

def _leave_three(p, one, wc):
    """Client 1's character sets the matches down, lodges its axe and kills a
    wanderer. Returns (matches, axe, corpse, where each is) or None."""
    # --- a trunk ----------------------------------------------------------------
    lying = [a.get_actor_location() for a in _items(p) if p.get(a, IV.Dropped)]
    here = one.get_actor_location()
    spot = base = None
    for _comp, _index, base in sorted(_trees(p), key=lambda t: (t[2] - here).length())[:60]:
        if any(_flat(at - base) < CLEAR_CM for at in lying):
            continue
        spot = _spot(p, one, base)
        if spot:
            break
    p.check("the server found a trunk to stand client 1 at", spot is not None)
    if spot is None:
        return None
    at, yaw, _near, ground, _view = spot
    turn = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    one.set_actor_location_and_rotation(at, turn, False, True)
    yield 0.5

    # --- the item set down --------------------------------------------------------
    matches = next((i for i in p.get(wc, WV.Inventory) if _name(i) == MATCHES), None)
    p.check("client 1 carries matches, and nothing it carries is on the list of "
            "leftovers", matches is not None
            and all(_noted(i) == NOT_NOTED for i in p.get(wc, WV.Inventory)), str(_bag(p, wc)))
    if matches is None:
        return None
    p.ask_drop(wc, p.get(matches, SLOT_VAR))
    yield from _await(lambda: p.get(matches, IV.Dropped) and p.get(matches, IV.InWorld), 10.0)
    yield 0.5
    p.check("the matches client 1 set down lie in the server's world, and are noted "
            f"with the ITEM row's lifetime ({ITEM.lifetime_s:g} s)",
            bool(p.get(matches, IV.Dropped)) and matches not in list(p.get(wc, WV.Inventory))
            and abs(_noted(matches) - ITEM.lifetime_s) < 1e-3,
            f"Dropped {p.get(matches, IV.Dropped)}, noted {_noted(matches)}")

    # --- the axe in the tree --------------------------------------------------------
    yield from _to_hand(p, wc, AXE)
    axe = p.get(wc, WV.Held)
    if _name(axe) != AXE:
        p.check("client 1 brought its axe to hand", False, f"{_name(axe)} in hand")
        return None
    speed = float(p.get(axe, THROW_SPEED_VAR))
    wc.call_method(SERVER_THROW, (_launch(at, yaw), _dir(THROW_MELEE_PITCH_UP_DEG, yaw) * speed))
    yield from _await(lambda: p.get(wc, THROWN_VAR) is None and p.get(axe, IV.Dropped), 10.0)
    yield 0.3
    rest = axe.get_actor_location()
    p.check("client 1's axe, thrown, is in the trunk on the server: Lodged, off the ground",
            bool(p.get(axe, IV.Lodged)) and axe not in list(p.get(wc, WV.Inventory))
            and ON_GROUND_CM < rest.z - ground < LODGE_MAX_HEIGHT_CM + 30.0,
            f"Dropped {p.get(axe, IV.Dropped)}, Lodged {p.get(axe, IV.Lodged)}, "
            f"{rest.z - ground:.0f} cm up")
    p.check("...and noted from the throw's release, a second item left in the world",
            abs(_noted(axe) - ITEM.lifetime_s) < 1e-3
            and LEFT.left_count(p.world(), ITEM.kind) == 2,
            f"noted {_noted(axe)}, {LEFT.left_count(p.world(), ITEM.kind)} item(s) on the list")
    placed = [a for a in _items(p) if _level_actor(a) and p.get(a, IV.Dropped)]
    p.check("the items placed in the level are not: they are the level's, left by no one",
            all(_noted(a) == NOT_NOTED for a in placed), f"{len(placed)} placed item(s)")

    # --- the corpse (last: it lies 60 s) ------------------------------------------------
    yield from _await(lambda: _wanderers(p), 60.0)
    ctrls = _wanderers(p)
    p.check("the server has a wanderer to kill", bool(ctrls), f"{len(ctrls)} wanderer(s)")
    if not ctrls:
        return None
    side = unreal.MathLibrary.get_right_vector(turn)
    prey = min((c.get_controlled_pawn() for c in ctrls),
               key=lambda b: (b.get_actor_location() - at).length())
    for ctrl in ctrls:
        if ctrl.get_controlled_pawn() != prey:
            ctrl.get_controlled_pawn().destroy_actor()
    prey.set_actor_location(at + side * BESIDE_CM + unreal.Vector(0.0, 0.0, 20.0), False, True)
    health = _health(p, prey)
    p.set(health, HV.DamagedByPlayer, True)
    p.set(health, HV.Health, 0.0)
    yield from _await(lambda: p.get(health, HV.Dead), 10.0)
    yield 1.0
    died = time.time()
    p.check("the wanderer beside client 1 is dead on the server, and its body noted as "
            f"a corpse (its own {CORPSE_SECONDS:.0f} s of lifespan, the CORPSE row's cap)",
            bool(p.get(health, HV.Dead)) and abs(_noted(prey) - CORPSE.lifetime_s) < 1e-3
            and LEFT.left_count(p.world(), CORPSE.kind) == 1
            and abs(prey.get_life_span() - CORPSE_SECONDS) < 5.0,
            f"Dead {p.get(health, HV.Dead)}, noted {_noted(prey)}, "
            f"{LEFT.left_count(p.world(), CORPSE.kind)} corpse(s), "
            f"{prey.get_life_span():.0f} s of lifespan left")
    return (matches, axe, prey, died,
            {"at": _vec(at), "yaw": yaw, "matches": _vec(matches.get_actor_location()),
             "axe": _vec(rest), "corpse": _vec(prey.get_actor_location())})


def _cleanup(p, one, wc, matches, axe):
    """The rule, with a probe's numbers: a lifetime that runs out, the take
    that strikes an item off, the cap that the oldest makes room under."""
    world = p.world()
    expired, evicted = LEFT.left_expired(world), LEFT.left_evicted(world)

    # --- the lifetime -------------------------------------------------------------
    LEFT.left_in_world(matches, ITEM.kind, SHORT_S, ITEM.cap)
    yield 1.0
    p.check(f"noted again with {SHORT_S:g} s to lie, the matches are still there a "
            "second on", _alive(matches))
    yield from _await(lambda: not _alive(matches), SHORT_S + 5.0)
    p.check("...and destroyed by the server once the lifetime has run out, one expiry "
            "counted", not _alive(matches) and LEFT.left_expired(world) == expired + 1
            and _alive(axe),
            f"matches alive {_alive(matches)}, {LEFT.left_expired(world) - expired} expired")
    p.post("expired")
    yield from _await(lambda: p.posted("client 1", "saw expired")
                      and p.posted("client 2", "saw expired"), 30.0)

    # --- the take strikes it off; set down again, it is noted again -------------------
    spare = _spare(p, wc)
    p.check("client 1 carries one more thing to set down", spare is not None, str(_bag(p, wc)))
    if spare is None:
        return
    name = _name(spare)
    p.ask_drop(wc, p.get(spare, SLOT_VAR))
    yield from _await(lambda: p.get(spare, IV.Dropped) and p.get(spare, IV.InWorld), 10.0)
    yield 0.5
    first = _noted(spare)
    spare.set_actor_location(one.get_actor_location(), False, True)
    wc.call_method(SERVER_TAKE, (spare,))
    yield 0.5
    carried = _noted(spare)
    back = spare in list(p.get(wc, WV.Inventory))
    p.ask_drop(wc, p.get(spare, SLOT_VAR))
    yield from _await(lambda: p.get(spare, IV.Dropped) and p.get(spare, IV.InWorld), 10.0)
    yield 0.5
    p.check(f"a {name} set down is noted, taken back it is struck off the list (no "
            "lifetime runs on a carried item), set down again it is noted again",
            abs(first - ITEM.lifetime_s) < 1e-3 and back and carried == NOT_NOTED
            and abs(_noted(spare) - ITEM.lifetime_s) < 1e-3,
            f"noted {first}, carried {carried} (in the bag {back}), noted {_noted(spare)}")

    # --- the cap ------------------------------------------------------------------------
    count = LEFT.left_count(world, ITEM.kind)
    p.check("two items are left in the world now: the axe in the tree and the "
            f"{name}", count == 2 and _alive(axe), f"{count} on the list")
    LEFT.left_in_world(spare, ITEM.kind, ITEM.lifetime_s, 1)
    yield 0.5
    p.check("noted with a cap of one, the oldest of the kind makes room: the axe in "
            f"the tree is destroyed, the {name} lies on, one eviction counted",
            not _alive(axe) and _alive(spare) and LEFT.left_count(world, ITEM.kind) == 1
            and LEFT.left_evicted(world) == evicted + 1,
            f"axe alive {_alive(axe)}, {name} alive {_alive(spare)}, "
            f"{LEFT.left_count(world, ITEM.kind)} on the list, "
            f"{LEFT.left_evicted(world) - evicted} evicted")
    p.post("evicted", {"name": name, "at": _vec(spare.get_actor_location())})
    yield from _await(lambda: p.posted("client 1", "saw evicted")
                      and p.posted("client 2", "saw evicted"), 30.0)


def probe_server(p):
    # boot.py starts this once the first player has joined (--title).
    yield from _await(lambda: p.players() and p.players()[0].get_controlled_pawn(), 30.0)
    one = p.players()[0].get_controlled_pawn()
    wc = p.component(one, WEAPON_COMP_CLASS_PATH)
    p.set(_health(p, one), HV.Health, SPARE_HEALTH)
    p.check("this is a server: not standalone", not unreal.SystemLibrary.is_standalone(p.world()))

    left = yield from _leave_three(p, one, wc)
    if left is None:
        return
    matches, axe, prey, died, where = left
    p.post("done", where)

    # --- the late joiner ------------------------------------------------------------
    yield from _await(lambda: len(p.players()) >= 2 and p.players()[1].get_controlled_pawn(),
                      LATE_S + JOIN_S)
    p.check("client 2 joined after the three were left", len(p.players()) >= 2)
    if len(p.players()) < 2:
        return
    two = p.players()[1].get_controlled_pawn()
    p.set(_health(p, two), HV.Health, SPARE_HEALTH)
    turn = unreal.Rotator(pitch=0.0, yaw=where["yaw"], roll=0.0)
    two.set_actor_location_and_rotation(
        unreal.Vector(*where["at"]) - unreal.MathLibrary.get_forward_vector(turn) * BESIDE_CM,
        turn, False, True)
    p.post("beside")
    yield from _await(lambda: p.posted("client 2", "judged"), 60.0)
    lay = time.time() - died
    p.check("client 2 judged its world while the corpse still lay on the server",
            bool(p.posted("client 2", "judged")) and _alive(prey),
            f"{lay:.0f} s after the kill, corpse alive {_alive(prey)}")
    yield from _await(lambda: p.posted("client 1", "judged"), 30.0)

    yield from _cleanup(p, one, wc, matches, axe)

    # --- the corpse goes by its own lifespan, and leaves the list ---------------------
    yield from _await(lambda: not _alive(prey), CORPSE_SECONDS + 10.0)
    yield 1.5      # the list is swept once a second
    p.check(f"the corpse is gone after its {CORPSE_SECONDS:.0f} s, and the list holds "
            "no corpse", not _alive(prey) and LEFT.left_count(p.world(), CORPSE.kind) == 0,
            f"alive {_alive(prey)}, {LEFT.left_count(p.world(), CORPSE.kind)} on the list, "
            f"{time.time() - died:.0f} s after the kill")
    p.post("over")


# ─── the clients ─────────────────────────────────────────────────────────────

def _joined(p):
    world = p.world()
    return (bool(world) and world.get_path_name().startswith(p.map_path)
            and not unreal.SystemLibrary.is_standalone(world) and p.pawn() is not None)


def _join(p):
    """Leave the title for the server; wait until this process stands on the
    server's level with a character of its own."""
    world = p.world()
    unreal.GameplayStatics.set_game_paused(world, False)
    unreal.GameplayStatics.open_level(world, p.net.address, True, "")
    began, until, said = time.time(), time.time() + JOIN_S, [0.0]

    def there():
        try:
            return _joined(p) or time.time() > until
        except Exception as error:      # a world or a pawn mid-travel
            if time.time() - said[0] > 2.0:
                said[0] = time.time()
                unreal.log_warning(f"[PROBE] {p.where} still joining: {error!r}")
            return time.time() > until
    yield there
    p.check(f"{p.where} joined the server from the title", _joined(p),
            f"{time.time() - began:.0f} s")
    return _joined(p)


def _near(actors, point, reach):
    at = unreal.Vector(*point)
    return [a for a in actors if (a.get_actor_location() - at).length() < reach]


def _sees_three(p, where):
    """The matches on the ground, the axe in the bark, the wanderer dead."""
    seen = lambda: (_near(_lying(p, MATCHES), where["matches"], SAME_PLACE_CM)
                    and _near(_lying(p, AXE), where["axe"], SAME_PLACE_CM)
                    and _near([b for b, _h in _corpses(p)], where["corpse"], CORPSE_NEAR_CM))
    yield from _await(seen, 15.0)
    yield 1.0      # the collapse is the next frames' work
    matches = _near(_lying(p, MATCHES), where["matches"], SAME_PLACE_CM)
    p.check(f"{p.where} sees the matches client 1 set down, where the server has them: "
            "the server's actor, sent to it",
            len(matches) == 1 and not matches[0].has_authority(),
            f"{len(matches)} there of {len(_lying(p, MATCHES))} lying; "
            + str([(bool(p.get(a, IV.Dropped)), bool(a.get_editor_property("hidden")),
                    _vec(a.get_actor_location())) for a in _items(p, MATCHES)])
            + f", the server's at {where['matches']}")
    axes = _near(_lying(p, AXE), where["axe"], SAME_PLACE_CM)
    p.check(f"{p.where} sees the axe in the trunk, where the server has it, Lodged",
            len(axes) == 1 and bool(p.get(axes[0], IV.Lodged)) and not axes[0].has_authority(),
            f"{len(axes)} there of {len(_lying(p, AXE))} in the world")
    corpses = [(b, h) for b, h in _corpses(p)
               if (b.get_actor_location() - unreal.Vector(*where["corpse"])).length()
               < CORPSE_NEAR_CM]
    limp = False
    if corpses:
        body, health = corpses[0]
        mesh = body.get_component_by_class(unreal.SkeletalMeshComponent)
        limp = bool(p.get(health, HV.DeathPlayed)) and bool(mesh.is_any_simulating_physics())
    p.check(f"{p.where} sees the wanderer client 1 killed: one body there, Dead, and "
            "collapsed on this machine (its death path ran, the mesh is a ragdoll)",
            len(corpses) == 1 and limp,
            f"{len(corpses)} dead there of {len(_corpses(p))}, collapsed {limp}; "
            + str(_bodies_seen(p, where)))


def _sees_cleanup(p, where):
    yield from _await(lambda: p.posted("server", "expired"), 60.0)
    if not p.posted("server", "expired"):
        return
    gone = lambda: not _near(_lying(p, MATCHES), where["matches"], SAME_PLACE_CM)
    yield from _await(gone, 10.0)
    p.check(f"{p.where} sees the matches gone once their lifetime ran out on the server",
            gone() and len(_near(_lying(p, AXE), where["axe"], SAME_PLACE_CM)) == 1,
            f"{len(_lying(p, MATCHES))} matches lying, {len(_lying(p, AXE))} axe(s)")
    p.post("saw expired")
    yield from _await(lambda: p.posted("server", "evicted"), 60.0)
    last = p.posted("server", "evicted")
    if not last:
        return
    gone = lambda: not _near(_lying(p, AXE), where["axe"], SAME_PLACE_CM)
    yield from _await(gone, 10.0)
    kept = _near(_lying(p, last["name"]), last["at"], SAME_PLACE_CM * 4)
    p.check(f"{p.where} sees the axe gone from the tree once the cap made room, and "
            f"the {last['name']} set down last still lying",
            gone() and len(kept) == 1, f"{len(_lying(p, AXE))} axe(s), {len(kept)} kept")
    p.post("saw evicted")
    yield from _await(lambda: p.posted("server", "over"), CORPSE_SECONDS + 30.0)


def _client_one(p):
    if not (yield from _join(p)):
        return
    yield from _await(lambda: p.posted("server", "done"), 200.0)
    where = p.posted("server", "done")
    if not where:
        p.check("the server left the three", False, "no post")
        return
    yield from _sees_three(p, where)
    p.post("judged")
    yield from _sees_cleanup(p, where)


def _client_two(p):
    yield from _await(lambda: p.posted("server", "done"), 300.0)
    where = p.posted("server", "done")
    if not where:
        p.check("the server left the three", False, "no post")
        return
    p.check("client 2 is still alone on its title while client 1 plays",
            unreal.SystemLibrary.is_standalone(p.world()))
    # Game time stands still on the paused title: the wait is wall time.
    yield from _await(lambda: False, LATE_S)
    if not (yield from _join(p)):
        return
    yield from _await(lambda: p.posted("server", "beside"), 30.0)
    at = unreal.Vector(*where["at"])
    yield from _await(lambda: _flat(p.pawn().get_actor_location() - at) < BESIDE_CM * 2, 10.0)
    yield from _sees_three(p, where)
    p.post("judged")
    yield from _sees_cleanup(p, where)


def probe_client(p):
    if p.client == 1:
        yield from _client_one(p)
    else:
        yield from _client_two(p)


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    """Standalone keeps what is left until it is taken: nothing is noted."""
    one = p.pawn()
    wc = p.component(one, WEAPON_COMP_CLASS_PATH)
    yield from _await(lambda: p.get(wc, WV.Held) is not None, 20.0)
    world = p.world()
    p.check("this is single player: standalone", unreal.SystemLibrary.is_standalone(world))
    spare = _spare(p, wc)
    p.check("the player carries something to set down", spare is not None, str(_bag(p, wc)))
    if spare is None:
        return
    name = _name(spare)
    p.ask_drop(wc, p.get(spare, SLOT_VAR))
    yield from _await(lambda: p.get(spare, IV.Dropped) and p.get(spare, IV.InWorld), 10.0)
    yield 0.5
    p.check(f"a {name} set down lies in the world and is on no list: single player "
            "notes nothing", bool(p.get(spare, IV.Dropped)) and _noted(spare) == NOT_NOTED
            and LEFT.left_count(world, ITEM.kind) == 0,
            f"Dropped {p.get(spare, IV.Dropped)}, noted {_noted(spare)}, "
            f"{LEFT.left_count(world, ITEM.kind)} on the list")
    LEFT.left_in_world(spare, ITEM.kind, 1.0, 1)
    yield 3.0
    p.check("...and the call that gives it a second to lie does nothing here: it is "
            "still there three seconds on, nothing expired, nothing evicted",
            _alive(spare) and bool(p.get(spare, IV.Dropped)) and _noted(spare) == NOT_NOTED
            and LEFT.left_expired(world) == 0 and LEFT.left_evicted(world) == 0,
            f"alive {_alive(spare)}, noted {_noted(spare)}")
