import unreal

level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Find or create PostProcessVolume
pp_actor = None
for a in editor_actor_sub.get_all_level_actors():
    if isinstance(a, unreal.PostProcessVolume):
        pp_actor = a
        break

if not pp_actor:
    pp_actor = editor_actor_sub.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    pp_actor.set_actor_label("PostProcessVolume_Forest")

pp_actor.set_editor_property("unbound", True)
settings = pp_actor.get_editor_property("settings")

# Configure balanced exposure settings
settings.set_editor_property("override_auto_exposure_method", True)
settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
settings.set_editor_property("override_auto_exposure_min_brightness", True)
settings.set_editor_property("auto_exposure_min_brightness", 0.5)
settings.set_editor_property("override_auto_exposure_max_brightness", True)
settings.set_editor_property("auto_exposure_max_brightness", 2.0)
settings.set_editor_property("override_auto_exposure_bias", True)
settings.set_editor_property("auto_exposure_bias", 0.0)

pp_actor.set_editor_property("settings", settings)

# Adjust DirectionalLight to balanced physical lux (10.0 or 20.0 for standard or 10000 lux)
for a in editor_actor_sub.get_all_level_actors():
    if isinstance(a, unreal.DirectionalLight):
        comp = a.get_component_by_class(unreal.DirectionalLightComponent)
        if comp:
            comp.set_editor_property("intensity", 10.0)
            comp.set_editor_property("light_source_angle", 0.5)
            comp.set_editor_property("atmosphere_sun_light", True)
            comp.set_editor_property("atmosphere_sun_light_index", 0)
            comp.set_editor_property("cast_shadows", True)
            unreal.log_warning("[AGY] Adjusted DirectionalLight intensity to 10.0!")

level_editor_sub.save_current_level()
unreal.log_warning("[AGY] PostProcessVolume configured and Lvl_Forest saved!")
