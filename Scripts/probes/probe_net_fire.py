"""The shot and the reload are the server's (task M19): the owning client
asks, predicts its own round, and the server traces, hurts and spends.

    server     stands a wanderer 4 m in front of client 1 and holds it there
    client 1   brings the sights up, rests them on it and forces the fire key
               until its copy of the wanderer is dead: each press spends a round on its own
               copy at once (the prediction). Then it forces the reload key.
               When the server has answered every ask (AsksServed has caught
               up with AsksSent) it posts its rounds
    server     saw client 1 aim down the sights, and its own cloud for that
               gun close (the shot is drawn in the server's cloud); every
               body's mesh refreshes its bones (server_pose.py)
    server     the wanderer is dead, by client 1's hand; its copy of client
               1's gun holds exactly the rounds client 1 counts, loaded and in
               reserve; it served as many asks as client 1 sent; its gun is
               where client 1's is. Then three more Server_Fire in one frame
               spend one round: the cooldown is the server's
    client 2   sees the wanderer dead, and its own gun untouched

Single player (`--game`): one press is one round and one served ask, with no
prediction (AsksSent stays 0), and the reload key fills the magazine.

FireForced, ReloadForced and SightsForced stand in for the keys. The server
gives both players health to spare: the shots draw the pack.
"""

SYSTEMS = ('net',)

import time

import unreal

from combat import health_vars as HV
from combat.game_state import DAMAGED_BY_PLAYER_VAR
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.weapon_component.accuracy import AIM_SPREAD_VAR
from combat.shot_vars import SERVER_FIRE, AsksSent, AsksServed, ReloadForced
from combat.weapon_component.tick import FIRE_FORCED_VAR

RUNS_ON = ("server", "client", "standalone")
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (FIRE_FORCED_VAR, ReloadForced, SIGHTS_FORCED_VAR)] + [(HEALTH_BP_PATH, HV.Health)]

WAIT = 30.0
AHEAD_CM = 400.0
AIM_NEAR_CM = 70.0
MAX_ROUNDS = 5
SIGHTS_SPREAD_DEG = 0.1     # the cloud down the sights: none
SPARE_HEALTH = 100000.0
GUN_NEAR_CM = 60.0
HAND_MOVED_CM = 10.0


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    return lambda: ready() or time.time() > until


def _vec(v):
    return [v.x, v.y, v.z]


def _health(p, actor):
    return p.component(actor, HEALTH_CLASS_PATH)


def _bodies(p):
    """(players', wanderers'): every character with a health component."""
    cls = p.load_class(HEALTH_CLASS_PATH)
    found = [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), unreal.Character) if a.get_component_by_class(cls)]
    mine = [a for a in found if not p.get(_health(p, a), HV.DespawnOnDeath)]
    return mine, [a for a in found if a not in mine]


def _nearest(actors, point):
    at = unreal.Vector(*point)
    return min(actors, key=lambda a: (a.get_actor_location() - at).length(), default=None)


def _gun(p, wc):
    held = p.get(wc, "Held")
    return held, (int(p.get(held, "Loaded")), int(p.get(held, "Reserve"))) if held else None


