"""Checks for the wanderers' patrol and agro, read back off the saved
controllers. Run through Scripts/verify_npc_blueprints.py.

Each controller is checked against ITS OWN creature's numbers,
npc/monster_tuning.monster_specs(): every graph reads them off the
controller's Tune* variables (npc/tuned.py), so the checks are that each is
wired to its variable and that the variable's default is this creature's --
a wendigo controller carrying the zombie's vision range compiles, runs, and
is wrong.

The chase and melee half of these graphs is still checked by the level
verifier (verify_<Level>.py); this file owns what npc/agro.py, patrol.py,
senses.py, corpse.py, combat_trace.py and block.py added. The behaviour tree
and the step events are npc/verify_tree.py's.
"""

import unreal

from combat.tuning import COMBAT
from forest_generator.npc_agro import (
    AGRO_LOG_PREFIX, NPC_AGRO, PATROL_ACCEPT_FRACTION, PATROL_ACCEPT_SLACK_CM,
    agro_for,
)
from forest_generator.npc_placement import NPC_VARIANTS
from combat.game_state import COMBAT_TRACE_PREFIX, COMBAT_TRACE_VAR, DEBUG_MODE_VAR
from npc.paths import (
    AGGRO_REASON_VAR, AGGRO_VAR, AI_BP_PATH, CORPSE_LOG_PREFIX, CORPSE_VAR,
    NEXT_PATROL_VAR, PATROL_HOME_VAR, PATROL_READY_VAR, PATROL_TARGET_VAR,
    HIT_DAMAGE_VAR, RUN_SPEED_VAR, STEP_CHASE,
)
from npc.block import BLOCK_MIN_DOT
from npc.monster_tuning import MONSTER_STATS, TUNED_VAR, monster_specs, stock_run_speed
from npc.tuned import tuned_values

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'}  {label}"
                       + (f" — {detail}" if detail else ""))


# ─── Graph reading ───────────────────────────────────────────────────────────

def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _titled(nodes, title):
    return [n for n in nodes if _title(n) == title]


def _ins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _lit(n, pin):
    return str(PIN.get_pin_value(BEL.find_input_pin(n, pin)))


def _num(n, pin):
    try:
        return float(_lit(n, pin))
    except ValueError:
        return None


def _close(a, b):
    return a is not None and abs(a - b) < 1e-3


def _feeders(n, pin):
    """The nodes wired into ``n``'s input pin ``pin`` (data or exec)."""
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_input_pin(n, pin))]


def _drivers(n):
    """The nodes whose exec output runs ``n``."""
    return [PIN.get_owning_node(q)
            for q in BEL.find_execute_pin(n).list_connected_pins()]


def _with_literal(nodes, pin, value):
    return [n for n in nodes if pin in _ins(n) and _close(_num(n, pin), value)]


def _limits(nodes, *measured):
    """Every "distance <= B" whose distance is measured between exactly the
    ``measured`` getters -- so two limits are told apart by what they
    measure, not by what they are compared with."""
    out = []
    for n in _titled(nodes, "float <= float"):
        for d in _feeders(n, "A"):
            if _title(d) == "Distance (Vector)" and sorted(
                    _title(f) for pin in ("V1", "V2") for f in _feeders(d, pin)) \
                    == sorted(measured):
                out.append(n)
    return out


def _fed(n, pin, column):
    """Is ``n``'s ``pin`` wired from exactly the Tune variable for ``column``?"""
    return {_title(f) for f in _feeders(n, pin)} == {f"Get {TUNED_VAR[column]}"}


# ─── The settings table ──────────────────────────────────────────────────────

def check_settings():
    for variant in NPC_VARIANTS:
        try:
            a = agro_for(variant.key)
        except KeyError as exc:
            check(f"{variant.key} has agro settings", False, str(exc))
            continue
        check(f"{variant.key} has agro settings", True)
        check(f"{variant.key}: the vision cone is a cone (0-90 degrees either side)",
              0.0 < a.vision_half_angle_deg < 90.0, f"{a.vision_half_angle_deg}")
        check(f"{variant.key}: patrols slower than it runs",
              0.0 < a.patrol_speed_scale < 1.0, f"{a.patrol_speed_scale}")
        check(f"{variant.key}: every range is positive",
              min(a.vision_range_cm, a.touch_range_cm, a.patrol_radius_cm,
                  a.hearing_scale) > 0.0)
        check(f"{variant.key}: touch is shorter than sight",
              a.touch_range_cm < a.vision_range_cm)
        check(f"{variant.key}: the re-pick window is a window",
              0.0 < a.patrol_repick_min_s <= a.patrol_repick_max_s)
    check("no agro settings for a creature that does not exist",
          set(NPC_AGRO) <= {v.key for v in NPC_VARIANTS}, f"{sorted(NPC_AGRO)}")


