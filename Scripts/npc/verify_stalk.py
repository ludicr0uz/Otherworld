"""Checks for the wendigo's hunt (npc/stalk.py, stalk_cover.py), read back off
the saved controllers. Run through Scripts/verify_npc_blueprints.py.

What it proves, of each stalker's BT_Stalk: it roars once, standing and
facing the player, with its roar clip and a voice; the way it goes round the
player is a coin at the roar, turned about at a leg's pick once a thrown
time is up; it runs its legs faster than it chases; one the player has hurt
is enraged and never hunts; a leg's spot is behind a tree a sweep struck
(an instanced mesh, by its own transform), on the navmesh, or in the open
when no sweep found one; it waits behind a trunk and not in the open; and
within the charge range the step fails for good. And that a creature which
does not stalk has no such step. That its place in the tree is ahead of
Chase is npc/verify_tree.py's, and that a wendigo does all this in the game
is probes/probe_wendigo_stalk.py's.
"""

import unreal

from forest_generator.npc_placement import NPC_MELEE_RANGE_CM, NPC_VARIANTS
from forest_generator.npc_stalk import (
    NPC_STALK_ARC_DEG, NPC_STALK_ARRIVE_CM, NPC_STALK_BEHIND_CM,
    NPC_STALK_CHARGE_CM, NPC_STALK_COVER_MIN_CM, NPC_STALK_GAIN_MIN_CM,
    NPC_STALK_HIDE_MAX_S,
    NPC_STALK_HIDE_MIN_S, NPC_STALK_LEG_TIMEOUT_S, NPC_STALK_ROAR,
    NPC_STALK_ROAR_S, NPC_STALK_RUN_SCALE, NPC_STALK_STALLED_CMS,
    NPC_STALK_SWEEP_RADIUS_CM, NPC_STALK_TURN_MAX_S, NPC_STALK_TURN_MIN_S,
)
from combat.game_state import DAMAGED_BY_PLAYER_VAR
from npc.paths import (
    AI_BP_PATH, ENRAGED_VAR, MELEE_SLOT, STALK_ARRIVED_VAR, STALK_CHARGING_VAR,
    STALK_COVER_VAR, STALK_HIDDEN_VAR, STALK_IGNORE_VAR, STALK_LEG_UNTIL_VAR,
    STALK_LEGS_VAR, STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR, STALK_TURN_AT_VAR,
    STEP_RESULT_VAR, STEP_STALK, VOICES_VAR,
)
from npc.verify import (
    BEL, PIN, _close, _drivers, _exec_reach, _feeders, _ins, _lit, _num,
    _sources, _title, _titled, check, step_nodes,
)


def _titles(nodes):
    return {_title(n) for n in nodes}


def _is(node, pin, value):
    """A bool literal; a false one is the pin's default, which a graph loaded
    from disk holds as ""."""
    return _lit(node, pin) in (("true",) if value else ("false", ""))


def _after(pin):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]


def _result(nodes, value):
    """Is this one StepResult write of ``value``?"""
    return (len(nodes) == 1 and _title(nodes[0]) == f"Set {STEP_RESULT_VAR}"
            and _is(nodes[0], STEP_RESULT_VAR, value))


def _with(nodes, *pins):
    return [n for n in nodes if set(pins) <= _ins(n)]


def _limit(branch, measure, bound):
    """Is ``branch``'s condition one "<measure> <= bound"?"""
    tests = _feeders(branch, "Condition")
    # A 0 is the pin's default, which a graph loaded from disk holds as "".
    return (len(tests) == 1 and _title(tests[0]) == "float <= float"
            and (_close(_num(tests[0], "B"), bound)
                 or (bound == 0.0 and _lit(tests[0], "B") == ""))
            and _titles(_feeders(tests[0], "A")) == {measure})


