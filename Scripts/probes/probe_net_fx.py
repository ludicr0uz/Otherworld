"""Everyone sees and hears the fight (task M21, combat/fx_vars.py).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_fx.py
    OW_FX_SHOTS=1 python3 Scripts/dev/uepy.py --net --clients 2 --windowed --probe-timeout 240 --probe Scripts/probes/probe_net_fx.py

Client 1 acts: it walks a few metres off (its footsteps), fires its issued
gun at the ground ahead, reloads, brings the knife to hand and slashes, then
throws the knife. After each step it posts what its own copy counts.

Every cosmetic the server tells of is counted on the copy that played it
(FxPlayed, the gated arm of each Multicast_*): the server and client 2 count
client 1's shot, reload, swing and throw (and its throw's clip), client 2 the
pellets' chips too, and client 1 itself counts only the chips (what it did
not predict). Client 2 also sees the knife's clip and the throw's clip
playing on its copy of client 1's character, and the chips as BP_BulletImpact
actors in its world, and its copy's footstep component striding.

With --windowed and OW_FX_SHOTS=1 client 2 faces client 1's character and
saves a picture at each step to Saved/Screenshots/MacEditor.

``probe`` is single player's arm (--game): the one machine has authority, so
each Multicast is a plain call that plays here, and the counter rises by one
per cosmetic (the pellets' chips too).
"""

import os
import time

import unreal

from combat import footstep_vars as FV
from combat import health_vars as HV
from combat.anim_blueprint import AIM_SLOT
from combat.fx_vars import FxPlayed
from combat.paths import (
    BULLET_IMPACT_CLASS_PATH, FOOTSTEP_BP_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH,
    WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.record_vars import SlotForced
from combat.shot_vars import ReloadForced
from combat.weapon_component import vars as WV
from combat.weapon_component.knife import KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR)
from combat.weapon_component.throw_windup import THROW_ANIM_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from combat.weapon_component.knife import KNIFE_ANIM_VAR

RUNS_ON = ("server", "client", "standalone")
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in (
    FIRE_FORCED_VAR, ReloadForced, KNIFE_QUEUED_VAR, THROW_FORCED_VAR,
    THROW_CLICK_FORCED_VAR, SlotForced)] + [(HEALTH_BP_PATH, HV.Health)]

FOOTSTEP_CLASS_PATH = f"{FOOTSTEP_BP_PATH}.BP_FootstepComponent_C"
SHOTS = bool(os.environ.get("OW_FX_SHOTS"))
WAIT = 30.0
SEEN_S = 6.0          # wall seconds a watcher gives a cosmetic to arrive
WALK_CM = 350.0
AIM_DOWN_DEG = -25.0  # the shot goes into the ground ahead: pellets that land
SPARE_HEALTH = 100000.0
STEPS = ("fired", "reloaded", "slashed", "thrown")
# What the server's word adds to FxPlayed on a copy that did not predict it.
TOLD = {"fired": 1, "reloaded": 1, "slashed": 1, "thrown": 2}


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _xyz(actor):
    v = actor.get_actor_location()
    return [v.x, v.y, v.z]


def _others(p, mine):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), mine.get_class())
            if a != mine]


def _played(p, wc):
    return int(p.get(wc, FxPlayed))


def _impacts(p):
    return len(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(BULLET_IMPACT_CLASS_PATH)))


def _index(p, wc, word):
    for i, item in enumerate(p.get(wc, WV.Inventory)):
        if word in item.get_class().get_name().lower():
            return i
    return -1


def _playing(p, wc, pawn, anim_var):
    anim = pawn.mesh.get_anim_instance()
    clip = p.get(wc, anim_var)
    return bool(anim and clip and anim.is_playing_slot_animation(clip, AIM_SLOT))


def _slot(p, pawn):
    """What the upper-body slot is doing, for a check's detail."""
    anim = pawn.mesh.get_anim_instance()
    if not anim:
        return "no anim instance"
    montage = anim.get_current_active_montage()
    return (f"slot active {anim.is_slot_active(AIM_SLOT)}, montage "
            f"{montage.get_name() if montage else None}"
            + (f" at {anim.montage_get_position(montage):.2f} s" if montage else ""))


