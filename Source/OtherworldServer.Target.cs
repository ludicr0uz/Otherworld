using UnrealBuildTool;

public class OtherworldServerTarget : TargetRules
{
	public OtherworldServerTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		Type = TargetType.Server;
		ExtraModuleNames.Add("Otherworld");
	}
}
