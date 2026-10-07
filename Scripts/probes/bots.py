"""The load test's bots: characters the server drives in a player's place.

``uepy.py --net --bots N`` (UEPY_NET_BOTS, uepylib/net_plan.py) has the
dedicated server spawn N more BP_ThirdPersonCharacter bodies once its level is
up (boot.py calls ``start``), each possessed by the engine's plain AIController
(the character's own AIControllerClass) and told what to do from here, on a
timer of its own: walk to a random reachable point near it, crouch or stand,
and fire at the nearest other living body in range. A bot asks the weapon
component for its shot exactly as a client does -- ``Server_Fire(AimPoint)``,
``Server_Reload`` -- so the server's Tick, the record, the hit history and the
health path run for it as for a player (Scripts/net/CLAUDE.md, "Measured at
scale"). What differs from a player: the aim is a point near the target with
no client prediction or lag to rewind, the gun's reserve is refilled when it
runs dry (REFILL_ROUNDS), and a dead bot gets a new body RESPAWN_S later
while the old one lies for BODY_S, as a player's does.

The driving is Python, from the engine's ticker: a few decisions a frame at
most, each a handful of calls. The probe (probe_net_load.py) reads
``status()`` for how many are alive and what they did.
"""

import os
import random
import time

try:
    import unreal
except ImportError:          # off-engine: count() and WRITABLE are unit-tested
    unreal = None

from combat import health_vars as HV
from combat import item_vars as IV
from combat.paths import (
    CHARACTER_CLASS_PATH, HEALTH_CLASS_PATH, ITEM_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.shot_vars import SERVER_FIRE, SERVER_RELOAD

COUNT_ENV = "UEPY_NET_BOTS"
# The gun's reserve is written when it is empty (boot.py makes it writable).
WRITABLE = [(ITEM_BP_PATH, str(IV.Reserve))]
SPAWN_PER_TICK = 2
SPAWN_RADIUS_CM = 4000.0     # round a PlayerStart
SPAWN_UP_CM = 100.0
WALK_RADIUS_CM = 1500.0
ACCEPT_CM = 50.0
DECIDE_S = (1.5, 3.0)        # the gap between two decisions
FIRE_RANGE_CM = 6000.0
# Round the target: wide enough that most shots miss, as a player's do, so the
# bots are not all dead at once (a shotgun hit kills in one).
AIM_SCATTER_CM = 150.0
CROUCH_CHANCE = 0.3
RESPAWN_S = 10.0
BODY_S = 60.0
REFILL_ROUNDS = 50

_state = {"want": 0, "world": None, "bots": [], "bodies": [], "starts": [],
          "shots": 0, "reloads": 0, "deaths": 0, "spawned": 0, "started": 0.0,
          "errors": {}, "driver_ms": []}


def _log(text):
    unreal.log_warning(f"[BOTS] {text}")


def count(env=None):
    """How many bots the run asked for (0 outside a load run)."""
    try:
        return max(0, int((env or os.environ).get(COUNT_ENV) or 0))
    except ValueError:
        return 0


def status():
    """What the bots are up to, for the probe and the log."""
    alive = sum(1 for b in _state["bots"] if _alive(b))
    return {"want": _state["want"], "alive": alive, "spawned": _state["spawned"],
            "shots": _state["shots"], "reloads": _state["reloads"],
            "deaths": _state["deaths"],
            "seconds": time.time() - _state["started"] if _state["started"] else 0.0}


def take_driver_ms():
    """How long each frame's driving took, in milliseconds, since the last
    call: the harness's own cost, to be read off the server's frame time."""
    taken, _state["driver_ms"] = _state["driver_ms"], []
    return taken


def ready():
    """Every bot asked for has been spawned once (a dead one respawns by itself)."""
    return _state["want"] > 0 and _state["spawned"] >= _state["want"]


def start(world, want=None):
    """Spawn ``want`` bots (default: the environment's) into ``world`` over the
    next frames and drive them until the process ends."""
    want = count() if want is None else want
    if want <= 0 or _state["started"]:
        return
    _state.update(want=want, world=world, started=time.time())
    cls = unreal.load_object(None, CHARACTER_CLASS_PATH)
    _state["cls"] = cls
    _state["hc"] = unreal.load_object(None, HEALTH_CLASS_PATH)
    _state["wcc"] = unreal.load_object(None, WEAPON_COMP_CLASS_PATH)
    _state["starts"] = [a.get_actor_location() for a in
                        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)]
    if not _state["starts"]:
        _state["starts"] = [unreal.Vector(0, 0, 200)]
    _log(f"spawning {want} bot(s) round {len(_state['starts'])} PlayerStart(s)")
    unreal.register_ticker_callback(_tick)


# ─── one bot ─────────────────────────────────────────────────────────────────

def _valid(obj):
    return obj is not None and unreal.SystemLibrary.is_valid(obj)


def _alive(bot):
    return _valid(bot.get("pawn")) and not bot["health"].get_editor_property(str(HV.Dead))


def _spawn_point(world):
    origin = random.choice(_state["starts"])
    point = unreal.NavigationSystemV1.get_random_reachable_point_in_radius(
        world, origin, SPAWN_RADIUS_CM)
    return (point if point is not None else origin) + unreal.Vector(0, 0, SPAWN_UP_CM)


