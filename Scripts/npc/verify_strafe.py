"""Checks for the step between two swings (npc/strafe.py), read back off the
saved controllers. Run through Scripts/verify_npc_blueprints.py.

What it proves: the Chase step sends a wanderer off and round the player only
while the player is near and the swing's cooldown is young; the pick is made
once per swing and stored; it faces the player while it steps and the way it
runs once it chases again; and it steps at the strafe speed. That it happens
in the game is Scripts/probes/probe_npc_strafe.py.
"""

import unreal

from forest_generator.npc_placement import NPC_MELEE_RANGE_CM, NPC_VARIANTS
from forest_generator.npc_strafe import (
    NPC_STRAFE_ENGAGE_CM, NPC_STRAFE_MAX_ANGLE_DEG, NPC_STRAFE_MAX_DISTANCE_CM,
    NPC_STRAFE_MIN_ANGLE_DEG, NPC_STRAFE_MIN_DISTANCE_CM, NPC_STRAFE_SHARE,
    NPC_STRAFE_SPEED_SCALE,
)
from npc.paths import (
    AI_BP_PATH, PATROL_TARGET_VAR, STEP_CHASE, STEP_EVENT_PREFIX,
    STRAFE_DIST_VAR, STRAFE_FOR_VAR, STRAFE_YAW_VAR,
)
from npc.strafe import DESIRED_FLAG, ORIENT_FLAG
from npc.verify import (
    BEL, PIN, _close, _drivers, _events_into, _exec_reach, _fed, _feeders,
    _lit, _num, _sources, _title, _titled, check,
)

NEXT_ATTACK = "Get NextAttackTime"


def _titles(nodes):
    return {_title(n) for n in nodes}


def _is(node, pin, value):
    """A bool literal; a false one is the pin's default, which a graph loaded
    from disk holds as ""."""
    return _lit(node, pin) in (("true",) if value else ("false", ""))


def _one_throw(setter, var, low, high):
    """Is ``setter``'s value one RandomFloatInRange(low, high), read once?"""
    throws = [n for n in _sources(setter, var) if _title(n) == "RandomFloatInRange"]
    return (len(throws) == 1 and _close(_num(throws[0], "Min"), low)
            and _close(_num(throws[0], "Max"), high)
            and len(PIN.list_connected_pins(
                BEL.find_output_pin(throws[0], "ReturnValue"))) == 1)


def check_settings():
    check("strafe: the step ends outside the melee range and inside the range "
          "it is tried at",
          NPC_MELEE_RANGE_CM < NPC_STRAFE_MIN_DISTANCE_CM
          <= NPC_STRAFE_MAX_DISTANCE_CM < NPC_STRAFE_ENGAGE_CM)
    check("strafe: it is a sidestep (an angle either way, never straight back) "
          "at less than a run, for part of the cooldown",
          0.0 < NPC_STRAFE_MIN_ANGLE_DEG <= NPC_STRAFE_MAX_ANGLE_DEG < 90.0
          and 0.0 < NPC_STRAFE_SPEED_SCALE < 1.0 and 0.0 < NPC_STRAFE_SHARE < 1.0)


