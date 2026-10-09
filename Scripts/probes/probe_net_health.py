"""Health is the server's: a wanderer's blow on client 1 lowers client 1's bar,
on every machine's copy of that character, and nobody else's (M14).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_health.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_net_health.py    # single player

combat/damage.py: a blow calls the target's TakeHit, which only the server
runs; Health, MaxHealth, Dead, HitCount, LastHitFrom and the wanderer's number
replicate, and a client's OnRep_Health stamps the blow with its own clock.
The server acts, step by step, and the three machines compare:

    "ids"    the wanderers' numbers, which each client's copies must carry
    "kill"   a wanderer killed by a blow naming client 2's controller: the
             kill is on client 2's PlayerState and not on client 1's
    "hit"    a zombie stood beside client 1 and left to swing. Client 1's
             health falls on the server; client 1's bar and client 2's copy
             of that character follow, each stamped as a blow (the flinch,
             LastDamageTime), and client 2's own health and bar do not move
    "cheat"  client 2 calls TakeHit on its own copy of client 1's character
             and of its own: nothing changes anywhere
    "low"    client 1 taken to 20 HP: its heart is heard on client 1 alone
    "dead"   client 1 taken to 0: Dead reaches both clients, and each has run
             the death path once (DeathPlayed)

Join order varies, so a player is known by its player id, never by index.
"""

SYSTEMS = ('net', 'health')

import time

import unreal

from combat import health_vars as HV
from combat.damage import TAKE_HIT
from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, KILL_COUNT_VAR, LAST_DAMAGE_VAR, NEVER_DAMAGED, NPC_ID_VAR)
from combat.hit_reaction import NEXT_REACT_VAR
from combat.paths import HEALTH_CLASS_PATH
from forest_generator.npc_placement import NAV_REACHABLE_EXTENT_CM
from graphics_menu import umg_consts as C

RUNS_ON = ("server", "client", "standalone")

WAIT = 30.0             # wall seconds any one step may take
SWING_WAIT = 60.0       # ...and the zombie's first blow: it has to notice first
START_CM = 150.0        # where the zombie is stood: inside its reach
NEAR = 0.5              # HP
LOW = 20.0
AHEAD = unreal.Vector(1.0, 0.0, 0.0)


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _health(p, actor):
    return p.component(actor, HEALTH_CLASS_PATH)


def _hp(p, actor):
    return float(p.get(_health(p, actor), HV.Health))


def _bodies(p):
    """Every character with a health component: (players', wanderers')."""
    cls = p.load_class(HEALTH_CLASS_PATH)
    found = [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), unreal.Character) if a.get_component_by_class(cls)]
    mine = [a for a in found if not p.get(_health(p, a), HV.DespawnOnDeath)]
    return mine, [a for a in found if a not in mine]


def _player_id(pawn):
    state = pawn.get_editor_property("player_state") if pawn else None
    return state.get_editor_property("player_id") if state else None


def _drawn(hud):
    """One HUD frame: a -nullrhi client draws none of its own."""
    if "-nullrhi" in unreal.SystemLibrary.get_command_line().lower():
        hud.call_method("ReceiveDrawHUD", (1920, 1080))
    yield 0.3


def _bar(hud):
    return float(hud.get_editor_property("UiHud").get_editor_property(C.HP_BAR)
                 .get_editor_property("percent"))


def _take(p, actor, amount, by=None, cause=None):
    _health(p, actor).call_method(TAKE_HIT, (float(amount), AHEAD, by, cause))


def _state(p, actor):
    h = _health(p, actor)
    return {v: p.get(h, v) for v in (HV.Health, HV.Dead, HV.HitCount)}


# ─── the server acts ─────────────────────────────────────────────────────────

def _stand_beside(p, npc, target, away_from):
    """Stand ``npc`` START_CM from ``target``, on the side away from
    ``away_from`` (so ``target`` is the nearest player), facing it."""
    here, there = target.get_actor_location(), away_from.get_actor_location()
    out = unreal.Vector(here.x - there.x, here.y - there.y, 0.0)
    out = out.normal() if out.length() > 1.0 else AHEAD
    ground = unreal.NavigationSystemV1.project_point_to_navigation(
        p.world(), here + out * START_CM, None, None, unreal.Vector(*NAV_REACHABLE_EXTENT_CM))
    if ground is None:
        return False
    yaw = unreal.MathLibrary.find_look_at_rotation(ground, here).yaw
    npc.set_actor_location_and_rotation(
        ground + unreal.Vector(0.0, 0.0, 95.0),
        unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0), False, True)
    return True


