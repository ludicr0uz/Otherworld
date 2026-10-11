"""build_title_level.py's steps, each one actor of the stage (title/paths.py
has the numbers). The level is made if missing, and the stage's own actors
(by label) are replaced, so the build is a rebuild."""

import unreal

from combat.materials import build_flat_material
from title import paths as P

_LOG = "[GEN]"


def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _assets():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _rotator(pyr):
    """A (pitch, yaw, roll) triple as the engine's Rotator, whose constructor
    takes (roll, pitch, yaw)."""
    pitch, yaw, roll = pyr
    return unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw)


def _spawn(cls, location, rotation, label):
    actor = _actors().spawn_actor_from_class(
        cls, unreal.Vector(*location), _rotator(rotation))
    if actor is None:
        raise RuntimeError(f"could not spawn {cls} as {label}")
    actor.set_actor_label(label)
    return actor


def _colour(rgb):
    return unreal.LinearColor(*rgb, 1.0)


def open_level():
    """The level, loaded or made, with none of the stage's actors in it."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if _assets().does_asset_exist(P.TITLE_LEVEL):
        if not les.load_level(P.TITLE_LEVEL):
            raise RuntimeError(f"could not load {P.TITLE_LEVEL}")
        stale = [a for a in _actors().get_all_level_actors()
                 if a.get_actor_label() in P.LABELS]
        if stale:
            _actors().destroy_actors(stale)
        unreal.log_warning(f"{_LOG} {P.TITLE_LEVEL}: loaded, {len(stale)} stage actor(s) replaced")
    else:
        if not les.new_level(P.TITLE_LEVEL):
            raise RuntimeError(f"could not create {P.TITLE_LEVEL}")
        unreal.log_warning(f"{_LOG} {P.TITLE_LEVEL}: created")


def place_floor():
    mesh = _assets().load_asset(P.FLOOR_MESH)
    material = build_flat_material(P.FLOOR_MATERIAL, P.FLOOR_COLOUR, P.FLOOR_METALLIC,
                                   P.FLOOR_ROUGHNESS)
    if not mesh or not material:
        raise RuntimeError(f"{P.FLOOR_MESH} or {P.FLOOR_MATERIAL} is missing")
    floor = _spawn(unreal.StaticMeshActor, (0.0, 0.0, P.FLOOR_Z), (0.0, 0.0, 0.0), P.FLOOR_LABEL)
    smc = floor.get_component_by_class(unreal.StaticMeshComponent)
    smc.set_mobility(unreal.ComponentMobility.STATIC)
    smc.set_static_mesh(mesh)
    smc.set_material(0, material)
    smc.set_collision_profile_name("BlockAll")
    smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    floor.set_actor_scale3d(unreal.Vector(*P.FLOOR_SCALE))
    return floor


def _directional(label, spec, shadows):
    light = _spawn(unreal.DirectionalLight, (0.0, 0.0, 300.0), spec["rotation"], label)
    comp = light.get_component_by_class(unreal.DirectionalLightComponent)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.set_intensity(spec["intensity"])
    comp.set_light_color(_colour(spec["color"]))
    comp.set_cast_shadows(shadows)
    return light


def place_lights():
    """The key light with shadows, the fill without, the fog, and a fixed
    exposure."""
    key = _directional(P.KEY_LIGHT_LABEL, P.KEY_LIGHT, True)
    fill = _directional(P.FILL_LIGHT_LABEL, P.FILL_LIGHT, False)
    fog = _spawn(unreal.ExponentialHeightFog, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), P.FOG_LABEL)
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_fog_density(P.FOG["density"])
    fc.set_fog_height_falloff(P.FOG["height_falloff"])
    fc.set_fog_inscattering_color(_colour(P.FOG["luminance"]))
    ppv = _spawn(unreal.PostProcessVolume, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
                 P.POST_PROCESS_LABEL)
    ppv.set_editor_property("unbound", True)
    settings = ppv.get_editor_property("settings")
    # A setting without its override flag is not applied at all.
    for flag in P.EXPOSURE_OVERRIDES:
        settings.set_editor_property(flag, True)
    settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
    settings.set_editor_property("auto_exposure_min_brightness", P.EXPOSURE["min_brightness"])
    settings.set_editor_property("auto_exposure_max_brightness", P.EXPOSURE["max_brightness"])
    settings.set_editor_property("auto_exposure_bias", P.EXPOSURE["bias"])
    ppv.set_editor_property("settings", settings)
    return key, fill, fog, ppv


def place_camera():
    """The camera the title is seen through: the player's view target as
    soon as the level is up (AutoActivateForPlayer), in front of the figure."""
    camera = _spawn(unreal.CameraActor, P.CAMERA, P.CAMERA_ROTATION, P.CAMERA_LABEL)
    camera.set_editor_property("auto_activate_for_player", unreal.AutoReceiveInput.PLAYER0)
    cc = camera.get_component_by_class(unreal.CameraComponent)
    cc.set_field_of_view(P.CAMERA_FOV)
    cc.set_constraint_aspect_ratio(False)
    return camera


def place_player_start():
    return _spawn(unreal.PlayerStart, P.PLAYER_START, (0.0, P.PLAYER_START_YAW, 0.0),
                  P.PLAYER_START_LABEL)


def save():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.save_current_level():
        raise RuntimeError(f"could not save {P.TITLE_LEVEL}")
    unreal.log_warning(f"{_LOG} {P.TITLE_LEVEL}: saved")
