"""
Otherworld - Fast, Robust Foliage & Tree Shading System
Builds Two-Sided Masked Foliage Material Instances & PBR Bark Material Instances
and binds them to all static meshes and HISM components in Lvl_Forest.
"""
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

# Ensure master materials are loaded
master_foliage = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Master_Foliage")
master_bark = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Master_Bark")

if not master_foliage or not master_bark:
    raise RuntimeError("Master materials M_Master_Foliage and M_Master_Bark must exist!")

# Load all scanned textures into indexed map
all_assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)
all_textures = {}
for a in all_assets:
    obj = editor_asset_sub.load_asset(a)
    if isinstance(obj, unreal.Texture):
        all_textures[obj.get_name().lower()] = obj

unreal.log_warning(f"[AGY] Loaded {len(all_textures)} scanned textures for material assignment.")

def find_tex(keywords, role):
    """Find texture matching keywords and role ('diff', 'nor', 'rough')."""
    role_kws = {
        'diff': ['diff', 'base', 'albedo', 'col', 'alpha', 'opacity'],
        'nor': ['nor', 'nrm', 'normal'],
        'rough': ['rough', 'arm', 'rgh']
    }
    targets = role_kws.get(role, [])
    
    # 1. Try matching all keywords + target
    for tname, tex in all_textures.items():
        if all(k in tname for k in keywords) and any(t in tname for t in targets):
            return tex
            
    # 2. Try matching any keyword + target
    for tname, tex in all_textures.items():
        if any(k in tname for k in keywords) and any(t in tname for t in targets):
            return tex
            
    return None

foliage_keywords = ['leaf', 'leaves', 'twig', 'needle', 'foliage', 'grass', 'fern', 'moss', 'plant', 'periwinkle', 'shrub']
opaque_keywords = ['trunk', 'bark', 'branch', 'branches', 'dead_branches', 'rock', 'stump', 'root']

mic_factory = unreal.MaterialInstanceConstantFactoryNew()
pkg_mat_dir = "/Game/Forest/Materials/Instances"

