using UnrealBuildTool;

public class OtherworldEditorTarget : TargetRules
{
	public OtherworldEditorTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		Type = TargetType.Editor;
		ExtraModuleNames.Add("Otherworld");
	}
}
