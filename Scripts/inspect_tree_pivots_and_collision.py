import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

tree_paths = [
    ("IslandTree01", "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01"),
    ("IslandTree02", "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/StaticMeshes/SM_island_tree_02.SM_island_tree_02"),
    ("FirTree01A", "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_a_LOD0.fir_tree_01_a_LOD0"),
    ("FirTree01B", "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_b_LOD0.fir_tree_01_b_LOD0"),
    ("FirTree01C", "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_c_LOD0.fir_tree_01_c_LOD0"),
    ("PineA", "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a"),
    ("Deciduous", "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02"),
]

out = ["=== Tree Bounding Boxes & Pivot Offsets ==="]
for name, p in tree_paths:
    m = editor_asset_sub.load_asset(p)
    if m:
        bounds = m.get_bounds()
        box_ext = bounds.box_extent
        origin = bounds.origin
        min_z = origin.z - box_ext.z
        max_z = origin.z + box_ext.z
        out.append(f"{name}: Origin={origin}, Extent={box_ext}, MinZ={min_z:.2f}, MaxZ={max_z:.2f}")

# Check SM_ForestLandscape collision
tm = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if tm:
    bs = tm.get_editor_property("body_setup")
    if bs:
        out.append(f"\nTerrain BodySetup: TraceFlag={bs.get_editor_property('collision_trace_flag')}")
    nanite = tm.get_editor_property("nanite_settings")
    if nanite:
        out.append(f"Terrain Nanite: Enabled={nanite.get_editor_property('enabled')}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/tree_pivots_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning("Done inspecting tree pivots and collision!")
