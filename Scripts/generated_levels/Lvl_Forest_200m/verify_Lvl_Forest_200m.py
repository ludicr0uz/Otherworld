"""
Auto-generated Unreal verification script for Lvl_Forest_200m.
Verifies collision, materials, actor presence, tree and grass HISM
instances (including that grass really is knee high), and the
time-of-day lighting rig.
Time of day: Night — starry sky as the only light source, low luminosity
"""
import json
import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

LEVEL_NAME = "Lvl_Forest_200m"
WORLD_SIZE_CM = 20000.0
EXPECTED_TREE_COUNT = 136
EXPECTED_SPEC_COUNTS = {"HISM_Tree_Leafy_Island_01": 28, "HISM_Tree_Leafy_Island_02": 28, "HISM_Tree_Fir_A": 44, "HISM_Tree_Pine_A": 20, "HISM_Tree_Deciduous": 16}
EXPECTED_GRASS_COUNT = 44368
EXPECTED_GRASS_SPEC_COUNTS = {"HISM_Grass_Knee_Tall_C": 6415, "HISM_Grass_Under_Mid_B": 2850, "HISM_Grass_Knee_Tall_B": 7813, "HISM_Grass_Knee_Mid_A": 5862, "HISM_Grass_Knee_Tall_A": 8451, "HISM_Grass_Knee_Clump_C": 5844, "HISM_Grass_Under_Clump_A": 2325, "HISM_Grass_Under_Large_B": 2611, "HISM_Grass_Under_Large_A": 2197}
EXPECTED_GRASS_HEIGHTS = {"HISM_Grass_Knee_Tall_C": [42.242809249629246, 55.199687244614566], "HISM_Grass_Under_Mid_B": [25.503926948960117, 35.99430151464459], "HISM_Grass_Knee_Tall_B": [42.50254371397834, 59.99927478522139], "HISM_Grass_Knee_Mid_A": [40.481314514524335, 50.599412580219756], "HISM_Grass_Knee_Tall_A": [42.50006710260952, 59.99895840027987], "HISM_Grass_Knee_Clump_C": [43.12312612443456, 53.89936647630565], "HISM_Grass_Under_Clump_A": [23.800345353400235, 33.59905037018744], "HISM_Grass_Under_Large_B": [24.65506062683597, 34.79728745482545], "HISM_Grass_Under_Large_A": [22.100624064757703, 31.198261357139028]}
LIGHTING = json.loads(r"""{"key": "night", "label": "Night \u2014 starry sky as the only light source, low luminosity", "sun": {"enabled": true, "label_suffix": "Moon", "intensity": 0.12, "color": [170, 195, 255], "pitch": -32.0, "yaw": 120.0, "cast_shadows": true}, "sky_light": {"intensity": 3.0, "real_time_capture": true}, "sky_dome": {"enabled": true, "material": "/Game/Forest/Materials/M_NightSky_Starfield", "build_starfield": true, "star_brightness": 2.5, "night_sky_color": [0.004, 0.008, 0.022, 1.0], "star_tiling": [2.0, 1.0]}, "volumetric_cloud": {"enabled": false}, "fog": {"density": 0.035, "inscattering_color": [0.015, 0.025, 0.055], "enable_volumetric": true, "volumetric_extinction_scale": 0.6}, "post_process": {"auto_exposure_min_brightness": 0.004, "auto_exposure_max_brightness": 0.6, "auto_exposure_bias": 1.6}}""")

passed = 0
failed = 0
total = 0

