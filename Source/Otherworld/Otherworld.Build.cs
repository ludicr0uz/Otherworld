using UnrealBuildTool;

public class Otherworld : ModuleRules
{
	public Otherworld(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		// Each source compiles by itself: in a unity blob two files' unnamed-namespace
		// helpers of one name (ReadInt, ClassName) collide, and which files share a
		// blob changes whenever a source is added.
		bUseUnity = false;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "NetCore", "ReplicationGraph", "InputCore", "EnhancedInput" });
	}
}
