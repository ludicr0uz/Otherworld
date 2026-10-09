"""Two players see each other walk and jump: the engine's stock replication.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_see_each_other.py

Client 1 walks a few metres and jumps; client 2 watches client 1's character
arrive at the same place and leave the ground; the server, which owns the
state, has it there too. Then the two swap. Nothing here is the game's own
networking: a Character replicates its movement by default, and this is the
proof that the player's Blueprint, as built for single player, still does.

The steps go round the board (probes/net.py), each mover posting where it is:

    client k   "start"    it sees the other's character; where its own stands
    client k   "walked"   where it stopped
    watcher    "saw-walk-k"
    client k   "jumped"   how high it rose, and it has landed
"""

SYSTEMS = ('net',)

import time

import unreal

RUNS_ON = ("server", "client")

WAIT = 30.0             # wall seconds any one step may take
WALK_CM = 300.0         # how far a mover walks
WALK_MIN_CM = 150.0     # ... and the least that counts as having walked
NEAR_CM = 60.0          # two machines agree on a place within this
JUMP_MIN_CM = 25.0      # the least rise that counts as a jump (the stock one is ~1 m)
SETTLE_S = 0.5          # wall seconds a stopped character takes to stand still everywhere


def _await(ready, seconds=WAIT):
    """Yield until ``ready()`` or ``seconds`` of wall time: the check after it
    says which, where a bare wait would time the whole probe out."""
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _xyz(actor):
    v = actor.get_actor_location()
    return [v.x, v.y, v.z]


def _flat(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _others(p, mine):
    """The other players' characters in this process's world: every actor of
    the player's class but its own. (A wanderer is another class.)"""
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), mine.get_class())
            if a != mine]


def _move(p, me, other):
    """This client's turn: walk away from the other player, stop, jump."""
    k = p.client
    start = _xyz(me)
    away = unreal.Vector(start[0] - _xyz(other)[0], start[1] - _xyz(other)[1], 0.0)
    away = away.normal() if away.length() > 1.0 else me.get_actor_forward_vector()

    def walking():
        me.add_movement_input(away, 1.0)
        return _flat(_xyz(me), start) >= WALK_CM
    yield from _await(walking, 12.0)
    yield from _await(lambda: False, SETTLE_S)
    stopped = _xyz(me)
    p.check(f"{p.where} walked", _flat(stopped, start) >= WALK_MIN_CM,
            f"{_flat(stopped, start):.0f} cm from its start")
    p.post("walked", stopped)

    yield from _await(lambda: p.posted(f"client {3 - k}", f"saw-walk-{k}"))
    ground = _xyz(me)[2]
    peak = [ground]
    me.jump()

    movement = me.get_movement_component()

    def landed():
        peak[0] = max(peak[0], _xyz(me)[2])
        return peak[0] - ground >= JUMP_MIN_CM and not movement.is_falling()
    yield from _await(landed, 10.0)
    me.stop_jumping()
    p.check(f"{p.where} jumped", peak[0] - ground >= JUMP_MIN_CM,
            f"rose {peak[0] - ground:.0f} cm")
    p.post("jumped", peak[0] - ground)


def _watch(p, other):
    """The other client's turn, seen from here."""
    k = 3 - p.client
    mover = f"client {k}"
    before = _xyz(other)
    yield from _await(lambda: p.posted(mover, "walked"))
    there = p.posted(mover, "walked")
    if not p.check(f"{p.where} heard that {mover} walked", bool(there), "its 'walked' post"):
        return
    yield from _await(lambda: _flat(_xyz(other), there) <= NEAR_CM)
    seen = _xyz(other)
    p.check(f"{p.where} sees {mover}'s character at the new place",
            _flat(seen, there) <= NEAR_CM,
            f"{_flat(seen, there):.0f} cm from where {mover} says it stands")
    p.check(f"{p.where} saw {mover}'s character move",
            _flat(seen, before) >= WALK_MIN_CM, f"{_flat(seen, before):.0f} cm")

    ground = seen[2]
    peak = [ground]

    def landed():
        peak[0] = max(peak[0], _xyz(other)[2])
        return p.posted(mover, "jumped") is not None
    p.post(f"saw-walk-{k}")
    yield from _await(landed)
    p.check(f"{p.where} saw {mover}'s character jump", peak[0] - ground >= JUMP_MIN_CM,
            f"rose {peak[0] - ground:.0f} cm here, {p.posted(mover, 'jumped') or 0:.0f} cm there")


def probe_client(p):
    if p.clients != 2:
        p.check("this probe wants two clients", False, f"--clients {p.clients}")
        return
    yield from _await(lambda: p.pawn() and _others(p, p.pawn()))
    me = p.pawn()
    others = _others(p, me) if me else []
    if not p.check(f"{p.where} sees the other player's character", len(others) == 1,
                   f"{len(others)} other character(s) of its class"):
        return
    other = others[0]
    p.check(f"{p.where} does not control the other's character",
            me.is_locally_controlled() and not other.is_locally_controlled(),
            f"mine {me.get_name()}, the other's {other.get_name()}")
    p.post("start", _xyz(me))
    # Both must see each other before anyone moves: a late joiner would miss it.
    yield from _await(lambda: p.posted(f"client {3 - p.client}", "start"))
    if p.client == 1:
        yield from _move(p, me, other)
        yield from _watch(p, other)
    else:
        yield from _watch(p, other)
        yield from _move(p, me, other)


def probe_server(p):
    """The server owns the state: each mover's character is where it says."""
    if p.clients != 2:
        return
    for k in (1, 2):
        mover = f"client {k}"
        yield from _await(lambda: p.posted(mover, "walked"), 3 * WAIT)
        there = p.posted(mover, "walked")
        if not p.check(f"the server heard that {mover} walked", bool(there), "its 'walked' post"):
            continue

        def nearest():
            pawns = [c.get_controlled_pawn() for c in p.players()]
            return min((_flat(_xyz(pawn), there) for pawn in pawns if pawn), default=1e9)
        yield from _await(lambda: nearest() <= NEAR_CM)
        p.check(f"the server has {mover}'s character at the new place", nearest() <= NEAR_CM,
                f"{nearest():.0f} cm from where {mover} says it stands")
        yield from _await(lambda: p.posted(mover, "jumped") is not None, 3 * WAIT)
