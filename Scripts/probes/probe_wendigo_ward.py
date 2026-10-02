"""Fire holds a wendigo off (npc/ward.py): with the player's FireWard up, a
wendigo in front of them does not attack; it circles; past the fire it
attacks; and held off long enough it runs away.

npc/verify_ward.py reads the graph; this watches one wendigo do it. The fire
is the game's own: the player takes the issued stick in hand, it is set
burning (Lit, written: lighting it at a campfire is probe_lit_stick.py's),
and the use key is held (SightsForced), which is what raises FireWard. The
wendigo is stood in front of the player, inside the fire's range:

  - it goes aggro and is held: no swing, kept out of reach, facing the
    player, moving round them;
  - the player does not turn, so it gets past the fire, and then it attacks;
  - the player turns the fire on it: the swings stop and it is back on the
    ring;
  - with the hold all but run out (WardSince written back; 30 s is a long
    headless wait) it runs away, and its hunt is reset for its return.

That a wendigo with no fire in front of it hunts and swings as before is
probes/probe_wendigo_stalk.py's.
"""

import math
import os
import shutil

import unreal

from combat.paths import (
    FIRE_WARD_VAR, ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.torch_tuning import BURN_OUT_VAR, LIT_VAR
from forest_generator.npc_placement import NAV_REACHABLE_EXTENT_CM
from forest_generator.npc_ward import (
    NPC_WARD_FLEE_S, NPC_WARD_HALF_ANGLE_DEG, NPC_WARD_HOLD_S, NPC_WARD_RANGE_CM,
    NPC_WARD_RING_CM,
)
from npc.monster_tuning import TUNED_VAR
from npc.paths import (
    AGGRO_VAR, NPC_DIR, STALK_CHARGING_VAR, STALK_ROAR_UNTIL_VAR,
    WARD_FLEE_UNTIL_VAR, WARD_SIDE_VAR, WARD_SINCE_VAR,
)
from probes.probe_knife import _file

WENDIGO_AI = f"{NPC_DIR}/BP_ForestWandererAI_Wendigo"
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             ("EquippedIndex", "NeedsRefresh", SIGHTS_FORCED_VAR)]
            + [(ITEM_BP_PATH, LIT_VAR), (ITEM_BP_PATH, BURN_OUT_VAR),
               (WENDIGO_AI, WARD_SINCE_VAR)])

STICK = "BP_Stick_C"

START_CM = 600.0      # inside the fire's range, outside the wendigo's reach
SAMPLE_S = 0.1
FACING_DOT = 0.7      # within 45 degrees of the player
HELD_S = 1.2          # how long the first hold is watched
FLANK_SAMPLES = 150   # 15 s of game time to get round and swing
FLEE_WATCH_S = 3.0


def _wendigos(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls
            if c.get_class().get_name().startswith("BP_ForestWandererAI_Wendigo")
            and c.get_controlled_pawn() is not None]


def _on_navmesh(p, point):
    return unreal.NavigationSystemV1.project_point_to_navigation(
        p.world(), point, None, None, unreal.Vector(*NAV_REACHABLE_EXTENT_CM))


def _state(p, ctrl, npc, player):
    """Where the wendigo stands about the player, and what it is doing."""
    at, home = npc.get_actor_location(), player.get_actor_location()
    dx, dy = at.x - home.x, at.y - home.y
    gap = math.hypot(dx, dy) or 1.0
    fwd, look, vel = (player.get_actor_forward_vector(), npc.get_actor_forward_vector(),
                      npc.get_velocity())
    speed = math.hypot(vel.x, vel.y)
    return dict(
        gap=gap, bearing=math.degrees(math.atan2(dy, dx)),
        # Off the line the player faces along: 0 is dead ahead, 180 behind.
        off=math.degrees(math.acos(max(-1.0, min(1.0, (fwd.x * dx + fwd.y * dy) / gap)))),
        facing=-(look.x * dx + look.y * dy) / gap, speed=speed,
        away=(vel.x * dx + vel.y * dy) / (gap * (speed or 1.0)),
        swung=float(p.get(ctrl, "NextAttackTime")))


