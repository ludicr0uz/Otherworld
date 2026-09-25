import unreal

asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
filter = unreal.ARFilter(class_names=["Texture2D"], package_paths=["/Game/Forest/Textures", "/Game/Forest/Scanned"])
assets = asset_reg.get_assets(filter)

out = [f"Total Textures found: {len(assets)}"]
for ad in assets:
    pkg = ad.package_name
    name = ad.asset_name
    obj = ad.get_asset()
    if obj:
        w = obj.blueprint_get_size_x() if hasattr(obj, "blueprint_get_size_x") else "?"
        h = obj.blueprint_get_size_y() if hasattr(obj, "blueprint_get_size_y") else "?"
        srgb = obj.get_editor_property("srgb") if hasattr(obj, "srgb") else "?"
        out.append(f"{name} ({pkg}) -> {w}x{h}, sRGB={srgb}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/textures_list.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning(f"Listed {len(assets)} textures")
