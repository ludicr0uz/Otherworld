"""Checks for debug mode's sight cone (npc/sight_cone.py), read back off the
saved controllers. Run through Scripts/verify_npc_blueprints.py.

What it proves: the cone is drawn from exactly what the sight sense tests
(the pawn's location and forward vector, TuneSightRange, TuneSightHalfAngle),
every frame, and only in debug mode, with a pawn, and not for a corpse. That
the draw runs in the game is Scripts/probes/probe_sight_cone.py.
"""

import unreal

from combat.game_state import DEBUG_MODE_VAR
from forest_generator.npc_placement import NPC_VARIANTS
from npc.monster_tuning import TUNED_VAR
from npc.paths import (
    AGGRO_VAR, AI_BP_PATH, CORPSE_VAR, SIGHT_CONE_AGGRO_COLOR,
    SIGHT_CONE_PATROL_COLOR, SIGHT_CONE_SIDES, SIGHT_CONE_STAMP_VAR,
    SIGHT_CONE_THICKNESS,
)
from npc.verify import BEL, PIN, _close, _feeders, _ins, _lit, _num, _title, check


def _gates(node):
    """[(condition titles, arm taken)] for each Branch on the one exec path
    back from ``node``, nearest first, and the node the path starts at."""
    out = []
    while True:
        links = PIN.list_connected_pins(BEL.find_execute_pin(node))
        if len(links) != 1:
            return out, node
        arm, node = str(PIN.get_pin_name(links[0])), PIN.get_owning_node(links[0])
        if _title(node) == "Branch":
            out.append((sorted(_title(f) for f in _feeders(node, "Condition")), arm))


def check_sight_cone(path):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag}: exists, for its sight cone", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    cones = [n for n in nodes if {"Origin", "Direction", "AngleWidth"} <= _ins(n)]
    check(f"{tag}: debug mode draws one sight cone", len(cones) == 1, str(len(cones)))
    if len(cones) != 1:
        return
    cone = cones[0]

    def fed(pin):
        return [_title(f) for f in _feeders(cone, pin)]

    sight_range, half = TUNED_VAR["vision_range_cm"], TUNED_VAR["vision_half_angle_deg"]
    check(f"{tag}: ...from the pawn, along the way it faces: the sight sense's own",
          fed("Origin") == ["Get Actor Location"]
          and fed("Direction") == ["GetActorForwardVector"],
          f"{fed('Origin')}, {fed('Direction')}")
    check(f"{tag}: ...{sight_range} long and {half} either side, so the MONSTER "
          f"SETTINGS tab moves it",
          fed("Length") == [f"Get {sight_range}"]
          and fed("AngleWidth") == [f"Get {half}"]
          and fed("AngleHeight") == [f"Get {half}"],
          f"{fed('Length')}, {fed('AngleWidth')}, {fed('AngleHeight')}")
    check(f"{tag}: ...for one frame at a time, so it follows the body",
          _close(_num(cone, "Duration"), 0.0)
          and _close(_num(cone, "NumSides"), SIGHT_CONE_SIDES)
          and _close(_num(cone, "Thickness"), SIGHT_CONE_THICKNESS),
          f"{_lit(cone, 'Duration')} s, {_lit(cone, 'NumSides')} sides")
    tints = _feeders(cone, "LineColor")
    check(f"{tag}: ...in the hunting colour once {AGGRO_VAR}, the patrol colour before",
          len(tints) == 1 and _lit(tints[0], "A") == SIGHT_CONE_AGGRO_COLOR
          and _lit(tints[0], "B") == SIGHT_CONE_PATROL_COLOR
          and [_title(f) for f in _feeders(tints[0], "bPickA")] == [f"Get {AGGRO_VAR}"])

    gates, start = _gates(cone)
    # The cast in between is not a Branch: its exec out is "then" as well.
    check(f"{tag}: it runs off the controller's Tick, behind three nested gates: "
          f"{DEBUG_MODE_VAR}, a pawn, not a {CORPSE_VAR.lower()}",
          _title(start) == "Event Tick"
          and gates == [([f"Get {CORPSE_VAR}"], "else"), (["IsValid"], "then"),
                        ([f"Get {DEBUG_MODE_VAR}"], "then")],
          f"{_title(start)}: {gates}")
    stamps = [n for n in nodes if _title(n) == f"Set {SIGHT_CONE_STAMP_VAR}"]
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check(f"{tag}: each cone drawn stamps {SIGHT_CONE_STAMP_VAR} with the game time",
          len(stamps) == 1
          and [_title(f) for f in _feeders(stamps[0], "execute")] == [_title(cone)]
          and isinstance(cdo.get_editor_property(SIGHT_CONE_STAMP_VAR), float),
          str(len(stamps)))


def run():
    check_sight_cone(AI_BP_PATH)
    for variant in NPC_VARIANTS:
        check_sight_cone(variant.ai_blueprint)
