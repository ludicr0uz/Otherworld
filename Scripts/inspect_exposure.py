import unreal

# We can find console variable via Unreal's IConsoleManager or test executing console command
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

# Let's inspect DirectionalLight and PostProcessVolume settings
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in editor_actor_sub.get_all_level_actors():
    if isinstance(a, unreal.DirectionalLight):
        comp = a.get_component_by_class(unreal.DirectionalLightComponent)
        if comp:
            unreal.log_warning(f"DirectionalLight intensity: {comp.get_editor_property('intensity')}, light_source_angle: {comp.get_editor_property('light_source_angle')}")
    elif isinstance(a, unreal.PostProcessVolume):
        settings = a.get_editor_property("settings")
        unreal.log_warning(f"PostProcessVolume: {a.get_actor_label()}")
