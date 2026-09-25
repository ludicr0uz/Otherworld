"""
Auto-generated Unreal verification script for Lvl_Forest_200m.
Verifies collision, materials, actor presence, and tree HISM instances.
"""
import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

LEVEL_NAME = "Lvl_Forest_200m"
WORLD_SIZE_CM = 20000.0
EXPECTED_TREE_COUNT = 136
EXPECTED_SPEC_COUNTS = {"HISM_Tree_Leafy_Island_01": 28, "HISM_Tree_Leafy_Island_02": 28, "HISM_Tree_Fir_A": 44, "HISM_Tree_Pine_A": 20, "HISM_Tree_Deciduous": 16}

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

# ── 3. Lighting & Sky Actors ─────────────────────────────────────────
if "night" != "night":
    sun_actor = next((a for a in actors if a.get_actor_label() == f"{LEVEL_NAME}_Sun"), None)
    check("Sun Light Exists", sun_actor is not None)
    if sun_actor:
        sun_comp = sun_actor.get_component_by_class(unreal.DirectionalLightComponent)
        check("Sun Intensity is 6.0 in Day", sun_comp.get_editor_property("intensity") == 6.0)
        check("Sun Casts Shadows in Day", sun_comp.get_editor_property("cast_shadows") == True)
        check("Sun Atmosphere Light is True in Day", sun_comp.get_editor_property("atmosphere_sun_light") == True)

if "night" == "night":
    moon_actor = next((a for a in actors if a.get_actor_label() == f"{LEVEL_NAME}_Moon"), None)
    check("Moon Light Exists", moon_actor is not None)
    if moon_actor:
        moon_comp = moon_actor.get_component_by_class(unreal.DirectionalLightComponent)
        check("Moon Intensity is 2.0 (Locked Exposure Night)", moon_comp.get_editor_property("intensity") == 2.0)
        check("Moon Atmosphere Light is True", moon_comp.get_editor_property("atmosphere_sun_light") == True)
        check("Moon Index is 0", moon_comp.get_editor_property("atmosphere_sun_light_index") == 0)
        check("Moon Casts Shadows", moon_comp.get_editor_property("cast_shadows") == True)

check("Sky Atmosphere Exists", f"{LEVEL_NAME}_SkyAtmosphere" in actor_labels)
check("Volumetric Cloud Exists", f"{LEVEL_NAME}_VolumetricCloud" in actor_labels)
if "night" != "night":
    check("Sky Sphere Exists", f"{LEVEL_NAME}_SkySphere" in actor_labels)
check("Sky Light Exists", f"{LEVEL_NAME}_SkyLight" in actor_labels)
check("Fog Exists", f"{LEVEL_NAME}_Fog" in actor_labels)

ppv_actor = next((a for a in actors if a.get_actor_label() == f"{LEVEL_NAME}_PostProcess"), None)
check("PostProcess Exists", ppv_actor is not None)
if ppv_actor:
    settings = ppv_actor.get_editor_property("settings")
    min_bright = settings.get_editor_property("auto_exposure_min_brightness")
    bias = settings.get_editor_property("auto_exposure_bias")
    priority = ppv_actor.get_editor_property("priority")

    check("PostProcess Priority is 10.0", priority == 10.0)

    expected_min = 1.0 if "night" == "night" else 0.03
    check(f"PostProcess Min Exposure is {expected_min}", abs(min_bright - expected_min) < 0.01)

    # Check bias
    check(f"PostProcess Bias is 0.0", abs(bias - 0.0) < 0.01)

check("Player Start Exists", f"{LEVEL_NAME}_PlayerStart" in actor_labels)

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

# ── Summary ──────────────────────────────────────────────────────────
unreal.log_warning("")
unreal.log_warning("=" * 60)
if failed == 0:
    unreal.log_warning(f"[VERIFY] ✅ ALL {total} CHECKS PASSED!")
else:
    unreal.log_error(f"[VERIFY] ❌ {failed}/{total} CHECKS FAILED!")
unreal.log_warning("=" * 60)

# ── 5. Runtime Error Checking (PIE) ──────────────────────────────────
unreal.log_warning("[VERIFY] Starting Play-In-Editor (PIE) to check for runtime rendering errors...")
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_play_simulate()

# We will schedule a python tick to stop PIE after 3 seconds and check the log.
import time
import os

start_time = time.time()

def check_pie_log(dt):
    if time.time() - start_time < 3.0:
        return True # continue ticking

    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_end_play()

    # Read the latest Mac Unreal log
    log_path = os.path.expanduser("~/Library/Logs/Unreal Engine/OtherworldEditor/Otherworld.log")
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_data = f.read()

        # Only check the last 20,000 characters to see if it occurred during THIS pie session
        if "Cached lighting in Lumen and real-time sky capture lighting is going to be clipped" in log_data[-20000:]:
            unreal.log_error("❌ [VERIFY] RUNTIME ERROR DETECTED: Lumen cached lighting clipping error! The scene is too pitch black.")
        else:
            unreal.log_warning("✅ [VERIFY] RUNTIME TEST PASSED: No Lumen exposure clipping errors detected during Play!")
    else:
        unreal.log_warning("⚠️ [VERIFY] Could not locate Unreal log file to verify runtime errors.")

    return False # unregister

unreal.register_slate_post_tick_callback(check_pie_log)