def _spawn(world, bot):
    """A body for ``bot``: spawned, possessed by its AIController, its
    components found."""
    where = _spawn_point(world)
    yaw = unreal.Rotator(0.0, random.uniform(-180, 180), 0.0)
    pawn = unreal.AIHelperLibrary.spawn_ai_from_class(world, _state["cls"], None, where, yaw, True)
    if pawn is None:
        raise RuntimeError("spawn_ai_from_class returned no pawn")
    controller = pawn.get_controller()
    if controller is None:
        pawn.spawn_default_controller()
        controller = pawn.get_controller()
    bot.update(pawn=pawn, controller=unreal.AIController.cast(controller) if controller else None,
               health=pawn.get_component_by_class(_state["hc"]),
               wc=pawn.get_component_by_class(_state["wcc"]),
               next=time.time() + random.uniform(*DECIDE_S), dead_at=None)
    if bot["health"] is None or bot["wc"] is None:
        raise RuntimeError(f"{pawn.get_name()} lacks a health or weapon component")
    _state["spawned"] += 1


def _others(bot):
    """Every other living body with a health component (bots, players, wanderers)."""
    found = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(_state["world"], unreal.Character):
        if actor == bot["pawn"]:
            continue
        health = actor.get_component_by_class(_state["hc"])
        if health is not None and not health.get_editor_property(str(HV.Dead)):
            found.append(actor)
    return found


def _nearest(actors, point):
    return min(actors, key=lambda a: (a.get_actor_location() - point).length(), default=None)


def _fire(bot, target):
    """The shot a client would ask for: at a point near the target, from a
    gun in hand; a dry gun is reloaded (its reserve refilled first if empty)."""
    wc = bot["wc"]
    held = wc.get_editor_property("Held")
    if held is None:
        return
    loaded = int(held.get_editor_property(str(IV.Loaded)))
    if loaded > 0:
        scatter = unreal.Vector(*(random.uniform(-AIM_SCATTER_CM, AIM_SCATTER_CM) for _ in range(3)))
        aim = target.get_actor_location() + unreal.Vector(0, 0, 40.0) + scatter
        wc.call_method(SERVER_FIRE, (aim,))
        _state["shots"] += 1
        return
    if int(held.get_editor_property(str(IV.Reserve))) <= 0:
        held.set_editor_property(str(IV.Reserve), REFILL_ROUNDS,
                                 unreal.PropertyAccessChangeNotifyMode.NEVER)
    wc.call_method(SERVER_RELOAD)
    _state["reloads"] += 1


def _decide(bot, now):
    pawn = bot["pawn"]
    here = pawn.get_actor_location()
    target = _nearest(_others(bot), here)
    if target is not None:
        face = unreal.MathLibrary.find_look_at_rotation(here, target.get_actor_location())
        pawn.set_actor_rotation(unreal.Rotator(0.0, face.yaw, 0.0), False)
    if random.random() < CROUCH_CHANCE:
        if bool(pawn.get_editor_property("is_crouched")):
            pawn.un_crouch()
        else:
            pawn.crouch()
    elif bot["controller"] is not None:
        dest = unreal.NavigationSystemV1.get_random_reachable_point_in_radius(
            _state["world"], here, WALK_RADIUS_CM)
        if dest is not None:
            bot["controller"].move_to_location(dest, ACCEPT_CM, True, True, True, False, None, True)
    if target is not None and (target.get_actor_location() - here).length() <= FIRE_RANGE_CM:
        _fire(bot, target)
    bot["next"] = now + random.uniform(*DECIDE_S)


def _step(bot, now):
    if not _valid(bot.get("pawn")):
        _spawn(_state["world"], bot)
        return
    if bot["health"].get_editor_property(str(HV.Dead)):
        if bot["dead_at"] is None:
            bot["dead_at"] = now
            _state["deaths"] += 1
        elif now - bot["dead_at"] >= RESPAWN_S:
            _state["bodies"].append((bot["pawn"], now))
            _spawn(_state["world"], bot)
        return
    if now >= bot["next"]:
        _decide(bot, now)


def _clear_bodies(now):
    kept = []
    for body, since in _state["bodies"]:
        if now - since >= BODY_S:
            if _valid(body):
                body.destroy_actor()
        else:
            kept.append((body, since))
    _state["bodies"] = kept


def _complain(kind, exc):
    """Each kind of failure is logged once, with a count at the end."""
    n = _state["errors"].get(kind, 0)
    _state["errors"][kind] = n + 1
    if n == 0:
        _log(f"{kind}: {exc!r}")


def _tick(_delta):
    """Once a frame: spawn the bots still missing, a few at a time, then give
    each one whose timer is up its next decision. Never raises."""
    now = time.time()
    try:
        _drive(now)
    except Exception as exc:
        _complain("tick", exc)
    _state["driver_ms"].append((time.time() - now) * 1000.0)
    return True


def _drive(now):
    """Spawn the bots still missing, a few at a time, then give each one whose
    timer is up its next decision; a bot's own failure stops only it."""
    missing = _state["want"] - len(_state["bots"])
    for _ in range(min(SPAWN_PER_TICK, missing)):
        bot = {}
        _spawn(_state["world"], bot)
        _state["bots"].append(bot)
        if len(_state["bots"]) == _state["want"]:
            _log(f"all {_state['want']} bots spawned, {status()['seconds']:.1f}s in")
    for bot in _state["bots"]:
        try:
            _step(bot, now)
        except Exception as exc:
            _complain("step", exc)
    _clear_bodies(now)
