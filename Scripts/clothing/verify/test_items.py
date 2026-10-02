"""The test garments in front of the 200 m map's PlayerStart."""

import math

import unreal

from combat.verify.common import check
from clothing.placement import AHEAD_CM, TEST_LEVEL, test_clothing_in_level
from clothing.specs import GARMENTS


def run():
    placed = test_clothing_in_level(TEST_LEVEL)
    classes = sorted(a.get_class().get_path_name() for a in placed)
    want = sorted(g.class_path for g in GARMENTS)
    check(f"{TEST_LEVEL} has one test garment of each kind", classes == want,
          f"{len(placed)} placed: {classes}")
    start = next((a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                  .get_all_level_actors() if isinstance(a, unreal.PlayerStart)), None)
    if start is None or not placed:
        check("the PlayerStart and the garments are there", False)
        return
    at, yaw = start.get_actor_location(), math.radians(start.get_actor_rotation().yaw)
    ahead = []
    for a in placed:
        p = a.get_actor_location()
        dx, dy = p.x - at.x, p.y - at.y
        ahead.append(dx * math.cos(yaw) + dy * math.sin(yaw))
    check(f"every test garment lies {AHEAD_CM / 100:.0f} m in front of the PlayerStart",
          all(abs(d - AHEAD_CM) < 1.0 for d in ahead), str([round(d) for d in ahead]))
    check("every test garment is on the ground near the PlayerStart's height",
          all(abs(a.get_actor_location().z - at.z) < 300.0 for a in placed),
          str([round(a.get_actor_location().z) for a in placed]))
