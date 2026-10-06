using UnrealBuildTool;

public class OtherworldTarget : TargetRules
{
	public OtherworldTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		Type = TargetType.Game;
		ExtraModuleNames.Add("Otherworld");
	}
}
