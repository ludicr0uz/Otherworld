"""
Auto-generated Unreal verification script for Lvl_Forest_1000m.
Verifies collision, materials, actor presence, tree and grass HISM
instances (including that grass really is knee high), the NPC and its
navigation rig, and the time-of-day lighting rig.
Time of day: Night — starry sky as the only light source, low luminosity
"""
import json
import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

LEVEL_NAME = "Lvl_Forest_1000m"
WORLD_SIZE_CM = 100000.0
EXPECTED_TREE_COUNT = 3400
EXPECTED_SPEC_COUNTS = {"HISM_Tree_Leafy_Island_01": 700, "HISM_Tree_Leafy_Island_02": 700, "HISM_Tree_Fir_A": 1100, "HISM_Tree_Pine_A": 500, "HISM_Tree_Deciduous": 400}
EXPECTED_GRASS_COUNT = 1115761
EXPECTED_GRASS_SPEC_COUNTS = {"HISM_Grass_Knee_Tall_C": 162526, "HISM_Grass_Under_Mid_B": 73399, "HISM_Grass_Knee_Tall_B": 195411, "HISM_Grass_Knee_Mid_A": 146969, "HISM_Grass_Knee_Tall_A": 211338, "HISM_Grass_Knee_Clump_C": 146558, "HISM_Grass_Under_Clump_A": 57107, "HISM_Grass_Under_Large_B": 65351, "HISM_Grass_Under_Large_A": 57102}
EXPECTED_GRASS_HEIGHTS = {"HISM_Grass_Knee_Tall_C": [42.24006685497192, 55.199893491401276], "HISM_Grass_Under_Mid_B": [25.500140594845533, 35.99955340636545], "HISM_Grass_Knee_Tall_B": [42.50004418637726, 59.9998529540912], "HISM_Grass_Knee_Mid_A": [40.48006467178663, 50.59994909808587], "HISM_Grass_Knee_Tall_A": [42.50012028500365, 59.99984698887548], "HISM_Grass_Knee_Clump_C": [43.12001264538074, 53.89977546867576], "HISM_Grass_Under_Clump_A": [23.80017238514594, 33.59961510198457], "HISM_Grass_Under_Large_B": [24.65018734209176, 34.79986821158218], "HISM_Grass_Under_Large_A": [22.10008810158521, 31.199997158391774]}
EXPECTED_NPCS = json.loads(r"""[{"x": -2157.65, "y": 7761.17, "z": 88.0, "yaw": 285.54, "distance_cm": 8055.51}, {"x": 4415.19, "y": 6517.06, "z": 88.0, "yaw": 235.88, "distance_cm": 7871.84}, {"x": 8000.93, "y": -3824.09, "z": 88.0, "yaw": 154.45, "distance_cm": 8867.84}, {"x": -8035.34, "y": -244.76, "z": 88.0, "yaw": 1.74, "distance_cm": 8039.07}, {"x": -4049.92, "y": 7352.05, "z": 88.0, "yaw": 298.85, "distance_cm": 8393.72}, {"x": -7535.23, "y": 1445.21, "z": 88.0, "yaw": 349.14, "distance_cm": 7672.57}, {"x": -4895.2, "y": 8142.14, "z": 88.0, "yaw": 301.02, "distance_cm": 9500.39}, {"x": 6676.28, "y": 6003.28, "z": 88.0, "yaw": 221.96, "distance_cm": 8978.43}, {"x": -7872.46, "y": 941.5, "z": 88.0, "yaw": 353.18, "distance_cm": 7928.56}, {"x": 675.29, "y": -8803.66, "z": 88.0, "yaw": 94.39, "distance_cm": 8829.52}]""")
EXPECTED_NPC_RUN_SPEED = 600.0
EXPECTED_VARIANTS = json.loads(r"""[{"key": "Zombie", "blueprint": "/Game/Forest/NPC/BP_Wanderer_Zombie", "mesh": "/Game/Sourced/Characters/SKM_Zombie01/SKM_Zombie01", "anim_bp": "/Game/Sourced/Characters/Anims/Zombie01/A_Zombie01_ABP_Unarmed", "melee": "/Game/Sourced/Characters/Anims/Zombie01/A_Zombie01_MM_Attack_01", "ai_blueprint": "/Game/Forest/NPC/BP_ForestWandererAI_Zombie", "health": 100.0, "speed_scale": 1.0, "voices": ["/Game/Audio/A_ZombieGrowl_01", "/Game/Audio/A_ZombieGrowl_02", "/Game/Audio/A_ZombieGrowl_03"]}, {"key": "Wendigo", "blueprint": "/Game/Forest/NPC/BP_Wanderer_Wendigo", "mesh": "/Game/Sourced/Characters/SKM_Wendigo01/SKM_Wendigo01", "anim_bp": "/Game/Sourced/Characters/Anims/Wendigo01/A_Wendigo01_ABP_Unarmed", "melee": "/Game/Sourced/Characters/Anims/Wendigo01/A_Wendigo01_MM_Attack_01", "ai_blueprint": "/Game/Forest/NPC/BP_ForestWandererAI_Wendigo", "health": 300.0, "speed_scale": 1.15, "voices": ["/Game/Audio/A_WendigoRoar_01", "/Game/Audio/A_WendigoRoar_02", "/Game/Audio/A_WendigoRoar_03"]}]""")
# Per-instance {key, rate, speed} -- see
# npc_placement.gait_scale_for_index and NpcVariant.speed_scale.
EXPECTED_NPC_GAITS = json.loads(r"""[{"key": "Zombie", "rate": 1.0188854381999832, "speed": 611.33126291999}, {"key": "Zombie", "rate": 0.9577708763999664, "speed": 574.6625258399798}, {"key": "Zombie", "rate": 1.0566563145999497, "speed": 633.9937887599698}, {"key": "Zombie", "rate": 0.9955417527999327, "speed": 597.3250516799596}, {"key": "Wendigo", "rate": 1.0745912696499034, "speed": 644.754761789942}, {"key": "Zombie", "rate": 1.033312629199899, "speed": 619.9875775199395}, {"key": "Zombie", "rate": 0.9721980673998823, "speed": 583.3188404399294}, {"key": "Zombie", "rate": 1.0710835055998655, "speed": 642.6501033599193}, {"key": "Zombie", "rate": 1.0099689437998487, "speed": 605.9813662799093}, {"key": "Wendigo", "rate": 1.0911825392998065, "speed": 654.709523579884}]""")
EXPECTED_MELEE_RANGE = 200.0
EXPECTED_MELEE_DAMAGE = 10.0
EXPECTED_MELEE_INTERVAL = 1.5
EXPECTED_NAV_AGENT_RADIUS = 35.0
EXPECTED_REACHABLE_EXTENT = (200.0, 200.0, 400.0)
EXPECTED_NAV_BOUNDS = json.loads(r"""{"half_xy_cm": 50000.0, "center_z_cm": 999.88, "half_z_cm": 1799.77, "terrain_min_z_cm": -599.9, "terrain_max_z_cm": 2599.65}""")
LIGHTING = json.loads(r"""{"key": "night", "label": "Night \u2014 starry sky as the only light source, low luminosity", "sun": {"enabled": true, "label_suffix": "Moon", "intensity": 0.12, "color": [170, 195, 255], "pitch": -32.0, "yaw": 120.0, "cast_shadows": true, "shadow_distance_cm": 10000.0}, "sky_light": {"intensity": 3.0, "real_time_capture": true}, "sky_dome": {"enabled": true, "material": "/Game/Forest/Materials/M_NightSky_Starfield", "build_starfield": true, "star_brightness": 2.5, "night_sky_color": [0.004, 0.008, 0.022, 1.0], "star_tiling": [2.0, 1.0]}, "volumetric_cloud": {"enabled": false}, "fog": {"density": 0.035, "inscattering_color": [0.015, 0.025, 0.055], "enable_volumetric": true, "volumetric_extinction_scale": 0.6}, "post_process": {"auto_exposure_min_brightness": 0.004, "auto_exposure_max_brightness": 0.6, "auto_exposure_bias": 1.6}}""")

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
            dist = dlc.get_editor_property("dynamic_shadow_distance_movable_light")
            check("Directional Light Shadow Distance",
                  close(dist, sun_cfg["shadow_distance_cm"], 1.0),
                  f"(expected {sun_cfg['shadow_distance_cm']} cm, got {dist})")

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
import sys
if r"/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts" not in sys.path:
    sys.path.insert(0, r"/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts")