# Model slot explicit mapping
mesh_configs = [
    # Leafy broadleaf trees
    {
        "mesh": "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01",
        "slots": [
            ("trunk", False, ["island_tree_01", "diff"], ["island_tree_01", "nor"], ["island_tree_01", "rough"]),
            ("leaves", True, ["island_tree_01_leaves", "diff"], ["island_tree_01_leaves", "nor"], ["island_tree_01_leaves", "rough"]),
            ("branches", False, ["island_tree_01_branches", "diff"], ["island_tree_01_branches", "nor"], ["island_tree_01_branches", "rough"]),
        ]
    },
    {
        "mesh": "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/StaticMeshes/SM_island_tree_02.SM_island_tree_02",
        "slots": [
            ("trunk", False, ["island_tree_02", "diff"], ["island_tree_02", "nor"], ["island_tree_02", "rough"]),
            ("leaves", True, ["island_tree_02_leaves", "diff"], ["island_tree_02_leaves", "nor"], ["island_tree_02_leaves", "rough"]),
            ("branches", False, ["island_tree_02_branches", "diff"], ["island_tree_02_branches", "nor"], ["island_tree_02_branches", "rough"]),
        ]
    },
    {
        "mesh": "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
        "slots": [
            ("branches", False, ["tree_small_02_branch", "diff"], ["tree_small_02_branch", "nor"], ["tree_small_02_branch", "rough"]),
            ("leaves", True, ["tree_small_02_leaves", "diff"], ["tree_small_02_leaves", "nor"], ["tree_small_02_leaves", "rough"]),
            ("trunk", False, ["tree_small_02", "diff"], ["tree_small_02", "nor"], ["tree_small_02", "rough"]),
        ]
    },
    # Evergreen Fir trees
    {
        "mesh": "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_a_LOD0.fir_tree_01_a_LOD0",
        "slots": [
            ("bark", False, ["fir_tree_01_bark", "diff"], ["fir_tree_01_bark", "nor"], ["fir_tree_01_bark", "rough"]),
            ("trunk_a", False, ["fir_tree_01_trunk_a", "diff"], ["fir_tree_01_trunk_a", "nor"], ["fir_tree_01_trunk_a", "rough"]),
            ("twig", True, ["fir_tree_01_twig", "diff"], ["fir_tree_01_twig", "nor"], ["fir_tree_01_twig", "rough"]),
            ("dead_branches", False, ["fir_tree_01_bark", "diff"], ["fir_tree_01_bark", "nor"], ["fir_tree_01_bark", "rough"]),
        ]
    },
    {
        "mesh": "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_b_LOD0.fir_tree_01_b_LOD0",
        "slots": [
            ("bark", False, ["fir_tree_01_bark", "diff"], ["fir_tree_01_bark", "nor"], ["fir_tree_01_bark", "rough"]),
            ("trunk_b", False, ["fir_tree_01_trunk_b", "diff"], ["fir_tree_01_trunk_b", "nor"], ["fir_tree_01_trunk_b", "rough"]),
            ("twig", True, ["fir_tree_01_twig", "diff"], ["fir_tree_01_twig", "nor"], ["fir_tree_01_twig", "rough"]),
            ("dead_branches", False, ["fir_tree_01_bark", "diff"], ["fir_tree_01_bark", "nor"], ["fir_tree_01_bark", "rough"]),
        ]
    },
    {
        "mesh": "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_c_LOD0.fir_tree_01_c_LOD0",
        "slots": [
            ("bark", False, ["fir_tree_01_bark", "diff"], ["fir_tree_01_bark", "nor"], ["fir_tree_01_bark", "rough"]),
            ("twig", True, ["fir_tree_01_twig", "diff"], ["fir_tree_01_twig", "nor"], ["fir_tree_01_twig", "rough"]),
            ("dead_branches", False, ["fir_tree_01_bark", "diff"], ["fir_tree_01_bark", "nor"], ["fir_tree_01_bark", "rough"]),
            ("trunk_c", False, ["fir_tree_01_trunk_b", "diff"], ["fir_tree_01_trunk_b", "nor"], ["fir_tree_01_trunk_b", "rough"]),
        ]
    },
    # Pine saplings
    {
        "mesh": "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a",
        "slots": [
            ("bark", False, ["pine_sapling_small_bark", "diff"], ["pine_sapling_small_bark", "nor"], ["pine_sapling_small_bark", "rough"]),
            ("twig", True, ["pine_sapling_small_twig", "diff"], ["pine_sapling_small_twig", "nor"], ["pine_sapling_small_twig", "rough"]),
        ]
    },
    {
        "mesh": "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_b.pine_sapling_small_b",
        "slots": [
            ("bark", False, ["pine_sapling_small_bark", "diff"], ["pine_sapling_small_bark", "nor"], ["pine_sapling_small_bark", "rough"]),
            ("twig", True, ["pine_sapling_small_twig", "diff"], ["pine_sapling_small_twig", "nor"], ["pine_sapling_small_twig", "rough"]),
        ]
    },
    {
        "mesh": "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_c.pine_sapling_small_c",
        "slots": [
            ("bark", False, ["pine_sapling_small_bark", "diff"], ["pine_sapling_small_bark", "nor"], ["pine_sapling_small_bark", "rough"]),
            ("twig", True, ["pine_sapling_small_twig", "diff"], ["pine_sapling_small_twig", "nor"], ["pine_sapling_small_twig", "rough"]),
        ]
    },
]