# ─── client 1 acts ───────────────────────────────────────────────────────────

def _walk_off(p, pawn, other):
    start = pawn.get_actor_location()
    away = start - other.get_actor_location()
    away = unreal.Vector(away.x, away.y, 0.0)
    away = away.normal() if away.length() > 1.0 else pawn.get_actor_forward_vector()

    def walking():
        pawn.add_movement_input(away, 1.0)
        return (pawn.get_actor_location() - start).length() >= WALK_CM
    yield from _await(walking, 12.0)
    p.check("client 1 walked clear of the other player",
            (pawn.get_actor_location() - start).length() >= 0.5 * WALK_CM,
            f"{(pawn.get_actor_location() - start).length():.0f} cm")


def _act(p, pawn, wc, other):
    p.post("walking")
    yield from _walk_off(p, pawn, other)
    yield from _await(lambda: False, 0.5)
    p.post("walked")
    pc = p.controller()
    rot = pc.get_control_rotation()
    pc.set_control_rotation(unreal.Rotator(pitch=AIM_DOWN_DEG, yaw=rot.yaw, roll=0.0))
    yield from _await(lambda: False, 0.5)
    held = p.get(wc, WV.Held)
    mine = {}

    def step(name, do, done):
        before = _played(p, wc)
        do()
        yield from _await(done, 10.0)
        yield from _await(lambda: False, 0.3)
        mine[name] = _played(p, wc) - before
        p.post(name, mine[name])

    was = int(p.get(held, "Loaded"))
    yield from step("fired", lambda: p.set(wc, FIRE_FORCED_VAR, True),
                    lambda: int(p.get(held, "Loaded")) < was)
    p.set(wc, FIRE_FORCED_VAR, False)
    yield from _await(lambda: _played(p, wc) > 0, 3.0)
    mine["fired"] = _played(p, wc)
    p.check("client 1's own copy counts only the pellets' chips of its shot: the "
            "sound it predicted itself is not played again", mine["fired"] >= 1,
            f"{mine['fired']} cosmetic(s), {_impacts(p)} impact actor(s)")
    p.check("...and its pellets' chips stand in its world", _impacts(p) >= 1, str(_impacts(p)))
    yield from _await(lambda: all(p.posted(w, "saw fired") for w in ("client 2", "server")))

    loaded = int(p.get(held, "Loaded"))
    yield from step("reloaded", lambda: p.set(wc, ReloadForced, True),
                    lambda: int(p.get(held, "Loaded")) > loaded)
    p.set(wc, ReloadForced, False)
    yield from _await(lambda: all(p.posted(w, "saw reloaded") for w in ("client 2", "server")))

    p.hold(wc, _index(p, wc, "knife"))
    yield from _await(lambda: p.get(wc, WV.Held) is not None
                      and "knife" in p.get(wc, WV.Held).get_class().get_name().lower(), 10.0)
    yield from _await(lambda: False, 0.5)
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    yield from _await(lambda: now() >= p.get(wc, NEXT_KNIFE_VAR), 5.0)
    yield from step("slashed", lambda: p.set(wc, KNIFE_QUEUED_VAR, True),
                    lambda: not p.get(wc, KNIFE_QUEUED_VAR))
    yield from _await(lambda: all(p.posted(w, "saw slashed") for w in ("client 2", "server")))

    bag = len(list(p.get(wc, WV.Inventory)))

    def throw():
        p.set(wc, THROW_FORCED_VAR, True)
    yield from _await(lambda: False, 0.2)
    yield from step("thrown", throw, lambda: p.get(wc, THROW_AIMING_VAR))
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield from _await(lambda: not p.get(wc, THROW_AIMING_VAR), 5.0)
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    yield from _await(lambda: len(list(p.get(wc, WV.Inventory))) < bag, 10.0)
    p.set(wc, THROW_FORCED_VAR, False)
    p.check("client 1's throw left its hand", len(list(p.get(wc, WV.Inventory))) < bag,
            f"{bag} -> {len(list(p.get(wc, WV.Inventory)))} item(s)")
    p.check("client 1 did not count its own reload, swing or throw: it predicted them",
            mine["reloaded"] == 0 and mine["slashed"] == 0 and mine["thrown"] == 0,
            str(mine))
    yield from _await(lambda: all(p.posted(w, "saw thrown") for w in ("client 2", "server")))
    p.post("done")


