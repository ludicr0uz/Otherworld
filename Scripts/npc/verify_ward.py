"""Checks for the step fire holds a wendigo off in (npc/ward.py), read back
off the saved controllers. Run through Scripts/verify_npc_blueprints.py.

What it proves, of each fire-fearing creature's BT_Ward: it is held only
while the player's FireWard is up, it is within the range and it stands in
front of them, and otherwise the step fails; held, it gives no blow and
circles the player on the ring, facing them, the way round a coin when the
hold begins and turned about every couple of seconds; a hold
long enough ends in a flight, straight away from the player on the navmesh,
which also starts a stalker's hunt over; and every held or fleeing pass
succeeds. Its two roars, and the blow that starts a hold over, are
npc/verify_ward_roar.py's. And that a creature which does not fear fire has no such step.
That the step sits ahead of the attack in the tree is npc/verify_tree.py's,
and that a wendigo does all this in the game is
probes/probe_wendigo_ward.py's.
"""

import unreal

from net.players_consts import NEAREST_TITLE
from combat.heat_tuning import FIRE_FEAR_TAG
from combat.paths import FIRE_WARD_VAR
from forest_generator.npc_placement import NPC_MELEE_RANGE_CM, NPC_VARIANTS
from forest_generator.npc_stalk import (
    NPC_STALK_ROAR, NPC_STALK_TURN_MAX_S, NPC_STALK_TURN_MIN_S,
)
from forest_generator.npc_ward import (
    NPC_WARD_ARC_DEG, NPC_WARD_FEARS, NPC_WARD_FLEE_NAV_EXTENT_CM,
    NPC_WARD_FLEE_S, NPC_WARD_FLEE_STEP_CM, NPC_WARD_GRACE_S,
    NPC_WARD_HALF_ANGLE_DEG, NPC_WARD_HOLD_S, NPC_WARD_RANGE_CM,
    NPC_WARD_RING_CM, NPC_WARD_ROAR_S, NPC_WARD_STALLED_CMS,
    NPC_WARD_TURN_MAX_S, NPC_WARD_TURN_MIN_S,
)
from npc.paths import (
    AI_BP_PATH, STALK_CHARGING_VAR, STALK_LEG_UNTIL_VAR, STALK_ROAR_UNTIL_VAR,
    STEP_RESULT_VAR, STEP_WARD, WARD_FLEE_GOAL_VAR, WARD_FLEE_UNTIL_VAR,
    WARD_LAST_VAR, WARD_ROAR_AT_VAR, WARD_SIDE_VAR, WARD_SINCE_VAR,
    WARD_TURN_AT_VAR,
)
from npc.verify import (
    BEL, PIN, _close, _drivers, _exec_reach, _fed, _feeders, _ins, _lit, _num,
    _sources, _title, _titled, check, step_nodes,
)


def _titles(nodes):
    return {_title(n) for n in nodes}


def _after(pin):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]


def _zero(node, pin):
    """A literal 0 or false: the pin's default, which a graph loaded from disk
    holds as ""."""
    return _lit(node, pin) in ("", "false") or _close(_num(node, pin), 0.0)


def _tests(branch, title):
    """The comparisons of ``title`` among what feeds ``branch``'s condition."""
    return [n for n in _sources(branch, "Condition") if _title(n) == title]


def _ends(pin):
    """The StepResult values every exec path from ``pin`` ends on (None for an
    exit that writes none)."""
    found, seen, todo = set(), set(), _after(pin)
    while todo:
        n = todo.pop()
        if n.get_path_name() in seen:
            continue
        seen.add(n.get_path_name())
        nxt = [PIN.get_owning_node(q) for p in BEL.list_output_pins(n)
               if "exec" in str(PIN.get_pin_type_display_string(p)).lower()
               for q in PIN.list_connected_pins(p)]
        if nxt:
            todo += nxt
        elif _title(n) == f"Set {STEP_RESULT_VAR}":
            found.add(_lit(n, STEP_RESULT_VAR) == "true")
        else:
            found.add(None)
    return found


