import unreal

editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Load ThirdPersonMap to see standard working lighting settings
level_path = "/Game/ThirdPerson/Maps/ThirdPersonMap.umap"
world = unreal.EditorLoadingAndSavingUtils.load_map(level_path)

out = ["=== ThirdPersonMap Lighting Settings ==="]
actors = editor_actor_sub.get_all_level_actors()

for a in actors:
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    if isinstance(a, unreal.DirectionalLight):
        comp = a.get_component_by_class(unreal.DirectionalLightComponent)
        if comp:
            out.append(f"DirectionalLight: Intensity={comp.get_editor_property('intensity')}, LightColor={comp.get_editor_property('light_color')}, AtmosphereSunLight={comp.get_editor_property('atmosphere_sun_light') if hasattr(comp, 'atmosphere_sun_light') else 'N/A'}")
    elif isinstance(a, unreal.SkyLight):
        comp = a.get_component_by_class(unreal.SkyLightComponent)
        if comp:
            out.append(f"SkyLight: Intensity={comp.get_editor_property('intensity')}, RealTimeCapture={comp.get_editor_property('real_time_capture')}")
    elif isinstance(a, unreal.PostProcessVolume):
        settings = a.get_editor_property("settings")
        out.append(f"PostProcessVolume: Unbound={a.get_editor_property('unbound')}")
        out.append(f"  ExposureMethod={settings.get_editor_property('auto_exposure_method')}")
        out.append(f"  MinEV100={settings.get_editor_property('auto_exposure_min_brightness')}")
        out.append(f"  MaxEV100={settings.get_editor_property('auto_exposure_max_brightness')}")
        out.append(f"  ExposureBias={settings.get_editor_property('auto_exposure_bias')}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/tp_lighting_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning("ThirdPersonMap inspection done!")
