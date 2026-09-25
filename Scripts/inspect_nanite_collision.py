import unreal

# 1. Inspect Material properties for Nanite
mat = unreal.EditorAssetSubsystem().load_asset("/Game/Forest/Materials/M_Forest_Grass.M_Forest_Grass")
nanite_props = [p for p in dir(mat) if "nanite" in p.lower()]
unreal.log_warning(f"Material Nanite properties in dir: {nanite_props}")

# Check all boolean editor properties on mat
props = [p for p in ["b_used_with_nanite", "used_with_nanite", "nanite_override"] if hasattr(mat, p)]
unreal.log_warning(f"Has attrs: {props}")

# 2. Inspect StaticMesh Nanite and Collision settings
mesh = unreal.EditorAssetSubsystem().load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if mesh:
    nanite_settings = mesh.get_editor_property("nanite_settings")
    unreal.log_warning(f"Nanite settings: {nanite_settings}")
    if nanite_settings:
        unreal.log_warning(f"Nanite enabled: {nanite_settings.get_editor_property('enabled')}")

    body_setup = mesh.get_editor_property("body_setup")
    unreal.log_warning(f"BodySetup: {body_setup}")
    if body_setup:
        unreal.log_warning(f"Collision trace flag: {body_setup.get_editor_property('collision_trace_flag')}")

# Check EditorStaticMeshLibrary
unreal.log_warning(f"EditorStaticMeshLibrary exists: {hasattr(unreal, 'EditorStaticMeshLibrary')}")
if hasattr(unreal, "EditorStaticMeshLibrary"):
    methods = [m for m in dir(unreal.EditorStaticMeshLibrary) if not m.startswith("_")]
    unreal.log_warning(f"EditorStaticMeshLibrary methods: {methods}")
