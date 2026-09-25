"""
Otherworld - Configure Photorealistic Two-Sided Foliage & Bark Materials on All Scanned Assets
"""
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

master_foliage = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Master_Foliage")
master_bark = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Master_Bark")

if not master_foliage or not master_bark:
    unreal.log_error("Master materials missing!")

all_assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)
all_textures = {}
for a in all_assets:
    obj = editor_asset_sub.load_asset(a)
    if isinstance(obj, unreal.Texture):
        all_textures[obj.get_name().lower()] = obj

unreal.log_warning(f"Found {len(all_textures)} scanned textures.")

def find_texture(prefix, role):
    """
    Find best matching texture for a given prefix and role ('diff', 'nor', 'rough').
    """
    prefix = prefix.lower()
    # 1. Exact or near match
    for tname, tex in all_textures.items():
        if prefix in tname:
            if role == 'diff' and any(k in tname for k in ['diff', 'base', 'albedo', 'col']):
                return tex
            elif role == 'nor' and any(k in tname for k in ['nor', 'nrm', 'normal']):
                return tex
            elif role == 'rough' and any(k in tname for k in ['rough', 'arm', 'rgh']):
                return tex
    # Fallback to general model prefix
    base_model = prefix.split('_')[0]
    for tname, tex in all_textures.items():
        if base_model in tname:
            if role == 'diff' and any(k in tname for k in ['diff', 'base', 'albedo', 'col']):
                return tex
            elif role == 'nor' and any(k in tname for k in ['nor', 'nrm', 'normal']):
                return tex
            elif role == 'rough' and any(k in tname for k in ['rough', 'arm', 'rgh']):
                return tex
    return None

foliage_keywords = ['leaf', 'leaves', 'twig', 'needle', 'foliage', 'grass', 'fern', 'moss', 'plant', 'periwinkle', 'shrub']

# Gather all StaticMeshes under /Game/Forest/Scanned
all_meshes = []
for a in all_assets:
    obj = editor_asset_sub.load_asset(a)
    if isinstance(obj, unreal.StaticMesh):
        all_meshes.append(obj)

unreal.log_warning(f"Found {len(all_meshes)} StaticMeshes to configure.")

mic_factory = unreal.MaterialInstanceConstantFactoryNew()
pkg_mat_dir = "/Game/Forest/Materials/Instances"

for mesh in all_meshes:
    mesh_name = mesh.get_name()
    num_sections = mesh.get_num_sections(0)
    unreal.log_warning(f"\nConfiguring Mesh: {mesh_name} ({num_sections} sections)")
    
    for s in range(num_sections):
        orig_mat = mesh.get_material(s)
        slot_name = orig_mat.get_name() if orig_mat else f"Slot_{s}"
        slot_lower = slot_name.lower()
        
        is_foliage = any(kw in slot_lower for kw in foliage_keywords) or any(kw in mesh_name.lower() for kw in foliage_keywords)
        if any(kw in slot_lower for kw in ['trunk', 'bark', 'branch', 'dead_branches', 'rock', 'stump', 'root']):
            is_foliage = False
            
        parent_master = master_foliage if is_foliage else master_bark
        mi_name = f"MI_{mesh_name}_S{s}_{slot_name}"
        mi_path = f"{pkg_mat_dir}/{mi_name}"
        
        # Load or create Material Instance
        mic = editor_asset_sub.load_asset(mi_path)
        if not mic:
            mic = asset_tools.create_asset(mi_name, pkg_mat_dir, unreal.MaterialInstanceConstant, mic_factory)
        
        if not mic:
            continue
            
        mic.set_editor_property("parent", parent_master)
        
        # Find textures for this slot
        # Try matching slot name, or mesh name + slot
        diff_tex = find_texture(slot_name, 'diff') or find_texture(mesh_name, 'diff')
        norm_tex = find_texture(slot_name, 'nor') or find_texture(mesh_name, 'nor')
        rough_tex = find_texture(slot_name, 'rough') or find_texture(mesh_name, 'rough')
        
        if diff_tex:
            mel.set_material_instance_texture_parameter_value(mic, "BaseColorTexture", diff_tex)
        if norm_tex:
            mel.set_material_instance_texture_parameter_value(mic, "NormalTexture", norm_tex)
        if rough_tex:
            mel.set_material_instance_texture_parameter_value(mic, "RoughnessTexture", rough_tex)
            
        mel.update_material_instance(mic)
        editor_asset_sub.save_loaded_asset(mic)
        
        # Assign to mesh
        mesh.set_material(s, mic)
        unreal.log_warning(f"  Slot {s} ({slot_name}) -> {'FOLIAGE' if is_foliage else 'BARK/OPAQUE'} [{mi_name}] (Diff: {diff_tex.get_name() if diff_tex else 'None'})")

    # Save mesh
    editor_asset_sub.save_loaded_asset(mesh)

unreal.log_warning("\n=== ALL SCANNED MESHES CONFIGURED WITH TWO-SIDED FOLIAGE & PBR BARK! ===")
