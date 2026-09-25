import unreal

# Check classes and methods related to ISM / HISM / InstancedStaticMeshActor
for name in dir(unreal):
    if "Instanced" in name or "HISM" in name or "Foliage" in name:
        unreal.log_warning(f"Found class: {name}")

# Check SubobjectDataSubsystem or EditorActorSubsystem or InstancedStaticMeshActor
unreal.log_warning(f"InstancedStaticMeshActor in unreal: {hasattr(unreal, 'InstancedStaticMeshActor')}")
if hasattr(unreal, 'InstancedStaticMeshActor'):
    unreal.log_warning(f"InstancedStaticMeshActor dir: {[m for m in dir(unreal.InstancedStaticMeshActor) if not m.startswith('_')]}")

# Check how to add component via SubobjectDataSubsystem if it exists
unreal.log_warning(f"SubobjectDataSubsystem in unreal: {hasattr(unreal, 'SubobjectDataSubsystem')}")
