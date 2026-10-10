"""The garments build_clothing.py scattered through each generated level."""

import math

import unreal

from combat.verify.common import check
from clothing.scatter import SCATTER_KINDS, TRUNK_CLEAR_CM, garment_count
from clothing.scatter_level import scatter_levels, scattered_in_level
from clothing.specs import GARMENTS
from survival.forage_level import _trunks


def run():
    levels = scatter_levels()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    was_open = world.get_path_name().split(".")[0] if world else None
    kind_of = {g.class_path: g.display for g in GARMENTS}
    for level in levels:
        placed = scattered_in_level(level)
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        terrain = next((a for a in actors if a.get_actor_label().endswith("_Terrain")), None)
        _origin, extent = terrain.get_actor_bounds(False)
        want = garment_count(2.0 * extent.x, 2.0 * extent.y)
        kinds = {}
        for a in placed:
            kind = kind_of.get(a.get_class().get_path_name(), "?")
            kinds[kind] = kinds.get(kind, 0) + 1
        check(f"{level}: {want} garments scattered (tag OW_Clothing), one a hectare",
              len(placed) == want, str(kinds))
        check(f"{level}: each is a jacket, pants or boots, every kind there is room for",
              set(kinds) == set(SCATTER_KINDS[:want]), str(kinds))
        loose = [a.get_actor_label() for a in placed
                 if not a.get_editor_property("Dropped")]
        check(f"{level}: every scattered garment can be picked up (Dropped)",
              not loose, str(loose[:5]))
        trunks = _trunks(actors)
        inside = [a.get_actor_label() for a in placed
                  if any(math.hypot(a.get_actor_location().x - tx,
                                    a.get_actor_location().y - ty) < TRUNK_CLEAR_CM - 1.0
                         for tx, ty in trunks)]
        check(f"{level}: no scattered garment lies inside a trunk", not inside,
              str(inside[:5]))
    if was_open and levels and was_open != levels[-1]:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(was_open)
