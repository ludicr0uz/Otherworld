import unreal

world = unreal.EditorLoadingAndSavingUtils.load_map("/Game/Maps/Lvl_Forest.umap")
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

out = []
actors = editor_actor_sub.get_all_level_actors()
for a in actors:
    cls = a.get_class().get_name()
    name = a.get_name()
    label = a.get_actor_label()
    
    if isinstance(a, unreal.DirectionalLight):
        comp = a.directional_light_component
        out.append(f"DirectionalLight: Intensity={comp.get_editor_property('intensity')}, LightColor={comp.get_editor_property('light_color')}, Temp={comp.get_editor_property('temperature')}, UseTemp={comp.get_editor_property('use_temperature')}")
    elif isinstance(a, unreal.SkyLight):
        comp = a.sky_light_component
        out.append(f"SkyLight: Intensity={comp.get_editor_property('intensity')}, LightColor={comp.get_editor_property('light_color')}, RealTimeCapture={comp.get_editor_property('real_time_capture')}")
    elif isinstance(a, unreal.ExponentialHeightFog):
        comp = a.component
        out.append(f"ExponentialHeightFog: Density={comp.get_editor_property('fog_density')}, InscatteringColor={comp.get_editor_property('fog_inscattering_luminance')}")
    elif isinstance(a, unreal.PostProcessVolume):
        settings = a.get_editor_property("settings")
        out.append(f"PostProcessVolume: ExposureMin={settings.get_editor_property('auto_exposure_min_brightness')}, ExposureMax={settings.get_editor_property('auto_exposure_max_brightness')}, Method={settings.get_editor_property('auto_exposure_method')}, Bias={settings.get_editor_property('auto_exposure_bias')}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/lighting_inspect.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning("Done inspecting lighting")
