import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

pine_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_PineTree_01.SM_PineTree_01")
oak_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_BroadleafTree_01.SM_BroadleafTree_01")

if pine_mesh:
    unreal.log_warning(f"Pine Mesh Bounds: {pine_mesh.get_bounds()}")
if oak_mesh:
    unreal.log_warning(f"Oak Mesh Bounds: {oak_mesh.get_bounds()}")

# Inspect tree actors in level
tree_actors = [a for a in editor_actor_sub.get_all_level_actors() if "Tree" in a.get_actor_label()]
unreal.log_warning(f"Found {len(tree_actors)} tree actors in level")
for t in tree_actors[:5]:
    unreal.log_warning(f"Tree: {t.get_actor_label()}, Loc: {t.get_actor_location()}, Rot: {t.get_actor_rotation()}, Scale: {t.get_actor_scale3d()}")