def check_strafe(path):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag}: exists, for its step between swings", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    held = [cdo.get_editor_property(v)
            for v in (STRAFE_YAW_VAR, STRAFE_DIST_VAR, STRAFE_FOR_VAR)]
    check(f"{tag}: the pick (angle, distance, the swing it is for) is three "
          f"reals that start at 0",
          all(isinstance(v, float) and v == 0.0 for v in held), f"{held}")

    steps = [n for n in _titled(nodes, "SimpleMoveToLocation")
             if _titles(_feeders(n, "Goal")) != {f"Get {PATROL_TARGET_VAR}"}]
    check(f"{tag}: one step order between swings", len(steps) == 1, f"{len(steps)}")
    if len(steps) != 1:
        return
    step = steps[0]
    goal = _titles(_sources(step, "Goal"))
    check(f"{tag}: ...to a point off the player, round from where it stands by "
          f"the stored angle and out by the stored distance",
          {"GetPlayerPawn", "Rotate Vector Around Axis", "Normalize 2D (Vector)",
           f"Get {STRAFE_YAW_VAR}", f"Get {STRAFE_DIST_VAR}"} <= goal
          and "RandomFloatInRange" not in goal, f"{sorted(goal)}")
    check(f"{tag}: ...reached only from BT_{STEP_CHASE}",
          _events_into(step) == {f"{STEP_EVENT_PREFIX}{STEP_CHASE}"},
          f"{sorted(_events_into(step))}")

    # --- when ----------------------------------------------------------------
    gates = [b for b in _titled(nodes, "Branch")
             if step in _exec_reach(b)
             and NEXT_ATTACK in _titles(_sources(b, "Condition"))
             and f"Get {STRAFE_FOR_VAR}" not in _titles(_sources(b, "Condition"))]
    terms = [t for g in gates for c in _feeders(g, "Condition")
             for pin in ("A", "B") for t in _feeders(c, pin)]
    near = [t for t in terms if _title(t) == "float <= float"
            and _close(_num(t, "B"), NPC_STRAFE_ENGAGE_CM)
            and _titles(_feeders(t, "A")) == {"Distance (Vector)"}]
    early = [t for t in terms if _title(t) == "float < float"
             and _titles(_feeders(t, "B")) == {NEXT_ATTACK}]
    leads = [m for t in early for m in _sources(t, "A")
             if _title(m) == "float * float" and _fed(m, "A", "melee_interval_s")
             and _close(_num(m, "B"), 1.0 - NPC_STRAFE_SHARE)]
    check(f"{tag}: ...only with the player within {NPC_STRAFE_ENGAGE_CM:.0f} cm "
          f"and for the first {NPC_STRAFE_SHARE:.0%} of TuneMeleeInterval after "
          f"a swing",
          len(gates) == 1 and len(near) == 1 and len(early) == 1 and len(leads) == 1
          and any("Time" in t for t in _titles(_sources(early[0], "A"))),
          f"{len(gates)} gates, {len(near)} near, {len(early)} early, {len(leads)} leads")
    chases = [n for n in nodes if "Goal" in {str(PIN.get_pin_name(p))
                                             for p in BEL.list_input_pins(n)}
              and _title(n) != "SimpleMoveToLocation"]
    check(f"{tag}: ...and otherwise the chase runs, as before",
          len(gates) == 1 and len(chases) == 1
          and chases[0] in _exec_reach(PIN.get_owning_node(
              PIN.list_connected_pins(BEL.find_else_pin(gates[0]))[0]))
          and step not in _exec_reach(chases[0]))

    # --- the pick ------------------------------------------------------------
    yaws = _titled(nodes, f"Set {STRAFE_YAW_VAR}")
    dists = _titled(nodes, f"Set {STRAFE_DIST_VAR}")
    fors = _titled(nodes, f"Set {STRAFE_FOR_VAR}")
    check(f"{tag}: the angle is one throw of {NPC_STRAFE_MIN_ANGLE_DEG:.0f}-"
          f"{NPC_STRAFE_MAX_ANGLE_DEG:.0f} deg, stored, left or right on a coin",
          len(yaws) == 1
          and _one_throw(yaws[0], STRAFE_YAW_VAR, NPC_STRAFE_MIN_ANGLE_DEG,
                         NPC_STRAFE_MAX_ANGLE_DEG)
          and {"RandomBool", "SelectFloat"} <= _titles(_sources(yaws[0], STRAFE_YAW_VAR))
          and sorted(_num(s, pin) for s in _sources(yaws[0], STRAFE_YAW_VAR)
                     if _title(s) == "SelectFloat" for pin in ("A", "B")) == [-1.0, 1.0])
    check(f"{tag}: the distance is one throw of {NPC_STRAFE_MIN_DISTANCE_CM:.0f}-"
          f"{NPC_STRAFE_MAX_DISTANCE_CM:.0f} cm, stored",
          len(dists) == 1
          and _one_throw(dists[0], STRAFE_DIST_VAR, NPC_STRAFE_MIN_DISTANCE_CM,
                         NPC_STRAFE_MAX_DISTANCE_CM))
    picks = [d for y in yaws for d in _drivers(y)]
    check(f"{tag}: one pick per swing: only when NextAttackTime is not the one "
          f"the last pick was for, which it then becomes",
          len(fors) == 1 and _titles(_feeders(fors[0], STRAFE_FOR_VAR)) == {NEXT_ATTACK}
          and len(picks) == 1 and _title(picks[0]) == "Branch"
          and _titles(_sources(picks[0], "Condition"))
          == {"Not Equal (Float)", f"Get {STRAFE_FOR_VAR}", NEXT_ATTACK}
          and fors[0] in _exec_reach(yaws[0]) and dists[0] in _exec_reach(yaws[0])
          and step in _exec_reach(fors[0])
          and step in _exec_reach(PIN.get_owning_node(
              PIN.list_connected_pins(BEL.find_else_pin(picks[0]))[0])),
          f"{[_title(p) for p in picks]}")

    # --- which way it faces --------------------------------------------------
    orients = _titled(nodes, f"Set {ORIENT_FLAG}")
    desireds = _titled(nodes, f"Set {DESIRED_FLAG}")
    focuses, clears = _titled(nodes, "SetFocus"), _titled(nodes, "ClearFocus")

    def before(target, value):
        """The flag writes that run into ``target``: orient-to-movement
        ``not value``, turn-with-the-controller ``value``."""
        return (len([n for n in orients if target in _exec_reach(n)
                     and _is(n, ORIENT_FLAG, not value)]) == 1
                and len([n for n in desireds if target in _exec_reach(n)
                         and _is(n, DESIRED_FLAG, value)]) == 1)

    check(f"{tag}: it steps facing the player: focus on them, and the body "
          f"turns with the controller rather than the movement",
          len(focuses) == 1 and _titles(_feeders(focuses[0], "NewFocus"))
          == {"GetPlayerPawn"} and step in _exec_reach(focuses[0])
          and len(orients) == 2 and len(desireds) == 2 and before(step, True))
    check(f"{tag}: ...and chases facing the way it runs, the focus dropped",
          len(clears) == 1 and len(chases) == 1
          and chases[0] in _exec_reach(clears[0]) and before(clears[0], False)
          and step not in _exec_reach(clears[0]))

    # --- how fast ------------------------------------------------------------
    eased = [m for m in _titled(nodes, "float * float")
             if _close(_num(m, "B"), NPC_STRAFE_SPEED_SCALE)]
    writes = [n for n in _exec_reach(step) if _title(n) == "Set MaxWalkSpeed"]
    check(f"{tag}: it steps at {NPC_STRAFE_SPEED_SCALE:.0%} of its run speed",
          len(eased) == 1 and len(writes) == 1
          and eased[0] in _feeders(writes[0], "MaxWalkSpeed"),
          f"{len(eased)} scales, {len(writes)} writes")


def run():
    check_settings()
    check_strafe(AI_BP_PATH)
    for variant in NPC_VARIANTS:
        check_strafe(variant.ai_blueprint)
