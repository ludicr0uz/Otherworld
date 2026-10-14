"""Give a planted level's grass cells the materials its specs name, without
planting it again.

    python3 Scripts/dev/uepy.py Scripts/recolour_grass.py

A level that only gains the dark grass's colour (forest_generator/grass_look.py,
``DARK_GRASS_LEVELS`` without ``PATCH_GRASS_LEVELS``) keeps every clump where it
is, so a re-import would plant a million instances again, and put the forage,
the clothing, the sky and the sound beds back after it, to change one material
per cell. This sets the override the import would have set (forest_import/
grass.py ``spawn_cell``) on each grass cell and saves the level; the level's
generated import and verify scripts, regenerated from the same specs, then
describe it. A cell that already draws its spec's materials is left alone, and
a level with nothing to change is not saved.
"""

import unreal

from forest_generator.grass_cells import GRASS_TIERS, spec_of_label, tier_spec
from forest_generator.grass_look import grass_specs_for
from forest_import import grass_look as grass_look_import
from world import level_save

MAPS = "/Game/Maps"


def _log(msg):
    unreal.log(f"[GEN] {msg}")


def _must_load(path):
    asset = unreal.load_asset(path)
    if asset is None:
        raise RuntimeError(f"cannot load {path}")
    return asset


def recolour(level_name):
    """Open ``level_name``, set its grass cells' materials and save it.
    Returns how many cells changed."""
    grass_look_import.ensure_grass_look()
    # A cell's label starts with its species and tier (grass_cells.cell_label).
    wanted = {tier_spec(spec.name, tier): [_must_load(p) for p in spec.material_paths]
              for spec in grass_specs_for(level_name)
              for tier in range(len(GRASS_TIERS))}
    level_path = f"{MAPS}/{level_name}"
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.load_level(level_path):
        raise RuntimeError(f"cannot open {level_path}")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    cells = changed = 0
    for actor in actors:
        label = actor.get_actor_label()
        # The bushes' cells share the grass's tag: tell them by the label.
        if not (label.startswith("HISM_Grass") and "__" in label):
            continue
        materials = wanted.get(spec_of_label(label))
        root = actor.get_editor_property("root_component")
        if materials is None or root is None:
            raise RuntimeError(f"{label}: not a cell of this level's specs")
        cells += 1
        drawn = [m for m in root.get_editor_property("override_materials") if m]
        if drawn == materials:
            continue
        root.set_editor_property("override_materials", [])
        for index, material in enumerate(materials):
            root.set_material(index, material)
        changed += 1
    if not cells:
        raise RuntimeError(f"{level_name} has no grass cells")
    if changed:
        level_save.save_level(level_path)
    _log(f"{level_name}: {changed} of {cells} grass cells recoloured"
         f"{'' if changed else ' (not saved)'}")
    return changed
