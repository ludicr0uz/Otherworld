"""The population budget (npc/population.py, task M29), per controller: on
possession it registers its wanderer with the creature's TunePop* numbers
and the single-player replacement's band and wait; and the table's numbers
make a budget.

That the count follows two clients standing far apart on a server is
probes/probe_net_population.py's; that single player replaces a dead
wanderer itself, behind IsStandalone, is combat/verify/health.py's.
"""

import unreal

from forest_generator.npc_placement import NPC_SPAWN_MAX_DISTANCE_CM, NPC_VARIANTS
from net.relevancy_consts import CHARACTER, M_TO_CM
from npc.monster_tuning import monster_specs
from npc.paths import AI_BP_PATH
from npc.population import BAND_PINS, BUDGET_PINS
from npc.verify import _close, _drivers, _events_into, _fed, _feeders, _ins, _num, _title, check

WANTED = {"Wanderer"} | {pin for pin, _c in BUDGET_PINS} | {pin for pin, _v in BAND_PINS}


def check_budget(key):
    spec = monster_specs(key)
    check(f"{key}: the server's cap is at least one player's ({spec['pop_per_player']:g} "
          f"near a player, {spec['pop_server_cap']:g} alive)",
          0.0 <= spec["pop_per_player"] <= spec["pop_server_cap"])
    check(f"{key}: a wanderer is removed past where a client is sent it "
          f"({CHARACTER.cull_m:.0f} m) and past the band a new one appears in",
          spec["pop_despawn_cm"] > CHARACTER.cull_m * M_TO_CM
          and spec["pop_despawn_cm"] > NPC_SPAWN_MAX_DISTANCE_CM, f"{spec['pop_despawn_cm']:g} cm")


def check_population(path):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag} exists", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    asks = [n for n in ed.list_all_nodes() if WANTED <= _ins(n)]
    check(f"{tag}: one RegisterWanderer, run by possession", len(asks) == 1
          and _events_into(asks[0]) == {"Event"} and bool(_drivers(asks[0])),
          f"{len(asks)} node(s); {[sorted(_events_into(n)) for n in asks]}")
    if len(asks) != 1:
        return
    ask = asks[0]
    check(f"{tag}: ...of the pawn it possessed",
          ["Event On Possess"] == [_title(f) for f in _feeders(ask, "Wanderer")],
          f"{[_title(f) for f in _feeders(ask, 'Wanderer')]}")
    off = [pin for pin, column in BUDGET_PINS if not _fed(ask, pin, column)]
    check(f"{tag}: ...with the creature's budget off its TunePop* variables", not off, f"{off}")
    off = [f"{pin}={_num(ask, pin)}" for pin, value in BAND_PINS if not _close(_num(ask, pin), value)]
    check(f"{tag}: ...and the single-player replacement's band and wait", not off, f"{off}")


def run():
    for variant in NPC_VARIANTS:
        check_budget(variant.key)
    for path in [AI_BP_PATH] + [variant.ai_blueprint for variant in NPC_VARIANTS]:
        check_population(path)