def check_settings():
    keys = {v.key for v in NPC_VARIANTS}
    check("ward: every creature afraid of fire is a creature",
          set(NPC_WARD_FEARS) <= keys, f"{sorted(set(NPC_WARD_FEARS) - keys)}")
    # What a hot blade's blow reads (combat/weapon_component/hot_blow.py): the
    # actor tag, on the creatures afraid of fire and on no other.
    tagged = {v.key: [str(t) for t in unreal.get_default_object(
        unreal.load_class(None, f"{v.blueprint}.{v.blueprint.rsplit('/', 1)[-1]}_C")
    ).get_editor_property("tags")] for v in NPC_VARIANTS}
    check(f"ward: a creature afraid of fire carries the {FIRE_FEAR_TAG} actor "
          "tag, and no other creature does",
          all(tags == ([FIRE_FEAR_TAG] if key in NPC_WARD_FEARS else [])
              for key, tags in tagged.items()), str(tagged))
    check("ward: the ring it circles on is outside its reach and inside the "
          "fire's range, and getting round the fire means a quarter turn or more",
          NPC_MELEE_RANGE_CM < NPC_WARD_RING_CM < NPC_WARD_RANGE_CM
          and NPC_WARD_HALF_ANGLE_DEG >= 90.0,
          f"{NPC_MELEE_RANGE_CM} < {NPC_WARD_RING_CM} < {NPC_WARD_RANGE_CM}, "
          f"{NPC_WARD_HALF_ANGLE_DEG} deg")
    mean = (NPC_WARD_TURN_MIN_S + NPC_WARD_TURN_MAX_S) / 2.0
    hunt = (NPC_STALK_TURN_MIN_S + NPC_STALK_TURN_MAX_S) / 2.0
    check("ward: the way round turns about twice as often as the hunt's arc "
          "does, at times that vary, never under 1 s apart",
          1.0 <= NPC_WARD_TURN_MIN_S < NPC_WARD_TURN_MAX_S
          and 1.5 <= hunt / mean <= 2.5,
          f"{NPC_WARD_TURN_MIN_S:g}-{NPC_WARD_TURN_MAX_S:g} s against "
          f"{NPC_STALK_TURN_MIN_S:g}-{NPC_STALK_TURN_MAX_S:g} s")
    check("ward: held off for 30 s, it runs",
          _close(NPC_WARD_HOLD_S, 30.0) and NPC_WARD_FLEE_S > 0.0)


def check_held(tag, own):
    """The gate: fire up, near, in front. Returns the Branch, or None."""
    gates = [b for b in _titled(own, "Branch")
             if f"Get {FIRE_WARD_VAR}" in _titles(_sources(b, "Condition"))]
    check(f"{tag}: one gate reads the player's {FIRE_WARD_VAR}", len(gates) == 1,
          f"{len(gates)}")
    if len(gates) != 1:
        return None
    gate = gates[0]
    fed = _titles(_sources(gate, "Condition", limit=200))
    near, front = _tests(gate, "float <= float"), _tests(gate, "float > float")
    check(f"{tag}: held off only with the fire up, within "
          f"TuneWardRange (flat)...",
          len(near) == 1 and _fed(near[0], "B", "ward_range_cm")
          and _titles(_feeders(near[0], "A")) == {"Distance2D (Vector)"}
          and "OR Boolean" not in fed, f"{len(near)} tests")
    edges = [c for t in front for c in _feeders(t, "B")]
    check(f"{tag}: ...and within DegCos(TuneWardHalfAngle) of where the "
          f"player faces: further round, it is past the fire",
          len(front) == 1 and _titles(_feeders(front[0], "A")) == {"Dot Product"}
          and len(edges) == 1 and _title(edges[0]) == "Cos (Degrees)"
          and _fed(edges[0], "A", "ward_half_angle_deg")
          and {"GetActorForwardVector", "Normalize 2D (Vector)", NEAREST_TITLE} <= fed,
          f"{_titles(edges)}")
    casts = [d for d in _drivers(gate) if "WeaponComponent" in _title(d)]
    valid = [d for c in casts for d in _drivers(c) if _title(d) == "Branch"]
    check(f"{tag}: the fire is read off the player's weapon component, behind a "
          f"Branch on the player being there",
          len(casts) == 1 and len(valid) == 1
          and _titles(_feeders(valid[0], "Condition")) == {"IsValid"})
    check(f"{tag}: no player, no component or no fire between them: the step "
          f"fails, and the attack runs",
          len(casts) == 1 and len(valid) == 1
          and _ends(BEL.find_else_pin(gate)) == {False}
          and _ends(BEL.find_else_pin(valid[0])) == {False}
          and _ends(BEL.find_output_pin(casts[0], "CastFailed")) == {False})
    check(f"{tag}: every pass that is held off succeeds, so the tree never goes "
          f"on to the swing", _ends(BEL.find_then_pin(gate)) == {True},
          f"{_ends(BEL.find_then_pin(gate))}")
    return gate


