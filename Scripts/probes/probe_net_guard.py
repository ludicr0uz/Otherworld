"""Every Server event checks what it is told and how often (task A5): the
RPC guard (net/guard.py, net/guard_consts.py, C++ UOtherworldRpcGuard).

    server     gives client 1's gun the fastest gun's fire interval and rounds
               to spare, and watches its guard's counters
    client 1   sends Server_Fire with an AimPoint ahead of itself, then one
               behind itself: the first spends a round on the server, the
               second is refused and the round goes nowhere
    client 1   holds the trigger (FireForced): it asks at the gun's rate and
               the guard refuses none of it
    client 1   sends FLOOD_SHOTS Server_Fire in one frame: the guard lets a
               burst through and refuses the rest, and the gun fires at its
               own rate
    client 1   sends FLOOD_ASKS AskSlot in a second: the server closes its
               connection (ClosedByRpcGuard, RPC-KICKED in the server's log)
    client 2   is still in the game

A client's Python cannot call a Blueprint Server event so that it travels, so
client 1 sends them with OtherworldNetLibrary.SendServerEvent, which does
what the Blueprint VM does. Run with --clients 2.

Single player (`--game`): a shot at a point behind the player is fired, and a
frame of FLOOD_ASKS AskSlot is served: the guard passes both and counts
nothing.
"""

SYSTEMS = ('net',)

import time

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.ask_consts import ASK_SLOT
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, ITEM_BP_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH)
from combat.shot_vars import SERVER_FIRE, AsksSent, AsksServed
from combat.weapon_component.tick import FIRE_FORCED_VAR
from net import guard_consts as GC

RUNS_ON = ("server", "client", "standalone")
WRITABLE = [(WEAPON_COMP_BP_PATH, FIRE_FORCED_VAR), (HEALTH_BP_PATH, HV.Health),
            (ITEM_BP_PATH, IV.FireInterval), (ITEM_BP_PATH, IV.Loaded)]

WAIT = 30.0
SPARE_HEALTH = 100000.0
ROUNDS = 400
AIM_CM = 2000.0
HOLD_S = 1.5
FLOOD_SHOTS = 50
FLOOD_ASKS = 200
NO_SLOT = 99        # a slot nothing has: the serve refuses it, the guard counts it


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    return lambda: ready() or time.time() > until


def _vec(v):
    return [v.x, v.y, v.z]


def _text(v):
    return f"(X={v.x:.1f},Y={v.y:.1f},Z={v.z:.1f})"


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _guard(actor):
    return actor.get_component_by_class(unreal.OtherworldRpcGuard)


def _counts(guard):
    """(counted, refused, aim refused) of a guard."""
    return tuple(int(guard.get_editor_property(n)) for n in ("counted", "refused", "aim_refused"))