# Add all Grass, Fern, Moss, Periwinkle, Shrub, Rock, Stump meshes
single_slot_models = [
    # Foliage (Slot 0 is foliage)
    ("grass_medium_01", True, ["grass_medium_01", "diff"], ["grass_medium_01", "nor"], ["grass_medium_01", "rough"]),
    ("grass_medium_02", True, ["grass_medium_02", "diff"], ["grass_medium_02", "nor"], ["grass_medium_02", "rough"]),
    ("fern_02", True, ["fern_02", "diff"], ["fern_02", "nor"], ["fern_02", "rough"]),
    ("moss_01", True, ["moss_01", "diff"], ["moss_01", "nor"], ["moss_01", "rough"]),
    ("periwinkle_plant", True, ["periwinkle_plant", "diff"], ["periwinkle_plant", "nor"], ["periwinkle_plant", "rough"]),
    ("shrub_01", True, ["shrub_01", "diff"], ["shrub_01", "nor"], ["shrub_01", "rough"]),
    ("shrub_03", True, ["shrub_03", "diff"], ["shrub_03", "nor"], ["shrub_03", "rough"]),
    # Opaque (Slot 0 is bark/rock)
    ("rock_07", False, ["rock_07", "diff"], ["rock_07", "nor"], ["rock_07", "rough"]),
    ("rock_moss_set_01", False, ["rock_moss_set_01", "diff"], ["rock_moss_set_01", "nor"], ["rock_moss_set_01", "rough"]),
    ("tree_stump_01", False, ["tree_stump_01", "diff"], ["tree_stump_01", "nor"], ["tree_stump_01", "rough"]),
    ("tree_stump_02", False, ["tree_stump_02", "diff"], ["tree_stump_02", "nor"], ["tree_stump_02", "rough"]),
    ("root_cluster_01", False, ["root_cluster_01", "diff"], ["root_cluster_01", "nor"], ["root_cluster_01", "rough"]),
]

for mid, is_fol, d_kw, n_kw, r_kw in single_slot_models:
    matching_meshes = [a for a in all_assets if f"/{mid}/" in a and ("StaticMeshes" in a or "SM_" in a or "_LOD" in a or "_a" in a)]
    for ma in matching_meshes:
        mesh_configs.append({
            "mesh": ma,
            "slots": [
                (mid, is_fol, d_kw, n_kw, r_kw)
            ]
        })

created_mics = {}

for cfg in mesh_configs:
    mpath = cfg["mesh"]
    mesh = editor_asset_sub.load_asset(mpath)
    if not isinstance(mesh, unreal.StaticMesh):
        continue
        
    mname = mesh.get_name()
    num_sections = mesh.get_num_sections(0)
    
    for s_idx, (slot_tag, is_fol, d_kws, n_kws, r_kws) in enumerate(cfg["slots"]):
        if s_idx >= num_sections:
            break
            
        parent_mat = master_foliage if is_fol else master_bark
        mi_name = f"MI_{mname}_S{s_idx}_{slot_tag}"
        mi_path = f"{pkg_mat_dir}/{mi_name}"
        
        mic = created_mics.get(mi_path)
        if not mic:
            mic = editor_asset_sub.load_asset(mi_path)
            if not mic:
                mic = asset_tools.create_asset(mi_name, pkg_mat_dir, unreal.MaterialInstanceConstant, mic_factory)
            
            if mic:
                mic.set_editor_property("parent", parent_mat)
                
                # Assign textures
                diff_t = find_tex(d_kws, 'diff')
                norm_t = find_tex(n_kws, 'nor')
                rough_t = find_tex(r_kws, 'rough')
                
                if diff_t:
                    mel.set_material_instance_texture_parameter_value(mic, "BaseColorTexture", diff_t)
                if norm_t:
                    mel.set_material_instance_texture_parameter_value(mic, "NormalTexture", norm_t)
                if rough_t:
                    mel.set_material_instance_texture_parameter_value(mic, "RoughnessTexture", rough_t)
                    
                mel.update_material_instance(mic)
                editor_asset_sub.save_loaded_asset(mic)
                created_mics[mi_path] = mic
                
        if mic:
            mesh.set_material(s_idx, mic)
            
    # Save the mesh asset once with all slots configured
    editor_asset_sub.save_loaded_asset(mesh)
    unreal.log_warning(f"[AGY] Configured StaticMesh: {mname} ({num_sections} slots)")

unreal.log_warning(f"[AGY] Successfully generated and configured {len(created_mics)} Material Instances across all nature models!")
