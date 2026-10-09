"""Random rolls happen once, on the server (M17): every machine sees the same
contents on a body, and they are the server's roll, not its own.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_loot_roll.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_net_loot_roll.py    # single player

loot/roll.py (the roll, on the kill's arm of BP_HealthComponent, behind the
Tick's authority switch), net/CLAUDE.md ("Random rolls"). The server stands
the wanderers round the players and kills them all in a player's name. Two of
them are loaded, each machine its own way, so a copy that rolled for itself
would show it:

    "sure"    the server's chance is 1, each client's copy's is 0: the body
              carries exactly one canteen everywhere (two would be two rolls,
              none a client's own)
    "never"   the server's chance is 0, each client's copy's is 1: the body
              carries nothing anywhere
    the rest  the table's own 50%: whatever the server rolled, both clients
              read the same, body by body

Bodies are matched by NpcId, the number the server gives a wanderer: no actor
name is shared between processes.
"""

SYSTEMS = ('net', 'loot')

import math
import time

import unreal

from combat.damage import TAKE_HIT
from combat.game_state import NPC_ID_VAR
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from combat import health_vars as HV
from loot.consts import LOOT_CHANCES_VAR, LOOT_NAMES_VAR, LOOT_VAR

RUNS_ON = ("server", "client", "standalone")
WRITABLE = [(HEALTH_BP_PATH, LOOT_CHANCES_VAR)]

WAIT = 40.0             # wall seconds any one step may take
RING_CM = 900.0         # where the wanderers are stood: round the players, in sight
FATAL = 100000.0
AHEAD = unreal.Vector(1.0, 0.0, 0.0)
CANTEEN = "BP_WaterCanteen_C"


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _health(p, actor):
    return actor.get_component_by_class(p.load_class(HEALTH_CLASS_PATH))


def _numbered(p):
    """{NpcId: health component} of every wanderer this machine has, alive or dead."""
    out = {}
    for c in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Character):
        h = _health(p, c)
        if h is not None and int(p.get(h, NPC_ID_VAR)) > 0:
            out[int(p.get(h, NPC_ID_VAR))] = h
    return out


def _loot(p, h):
    return [c.get_name() for c in p.get(h, LOOT_VAR) if c]


def _carries(p, bodies):
    """{str(NpcId): the classes on the body}, as a board post carries it."""
    return {str(i): _loot(p, h) for i, h in sorted(bodies.items())}


# ─── The server (and single player) rolls ────────────────────────────────────

def _roll(p, watchers):
    """Stand the wanderers round the first player, load two of them and kill
    them all in that player's name; returns {NpcId: health component}, or None."""
    yield from _await(lambda: len(p.players()) >= max(1, p.clients)
                      and all(c.get_controlled_pawn() for c in p.players())
                      and len(_numbered(p)) >= 3)
    bodies = _numbered(p)
    p.check("the level has wanderers, each with the server's number",
            len(bodies) >= 3, f"{len(bodies)}")
    if len(bodies) < 3:
        return None
    killer = p.players()[0]
    centre = killer.get_controlled_pawn().get_actor_location()
    for k, (_i, h) in enumerate(sorted(bodies.items())):
        turn = 2.0 * math.pi * k / len(bodies)
        h.get_owner().set_actor_location(
            centre + unreal.Vector(RING_CM * math.cos(turn), RING_CM * math.sin(turn), 150.0),
            False, True)
    ids = sorted(bodies)
    sure, never = ids[0], ids[1]
    p.post("plan", {"ids": ids, "sure": sure, "never": never})
    yield from _await(lambda: all(p.posted(w, "set") is not None for w in watchers))
    if watchers:
        p.check("every client has its own copy of every wanderer, and has loaded its "
                "two against the server's",
                all(p.posted(w, "set") == len(ids) for w in watchers),
                f"{[p.posted(w, 'set') for w in watchers]} of {len(ids)}")
    p.set(bodies[sure], LOOT_CHANCES_VAR, [1.0])
    p.set(bodies[never], LOOT_CHANCES_VAR, [0.0])
    for h in bodies.values():
        h.call_method(TAKE_HIT, (FATAL, AHEAD, killer, None))
    yield from _await(lambda: all(p.get(h, HV.Dead) for h in bodies.values()))
    yield 0.3
    p.check("every wanderer is dead, killed in a player's name",
            all(p.get(h, HV.Dead) for h in bodies.values()))
    p.check("the body sure to carry a canteen carries exactly one: one roll",
            _loot(p, bodies[sure]) == [CANTEEN]
            and len(p.get(bodies[sure], LOOT_NAMES_VAR)) == 1, str(_loot(p, bodies[sure])))
    p.check("the body sure to carry nothing carries nothing",
            _loot(p, bodies[never]) == [], str(_loot(p, bodies[never])))
    p.check("no body carries more than the table can give it (one roll per entry)",
            all(len(_loot(p, h)) <= 1 for h in bodies.values()), str(_carries(p, bodies)))
    return bodies


