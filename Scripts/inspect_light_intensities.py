import unreal

level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

for a in editor_actor_sub.get_all_level_actors():
    if isinstance(a, unreal.DirectionalLight):
        comp = a.get_component_by_class(unreal.DirectionalLightComponent)
        if comp:
            unreal.log_warning(f"DirectionalLight: intensity={comp.get_editor_property('intensity')}")
            # If intensity is default 10.0 or 75000 lux, let's check
    elif isinstance(a, unreal.SkyLight):
        comp = a.get_component_by_class(unreal.SkyLightComponent)
        if comp:
            unreal.log_warning(f"SkyLight: intensity={comp.get_editor_property('intensity')}")
    elif isinstance(a, unreal.PostProcessVolume):
        unreal.log_warning(f"PostProcessVolume: {a.get_actor_label()}")