def check_hold(tag, own, gate):
    held = _exec_reach(gate)
    begins = [s for s in _titled(own, f"Set {WARD_SINCE_VAR}")
              if _titles(_feeders(s, WARD_SINCE_VAR)) == {"GetTimeSeconds"}]
    fresh = [d for s in begins for d in _drivers(s)]
    lapse = [t for b in fresh for t in _tests(b, "float > float")]
    check(f"{tag}: a hold begins when none is under way, or the last held pass "
          f"was over {NPC_WARD_GRACE_S:g} s ago",
          len(begins) == 1 and begins[0] in held and len(fresh) == 1
          and len(lapse) == 1 and _close(_num(lapse[0], "B"), NPC_WARD_GRACE_S)
          and {"GetTimeSeconds", f"Get {WARD_LAST_VAR}", f"Get {WARD_SINCE_VAR}",
               "Equal (Float)"} <= _titles(_sources(fresh[0], "Condition")))
    sides = _titled(own, f"Set {WARD_SIDE_VAR}")
    coins = [n for s in sides for n in _sources(s, WARD_SIDE_VAR)
             if _title(n) == "RandomBool"]
    thrown = [s for s in sides if "RandomBool" in _titles(_sources(s, WARD_SIDE_VAR))]
    check(f"{tag}: ...with the way round a coin thrown once, read once",
          len(coins) == 1 and len(thrown) == 1 and len(begins) == 1
          and thrown[0] in _exec_reach(begins[0])
          and len(PIN.list_connected_pins(
              BEL.find_output_pin(coins[0], "ReturnValue"))) == 1
          and sorted(_num(s, pin) for s in _feeders(thrown[0], WARD_SIDE_VAR)
                     for pin in ("A", "B")) == [-1.0, 1.0])
    flips = [s for s in sides if s not in thrown]
    stuck = [d for s in flips for d in _drivers(s)]
    check(f"{tag}: ...turned about when the hold is under way and it is "
          f"standing still (under {NPC_WARD_STALLED_CMS:.0f} cm/s)",
          len(flips) == 1 and len(stuck) == 1 and len(fresh) == 1
          and stuck[0] in _after(BEL.find_else_pin(fresh[0]))
          and "GetVelocity" in _titles(_sources(stuck[0], "Condition"))
          and [_num(t, "B") for t in _tests(stuck[0], "float < float")]
          == [NPC_WARD_STALLED_CMS]
          and [_num(m, "B") for m in _feeders(flips[0], WARD_SIDE_VAR)] == [-1.0])
    due = [t for b in stuck for t in _tests(b, "float <= float")]
    check(f"{tag}: ...or when {WARD_TURN_AT_VAR} is up, either one",
          len(stuck) == 1 and len(due) == 1
          and _titles(_feeders(stuck[0], "Condition")) == {"OR Boolean"}
          and _titles(_feeders(due[0], "A")) == {f"Get {WARD_TURN_AT_VAR}"}
          and _titles(_feeders(due[0], "B")) == {"GetTimeSeconds"})
    times = _titled(own, f"Set {WARD_TURN_AT_VAR}")
    sums = [a for t in times for a in _feeders(t, WARD_TURN_AT_VAR)]
    throws = [r for a in sums for r in _feeders(a, "B")]
    check(f"{tag}: ...which is TuneWardTurnMin-Max s "
          f"(one throw each) after the hold began, and after each turn",
          len(times) == 2 and len(thrown) == 1 and len(flips) == 1
          and [t for t in times if t in _after(BEL.find_then_pin(thrown[0]))]
          and [t for t in times if t in _after(BEL.find_then_pin(flips[0]))]
          and len(sums) == 2 and len(throws) == 2 and throws[0] != throws[1]
          and all(_title(a) == "float + float"
                  and _titles(_feeders(a, "A")) == {"GetTimeSeconds"} for a in sums)
          and all(_title(r) == "RandomFloatInRange"
                  and _fed(r, "Min", "ward_turn_min_s")
                  and _fed(r, "Max", "ward_turn_max_s")
                  and len(PIN.list_connected_pins(
                      BEL.find_output_pin(r, "ReturnValue"))) == 1 for r in throws),
          f"{len(times)} writes of {WARD_TURN_AT_VAR}")
    stamps = _titled(own, f"Set {WARD_LAST_VAR}")
    spent = [b for s in stamps for b in _after(BEL.find_then_pin(s))]
    check(f"{tag}: every held pass stamps {WARD_LAST_VAR}",
          len(stamps) == 1 and stamps[0] in held
          and _titles(_feeders(stamps[0], WARD_LAST_VAR)) == {"GetTimeSeconds"}
          and len(_drivers(stamps[0])) == 3)
    limits = [t for b in spent for t in _tests(b, "float >= float")]
    check(f"{tag}: held off TuneWardHold s (now - {WARD_SINCE_VAR}), "
          f"it gives up",
          len(spent) == 1 and _title(spent[0]) == "Branch" and len(limits) == 1
          and _fed(limits[0], "B", "ward_hold_s")
          and {"GetTimeSeconds", f"Get {WARD_SINCE_VAR}"}
          <= _titles(_sources(spent[0], "Condition")),
          f"{len(limits)} limits")
    return spent[0] if len(spent) == 1 else None