def _face(p, player, npc):
    """Turn the player, and so the fire, at the wendigo. Through the view:
    the body's yaw is the controller's, written back every frame."""
    at, home = npc.get_actor_location(), player.get_actor_location()
    p.controller().set_control_rotation(unreal.Rotator(
        pitch=0.0, yaw=math.degrees(math.atan2(at.y - home.y, at.x - home.x)), roll=0.0))


def _turn(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


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


def _burning_stick(p, comp):
    """Take the issued stick in hand and set it burning; None without one."""
    bag = list(p.get(comp, "Inventory"))
    names = [i.get_class().get_name() for i in bag]
    if STICK not in names:
        return None
    stick = bag[names.index(STICK)]
    p.set(comp, "EquippedIndex", names.index(STICK))
    p.set(comp, "NeedsRefresh", True)
    yield lambda: p.get(comp, "Held") == stick
    p.set(stick, BURN_OUT_VAR, p.time() + 1.0e6)
    p.set(stick, LIT_VAR, True)
    yield 0.1
    return stick


def _run(p):
    yield lambda: len(_wendigos(p)) > 0
    yield 0.5
    ctrl = _wendigos(p)[0]
    npc, player = ctrl.get_controlled_pawn(), p.pawn()
    comp = p.component(player, WEAPON_COMP_CLASS_PATH)
    reach = float(p.get(ctrl, TUNED_VAR["melee_range_cm"]))

    # A headless -game run was found with no navmesh tiles at all, and none
    # being built; RebuildNavigation builds them in a few seconds.
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None

    p.check("no fire is held out until something lights one, and no hold is under way",
            p.get(comp, FIRE_WARD_VAR) is False
            and float(p.get(ctrl, WARD_SINCE_VAR)) == 0.0
            and float(p.get(ctrl, WARD_FLEE_UNTIL_VAR)) == 0.0)

    # --- held ----------------------------------------------------------------
    stick = yield from _burning_stick(p, comp)
    p.check("the player has the issued stick in hand, burning, and the fire is still "
            "down until the use key is held",
            stick is not None and p.get(comp, FIRE_WARD_VAR) is False)
    if stick is None:
        return
    p.set(comp, SIGHTS_FORCED_VAR, True)
    yield lambda: bool(p.get(comp, FIRE_WARD_VAR))
    home = player.get_actor_location()
    yaw = player.get_actor_rotation().yaw
    ahead = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.0)
    ground = _on_navmesh(p, home + ahead * START_CM)
    p.check(f"a wendigo is stood {START_CM / 100:.0f} m in front of the player, "
            f"who holds fire out", ground is not None)
    if ground is None:
        return
    npc.set_actor_location_and_rotation(
        ground + unreal.Vector(0.0, 0.0, 95.0),
        unreal.Rotator(pitch=0.0, yaw=yaw + 180.0, roll=0.0), False, True)
    yield lambda: bool(p.get(ctrl, AGGRO_VAR))
    yield lambda: float(p.get(ctrl, WARD_SINCE_VAR)) > 0.0
    began, side = p.time(), float(p.get(ctrl, WARD_SIDE_VAR))
    p.check("aggro, with the fire in front of it, it is held off: a hold begins, "
            "and it picks a way round",
            side in (1.0, -1.0) and float(p.get(ctrl, STALK_ROAR_UNTIL_VAR)) == 0.0,
            f"side {side}")
    first = _state(p, ctrl, npc, player)
    held = [first]
    while p.time() - began < HELD_S and held[-1]["off"] < NPC_WARD_HALF_ANGLE_DEG - 15.0:
        yield SAMPLE_S
        held.append(_state(p, ctrl, npc, player))
    p.check("held, it does not swing, and is kept out of its reach",
            all(s["swung"] == 0.0 for s in held)
            and min(s["gap"] for s in held) > reach + 50.0,
            f"nearest {min(s['gap'] for s in held):.0f} cm of a {reach:.0f} cm reach")
    turned = _turn(first["bearing"], held[-1]["bearing"])
    p.check("...it goes round the player, facing them",
            abs(turned) >= 15.0 and max(s["speed"] for s in held) > 100.0
            and sorted(s["facing"] for s in held)[len(held) // 2] >= FACING_DOT,
            f"{turned:.0f} deg round in {p.time() - began:.1f} s, median facing dot "
            f"{sorted(s['facing'] for s in held)[len(held) // 2]:.2f}")

    # --- past the fire: the player has not turned ------------------------------
    flank = []
    while len(flank) < FLANK_SAMPLES:
        flank.append(_state(p, ctrl, npc, player))
        if flank[-1]["swung"] > 0.0:
            break
        yield SAMPLE_S
    front = [s for s in flank if s["off"] < NPC_WARD_HALF_ANGLE_DEG - 5.0]
    p.check(f"it gets more than {NPC_WARD_HALF_ANGLE_DEG:.0f} deg round the fire, "
            f"and then it attacks",
            flank[-1]["swung"] > 0.0 and flank[-1]["off"] >= NPC_WARD_HALF_ANGLE_DEG
            and flank[-1]["gap"] <= reach + 50.0,
            f"swung {flank[-1]['off']:.0f} deg off the player's front, at "
            f"{flank[-1]['gap']:.0f} cm, after {len(flank) * SAMPLE_S:.1f} s")
    p.check("...never while the fire was between them",
            all(s["gap"] > reach for s in front),
            f"{len(front)} samples in front, nearest "
            f"{min([s['gap'] for s in front] or [0.0]):.0f} cm")
    if flank[-1]["swung"] == 0.0:
        return

    # --- the player turns the fire on it --------------------------------------
    for _ in range(8):          # a swing under way lands; a pass later it is held
        _face(p, player, npc)
        yield SAMPLE_S
    swings = float(p.get(ctrl, "NextAttackTime"))
    again = []
    for _ in range(25):
        _face(p, player, npc)
        again.append(_state(p, ctrl, npc, player))
        yield SAMPLE_S
    p.check("the player turns the fire on it: the swings stop, and it is back "
            "out of reach",
            all(s["swung"] == swings for s in again) and again[-1]["gap"] > reach + 50.0
            and again[-1]["gap"] <= NPC_WARD_RANGE_CM,
            f"{again[-1]['gap']:.0f} cm off (the ring is {NPC_WARD_RING_CM:.0f})")

    # --- held off long enough --------------------------------------------------
    p.check("it has not run yet: the hold is short of its "
            f"{NPC_WARD_HOLD_S:.0f} s", float(p.get(ctrl, WARD_FLEE_UNTIL_VAR)) == 0.0)
    p.set(ctrl, WARD_SINCE_VAR, p.time() - (NPC_WARD_HOLD_S - 0.5))
    for _ in range(30):
        if float(p.get(ctrl, WARD_FLEE_UNTIL_VAR)) > 0.0:
            break
        _face(p, player, npc)
        yield SAMPLE_S
    until = float(p.get(ctrl, WARD_FLEE_UNTIL_VAR))
    p.check(f"held off {NPC_WARD_HOLD_S:.0f} s, it gives up: it will run for "
            f"{NPC_WARD_FLEE_S:.0f} s",
            abs(until - p.time() - NPC_WARD_FLEE_S) < 1.0,
            f"{until - p.time():.1f} s to go")
    p.check("...and its hunt starts over for when it comes back",
            float(p.get(ctrl, STALK_ROAR_UNTIL_VAR)) == 0.0
            and not p.get(ctrl, STALK_CHARGING_VAR)
            and float(p.get(ctrl, WARD_SINCE_VAR)) == 0.0)
    p.set(comp, SIGHTS_FORCED_VAR, False)   # it runs with the fire down too
    start = _state(p, ctrl, npc, player)
    fled = [start]
    while p.time() < until and len(fled) < FLEE_WATCH_S / SAMPLE_S:
        yield SAMPLE_S
        fled.append(_state(p, ctrl, npc, player))
    running = [s for s in fled if s["speed"] > 200.0]
    p.check("it runs away from the player, not swinging, though the fire is down",
            fled[-1]["gap"] > start["gap"] + 600.0 and len(running) > 0
            and sorted(s["away"] for s in running)[len(running) // 2] >= 0.7
            and all(s["swung"] == swings for s in fled),
            f"{start['gap'] / 100:.1f} -> {fled[-1]['gap'] / 100:.1f} m in "
            f"{len(fled) * SAMPLE_S:.1f} s")
