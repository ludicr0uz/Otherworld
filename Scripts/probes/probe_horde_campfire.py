"""The Horde Survival level's permanent campfire: one fire burning in the
fort from the start, which draws the zombies as a lit campfire does and
never burns out (survival/permanent_campfire.py, placed by
forest_import/fort.py).

  - the level holds one BP_PermanentCampfire, in the fort, beside the
    player's start, and it is a BP_Campfire (what the zombies look for);
  - it has no life span: it never burns out;
  - every zombie on patrol is Drawn, to that fire, and one closes on it;
  - it draws from the whole level: moved FAR_CM off a zombie (past the
    NPC_DRAWN_RANGE_CM a lit campfire draws from), it still draws it;
  - the player beside it is warmed.

The fire's rate is raised for the warmth check and the night's cold zeroed,
as probe_campfire.py does, for the same reasons.
"""

SYSTEMS = ('survival', 'npc')

LEVEL = "/Game/Maps/Lvl_Horde_Survival"  # the fire is this level's alone

import unreal

from forest_generator.npc_drawn import NPC_DRAWN_ARRIVE_CM, NPC_DRAWN_RANGE_CM
from forest_generator.npc_placement import NAV_REACHABLE_EXTENT_CM
from forest_import.fort import CAMPFIRE_OFFSET_CM
from npc.paths import DRAWN_TO_VAR, DRAWN_VAR
from probes.probe_campfire import COOL, RATE, WRITABLE as _FIRE_WRITABLE
from probes.probe_campfire import _fires, _watch
from probes.probe_zombie_drawn import _controllers, _gap, _on_patrol
from survival.campfire import WARM_RATE_VAR
from survival.paths import (
    PERMANENT_CAMPFIRE_BP_PATH, PERMANENT_CAMPFIRE_CLASS_PATH, SURVIVAL_CLASS_PATH,
)
from survival.tuning import CAMPFIRE_WARM_RADIUS_CM
from world.day_night_blueprint import NIGHT_COLD_VAR
from world.paths import DAY_NIGHT_CLASS_PATH

WRITABLE = list(_FIRE_WRITABLE) + [(PERMANENT_CAMPFIRE_BP_PATH, WARM_RATE_VAR)]

BEAT_S = 1.2              # two of the tree's 0.5 s passes, and a little
WALK_S = 3.0
CLOSED_CM = 150.0         # it closes on the fire by at least this in WALK_S
FAR_CM = NPC_DRAWN_RANGE_CM * 1.5   # well past a lit campfire's reach


def probe(p):
    yield lambda: len(_controllers(p, "Zombie")) > 0
    yield 0.5
    player = p.pawn()

    def nav():
        return unreal.NavigationSystemV1.project_point_to_navigation(
            p.world(), player.get_actor_location(), None, None,
            unreal.Vector(*NAV_REACHABLE_EXTENT_CM)) is not None
    if not nav():
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield nav

    mine = list(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(PERMANENT_CAMPFIRE_CLASS_PATH)))
    fires = _fires(p)
    p.check("the level holds one permanent campfire, and it is a campfire",
            len(mine) == 1 and fires == mine, f"{len(mine)} permanent, {len(fires)} campfires")
    if len(mine) != 1:
        return
    fire = mine[0]
    at = fire.get_actor_location()
    x, y = CAMPFIRE_OFFSET_CM
    p.check("...in the fort, beside the player's start",
            abs(at.x - x) < 1.0 and abs(at.y - y) < 1.0
            and _gap(player, fire) < CAMPFIRE_WARM_RADIUS_CM,
            f"at ({at.x:.0f}, {at.y:.0f}), the player {_gap(player, fire):.0f} cm off")
    p.check("...with no life span: it never burns out", fire.get_life_span() == 0.0,
            str(fire.get_life_span()))

    yield BEAT_S
    zombies = _controllers(p, "Zombie")
    patrol = [c for c in zombies if _on_patrol(p, c)
              and _gap(c.get_controlled_pawn(), fire) > NPC_DRAWN_ARRIVE_CM + 1000.0]
    drawn = [c for c in patrol if p.get(c, DRAWN_VAR) and p.get(c, DRAWN_TO_VAR) == fire]
    p.check("every zombie on patrol is Drawn, to the permanent fire",
            len(patrol) > 0 and len(drawn) == len(patrol),
            f"{len(drawn)} of {len(patrol)} on patrol ({len(zombies)} zombies); fire "
            f"{min([_gap(c.get_controlled_pawn(), fire) for c in patrol] or [0]) / 100:.0f}-"
            f"{max([_gap(c.get_controlled_pawn(), fire) for c in patrol] or [0]) / 100:.0f} m off")
    if drawn:
        npc = max(drawn, key=lambda c: _gap(c.get_controlled_pawn(), fire)).get_controlled_pawn()
        before = _gap(npc, fire)
        yield WALK_S
        after = _gap(npc, fire)
        p.check(f"...and closes on it (by {CLOSED_CM:.0f} cm or more in {WALK_S:g} s)",
                before - after >= CLOSED_CM, f"{before:.0f} -> {after:.0f} cm")

        # Out of any campfire's reach: the fire moved away from that zombie,
        # flat (the level holds no spot that far from one), then put back.
        ctrl = npc.get_controller()
        here, there = npc.get_actor_location(), fire.get_actor_location()
        dx, dy = there.x - here.x, there.y - here.y
        way = (dx * dx + dy * dy) ** 0.5 or 1.0
        fire.set_actor_location(unreal.Vector(here.x + dx / way * FAR_CM,
                                              here.y + dy / way * FAR_CM, there.z),
                                False, True)
        far = _gap(npc, fire)
        yield BEAT_S
        p.check(f"...and draws from the whole level: {FAR_CM / 100:.0f} m off (a "
                f"lit campfire draws from {NPC_DRAWN_RANGE_CM / 100:.0f} m) it is "
                f"still Drawn, to it",
                far > NPC_DRAWN_RANGE_CM and bool(p.get(ctrl, DRAWN_VAR))
                and p.get(ctrl, DRAWN_TO_VAR) == fire and _on_patrol(p, ctrl),
                f"{far / 100:.0f} m off: Drawn {p.get(ctrl, DRAWN_VAR)}, "
                f"on patrol {_on_patrol(p, ctrl)}")
        fire.set_actor_location(there, False, True)

    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    if cycle is not None:
        p.set(cycle, NIGHT_COLD_VAR, 0.0)
    survival = p.component(player, SURVIVAL_CLASS_PATH)
    p.set(fire, WARM_RATE_VAR, RATE)
    gap = _gap(player, fire)
    gained, dt = yield from _watch(p, survival)
    p.check("the player beside it is warmed",
            gap < CAMPFIRE_WARM_RADIUS_CM and dt > 0 and gained > 0
            and abs(gained - RATE * dt) <= 0.25 * RATE * dt + 1e-3,
            f"{gap:.0f} cm away: +{gained:.4f} from {COOL} in {dt:.4f} s")