# ─── One controller ──────────────────────────────────────────────────────────

def check_controller(path, key):
    tag = path.rsplit("/", 1)[-1]
    spec = monster_specs(key)
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    check(f"{tag} exists", bp is not None)
    if not bp:
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check(f"{tag}: the graph compiles clean", not ed.list_nodes_with_errors())
    check_corpse_and_trace(tag, nodes, cdo)
    check_player_guard(tag, nodes, spec)

    # --- state, and that it starts patrolling --------------------------------
    kinds = {AGGRO_VAR: bool, PATROL_READY_VAR: bool, AGGRO_REASON_VAR: str,
             RUN_SPEED_VAR: float, NEXT_PATROL_VAR: float,
             PATROL_HOME_VAR: unreal.Vector, PATROL_TARGET_VAR: unreal.Vector}
    for name, kind in kinds.items():
        value = cdo.get_editor_property(name)
        check(f"{tag}: {name} is a {kind.__name__}", isinstance(value, kind),
              type(value).__name__)
    check(f"{tag}: spawns PATROLLING (Aggro defaults to false)",
          cdo.get_editor_property(AGGRO_VAR) is False)
    held = tuned_values(cdo)
    off = [f"{c}={held[c]:g} want {spec[c]:g}" for c, *_r in MONSTER_STATS
           if abs(held[c] - spec[c]) > 1e-3]
    check(f"{tag}: its {len(MONSTER_STATS)} Tune variables hold {key}'s "
          f"monster_specs (monster_tuning.csv over the literals)", not off, "; ".join(off))

    # --- the switch ----------------------------------------------------------
    flips = _titled(nodes, f"Set {AGGRO_VAR}")
    check(f"{tag}: one thing flips it to aggro, and nothing flips it back",
          len(flips) == 1 and _lit(flips[0], AGGRO_VAR) == "true",
          f"{[_lit(n, AGGRO_VAR) for n in flips]}")
    reasons = sorted(_lit(n, AGGRO_REASON_VAR)
                     for n in _titled(nodes, f"Set {AGGRO_REASON_VAR}"))
    check(f"{tag}: four senses can flip it -- hurt, sight, touch, sound",
          reasons == ["hurt", "sight", "sound", "touch"], f"{reasons}")
    moves = [n for n in nodes if {"Goal", "AcceptanceRadius"} <= _ins(n)]
    chase_gate = [d for m in moves for d in _drivers(m)]
    # The chase is its own step, BT_Chase, and nothing else runs into it: that
    # it runs only once aggro is the tree's Blackboard gate (verify_tree.py).
    into_chase = [_title(d) for g in chase_gate for d in _drivers(g)]
    check(f"{tag}: the chase is reached only from its step event, BT_{STEP_CHASE}",
          len(chase_gate) == 1 and len(into_chase) == 1
          and into_chase[0].startswith(f"BT_{STEP_CHASE}"), f"{into_chase}")
    warns = _titled(nodes, "PrintWarning")
    heads = [n for n in _titled(nodes, "Append") if _lit(n, "A") == AGRO_LOG_PREFIX]
    check(f"{tag}: going aggro is logged as '{AGRO_LOG_PREFIX.strip()} <sense>'",
          len(warns) == 1 and len(heads) == 1)
    gates = [d for w in warns for d in _drivers(w)]
    check(f"{tag}: ...only while the GameMode's {DEBUG_MODE_VAR} is on",
          len(gates) == 1 and _title(gates[0]) == "Branch"
          and {_title(f) for f in _feeders(gates[0], "Condition")}
          == {f"Get {DEBUG_MODE_VAR}"}
          and [str(PIN.get_pin_name(q)) for q in
               BEL.find_execute_pin(warns[0]).list_connected_pins()] == ["then"],
          f"{sorted(_title(d) for d in gates)}")

    # --- speed ---------------------------------------------------------------
    speeds = _titled(nodes, "Set MaxWalkSpeed")
    check(f"{tag}: two speed writes, the stroll and the run", len(speeds) == 2,
          f"{len(speeds)}")
    stock = stock_run_speed(key)
    muls = _titled(nodes, "float * float")
    runs = [n for n in muls
            if {_title(f) for f in _feeders(n, "A")} == {f"Get {RUN_SPEED_VAR}"}]
    ratios = [f for n in runs for f in _feeders(n, "B")]
    strolls = [n for n in muls if _fed(n, "B", "patrol_speed_scale")
               and set(_feeders(n, "A")) <= set(runs)]
    check(f"{tag}: runs at ITS OWN run speed x TuneRunSpeed / {stock:.0f} (the "
          f"stored RunSpeed, never the live MaxWalkSpeed), and strolls at "
          f"TunePatrolSpeed of that",
          len(runs) == 2 and len(ratios) == 2
          and all(_fed(r, "A", "run_speed_cms") and _close(_num(r, "B"), stock)
                  for r in ratios) and len(strolls) == 1,
          f"{len(runs)} runs, {len(strolls)} strolls")
    cached = _titled(nodes, f"Set {RUN_SPEED_VAR}")
    check(f"{tag}: RunSpeed is read off the pawn once",
          len(cached) == 1 and {_title(f) for f in _feeders(cached[0], RUN_SPEED_VAR)}
          == {"Get MaxWalkSpeed"})

    # --- patrol --------------------------------------------------------------
    picks = [n for n in nodes if {"Origin", "Radius"} <= _ins(n)]
    check(f"{tag}: picks points inside a TunePatrolRadius circle",
          len(picks) == 1 and _fed(picks[0], "Radius", "patrol_radius_cm")
          and {_title(f) for f in _feeders(picks[0], "Origin")} == {f"Get {PATROL_HOME_VAR}"},
          f"{[_lit(n, 'Radius') for n in picks]}")
    if picks:
        # Pure: every output read is a fresh random query. One read, into a Set.
        rv = BEL.find_output_pin(picks[0], "ReturnValue")
        loc = BEL.find_output_pin(picks[0], "RandomLocation")
        users = {_title(PIN.get_owning_node(q)) for q in PIN.list_connected_pins(loc)}
        check(f"{tag}: the random query is read exactly once, into PatrolTarget",
              not PIN.list_connected_pins(rv) and users == {f"Set {PATROL_TARGET_VAR}"},
              f"{users}")
    homes = _titled(nodes, f"Set {PATROL_HOME_VAR}")
    check(f"{tag}: the circle is centred where it spawned",
          len(homes) == 1 and {_title(f) for f in _feeders(homes[0], PATROL_HOME_VAR)}
          == {"Get Actor Location"})
    fences = _limits(nodes, f"Get {PATROL_TARGET_VAR}", f"Get {PATROL_HOME_VAR}")
    adds = [f for n in fences for f in _feeders(n, "B")]
    loose = [f for a in adds for f in _feeders(a, "A")]
    check(f"{tag}: a point outside the circle (the no-navmesh origin) is refused: "
          f"TunePatrolRadius x {PATROL_ACCEPT_FRACTION} + {PATROL_ACCEPT_SLACK_CM:.0f} cm",
          len(fences) == 1 and len(adds) == 1 and len(loose) == 1
          and _close(_num(adds[0], "B"), PATROL_ACCEPT_SLACK_CM)
          and _close(_num(loose[0], "B"), PATROL_ACCEPT_FRACTION)
          and _fed(loose[0], "A", "patrol_radius_cm"),
          f"{len(fences)} fences")
    strolls = _titled(nodes, "SimpleMoveToLocation")
    check(f"{tag}: one stroll order, to the stored PatrolTarget",
          len(strolls) == 1 and {_title(f) for f in _feeders(strolls[0], "Goal")}
          == {f"Get {PATROL_TARGET_VAR}"}, f"{len(strolls)}")
    windows = [n for n in nodes if {"Min", "Max"} <= _ins(n)
               and _fed(n, "Min", "patrol_repick_min_s")
               and _fed(n, "Max", "patrol_repick_max_s")]
    check(f"{tag}: a new point every TunePatrolRepickMin-Max s "
          f"({spec['patrol_repick_min_s']:g}-{spec['patrol_repick_max_s']:g})",
          len(windows) == 1)

    # --- the senses ----------------------------------------------------------
    # Sight, touch and the melee swing all measure pawn-to-player, so each is
    # looked for among those limits (the settings check keeps them distinct).
    reach = _limits(nodes, "Get Actor Location", "Get Actor Location")
    fed = sorted(_title(f) for n in reach for f in _feeders(n, "B"))
    check(f"{tag}: sees TuneSightRange ({spec['vision_range_cm'] / 100:.0f} m)",
          sum(_fed(n, "B", "vision_range_cm") for n in reach) == 1, f"{fed}")
    cones = [n for n in _titled(nodes, "float >= float")
             if any(_fed(c, "A", "vision_half_angle_deg") for c in _feeders(n, "B"))]
    check(f"{tag}: ...within DegCos(TuneSightHalfAngle) of its facing "
          f"({spec['vision_half_angle_deg']:.0f} degrees either side)", len(cones) == 1)
    los = _titled(nodes, "LineOfSightTo")
    check(f"{tag}: ...and not through a tree (line of sight to the player)",
          len(los) == 1 and {_title(f) for f in _feeders(los[0], "Other")}
          == {"GetPlayerPawn"})
    check(f"{tag}: feels the player within TuneTouchRange "
          f"({spec['touch_range_cm']:.0f} cm)",
          sum(_fed(n, "B", "touch_range_cm") for n in reach) == 1, f"{fed}")
    check(f"{tag}: hears at TuneHearing ({spec['hearing_scale']:g})x a noise's own "
          f"reach, all round and down the cone",
          sum(_fed(n, "B", "hearing_scale") for n in muls) == 2)
    check(f"{tag}: only a noise from the last {COMBAT.noise_hold_s} s is heard",
          len(_with_literal(_titled(nodes, "float <= float"), "B", COMBAT.noise_hold_s)) == 1)