def check_settings():
    keys = {v.key for v in NPC_VARIANTS}
    check("stalk: every stalker is a creature", set(NPC_STALK_ROAR) <= keys,
          f"{sorted(set(NPC_STALK_ROAR) - keys)}")
    check("stalk: the charge starts outside the melee range, and the last "
          "cover outside the charge range",
          NPC_MELEE_RANGE_CM < NPC_STALK_CHARGE_CM < NPC_STALK_COVER_MIN_CM)
    check("stalk: every leg goes round the player, never straight at them or "
          "away", all(0.0 < a < 90.0 for a in NPC_STALK_ARC_DEG) and NPC_STALK_ARC_DEG)
    check("stalk: a wait behind a trunk ends before a leg is given up",
          0.0 < NPC_STALK_HIDE_MIN_S < NPC_STALK_HIDE_MAX_S < NPC_STALK_LEG_TIMEOUT_S)
    check("stalk: a leg is run faster than the chase, and the way round is "
          "turned about after a time that varies",
          NPC_STALK_RUN_SCALE > 1.0
          and 0.0 < NPC_STALK_TURN_MIN_S < NPC_STALK_TURN_MAX_S)


def check_roar(tag, own, key):
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    clip = NPC_STALK_ROAR[key]
    check(f"{tag}: its roar clip exists ({clip.rsplit('/', 1)[-1]})",
          eas.does_asset_exist(clip))
    roars = _with(own, "Asset", "SlotNodeName")
    check(f"{tag}: the hunt plays that clip, once, into {MELEE_SLOT}",
          len(roars) == 1 and _lit(roars[0], "Asset").split(".")[0] == clip
          and _lit(roars[0], "SlotNodeName") == MELEE_SLOT,
          f"{[_lit(r, 'Asset') for r in roars]}")
    voices = [v for v in _with(own, "Sound", "Location")
              if roars and v in _exec_reach(roars[0])]
    check(f"{tag}: ...with one of its voices",
          len(voices) == 1 and len(roars) == 1
          and f"Get {VOICES_VAR}" in _titles(_sources(voices[0], "Sound")))
    stamps = _titled(own, f"Set {STALK_ROAR_UNTIL_VAR}")
    lasts = [a for s in stamps for a in _feeders(s, STALK_ROAR_UNTIL_VAR)]
    firsts = [d for s in stamps for d in _drivers(s)]
    check(f"{tag}: it roars on the first pass only (StalkRoarUntil still 0), "
          f"for {NPC_STALK_ROAR_S:g} s",
          len(stamps) == 1 and len(roars) == 1 and roars[0] in _exec_reach(stamps[0])
          and len(lasts) == 1 and _close(_num(lasts[0], "B"), NPC_STALK_ROAR_S)
          and _titles(_feeders(lasts[0], "A")) == {"GetTimeSeconds"}
          and len(firsts) == 1 and _limit(firsts[0], f"Get {STALK_ROAR_UNTIL_VAR}", 0.0))
    stops = _titled(own, "StopMovement")
    looks = [f for f in _titled(own, "SetFocus")
             if roars and roars[0] in _exec_reach(f)]
    check(f"{tag}: ...standing, and facing the player",
          len(stops) == 1 and len(stamps) == 1 and stops[0] in _exec_reach(stamps[0])
          and len(looks) == 1 and looks[0] in _exec_reach(stops[0])
          and _titles(_feeders(looks[0], "NewFocus")) == {"GetPlayerPawn"})
    waits = [b for b in _titled(own, "Branch")
             if {"float < float", "GetTimeSeconds", f"Get {STALK_ROAR_UNTIL_VAR}"}
             == _titles(_sources(b, "Condition"))]
    check(f"{tag}: ...and does nothing else until the roar is over",
          len(waits) == 1 and _result(_after(BEL.find_then_pin(waits[0])), True))
    coins = [n for n in own if _title(n) == "RandomBool"]
    sides = [s for s in _titled(own, f"Set {STALK_SIDE_VAR}")
             if "RandomBool" in _titles(_sources(s, STALK_SIDE_VAR))]
    check(f"{tag}: the way round is a coin thrown once, at the roar",
          len(sides) == 1 and len(stamps) == 1 and sides[0] in _exec_reach(stamps[0])
          and len(coins) == 1
          and len(PIN.list_connected_pins(BEL.find_output_pin(coins[0], "ReturnValue"))) == 1
          and sorted(_num(s, pin) for s in _feeders(sides[0], STALK_SIDE_VAR)
                     for pin in ("A", "B")) == [-1.0, 1.0])


