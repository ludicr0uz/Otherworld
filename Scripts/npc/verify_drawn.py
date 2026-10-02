"""Checks for the fire that draws a zombie (npc/drawn.py, numbers in
forest_generator/npc_drawn.py), read back off the saved controllers and
trees. Run through Scripts/verify_npc_blueprints.py.

What it proves: only a creature of NPC_DRAWN_BY_FIRE has the step; the step
looks for campfires, keeps the nearest in DrawnTo (one read of the pure
query), and is Drawn only by a live fire within range; Drawn, it is ordered
to the fire at its patrol walk, or stood beside it, and the step succeeds;
otherwise the step fails with Drawn false. In the tree the step shares a
selector with the Stroll, ahead of it and behind the senses. That a zombie
walks to a fire in the game is probes/probe_zombie_drawn.py.
"""

import unreal

from forest_generator.npc_drawn import (
    NPC_DRAWN_ARRIVE_CM, NPC_DRAWN_BY_FIRE, NPC_DRAWN_RANGE_CM,
)
from forest_generator.npc_placement import NPC_MELEE_RANGE_CM, NPC_VARIANTS
from npc.paths import (
    AI_BP_PATH, DRAWN_TO_VAR, DRAWN_VAR, SENSE_STEPS, STEP_DRAWN, STEP_STROLL,
    STEP_VAR, step_task_path, tree_path,
)
from npc.verify import (
    BEL, _close, _drivers, _fed, _feeders, _ins, _lit, _num, _sources, _title,
    _titled, check, step_nodes,
)
from npc.verify_tree import _gates_on_aggro, _load, _walk
from npc.verify_ward import _after, _ends, _titles, _zero
from survival.paths import CAMPFIRE_CLASS_PATH


def check_settings():
    keys = {v.key for v in NPC_VARIANTS}
    check("drawn: every creature a fire draws is a creature",
          set(NPC_DRAWN_BY_FIRE) <= keys, f"{sorted(set(NPC_DRAWN_BY_FIRE) - keys)}")
    check("drawn: a fire draws from 200 m, and a zombie stops beside it, "
          "further off than it can swing",
          _close(NPC_DRAWN_RANGE_CM, 20000.0)
          and NPC_MELEE_RANGE_CM < NPC_DRAWN_ARRIVE_CM < NPC_DRAWN_RANGE_CM,
          f"{NPC_DRAWN_RANGE_CM} cm, {NPC_DRAWN_ARRIVE_CM} cm")


def check_target(tag, own):
    """The fire: the nearest campfire, kept. Returns the Branch on it, or None."""
    looks = _titled(own, "GetAllActorsOfClass")
    check(f"{tag}: it looks for campfires",
          len(looks) == 1 and _lit(looks[0], "ActorClass") == CAMPFIRE_CLASS_PATH,
          f"{[_lit(n, 'ActorClass') for n in looks]}")
    keeps = _titled(own, f"Set {DRAWN_TO_VAR}")
    nearest = [f for k in keeps for f in _feeders(k, DRAWN_TO_VAR)]
    check(f"{tag}: ...and keeps the nearest to its pawn in {DRAWN_TO_VAR}: one "
          f"read of the pure query, straight after the search",
          len(keeps) == 1 and len(looks) == 1
          and _titles(nearest) == {"FindNearestActor"}
          and _feeders(nearest[0], "ActorsToCheck") == looks
          and {"Get Actor Location", "Get Controlled Pawn"}
          <= _titles(_sources(nearest[0], "Origin"))
          and _drivers(keeps[0]) == looks
          and len(_titled(own, "FindNearestActor")) == 1,
          f"{sorted(_titles(nearest))}")
    if len(keeps) != 1:
        return None
    live = _after(BEL.find_then_pin(keeps[0]))
    ok = (len(live) == 1 and _title(live[0]) == "Branch"
          and _titles(_feeders(live[0], "Condition")) == {"IsValid"}
          and _titles(_sources(live[0], "Condition"))
          == {"IsValid", f"Get {DRAWN_TO_VAR}"})
    check(f"{tag}: no fire burning: nothing else is read of it (the next "
          f"Branch tests only that {DRAWN_TO_VAR} is valid)", ok)
    return live[0] if ok else None


