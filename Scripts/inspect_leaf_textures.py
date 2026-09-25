import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

tex_paths = [
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_diff-island_tree_01_leaves_alpha",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_leaves_diff-island_tree_02_leaves_alpha",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_leaves_diff-tree_small_02_leaves_alpha",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_twig_diff-fir_tree_01_twig_alpha",
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/Textures/pine_sapling_small_twig_diff-pine_sapling_small_twig_alpha"
]

for tp in tex_paths:
    tex = editor_asset_sub.load_asset(tp)
    if not tex:
        unreal.log_warning(f"Texture not found: {tp}")
        continue
    unreal.log_warning(f"=== TEXTURE: {tex.get_name()} ===")
    unreal.log_warning(f"  Size: {tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()}")
    unreal.log_warning(f"  Compression: {tex.get_editor_property('compression_settings')}")
    unreal.log_warning(f"  SRGB: {tex.get_editor_property('srgb')}")
    unreal.log_warning(f"  HasAlpha: {tex.has_alpha_channel() if hasattr(tex, 'has_alpha_channel') else 'N/A'}")
    unreal.log_warning(f"  AlphaCoverageThresholds: {tex.get_editor_property('alpha_coverage_thresholds') if hasattr(tex, 'alpha_coverage_thresholds') else 'N/A'}")