from forest_import import trees as trees_import
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
                trees_import.verify_tree_component(check, spec_name, root)
            break
    check(f"{spec_name} Actor Exists", found)

check("Total Tree Instances",
      total_tree_instances == EXPECTED_TREE_COUNT,
      f"(expected {EXPECTED_TREE_COUNT}, got {total_tree_instances})")

# ── 5. Grass cells (forest_import/grass.py) ─────────────────────────
if EXPECTED_GRASS_COUNT > 0:
    import sys
    if r"/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts" not in sys.path:
        sys.path.insert(0, r"/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts")
    from forest_import import grass as grass_import
    grass_import.verify_grass(check, actors, EXPECTED_GRASS_SPEC_COUNTS,
                              EXPECTED_GRASS_HEIGHTS, EXPECTED_GRASS_COUNT)

# ── 6. Navigation + NPCs ─────────────────────────────────────────────
if EXPECTED_NPCS:
    npc_actors = []
    nav_bounds = None
    nav_mesh = None
    for a in actors:
        lbl = a.get_actor_label()
        if lbl.startswith(f"{LEVEL_NAME}_NPC_Wanderer"):
            npc_actors.append(a)
        elif lbl == f"{LEVEL_NAME}_NavBounds":
            nav_bounds = a
        elif lbl == f"{LEVEL_NAME}_NavMesh":
            nav_mesh = a
    # Sort by the label's trailing NUMBER, not by the label. The
    # wanderers are checked against EXPECTED_NPCS pairwise by position,
    # and a plain string sort puts "_10" between "_1" and "_2" -- so
    # every NPC from the second one on is compared against its
    # neighbour's expected spawn point and all of them fail, while the
    # placement itself is perfectly correct. Invisible below ten.
    def _npc_index(actor):
        tail = actor.get_actor_label().rsplit("_", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    npc_actors.sort(key=_npc_index)

    # -- The Blueprint assets --
    for path in (["/Game/Forest/NPC/BP_ForestWanderer",
                  "/Game/Forest/NPC/BP_ForestWandererAI"]
                 + [v["blueprint"] for v in EXPECTED_VARIANTS]
                 + [v["ai_blueprint"] for v in EXPECTED_VARIANTS]):
        check(f"Asset Exists {path.rsplit('/', 1)[-1]}",
              editor_asset_sub.does_asset_exist(path))

    # Each creature must animate against ITS OWN skeleton. Sharing one
    # skeleton across monsters is what put the wendigo's forward neck
    # pitch on the zombie and left its head hanging off the front of
    # its chest -- and nothing errored, at build time or at runtime.
    # This is the check that would have caught it.
    seen_skeletons = {}
    for variant in EXPECTED_VARIANTS:
        bp = editor_asset_sub.load_asset(variant["blueprint"])
        if not bp:
            check(f"{variant['key']} Blueprint Loads", False)
            continue
        cdo = unreal.get_default_object(
            unreal.BlueprintEditorLibrary.generated_class(bp))
        comp = cdo.get_editor_property("mesh")
        mesh = comp.get_editor_property("skeletal_mesh_asset")
        anim_cls = comp.get_editor_property("anim_class")
        mesh_skel = mesh.get_editor_property("skeleton") if mesh else None

        check(f"{variant['key']} Wears Its Own Mesh",
              mesh is not None and variant["mesh"].endswith(mesh.get_name()),
              f"(got {mesh.get_name() if mesh else None})")

        anim_skel = None
        if anim_cls:
            anim_bp = editor_asset_sub.load_asset(variant["anim_bp"])
            if anim_bp:
                anim_skel = anim_bp.get_editor_property("target_skeleton")
        check(f"{variant['key']} Anim BP Matches Its Skeleton",
              anim_skel is not None and anim_skel == mesh_skel,
              f"(mesh on {mesh_skel.get_name() if mesh_skel else None}, "
              f"anim BP on {anim_skel.get_name() if anim_skel else None})")

        melee = editor_asset_sub.load_asset(variant["melee"])
        check(f"{variant['key']} Attack Clip Matches Its Skeleton",
              melee is not None
              and melee.get_editor_property("skeleton") == mesh_skel,
              f"(clip on "
              f"{melee.get_editor_property('skeleton').get_name() if melee else None})")

        # Its own run speed, on the pawn. The wendigo is meant to be
        # 15% faster than the zombie and the only place that can be
        # said is CharacterMovement's own default, so it is the only
        # place worth checking.
        want_speed = EXPECTED_NPC_RUN_SPEED * variant["speed_scale"]
        got_speed = cdo.get_editor_property(
            "character_movement").get_editor_property("max_walk_speed")
        check(f"{variant['key']} Runs At Its Own Speed",
              close(got_speed, want_speed, 0.5),
              f"(wanted {want_speed:.0f} cm/s, got {got_speed:.0f})")

        # Its own health and its own voice, both of which live on its
        # AI controller -- MaxHealth is on an INHERITED component and
        # Unreal keeps a child Blueprint's override of one somewhere
        # Python cannot reach, so the controller applies it on
        # possession instead. That indirection is exactly the sort of
        # thing that silently stops working, hence the check.
        ai = editor_asset_sub.load_asset(variant["ai_blueprint"])
        ai_cdo = unreal.get_default_object(
            unreal.BlueprintEditorLibrary.generated_class(ai)) if ai else None
        voices = (list(ai_cdo.get_editor_property("Voices"))
                  if ai_cdo else [])
        hits = (list(ai_cdo.get_editor_property("HitSounds"))
                if ai_cdo else [])
        check(f"{variant['key']} Has Its Own Voice",
              len(voices) == len(variant["voices"]) and len(voices) > 0,
              f"(wanted {len(variant['voices'])} clips, got {len(voices)})")
        check(f"{variant['key']} Has Melee Impact Sounds",
              len(hits) > 0, f"(got {len(hits)})")

        # ...and that both arrays are heard from where the creature is.
        # A SoundWave with no AttenuationSettings is not quietly
        # defaulted: it plays at full volume, centred, from anywhere on
        # the 200 m map, which sounds exactly like a working sound
        # until you walk away from it.
        flat = [s.get_name() for s in voices + hits
                if s is None
                or s.get_editor_property("attenuation_settings") is None]
        check(f"{variant['key']} Is Heard From Where It Stands",
              not flat and len(voices + hits) > 0,
              f"(unattenuated: {flat})")

        # Footsteps, on the wanderer as well as on the player.
        foot = None
        for handle in unreal.get_engine_subsystem(
                unreal.SubobjectDataSubsystem).k2_gather_subobject_data_for_blueprint(bp):
            obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(
                unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
            if obj and "Footstep" in obj.get_name():
                foot = obj
        check(f"{variant['key']} Has Footsteps", foot is not None)

        if mesh_skel:
            seen_skeletons.setdefault(mesh_skel.get_name(), []).append(
                variant["key"])

    shared = {k: v for k, v in seen_skeletons.items() if len(v) > 1}
    check("Each Creature Has Its Own Skeleton", not shared,
          f"(shared: {shared} -- one of these wears another's bind pose)")

    npc_bp = editor_asset_sub.load_asset("/Game/Forest/NPC/BP_ForestWanderer")
    if npc_bp:
        cdo = unreal.get_default_object(
            unreal.BlueprintEditorLibrary.generated_class(npc_bp))
        ai_cls = cdo.get_editor_property("ai_controller_class")
        check("NPC AI Controller Class",
              ai_cls is not None and "ForestWandererAI" in str(ai_cls),
              f"(got {ai_cls})")
        check("NPC Auto Possess AI",
              cdo.get_editor_property("auto_possess_ai") ==
              unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
        mv = cdo.get_editor_property("character_movement")
        speed = mv.get_editor_property("max_walk_speed")
        check("NPC Runs At The Player",
              close(speed, EXPECTED_NPC_RUN_SPEED, 0.5),
              f"(expected {EXPECTED_NPC_RUN_SPEED} cm/s, got {speed})")
        check("NPC Orients To Movement",
              mv.get_editor_property("orient_rotation_to_movement") is True)
        mesh_comp = cdo.get_editor_property("mesh")
        check("NPC Has Skeletal Mesh",
              mesh_comp.get_editor_property("skeletal_mesh_asset") is not None)
        check("NPC Animation Mode Blueprint",
              mesh_comp.get_editor_property("animation_mode") ==
              unreal.AnimationMode.ANIMATION_BLUEPRINT,
              f"(got {mesh_comp.get_editor_property('animation_mode')})")
        check("NPC Has Anim Class",
              mesh_comp.get_editor_property("anim_class") is not None)

    # -- The melee attack, read off the controller's own graph --
    # Pin literals rather than behaviour: a headless editor cannot run
    # the chase, but a swing that costs 0 damage or fires at a range of
    # 0 is exactly what an unset pin compiles to (see the set_pin_value
    # gotcha in CLAUDE.md), so the numbers are worth asserting.
    ai_bp = editor_asset_sub.load_asset("/Game/Forest/NPC/BP_ForestWandererAI")
    if ai_bp:
        BEL = unreal.BlueprintEditorLibrary
        ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(
            ai_bp, "EventGraph")
        nodes = ed.list_all_nodes() if ed else []
        literals = set()
        for n in nodes:
            for pin in BEL.list_input_pins(n):
                val = str(unreal.BlueprintGraphPinLibrary.get_pin_value(pin))
                if val:
                    literals.add(val)
        names = {str(v) for v in BEL.list_member_variable_names(ai_bp, False)}
        check("NPC Melee Cooldown Variable", "NextAttackTime" in names,
              f"(variables: {sorted(names)})")
        for label, value in (("Range", EXPECTED_MELEE_RANGE),
                             ("Damage", EXPECTED_MELEE_DAMAGE),
                             ("Interval", EXPECTED_MELEE_INTERVAL)):
            check(f"NPC Melee {label} Literal",
                  any(close(float(v), value, 0.01)
                      for v in literals
                      if v.replace(".", "", 1).replace("-", "", 1).isdigit()),
                  f"(expected {value})")
        check("NPC Melee Plays An Attack Montage",
              any("MM_Attack" in v for v in literals))
        check("NPC Melee Uses The Upper-Body Slot",
              any(v == "DefaultSlot" for v in literals))
        check("NPC Graph Compiles Clean",
              ed is not None and not ed.list_nodes_with_errors())
        # Debugging the chase means splicing PrintStrings into this
        # graph (it is the only way to see what the AI is measuring),
        # so guard against one being left behind. Two are meant to be
        # there -- the combat trace and the corpse state's one line --
        # and each is told apart by the literal its text starts with.
        def _line_head(n):
            pin = BEL.find_input_pin(n, "InString")
            for _ in range(40):
                fed = unreal.BlueprintGraphPinLibrary.list_connected_pins(pin)
                if not fed:
                    return str(unreal.BlueprintGraphPinLibrary.get_pin_value(pin))
                pin = BEL.find_input_pin(
                    unreal.BlueprintGraphPinLibrary.get_owning_node(fed[0]), "A")
                if pin is None:
                    return ""
            return ""
        stray = [n for n in nodes
                 if "PrintString" in " ".join(str(BEL.get_node_title(n)).split())
                 and not _line_head(n).startswith(("[COMBAT-TRACE]", "[NPC-CORPSE]"))]
        check("No Leftover Debug PrintStrings In The AI Graph", not stray,
              f"({len(stray)} unexplained)")
        # A controller's BeginPlay runs before it possesses anything,
        # so the first pass through the chase loop has no pawn: the
        # melee chain then reads a location off None and the VM logs an
        # "Accessed None ... K2_GetPawn_ReturnValue" error once per
        # spawned NPC. The gate has to be an exec branch ahead of
        # MoveToActor -- folding IsValid into the melee AND would not
        # help, since BooleanAND reads both pins and so still pulls the
        # location chain.
        PIN = unreal.BlueprintGraphPinLibrary
        def ins(n):
            return {str(PIN.get_pin_name(q))
                    for q in BEL.list_input_pins(n)}
        moves = [n for n in nodes
                 if {"Goal", "AcceptanceRadius"} <= ins(n)]
        check("NPC Chase Has One Move Order", len(moves) == 1,
              f"(got {len(moves)})")
        if moves:
            drivers = [PIN.get_owning_node(q) for q in
                       BEL.find_execute_pin(moves[0]).list_connected_pins()]
            check("NPC Chase Is Gated On Possession",
                  bool(drivers) and all(
                      d.get_class().get_name() == "K2Node_IfThenElse"
                      for d in drivers),
                  f"(driven by {[d.get_class().get_name() for d in drivers]})")
            check("NPC Possession Gate Asks IsValid",
                  any("IsValid" ==
                      " ".join(str(BEL.get_node_title(n)).split())
                      for n in nodes))

        # -- Chasing off the navmesh --
        # The navmesh now covers the whole terrain, so the 15 m ring of
        # un-navigable ground that used to surround the map -- where a
        # player was simply unreachable, and where MoveToActor's
        # bAllowPartialPath meant the request SUCCEEDED at the island
        # edge rather than failing -- is gone.  The straight-line
        # fallback stays as a net for the corner ramps Recast refuses
        # to build on, and these check it is still wired correctly.
        direct = [n for n in nodes
                  if {"Dest", "bUsePathfinding"} <= ins(n)]
        check("NPC Has A Straight-Line Move Order", len(direct) == 1,
              f"(got {len(direct)})")
        if direct:
            def lit(node, pin):
                return str(PIN.get_pin_value(
                    BEL.find_input_pin(node, pin)))
            check("Straight-Line Order Does Not Pathfind",
                  lit(direct[0], "bUsePathfinding") == "false",
                  f"(got {lit(direct[0], 'bUsePathfinding')})")
            # The whole bug, restated: projecting the destination back
            # onto the navmesh walks the NPC to the island edge and
            # stops it there, which is exactly what it used to do.
            check("Straight-Line Order Keeps The Real Destination",
                  lit(direct[0], "bProjectDestinationToNavigation")
                  == "false",
                  f"(got {lit(direct[0], 'bProjectDestinationToNavigation')})")
            check("Pathfinding Order Still Pathfinds",
                  lit(moves[0], "bUsePathfinding") == "true"
                  if moves else False)
        # Both ends are tested -- the player may have walked off the
        # navmesh, and so may the wanderer.
        projections = [n for n in nodes
                       if {"Point", "QueryExtent"} <= ins(n)]
        check("Reachability Tests Both Ends Of The Chase",
              len(projections) == 2, f"(got {len(projections)})")
        # A loose query box answers "yes, reachable" for a player ten
        # metres outside the island by snapping to its edge, which is
        # the dead zone with extra steps.  A tight one in Z reports a
        # player standing squarely ON the navmesh as being off it,
        # because the point is a capsule centre and a Recast polygon
        # can sit most of a metre under the real ground.
        extents = [n for n in nodes if {"X", "Y", "Z"} <= ins(n)]
        want_extent = [f"{v:.1f}" for v in EXPECTED_REACHABLE_EXTENT]
        check("Reachability Query Box Matches The Constant",
              any([str(PIN.get_pin_value(BEL.find_input_pin(n, a)))
                   for a in ("X", "Y", "Z")] == want_extent
                  for n in extents),
              f"(expected {want_extent})")
        # One branch, feeding both move orders: the pathfinding one on
        # True and the straight line on False.
        if direct and moves:
            def driver_of(node):
                pins = BEL.find_execute_pin(node).list_connected_pins()
                return {PIN.get_owning_node(q) for q in pins}
            shared = driver_of(moves[0]) & driver_of(direct[0])
            check("One Branch Chooses Between The Two Move Orders",
                  len(shared) == 1 and next(iter(shared)).get_class()
                  .get_name() == "K2Node_IfThenElse",
                  f"(shared drivers: {len(shared)})")

    # -- The placed actors --
    check("NPC Count",
          len(npc_actors) == len(EXPECTED_NPCS),
          f"(expected {len(EXPECTED_NPCS)}, got {len(npc_actors)})")
    for i, (actor, want) in enumerate(zip(npc_actors, EXPECTED_NPCS),
                                      start=1):
        loc = actor.get_actor_location()
        check(f"NPC {i} Spawn Location",
              close(loc.x, want["x"], 1.0)
              and close(loc.y, want["y"], 1.0)
              and close(loc.z, want["z"], 1.0),
              f"(expected {want['x']:.0f},{want['y']:.0f},{want['z']:.0f} "
              f"got {loc.x:.0f},{loc.y:.0f},{loc.z:.0f})")
        dist = (loc.x ** 2 + loc.y ** 2) ** 0.5
        check(f"NPC {i} In The Spawn Band",
              close(dist, want["distance_cm"], 2.0),
              f"({dist / 100.0:.1f} m from the player start)")
        check(f"NPC {i} Is A Character",
              isinstance(actor, unreal.Character))

    # -- Navigation rig --
    check("Nav Bounds Volume Exists", nav_bounds is not None)
    if nav_bounds and EXPECTED_NAV_BOUNDS:
        origin, extent = nav_bounds.get_actor_bounds(False)
        want_xy = EXPECTED_NAV_BOUNDS["half_xy_cm"]
        want_z = EXPECTED_NAV_BOUNDS["half_z_cm"]
        check("Nav Bounds XY Extent",
              close(extent.x, want_xy, 2.0) and close(extent.y, want_xy, 2.0),
              f"(expected +/-{want_xy:.0f}, got {extent.x:.0f}x{extent.y:.0f})")
        check("Nav Bounds Z Extent",
              close(extent.z, want_z, 2.0),
              f"(expected +/-{want_z:.0f}, got {extent.z:.0f})")
        check("Nav Bounds Centred On Terrain",
              close(origin.z, EXPECTED_NAV_BOUNDS["center_z_cm"], 2.0),
              f"(expected z {EXPECTED_NAV_BOUNDS['center_z_cm']:.0f}, "
              f"got {origin.z:.0f})")
        # The bug that made the NPC immobile: an over-tall volume makes
        # Recast generate no tiles at all.
        check("Nav Bounds Vertical Span Sane",
              extent.z * 2.0 <= 5000.0,
              f"(span {extent.z * 2.0:.0f} cm, limit 5000)")
        # Lockstep guard: every wanderer must have its own gait, and
        # its animation rate must match its ground speed or its feet
        # skate.  A regression here is invisible in a screenshot and
        # obvious in motion, which is exactly why it is checked.
        gaits, mismatched, skating = [], [], []
        for i, actor in enumerate(npc_actors, start=1):
            want = EXPECTED_NPC_GAITS[i - 1]
            rate = actor.get_editor_property("mesh").get_editor_property(
                "global_anim_rate_scale")
            speed = actor.get_editor_property(
                "character_movement").get_editor_property("max_walk_speed")
            gaits.append(round(rate, 4))
            if not (close(rate, want["rate"], 0.001)
                    and close(speed, want["speed"], 0.5)):
                mismatched.append(
                    f"NPC {i} ({want['key']}) rate {rate:.3f} "
                    f"speed {speed:.1f} (wanted {want['rate']:.3f} / "
                    f"{want['speed']:.1f})")
            # The invariant behind both numbers, checked directly:
            # ground covered per second divided by animation rate must
            # be the speed the locomotion was authored at. If it is
            # not, the feet skate -- and that is exactly the failure a
            # per-creature speed multiplier introduces if the rate is
            # left alone.
            if rate > 1e-6 and not close(speed / rate,
                                         EXPECTED_NPC_RUN_SPEED, 1.0):
                skating.append(
                    f"NPC {i} ({want['key']}) {speed:.0f} cm/s at "
                    f"x{rate:.3f} = {speed / rate:.0f} cm/s of stride")
        check("NPC Gaits Are Staggered", len(set(gaits)) == len(gaits),
              f"(rates {sorted(gaits)} -- duplicates march in lockstep)")
        check("NPC Anim Rate Matches Ground Speed", not mismatched,
              "; ".join(mismatched))
        check("NPC Strides Stay Planted", not skating,
              "; ".join(skating) +
              f" (stride speed must be {EXPECTED_NPC_RUN_SPEED:.0f})")

        # Every NPC must stand inside the volume or it has no navmesh.
        outside = []
        for i, actor in enumerate(npc_actors, start=1):
            loc = actor.get_actor_location()
            feet_z = loc.z - 88.0
            if not (abs(loc.x) <= want_xy and abs(loc.y) <= want_xy
                    and abs(feet_z - origin.z) <= want_z):
                outside.append(f"NPC {i} at ({loc.x:.0f},{loc.y:.0f},"
                               f"feet {feet_z:.0f})")
        check("NPCs Inside Nav Bounds", not outside,
              f"(volume {origin.z - want_z:.0f}..{origin.z + want_z:.0f}"
              f"{'; outside: ' + ', '.join(outside) if outside else ''})")
    # NOTE: whether stale nav data was SAVED cannot be asserted from
    # here -- opening the level makes the navigation system create a
    # RecastNavMesh in memory, so one is always present in an editor
    # session regardless of what is on disk.  The import script strips
    # nav data immediately before saving; the real gate is the runtime
    # check documented in systemDesign.md (grep the game log for
    # "Building tile", which must be non-zero).

# ── Summary ──────────────────────────────────────────────────────────
unreal.log_warning("")
unreal.log_warning("=" * 60)
if failed == 0:
    unreal.log_warning(f"[VERIFY] ✅ ALL {total} CHECKS PASSED!")
else:
    unreal.log_error(f"[VERIFY] ❌ {failed}/{total} CHECKS FAILED!")
unreal.log_warning("=" * 60)