def _turn_time(stamp):
    """What a StalkTurnAt write adds its one throw of the turn time to: the
    titles feeding the sum's A, or None when it is not such a write."""
    sums = _feeders(stamp, STALK_TURN_AT_VAR)
    throws = [t for a in sums for t in _feeders(a, "B")]
    if not (len(sums) == 1 and _title(sums[0]) == "float + float"
            and len(throws) == 1 and _title(throws[0]) == "RandomFloatInRange"
            and _close(_num(throws[0], "Min"), NPC_STALK_TURN_MIN_S)
            and _close(_num(throws[0], "Max"), NPC_STALK_TURN_MAX_S)
            and len(PIN.list_connected_pins(
                BEL.find_output_pin(throws[0], "ReturnValue"))) == 1):
        return None
    return _feeders(sums[0], "A")


def check_turns(tag, own):
    """The way round alternates: turned about at a leg's pick, once the time
    thrown at the last turn (or at the roar) is up."""
    flips = [s for s in _titled(own, f"Set {STALK_SIDE_VAR}")
             if any(_title(m) == "float * float" and _close(_num(m, "B"), -1.0)
                    and _titles(_feeders(m, "A")) == {f"Get {STALK_SIDE_VAR}"}
                    for m in _feeders(s, STALK_SIDE_VAR))]
    dues = [d for f in flips for d in _drivers(f)]
    tests = [t for d in dues for t in _feeders(d, "Condition")]
    check(f"{tag}: the way round is turned about once StalkTurnAt is up",
          len(flips) == 1 and len(dues) == 1 and _title(dues[0]) == "Branch"
          and flips[0] in _after(BEL.find_then_pin(dues[0]))
          and len(tests) == 1 and _title(tests[0]) == "float <= float"
          and _titles(_feeders(tests[0], "A")) == {f"Get {STALK_TURN_AT_VAR}"}
          and _titles(_feeders(tests[0], "B")) == {"GetTimeSeconds"},
          f"{len(flips)} turns, {len(dues)} gates")
    stamps = _titled(own, f"Set {STALK_TURN_AT_VAR}")
    again = [s for f in flips for s in _after(BEL.find_then_pin(f))]
    first = [s for s in stamps if s not in again]
    roars = _titled(own, f"Set {STALK_ROAR_UNTIL_VAR}")
    check(f"{tag}: ...{NPC_STALK_TURN_MIN_S:g}-{NPC_STALK_TURN_MAX_S:g} s (one "
          f"throw) after the last turn, or after the roar's end",
          len(stamps) == 2 and len(again) == 1 and again[0] in stamps
          and _titles(_turn_time(again[0]) or []) == {"GetTimeSeconds"}
          and len(first) == 1 and len(roars) == 1 and first[0] in _exec_reach(roars[0])
          and (_turn_time(first[0]) or []) == _feeders(roars[0], STALK_ROAR_UNTIL_VAR),
          f"{len(stamps)} writes of {STALK_TURN_AT_VAR}")
    begins = [n for n in _titled(own, f"Set {STALK_ARRIVED_VAR}")
              if _is(n, STALK_ARRIVED_VAR, False)]
    check(f"{tag}: ...at a leg's pick, before its sweeps, and the pick goes "
          f"on either way",
          len(begins) == 1 and len(dues) == 1 and len(again) == 1
          and sorted(_drivers(begins[0]), key=_title)
          == sorted([dues[0], again[0]], key=_title)
          and begins[0] in _after(BEL.find_else_pin(dues[0])))


