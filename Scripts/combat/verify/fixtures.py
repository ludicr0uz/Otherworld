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
from combat.tuning import HEALTH_DRAINS
from combat.verify.common import BEL, PIN, by_pins, cdo, graph, load, num_pin, pin_value
from combat.weapon_component.dead import OWNER_DEAD_VAR

_eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

health_bp = load(HEALTH_BP_PATH)
h = cdo(health_bp)
hg = graph(health_bp).list_all_nodes()
# Every montage in the health graph; there should be exactly one, the flinch.
_montages = by_pins(hg, "Asset", "SlotNodeName")

wc = load(WEAPON_COMP_BP_PATH)
w = cdo(wc)
wc_cdo = cdo(wc)



def _is_exec(pin):
    return "exec" in str(PIN.get_pin_type_display_string(pin)).lower()


def exec_reach(pins):
    """Every node the exec output ``pins`` run, directly or further on."""
    seen, todo = {}, [PIN.get_owning_node(q) for p in pins
                      for q in PIN.list_connected_pins(p)]
    while todo:
        n = todo.pop()
        if n.get_path_name() in seen:
            continue
        seen[n.get_path_name()] = n
        todo += [PIN.get_owning_node(q) for p in BEL.list_output_pins(n) if _is_exec(p)
                 for q in PIN.list_connected_pins(p)]
    return list(seen.values())


def _dead_arm(nodes):
    """The dead gate's True arm (weapon_component/dead.py): what it runs, and
    the pure nodes that feed nothing else."""
    marks = [n for n in nodes
             if str(BEL.get_node_title(n)) == f"Set {OWNER_DEAD_VAR}"
             and pin_value(n, OWNER_DEAD_VAR) == "true"]
    arm = {n.get_path_name(): n for m in marks
           for n in [m] + exec_reach(BEL.list_output_pins(m))}
    grew = True
    while grew:
        grew = False
        for n in list(arm.values()):
            for p in BEL.list_input_pins(n):
                for q in PIN.list_connected_pins(p):
                    f = PIN.get_owning_node(q)
                    if f.get_path_name() in arm or any(
                            _is_exec(x) for x in BEL.list_all_pins(f)):
                        continue
                    users = [PIN.get_owning_node(u) for o in BEL.list_output_pins(f)
                             for u in PIN.list_connected_pins(o)]
                    if all(u.get_path_name() in arm for u in users):
                        arm[f.get_path_name()] = f
                        grew = True
    return arm


# The weapon component's Tick is two states (weapon_component/dead.py): the
# living Tick, which is what every section but verify/dead.py reads as ``wg``,
# and the dead arm, which lets go of what the living one holds. Kept apart so
# "written once" stays a statement about the living Tick.
_wg_all = graph(wc).list_all_nodes()
_arm = _dead_arm(_wg_all)
wg_dead = list(_arm.values())
wg = [n for n in _wg_all if n.get_path_name() not in _arm]
titles = [str(BEL.get_node_title(n)).replace("\n", " ") for n in wg]

gm = load(GAME_MODE_BP_PATH)
char = load(CHARACTER_BP_PATH)
npc = load(NPC_BP_PATH)
ag = graph(load(AMMO_BP_PATH)).list_all_nodes()


def _consumers(node):
    out = BEL.find_output_pin(node, "ReturnValue")
    return [PIN.get_owning_node(q) for q in out.list_connected_pins()] if out else []


# The debuff drain's nodes (combat/debuff_drain.py), found by their shape rather
# than by count: one multiply per drained tag carries its rate, their sum feeds
# the loss, the loss feeds one subtract per variable, and each subtract feeds
# one Set. Two sections need them -- the Health-writer check and the
# PrevHealth-trigger check -- to tell the drain's legitimate writes from a
# probe left behind.
def _downstream(nodes):
    """Everything fed by ``nodes``, however many nodes away."""
    found, queue = {}, list(nodes)
    while queue:
        for c in _consumers(queue.pop()):
            if c.get_path_name() not in found:
                found[c.get_path_name()] = c
                queue.append(c)
    return list(found.values())


_rate = [n for n in hg if num_pin(n, "B") is not None and any(
    abs(num_pin(n, "B") - rate) < 1e-6 for _tag, rate in HEALTH_DRAINS)]
_drained = _downstream(_rate)
drain_writes = [n for n in _drained
                if str(n.get_class().get_name()) == "K2Node_VariableSet"]
drain_subtracts = [n for n in _drained
                   if any(c in drain_writes for c in _consumers(n))]