def check_circle(tag, own, spent):
    # Past the roar a hold gives part way through (npc/verify_ward_roar.py).
    due = [b for b in _titled(_exec_reach(_after(BEL.find_else_pin(spent))[0]), "Branch")
           if f"Get {WARD_ROAR_AT_VAR}" in _titles(_sources(b, "Condition"))]
    check(f"{tag}: a held pass with no roar to give goes on round", len(due) == 1)
    if len(due) != 1:
        return
    ring = _exec_reach(_after(BEL.find_else_pin(due[0]))[0])
    moves = [n for n in ring if _title(n) == "SimpleMoveToLocation"]
    looks = _titled(ring, "SetFocus")
    check(f"{tag}: still held, it faces the player and moves",
          len(moves) == 1 and len(looks) == 1 and moves[0] in _exec_reach(looks[0])
          and _titles(_feeders(looks[0], "NewFocus")) == {NEAREST_TITLE}
          and not _titled(ring, "ClearFocus"))
    if len(moves) != 1:
        return
    goal = _sources(moves[0], "Goal", limit=200)
    turns = [n for n in goal if _title(n) == "Rotate Vector Around Axis"]
    arcs = [m for t in turns for m in _feeders(t, "AngleDeg")]
    rings = [n for n in goal if _title(n) == "MakeVector"
             and all(_fed(n, axis, "ward_ring_cm") for axis in "XYZ")]
    check(f"{tag}: ...to a point TuneWardRing from the player, "
          f"{NPC_WARD_ARC_DEG:.0f} deg further round them than it stands, the "
          f"hold's way",
          len(turns) == 1 and len(arcs) == 1 and len(rings) == 1
          and _close(_num(arcs[0], "B"), NPC_WARD_ARC_DEG)
          and _titles(_feeders(arcs[0], "A")) == {f"Get {WARD_SIDE_VAR}"}
          and _titles(_feeders(turns[0], "InVect")) == {"Normalize 2D (Vector)"})
    paces = [n for n in ring if _title(n) == "Set MaxWalkSpeed"]
    scale = [n for p in paces for n in _sources(p, "MaxWalkSpeed")
             if _title(n) == "float * float" and _fed(n, "B", "ward_speed_scale")]
    check(f"{tag}: ...at TuneWardSpeed of its run",
          len(paces) == 1 and len(scale) == 1 and paces[0] in _exec_reach(moves[0]))


