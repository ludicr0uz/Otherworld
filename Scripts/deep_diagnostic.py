import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

out = []
out.append("==================================================")
out.append("DEEP DIAGNOSTIC OF FOREST TERRAIN RENDERING")
out.append("==================================================")

# 1. Inspect SM_ForestLandscape Static Mesh
mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if mesh:
    out.append(f"Mesh: {mesh.get_path_name()}")
    out.append(f"  Num LODs: {mesh.get_num_lods()}")
    out.append(f"  Num Sections LOD0: {mesh.get_num_sections(0)}")
    out.append(f"  Num Materials: {len(mesh.static_materials)}")
    for i, sm in enumerate(mesh.static_materials):
        mat_iface = sm.material_interface
        out.append(f"    Slot[{i}] ({sm.material_slot_name}): {mat_iface.get_path_name() if mat_iface else 'None'}")
    
    nanite = mesh.get_editor_property("nanite_settings")
    if nanite:
        out.append(f"  Nanite Enabled: {nanite.get_editor_property('enabled')}")

# 2. Inspect M_Forest_Ground_PBR Material
mat = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Forest_Ground_PBR.M_Forest_Ground_PBR")
if mat:
    out.append(f"\nMaterial: {mat.get_path_name()}")
    out.append(f"  BlendMode: {mat.get_editor_property('blend_mode')}")
    out.append(f"  ShadingModel: {mat.get_editor_property('shading_model')}")
    out.append(f"  TwoSided: {mat.get_editor_property('two_sided')}")
    out.append(f"  UsedWithNanite: {mat.get_editor_property('used_with_nanite')}")
    out.append(f"  UsedWithISM: {mat.get_editor_property('used_with_instanced_static_meshes')}")
    
    exprs = mel.get_material_expressions(mat)
    out.append(f"  Total Expressions: {len(exprs)}")
    for e in exprs:
        cls_name = e.get_class().get_name()
        if isinstance(e, unreal.MaterialExpressionTextureSample):
            t = e.get_editor_property("texture")
            st = e.get_editor_property("sampler_type")
            out.append(f"    TextureSample: {t.get_name() if t else 'None'} ({st})")
        elif isinstance(e, unreal.MaterialExpressionTextureCoordinate):
            u = e.get_editor_property("u_tiling")
            v = e.get_editor_property("v_tiling")
            idx = e.get_editor_property("coordinate_index")
            out.append(f"    TexCoord: Index={idx}, Tiling=({u}, {v})")
        elif isinstance(e, unreal.MaterialExpressionLinearInterpolate):
            out.append(f"    Lerp: {e.get_name()}")

# 3. Inspect Textures (Streaming, Mips, Compression, sRGB)
tex_names = ["T_GrassGround_D", "T_GrassGround_N", "T_GrassGround_R", "T_GrassGround_AO",
             "T_ForrestGround01_D", "T_ForrestGround01_N", "T_ForrestGround01_R", "T_ForrestGround01_AO",
             "T_ForestGround05_D"]

out.append("\nTextures:")
for tn in tex_names:
    t = editor_asset_sub.load_asset(f"/Game/Forest/Textures/{tn}.{tn}")
    if t:
        w = t.blueprint_get_size_x()
        h = t.blueprint_get_size_y()
        srgb = t.get_editor_property("srgb")
        comp = t.get_editor_property("compression_settings")
        never_stream = t.get_editor_property("never_stream")
        lod_group = t.get_editor_property("lod_group")
        out.append(f"  {tn}: Size={w}x{h}, sRGB={srgb}, Compression={comp}, NeverStream={never_stream}, LODGroup={lod_group}")
    else:
        out.append(f"  {tn}: NOT FOUND!")

# 4. Inspect Actors in Lvl_Forest.umap
level_path = "/Game/Maps/Lvl_Forest.umap"
world = unreal.EditorLoadingAndSavingUtils.load_map(level_path)
actors = unreal.EditorLevelLibrary.get_all_level_actors()

out.append(f"\nLevel Actors ({len(actors)} total):")
for a in actors:
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    if "Terrain" in lbl or "Landscape" in lbl or "Ground" in lbl or "Light" in lbl or "PostProcess" in lbl or "Fog" in lbl:
        loc = a.get_actor_location()
        scale = a.get_actor_scale3d()
        out.append(f"  Actor '{lbl}' ({cls}) Loc={loc}, Scale={scale}")
        if isinstance(a, unreal.StaticMeshActor):
            smc = a.static_mesh_component
            m = smc.static_mesh
            out.append(f"    Mesh: {m.get_path_name() if m else 'None'}")
            num_mats = smc.get_num_materials()
            for mi in range(num_mats):
                mat_inst = smc.get_material(mi)
                out.append(f"    Material Override[{mi}]: {mat_inst.get_path_name() if mat_inst else 'None'}")
        elif isinstance(a, unreal.DirectionalLight):
            comp = a.get_component_by_class(unreal.DirectionalLightComponent)
            if comp:
                out.append(f"    DirLight Intensity: {comp.get_editor_property('intensity')}")
                out.append(f"    DirLight Color: {comp.get_editor_property('light_color')}")
        elif isinstance(a, unreal.SkyLight):
            comp = a.get_component_by_class(unreal.SkyLightComponent)
            if comp:
                out.append(f"    SkyLight Intensity: {comp.get_editor_property('intensity')}")
        elif isinstance(a, unreal.PostProcessVolume):
            settings = a.get_editor_property("settings")
            out.append(f"    PP Unbound: {a.get_editor_property('unbound')}")
            out.append(f"    PP AutoExposure Method: {settings.get_editor_property('auto_exposure_method')}")
            out.append(f"    PP AutoExposure MinEV100: {settings.get_editor_property('auto_exposure_min_brightness')}")
            out.append(f"    PP AutoExposure MaxEV100: {settings.get_editor_property('auto_exposure_max_brightness')}")
            out.append(f"    PP AutoExposure Bias: {settings.get_editor_property('auto_exposure_bias')}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/deep_diagnostic_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning("Deep diagnostic completed successfully!")
