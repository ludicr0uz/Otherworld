"""verify.fixtures -- the saved assets more than one verifier section reads,
loaded from disk once when this module is first imported.

Anything a single section needs, it loads itself. A value moves here only when
a second section needs it, so no section depends on another having run first.
"""

import unreal

from combat.paths import (
    AMMO_BP_PATH, CHARACTER_BP_PATH, GAME_MODE_BP_PATH, HEALTH_BP_PATH, NPC_BP_PATH,
    WEAPON_COMP_BP_PATH,
)
from combat.tuning import DEBUFF_DRAIN_HP_PER_S
from combat.verify.common import BEL, PIN, by_pins, cdo, graph, load, num_pin

_eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

health_bp = load(HEALTH_BP_PATH)
h = cdo(health_bp)
hg = graph(health_bp).list_all_nodes()
# Every montage in the health graph; there should be exactly one, the flinch.
_montages = by_pins(hg, "Asset", "SlotNodeName")

wc = load(WEAPON_COMP_BP_PATH)
w = cdo(wc)
wc_cdo = cdo(wc)
wg = graph(wc).list_all_nodes()
titles = [str(BEL.get_node_title(n)).replace("\n", " ") for n in wg]

gm = load(GAME_MODE_BP_PATH)
char = load(CHARACTER_BP_PATH)
npc = load(NPC_BP_PATH)
ag = graph(load(AMMO_BP_PATH)).list_all_nodes()


def _consumers(node):
    out = BEL.find_output_pin(node, "ReturnValue")
    return [PIN.get_owning_node(q) for q in out.list_connected_pins()] if out else []


# The debuff drain's nodes (combat/debuff_drain.py), found by their shape rather
# than by count: the one multiply carrying the drain rate feeds the loss, the
# loss feeds one subtract per variable, and each subtract feeds one Set. Two
# sections need them -- the Health-writer check and the PrevHealth-trigger check
# -- to tell the drain's legitimate writes from a probe left behind.
_rate = [n for n in hg if num_pin(n, "B") == DEBUFF_DRAIN_HP_PER_S]
_loss = [c for n in _rate for c in _consumers(n)]
drain_subtracts = [c for n in _loss for c in _consumers(n)]
drain_writes = [c for n in drain_subtracts for c in _consumers(n)]