def check_rage(tag, own, event, cdo):
    """A wendigo the player has hurt is enraged: it never hunts, it charges."""
    check(f"{tag}: it starts calm: {ENRAGED_VAR} is a bool that starts false",
          cdo.get_editor_property(ENRAGED_VAR) is False)
    heads = [b for b in _titled(own, "Branch")
             if _titles(_feeders(b, "Condition")) == {f"Get {ENRAGED_VAR}"}]
    hunt = [n for n in own if _title(n).startswith("Set Stalk")
            or _title(n) in ("SimpleMoveToLocation", "StopMovement")]
    check(f"{tag}: enraged, the step fails before anything else: no roar, no "
          f"tree, only the chase",
          len(heads) == 1 and _result(_after(BEL.find_then_pin(heads[0])), False)
          and heads[0] in _exec_reach(event) and bool(hunt)
          and all(n in _exec_reach(heads[0]) for n in hunt))
    marks = _titled(own, f"Set {ENRAGED_VAR}")
    hurts = [d for m in marks for d in _drivers(m)]
    casts = [c for h in hurts for c in _drivers(h)]
    check(f"{tag}: what enrages it is the hurt sense's flag "
          f"({DAMAGED_BY_PLAYER_VAR}), read next, on every pass",
          len(marks) == 1 and _is(marks[0], ENRAGED_VAR, True)
          and len(hurts) == 1 and _title(hurts[0]) == "Branch"
          and marks[0] in _after(BEL.find_then_pin(hurts[0]))
          and _titles(_feeders(hurts[0], "Condition")) == {f"Get {DAMAGED_BY_PLAYER_VAR}"}
          and len(heads) == 1 and len(casts) == 1
          and casts[0] in _after(BEL.find_else_pin(heads[0])),
          f"{[_title(h) for h in hurts]}")
    after = _exec_reach(marks[0]) if len(marks) == 1 else []
    voices = [v for v in _with(after, "Sound", "Location")
              if f"Get {VOICES_VAR}" in _titles(_sources(v, "Sound"))]
    ends = _titled(after, f"Set {STEP_RESULT_VAR}")
    check(f"{tag}: ...and it says so with one of its voices, the once, and "
          f"the step fails: the charge",
          len(voices) == 1 and len(ends) == 1 and _is(ends[0], STEP_RESULT_VAR, False)
          and not [n for n in after if n in hunt])
    calm = [b for b in _titled(own, "Branch")
            if _titles(_feeders(b, "Condition")) == {f"Get {STALK_CHARGING_VAR}"}]
    check(f"{tag}: unhurt (or with no health component), it hunts as before",
          len(calm) == 1 and len(hurts) == 1 and len(casts) == 1
          and calm[0] in _after(BEL.find_else_pin(hurts[0]))
          and calm[0] in [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
              BEL.find_output_pin(casts[0], "CastFailed"))])


def check_charge(tag, own, event):
    flags = _titled(own, f"Set {STALK_CHARGING_VAR}")
    gates = [d for f in flags for d in _drivers(f)]
    check(f"{tag}: within {NPC_STALK_CHARGE_CM:.0f} cm of the player it charges: "
          f"StalkCharging is set and the step fails",
          len(flags) == 1 and _is(flags[0], STALK_CHARGING_VAR, True)
          and len([g for g in gates
                   if _limit(g, "Distance2D (Vector)", NPC_STALK_CHARGE_CM)
                   and flags[0] in _after(BEL.find_then_pin(g))]) == 1
          and _result(_after(BEL.find_then_pin(flags[0])), False))
    still = [g for g in gates if _title(g) == "Branch"
             and "GetVelocity" in _titles(_sources(g, "Condition"))
             and [_num(t, "B") for t in _feeders(g, "Condition")
                  if _title(t) == "float < float"] == [NPC_STALK_STALLED_CMS]
             and flags[0] in _after(BEL.find_then_pin(g))]
    lost = [g for g in gates if _title(g) == "Branch"
            and _titles(_feeders(g, "Condition")) == {"Project Point to Navigation"}
            and flags[0] in _after(BEL.find_else_pin(g))]
    check(f"{tag}: ...and rather than stand: when it is not moving on a leg, "
          f"and when a leg has nowhere to end",
          len(gates) == 3 and len(still) == 1 and len(lost) == 1,
          f"{sorted(_title(g) for g in gates)}")
    heads = [b for b in _titled(own, "Branch")
             if _titles(_feeders(b, "Condition")) == {f"Get {STALK_CHARGING_VAR}"}]
    check(f"{tag}: ...and fails from then on, before anything else",
          len(heads) == 1 and _result(_after(BEL.find_then_pin(heads[0])), False)
          and all(n in _exec_reach(heads[0]) for n in own
                  if _title(n).startswith("Set Stalk"))
          and heads[0] in _exec_reach(event))


