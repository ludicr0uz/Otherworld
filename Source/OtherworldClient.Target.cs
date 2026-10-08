using UnrealBuildTool;

public class OtherworldClientTarget : TargetRules
{
	public OtherworldClientTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		Type = TargetType.Client;
		ExtraModuleNames.Add("Otherworld");
		// The inventory's record is sent when it is marked, not compared every
		// update (OtherworldInventoryRecord.h). An editor target has this already.
		bWithPushModel = true;
	}
}
