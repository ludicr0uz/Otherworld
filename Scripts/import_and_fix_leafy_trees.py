"""
Otherworld - Import Leafy Trees & Ensure Two-Sided Masked Foliage Rendering
"""
import os
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

SCANNED_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/downloaded_scanned_assets"
tree_models = ["island_tree_01", "island_tree_02", "fir_tree_01"]

for mid in tree_models:
    gltf_file = os.path.join(SCANNED_DIR, mid, f"{mid}_1k.gltf")
    if os.path.exists(gltf_file):
        dest_folder = f"/Game/Forest/Scanned/{mid}"
        task = unreal.AssetImportTask()
        task.filename = gltf_file
        task.destination_path = dest_folder
        task.destination_name = f"SM_{mid}"
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])
        unreal.log_warning(f"[AGY] Imported tree model: {mid}")

# Now configure and fix all foliage materials across all trees
all_scanned_assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)

for a in all_scanned_assets:
    asset = editor_asset_sub.load_asset(a)
    if not asset:
        continue

    # Fix static mesh nanite & collision
    if isinstance(asset, unreal.StaticMesh):
        body = asset.get_editor_property("body_setup")
        if body:
            body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        nanite_s = asset.get_editor_property("nanite_settings")
        if nanite_s:
            nanite_s.set_editor_property("enabled", True)
            asset.set_editor_property("nanite_settings", nanite_s)
        editor_asset_sub.save_loaded_asset(asset)

    # Fix leaf/needle materials
    elif isinstance(asset, unreal.Material):
        mat_name = asset.get_name().lower()
        if any(w in mat_name for w in ["leaf", "leaves", "twig", "branch", "needle", "foliage", "grass", "fern", "plant", "periwinkle"]):
            asset.set_editor_property("two_sided", True)
            asset.set_editor_property("used_with_nanite", True)
            asset.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
            asset.set_editor_property("opacity_mask_clip_value", 0.3)
            
            # Find texture samples and ensure Alpha is connected to Opacity Mask
            expressions = mel.get_material_expressions(asset)
            for expr in expressions:
                if isinstance(expr, unreal.MaterialExpressionTextureSample):
                    tex = expr.get_editor_property("texture")
                    if tex and any(w in tex.get_name().lower() for w in ["diff", "base", "color", "leaf", "leaves", "twig", "branch"]):
                        try:
                            mel.connect_material_property(expr, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
                        except Exception as e:
                            pass
            mel.recompile_material(asset)
            editor_asset_sub.save_loaded_asset(asset)
            unreal.log_warning(f"[AGY] Configured 2-Sided Masked Foliage Material: {asset.get_name()}")

unreal.log_warning("[AGY] ALL LEAFY TREE MATERIALS CONFIGURED AND COMPILED!")
