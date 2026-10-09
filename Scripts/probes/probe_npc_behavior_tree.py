"""The wanderers run on their Behavior Trees: patrol, notice, hunt, corpse.

verify_npc_blueprints.py proves the tree and the steps are authored; this
proves the game runs them. Every wanderer's brain is a BehaviorTreeComponent
on its own BT_*, and its Pulse step has run (health applied, patrol set up)
-- nothing but the tree calls it. Then one wanderer is put beside the player,
where its touch sense fires: Aggro flips on the controller AND the Blackboard
(the Hunt branch's gate), and the Hunt branch swings at the player. Last, its pawn is marked Dead:
the Pulse step makes it a corpse and stops the tree.
"""

SYSTEMS = ('npc',)

import unreal

from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from npc.paths import (
    AGGRO_REASON_VAR, AGGRO_VAR, BB_AGGRO_KEY, BB_REASON_KEY, CORPSE_VAR,
    NEXT_PATROL_VAR, PATROL_READY_VAR, STATS_APPLIED_VAR,
)
from combat import health_vars as HV

WRITABLE = [(HEALTH_BP_PATH, HV.Dead)]

SETTLE = 1.5          # game seconds: a few passes of the tree
BESIDE_CM = 100.0     # well inside every creature's touch range


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def probe(p):
    yield lambda: len(_wanderers(p)) > 0
    yield SETTLE
    ctrls = _wanderers(p)
    p.check("the wanderers are possessed", len(ctrls) > 0, f"{len(ctrls)}")

    wrong = []
    for c in ctrls:
        brain = c.get_editor_property("brain_component")
        if not isinstance(brain, unreal.BehaviorTreeComponent) or not brain.is_running():
            wrong.append(f"{c.get_name()}: {type(brain).__name__}")
    p.check("every wanderer's brain is a running BehaviorTreeComponent",
            not wrong, "; ".join(wrong[:3]))
    pulsed = [c for c in ctrls if p.get(c, STATS_APPLIED_VAR) and p.get(c, PATROL_READY_VAR)]
    p.check("the tree's Pulse step ran for each (stats applied, patrol set up)",
            len(pulsed) == len(ctrls), f"{len(pulsed)}/{len(ctrls)}")
    calm = [c for c in ctrls if not p.get(c, AGGRO_VAR)]
    p.check("they start patrolling", len(calm) > 0, f"{len(calm)}/{len(ctrls)} calm")
    if not calm:
        return
    strolled = [c for c in calm if p.get(c, NEXT_PATROL_VAR) > 0.0]
    p.check("...and the Patrol branch's Stroll step picks their points",
            len(strolled) == len(calm), f"{len(strolled)}/{len(calm)}")

    ctrl = calm[0]
    npc, player = ctrl.get_controlled_pawn(), p.pawn()
    board = ctrl.get_editor_property("blackboard")
    p.check("a patrolling wanderer's Blackboard says not aggro",
            board is not None and not board.get_value_as_bool(BB_AGGRO_KEY))
    spot = player.get_actor_location() + unreal.Vector(BESIDE_CM, 0.0, 0.0)
    npc.set_actor_location(spot, False, True)
    yield lambda: p.get(ctrl, AGGRO_VAR)
    p.check("beside the player it notices (touch)", p.get(ctrl, AGGRO_VAR),
            f"reason {p.get(ctrl, AGGRO_REASON_VAR)!r}")
    yield 0.2
    p.check("...and the Blackboard's Aggro follows, which gates the Hunt branch",
            board.get_value_as_bool(BB_AGGRO_KEY),
            f"reason {board.get_value_as_string(BB_REASON_KEY)!r}")

    yield lambda: p.get(ctrl, "NextAttackTime") > 0.0
    p.check("the Hunt branch runs: Chase, then Swing at the player in reach",
            p.get(ctrl, "NextAttackTime") > 0.0,
            f"NextAttackTime {p.get(ctrl, 'NextAttackTime'):.2f}")

    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, "Dead", True)
    yield lambda: p.get(ctrl, CORPSE_VAR)
    p.check("marked Dead, the Pulse step makes it a corpse", p.get(ctrl, CORPSE_VAR))
    yield 0.2
    brain = ctrl.get_editor_property("brain_component")
    p.check("...and the corpse's tree is stopped", not brain.is_running())
