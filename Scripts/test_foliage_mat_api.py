import unreal

unreal.log_warning("=== TESTING MATERIAL CREATION & SHADING MODELS ===")
for sm in dir(unreal.MaterialShadingModel):
    if not sm.startswith("_"):
        unreal.log_warning(f"  ShadingModel: {sm}")

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
unreal.log_warning(f"AssetTools create_asset available: {hasattr(asset_tools, 'create_asset')}")
