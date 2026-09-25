import unreal

# Query console variable help for EyeAdaptation and CachedLightingPreExposure
cvar_name = "r.EyeAdaptation.CachedLightingPreExposure"
# Let's inspect console variables or execute console command
unreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_editor_world(), f"{cvar_name} ?")
