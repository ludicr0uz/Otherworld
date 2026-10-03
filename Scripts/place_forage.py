"""
place_forage.py -- scatter mushrooms and water canteens through the generated
forest levels.

    python3 Scripts/dev/uepy.py Scripts/place_forage.py

Run after build_survival.py (the item classes must exist) and after any
import_<Level>.py, which rebuilds the level from scratch and so drops the
forage with everything else. Idempotent: each run removes the previous forage
(tag OW_Forage) and places it again from the same seed.

This file is only the entry point; the code is survival.forage_placement
(where, pure Python) and survival.forage_level (putting it in the level).
"""

import os
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS)
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("uebp", "combat", "survival")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from survival.forage_level import place_forage                    # noqa: E402

# Every level the generator has produced that also exists as a map. The 1 km
# level takes about a minute to load in a live editor.
LEVELS = sorted(
    f"/Game/Maps/{name}"
    for name in os.listdir(os.path.join(_SCRIPTS, "generated_levels"))
    if unreal.EditorAssetLibrary.does_asset_exist(f"/Game/Maps/{name}"))


def main():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    was_open = world.get_path_name().split(".")[0] if world else None
    for level in LEVELS:
        place_forage(level)
    # Put the editor back where it was, so a live session is not left
    # looking at whichever level happened to be last.
    if was_open and was_open not in ("", LEVELS[-1] if LEVELS else ""):
        les.load_level(was_open)


if __name__ == "__main__":
    main()
