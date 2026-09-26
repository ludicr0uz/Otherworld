"""
Auto-generated Unreal verification script for Lvl_Forest_200m.
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

LEVEL_NAME = "Lvl_Forest_200m"
WORLD_SIZE_CM = 20000.0
EXPECTED_TREE_COUNT = 136
EXPECTED_SPEC_COUNTS = {"HISM_Tree_Leafy_Island_01": 28, "HISM_Tree_Leafy_Island_02": 28, "HISM_Tree_Fir_A": 44, "HISM_Tree_Pine_A": 20, "HISM_Tree_Deciduous": 16}
EXPECTED_GRASS_COUNT = 44368
EXPECTED_GRASS_SPEC_COUNTS = {"HISM_Grass_Knee_Tall_C": 6415, "HISM_Grass_Under_Mid_B": 2850, "HISM_Grass_Knee_Tall_B": 7813, "HISM_Grass_Knee_Mid_A": 5862, "HISM_Grass_Knee_Tall_A": 8451, "HISM_Grass_Knee_Clump_C": 5844, "HISM_Grass_Under_Clump_A": 2325, "HISM_Grass_Under_Large_B": 2611, "HISM_Grass_Under_Large_A": 2197}
EXPECTED_GRASS_HEIGHTS = {"HISM_Grass_Knee_Tall_C": [42.242809249629246, 55.199687244614566], "HISM_Grass_Under_Mid_B": [25.503926948960117, 35.99430151464459], "HISM_Grass_Knee_Tall_B": [42.50254371397834, 59.99927478522139], "HISM_Grass_Knee_Mid_A": [40.481314514524335, 50.599412580219756], "HISM_Grass_Knee_Tall_A": [42.50006710260952, 59.99895840027987], "HISM_Grass_Knee_Clump_C": [43.12312612443456, 53.89936647630565], "HISM_Grass_Under_Clump_A": [23.800345353400235, 33.59905037018744], "HISM_Grass_Under_Large_B": [24.65506062683597, 34.79728745482545], "HISM_Grass_Under_Large_A": [22.100624064757703, 31.198261357139028]}
EXPECTED_NPCS = json.loads(r"""[{"x": -2033.79, "y": 7315.62, "z": 618.02, "yaw": 285.54, "distance_cm": 7593.07}, {"x": 4241.23, "y": 6260.28, "z": 520.91, "yaw": 235.88, "distance_cm": 7561.69}, {"x": 6982.28, "y": -3337.22, "z": 718.2, "yaw": 154.45, "distance_cm": 7738.82}, {"x": 2918.4, "y": 6910.06, "z": 497.24, "yaw": 247.1, "distance_cm": 7501.07}, {"x": 7427.7, "y": -2197.98, "z": 598.26, "yaw": 163.52, "distance_cm": 7746.09}]""")
EXPECTED_NPC_RUN_SPEED = 600.0
EXPECTED_MELEE_RANGE = 200.0
EXPECTED_MELEE_DAMAGE = 10.0
EXPECTED_MELEE_INTERVAL = 1.5
EXPECTED_NAV_AGENT_RADIUS = 35.0
EXPECTED_NAV_BOUNDS = json.loads(r"""{"half_xy_cm": 8500.0, "center_z_cm": 354.6, "half_z_cm": 739.54, "terrain_min_z_cm": -184.94, "terrain_max_z_cm": 894.14}""")
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
    npc_actors.sort(key=lambda a: a.get_actor_label())

    # -- The Blueprint assets --
    for path in ("/Game/Forest/NPC/BP_ForestWanderer",
                 "/Game/Forest/NPC/BP_ForestWandererAI"):
        check(f"Asset Exists {path.rsplit('/', 1)[-1]}",
              editor_asset_sub.does_asset_exist(path))

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
              extent.z * 2.0 <= 1600.0,
              f"(span {extent.z * 2.0:.0f} cm, limit 1600)")
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