def check_drawn_state(tag, own, live):
    """The range, and the state either way. Returns the write of Drawn =
    true, or None."""
    reach = _after(BEL.find_then_pin(live))
    tests = ([n for n in _sources(reach[0], "Condition")
              if _title(n) == "float <= float"] if len(reach) == 1 else [])
    measured = _titles(_sources(tests[0], "A", limit=200)) if tests else set()
    check(f"{tag}: a fire draws it from {NPC_DRAWN_RANGE_CM / 100:.0f} m, "
          f"flat, measured from its pawn to {DRAWN_TO_VAR}",
          len(reach) == 1 and _title(reach[0]) == "Branch" and len(tests) == 1
          and _close(_num(tests[0], "B"), NPC_DRAWN_RANGE_CM)
          and _titles(_feeders(tests[0], "A")) == {"Distance2D (Vector)"}
          and {"Get Controlled Pawn", f"Get {DRAWN_TO_VAR}"} <= measured,
          f"{[_num(t, 'B') for t in tests]}, {sorted(measured)}")
    if len(reach) != 1:
        return None
    writes = _titled(own, f"Set {DRAWN_VAR}")
    off = [w for w in writes if _zero(w, DRAWN_VAR)]
    on = [w for w in writes if _lit(w, DRAWN_VAR) == "true"]
    refused = _after(BEL.find_else_pin(live)) + _after(BEL.find_else_pin(reach[0]))
    check(f"{tag}: no fire, or none that near: {DRAWN_VAR} = false and the "
          f"step fails, so the tree goes on to the stroll",
          len(off) == 1 and refused == off + off
          and _ends(BEL.find_then_pin(off[0])) == {False}
          and not any(_title(n) in ("SimpleMoveToLocation", "StopMovement")
                      for n in _after(BEL.find_then_pin(off[0]))),
          f"{len(off)} writes, {sorted(_titles(refused))}")
    check(f"{tag}: a fire in range: {DRAWN_VAR} = true, and every way on "
          f"succeeds, so the stroll is not reached",
          len(on) == 1 and _after(BEL.find_then_pin(reach[0])) == on
          and _ends(BEL.find_then_pin(on[0])) == {True},
          f"{len(on)} writes")
    return on[0] if len(on) == 1 else None


def check_walk(tag, own, on):
    """Drawn: to the fire at the patrol walk, or standing beside it."""
    gate = _after(BEL.find_then_pin(on))
    tests = ([n for n in _sources(gate[0], "Condition")
              if _title(n) == "float > float"] if len(gate) == 1 else [])
    check(f"{tag}: Drawn, it walks while it is more than "
          f"{NPC_DRAWN_ARRIVE_CM:.0f} cm from the fire",
          len(gate) == 1 and _title(gate[0]) == "Branch" and len(tests) == 1
          and _close(_num(tests[0], "B"), NPC_DRAWN_ARRIVE_CM)
          and _titles(_feeders(tests[0], "A")) == {"Distance2D (Vector)"},
          f"{[_num(t, 'B') for t in tests]}")
    if len(gate) != 1:
        return
    orders = _after(BEL.find_then_pin(gate[0]))
    goal = (_titles(_sources(orders[0], "Goal"))
            if len(orders) == 1 and "Goal" in _ins(orders[0]) else set())
    check(f"{tag}: ...ordered to where {DRAWN_TO_VAR} is, the step's one order "
          f"(no MoveTo, no blow)",
          len(orders) == 1 and _title(orders[0]) == "SimpleMoveToLocation"
          and goal == {"Get Actor Location", f"Get {DRAWN_TO_VAR}"}
          and len(_titled(own, "SimpleMoveToLocation")) == 1
          and not any({"Dest"} <= _ins(n)
                      or _title(n) in ("Move To Actor", "MoveToActor", "Set Health")
                      for n in own),
          f"{sorted(goal)}")
    paces = _titled(own, "Set MaxWalkSpeed")
    slowed = [n for p in paces for n in _sources(p, "MaxWalkSpeed")
              if _title(n) == "float * float" and _fed(n, "B", "patrol_speed_scale")]
    check(f"{tag}: ...slowly: after the order, its speed is written as the "
          f"patrol walk (TunePatrolSpeed of its run)",
          len(paces) == 1 and len(slowed) == 1 and len(orders) == 1
          and orders[0].get_path_name() in
          {d.get_path_name() for c in _drivers(paces[0]) for d in _drivers(c)},
          f"{len(paces)} writes, {len(slowed)} scaled")
    stands = _after(BEL.find_else_pin(gate[0]))
    check(f"{tag}: beside the fire it stops and stands",
          len(stands) == 1 and _title(stands[0]) == "StopMovement")