def _send(wc, event, *args):
    return unreal.OtherworldNetLibrary.send_server_event(wc, event, [str(a) for a in args])


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield _await(lambda: p.posted("client 1", "pos"))
    here = p.posted("client 1", "pos")
    if not here:
        p.check("client 1 said where it stands", False, "no post")
        return
    health = p.load_class(HEALTH_CLASS_PATH)
    players = [c.get_controlled_pawn() for c in p.players() if c.get_controlled_pawn()]
    for body in players:
        p.set(body.get_component_by_class(health), HV.Health, SPARE_HEALTH)
    at = unreal.Vector(*here)
    shooter = min(players, key=lambda a: (a.get_actor_location() - at).length())
    wc = p.component(shooter, WEAPON_COMP_CLASS_PATH)
    guard = _guard(shooter)
    held = p.get(wc, "Held")
    p.check("client 1's character has the RPC guard on the server, and a gun in hand",
            guard is not None and held is not None, f"{guard}, {held}")
    if guard is None or held is None:
        return
    p.set(held, IV.FireInterval, GC.FASTEST_INTERVAL_S)
    p.set(held, IV.Loaded, ROUNDS)
    loaded = lambda: int(p.get(held, IV.Loaded))
    served = lambda: int(p.get(wc, AsksServed))
    p.post("ready")

    # --- the aim ------------------------------------------------------------
    base = served()
    yield _await(lambda: p.posted("client 1", "ahead") and served() > base)
    yield 0.2
    p.check(f"a {SERVER_FIRE} at a point ahead of client 1 spends a round on the server",
            loaded() == ROUNDS - 1 and _counts(guard)[2] == 0,
            f"Loaded {ROUNDS} -> {loaded()}, {_counts(guard)[2]} aim(s) refused")
    before, base = loaded(), served()
    p.post("ahead judged")
    yield _await(lambda: p.posted("client 1", "behind") and served() > base)
    yield 0.2
    p.check(f"...and one at a point behind it is refused (the guard's AimAllowed): the "
            "round goes nowhere, and the ask is still counted served",
            loaded() == before and _counts(guard)[2] == 1 and served() == base + 1,
            f"Loaded {before} -> {loaded()}, {_counts(guard)[2]} aim(s) refused, "
            f"served {base} -> {served()}")

    # --- the trigger held ---------------------------------------------------
    before, was = loaded(), _counts(guard)
    p.post("aim judged")
    yield _await(lambda: p.posted("client 1", "held"))
    sent, seconds = p.posted("client 1", "held") or (0, 0.0)
    yield 0.3
    now = _counts(guard)
    most = seconds * GC.FIRE_RATE + 1
    p.check(f"the trigger held for {seconds:.2f} s asks at the gun's rate and no more "
            f"({1 / GC.FASTEST_INTERVAL_S:.1f}/s; the guard's bucket is {GC.FIRE_RATE:.1f}/s)",
            3 <= sent <= most and now[0] - was[0] >= sent,
            f"{sent} asks sent ({now[0] - was[0]} requests counted, of any kind); at most {most:.0f}")
    p.check("...none of them refused by the guard, and the server fired them",
            now[1] == was[1] and sent - 2 <= before - loaded() <= sent,
            f"{now[1] - was[1]} refused, {before - loaded()} of {sent} fired")

    # --- a flood of shots ---------------------------------------------------
    before, was, began = loaded(), _counts(guard), _now(p)
    p.post("held judged")
    yield _await(lambda: p.posted("client 1", "shots") and _counts(guard)[0] - was[0] >= FLOOD_SHOTS)
    took = _now(p) - began
    yield 0.3
    now = _counts(guard)
    counted, refused = now[0] - was[0], now[1] - was[1]
    burst = GC.FIRE_RATE * GC.BURST_S
    p.check(f"{FLOOD_SHOTS} {SERVER_FIRE} in one frame: the guard lets a burst through "
            f"({burst:.0f}) and refuses the rest",
            counted >= FLOOD_SHOTS and 1 <= counted - refused <= burst + 3,
            f"{counted} requests counted, {refused} refused")
    most = (took + 0.3) / GC.FASTEST_INTERVAL_S + 2
    p.check("...and the gun fires at its own rate: the cooldown is the server's",
            1 <= before - loaded() <= most,
            f"{before - loaded()} round(s) in {took:.2f} s; at most {most:.0f}")
    p.check("...which is not yet a kick", not guard.get_editor_property("kicked")
            and shooter.get_controller() is not None, f"{refused} refusals")

    # --- a flood of asks: the kick ------------------------------------------
    joined = len(p.players())
    seen = {"kicked": False, "refused": 0}

    def gone():
        try:
            seen["kicked"] = seen["kicked"] or bool(guard.get_editor_property("kicked"))
            seen["refused"] = max(seen["refused"], _counts(guard)[1] - now[1])
        except Exception:
            pass
        return seen["kicked"] and len(p.players()) < joined

    p.post("shots judged")
    yield _await(gone, 60.0)
    p.check(f"{FLOOD_ASKS} {ASK_SLOT} in a second get client 1 kicked: more than "
            f"{GC.KICK_REFUSALS} refusals in {GC.KICK_S:g} s close the connection "
            f"({GC.CLOSE_REASON})", seen["kicked"], f"{seen['refused']} refused")
    p.check("...and the server has one player fewer", len(p.players()) == joined - 1,
            f"{joined} -> {len(p.players())}")
    p.post("kicked")
    yield 1.0


# ─── the clients ─────────────────────────────────────────────────────────────