def check(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        unreal.log_warning(f"  ✅ {name}: PASSED {detail}")
    else:
        failed += 1
        unreal.log_error(f"  ❌ {name}: FAILED {detail}")

unreal.log_warning("=" * 60)
unreal.log_warning(f"[VERIFY] Verifying {LEVEL_NAME} in Unreal Engine")
unreal.log_warning("=" * 60)

# Load level
level_editor_sub.load_level(f"/Game/Maps/{LEVEL_NAME}")

actors = editor_actor_sub.get_all_level_actors()
actor_labels = [a.get_actor_label() for a in actors]

# ── 1. Terrain Actor Exists ──────────────────────────────────────────
terrain_label = f"{LEVEL_NAME}_Terrain"
check("Terrain Actor Exists", terrain_label in actor_labels)

# ── 2. Terrain has StaticMeshComponent with BlockAll collision ────────
for a in actors:
    if a.get_actor_label() == terrain_label:
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        check("Terrain Has SMC", smc is not None)
        if smc:
            check("Terrain Collision Profile",
                  smc.get_collision_profile_name() == "BlockAll",
                  f"(got: {smc.get_collision_profile_name()})")
            check("Terrain Collision Enabled",
                  smc.get_collision_enabled() == unreal.CollisionEnabled.QUERY_AND_PHYSICS)

            mesh = smc.get_editor_property("static_mesh")
            check("Terrain Mesh Assigned", mesh is not None)
            if mesh:
                nanite = mesh.get_editor_property("nanite_settings")
                check("Terrain Nanite Disabled",
                      not nanite.enabled if nanite else True)

                body = mesh.get_editor_property("body_setup")
                if body:
                    flag = body.get_editor_property("collision_trace_flag")
                    check("Terrain Complex Collision",
                          flag == unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE,
                          f"(got: {flag})")

                mat = mesh.get_material(0)
                check("Terrain Material Assigned", mat is not None)
                if mat:
                    check("Terrain Material Is PBR",
                          "M_Forest_Ground_PBR" in mat.get_path_name(),
                          f"(got: {mat.get_path_name()})")

# ── 3. Lighting & Sky Actors (time of day: Night — starry sky as the only light source, low luminosity) ──────────────
sun_cfg = LIGHTING["sun"]
sky_cfg = LIGHTING["sky_light"]
dome_cfg = LIGHTING["sky_dome"]
cloud_cfg = LIGHTING["volumetric_cloud"]
pp_cfg = LIGHTING["post_process"]

sun_label = f"{LEVEL_NAME}_{sun_cfg['label_suffix']}"
check("Directional Light Exists", sun_label in actor_labels, f"({sun_label})")
check("Sky Atmosphere Exists", f"{LEVEL_NAME}_SkyAtmosphere" in actor_labels)
check("Sky Sphere Exists", f"{LEVEL_NAME}_SkySphere" in actor_labels)
check("Sky Light Exists", f"{LEVEL_NAME}_SkyLight" in actor_labels)
check("Fog Exists", f"{LEVEL_NAME}_Fog" in actor_labels)
check("PostProcess Exists", f"{LEVEL_NAME}_PostProcess" in actor_labels)
check("Player Start Exists", f"{LEVEL_NAME}_PlayerStart" in actor_labels)

cloud_present = f"{LEVEL_NAME}_VolumetricCloud" in actor_labels
check("Volumetric Cloud Matches Preset",
      cloud_present == cloud_cfg["enabled"],
      f"(preset wants {cloud_cfg['enabled']}, found {cloud_present})")

def close(a, b, tol=1e-3):
    return abs(a - b) <= tol

for a in actors:
    lbl = a.get_actor_label()

    if lbl == sun_label:
        dlc = a.get_component_by_class(unreal.DirectionalLightComponent)
        check("Directional Light Component", dlc is not None)
        if dlc:
            inten = dlc.get_editor_property("intensity")
            check("Directional Light Intensity",
                  close(inten, sun_cfg["intensity"], 0.01),
                  f"(expected {sun_cfg['intensity']} lux, got {inten})")
            check("Atmosphere Sun Light Enabled",
                  dlc.get_editor_property("atmosphere_sun_light"))
            check("Directional Light Casts Shadows",
                  dlc.get_editor_property("cast_shadows") == sun_cfg["cast_shadows"])

    elif lbl == f"{LEVEL_NAME}_SkyLight":
        slc = a.get_component_by_class(unreal.SkyLightComponent)
        if slc:
            inten = slc.get_editor_property("intensity")
            check("Sky Light Intensity",
                  close(inten, sky_cfg["intensity"], 0.01),
                  f"(expected {sky_cfg['intensity']}, got {inten})")
            check("Sky Light Real Time Capture",
                  slc.get_editor_property("real_time_capture") == sky_cfg["real_time_capture"])

    elif lbl == f"{LEVEL_NAME}_SkySphere":
        ssc = a.get_component_by_class(unreal.StaticMeshComponent)
        if ssc:
            dome_mat = ssc.get_material(0)
            check("Sky Dome Material Assigned", dome_mat is not None)
            if dome_mat:
                mat_path = dome_mat.get_path_name()
                if dome_cfg.get("build_starfield"):
                    check("Sky Dome Is Starfield",
                          "NightSky_Starfield" in mat_path,
                          f"(got: {mat_path})")
                    base = dome_mat.get_base_material() if hasattr(dome_mat, "get_base_material") else None
                    src = base or dome_mat
                    try:
                        check("Starfield Material Is Unlit",
                              src.get_editor_property("shading_model")
                              == unreal.MaterialShadingModel.MSM_UNLIT)
                        check("Starfield Material Tagged IsSky",
                              src.get_editor_property("is_sky"))
                    except Exception as exc:
                        check("Starfield Material Flags", False, f"({exc})")
                    try:
                        sb = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
                            dome_mat, "StarBrightness")
                        check("Star Brightness Set",
                              close(sb, dome_cfg["star_brightness"], 0.01),
                              f"(expected {dome_cfg['star_brightness']}, got {sb})")
                    except Exception as exc:
                        check("Star Brightness Set", False, f"({exc})")
                else:
                    check("Sky Dome Material Matches Preset",
                          dome_cfg["material"].split(".")[0] in mat_path,
                          f"(got: {mat_path})")

    elif lbl == f"{LEVEL_NAME}_PostProcess":
        st = a.get_editor_property("settings")
        check("Exposure Min Brightness",
              close(st.get_editor_property("auto_exposure_min_brightness"),
                    pp_cfg["auto_exposure_min_brightness"], 1e-4),
              f"(expected {pp_cfg['auto_exposure_min_brightness']})")
        check("Exposure Max Brightness",
              close(st.get_editor_property("auto_exposure_max_brightness"),
                    pp_cfg["auto_exposure_max_brightness"], 1e-4),
              f"(expected {pp_cfg['auto_exposure_max_brightness']})")
        check("Exposure Bias",
              close(st.get_editor_property("auto_exposure_bias"),
                    pp_cfg["auto_exposure_bias"], 1e-4),
              f"(expected {pp_cfg['auto_exposure_bias']})")

