import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] Calibrating Daylight Forest Lighting & Exposure...")
unreal.log_warning("==================================================")

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

actors = editor_actor_sub.get_all_level_actors()
for a in actors:
    lbl = a.get_actor_label()
    
    # 1. Post Process Volume - Standard Vibrant Daylight Exposure
    if isinstance(a, unreal.PostProcessVolume) or "PostProcess" in lbl:
        a.set_editor_property("unbound", True)
        settings = a.get_editor_property("settings")
        settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
        # Relative luminance scale for non-extended luminance range:
        settings.set_editor_property("auto_exposure_min_brightness", 0.03)
        settings.set_editor_property("auto_exposure_max_brightness", 2.0)
        settings.set_editor_property("auto_exposure_bias", 0.6) # +0.6 EV boost for bright, lush woodland
        settings.set_editor_property("bloom_intensity", 0.675)
        settings.set_editor_property("vignette_intensity", 0.25)
        a.set_editor_property("settings", settings)
        unreal.log_warning("[AGY] PostProcessVolume calibrated: MinBrightness=0.03, MaxBrightness=2.0, Bias=+0.6")
    
    # 2. Directional Light (Sun)
    elif isinstance(a, unreal.DirectionalLight) or "DirectionalLight" in lbl:
        comp = a.get_component_by_class(unreal.DirectionalLightComponent)
        if comp:
            comp.set_editor_property("intensity", 10.0) # Bright daytime sunlight
            comp.set_editor_property("light_color", unreal.Color(r=255, g=248, b=232, a=255))
            comp.set_editor_property("cast_shadows", True)
            comp.set_editor_property("dynamic_shadow_distance_movable_light", 20000.0)
            comp.set_editor_property("atmosphere_sun_light", True)
            unreal.log_warning("[AGY] DirectionalLight calibrated: Intensity=10.0 (Daylight Sun)")
    
    # 3. Sky Light (Ambient Fill)
    elif isinstance(a, unreal.SkyLight) or "SkyLight" in lbl:
        comp = a.get_component_by_class(unreal.SkyLightComponent)
        if comp:
            comp.set_editor_property("intensity", 2.0) # Ambient sky illumination
            comp.set_editor_property("light_color", unreal.Color(r=210, g=230, b=255, a=255))
            comp.set_editor_property("real_time_capture", True)
            unreal.log_warning("[AGY] SkyLight calibrated: Intensity=2.0 (Real-time ambient capture)")
    
    # 4. Exponential Height Fog
    elif isinstance(a, unreal.ExponentialHeightFog) or "Fog" in lbl:
        comp = a.get_component_by_class(unreal.ExponentialHeightFogComponent)
        if comp:
            comp.set_editor_property("fog_density", 0.0015)
            comp.set_editor_property("fog_height_falloff", 0.05)
            unreal.log_warning("[AGY] ExponentialHeightFog calibrated: Density=0.0015")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] DAYLIGHT FOREST LIGHTING CALIBRATED & SAVED!")
unreal.log_warning("==================================================")
