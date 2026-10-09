"""A wendigo held off by fire roars (npc/ward_roar.py): once part way through
the hold, once at its end before it runs, and a blow it lands on the player
starts the hold over.

npc/verify_ward_roar.py reads the graph; this watches one wendigo do it. The
fire and the wendigo are set up as probes/probe_wendigo_ward.py does (the
issued stick, burning, held out; a wendigo stood in front of it), and the
player keeps the fire turned on it except where it says otherwise:

  - a hold begins with its first roar thrown 13-17 s on;
  - that time up (written due: 15 s is a long headless wait), it stands,
    facing the player, playing the scream, for the roar's 2.4 s, and the hold
    is the same one after it: it circles again, and does not roar twice;
  - the player stops turning: it gets round the fire and lands a blow, which
    ends the hold; held again, the count and the roar's throw are new;
  - with the hold all but run out (WardSince written back) it roars again,
    standing, and only then runs.
"""

SYSTEMS = ('npc',)

import math
import os
import shutil

import unreal

from combat.paths import FIRE_WARD_VAR, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SIGHTS_FORCED_VAR
from forest_generator.npc_stalk import NPC_STALK_ROAR
from forest_generator.npc_ward import (
    NPC_WARD_ROAR_AT_S, NPC_WARD_ROAR_S, NPC_WARD_ROAR_VARY_S,
)
from npc.paths import (
    AGGRO_VAR, WARD_FLEE_UNTIL_VAR, WARD_ROAR_AT_VAR, WARD_ROAR_UNTIL_VAR,
    WARD_SINCE_VAR,
)
from probes.probe_knife import _file
from probes.probe_wendigo_stalk import _montage_clips
from probes.probe_wendigo_ward import (
    BEAT_S, FACING_DOT, SAMPLE_S, START_CM, WARD_FLEE_S, WARD_HOLD_S,
    WENDIGO_AI, WRITABLE as WARD_WRITABLE, _burning_stick, _face, _on_navmesh,
    _state, _wendigos,
)

WRITABLE = WARD_WRITABLE + [(WENDIGO_AI, WARD_ROAR_AT_VAR)]

ROAR_CLIP = NPC_STALK_ROAR["Wendigo"].rsplit("/", 1)[-1]
STAND_CMS = 60.0      # under this it is standing (a brake's tail, not a prowl)
FLANK_SAMPLES = 150   # 15 s of game time to get round and swing


def probe(p):
    # Any profile on disk is set aside, so the game starts on the issued
    # loadout (the stick), and put back at the end.
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _watch(p, ctrl, npc, player, until, turn=True):
    """Samples of the wendigo until game time ``until``, the fire kept on it."""
    seen = []
    while p.time() < until:
        if turn:
            _face(p, player, npc)
        yield SAMPLE_S
        seen.append(_state(p, ctrl, npc, player))
    return seen


def _stood(seen):
    """Of a roar's samples, past the beat it brakes in: did it stand, facing
    the player?"""
    late = seen[int(BEAT_S / SAMPLE_S):]
    return (len(late) > 0 and max(s["speed"] for s in late) < STAND_CMS
            and min(s["facing"] for s in late) >= FACING_DOT)


