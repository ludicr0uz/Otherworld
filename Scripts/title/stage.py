"""build_title_level.py's steps: the floor, the trees (title/forest.py picks
them), the night (forest_generator/lighting.py has its numbers), the camera
and the PlayerStart; title/paths.py has the stage's own numbers. The level
is made if missing, and the stage's own actors (by label) are replaced, so
the build is a rebuild."""

import unreal

from forest_generator.lighting import get_preset
from forest_import import trees as trees_import
from title import forest
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


def _must_load(path):
    asset = _assets().load_asset(path)
    if asset is None:
        raise RuntimeError(f"{path} is missing")
    return asset


def open_level():
    """The level, loaded or made, with none of the stage's actors in it."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if _assets().does_asset_exist(P.TITLE_LEVEL):
        if not les.load_level(P.TITLE_LEVEL):
            raise RuntimeError(f"could not load {P.TITLE_LEVEL}")
        stale = [a for a in _actors().get_all_level_actors()
                 if a.get_actor_label() in P.LABELS + P.RETIRED_LABELS
                 or a.get_actor_label().startswith(P.TREE_LABEL_PREFIX)]
        if stale:
            _actors().destroy_actors(stale)
        unreal.log_warning(f"{_LOG} {P.TITLE_LEVEL}: loaded, {len(stale)} stage actor(s) replaced")
    else:
        if not les.new_level(P.TITLE_LEVEL):
            raise RuntimeError(f"could not create {P.TITLE_LEVEL}")
        unreal.log_warning(f"{_LOG} {P.TITLE_LEVEL}: created")


def place_floor():
    mesh, material = _must_load(P.FLOOR_MESH), _must_load(P.FLOOR_MATERIAL)
    floor = _spawn(unreal.StaticMeshActor, (0.0, 0.0, P.FLOOR_Z), (0.0, 0.0, 0.0), P.FLOOR_LABEL)
    smc = floor.get_component_by_class(unreal.StaticMeshComponent)
    smc.set_mobility(unreal.ComponentMobility.STATIC)
    smc.set_static_mesh(mesh)
    smc.set_material(0, material)
    smc.set_collision_profile_name("BlockAll")
    smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    floor.set_actor_scale3d(unreal.Vector(*P.FLOOR_SCALE))
    return floor


def plant_trees():
    """The play level's middle trees, in cells as any level's are, from the
    LOD build (forest_generator/tree_lods.py names this level)."""
    placements = forest.trees()
    planted, _cells = trees_import.plant_trees(
        placements, forest.configs(), _actors(), _assets(), P.TITLE_LEVEL_NAME)
    if planted != len(placements):
        raise RuntimeError(f"planted {planted} of {len(placements)} trees")
    return planted


def _place_moon(cfg):
    moon = _spawn(unreal.DirectionalLight, (0.0, 0.0, 5000.0),
                  (cfg["pitch"], cfg["yaw"], 0.0), P.MOON_LABEL)
    comp = moon.get_component_by_class(unreal.DirectionalLightComponent)
    comp.set_editor_property("intensity", cfg["intensity"])
    red, green, blue = cfg["color"]
    comp.set_editor_property("light_color", unreal.Color(r=red, g=green, b=blue, a=255))
    comp.set_editor_property("cast_shadows", cfg["cast_shadows"])
    comp.set_editor_property("dynamic_shadow_distance_movable_light", cfg["shadow_distance_cm"])
    comp.set_editor_property("atmosphere_sun_light", True)
    comp.set_editor_property("atmosphere_sun_light_index", 0)
    return moon


def _place_sky(sky_cfg):
    """The starfield dome and the sky light that captures it: the stars are
    the stage's ambient light, as they are the forest's."""
    _spawn(unreal.SkyAtmosphere, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), P.SKY_ATMOSPHERE_LABEL)
    dome = _spawn(unreal.StaticMeshActor, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), P.SKY_SPHERE_LABEL)
    smc = dome.get_component_by_class(unreal.StaticMeshComponent)
    smc.set_static_mesh(_must_load(P.SKY_SPHERE_MESH))
    smc.set_material(0, _must_load(P.SKY_SPHERE_MATERIAL))
    smc.set_editor_property("relative_scale3d", unreal.Vector(*[P.SKY_SPHERE_SCALE] * 3))
    smc.set_collision_profile_name("NoCollision")
    smc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    smc.set_editor_property("cast_shadow", False)
    sky = _spawn(unreal.SkyLight, (0.0, 0.0, 5000.0), (0.0, 0.0, 0.0), P.SKY_LIGHT_LABEL)
    comp = sky.get_component_by_class(unreal.SkyLightComponent)
    comp.set_editor_property("intensity", sky_cfg["intensity"])
    comp.set_editor_property("real_time_capture", sky_cfg["real_time_capture"])


def place_lights():
    """The forest's night: the moon, the starfield and its sky light, the
    fog, and the night's exposure range."""
    night = get_preset(P.NIGHT_PRESET)
    _place_moon(night["sun"])
    _place_sky(night["sky_light"])
    fog_cfg = night["fog"]
    fog = _spawn(unreal.ExponentialHeightFog, (0.0, 0.0, 500.0), (0.0, 0.0, 0.0), P.FOG_LABEL)
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("enable_volumetric_fog", fog_cfg["enable_volumetric"])
    fc.set_fog_density(fog_cfg["density"])
    fc.set_fog_inscattering_color(unreal.LinearColor(*fog_cfg["inscattering_color"], 1.0))
    fc.set_editor_property("volumetric_fog_extinction_scale",
                           fog_cfg["volumetric_extinction_scale"])
    pp_cfg = night["post_process"]
    ppv = _spawn(unreal.PostProcessVolume, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
                 P.POST_PROCESS_LABEL)
    ppv.set_editor_property("unbound", True)
    settings = ppv.get_editor_property("settings")
    # A setting without its override flag is not applied at all.
    for flag in P.EXPOSURE_OVERRIDES:
        settings.set_editor_property(flag, True)
    settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
    for key in P.EXPOSURE_KEYS:
        settings.set_editor_property(key, pp_cfg[key])
    ppv.set_editor_property("settings", settings)


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
