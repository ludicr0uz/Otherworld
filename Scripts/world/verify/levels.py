"""What build_day_night.py put in each generated level."""

import os

import unreal

from combat.verify.common import check
from world.level_placement import day_night_in_level
from world.paths import DAY_NIGHT_CLASS_PATH

GENERATED = os.path.join(os.path.dirname(__file__), "..", "..", "generated_levels")


def run():
    levels = sorted(f"/Game/Maps/{n}" for n in os.listdir(os.path.abspath(GENERATED))
                    if unreal.EditorAssetLibrary.does_asset_exist(f"/Game/Maps/{n}"))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    was_open = world.get_path_name().split(".")[0] if world else None
    for level in levels:
        cycles, rig, untagged = day_night_in_level(level)
        check(f"{level}: one day/night cycle",
              len(cycles) == 1
              and cycles[0].get_class().get_path_name() == DAY_NIGHT_CLASS_PATH,
              str([c.get_actor_label() for c in cycles]))
        check(f"{level}: the static sky is there to hand over", len(rig) > 0,
              str([a.get_actor_label() for a in rig]))
        check(f"{level}: every piece of the static sky is tagged", not untagged,
              str(untagged))
    if was_open and levels and was_open != levels[-1]:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(was_open)