# ── 4. Tree HISM Actors ──────────────────────────────────────────────
total_tree_instances = 0
for spec_name, expected_count in EXPECTED_SPEC_COUNTS.items():
    found = False
    for a in actors:
        if a.get_actor_label() == spec_name:
            found = True
            # Count HISM instances via root component
            root = a.get_editor_property("root_component")
            if root and isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
                inst_count = root.get_instance_count()
                total_tree_instances += inst_count
                check(f"{spec_name} Instance Count",
                      inst_count == expected_count,
                      f"(expected {expected_count}, got {inst_count})")
                check(f"{spec_name} Collision Profile",
                      root.get_collision_profile_name() == "BlockAll")
            break
    check(f"{spec_name} Actor Exists", found)

check("Total Tree Instances",
      total_tree_instances == EXPECTED_TREE_COUNT,
      f"(expected {EXPECTED_TREE_COUNT}, got {total_tree_instances})")

# ── 5. Grass HISM Actors ─────────────────────────────────────────────
if EXPECTED_GRASS_COUNT > 0:
    total_grass_instances = 0
    for spec_name, expected_count in EXPECTED_GRASS_SPEC_COUNTS.items():
        found = False
        for a in actors:
            if a.get_actor_label() == spec_name:
                found = True
                root = a.get_editor_property("root_component")
                if root and isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
                    inst_count = root.get_instance_count()
                    total_grass_instances += inst_count
                    check(f"{spec_name} Instance Count",
                          inst_count == expected_count,
                          f"(expected {expected_count}, got {inst_count})")
                    # Grass must never block the player.
                    check(f"{spec_name} No Collision",
                          str(root.get_collision_profile_name()) == "NoCollision",
                          f"(got {root.get_collision_profile_name()})")

                    # Prove the clumps really land at knee height:
                    # mesh bounds height × instance Z scale.
                    mesh = root.get_editor_property("static_mesh")
                    lo_hi = EXPECTED_GRASS_HEIGHTS.get(spec_name)
                    if mesh and lo_hi and inst_count > 0:
                        mesh_h = float(mesh.get_bounds().box_extent.z) * 2.0
                        sampled = []
                        step = max(1, inst_count // 50)
                        for i in range(0, inst_count, step):
                            tf = root.get_instance_transform(i, world_space=False)
                            sampled.append(float(tf.scale3d.z) * mesh_h)
                        lo, hi = lo_hi
                        worst = [h for h in sampled
                                 if not (lo - 1.0 <= h <= hi + 1.0)]
                        check(f"{spec_name} Knee Height",
                              len(worst) == 0,
                              f"(expected {lo:.1f}-{hi:.1f} cm, "
                              f"sampled {min(sampled):.1f}-{max(sampled):.1f} cm)")
                break
        check(f"{spec_name} Actor Exists", found)

    check("Total Grass Instances",
          total_grass_instances == EXPECTED_GRASS_COUNT,
          f"(expected {EXPECTED_GRASS_COUNT}, got {total_grass_instances})")

# ── Summary ──────────────────────────────────────────────────────────
unreal.log_warning("")
unreal.log_warning("=" * 60)
if failed == 0:
    unreal.log_warning(f"[VERIFY] ✅ ALL {total} CHECKS PASSED!")
else:
    unreal.log_error(f"[VERIFY] ❌ {failed}/{total} CHECKS FAILED!")
unreal.log_warning("=" * 60)
