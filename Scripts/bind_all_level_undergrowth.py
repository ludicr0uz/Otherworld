import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

mats = {
    "HISM_Grass_Medium": "/Game/Forest/Materials/Instances/MI_GrassMedium01",
    "HISM_Grass_Tall": "/Game/Forest/Materials/Instances/MI_GrassMedium02",
    "HISM_Ferns": "/Game/Forest/Materials/Instances/MI_Fern02",
    "HISM_Moss_Patch": "/Game/Forest/Materials/Instances/MI_Moss01",
    "HISM_Flowers": "/Game/Forest/Materials/Instances/MI_Periwinkle",
    "HISM_Shrub_01": "/Game/Forest/Materials/Instances/MI_Shrub01",
    "HISM_Shrub_03": "/Game/Forest/Materials/Instances/MI_Shrub03",
    "HISM_Rock_Granite": "/Game/Forest/Materials/Instances/MI_Rock07",
    "HISM_Rock_Moss": "/Game/Forest/Materials/Instances/MI_RockMossSet",
    "HISM_Stump_01": "/Game/Forest/Materials/Instances/MI_TreeStump01",
    "HISM_Stump_02": "/Game/Forest/Materials/Instances/MI_TreeStump02",
    "HISM_Root_Cluster": "/Game/Forest/Materials/Instances/MI_RootCluster01",
}

actors = editor_actor_sub.get_all_level_actors()
for a in actors:
    lbl = a.get_actor_label()
    if lbl in mats:
        mat_path = mats[lbl]
        mat_asset = editor_asset_sub.load_asset(mat_path)
        if mat_asset:
            root = a.get_editor_property("root_component")
            if isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
                root.set_material(0, mat_asset)
                unreal.log_warning(f"[AGY] Bound {mat_asset.get_name()} to {lbl}")

level_editor_sub.save_current_level()
unreal.log_warning("[AGY] ALL UNDERGROWTH AND ROCK MATERIALS UPDATED AND LEVEL SAVED!")