def check_cover(tag, own):
    sweeps = _with(own, "Start", "End", "Radius", "ActorsToIgnore")
    turns = sorted(_num(m, "B") for s in sweeps for m in _sources(s, "Start")
                   if _title(m) == "float * float"
                   and _titles(_feeders(m, "A")) == {f"Get {STALK_SIDE_VAR}"})
    check(f"{tag}: one sweep per angle ({', '.join(f'{a:.0f}' for a in NPC_STALK_ARC_DEG)} "
          f"deg), each turned the hunt's own way round the player",
          len(sweeps) == len(NPC_STALK_ARC_DEG) and len(turns) == len(sweeps)
          and all(_close(t, a) for t, a in zip(turns, sorted(NPC_STALK_ARC_DEG))),
          f"{len(sweeps)} sweeps, turned {turns}")
    check(f"{tag}: ...a {NPC_STALK_SWEEP_RADIUS_CM:.0f} cm sphere, along the line "
          f"at the player",
          bool(sweeps) and all(
              _close(_num(s, "Radius"), NPC_STALK_SWEEP_RADIUS_CM)
              and {"GetPlayerPawn", "Rotate Vector Around Axis",
                   "Normalize 2D (Vector)"} <= _titles(_sources(s, pin))
              for s in sweeps for pin in ("Start", "End")))
    clears = [n for n in own if _ins(n) == {"execute", "TargetArray"}]
    adds = _with(own, "TargetArray", "NewItem")
    spared = sorted(_title(f) for a in adds for f in _feeders(a, "NewItem"))
    check(f"{tag}: ...ignoring the ground it stands on and its own pawn, "
          f"listed afresh for each leg",
          len(clears) == 1 and spared == ["Get Controlled Pawn", "GetMovementBaseActor"]
          and all(a in _exec_reach(clears[0]) for a in adds)
          and all(s in _exec_reach(a) for a in adds for s in sweeps)
          and all(_titles(_feeders(s, "ActorsToIgnore")) == {f"Get {STALK_IGNORE_VAR}"}
                  for s in sweeps))

    raws = [s for s in _titled(own, f"Set {STALK_COVER_VAR}")
            if "BreakTransform" in _titles(_sources(s, STALK_COVER_VAR))]
    stands = _with(own, "InstanceIndex", "bWorldSpace")
    check(f"{tag}: a tree is an instanced mesh the sweep struck, and stands "
          f"where that instance's own transform says",
          len(stands) == len(sweeps) and all(
              _is(t, "bWorldSpace", True)
              and _titles(_feeders(t, "InstanceIndex")) == {"BreakHitResult"}
              and _titles(_feeders(t, "self")) == {"Cast To InstancedStaticMeshComponent"}
              for t in stands))
    hides = [n for n in _titled(own, f"Set {STALK_HIDDEN_VAR}")
             if _is(n, STALK_HIDDEN_VAR, True)]
    snaps = [d for h in hides for d in _drivers(h)]
    on_nav = [b for s in snaps for b in _drivers(s)]
    steps_in = [r for b in on_nav for r in _with(_sources(b, "Condition"),
                                                  "Value", "Min", "Max")]
    check(f"{tag}: a spot counts only {NPC_STALK_GAIN_MIN_CM:.0f} cm or more "
          f"closer to the player than the pawn stands, and no nearer than "
          f"{NPC_STALK_COVER_MIN_CM:.0f} cm",
          len(steps_in) == len(sweeps) > 0 and all(
              _close(_num(r, "Min"), NPC_STALK_COVER_MIN_CM)
              and _titles(_feeders(r, "Value")) == {"Distance2D (Vector)"}
              and f"Get {STALK_COVER_VAR}" in _titles(_sources(r, "Value"))
              and any(_title(m) == "float - float"
                      and _close(_num(m, "B"), NPC_STALK_GAIN_MIN_CM)
                      for m in _feeders(r, "Max"))
              for r in steps_in))
    check(f"{tag}: the spot is {NPC_STALK_BEHIND_CM:.0f} cm past the trunk, seen "
          f"from the player, and counts only once it is on the navmesh",
          len(hides) == len(sweeps) and len(snaps) == len(hides)
          and all(_title(s) == f"Set {STALK_COVER_VAR}"
                  and _titles(_feeders(s, STALK_COVER_VAR)) == {"Project Point to Navigation"}
                  for s in snaps)
          and len(on_nav) == len(snaps)
          and all(_title(b) == "Branch" and "Project Point to Navigation"
                  in _titles(_sources(b, "Condition"))
                  and _titles(_feeders(b, "Condition")) == {"AND Boolean"}
                  for b in on_nav)
          and len(raws) == len(sweeps)
          and all(any(_title(m) == "MakeVector"
                      and _close(_num(m, "X"), NPC_STALK_BEHIND_CM)
                      for m in _sources(raw, STALK_COVER_VAR))
                  and {"GetPlayerPawn", "Normalize 2D (Vector)"}
                  <= _titles(_sources(raw, STALK_COVER_VAR)) for raw in raws))
    lines = [n for n in _with(own, "Start", "End", "ActorsToIgnore")
             if "Radius" not in _ins(n)]
    check(f"{tag}: ...and only if a line from it to the player strikes a "
          f"tree: a sapling or a leaning trunk hides nothing",
          len(lines) == len(raws) == len(on_nav) > 0 and all(
              _titles(_feeders(ln, "Start")) == {f"Get {STALK_COVER_VAR}"}
              and "GetPlayerPawn" in _titles(_sources(ln, "End"))
              and _titles(_feeders(ln, "ActorsToIgnore")) == {f"Get {STALK_IGNORE_VAR}"}
              and len(_drivers(ln)) == 1 and _drivers(ln)[0] in raws
              for ln in lines)
          and all(len([c for c in _drivers(b)
                       if _title(c) == "Cast To InstancedStaticMeshComponent"
                       and any(ln in _drivers(g) for g in _drivers(c) for ln in lines)])
                  == 1 for b in on_nav))
    bare = [n for n in _titled(own, f"Set {STALK_HIDDEN_VAR}")
            if _is(n, STALK_HIDDEN_VAR, False)]
    opens = [s for s in _titled(own, f"Set {STALK_COVER_VAR}")
             if s not in raws and s not in snaps
             and "BreakHitResult" not in _titles(_sources(s, STALK_COVER_VAR))
             and "Project Point to Navigation"
             not in _titles(_feeders(s, STALK_COVER_VAR))]
    check(f"{tag}: no tree on any line: the leg ends in the open, on round "
          f"the player",
          len(bare) == 1 and len(sweeps) == len(NPC_STALK_ARC_DEG)
          and all(bare[0] in _exec_reach(s) for s in sweeps)
          and [_titles(_feeders(d, STALK_COVER_VAR)) for d in _drivers(bare[0])]
          == [{"Project Point to Navigation"}]
          and len(opens) == 1 and all(opens[0] in _exec_reach(s) for s in sweeps)
          and bare[0] in _exec_reach(opens[0]))
    return hides + bare


