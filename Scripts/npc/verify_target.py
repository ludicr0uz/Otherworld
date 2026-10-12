"""Who a wanderer hunts (npc/target.py, task M27), per controller: the
candidate BT_PlayerPresent takes in turn among the living players near it,
the Target BT_Target keeps while they live and replaces when they do not,
whoever struck it as the hurt sense's answer, and that no other step asks
for a player at all.

That a wanderer on a server goes for the nearer of two clients and turns on
the other when the first dies is probes/probe_net_npc_target.py's.
"""

import unreal

from forest_generator.npc_agro import NPC_TARGET_SCAN_CM
from forest_generator.npc_placement import NPC_VARIANTS
from forest_generator.npc_stalk import NPC_STALK_ROAR
from net.players_consts import LIVING_TITLE, NEAREST_TITLE
from npc.paths import (
    AI_BP_PATH, SENSE_STEPS, STALK_CHARGING_VAR, STALK_LEG_UNTIL_VAR,
    STALK_ROAR_UNTIL_VAR, STEP_PRESENT, STEP_RESULT_VAR, STEP_TARGET, TARGET_NEAR_VAR,
    TARGET_SCAN_VAR, TARGET_TITLE, TARGET_VAR, WARD_SINCE_VAR,
)
from npc.verify import (
    BEL, PIN, _close, _exec_reach, _feeders, _num, _sources, _title, _titled, check,
    outside_step, step_nodes,
)
from npc.verify_stalk import _result
from npc.verify_stalk_cover import _after, _titles
from npc.verify_ward import _zero
from npc.ward import wards

# What a graph that still meant "the player" would call.
PLAYER_ZERO = ("Get Player Pawn", "Get Player Character", "Get Player Controller")


def _then(node):
    return [n for a in _after(BEL.find_then_pin(node)) for n in _exec_reach(a)]


def _else(node):
    return [n for a in _after(BEL.find_else_pin(node)) for n in _exec_reach(a)]


def _someone(nodes):
    """The Branches on IsValid(Target)."""
    return [b for b in _titled(nodes, "Branch")
            if any(_title(v) == "IsValid" and _titles(_feeders(v, "Object")) == {TARGET_TITLE}
                   for v in _feeders(b, "Condition"))]


def check_candidate(tag, own):
    sets = _titled(own, f"Set {TARGET_VAR}")
    turns = [s for s in sets if "Get" in _titles(_feeders(s, TARGET_VAR))]
    far = [s for s in sets if _titles(_feeders(s, TARGET_VAR)) == {NEAREST_TITLE}]
    adds = _titled(own, "Add")
    near = [d for a in adds for d in BEL.find_execute_pin(a).list_connected_pins()]
    near = [PIN.get_owning_node(p) for p in near]
    check(f"{tag}: on patrol it scans the living players within "
          f"{NPC_TARGET_SCAN_CM / 100:.0f} m into {TARGET_NEAR_VAR}, afresh each pass",
          len(_titled(own, LIVING_TITLE)) == 1 and len(_titled(own, "For Each Loop")) == 1
          and len(_titled(own, "Clear")) == 1 and len(adds) == 1 and len(near) == 1
          and _titles(_feeders(adds[0], "TargetArray")) == {f"Get {TARGET_NEAR_VAR}"}
          and any(_title(c) == "float <= float" and _close(_num(c, "B"), NPC_TARGET_SCAN_CM)
                  and "Distance (Vector)" in _titles(_feeders(c, "A"))
                  for c in _feeders(near[0], "Condition")))
    check(f"{tag}: ...and takes them in turn, one a pass: {TARGET_VAR} = "
          f"{TARGET_NEAR_VAR}[{TARGET_SCAN_VAR} % their count], then the turn moves on",
          len(turns) == 1
          and {f"Get {TARGET_NEAR_VAR}", "% (Integer)", f"Get {TARGET_SCAN_VAR}", "Length"}
          <= _titles(_sources(turns[0], TARGET_VAR))
          and len([n for n in _exec_reach(turns[0])
                   if _title(n) == f"Set {TARGET_SCAN_VAR}"
                   and "int + int" in _titles(_feeders(n, TARGET_SCAN_VAR))]) == 1)
    check(f"{tag}: ...with no one that near, the nearest living player (a shot "
          f"heard or felt from far off is laid on someone)",
          len(far) == 1 and len(sets) == 2 and far[0] not in _exec_reach(turns[0]))
    gate = _someone(own)
    check(f"{tag}: the senses are asked only when {TARGET_VAR} is someone: no "
          f"living player and the step fails to the patrol",
          len(gate) == 1 and all(gate[0] in _exec_reach(s) for s in sets)
          and _result(_after(BEL.find_then_pin(gate[0])), True)
          and _result(_after(BEL.find_else_pin(gate[0])), False))