def check_flight(tag, own, event, spent, key):
    gave_up = _exec_reach(_after(BEL.find_then_pin(spent))[0])
    untils = _titled(own, f"Set {WARD_FLEE_UNTIL_VAR}")
    lasts = [a for u in untils for a in _feeders(u, WARD_FLEE_UNTIL_VAR)]
    runs = [a for s in lasts for a in _feeders(s, "A")]
    check(f"{tag}: giving up, it runs for TuneWardFlee s once it has roared "
          f"({NPC_WARD_ROAR_S:g} s), and the hold is over ({WARD_SINCE_VAR} back to 0)",
          len(untils) == 1 and untils[0] in gave_up and len(lasts) == 1
          and _close(_num(lasts[0], "B"), NPC_WARD_ROAR_S)
          and len(runs) == 1 and _fed(runs[0], "B", "ward_flee_s")
          and _titles(_feeders(runs[0], "A")) == {"GetTimeSeconds"}
          and len([s for s in _titled(gave_up, f"Set {WARD_SINCE_VAR}")
                   if _zero(s, WARD_SINCE_VAR)]) == 1)
    resets = {v: [s for s in _titled(gave_up, f"Set {v}") if _zero(s, v)]
              for v in (STALK_ROAR_UNTIL_VAR, STALK_LEG_UNTIL_VAR, STALK_CHARGING_VAR)}
    if key in NPC_STALK_ROAR:
        check(f"{tag}: ...and its hunt starts over: unroared, no leg, not charging",
              all(len(r) == 1 for r in resets.values()),
              f"{ {v: len(r) for v, r in resets.items()} }")
    else:
        check(f"{tag}: ...and, not a stalker, it has no hunt to start over",
              not any(resets.values()))
    heads = [b for b in _titled(own, "Branch")
             if {"float < float", "GetTimeSeconds", f"Get {WARD_FLEE_UNTIL_VAR}"}
             == _titles(_sources(b, "Condition"))]
    check(f"{tag}: while it runs, the step asks nothing else: the flight is "
          f"its first Branch, fire or no fire",
          len(heads) == 1 and heads[0] in _exec_reach(event)
          and all(n in _exec_reach(heads[0]) for n in own
                  if _title(n).startswith("Set Ward"))
          and _ends(BEL.find_then_pin(heads[0])) == {True})
    if len(heads) != 1:
        return
    run = _exec_reach(_after(BEL.find_then_pin(heads[0]))[0])
    moves = [n for n in run if _title(n) == "SimpleMoveToLocation"]
    check(f"{tag}: the flight faces the way it goes and gives one move order, "
          f"which the pass that gives up does not reach (it roars)",
          len(moves) == 1 and len(_titled(run, "ClearFocus")) == 1
          and not _titled(run, "SetFocus") and moves[0] not in gave_up
          and _titles(_feeders(moves[0], "Goal")) == {f"Get {WARD_FLEE_GOAL_VAR}"})
    goals = _titled(run, f"Set {WARD_FLEE_GOAL_VAR}")
    aimed = [s for s in goals if "Normalize 2D (Vector)"
             in _titles(_sources(s, WARD_FLEE_GOAL_VAR, limit=200))]
    strides = [n for s in aimed for n in _sources(s, WARD_FLEE_GOAL_VAR, limit=200)
               if _title(n) == "MakeVector"
               and all(_close(_num(n, axis), NPC_WARD_FLEE_STEP_CM) for axis in "XYZ")]
    check(f"{tag}: ...{NPC_WARD_FLEE_STEP_CM:.0f} cm straight away from the player",
          len(goals) == 2 and len(aimed) == 1 and len(strides) == 1
          and "RandomBool" not in _titles(_sources(aimed[0], WARD_FLEE_GOAL_VAR,
                                                   limit=200)))
    snaps = [s for s in goals if _titles(_feeders(s, WARD_FLEE_GOAL_VAR))
             == {"Project Point to Navigation"}]
    walkable = [d for s in snaps for d in _drivers(s)]
    boxes = [m for s in snaps for nav in _feeders(s, WARD_FLEE_GOAL_VAR)
             for m in _feeders(nav, "QueryExtent")]
    check(f"{tag}: ...snapped onto the navmesh, read behind a Branch on the "
          f"projection's bool; off it, no order is given",
          len(snaps) == 1 and len(walkable) == 1 and len(moves) == 1
          and _titles(_feeders(walkable[0], "Condition"))
          == {"Project Point to Navigation"}
          and snaps[0] in _after(BEL.find_then_pin(walkable[0]))
          and moves[0] not in _exec_reach(_after(BEL.find_else_pin(walkable[0]))[0])
          and len(boxes) == 1
          and [_num(boxes[0], a) for a in "XYZ"] == list(NPC_WARD_FLEE_NAV_EXTENT_CM))
    paces = [n for n in run if _title(n) == "Set MaxWalkSpeed"]
    check(f"{tag}: ...at its full run",
          len(paces) == 1 and not any(
              _fed(n, "B", "ward_speed_scale")
              for n in _sources(paces[0], "MaxWalkSpeed") if _title(n) == "float * float"))


