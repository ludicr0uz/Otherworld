using UnrealBuildTool;

public class OtherworldClientTarget : TargetRules
{
	public OtherworldClientTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		Type = TargetType.Client;
		ExtraModuleNames.Add("Otherworld");
	}
}