def probe_server(p):
    names = [f"client {i}" for i in range(1, p.clients + 1)]
    yield from _await(lambda: len(p.players()) >= p.clients
                      and all(c.get_controlled_pawn() for c in p.players())
                      and all(p.posted(n, "ready") is not None for n in names))
    by_id = {_player_id(c.get_controlled_pawn()): c for c in p.players()}
    ctrl = {i: by_id.get(p.posted(n, "ready")) for i, n in enumerate(names, 1)}
    if not all(ctrl.values()) or len(ctrl) < 2:
        p.check("the server knows each client's controller by its player id", False, str(ctrl))
        return
    one, two = ctrl[1].get_controlled_pawn(), ctrl[2].get_controlled_pawn()
    yield from _await(lambda: len(_bodies(p)[1]) >= 2
                      and all(p.get(_health(p, w), NPC_ID_VAR) > 0 for w in _bodies(p)[1]))
    wanderers = _bodies(p)[1]
    ids = sorted(int(p.get(_health(p, w), NPC_ID_VAR)) for w in wanderers)
    p.check("both players start at full health on the server",
            _hp(p, one) == _hp(p, two) == p.get(_health(p, one), HV.MaxHealth),
            f"{_hp(p, one)}, {_hp(p, two)}")
    p.post("ids", ids)

    # --- a kill is the instigator's -------------------------------------------
    zombies = [w for w in wanderers if "Zombie" in w.get_controller().get_class().get_name()]
    if len(zombies) < 1 or len(wanderers) < 2:
        p.check("the level has a zombie to swing and a wanderer to kill", False,
                str([w.get_name() for w in wanderers]))
        return
    hitter = zombies[0]
    victim = [w for w in wanderers if w != hitter][0]
    _take(p, victim, 10000.0, ctrl[2], two)
    yield from _await(lambda: p.get(_health(p, victim), HV.Dead))
    yield 0.3
    kills = {i: int(p.get(c.player_state, KILL_COUNT_VAR)) for i, c in ctrl.items()}
    p.check("a wanderer killed by a blow naming client 2's controller is client 2's "
            "kill, and not client 1's (whoever joined first)",
            kills == {1: 0, 2: 1} and p.get(_health(p, victim), DAMAGED_BY_PLAYER_VAR)
            and p.get(_health(p, victim), HV.LastInstigator) == ctrl[2], str(kills))
    p.post("kill", kills[2])
    # The body is removed below: the clients look at it first.
    yield from _await(lambda: all(p.posted(n, "saw kill") is not None for n in names))

    # --- a wanderer hits client 1 ---------------------------------------------
    for other in _bodies(p)[1]:
        if other != hitter:
            other.destroy_actor()
    brain = hitter.get_controller()
    if not _stand_beside(p, hitter, one, two):
        p.check("there is ground beside client 1 to stand a zombie on", False)
        return
    full = _hp(p, one)
    yield from _await(lambda: _hp(p, one) < full, SWING_WAIT)
    struck = _health(p, one)
    by, cause = p.get(struck, HV.LastInstigator), p.get(struck, HV.LastCause)
    blamed = p.get(struck, DAMAGED_BY_PLAYER_VAR)
    hitter.destroy_actor()
    yield 0.5
    left = _hp(p, one)
    p.check("a zombie left beside client 1 hits them: their health falls on the server",
            left < full, f"{full} -> {left}")
    p.check("...the blow names the zombie's controller and the zombie, and blames no "
            "player", by == brain and cause == hitter and not blamed,
            f"by {by.get_name() if by else None}, cause {cause.get_name() if cause else None}, "
            f"DamagedByPlayer {blamed}")
    p.check("...and client 2's health has not moved", _hp(p, two) == full, str(_hp(p, two)))
    if left >= full:
        return
    p.post("hit", left)
    yield from _await(lambda: all(p.posted(n, "saw hit") is not None for n in names))

    # --- a client cannot --------------------------------------------------------
    p.check("client 2's own TakeHit calls, on its copies, changed nothing on the server",
            _hp(p, one) == left and _hp(p, two) == full, f"{_hp(p, one)}, {_hp(p, two)}")

    # --- low, then dead ----------------------------------------------------------
    if left > LOW:
        _take(p, one, left - LOW)
    low = _hp(p, one)
    server_heart = float(p.get(_health(p, one), HV.HeartbeatNextTime))
    p.post("low", low)
    yield from _await(lambda: all(p.posted(n, "saw low") is not None for n in names))
    p.check("the server plays no heart for client 1: the character is not its own",
            float(p.get(_health(p, one), HV.HeartbeatNextTime)) == server_heart == 0.0,
            str(p.get(_health(p, one), HV.HeartbeatNextTime)))
    _take(p, one, 10000.0)
    yield from _await(lambda: p.get(_health(p, one), HV.Dead))
    p.check("at 0 the server marks client 1 Dead, and client 2 not",
            p.get(_health(p, one), HV.Dead) and not p.get(_health(p, two), HV.Dead)
            and _hp(p, one) == 0.0, str(_state(p, one)))
    p.post("dead")
    yield from _await(lambda: all(p.posted(n, "saw dead") is not None for n in names))


