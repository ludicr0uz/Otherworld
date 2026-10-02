"""
build_clothing.py -- the garments, and the test ones on the 200 m map.

Run inside the editor, AFTER build_weapons_and_combat.py (a garment is a
BP_WeaponItem, and the weapon component is what wears it):
    python3 Scripts/dev/uepy.py Scripts/build_clothing.py

This file is only the entry point; the code is the ``clothing`` package next
to it (Scripts/clothing/__init__.py is the map). Checked by verify_clothing.py.

/Game/Clothing
  BP_Hat, BP_Glasses, BP_Shirt, BP_Jacket, BP_Gloves, BP_Pants, BP_Boots,
  BP_Backpack                    children of BP_WeaponItem, worn by the fire key
  Materials/M_Cloth_<Garment>    their flat colours
and lays one of each 3 m in front of Lvl_Forest_200m's PlayerStart.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("combat", "survival", "clothing", "item_icons")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from combat.graph import _log                                     # noqa: E402
from clothing.items import build_garments                         # noqa: E402
from clothing.placement import TEST_LEVEL, place_test_clothing    # noqa: E402


def main():
    built = build_garments()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    was_open = world.get_path_name().split(".")[0] if world else None
    if unreal.EditorAssetLibrary.does_asset_exist(TEST_LEVEL):
        place_test_clothing(TEST_LEVEL)
    else:
        _log(f"note: {TEST_LEVEL} does not exist -- no test garments placed")
    # Put the editor back where it was, as place_forage.py does.
    if was_open and was_open != TEST_LEVEL:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(was_open)
    _log(f"done -- {', '.join(built)}")


if __name__ == "__main__":
    main()
