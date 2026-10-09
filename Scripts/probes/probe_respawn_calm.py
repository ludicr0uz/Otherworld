"""Nobody comes back from a respawn still hunting: not a killed wanderer's
replacement, and not the pack of a level reopened after the player's death.

One wanderer is put beside the player, where its touch sense makes it Aggro,
then its Health is written to 0. Its replacement (RespawnDelay shortened: a
headless game's clock never reaches the real ten seconds) must be a new
controller whose Aggro, and whose Blackboard's, are unset, and stay unset
over a few passes of its tree while the player makes no noise: nothing of
the dead one's hunt is handed on.

Then a second wanderer is made Aggro and the level is reopened, which is what
the death menu's restart does: Aggro lives on the controllers and the noise
record on the GameMode, and both are the old world's. The new pack must be
out at its placed distance, patrolling, and still patrolling seconds later.
"""

SYSTEMS = ('health',)

import unreal

from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from combat.respawn import RESPAWN_BAND, RESPAWN_DELAY_VAR
from combat import health_vars as HV
from npc.paths import AGGRO_REASON_VAR, AGGRO_VAR, BB_AGGRO_KEY, PATROL_READY_VAR

WRITABLE = [(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, RESPAWN_DELAY_VAR)]

PROBE_DELAY_S = 0.5
SETTLE = 1.5          # game seconds: a few passes of the tree
REOPEN_SETTLE = 3.0
BESIDE_CM = 100.0     # well inside every creature's touch range


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def _navmesh(p):
    return unreal.NavigationSystemV1.get_random_location_in_navigable_radius(
        p.world(), p.pawn().get_actor_location(), RESPAWN_BAND[1]) is not None


def probe(p):
    yield lambda: len(_wanderers(p)) > 0
    yield 0.5
    if not _navmesh(p):
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh round the player: sent RebuildNavigation")
    yield lambda: _navmesh(p)
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())

    before = _wanderers(p)
    calm = [c for c in before if not p.get(c, AGGRO_VAR)]
    if not calm:
        p.check("a wanderer is patrolling to start from", False)
        return
    ctrl = calm[0]
    npc = ctrl.get_controlled_pawn()
    npc.set_actor_location(
        p.pawn().get_actor_location() + unreal.Vector(BESIDE_CM, 0.0, 0.0), False, True)
    yield lambda: p.get(ctrl, AGGRO_VAR)
    p.check("beside the player a wanderer goes aggro", p.get(ctrl, AGGRO_VAR),
            f"reason {p.get(ctrl, AGGRO_REASON_VAR)!r}")

    theirs = p.component(npc, HEALTH_CLASS_PATH)
    p.set(theirs, RESPAWN_DELAY_VAR, PROBE_DELAY_S)
    p.set(theirs, "Health", 0.0)
    yield lambda: p.get(theirs, "Dead")
    died = now()
    known = {c.get_name() for c in before}
    fresh = lambda: [c for c in _wanderers(p) if c.get_name() not in known]
    yield lambda: fresh() or now() - died > PROBE_DELAY_S * 6
    new = fresh()
    p.check("killed, it is replaced", len(new) == 1, f"{len(new)} new controllers")
    if not new:
        return
    heir = new[0]
    gap = heir.get_controlled_pawn().get_actor_location().distance(
        p.pawn().get_actor_location())
    p.check("the replacement spawns patrolling", not p.get(heir, AGGRO_VAR),
            f"{gap / 100.0:.0f} m from the player, reason {p.get(heir, AGGRO_REASON_VAR)!r}")
    yield lambda: p.get(heir, PATROL_READY_VAR)
    yield SETTLE
    board = heir.get_editor_property("blackboard")
    p.check("...and is still patrolling a few passes of its tree later",
            not p.get(heir, AGGRO_VAR),
            f"reason {p.get(heir, AGGRO_REASON_VAR)!r}")
    p.check("...its Blackboard's Aggro unset, so the Hunt branch stays shut",
            board is not None and not board.get_value_as_bool(BB_AGGRO_KEY))

    # --- the player's own respawn: the level reopened -------------------------
    pack = [c for c in _wanderers(p) if not p.get(c, AGGRO_VAR)]
    if not pack:
        p.check("a second wanderer is patrolling to pull in", False)
        return
    pack[0].get_controlled_pawn().set_actor_location(
        p.pawn().get_actor_location() + unreal.Vector(BESIDE_CM, 0.0, 0.0), False, True)
    yield lambda: p.get(pack[0], AGGRO_VAR)
    old_mode = p.game_mode()
    unreal.GameplayStatics.open_level(p.world(), p.map_path, True, "")
    yield lambda: p.game_mode() is not None and p.game_mode() != old_mode
    yield lambda: p.pawn() is not None and len(_wanderers(p)) > 0
    yield lambda: all(p.get(c, PATROL_READY_VAR) for c in _wanderers(p))
    hot = [c for c in _wanderers(p) if p.get(c, AGGRO_VAR)]
    p.check("the level reopened, the new pack is patrolling", not hot,
            f"{len(hot)}/{len(_wanderers(p))} aggro")
    yield REOPEN_SETTLE
    hot = [f"{c.get_name()}: {p.get(c, AGGRO_REASON_VAR)}"
           for c in _wanderers(p) if p.get(c, AGGRO_VAR)]
    p.check("...and still is seconds later, the player silent",
            not hot, "; ".join(hot[:3]))