def check_keep(tag, own, key):
    kept = [b for b in _titled(own, "Branch")
            if any(_title(c) == "Contains Item"
                   and _titles(_feeders(c, "TargetArray")) == {LIVING_TITLE}
                   and _titles(_feeders(c, "ItemToFind")) == {TARGET_TITLE}
                   for c in _feeders(b, "Condition"))]
    check(f"{tag}: on the hunt it keeps {TARGET_VAR} while they are among the "
          f"living players: the step succeeds and writes nothing",
          len(kept) == 1 and _result(_after(BEL.find_then_pin(kept[0])), True))
    if len(kept) != 1:
        return
    switch = _else(kept[0])
    sets = _titled(switch, f"Set {TARGET_VAR}")
    gate = _someone(switch)
    check(f"{tag}: ...dead or gone, it turns on the nearest living player",
          len(sets) == 1 == len(_titled(own, f"Set {TARGET_VAR}"))
          and _titles(_feeders(sets[0], TARGET_VAR)) == {NEAREST_TITLE}
          and len(gate) == 1 and gate[0] in _exec_reach(sets[0]))
    if len(gate) != 1:
        return
    check(f"{tag}: ...and with no one living the step fails: the pass falls "
          f"through to the patrol, still Aggro",
          _result(_after(BEL.find_else_pin(gate[0])), False))
    found = _then(gate[0])
    want = ([STALK_ROAR_UNTIL_VAR, STALK_LEG_UNTIL_VAR, STALK_CHARGING_VAR]
            * (key in NPC_STALK_ROAR) + [WARD_SINCE_VAR] * wards(key))
    wrote = [n for n in found if _title(n).startswith("Set ")
             and _title(n) != f"Set {STEP_RESULT_VAR}"]
    check(f"{tag}: ...a switch starts the hunt over"
          + (f": {', '.join(want)} back to zero (a stalker roars at the new one)"
             if want else ": nothing of the last one is left to clear"),
          sorted(_title(n) for n in wrote) == sorted(f"Set {v}" for v in want)
          and all(_zero(n, _title(n)[4:]) for n in wrote)
          and _result(_titled(found, f"Set {STEP_RESULT_VAR}"), True),
          f"{sorted(_title(n) for n in wrote)}")


def check_blame(tag, hurt):
    blames = _titled(hurt, f"Set {TARGET_VAR}")
    flips = _titled(hurt, "Set Aggro")
    check(f"{tag}: hurt, it turns on whoever struck the blow: {TARGET_VAR} is "
          f"the pawn of the health component's LastInstigator, before Aggro is set",
          len(blames) == 1 and len(flips) == 1 and flips[0] in _exec_reach(blames[0])
          and {"Get LastInstigator", "Get Controlled Pawn"}
          <= _titles(_sources(blames[0], TARGET_VAR)))
    guards = [d for b in blames for d in BEL.find_execute_pin(b).list_connected_pins()]
    guards = [PIN.get_owning_node(p) for p in guards]
    check(f"{tag}: ...only when that pawn is there (a Branch of its own): "
          f"otherwise the candidate stands, and Aggro is set all the same",
          len(guards) == 1 and _title(guards[0]) == "Branch"
          and "IsValid" in _titles(_feeders(guards[0], "Condition"))
          and len(flips) == 1 and flips[0] in _else(guards[0]))


def check_heard(tag, sound):
    takes = _titled(sound, f"Set {TARGET_VAR}")
    flips = _titled(sound, "Set Aggro")
    check(f"{tag}: a noise heard, it turns on whoever made it (M28): {TARGET_VAR} is "
          f"the noise's Maker, before Aggro is set",
          len(takes) == 1 and len(flips) == 1 and flips[0] in _exec_reach(takes[0])
          and _titles(_feeders(takes[0], TARGET_VAR)) == {"HearNoise"})
    guards = [PIN.get_owning_node(d) for b in takes
              for d in BEL.find_execute_pin(b).list_connected_pins()]
    check(f"{tag}: ...only when that pawn is there: otherwise the candidate "
          f"stands, and Aggro is set all the same",
          len(guards) == 1 and _title(guards[0]) == "Branch"
          and "IsValid" in _titles(_feeders(guards[0], "Condition"))
          and len(flips) == 1 and flips[0] in _else(guards[0]))


def check_target(path, key):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.load_asset(path)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    present, hunt = step_nodes(nodes, STEP_PRESENT), step_nodes(nodes, STEP_TARGET)
    check_candidate(tag, present)
    check_keep(tag, hunt, key)
    check_blame(tag, step_nodes(nodes, dict(SENSE_STEPS)["hurt"]))
    check_heard(tag, step_nodes(nodes, dict(SENSE_STEPS)["sound"]))
    rest = outside_step(outside_step(nodes, STEP_PRESENT), STEP_TARGET)
    asks = sorted({_title(n) for n in rest if _title(n) in (LIVING_TITLE, NEAREST_TITLE)}
                  | {_title(n) for n in nodes if _title(n) in PLAYER_ZERO})
    check(f"{tag}: no other step asks for a player: each reads {TARGET_VAR}, and "
          f"none reads player 0", not asks and len(_titled(rest, TARGET_TITLE)) >= 4,
          f"{asks}")


def run():
    made = [(AI_BP_PATH, NPC_VARIANTS[0].key)]
    made += [(variant.ai_blueprint, variant.key) for variant in NPC_VARIANTS]
    for path, key in made:
        check_target(path, key)
