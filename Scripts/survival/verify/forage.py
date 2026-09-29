"""What place_forage.py put in each generated level."""

import os

import unreal

from combat.verify.common import check
from survival.forage_level import forage_in_level
from survival.paths import CANTEEN_CLASS_PATH, MUSHROOM_CLASS_PATH

GENERATED = os.path.join(os.path.dirname(__file__), "..", "..", "generated_levels")


def run():
    levels = sorted(f"/Game/Maps/{n}" for n in os.listdir(os.path.abspath(GENERATED))
                    if unreal.EditorAssetLibrary.does_asset_exist(f"/Game/Maps/{n}"))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    was_open = world.get_path_name().split(".")[0] if world else None
    for level in levels:
        placed = forage_in_level(level)
        kinds = {}
        for a in placed:
            path = a.get_class().get_path_name()
            kinds[path] = kinds.get(path, 0) + 1
        check(f"{level}: mushrooms placed", kinds.get(MUSHROOM_CLASS_PATH, 0) > 0,
              str(kinds))
        check(f"{level}: canteens placed", kinds.get(CANTEEN_CLASS_PATH, 0) > 0,
              str(kinds))
        loose = [a.get_actor_label() for a in placed
                 if not a.get_editor_property("Dropped")]
        check(f"{level}: every piece can be picked up (Dropped)", not loose, str(loose[:5]))
    if was_open and levels and was_open != levels[-1]:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(was_open)