def _exec_reach(start):
    """Every node reachable from ``start`` along exec wires, ``start`` included."""
    seen, todo = {}, [start]
    while todo:
        n = todo.pop()
        key = n.get_path_name()
        if key in seen:
            continue
        seen[key] = n
        for pin in BEL.list_output_pins(n):
            if "exec" not in str(PIN.get_pin_type_display_string(pin)).lower():
                continue
            todo += [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]
    return list(seen.values())


def check_corpse_and_trace(tag, nodes, cdo):
    """npc/corpse.py's state gate and npc/combat_trace.py's melee line."""
    check(f"{tag}: {CORPSE_VAR} is a bool that starts false",
          cdo.get_editor_property(CORPSE_VAR) is False)
    marks = _titled(nodes, f"Set {CORPSE_VAR}")
    check(f"{tag}: one thing makes it a corpse, and nothing makes it alive",
          len(marks) == 1 and _lit(marks[0], CORPSE_VAR) == "true",
          f"{[_lit(n, CORPSE_VAR) for n in marks]}")
    if len(marks) != 1:
        return
    gate = [d for d in _drivers(marks[0]) if _title(d) == "Branch"]
    check(f"{tag}: ...when its pawn's health component reads Dead",
          len(gate) == 1 and {_title(f) for f in _feeders(gate[0], "Condition")}
          == {"Get Dead"})
    after = _exec_reach(marks[0])
    check(f"{tag}: a corpse's heartbeat ends -- no Delay, no move, no swing after it",
          not any(_title(n) == "Delay" or {"Goal"} <= _ins(n) or {"Dest"} <= _ins(n)
                  or {"SlotNodeName"} <= _ins(n) for n in after),
          f"{sorted({_title(n) for n in after})}")
    check(f"{tag}: ...and it stops moving",
          any(_title(n) == "StopMovement" for n in after),
          f"{sorted({_title(n) for n in after})}")
    check(f"{tag}: ...and stops its behaviour tree",
          any(_title(n).replace(" ", "") == "StopLogic" for n in after),
          f"{sorted({_title(n) for n in after})}")
    heads = [n for n in _titled(nodes, "Append") if _lit(n, "A") == CORPSE_LOG_PREFIX]
    check(f"{tag}: becoming a corpse is logged as '{CORPSE_LOG_PREFIX}<n>'",
          len(heads) == 1)
    # The corpse check has to come before everything else the heartbeat does:
    # the stats/voice fragment must be reached only through it.
    if gate:
        cast = [d for d in _drivers(gate[0])]
        before = [d for c in cast for d in _drivers(c)]
        check(f"{tag}: it is the first thing checked once there is a pawn",
              len(before) == 1 and _title(before[0]) == "Branch"
              and {_title(f) for f in _feeders(before[0], "Condition")} == {"IsValid"},
              f"{[_title(b) for b in before]}")

    # --- the combat trace ----------------------------------------------------
    trace_heads = [n for n in _titled(nodes, "Append")
                   if _lit(n, "A") == f"{COMBAT_TRACE_PREFIX}melee #"]
    check(f"{tag}: a landed swing can log '{COMBAT_TRACE_PREFIX}melee #<n> ...'",
          len(trace_heads) == 1)
    flags = [n for n in nodes if _title(n) == f"Get {COMBAT_TRACE_VAR}"]
    gated = [b for f in flags for b in _titled(nodes, "Branch")
             if f in _feeders(b, "Condition")]
    check(f"{tag}: ...only while the GameMode's {COMBAT_TRACE_VAR} is on",
          len(flags) == 1 and len(gated) == 1)