def probe_client(p):
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    yield 0.5
    if p.client != 1:
        yield _await(lambda: p.posted("server", "kicked"), 150.0)
        yield 0.5
        world = p.world()
        p.check(f"{p.where} is still in the server's game after client 1 was kicked",
                bool(p.posted("server", "kicked")) and unreal.SystemLibrary.is_valid(p.pawn())
                and not unreal.SystemLibrary.is_standalone(world), "")
        return

    held = p.get(wc, "Held")
    p.post("pos", _vec(mine.get_actor_location()))
    yield _await(lambda: p.posted("server", "ready") and int(p.get(held, IV.Loaded)) == ROUNDS)
    p.set(held, IV.FireInterval, GC.FASTEST_INTERVAL_S)
    look = p.controller().get_control_rotation()
    forward = unreal.MathLibrary.get_forward_vector(unreal.Rotator(pitch=0.0, yaw=look.yaw, roll=0.0))
    eyes = mine.get_actor_location() + unreal.Vector(0.0, 0.0, 60.0)
    ahead, behind = eyes + forward * AIM_CM, eyes - forward * AIM_CM

    # --- the aim ------------------------------------------------------------
    ok = _send(wc, SERVER_FIRE, _text(ahead))
    p.check(f"client 1 sends {SERVER_FIRE} itself (SendServerEvent)", ok, "")
    p.post("ahead")
    yield _await(lambda: p.posted("server", "ahead judged"))
    _send(wc, SERVER_FIRE, _text(behind))
    p.post("behind")
    yield _await(lambda: p.posted("server", "aim judged"))

    # --- the trigger held ---------------------------------------------------
    yield 1.5       # the bucket full again
    sent, began = int(p.get(wc, AsksSent)), _now(p)
    p.set(wc, FIRE_FORCED_VAR, True)
    yield HOLD_S
    p.set(wc, FIRE_FORCED_VAR, False)
    took = _now(p) - began
    yield 0.2
    p.post("held", [int(p.get(wc, AsksSent)) - sent, took])
    yield _await(lambda: p.posted("server", "held judged"))

    # --- a flood of shots ---------------------------------------------------
    yield 1.5
    for _ in range(FLOOD_SHOTS):
        _send(wc, SERVER_FIRE, _text(ahead))
    p.post("shots")
    yield _await(lambda: p.posted("server", "shots judged"))

    # --- a flood of asks ----------------------------------------------------
    # The refused shots have left the guard's window: the kick is the asks' own.
    yield GC.KICK_S + 0.5
    for _ in range(4):
        for _ in range(FLOOD_ASKS // 4):
            _send(wc, ASK_SLOT, NO_SLOT)
        yield 0.1
    yield _await(lambda: p.posted("server", "kicked"), 40.0)
    # By the wall clock: back on the title, the game is paused.
    yield _await(lambda: False, 3.0)
    try:
        alone = unreal.SystemLibrary.is_standalone(p.world())
    except Exception as e:
        alone = repr(e)
    p.check("client 1 is no longer a client of the server: back in a game of its own",
            bool(p.posted("server", "kicked")) and alone is True, f"standalone: {alone}")


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    yield 0.5
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    guard, held = _guard(mine), p.get(wc, "Held")
    p.check("standalone: the player has the RPC guard", guard is not None, str(guard))
    if guard is None:
        return
    yield _await(lambda: _now(p) > p.get(held, IV.NextFireTime) + 0.2)
    before = int(p.get(held, IV.Loaded))
    behind = mine.get_actor_location() - mine.get_actor_forward_vector() * AIM_CM
    wc.call_method(SERVER_FIRE, (behind,))
    p.check("standalone: a shot at a point behind the player is fired (the guard "
            "passes: nothing came over a wire)", int(p.get(held, IV.Loaded)) == before - 1,
            f"Loaded {before} -> {int(p.get(held, IV.Loaded))}")
    for _ in range(FLOOD_ASKS):
        wc.call_method(ASK_SLOT, (NO_SLOT,))
    yield 0.3
    p.check(f"...and {FLOOD_ASKS} {ASK_SLOT} in a frame are refused nothing, counted "
            "nowhere", _counts(guard) == (0, 0, 0) and not guard.get_editor_property("kicked"),
            f"counted, refused, aim refused = {_counts(guard)}")
