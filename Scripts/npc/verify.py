"""Checks for the wanderers' patrol and agro, read back off the saved
controllers. Run through Scripts/verify_npc_blueprints.py.

Each controller is checked against ITS OWN creature's AgroSettings, because
the numbers are pin literals baked per controller: a wendigo controller
carrying the zombie's vision range compiles, runs, and is wrong.

The chase and melee half of these graphs is still checked by the level
verifier (verify_<Level>.py); this file owns what npc/agro.py, patrol.py and
senses.py added.
"""

import math

import unreal

from combat.tuning import COMBAT
from forest_generator.npc_agro import (
    AGRO_LOG_PREFIX, NPC_AGRO, PATROL_ACCEPT_FRACTION, PATROL_ACCEPT_SLACK_CM,
    agro_for,
)
from forest_generator.npc_placement import NPC_VARIANTS
from combat.game_state import COMBAT_TRACE_PREFIX, COMBAT_TRACE_VAR
from npc.paths import (
    AGGRO_REASON_VAR, AGGRO_VAR, AI_BP_PATH, CORPSE_LOG_PREFIX, CORPSE_VAR,
    NEXT_PATROL_VAR, PATROL_HOME_VAR, PATROL_READY_VAR, PATROL_TARGET_VAR,
    RUN_SPEED_VAR,
)

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
    """The B literals of every "distance <= B" whose distance is measured
    between exactly the ``measured`` getters -- so two limits that happen to
    share a number (the wendigo's 35 m sight and its 35 m patrol guard) are
    still told apart by what they measure."""
    out = []
    for n in _titled(nodes, "float <= float"):
        for d in _feeders(n, "A"):
            if _title(d) == "Distance (Vector)" and sorted(
                    _title(f) for pin in ("V1", "V2") for f in _feeders(d, pin)) \
                    == sorted(measured):
                out.append(_num(n, "B"))
    return out


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

def check_controller(path, agro):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    check(f"{tag} exists", bp is not None)
    if not bp:
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check(f"{tag}: the graph compiles clean", not ed.list_nodes_with_errors())
    check_corpse_and_trace(tag, nodes, cdo)

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
    ok = len(chase_gate) == 1
    if ok:
        into_chase = {_title(d) for d in _drivers(chase_gate[0])}
        # The chase is reached only through the switch: from the Aggro branch
        # (already hunting) or from the log line (just started).
        ok = into_chase == {"Branch", "PrintWarning"}
        by_aggro = [d for d in _drivers(chase_gate[0]) if _title(d) == "Branch"
                    and {_title(f) for f in _feeders(d, "Condition")} == {f"Get {AGGRO_VAR}"}]
        ok = ok and len(by_aggro) == 1
    check(f"{tag}: the chase runs only once aggro", ok)
    warns = _titled(nodes, "PrintWarning")
    heads = [n for n in _titled(nodes, "Append") if _lit(n, "A") == AGRO_LOG_PREFIX]
    check(f"{tag}: going aggro is logged as '{AGRO_LOG_PREFIX.strip()} <sense>'",
          len(warns) == 1 and len(heads) == 1)

    # --- speed ---------------------------------------------------------------
    speeds = _titled(nodes, "Set MaxWalkSpeed")
    check(f"{tag}: two speed writes, the stroll and the run", len(speeds) == 2,
          f"{len(speeds)}")
    stroll = _with_literal(_titled(nodes, "float * float"), "B", agro.patrol_speed_scale)
    check(f"{tag}: strolls at {agro.patrol_speed_scale:.0%} of ITS OWN run speed "
          f"(the stored RunSpeed, never the live MaxWalkSpeed)",
          len(stroll) == 1
          and {_title(f) for f in _feeders(stroll[0], "A")} == {f"Get {RUN_SPEED_VAR}"})
    cached = _titled(nodes, f"Set {RUN_SPEED_VAR}")
    check(f"{tag}: RunSpeed is read off the pawn once",
          len(cached) == 1 and {_title(f) for f in _feeders(cached[0], RUN_SPEED_VAR)}
          == {"Get MaxWalkSpeed"})

    # --- patrol --------------------------------------------------------------
    picks = [n for n in nodes if {"Origin", "Radius"} <= _ins(n)]
    check(f"{tag}: picks points inside a {agro.patrol_radius_cm / 100:.0f} m circle",
          len(picks) == 1 and _close(_num(picks[0], "Radius"), agro.patrol_radius_cm)
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
    guard = agro.patrol_radius_cm * PATROL_ACCEPT_FRACTION + PATROL_ACCEPT_SLACK_CM
    fences = _limits(nodes, f"Get {PATROL_TARGET_VAR}", f"Get {PATROL_HOME_VAR}")
    check(f"{tag}: a point outside the circle (the no-navmesh origin) is refused",
          len(fences) == 1 and _close(fences[0], guard), f"{fences} vs {guard:.0f} cm")
    strolls = _titled(nodes, "SimpleMoveToLocation")
    check(f"{tag}: one stroll order, to the stored PatrolTarget",
          len(strolls) == 1 and {_title(f) for f in _feeders(strolls[0], "Goal")}
          == {f"Get {PATROL_TARGET_VAR}"}, f"{len(strolls)}")
    windows = [n for n in nodes if {"Min", "Max"} <= _ins(n)
               and _close(_num(n, "Min"), agro.patrol_repick_min_s)
               and _close(_num(n, "Max"), agro.patrol_repick_max_s)]
    check(f"{tag}: a new point every {agro.patrol_repick_min_s:.0f}-"
          f"{agro.patrol_repick_max_s:.0f} s", len(windows) == 1)

    # --- the senses ----------------------------------------------------------
    # Sight, touch and the melee swing all measure pawn-to-player, so each is
    # looked for among those limits (the settings check keeps them distinct).
    reach = sorted(_limits(nodes, "Get Actor Location", "Get Actor Location"))
    check(f"{tag}: sees {agro.vision_range_cm / 100:.0f} m",
          any(_close(x, agro.vision_range_cm) for x in reach), f"{reach}")
    cone = math.cos(math.radians(agro.vision_half_angle_deg))
    check(f"{tag}: ...{agro.vision_half_angle_deg:.0f} degrees either side of its facing",
          len(_with_literal(_titled(nodes, "float >= float"), "B", cone)) == 1, f"cos {cone:.4f}")
    los = _titled(nodes, "LineOfSightTo")
    check(f"{tag}: ...and not through a tree (line of sight to the player)",
          len(los) == 1 and {_title(f) for f in _feeders(los[0], "Other")}
          == {"GetPlayerPawn"})
    check(f"{tag}: feels the player within {agro.touch_range_cm:.0f} cm",
          any(_close(x, agro.touch_range_cm) for x in reach), f"{reach}")
    check(f"{tag}: hears at {agro.hearing_scale}x a noise's own reach, "
          f"all round and down the cone",
          len(_with_literal(_titled(nodes, "float * float"), "B",
                            agro.hearing_scale)) == 2)
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


def run():
    check_settings()
    check_controller(AI_BP_PATH, agro_for(NPC_VARIANTS[0].key))
    for variant in NPC_VARIANTS:
        check_controller(variant.ai_blueprint, agro_for(variant.key))