def check_player_guard(tag, nodes, spec):
    """npc/block.py: what the player's guard does to a landed swing."""
    sets = _titled(nodes, f"Set {HIT_DAMAGE_VAR}")
    full = [n for n in sets if _fed(n, HIT_DAMAGE_VAR, "melee_damage")]
    soft = [n for n in sets for m in _feeders(n, HIT_DAMAGE_VAR)
            if _fed(m, "A", "melee_damage")
            and _close(_num(m, "B"), COMBAT.block_damage_scale)]
    check(f"{tag}: a swing deals TuneMeleeDamage ({spec['melee_damage']:g}), or "
          f"{COMBAT.block_damage_scale:g}x it on the player's guard",
          len(sets) == 2 and len(full) == 1 and len(soft) == 1
          and 0.0 < COMBAT.block_damage_scale < 1.0, f"{len(sets)} sets")
    hurts = [n for n in _titled(nodes, "float - float")
             if {_title(f) for f in _feeders(n, "A")} == {"Get Health"}]
    check(f"{tag}: the Health write subtracts {HIT_DAMAGE_VAR}, not a literal",
          len(hurts) == 1
          and {_title(f) for f in _feeders(hurts[0], "B")} == {f"Get {HIT_DAMAGE_VAR}"},
          f"{[_lit(n, 'B') for n in hurts]}")
    # The player's Health write, told from this creature's own (stats.py) by
    # what runs it.
    writes = [n for n in _titled(nodes, "Set Health")
              if f"Set {HIT_DAMAGE_VAR}" in {_title(d) for d in _drivers(n)}]
    check(f"{tag}: ...and runs only after {HIT_DAMAGE_VAR} is set, on both arms",
          len(writes) == 1 and sorted(_title(d) for d in _drivers(writes[0]))
          == [f"Set {HIT_DAMAGE_VAR}"] * 2,
          f"{[_title(d) for w in writes for d in _drivers(w)]}")
    pay = [d for n in soft for d in _drivers(n)]
    check(f"{tag}: a blocked swing costs the player "
          f"{COMBAT.block_stamina_per_hit:.0f} stamina first",
          len(pay) == 1 and _title(pay[0]) == "Set Stamina"
          and any(_close(_num(f, "B"), COMBAT.block_stamina_per_hit)
                  for c in _feeders(pay[0], "Stamina") for f in _feeders(c, "Value")),
          f"{[_title(d) for d in pay]}")
    gate = [d for p in pay for d in _drivers(p) if _title(d) == "Branch"]
    cond = [f for g in gate for f in _feeders(g, "Condition")]
    fed = {_title(x) for c in cond for pin in ("A", "B") for x in _feeders(c, pin)}
    fronts = [x for c in cond for x in _feeders(c, "B")]
    check(f"{tag}: ...only while the player is Blocking and the swing comes from "
          f"within {COMBAT.block_half_angle_deg:.0f} deg of their facing",
          len(gate) == 1 and "Get Blocking" in fed
          and any(_close(_num(x, "B"), BLOCK_MIN_DOT) for x in fronts),
          f"{sorted(fed)}")
    into_full = sorted(_title(d) for n in full for d in _drivers(n))
    check(f"{tag}: no guard, or no weapon component, is the full swing "
          f"(every exit of the check reaches the Health write)",
          len(full) == 1 and len(into_full) == 2 and "Branch" in into_full,
          f"{into_full}")
    # The HUD's save-and-exit is called off by a hit, and reads it off this.
    stamps = _titled(nodes, "Set LastDamageTime")
    check(f"{tag}: a landed swing stamps the player's LastDamageTime with the "
          f"game time, after its bearing",
          len(stamps) == 1
          and any("Time" in _title(f) for f in _feeders(stamps[0], "LastDamageTime"))
          and [_title(d) for d in _drivers(stamps[0])] == ["Set LastHitFrom"],
          f"{[[_title(d) for d in _drivers(n)] for n in stamps]}")


def run():
    check_settings()
    check_controller(AI_BP_PATH, NPC_VARIANTS[0].key)
    for variant in NPC_VARIANTS:
        check_controller(variant.ai_blueprint, variant.key)