def _run(p):
    yield lambda: len(_wendigos(p)) > 0
    yield 0.5
    ctrl = _wendigos(p)[0]
    npc, player = ctrl.get_controlled_pawn(), p.pawn()
    comp = p.component(player, WEAPON_COMP_CLASS_PATH)
    anim = npc.get_editor_property("mesh").get_anim_instance()
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None

    # --- held ----------------------------------------------------------------
    stick = yield from _burning_stick(p, comp)
    if stick is None:
        p.check("the player has the issued stick", False)
        return
    p.set(comp, SIGHTS_FORCED_VAR, True)
    yield lambda: bool(p.get(comp, FIRE_WARD_VAR))
    home, yaw = player.get_actor_location(), player.get_actor_rotation().yaw
    ahead = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.0)
    ground = _on_navmesh(p, home + ahead * START_CM)
    p.check(f"a wendigo is stood {START_CM / 100:.0f} m in front of the player, "
            f"who holds fire out", ground is not None)
    if ground is None:
        return
    p.check("before any hold it has no roar due and none under way",
            float(p.get(ctrl, WARD_ROAR_AT_VAR)) == 0.0
            and float(p.get(ctrl, WARD_ROAR_UNTIL_VAR)) == 0.0)
    npc.set_actor_location_and_rotation(
        ground + unreal.Vector(0.0, 0.0, 95.0),
        unreal.Rotator(pitch=0.0, yaw=yaw + 180.0, roll=0.0), False, True)
    yield lambda: bool(p.get(ctrl, AGGRO_VAR))
    yield lambda: float(p.get(ctrl, WARD_SINCE_VAR)) > 0.0
    since = float(p.get(ctrl, WARD_SINCE_VAR))
    due = float(p.get(ctrl, WARD_ROAR_AT_VAR)) - since
    lo, hi = (NPC_WARD_ROAR_AT_S - NPC_WARD_ROAR_VARY_S,
              NPC_WARD_ROAR_AT_S + NPC_WARD_ROAR_VARY_S)
    p.check(f"held off, its first roar is thrown {lo:g}-{hi:g} s into the hold, "
            f"and it is not roaring yet",
            lo - 0.01 <= due <= hi + 0.01
            and float(p.get(ctrl, WARD_ROAR_UNTIL_VAR)) == 0.0
            and anim.get_current_active_montage() is None, f"{due:.2f} s in")

    # --- the first roar ---------------------------------------------------------
    yield from _watch(p, ctrl, npc, player, p.time() + 1.0)   # up to its prowl
    p.set(ctrl, WARD_ROAR_AT_VAR, p.time())
    asked = p.time()
    while float(p.get(ctrl, WARD_ROAR_UNTIL_VAR)) == 0.0 and p.time() - asked < 2.0:
        _face(p, player, npc)
        yield SAMPLE_S
    until = float(p.get(ctrl, WARD_ROAR_UNTIL_VAR))
    p.check(f"that time up, it roars within a beat, for {NPC_WARD_ROAR_S:g} s, "
            f"the once (WardRoarAt back to 0)",
            p.time() - asked <= BEAT_S
            and abs(until - p.time() - NPC_WARD_ROAR_S) < 0.5
            and float(p.get(ctrl, WARD_ROAR_AT_VAR)) == 0.0,
            f"{p.time() - asked:.1f} s on, {until - p.time():.2f} s to go")
    yield lambda: anim.get_current_active_montage() is not None or p.time() > until
    montage = anim.get_current_active_montage()
    clips = _montage_clips(montage) if montage else []
    p.check("...playing the zombie scream", ROAR_CLIP in clips, f"{clips}")
    roar = yield from _watch(p, ctrl, npc, player, until)
    p.check("...standing, facing the player, with no swing",
            _stood(roar) and all(s["swung"] == 0.0 for s in roar),
            f"{len(roar)} samples, fastest late {max(s['speed'] for s in roar[int(BEAT_S / SAMPLE_S):] or roar):.0f} cm/s")
    after = yield from _watch(p, ctrl, npc, player, until + 1.5)
    p.check("the roar over, it is the same hold: it circles again, has not run, "
            "and does not roar a second time",
            float(p.get(ctrl, WARD_SINCE_VAR)) == since
            and max(s["speed"] for s in after) > 100.0
            and float(p.get(ctrl, WARD_FLEE_UNTIL_VAR)) == 0.0
            and float(p.get(ctrl, WARD_ROAR_AT_VAR)) == 0.0
            and float(p.get(ctrl, WARD_ROAR_UNTIL_VAR)) == until,
            f"hold began {float(p.get(ctrl, WARD_SINCE_VAR)):.2f} (was {since:.2f}), "
            f"fastest {max(s['speed'] for s in after):.0f} cm/s")

    # --- a blow starts the hold over: the player stops turning -----------------
    flank = []
    while len(flank) < FLANK_SAMPLES:
        flank.append(_state(p, ctrl, npc, player))
        if flank[-1]["swung"] > 0.0:
            break
        yield SAMPLE_S
    p.check("the player does not turn: it gets round the fire and lands a blow, "
            "which ends the hold (WardSince back to 0)",
            flank[-1]["swung"] > 0.0 and float(p.get(ctrl, WARD_SINCE_VAR)) == 0.0,
            f"after {len(flank) * SAMPLE_S:.1f} s, WardSince "
            f"{float(p.get(ctrl, WARD_SINCE_VAR)):.2f}")
    if flank[-1]["swung"] == 0.0:
        return
    struck = p.time()
    while float(p.get(ctrl, WARD_SINCE_VAR)) == 0.0 and p.time() - struck < 3.0:
        _face(p, player, npc)
        yield SAMPLE_S
    again = float(p.get(ctrl, WARD_SINCE_VAR))
    due = float(p.get(ctrl, WARD_ROAR_AT_VAR)) - again
    p.check(f"the fire turned on it again, a new hold begins: its "
            f"{WARD_HOLD_S:.0f} s count from now, and a first roar thrown anew",
            again >= struck - 0.01 and again > since and lo - 0.01 <= due <= hi + 0.01
            and float(p.get(ctrl, WARD_FLEE_UNTIL_VAR)) == 0.0,
            f"began {again:.2f} (the blow at {struck:.2f}, the old hold {since:.2f}), "
            f"roar {due:.2f} s in")

    # --- the last roar, and then the flight ------------------------------------
    yield from _watch(p, ctrl, npc, player, p.time() + 1.5)   # the swing is over
    before = float(p.get(ctrl, WARD_ROAR_UNTIL_VAR))
    p.set(ctrl, WARD_SINCE_VAR, p.time() - (WARD_HOLD_S - 0.5))
    asked = p.time()
    while float(p.get(ctrl, WARD_FLEE_UNTIL_VAR)) == 0.0 and p.time() - asked < 3.0:
        _face(p, player, npc)
        yield SAMPLE_S
    until, flee = (float(p.get(ctrl, WARD_ROAR_UNTIL_VAR)),
                   float(p.get(ctrl, WARD_FLEE_UNTIL_VAR)))
    p.check(f"held off {WARD_HOLD_S:.0f} s, it roars ({NPC_WARD_ROAR_S:g} s) "
            f"before it runs ({WARD_FLEE_S:.0f} s after that)",
            until > before and abs(until - p.time() - NPC_WARD_ROAR_S) < 0.5
            and abs(flee - until - WARD_FLEE_S) < 0.01,
            f"roars {until - p.time():.2f} s more, then runs {flee - until:.1f} s")
    yield lambda: anim.get_current_active_montage() is not None or p.time() > until
    montage = anim.get_current_active_montage()
    clips = _montage_clips(montage) if montage else []
    p.check("...playing the zombie scream", ROAR_CLIP in clips, f"{clips}")
    p.set(comp, SIGHTS_FORCED_VAR, False)   # it roars and runs with the fire down too
    start = _state(p, ctrl, npc, player)
    roar = yield from _watch(p, ctrl, npc, player, until, turn=False)
    p.check("...standing, facing the player, not running yet, though the fire is down",
            _stood(roar) and roar[-1]["gap"] < start["gap"] + 150.0
            and all(s["swung"] == roar[0]["swung"] for s in roar),
            f"{start['gap'] / 100:.1f} -> {roar[-1]['gap'] / 100:.1f} m")
    fled = yield from _watch(p, ctrl, npc, player, until + 3.0, turn=False)
    running = [s for s in fled if s["speed"] > 200.0]
    p.check("the roar over, it runs away from the player",
            fled[-1]["gap"] > roar[-1]["gap"] + 500.0 and len(running) > 0
            and sorted(s["away"] for s in running)[len(running) // 2] >= 0.7,
            f"{roar[-1]['gap'] / 100:.1f} -> {fled[-1]['gap'] / 100:.1f} m in "
            f"{len(fled) * SAMPLE_S:.1f} s")
