"""A fire draws the zombies: one lit within 200 m, and a zombie that has not
noticed the player leaves its patrol and walks to it, slowly.

npc/verify_drawn.py reads the graph; this watches a zombie do it. The fire
is lit the way the game lights one (probe_campfire.py's steps: wood cut
with the axe, then a strike of the matches), and the player is then stood
well out of the zombies' sight, so nothing below is a hunt:

  - before the fire no zombie is Drawn;
  - once it burns, every zombie on patrol is Drawn, to that fire (a 200 m
    map: all of them are within reach);
  - a drawn zombie closes on the fire, at its patrol walk, not its run;
  - stood beside the fire it stays there;
  - the fire moved out of reach lets it go, and back in reach draws it again;
  - the fire gone (burnt out: the actor destroyed), it is let go for good;
  - a wendigo has no such state.

Any profile on disk is set aside first, as probe_campfire.py does.
"""

import os
import shutil

import unreal

from combat.paths import WEAPON_COMP_CLASS_PATH
from forest_generator.npc_drawn import NPC_DRAWN_ARRIVE_CM, NPC_DRAWN_RANGE_CM
from forest_generator.npc_placement import NAV_REACHABLE_EXTENT_CM
from npc.monster_tuning import monster_specs, stock_run_speed
from npc.paths import AGGRO_VAR, DRAWN_TO_VAR, DRAWN_VAR, RUN_SPEED_VAR
from probes.probe_campfire import MATCHES, WRITABLE as _FIRE_WRITABLE
from probes.probe_campfire import _cut_wood, _fires, _strike
from probes.probe_chop_tree import _equip
from probes.probe_knife import _file
from probes.probe_wendigo_catch_up import _ground, _put
from probes.probe_wendigo_stalk import _about, _walk_speed

WRITABLE = list(_FIRE_WRITABLE)

BEAT_S = 1.2              # two of the tree's 0.5 s passes, and a little
WALK_S = 3.0
CLOSED_CM = 150.0         # it closes on the fire by at least this in WALK_S
PLAYER_OFF_CM = (6000.0, 5000.0, 4000.0)    # tried in turn, four ways each
CLEAR_OF_PLAYER_CM = 3000.0                 # past a zombie's sight (20 m)
BESIDE_CM = NPC_DRAWN_ARRIVE_CM - 80.0
STILL_CMS = 20.0


def _controllers(p, creature):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls
            if c.get_class().get_name().startswith(f"BP_ForestWandererAI_{creature}")
            and c.get_controlled_pawn() is not None]


def _on_patrol(p, ctrl):
    return not p.get(ctrl, AGGRO_VAR)


def _gap(a, b):
    return _about(a.get_actor_location(), b.get_actor_location())[0]


