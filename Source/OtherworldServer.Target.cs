using UnrealBuildTool;

public class OtherworldServerTarget : TargetRules
{
	public OtherworldServerTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		Type = TargetType.Server;
		ExtraModuleNames.Add("Otherworld");
		// The inventory's record is sent when it is marked, not compared every
		// update (OtherworldInventoryRecord.h). An editor target has this already.
		bWithPushModel = true;
	}
}