def check_ward(path, key):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag}: exists, for the fire that holds it off", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    own = step_nodes(ed.list_all_nodes(), STEP_WARD)
    if key not in NPC_WARD_FEARS:
        check(f"{tag}: does not fear fire: no BT_{STEP_WARD} step", not own)
        return
    events = [n for n in own if n.get_class().get_name() == "K2Node_CustomEvent"]
    check(f"{tag}: fears fire: it has a BT_{STEP_WARD} step", len(events) == 1)
    if len(events) != 1:
        return
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    held = {v: cdo.get_editor_property(v) for v in (
        WARD_SINCE_VAR, WARD_LAST_VAR, WARD_SIDE_VAR, WARD_TURN_AT_VAR,
        WARD_FLEE_UNTIL_VAR)}
    check(f"{tag}: it starts with no hold, no side, no turn and no flight: five reals at 0",
          all(isinstance(v, float) and v == 0.0 for v in held.values()), f"{held}")
    check(f"{tag}: the step gives no blow and no order but its own two: no "
          f"MoveTo, no damage, two SimpleMoveToLocation",
          not any({"Dest"} <= _ins(n)
                  or _title(n) in ("Move To Actor", "MoveToActor", "Set Health")
                  for n in own)
          and len(_titled(own, "SimpleMoveToLocation")) == 2)
    gate = check_held(tag, own)
    if gate is None:
        return
    spent = check_hold(tag, own, gate)
    if spent is None:
        return
    check_circle(tag, own, spent)
    check_flight(tag, own, events[0], spent, key)


def run():
    check_settings()
    check_ward(AI_BP_PATH, NPC_VARIANTS[0].key)
    for variant in NPC_VARIANTS:
        check_ward(variant.ai_blueprint, variant.key)