def check_legs(tag, own, settled):
    runs = _with(own, "Controller", "Goal")
    clears = _titled(own, "ClearFocus")
    check(f"{tag}: one move order, to the stored spot, facing the way it runs, "
          f"whichever way the spot was settled",
          len(runs) == 1 and _titles(_feeders(runs[0], "Goal")) == {f"Get {STALK_COVER_VAR}"}
          and _title(runs[0]) == "SimpleMoveToLocation"
          and len(clears) == 1 and runs[0] in _exec_reach(clears[0])
          and bool(settled) and all(clears[0] in _exec_reach(s) for s in settled))
    speeds = _titled(own, "Set MaxWalkSpeed")
    check(f"{tag}: it runs its legs at {NPC_STALK_RUN_SCALE:.0%} of its run "
          f"speed: written after the order, and on every pass of a leg",
          len(speeds) == 2 and len(runs) == 1
          and len([s for s in speeds if s in _exec_reach(runs[0])]) == 1
          and all("Get TuneRunSpeed" in _titles(_sources(s, "MaxWalkSpeed"))
                  and [_num(m, "B") for m in _feeders(s, "MaxWalkSpeed")
                       if _title(m) == "float * float"] == [NPC_STALK_RUN_SCALE]
                  for s in speeds))
    arrivals = [n for n in _titled(own, f"Set {STALK_ARRIVED_VAR}")
                if _is(n, STALK_ARRIVED_VAR, True)]
    gates = [d for a in arrivals for d in _drivers(a)]
    check(f"{tag}: a leg is over within {NPC_STALK_ARRIVE_CM:.0f} cm of its spot",
          len(arrivals) == 1 and len(gates) == 1
          and _limit(gates[0], "Distance2D (Vector)", NPC_STALK_ARRIVE_CM)
          and f"Get {STALK_COVER_VAR}" in _titles(_sources(gates[0], "Condition")))
    waits = [n for a in arrivals for n in _exec_reach(a)
             if _title(n) == f"Set {STALK_LEG_UNTIL_VAR}"]
    throws = [n for w in waits for n in _sources(w, STALK_LEG_UNTIL_VAR)
              if _title(n) == "RandomFloatInRange"]
    picks = [n for w in waits for n in _sources(w, STALK_LEG_UNTIL_VAR)
             if _title(n) == "SelectFloat"]
    check(f"{tag}: ...and then it waits {NPC_STALK_HIDE_MIN_S:g}-"
          f"{NPC_STALK_HIDE_MAX_S:g} s (one throw) behind a trunk, and not at "
          f"all in the open, watching the player",
          len(waits) == 1 and len(throws) == 1 and len(picks) == 1
          and _close(_num(throws[0], "Min"), NPC_STALK_HIDE_MIN_S)
          and _close(_num(throws[0], "Max"), NPC_STALK_HIDE_MAX_S)
          and len(PIN.list_connected_pins(
              BEL.find_output_pin(throws[0], "ReturnValue"))) == 1
          and _titles(_feeders(picks[0], "bPickA")) == {f"Get {STALK_HIDDEN_VAR}"}
          and throws[0] in _feeders(picks[0], "A")
          and _lit(picks[0], "B") in ("0.0", "0.000000", "0", "")
          and any(_title(n) == "SetFocus" for n in _exec_reach(waits[0])))
    starts = [n for n in _titled(own, f"Set {STALK_LEG_UNTIL_VAR}")
              if any(_close(_num(a, "B"), NPC_STALK_LEG_TIMEOUT_S)
                     for a in _feeders(n, STALK_LEG_UNTIL_VAR))]
    check(f"{tag}: a leg not finished in {NPC_STALK_LEG_TIMEOUT_S:g} s is given "
          f"up for the next",
          len(starts) == 1 and len(runs) == 1 and runs[0] in _exec_reach(starts[0])
          and len(_titled(own, f"Set {STALK_LEG_UNTIL_VAR}")) == 2)