# ─── the clients watch ───────────────────────────────────────────────────────

def probe_client(p):
    yield from _await(lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
                      and p.pawn() is not None and _player_id(p.pawn()) is not None)
    hud, mine = p.hud(), p.pawn()
    if not hud or not mine or _player_id(mine) is None:
        p.check(f"{p.where} has a HUD, a pawn and a player id", False, f"{hud}, {mine}")
        return
    yield from _await(lambda: p.get(hud, C.GAME_STARTED_VAR)
                      and len(_bodies(p)[0]) >= p.clients)
    p.post("ready", _player_id(mine))
    others = [a for a in _bodies(p)[0] if a != mine]
    if len(others) != 1:
        p.check(f"{p.where} holds one other player's character", False, str(len(others)))
        return
    other = others[0]
    hit_one = mine if p.client == 1 else other       # this machine's copy of client 1's
    spared = other if p.client == 1 else mine        # ...and of client 2's
    full = float(p.get(_health(p, mine), HV.MaxHealth))

    # --- the wanderers' numbers ----------------------------------------------
    yield from _await(lambda: p.posted("server", "ids") is not None)
    want = p.posted("server", "ids") or []
    yield from _await(lambda: sorted(int(p.get(_health(p, w), NPC_ID_VAR))
                                     for w in _bodies(p)[1]) == want)
    got = sorted(int(p.get(_health(p, w), NPC_ID_VAR)) for w in _bodies(p)[1])
    p.check(f"{p.where}'s copies of the wanderers carry the numbers the server gave them",
            got == want and bool(want), f"{got}, the server's {want}")

    # --- the kill ---------------------------------------------------------------
    yield from _await(lambda: p.posted("server", "kill") is not None)
    mine_kills = 1 if p.client == 2 else 0
    yield from _await(lambda: int(p.get(p.player_state(), KILL_COUNT_VAR)) == mine_kills
                      and any(p.get(_health(p, w), HV.Dead) for w in _bodies(p)[1]))
    dead = [w for w in _bodies(p)[1] if p.get(_health(p, w), HV.Dead)]
    p.check(f"{p.where} counts {mine_kills} kill(s): the kill is client 2's",
            int(p.get(p.player_state(), KILL_COUNT_VAR)) == mine_kills,
            str(p.get(p.player_state(), KILL_COUNT_VAR)))
    p.check(f"{p.where} sees the one killed wanderer dead: Health 0 and Dead arrived, "
            f"and its copy ran the death path",
            len(dead) == 1 and _hp(p, dead[0]) == 0.0
            and p.get(_health(p, dead[0]), HV.DeathPlayed),
            str([_state(p, w) for w in dead]))
    p.post("saw kill")

    # --- the hit ----------------------------------------------------------------
    before = {a: float(p.get(_health(p, a), LAST_DAMAGE_VAR)) for a in (hit_one, spared)}
    yield from _await(lambda: p.posted("server", "hit") is not None, SWING_WAIT + WAIT)
    left = p.posted("server", "hit")
    if left is None:
        p.check(f"{p.where} heard of the hit", False)
        return
    yield from _await(lambda: abs(_hp(p, hit_one) - left) < NEAR)
    yield from _drawn(hud)
    bar = _bar(hud)
    struck, safe = _health(p, hit_one), _health(p, spared)
    p.check(f"{p.where}'s copy of client 1's character has the server's health ({left:.0f}), "
            f"and of client 2's is still full",
            abs(_hp(p, hit_one) - left) < NEAR and _hp(p, spared) == full,
            f"{_hp(p, hit_one)}, {_hp(p, spared)}")
    own = left if p.client == 1 else full
    p.check(f"{p.where}'s HP bar shows its own character's health ({own / full:.0%}): "
            f"the blow lowered client 1's bar only",
            abs(bar - own / full) < 0.01, f"{bar:.2f}")
    p.check(f"{p.where} knows it for a blow, by its own clock: HitCount arrived and is "
            f"answered, LastDamageTime is stamped and the flinch armed; client 2's "
            f"character has none of it",
            int(p.get(struck, HV.HitCount)) >= 1
            and p.get(struck, HV.SeenHits) == p.get(struck, HV.HitCount)
            and float(p.get(struck, LAST_DAMAGE_VAR)) > max(before[hit_one], NEVER_DAMAGED)
            and float(p.get(struck, NEXT_REACT_VAR)) > 0.0
            and int(p.get(safe, HV.HitCount)) == 0
            and float(p.get(safe, LAST_DAMAGE_VAR)) == before[spared]
            and float(p.get(safe, NEXT_REACT_VAR)) == 0.0,
            f"hit {int(p.get(struck, HV.HitCount))}/{int(p.get(struck, HV.SeenHits))}, "
            f"stamped {float(p.get(struck, LAST_DAMAGE_VAR)):.1f}, "
            f"flinch {float(p.get(struck, NEXT_REACT_VAR)):.1f}; "
            f"spared {int(p.get(safe, HV.HitCount))}, "
            f"{float(p.get(safe, NEXT_REACT_VAR)):.1f}")

    # --- a client's own call does nothing --------------------------------------
    if p.client == 2:
        _take(p, hit_one, 30.0, p.controller(), mine)
        _take(p, mine, 30.0, p.controller(), mine)
        yield 0.5
        p.check("client 2's TakeHit on its own copies takes nothing: not off client 1's "
                "character, not off its own",
                abs(_hp(p, hit_one) - left) < NEAR and _hp(p, mine) == full,
                f"{_hp(p, hit_one)}, {_hp(p, mine)}")
    p.post("saw hit", round(_hp(p, hit_one), 1))

    # --- low: the heart ---------------------------------------------------------
    yield from _await(lambda: p.posted("server", "low") is not None)
    low = p.posted("server", "low")
    yield from _await(lambda: abs(_hp(p, hit_one) - low) < NEAR)
    yield 0.5
    heart = float(p.get(struck, HV.HeartbeatNextTime))
    if p.client == 1:
        yield from _drawn(hud)
        p.check(f"client 1 at {low:.0f} HP: its bar shows it and its heart is heard",
                abs(_bar(hud) - low / full) < 0.01 and heart > 0.0,
                f"bar {_bar(hud):.2f}, next beat {heart:.1f}")
    else:
        p.check(f"client 2 sees client 1 at {low:.0f} HP and hears no heart: it is not "
                f"its own", abs(_hp(p, hit_one) - low) < NEAR and heart == 0.0,
                f"{_hp(p, hit_one)}, next beat {heart:.1f}")
    p.post("saw low")

    # --- dead ---------------------------------------------------------------------
    yield from _await(lambda: p.posted("server", "dead") is not None)
    yield from _await(lambda: p.get(struck, HV.Dead) and p.get(struck, HV.DeathPlayed))
    p.check(f"{p.where}: client 1's character is Dead (the server's word arrived) and "
            f"this copy ran the death path; client 2's is alive",
            p.get(struck, HV.Dead) and p.get(struck, HV.DeathPlayed)
            and _hp(p, hit_one) == 0.0
            and not p.get(safe, HV.Dead) and not p.get(safe, HV.DeathPlayed),
            f"{_state(p, hit_one)}, {_state(p, spared)}")
    p.post("saw dead")


