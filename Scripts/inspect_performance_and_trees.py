import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

# 1. Inspect tree static meshes
for sm_name in ["tree_small_02", "pine_sapling_small_a", "SM_tree_stump_01", "SM_rock_07"]:
    assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)
    matching = [a for a in assets if sm_name in a and ("StaticMeshes" in a or "SM_" in a)]
    if matching:
        mesh = editor_asset_sub.load_asset(matching[0])
        if mesh and isinstance(mesh, unreal.StaticMesh):
            bounds = mesh.get_bounds()
            unreal.log_warning(f"Mesh {matching[0]}: Bounds Origin={bounds.origin}, BoxExtent={bounds.box_extent}")

# 2. Inspect a tree actor in level
tree_actors = [a for a in editor_actor_sub.get_all_level_actors() if "Forest_ScannedTree" in a.get_actor_label()]
unreal.log_warning(f"Total Scanned Trees in Level: {len(tree_actors)}")
for t in tree_actors[:3]:
    unreal.log_warning(f"Actor {t.get_actor_label()}: Mesh={t.get_component_by_class(unreal.StaticMeshComponent).get_editor_property('static_mesh').get_name()}, Loc={t.get_actor_location()}, Rot={t.get_actor_rotation()}, Scale={t.get_actor_scale3d()}")