def check_stalk(path, key):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag}: exists, for its hunt", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    own = step_nodes(ed.list_all_nodes(), STEP_STALK)
    if key not in NPC_STALK_ROAR:
        check(f"{tag}: does not stalk: no BT_{STEP_STALK} step", not own)
        return
    events = [n for n in own if n.get_class().get_name() == "K2Node_CustomEvent"]
    check(f"{tag}: stalks: it has a BT_{STEP_STALK} step", len(events) == 1)
    if len(events) != 1:
        return
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    held = {v: cdo.get_editor_property(v) for v in (
        STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR, STALK_TURN_AT_VAR, STALK_LEG_UNTIL_VAR,
        STALK_LEGS_VAR, STALK_CHARGING_VAR, STALK_ARRIVED_VAR, STALK_HIDDEN_VAR)}
    check(f"{tag}: a hunt starts unroared, with no leg and not charging",
          all(isinstance(held[v], float) and held[v] == 0.0 for v in (
              STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR, STALK_TURN_AT_VAR,
              STALK_LEG_UNTIL_VAR))
          and held[STALK_LEGS_VAR] == 0 and len(cdo.get_editor_property(STALK_IGNORE_VAR)) == 0
          and not any(held[v] for v in (STALK_CHARGING_VAR, STALK_ARRIVED_VAR,
                                        STALK_HIDDEN_VAR)), f"{held}")
    check_roar(tag, own, key)
    check_turns(tag, own)
    check_rage(tag, own, events[0], cdo)
    check_charge(tag, own, events[0])
    check_legs(tag, own, check_cover(tag, own))


def run():
    check_settings()
    check_stalk(AI_BP_PATH, NPC_VARIANTS[0].key)
    for variant in NPC_VARIANTS:
        check_stalk(variant.ai_blueprint, variant.key)