def check_drawn_tree(ai_path, tag, drawn):
    bt, task = _load(tree_path(ai_path)), _load(step_task_path(ai_path))
    if not bt or not task:
        check(f"{tag}: its tree and step task exist, for the Drawn step", False)
        return
    task_class = BEL.generated_class(task)
    steps = [(str(n.get_editor_property(STEP_VAR)), up)
             for n, _, up in _walk(bt.get_editor_property("root_node"))
             if n.get_class() == task_class]
    order = [name for name, _ in steps]
    if not drawn:
        check(f"{tag}: its tree has no Drawn step", STEP_DRAWN not in order)
        return
    over = [up for name, up in steps if name in (STEP_DRAWN, STEP_STROLL)]
    check(f"{tag}: Drawn and Stroll share one selector, Drawn first: the "
          f"stroll runs on the pass Drawn fails",
          len(over) == 2 and over[0][-1][0] == over[1][-1][0]
          and isinstance(over[0][-1][0], unreal.BTComposite_Selector)
          and STEP_DRAWN in order
          and order.index(STEP_STROLL) == order.index(STEP_DRAWN) + 1,
          f"{order}")
    check(f"{tag}: ...behind every sense, and not under the Blackboard's Aggro: "
          f"a zombie that notices the player on its way hunts them",
          STEP_DRAWN in order
          and all(order.index(name) < order.index(STEP_DRAWN)
                  for _, name in SENSE_STEPS if name in order)
          and not any(_gates_on_aggro(d) for up in over for _, d in up),
          f"{order}")


def check_drawn(path, key):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag}: exists, for the fire that draws it", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    own = step_nodes(ed.list_all_nodes(), STEP_DRAWN)
    drawn = key in NPC_DRAWN_BY_FIRE
    check_drawn_tree(path, tag, drawn)
    if not drawn:
        check(f"{tag}: a fire does not draw it: no BT_{STEP_DRAWN} step", not own)
        return
    events = [n for n in own if n.get_class().get_name() == "K2Node_CustomEvent"]
    check(f"{tag}: a fire draws it: it has a BT_{STEP_DRAWN} step", len(events) == 1)
    if len(events) != 1:
        return
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check(f"{tag}: it starts not {DRAWN_VAR}, to nothing",
          cdo.get_editor_property(DRAWN_VAR) is False
          and cdo.get_editor_property(DRAWN_TO_VAR) is None)
    live = check_target(tag, own)
    if live is None:
        return
    on = check_drawn_state(tag, own, live)
    if on is not None:
        check_walk(tag, own, on)


def run():
    check_settings()
    check_drawn(AI_BP_PATH, NPC_VARIANTS[0].key)
    for variant in NPC_VARIANTS:
        check_drawn(variant.ai_blueprint, variant.key)