# ─── the others watch ────────────────────────────────────────────────────────

def _face(p, other):
    if not SHOTS:
        return
    pc, me = p.controller(), p.pawn()
    to = other.get_actor_location() - me.get_actor_location()
    pc.set_control_rotation(unreal.Rotator(pitch=-8.0, yaw=to.rotator().yaw, roll=0.0))
    unreal.SystemLibrary.execute_console_command(p.world(), "FOV 35", pc)


def _shot(p):
    if SHOTS:
        unreal.SystemLibrary.execute_console_command(p.world(), "shot")


def _watch(p, other, draws):
    wc = p.component(other, WEAPON_COMP_CLASS_PATH)
    feet = p.component(other, FOOTSTEP_CLASS_PATH)
    yield from _await(lambda: p.posted("client 1", "walking"))
    strides = []
    while not p.posted("client 1", "walked") and len(strides) < 400:
        strides.append(float(p.get(feet, FV.Travelled)))
        yield 0.05
    moved = max(strides, default=0.0) - min(strides, default=0.0) if strides else 0.0
    wrapped = any(b < a - 1.0 for a, b in zip(strides, strides[1:]))
    p.check(f"{p.where}'s copy of client 1 strides as it walks: its footstep component "
            "ticks here (Travelled covers ground and wraps at a step)",
            moved > 20.0 and wrapped, f"{len(strides)} sample(s), {moved:.0f} cm covered, "
            f"a step {'seen' if wrapped else 'not seen'}")
    if draws:
        _face(p, other)
    counted = _played(p, wc)
    before_impacts = _impacts(p)
    for name in STEPS:
        yield from _await(lambda: p.posted("client 1", name) is not None)
        want = TOLD[name]
        yield from _await(lambda: _played(p, wc) >= counted + want, SEEN_S)
        if name in ("slashed", "thrown") and draws:
            clip = KNIFE_ANIM_VAR if name == "slashed" else THROW_ANIM_VAR
            seen, states, until = [], [], time.time() + 3.0
            while time.time() < until and not seen:
                if _playing(p, wc, other, clip):
                    seen.append(_slot(p, other))
                state = _slot(p, other)
                if not states or states[-1].split(" at ")[0] != state.split(" at ")[0]:
                    states.append(state)
                yield 0.0
            _shot(p)
            p.check(f"{p.where} sees client 1's {'knife' if name == 'slashed' else 'throw'} "
                    "clip playing on its copy of the character",
                    bool(seen), f"{seen[0] if seen else 'never seen'}; the slot went "
                    f"{states[:6]}")
        got = _played(p, wc) - counted
        if name == "fired" and draws:
            yield from _await(lambda: _impacts(p) > before_impacts, 3.0)
            p.check(f"{p.where} hears client 1's shot and sees its pellets' chips: "
                    f"{want} sound and the impacts", got >= want + 1
                    and _impacts(p) > before_impacts,
                    f"{got} cosmetic(s), {_impacts(p) - before_impacts} impact actor(s)")
            _shot(p)
        else:
            exact = name != "thrown"
            p.check(f"{p.where} is told client 1 {name}: {want} cosmetic(s) played at the "
                    "server's word" + ("" if exact else ", and a lodge if the knife struck a trunk"),
                    got == want if exact else want <= got <= want + 1,
                    f"{got} played here; client 1 counted {p.posted('client 1', name)} of its own")
        counted = _played(p, wc)
        p.post(f"saw {name}")
    yield from _await(lambda: p.posted("client 1", "done"))


def probe_client(p):
    if p.clients != 2:
        p.check("this probe wants two clients", False, f"--clients {p.clients}")
        return
    yield from _await(lambda: p.pawn() and _others(p, p.pawn()))
    me = p.pawn()
    others = _others(p, me) if me else []
    if not p.check(f"{p.where} sees the other player's character", len(others) == 1,
                   f"{len(others)} other character(s)"):
        return
    wc = p.component(me, WEAPON_COMP_CLASS_PATH)
    yield from _await(lambda: p.get(wc, WV.Held) is not None, 10.0)
    p.post("start", _xyz(me))
    yield from _await(lambda: p.posted(f"client {3 - p.client}", "start")
                      and p.posted("server", "start"))
    if p.client == 1:
        yield from _act(p, me, wc, others[0])
    else:
        yield from _watch(p, others[0], draws=True)