def _away_spot(p, fire):
    """A spot on the navmesh well away from the fire, for the player."""
    at = fire.get_actor_location()
    for off in PLAYER_OFF_CM:
        for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            spot = _ground(p, at.x + sx * off, at.y + sy * off)
            if spot:
                return spot
    return None


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: len(_controllers(p, "Zombie")) > 0
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)

    # A headless -game run was found with no navmesh tiles (probe_npc_strafe.py).
    def nav():
        return unreal.NavigationSystemV1.project_point_to_navigation(
            p.world(), player.get_actor_location(), None, None,
            unreal.Vector(*NAV_REACHABLE_EXTENT_CM)) is not None
    if not nav():
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield nav

    zombies = _controllers(p, "Zombie")
    p.check("with no fire burning, no zombie is Drawn",
            not _fires(p) and not any(p.get(c, DRAWN_VAR) for c in zombies),
            f"{len(zombies)} zombies, {len(_fires(p))} fires")

    got = yield from _cut_wood(p, player, wc)
    if got:
        yield from _equip(p, wc, MATCHES)
        yield from _strike(p, wc)
    fires = _fires(p)
    p.check("the player cuts wood and lights a campfire", got and len(fires) == 1,
            f"wood {got}, fires {len(fires)}")
    if len(fires) != 1:
        return
    fire = fires[0]
    home = fire.get_actor_location()

    spot = _away_spot(p, fire)
    if spot:
        _put(player, spot)
    else:
        p.note("no navmesh spot away from the fire: the player stays beside it")
    yield BEAT_S

    patrol = [c for c in _controllers(p, "Zombie") if _on_patrol(p, c)
              and _gap(c.get_controlled_pawn(), player) > CLEAR_OF_PLAYER_CM
              and _gap(c.get_controlled_pawn(), fire) > NPC_DRAWN_ARRIVE_CM + 1000.0]
    drawn = [c for c in patrol if p.get(c, DRAWN_VAR) and p.get(c, DRAWN_TO_VAR) == fire]
    p.check(f"the fire lit, every zombie on patrol (all within "
            f"{NPC_DRAWN_RANGE_CM / 100:.0f} m here) is Drawn, to that fire",
            len(patrol) > 0 and len(drawn) == len(patrol),
            f"{len(drawn)} of {len(patrol)} on patrol; fire "
            f"{min([_gap(c.get_controlled_pawn(), fire) for c in patrol] or [0]) / 100:.0f}-"
            f"{max([_gap(c.get_controlled_pawn(), fire) for c in patrol] or [0]) / 100:.0f} m off")
    if not drawn:
        return
    ctrl = max(drawn, key=lambda c: _gap(c.get_controlled_pawn(), player))
    npc = ctrl.get_controlled_pawn()

    before = _gap(npc, fire)
    yield WALK_S
    after = _gap(npc, fire)
    p.check(f"a drawn zombie closes on the fire (by {CLOSED_CM:.0f} cm or more "
            f"in {WALK_S:g} s)", before - after >= CLOSED_CM,
            f"{before:.0f} -> {after:.0f} cm")
    spec = monster_specs("Zombie")
    walk = (float(p.get(ctrl, RUN_SPEED_VAR)) * spec["run_speed_cms"]
            / stock_run_speed("Zombie") * spec["patrol_speed_scale"])
    p.check("...slowly: at its patrol walk, not its run",
            abs(_walk_speed(npc) - walk) < 1.0
            and _walk_speed(npc) < float(p.get(ctrl, RUN_SPEED_VAR)),
            f"MaxWalkSpeed {_walk_speed(npc):.0f}, the walk {walk:.0f}, the run "
            f"{float(p.get(ctrl, RUN_SPEED_VAR)):.0f}")
    p.check("...still on patrol: drawn is not aggro", _on_patrol(p, ctrl))

    # Beside the fire, on the side away from the player.
    way = _about(home, player.get_actor_location())[0] or 1.0
    ux = (home.x - player.get_actor_location().x) / way
    uy = (home.y - player.get_actor_location().y) / way
    near = _ground(p, home.x + ux * BESIDE_CM, home.y + uy * BESIDE_CM)
    if near:
        _put(npc, near)
        yield BEAT_S
        vel = npc.get_velocity()
        p.check(f"stood within {NPC_DRAWN_ARRIVE_CM:.0f} cm of the fire it stays "
                f"there, still Drawn",
                p.get(ctrl, DRAWN_VAR) and (vel.x ** 2 + vel.y ** 2) ** 0.5 < STILL_CMS
                and _gap(npc, fire) <= NPC_DRAWN_ARRIVE_CM + 20.0,
                f"{_gap(npc, fire):.0f} cm off, moving "
                f"{(vel.x ** 2 + vel.y ** 2) ** 0.5:.0f} cm/s, Drawn {p.get(ctrl, DRAWN_VAR)}")
    else:
        p.note("no navmesh beside the fire: the stand was not watched")

    # Out of reach: the fire itself moved away, flat (a 200 m map has no spot
    # 200 m from a zombie).
    fire.set_actor_location(home + unreal.Vector(NPC_DRAWN_RANGE_CM + 5000.0, 0.0, 0.0),
                            False, True)
    if _gap(npc, fire) > NPC_DRAWN_RANGE_CM:
        yield BEAT_S
        p.check(f"a fire further than {NPC_DRAWN_RANGE_CM / 100:.0f} m does not "
                f"draw it: it is let go",
                not p.get(ctrl, DRAWN_VAR), f"{_gap(npc, fire) / 100:.0f} m off")
        fire.set_actor_location(home, False, True)
        yield BEAT_S
        p.check("...and back in reach, it is Drawn again", bool(p.get(ctrl, DRAWN_VAR)),
                f"{_gap(npc, fire) / 100:.0f} m off")
    else:
        p.note("the fire would not move: the range was not watched")

    fire.destroy_actor()
    yield BEAT_S
    p.check("the fire gone, it is let go: not Drawn, and to nothing",
            not p.get(ctrl, DRAWN_VAR) and not p.get(ctrl, DRAWN_TO_VAR)
            and _on_patrol(p, ctrl),
            f"Drawn {p.get(ctrl, DRAWN_VAR)}, DrawnTo {p.get(ctrl, DRAWN_TO_VAR)}")

    wendigos = _controllers(p, "Wendigo")

    def has_state(c):
        try:
            p.get(c, DRAWN_VAR)
            return True
        except Exception:
            return False
    p.check("a wendigo has no such state", len(wendigos) > 0
            and not any(has_state(c) for c in wendigos), f"{len(wendigos)} wendigos")
