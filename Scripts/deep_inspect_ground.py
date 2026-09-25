import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

unreal.log_warning("==================================================")
unreal.log_warning("=== DEEP INSPECTION OF GROUND & TERRAIN ===")
unreal.log_warning("==================================================")

actors = editor_actor_sub.get_all_level_actors()
for a in actors:
    lbl = a.get_actor_label()
    loc = a.get_actor_location()
    scale = a.get_actor_scale3d()
    
    if "Terrain" in lbl or "Landscape" in lbl or "Ground" in lbl or "Floor" in lbl or "Plane" in lbl or "Cube" in lbl or "Player" in lbl:
        unreal.log_warning(f"Actor: {lbl} | Class: {a.get_class().get_name()} | Loc: ({loc.x}, {loc.y}, {loc.z}) | Scale: ({scale.x}, {scale.y}, {scale.z})")
        root = a.get_editor_property("root_component")
        if isinstance(root, unreal.StaticMeshComponent):
            sm = root.get_editor_property("static_mesh")
            sm_name = sm.get_name() if sm else "None"
            unreal.log_warning(f"  Mesh: {sm_name} (path: {sm.get_path_name() if sm else 'None'})")
            num_mats = root.get_num_materials()
            for i in range(num_mats):
                m = root.get_material(i)
                m_name = m.get_name() if m else "None"
                unreal.log_warning(f"  Comp Mat Slot {i}: {m_name} (path: {m.get_path_name() if m else 'None'})")
            if sm:
                mesh_num_mats = sm.get_num_sections(0)
                for j in range(mesh_num_mats):
                    mm = sm.get_material(j)
                    mm_name = mm.get_name() if mm else "None"
                    unreal.log_warning(f"  Asset Mat Slot {j}: {mm_name} (path: {mm.get_path_name() if mm else 'None'})")
        elif isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
            sm = root.get_editor_property("static_mesh")
            sm_name = sm.get_name() if sm else "None"
            unreal.log_warning(f"  HISM Mesh: {sm_name}")
            num_mats = root.get_num_materials()
            for i in range(num_mats):
                m = root.get_material(i)
                m_name = m.get_name() if m else "None"
                unreal.log_warning(f"  HISM Mat Slot {i}: {m_name}")

# Inspect SM_ForestLandscape geometry and bounds
mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if mesh:
    bounds = mesh.get_bounds()
    unreal.log_warning(f"\nSM_ForestLandscape Bounds: Origin=({bounds.origin.x}, {bounds.origin.y}, {bounds.origin.z}), BoxExtent=({bounds.box_extent.x}, {bounds.box_extent.y}, {bounds.box_extent.z}), SphereRadius={bounds.sphere_radius}")
    unreal.log_warning(f"Num Sections LOD0: {mesh.get_num_sections(0)}")
    for s in range(mesh.get_num_sections(0)):
        mat = mesh.get_material(s)
        unreal.log_warning(f"Section {s} Mat: {mat.get_name() if mat else 'None'}")

# Inspect M_Forest_Ground_PBR expressions & textures
ground_mat = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Forest_Ground_PBR")
if ground_mat:
    unreal.log_warning(f"\nM_Forest_Ground_PBR Details:")
    unreal.log_warning(f"  BlendMode: {ground_mat.get_editor_property('blend_mode')}")
    unreal.log_warning(f"  ShadingModel: {ground_mat.get_editor_property('shading_model')}")
    exprs = unreal.MaterialEditingLibrary.get_material_expressions(ground_mat)
    unreal.log_warning(f"  Num Expressions: {len(exprs)}")
    for exp in exprs:
        if isinstance(exp, unreal.MaterialExpressionTextureSample):
            tex = exp.get_editor_property("texture")
            tname = tex.get_name() if tex else "None"
            unreal.log_warning(f"  TextureSample: {tname}")
        elif isinstance(exp, unreal.MaterialExpressionConstant3Vector):
            c = exp.get_editor_property("constant")
            unreal.log_warning(f"  Constant3Vector: ({c.r}, {c.g}, {c.b})")
        elif isinstance(exp, unreal.MaterialExpressionTextureCoordinate):
            u = exp.get_editor_property("u_tiling")
            v = exp.get_editor_property("v_tiling")
            unreal.log_warning(f"  TexCoord: UTiling={u}, VTiling={v}")