def _asks(p, wc):
    return int(p.get(wc, AsksSent)), int(p.get(wc, AsksServed))


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield _await(lambda: p.posted("client 1", "pos"))
    posted = p.posted("client 1", "pos")
    if not posted:
        p.check("client 1 said where it stands", False, "no post")
        return
    here, forward = posted
    players, wanderers = _bodies(p)
    shooter = _nearest(players, here)
    wc = p.component(shooter, WEAPON_COMP_CLASS_PATH)
    held, start = _gun(p, wc)
    spot = unreal.Vector(*here) + unreal.Vector(*forward) * AHEAD_CM
    npc = _nearest(wanderers, _vec(spot))
    health = _health(p, npc)
    face = unreal.MathLibrary.find_look_at_rotation(spot, unreal.Vector(*here))

    # Client 1's hand in its body's frame, and how far apart it has been seen:
    # down at the carry, up at the sights.
    def hand():
        return shooter.get_actor_transform().inverse_transform_location(
            shooter.mesh.get_socket_location("hand_r"))

    seen = []

    def reach():
        seen.append(hand())
        lo = [min(getattr(v, a) for v in seen) for a in "xyz"]
        hi = [max(getattr(v, a) for v in seen) for a in "xyz"]
        del seen[:]
        seen.extend([unreal.Vector(*lo), unreal.Vector(*hi)])
        return (seen[1] - seen[0]).length()

    moved, cloud = [reach()], [None]
    for body in players:
        p.set(_health(p, body), HV.Health, SPARE_HEALTH)

    def stand():
        moved[0] = reach()
        if p.get(wc, "SightAiming"):
            spread = float(p.get(wc, AIM_SPREAD_VAR))
            cloud[0] = spread if cloud[0] is None else min(cloud[0], spread)
        if not p.get(health, HV.Dead):
            npc.set_actor_location_and_rotation(
                spot, unreal.Rotator(pitch=0.0, yaw=face.yaw, roll=0.0), False, True)
        return False

    stand()
    p.post("target", _vec(spot))
    yield _await(lambda: stand() or p.posted("client 1", "done"), 90.0)
    done = p.posted("client 1", "done")
    if not done:
        p.check("client 1 finished its shots", False, "no post")
        return
    loaded, reserve, sent, gun_at = done
    yield 0.3

    p.check("the wanderer client 1 shot is dead on the server, by a player's hand",
            bool(p.get(health, HV.Dead)) and bool(p.get(health, DAMAGED_BY_PLAYER_VAR)),
            f"Health {p.get(health, HV.Health):.0f}, Dead {p.get(health, HV.Dead)}")
    last = p.get(health, HV.LastInstigator)
    p.check("...and the blow names client 1's controller",
            last is not None and last == shooter.get_controller(), str(last))
    _held, now = _gun(p, wc)
    p.check("the server's copy of the gun holds the rounds client 1 counts: loaded "
            "and in reserve", now == (loaded, reserve),
            f"server {now}, client 1 {(loaded, reserve)}; it started at {start}")
    p.check("the server answered every ask client 1 sent",
            _asks(p, wc)[1] == sent, f"served {_asks(p, wc)[1]}, sent {sent}")
    off = (held.get_actor_location() - unreal.Vector(*gun_at)).length()
    p.check(f"the server's gun is where client 1's is (within {GUN_NEAR_CM:g} cm): "
            "the shot leaves the server's muzzle", off < GUN_NEAR_CM, f"{off:.0f} cm apart")

    p.check("the server saw client 1 aim down the sights, and its own cloud for the "
            "gun closed: the shot is drawn in the server's cloud, not a client's",
            cloud[0] is not None and cloud[0] < SIGHTS_SPREAD_DEG,
            f"the server's AimSpread fell to {cloud[0]} deg")

    # --- the server poses the bodies it judges (combat/server_pose.py) -----------
    always = unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES
    options = [a.mesh.get_editor_property("visibility_based_anim_tick_option")
               for a in players + wanderers]
    p.check("every body on the server refreshes its bones though nothing is drawn "
            "there: the hit bodies and the muzzle follow the animation",
            len(options) >= 3 and all(o == always for o in options),
            f"{sum(o == always for o in options)} of {len(options)}")
    # The gun goes down again a moment after the last shot, if it was up from
    # the start: either way the hand has been in two places.
    yield _await(lambda: stand() or moved[0] > HAND_MOVED_CM, 5.0)
    p.check("...and client 1's hand moved on the server between the carry and the "
            "sights (a body nothing poses keeps its reference pose: 0 cm)",
            moved[0] > HAND_MOVED_CM, f"hand_r seen {moved[0]:.0f} cm apart in the body's frame")

    # --- the cooldown is the server's ------------------------------------------
    world_now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    yield _await(lambda: world_now() > p.get(held, "NextFireTime") + 0.2)
    before = _gun(p, wc)[1][0]
    aim = unreal.Vector(*here) + unreal.Vector(*forward) * 2000.0
    for _ in range(3):
        wc.call_method(SERVER_FIRE, (aim,))
    after = _gun(p, wc)[1][0]
    p.check("three Server_Fire in one frame spend one round: the server keeps the "
            "gun's own rate", before - after == 1 and before > 0, f"{before} -> {after}")
    p.post("judged")


# ─── the clients ─────────────────────────────────────────────────────────────

def _aim(p, wc, point):
    cam = unreal.GameplayStatics.get_player_camera_manager(p.world(), 0)
    for _ in range(4):
        p.controller().set_control_rotation(unreal.MathLibrary.find_look_at_rotation(
            cam.get_camera_location(), point()))
        yield 0.15
    yield _await(lambda: p.get(wc, "AimValid")
                 and (p.get(wc, "AimPoint") - point()).length() < AIM_NEAR_CM, 5.0)


