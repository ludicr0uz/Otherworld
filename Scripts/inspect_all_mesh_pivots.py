import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
filter = unreal.ARFilter(class_names=["StaticMesh"], package_paths=["/Game/Forest/Scanned"])
assets = asset_reg.get_assets(filter)

out = [f"Total Scanned Meshes: {len(assets)}"]
for ad in assets:
    m = ad.get_asset()
    if m:
        b = m.get_bounds()
        o = b.origin
        e = b.box_extent
        min_z = o.z - e.z
        out.append(f"{ad.asset_name}: Origin=({o.x:.1f}, {o.y:.1f}, {o.z:.1f}), Extent=({e.x:.1f}, {e.y:.1f}, {e.z:.1f}), MinZ={min_z:.1f}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/mesh_pivots_list.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning(f"Listed {len(assets)} meshes")