# ─── single player: the same event, one machine ──────────────────────────────

def probe(p):
    yield from _await(lambda: p.pawn() is not None and len(_bodies(p)[1]) >= 1)
    mine, npc = p.pawn(), _bodies(p)[1][0]
    health, full = _health(p, mine), _hp(p, mine)
    _take(p, mine, 30.0, npc.get_controller(), npc)
    yield 0.2
    p.check("single player: TakeHit takes 30 off the player and stamps the blow",
            _hp(p, mine) == full - 30.0 and int(p.get(health, HV.HitCount)) == 1
            and float(p.get(health, LAST_DAMAGE_VAR)) > NEVER_DAMAGED
            and p.get(health, HV.LastInstigator) == npc.get_controller()
            and p.get(health, HV.LastCause) == npc
            and not p.get(health, DAMAGED_BY_PLAYER_VAR), str(_state(p, mine)))
    _take(p, npc, 10000.0, p.controller(), mine)
    yield from _await(lambda: p.get(_health(p, npc), HV.Dead))
    yield 0.3
    p.check("...and a wanderer the player's blow kills is Dead, at 0, and the player's kill",
            p.get(_health(p, npc), HV.Dead) and _hp(p, npc) == 0.0
            and p.get(_health(p, npc), DAMAGED_BY_PLAYER_VAR)
            and int(p.get(p.player_state(), KILL_COUNT_VAR)) == 1,
            f"{_state(p, npc)}, kills {p.get(p.player_state(), KILL_COUNT_VAR)}")