def probe_server(p):
    if p.clients != 2:
        return
    yield from _await(lambda: p.posted("client 1", "start"), 3 * WAIT)
    there = p.posted("client 1", "start")
    pawns = [c.get_controlled_pawn() for c in p.players()]
    pawns = [a for a in pawns if a]
    if not p.check("the server has client 1's character", bool(there) and len(pawns) == 2,
                   f"{len(pawns)} pawns"):
        return
    for body in pawns:
        p.set(p.component(body, HEALTH_CLASS_PATH), HV.Health, SPARE_HEALTH)
    acting = min(pawns, key=lambda a: sum((x - y) ** 2 for x, y in zip(_xyz(a), there)))
    p.post("start")
    yield from _watch(p, acting, draws=False)


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    yield lambda: p.pawn() is not None
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, WV.Held) is not None
    yield 0.3
    pc = p.controller()
    rot = pc.get_control_rotation()
    pc.set_control_rotation(unreal.Rotator(pitch=AIM_DOWN_DEG, yaw=rot.yaw, roll=0.0))
    yield 0.3
    held = p.get(wc, WV.Held)
    was = int(p.get(held, "Loaded"))
    p.set(wc, FIRE_FORCED_VAR, True)
    yield from _await(lambda: int(p.get(held, "Loaded")) < was, 5.0)
    p.set(wc, FIRE_FORCED_VAR, False)
    yield 0.3
    got = _played(p, wc)
    p.check("standalone: one shot plays its sound and its pellets' chips here, each a "
            "Multicast that is a plain call", got >= 2 and _impacts(p) >= 1,
            f"{got} cosmetic(s), {_impacts(p)} impact actor(s)")
    before = got
    p.set(wc, ReloadForced, True)
    yield from _await(lambda: int(p.get(held, "Loaded")) > was - 1, 5.0)
    p.set(wc, ReloadForced, False)
    yield 0.3
    p.check("...the reload its clack, once", _played(p, wc) == before + 1,
            f"{_played(p, wc) - before}")
    before = _played(p, wc)
    p.hold(wc, _index(p, wc, "knife"))
    yield from _await(lambda: p.get(wc, WV.Held) is not None
                      and "knife" in p.get(wc, WV.Held).get_class().get_name().lower(), 10.0)
    yield 0.3
    before = _played(p, wc)
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    yield from _await(lambda: now() >= p.get(wc, NEXT_KNIFE_VAR), 5.0)
    p.set(wc, KNIFE_QUEUED_VAR, True)
    yield from _await(lambda: not p.get(wc, KNIFE_QUEUED_VAR), 5.0)
    yield 0.3
    p.check("...the slash its clip and swing, once, playing here",
            _played(p, wc) == before + 1 and _playing(p, wc, pawn, KNIFE_ANIM_VAR),
            f"{_played(p, wc) - before}, playing {_playing(p, wc, pawn, KNIFE_ANIM_VAR)}")
    before = _played(p, wc)
    bag = len(list(p.get(wc, WV.Inventory)))
    p.set(wc, THROW_FORCED_VAR, True)
    yield from _await(lambda: p.get(wc, THROW_AIMING_VAR), 5.0)
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield from _await(lambda: not p.get(wc, THROW_AIMING_VAR), 5.0)
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    yield from _await(lambda: len(list(p.get(wc, WV.Inventory))) < bag, 10.0)
    p.set(wc, THROW_FORCED_VAR, False)
    yield 0.3
    p.check("...the throw its sound, once (its clip is the wind-up's own here: the "
            "thrower's machine never owes it), and a lodge if the knife struck a trunk",
            before + 1 <= _played(p, wc) <= before + 2, f"{_played(p, wc) - before}")
    p.check("...and the throw's clip plays on through the hand letting go",
            _playing(p, wc, pawn, THROW_ANIM_VAR), _slot(p, pawn))
