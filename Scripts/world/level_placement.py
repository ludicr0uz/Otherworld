"""Putting BP_DayNightCycle into a generated level, inside the editor.

Two edits per level, both idempotent:
  * every actor of the level's static sky rig -- directional lights, sky
    lights, height fogs, volumetric clouds and the SM_SkySphere dome -- gets
    STATIC_SKY_TAG. Nothing is deleted: the rig stays exactly as the generator
    built and verify_<Level>.py checks it, and the cycle removes it at
    BeginPlay. The level's PostProcessVolume stays too; the cycle's two grades
    outrank it.
  * any previous cycle actor (DAY_NIGHT_TAG) is removed and one is placed at
    the origin, where the dome is centred.

import_<Level>.py rebuilds a level from nothing, so re-run build_day_night.py
after it (as with place_forage.py).
"""

import unreal

from combat.graph import _log
from world.paths import DAY_NIGHT_CLASS_PATH, DAY_NIGHT_TAG, SKY_SPHERE_MESH_PATH, STATIC_SKY_TAG

RIG_CLASSES = (unreal.DirectionalLight, unreal.SkyLight, unreal.ExponentialHeightFog,
               unreal.VolumetricCloud)
CYCLE_LABEL = "DayNightCycle"


def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def is_static_sky(actor):
    """Is this actor part of a level's generated sky rig?"""
    if isinstance(actor, RIG_CLASSES):
        return True
    if isinstance(actor, unreal.StaticMeshActor):
        mesh = actor.static_mesh_component.get_editor_property("static_mesh")
        return mesh is not None and mesh.get_path_name() == SKY_SPHERE_MESH_PATH
    return False


def _tag(actor, tag):
    tags = list(actor.get_editor_property("tags"))
    if unreal.Name(tag) not in tags:
        actor.set_editor_property("tags", tags + [unreal.Name(tag)])


def place_day_night(level_path):
    """Tag the rig, replace the cycle actor, save. Returns the rig's labels."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.load_level(level_path):
        raise RuntimeError(f"could not load {level_path}")
    sub = _actors()
    actors = sub.get_all_level_actors()
    stale = [a for a in actors if a.actor_has_tag(DAY_NIGHT_TAG)]
    if stale:
        sub.destroy_actors(stale)
    rig = [a for a in actors if a not in stale and is_static_sky(a)]
    for a in rig:
        _tag(a, STATIC_SKY_TAG)

    cls = unreal.load_class(None, DAY_NIGHT_CLASS_PATH)
    if cls is None:
        raise RuntimeError(f"no class at {DAY_NIGHT_CLASS_PATH}; build it first")
    cycle = sub.spawn_actor_from_class(cls, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    cycle.set_actor_label(CYCLE_LABEL)
    cycle.set_editor_property("tags", [unreal.Name(DAY_NIGHT_TAG)])

    if not les.save_current_level():
        raise RuntimeError(f"could not save {level_path}")
    labels = sorted(a.get_actor_label() for a in rig)
    _log(f"{level_path}: day/night cycle placed; static sky tagged: {labels}")
    return labels


def day_night_in_level(level_path):
    """(cycle actors, rig actors, rig actors missing the tag) in a saved level."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.load_level(level_path):
        raise RuntimeError(f"could not load {level_path}")
    actors = _actors().get_all_level_actors()
    cycles = [a for a in actors if a.actor_has_tag(DAY_NIGHT_TAG)]
    rig = [a for a in actors if is_static_sky(a)]
    untagged = [a.get_actor_label() for a in rig if not a.actor_has_tag(STATIC_SKY_TAG)]
    return cycles, rig, untagged