def probe_client(p):
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    yield 0.5
    held, start = _gun(p, wc)
    if held is None:
        p.check(f"{p.where} holds its issued gun", False, "empty hands")
        return
    if p.client == 1:
        p.post("pos", [_vec(mine.get_actor_location()), _vec(mine.get_actor_forward_vector())])
    yield _await(lambda: p.posted("server", "target"))
    spot = p.posted("server", "target")
    yield _await(lambda: _nearest(_bodies(p)[1], spot) is not None and (
        _nearest(_bodies(p)[1], spot).get_actor_location() - unreal.Vector(*spot)).length() < 150.0)
    npc = _nearest(_bodies(p)[1], spot)
    health = _health(p, npc)
    dead = lambda: bool(p.get(health, HV.Dead))

    if p.client != 1:
        yield _await(lambda: p.posted("client 1", "done"), 90.0)
        yield _await(dead, 5.0)
        p.check(f"{p.where} sees the wanderer client 1 shot dead", dead(),
                f"Health {p.get(health, HV.Health):.0f}")
        p.check(f"...and {p.where}'s own gun is untouched", _gun(p, wc)[1] == start,
                f"{start} -> {_gun(p, wc)[1]}")
        return

    # --- client 1 shoots it, down the sights ------------------------------------
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield _await(lambda: p.get(wc, "SightAiming")
                 and float(p.get(wc, AIM_SPREAD_VAR)) < SIGHTS_SPREAD_DEG, 5.0)
    yield 0.5       # ...and the server's copy has eased onto them too
    world_now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    rounds, predicted = 0, True
    while rounds < MAX_ROUNDS and not dead():
        yield from _aim(p, wc, npc.get_actor_location)
        yield _await(lambda: world_now() > p.get(held, "NextFireTime") + 0.05, 5.0)
        was, sent = int(p.get(held, "Loaded")), _asks(p, wc)[0]
        p.set(wc, FIRE_FORCED_VAR, True)
        yield _await(lambda: int(p.get(held, "Loaded")) < was, 3.0)
        p.set(wc, FIRE_FORCED_VAR, False)
        # On this frame, before any answer can have come: the round is spent
        # here and the ask counted.
        predicted = predicted and int(p.get(held, "Loaded")) == was - 1 \
            and _asks(p, wc)[0] == sent + 1
        rounds += 1
        yield _await(dead, 1.0)
    p.set(wc, SIGHTS_FORCED_VAR, False)
    p.check("each press spends a round on client 1's own copy at once and counts "
            "one ask: the prediction", rounds > 0 and predicted,
            f"{rounds} round(s), {start} -> {_gun(p, wc)[1]}")
    p.check("client 1 sees the wanderer it shot dead: the server traced the shot "
            "and the kill replicated", dead(),
            f"Health {p.get(health, HV.Health):.0f} after {rounds} round(s)")

    # --- and reloads ------------------------------------------------------------
    yield _await(lambda: _asks(p, wc)[0] <= _asks(p, wc)[1], 5.0)
    yield 0.3
    before = _gun(p, wc)[1]
    p.set(wc, ReloadForced, True)
    yield _await(lambda: _gun(p, wc)[1] != before, 3.0)
    p.set(wc, ReloadForced, False)
    after = _gun(p, wc)[1]
    p.check("the reload key fills client 1's own copy at once, out of its reserve",
            after[0] > before[0] and sum(after) == sum(before), f"{before} -> {after}")

    yield _await(lambda: _asks(p, wc)[0] <= _asks(p, wc)[1], 5.0)
    yield 0.5
    sent, served = _asks(p, wc)
    p.check("the server answers every ask: AsksServed catches up with AsksSent",
            sent == served == rounds + 1, f"sent {sent}, served {served}")
    final = _gun(p, wc)[1]
    p.check("...and the server's record leaves client 1's rounds as it predicted them",
            final == after, f"predicted {after}, now {final}")
    p.post("done", [final[0], final[1], sent, _vec(held.get_actor_location())])
    yield _await(lambda: p.posted("server", "judged"))


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    yield 0.5
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    held, start = _gun(p, wc)
    p.set(wc, FIRE_FORCED_VAR, True)
    yield _await(lambda: _gun(p, wc)[1] != start, 5.0)
    p.set(wc, FIRE_FORCED_VAR, False)
    shot = _gun(p, wc)[1]
    p.check("standalone: one press of fire is one round", shot == (start[0] - 1, start[1]),
            f"{start} -> {shot}")
    p.check("...asked of this machine and served by it, with nothing predicted",
            _asks(p, wc) == (0, 1), f"sent, served = {_asks(p, wc)}")
    p.set(wc, ReloadForced, True)
    yield _await(lambda: _gun(p, wc)[1] != shot, 5.0)
    p.set(wc, ReloadForced, False)
    full = _gun(p, wc)[1]
    p.check("and the reload key fills the magazine out of the reserve",
            full[0] == start[0] and sum(full) == sum(shot), f"{shot} -> {full}")