def probe_server(p):
    watchers = [f"client {i}" for i in range(1, p.clients + 1)]
    bodies = yield from _roll(p, watchers)
    if bodies is None:
        p.post("rolled", {})
        return
    rolled = _carries(p, bodies)
    full = sum(1 for v in rolled.values() if v)
    p.note(f"the server rolled a canteen onto {full} of {len(rolled)} bodies")
    p.post("rolled", rolled)
    yield from _await(lambda: all(p.posted(w, "read") is not None for w in watchers))
    for w in watchers:
        p.check(f"{w} reads on every body what the server rolled",
                p.posted(w, "read") == rolled, f"{p.posted(w, 'read')} / {rolled}")
    p.check("the server's bodies are as it rolled them after the clients read them",
            _carries(p, bodies) == rolled)


def probe_client(p):
    yield from _await(lambda: p.posted("server", "plan") is not None, 120.0)
    plan = p.posted("server", "plan")
    if not plan:
        p.check("the server's plan arrived", False)
        p.post("set", 0)
        p.post("read", {})
        return
    ids = [int(i) for i in plan["ids"]]
    yield from _await(lambda: set(ids) <= set(_numbered(p)))
    mine = {i: h for i, h in _numbered(p).items() if i in ids}
    p.check("this client has a copy of every wanderer the server numbered",
            len(mine) == len(ids), f"{sorted(mine)} of {ids}")
    # Loaded the other way round from the server: a roll made here would show.
    if plan["sure"] in mine:
        p.set(mine[plan["sure"]], LOOT_CHANCES_VAR, [0.0])
    if plan["never"] in mine:
        p.set(mine[plan["never"]], LOOT_CHANCES_VAR, [1.0])
    p.post("set", len(mine))

    yield from _await(lambda: p.posted("server", "rolled") is not None, 120.0)
    rolled = p.posted("server", "rolled") or {}
    yield from _await(lambda: _carries(p, mine) == rolled
                      and all(p.get(h, HV.Dead) for h in mine.values()))
    yield 1.0       # a roll of this copy's own would have landed by now
    read = _carries(p, mine)
    p.check("every body is dead here too", all(p.get(h, HV.Dead) for h in mine.values()))
    p.check("every body carries here what the server rolled onto it",
            read == rolled and len(rolled) == len(ids), f"{read} / {rolled}")
    if plan["sure"] in mine:
        p.check("the body this copy would never have given a canteen carries the "
                "server's one, with its name",
                _loot(p, mine[plan["sure"]]) == [CANTEEN]
                and len(p.get(mine[plan["sure"]], LOOT_NAMES_VAR)) == 1,
                str(_loot(p, mine[plan["sure"]])))
    if plan["never"] in mine:
        p.check("the body this copy would always have given a canteen carries nothing",
                _loot(p, mine[plan["never"]]) == [], str(_loot(p, mine[plan["never"]])))
    p.post("read", read)


def probe(p):
    """Single player is the machine with authority: the same roll, made here."""
    yield from _roll(p, ())
