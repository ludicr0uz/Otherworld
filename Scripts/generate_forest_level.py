#!/usr/bin/env python3
"""
generate_forest_level.py — End-to-end forest level generator + verifier.

Usage:
    python3 Scripts/generate_forest_level.py --size 200
    python3 Scripts/generate_forest_level.py --size 400 --name Lvl_BigForest --seed 99

This script:
  1. Generates a terrain OBJ mesh (pure Python)
  2. Scatters trees with exact terrain snapping (pure Python)
  3. Runs 12+ offline verification checks
  4. Writes an Unreal Python script to import everything into the editor
  5. Prints a command to run the import inside UnrealEditor-Cmd
"""

import argparse
import json
import os
import sys
import textwrap

# Add parent directory so forest_generator package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forest_generator.terrain import (
    generate_terrain_obj,
    compute_grid,
    make_elevation_fn,
    get_exact_mesh_z,
)
from forest_generator.tree_placement import (
    scatter_trees,
    DEFAULT_TREE_SPECS,
)
from forest_generator.verification import run_all_checks


# ─── Constants ───────────────────────────────────────────────────────────────

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "Scripts")
UE_CMD = "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd"
UPROJECT = os.path.join(PROJECT_DIR, "Otherworld.uproject")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate a forest level for Otherworld")
    parser.add_argument("--size", type=float, required=True,
                        help="Map side length in METERS (e.g. 200 for 200m×200m)")
    parser.add_argument("--name", type=str, default=None,
                        help="Level name (default: Lvl_Forest_<size>m)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for tree placement")
    parser.add_argument("--grid", type=int, default=None,
                        help="Grid resolution (auto if omitted)")
    parser.add_argument("--time", type=str, choices=["day", "night"], default="day",
                        help="Time of day for the level's lighting (day or night)")
    parser.add_argument("--json-report", type=str, default=None,
                        help="Path to write JSON verification report")
    args = parser.parse_args()

    world_size_m = args.size
    world_size_cm = world_size_m * 100.0
    level_name = args.name or f"Lvl_Forest_{int(world_size_m)}m"

    output_dir = os.path.join(SCRIPTS_DIR, "generated_levels", level_name)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'═' * 60}")
    print(f"  Forest Level Generator — {level_name}")
    print(f"  Map size: {world_size_m}m × {world_size_m}m")
    print(f"  Seed: {args.seed}")
    print(f"{'═' * 60}\n")

    # ── Step 1: Generate terrain mesh ────────────────────────────────────
    obj_path = os.path.join(output_dir, f"SM_{level_name}_Terrain.obj")
    print(f"[1/4] Generating terrain mesh → {obj_path}")
    terrain = generate_terrain_obj(obj_path, world_size_cm, grid_size=args.grid)
    grid_size = terrain["grid_size"]
    grid_z = terrain["grid_z"]
    print(f"       Grid: {grid_size}×{grid_size} ({grid_size**2} quads)")
    print(f"       File: {terrain['bytes']:,} bytes")

    # ── Step 2: Scatter trees ────────────────────────────────────────────
    print(f"\n[2/4] Scattering trees (seed={args.seed})...")
    placed_trees = scatter_trees(
        world_size_cm=world_size_cm,
        grid_z=grid_z,
        grid_size=grid_size,
        seed=args.seed,
    )

    # Count per spec
    from collections import Counter
    counts = Counter(t.spec_name for t in placed_trees)
    for name, cnt in sorted(counts.items()):
        print(f"       {name}: {cnt} instances")
    print(f"       TOTAL: {len(placed_trees)} trees")

    # ── Step 3: Run verification ─────────────────────────────────────────
    print(f"\n[3/4] Running verification suite...")
    report = run_all_checks(
        level_name=level_name,
        world_size_cm=world_size_cm,
        obj_path=obj_path,
        grid_z=grid_z,
        grid_size=grid_size,
        placed_trees=placed_trees,
    )
    print()
    print(report.summary)
    print()

    json_path = args.json_report or os.path.join(output_dir, "verification_report.json")
    report.to_json(json_path)
    print(f"       Report saved → {json_path}")

    if not report.all_passed:
        print("\n⚠️  Verification failed — fix issues before importing into Unreal!")
        sys.exit(1)

    # ── Step 4: Write Unreal import script ───────────────────────────────
    print(f"\n[4/4] Writing Unreal import script...")
    ue_script_path = os.path.join(output_dir, f"import_{level_name}.py")
    _write_unreal_import_script(
        ue_script_path,
        level_name=level_name,
        obj_path=obj_path,
        world_size_cm=world_size_cm,
        grid_size=grid_size,
        placed_trees=placed_trees,
        time_of_day=args.time,
    )
    print(f"       Script → {ue_script_path}")

    # ── Step 5: Write Unreal verification script ─────────────────────────
    ue_verify_path = os.path.join(output_dir, f"verify_{level_name}.py")
    _write_unreal_verify_script(
        ue_verify_path,
        level_name=level_name,
        world_size_cm=world_size_cm,
        grid_size=grid_size,
        placed_trees=placed_trees,
        time_of_day=args.time,
    )
    print(f"       Verify → {ue_verify_path}")

    print(f"\n{'═' * 60}")
    print(f"  ✅ Generation complete!")
    print(f"")
    print(f"  To import into Unreal Editor:")
    print(f"  \"{UE_CMD}\" \"{UPROJECT}\" \\")
    print(f"    -ExecutePythonScript=\"{ue_script_path}\" -NoUI -stdout")
    print(f"")
    print(f"  To verify in Unreal (collision, materials, actors):")
    print(f"  \"{UE_CMD}\" \"{UPROJECT}\" \\")
    print(f"    -ExecutePythonScript=\"{ue_verify_path}\" -NoUI -stdout")
    print(f"{'═' * 60}\n")


# ─── Unreal import script generator ─────────────────────────────────────────

def _write_unreal_import_script(
    script_path: str,
    level_name: str,
    obj_path: str,
    world_size_cm: float,
    grid_size: int,
    placed_trees,
    time_of_day: str = "day",
):
    """Generate a self-contained Unreal Python script that imports everything."""

    # Serialize tree placements to embed in the script
    tree_data = []
    for t in placed_trees:
        tree_data.append({
            "spec": t.spec_name,
            "x": round(t.x, 2),
            "y": round(t.y, 2),
            "z": round(t.placed_z, 2),
            "yaw": round(t.yaw_deg, 2),
            "scale": round(t.scale, 3),
        })

    # Build the elevation function source so the verify script can use it
    elev_fn = make_elevation_fn(world_size_cm)

    # UV tiling scales with world size (target ~10m per tile for micro)
    micro_tiling = max(5.0, world_size_cm / 500.0)
    macro_tiling = max(1.0, world_size_cm / 16000.0)

    script = textwrap.dedent(f'''\
        """
        Auto-generated Unreal import script for {level_name}.
        Generated by generate_forest_level.py
        World size: {world_size_cm / 100.0}m × {world_size_cm / 100.0}m
        """
        import json
        import os
        import unreal

        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
        editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        mel = unreal.MaterialEditingLibrary

        LEVEL_NAME = "{level_name}"
        WORLD_SIZE_CM = {world_size_cm}
        OBJ_PATH = r"{obj_path}"
        MESH_ASSET_NAME = "SM_{level_name}_Terrain"
        MESH_CONTENT_PATH = "/Game/Forest/Test/" + MESH_ASSET_NAME

        unreal.log_warning("=" * 60)
        unreal.log_warning(f"[GEN] Importing {{LEVEL_NAME}} ({{WORLD_SIZE_CM / 100.0}}m x {{WORLD_SIZE_CM / 100.0}}m)")
        unreal.log_warning("=" * 60)

        # ── 1. Import OBJ terrain mesh ───────────────────────────────────────
        unreal.log_warning("[GEN] 1. Importing terrain mesh...")
        task = unreal.AssetImportTask()
        task.filename = OBJ_PATH
        task.destination_path = "/Game/Forest/Test"
        task.destination_name = MESH_ASSET_NAME
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])

        terrain_mesh = editor_asset_sub.load_asset(
            MESH_CONTENT_PATH + "." + MESH_ASSET_NAME
        )
        if not terrain_mesh:
            unreal.log_error(f"[GEN] FAILED to import terrain mesh from {{OBJ_PATH}}")
        else:
            # Disable Nanite, enable complex collision
            nanite = terrain_mesh.get_editor_property("nanite_settings")
            if nanite:
                nanite.set_editor_property("enabled", False)
                terrain_mesh.set_editor_property("nanite_settings", nanite)

            body_setup = terrain_mesh.get_editor_property("body_setup")
            if body_setup:
                body_setup.set_editor_property(
                    "collision_trace_flag",
                    unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
                )

            terrain_mesh.set_editor_property("allow_cpu_access", True)

            # Assign ground material
            ground_mat = editor_asset_sub.load_asset(
                "/Game/Forest/Materials/M_Forest_Ground_PBR.M_Forest_Ground_PBR"
            )
            if ground_mat:
                terrain_mesh.set_material(0, ground_mat)

            editor_asset_sub.save_loaded_asset(terrain_mesh)
            unreal.log_warning("[GEN] Terrain mesh imported with complex collision enabled!")

        # ── 2. Create / load the level ───────────────────────────────────────
        unreal.log_warning("[GEN] 2. Creating level...")
        map_path = f"/Game/Maps/{{LEVEL_NAME}}"

        if editor_asset_sub.does_asset_exist(map_path):
            level_editor_sub.load_level(map_path)
            # Remove existing generated actors to allow clean re-generation
            for a in editor_actor_sub.get_all_level_actors():
                lbl = a.get_actor_label()
                if lbl.startswith(LEVEL_NAME) or lbl.startswith("HISM_Tree"):
                    editor_actor_sub.destroy_actor(a)
        else:
            level_editor_sub.new_level(map_path)

        # ── 3. Spawn terrain actor ───────────────────────────────────────────
        unreal.log_warning("[GEN] 3. Spawning terrain actor...")
        terrain_actor = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(0, 0, 0),
            unreal.Rotator(0, 0, 0),
        )
        terrain_actor.set_actor_label(f"{{LEVEL_NAME}}_Terrain")
        smc = terrain_actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.set_static_mesh(terrain_mesh)
            smc.set_collision_profile_name("BlockAll")
            smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            smc.set_mobility(unreal.ComponentMobility.STATIC)

        # ── 4. Spawn lighting & Sky Atmosphere System ────────────────────────
        unreal.log_warning("[GEN] 4. Setting up lighting and sky atmosphere...")

        is_night = "{time_of_day}" == "night"

        # Directional Light (Primary Light Source)
        if not is_night:
            # DAY: Spawn Sun
            sun = editor_actor_sub.spawn_actor_from_class(
                unreal.DirectionalLight,
                unreal.Vector(0, 0, 5000),
                unreal.Rotator(-50, -30, 0),
            )
            sun.set_actor_label(f"{{LEVEL_NAME}}_Sun")
            sun_comp = sun.get_component_by_class(unreal.DirectionalLightComponent)
            if sun_comp:
                sun_comp.set_editor_property("intensity", 6.0)
                sun_comp.set_editor_property("light_color", unreal.Color(r=255, g=248, b=235, a=255))
                sun_comp.set_editor_property("cast_shadows", True)
                sun_comp.set_editor_property("atmosphere_sun_light", True)
                sun_comp.set_editor_property("atmosphere_sun_light_index", 0)
        else:
            # NIGHT: Spawn Moon (as the only directional light, index 0)
            moon = editor_actor_sub.spawn_actor_from_class(
                unreal.DirectionalLight,
                unreal.Vector(0, 0, 5000),
                unreal.Rotator(-60, 150, 0),
            )
            moon.set_actor_label(f"{{LEVEL_NAME}}_Moon")
            moon_comp = moon.get_component_by_class(unreal.DirectionalLightComponent)
            if moon_comp:
                moon_comp.set_editor_property("intensity", 2.0)
                moon_comp.set_editor_property("light_color", unreal.Color(r=150, g=180, b=255, a=255))
                moon_comp.set_editor_property("cast_shadows", True)
                moon_comp.set_editor_property("atmosphere_sun_light", True)
                moon_comp.set_editor_property("atmosphere_sun_light_index", 0)

        # SkyAtmosphere Component / Actor
        sky_atmo = editor_actor_sub.spawn_actor_from_class(
            unreal.SkyAtmosphere,
            unreal.Vector(0, 0, 0),
            unreal.Rotator(0, 0, 0),
        )
        sky_atmo.set_actor_label(f"{{LEVEL_NAME}}_SkyAtmosphere")

        # VolumetricCloud Actor
        vol_cloud = editor_actor_sub.spawn_actor_from_class(
            unreal.VolumetricCloud,
            unreal.Vector(0, 0, 0),
            unreal.Rotator(0, 0, 0),
        )
        vol_cloud.set_actor_label(f"{{LEVEL_NAME}}_VolumetricCloud")
        vc_comp = vol_cloud.get_component_by_class(unreal.VolumetricCloudComponent)
        if vc_comp:
            cloud_mat = editor_asset_sub.load_asset("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst")
            if cloud_mat:
                vc_comp.set_editor_property("material", cloud_mat)

        if not is_night:
            # Sky Dome Mesh (SM_SkySphere with M_SimpleSkyDome material tagged as IsSky)
            # Only spawned in the day since the default material is blue!
            sky_sphere_mesh = editor_asset_sub.load_asset("/Engine/EngineSky/SM_SkySphere.SM_SkySphere")
            sky_sphere_mat = editor_asset_sub.load_asset("/Engine/EngineSky/M_SimpleSkyDome.M_SimpleSkyDome")
            if sky_sphere_mesh:
                sky_sphere = editor_actor_sub.spawn_actor_from_class(
                    unreal.StaticMeshActor,
                    unreal.Vector(0, 0, 0),
                    unreal.Rotator(0, 0, 0),
                )
                sky_sphere.set_actor_label(f"{{LEVEL_NAME}}_SkySphere")
                ss_comp = sky_sphere.get_component_by_class(unreal.StaticMeshComponent)
                if ss_comp:
                    ss_comp.set_static_mesh(sky_sphere_mesh)
                    if sky_sphere_mat:
                        ss_comp.set_material(0, sky_sphere_mat)
                    ss_comp.set_editor_property("relative_scale3d", unreal.Vector(400.0, 400.0, 400.0))
                    ss_comp.set_collision_profile_name("NoCollision")
                    ss_comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                    ss_comp.set_editor_property("cast_shadow", False)

        # Sky Light with Real Time Capture
        sky = editor_actor_sub.spawn_actor_from_class(
            unreal.SkyLight,
            unreal.Vector(0, 0, 5000),
            unreal.Rotator(0, 0, 0),
        )
        sky.set_actor_label(f"{{LEVEL_NAME}}_SkyLight")
        sky_comp = sky.get_component_by_class(unreal.SkyLightComponent)
        if sky_comp:
            # Set to 0.5 at night for ambient fill, 1.2 for day
            sky_comp.set_editor_property("intensity", 0.5 if is_night else 1.2)
            sky_comp.set_editor_property("real_time_capture", True)

        # Exponential Height Fog with volumetric fog enabled
        fog = editor_actor_sub.spawn_actor_from_class(
            unreal.ExponentialHeightFog,
            unreal.Vector(0, 0, 500),
            unreal.Rotator(0, 0, 0),
        )
        fog.set_actor_label(f"{{LEVEL_NAME}}_Fog")
        fog_comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
        if fog_comp:
            fog_comp.set_editor_property("enable_volumetric_fog", True)

        # Post Process Volume
        ppv = editor_actor_sub.spawn_actor_from_class(
            unreal.PostProcessVolume,
            unreal.Vector(0, 0, 0),
            unreal.Rotator(0, 0, 0),
        )
        ppv.set_actor_label(f"{{LEVEL_NAME}}_PostProcess")
        ppv.set_editor_property("unbound", True)
        # Force this PostProcessVolume to override any default Character Camera settings
        ppv.set_editor_property("priority", 10.0)

        settings = ppv.get_editor_property("settings")
        settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
        
        # Override auto exposure bounds and bias
        settings.set_editor_property("override_auto_exposure_min_brightness", True)
        settings.set_editor_property("override_auto_exposure_max_brightness", True)
        settings.set_editor_property("override_auto_exposure_bias", True)

        # Lock the exposure to completely prevent "fading to pitch black" Eye Adaptation
        settings.set_editor_property("auto_exposure_min_brightness", 1.0 if is_night else 0.03)
        settings.set_editor_property("auto_exposure_max_brightness", 1.0 if is_night else 2.0)
        settings.set_editor_property("auto_exposure_bias", 0.0)
        ppv.set_editor_property("settings", settings)

        # ── 5. Plant trees ───────────────────────────────────────────────────
        unreal.log_warning("[GEN] 5. Planting trees...")

        TREE_DATA = {json.dumps(tree_data)}

        # Group placements by spec name
        from collections import defaultdict
        groups = defaultdict(list)
        for td in TREE_DATA:
            groups[td["spec"]].append(td)

        # Tree spec → mesh/material config
        TREE_CONFIGS = {{
            "HISM_Tree_Leafy_Island_01": {{
                "mesh": "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01",
                "mats": [
                    "/Game/Forest/Materials/Instances/MI_IslandTree01_Trunk",
                    "/Game/Forest/Materials/Instances/MI_IslandTree01_Leaves",
                    "/Game/Forest/Materials/Instances/MI_IslandTree01_Branches",
                ],
            }},
            "HISM_Tree_Leafy_Island_02": {{
                "mesh": "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/StaticMeshes/SM_island_tree_02.SM_island_tree_02",
                "mats": [
                    "/Game/Forest/Materials/Instances/MI_IslandTree02_Trunk",
                    "/Game/Forest/Materials/Instances/MI_IslandTree02_Leaves",
                    "/Game/Forest/Materials/Instances/MI_IslandTree02_Branches",
                ],
            }},
            "HISM_Tree_Fir_A": {{
                "mesh": "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_a_LOD0.fir_tree_01_a_LOD0",
                "mats": [
                    "/Game/Forest/Materials/Instances/MI_FirTree01_Bark",
                    "/Game/Forest/Materials/Instances/MI_FirTree01_TrunkA",
                    "/Game/Forest/Materials/Instances/MI_FirTree01_Twig",
                    "/Game/Forest/Materials/Instances/MI_FirTree01_Bark",
                ],
            }},
            "HISM_Tree_Pine_A": {{
                "mesh": "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a",
                "mats": [
                    "/Game/Forest/Materials/Instances/MI_PineSapling_Bark",
                    "/Game/Forest/Materials/Instances/MI_PineSapling_Twig",
                ],
            }},
            "HISM_Tree_Deciduous": {{
                "mesh": "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
                "mats": [
                    "/Game/Forest/Materials/Instances/MI_TreeSmall02_Branches",
                    "/Game/Forest/Materials/Instances/MI_TreeSmall02_Leaves",
                    "/Game/Forest/Materials/Instances/MI_TreeSmall02_Trunk",
                ],
            }},
        }}

        def create_hism(name, mesh_path, mat_paths):
            mesh = editor_asset_sub.load_asset(mesh_path)
            if not mesh:
                unreal.log_error(f"[GEN] Missing mesh: {{mesh_path}}")
                return None
            actor = editor_actor_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
            actor.set_actor_label(name)
            comp = unreal.HierarchicalInstancedStaticMeshComponent(actor)
            comp.set_static_mesh(mesh)
            actor.set_editor_property("root_component", comp)
            comp.set_collision_profile_name("BlockAll")
            comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            comp.set_mobility(unreal.ComponentMobility.STATIC)
            comp.set_editor_property("cast_shadow", True)
            for idx, mp in enumerate(mat_paths):
                mat_obj = editor_asset_sub.load_asset(mp)
                if mat_obj:
                    comp.set_material(idx, mat_obj)
            return comp

        total_planted = 0
        for spec_name, config in TREE_CONFIGS.items():
            instances = groups.get(spec_name, [])
            if not instances:
                continue
            comp = create_hism(spec_name, config["mesh"], config["mats"])
            if not comp:
                continue
            for td in instances:
                tf = unreal.Transform(
                    location=unreal.Vector(td["x"], td["y"], td["z"]),
                    rotation=unreal.Rotator(pitch=0, yaw=td["yaw"], roll=0),
                    scale=unreal.Vector(td["scale"], td["scale"], td["scale"]),
                )
                comp.add_instance(tf)
                total_planted += 1

        unreal.log_warning(f"[GEN] Planted {{total_planted}} trees across {{len(TREE_CONFIGS)}} species!")

        # ── 6. Spawn Player Start ────────────────────────────────────────────
        unreal.log_warning("[GEN] 6. Spawning player start...")
        ps = editor_actor_sub.spawn_actor_from_class(
            unreal.PlayerStart,
            unreal.Vector(0, 0, 100),
            unreal.Rotator(0, 0, 0),
        )
        ps.set_actor_label(f"{{LEVEL_NAME}}_PlayerStart")

        # ── 7. Save ─────────────────────────────────────────────────────────
        level_editor_sub.save_current_level()
        unreal.log_warning("=" * 60)
        unreal.log_warning(f"[GEN] ✅ {{LEVEL_NAME}} GENERATED AND SAVED!")
        unreal.log_warning("=" * 60)
    ''')

    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w") as f:
        f.write(script)


# ─── Unreal verification script generator ───────────────────────────────────

def _write_unreal_verify_script(
    script_path: str,
    level_name: str,
    world_size_cm: float,
    grid_size: int,
    placed_trees,
    time_of_day: str = "day",
):
    """Generate an Unreal Python script that verifies the level after import."""

    tree_count = len(placed_trees)
    from collections import Counter
    spec_counts = dict(Counter(t.spec_name for t in placed_trees))

    script = textwrap.dedent(f'''\
        """
        Auto-generated Unreal verification script for {level_name}.
        Verifies collision, materials, actor presence, and tree HISM instances.
        """
        import unreal

        editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
        editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

        LEVEL_NAME = "{level_name}"
        WORLD_SIZE_CM = {world_size_cm}
        EXPECTED_TREE_COUNT = {tree_count}
        EXPECTED_SPEC_COUNTS = {json.dumps(spec_counts)}

        passed = 0
        failed = 0
        total = 0

        def check(name, condition, detail=""):
            global passed, failed, total
            total += 1
            if condition:
                passed += 1
                unreal.log_warning(f"  ✅ {{name}}: PASSED {{detail}}")
            else:
                failed += 1
                unreal.log_error(f"  ❌ {{name}}: FAILED {{detail}}")

        unreal.log_warning("=" * 60)
        unreal.log_warning(f"[VERIFY] Verifying {{LEVEL_NAME}} in Unreal Engine")
        unreal.log_warning("=" * 60)

        # Load level
        level_editor_sub.load_level(f"/Game/Maps/{{LEVEL_NAME}}")

        actors = editor_actor_sub.get_all_level_actors()
        actor_labels = [a.get_actor_label() for a in actors]

        # ── 1. Terrain Actor Exists ──────────────────────────────────────────
        terrain_label = f"{{LEVEL_NAME}}_Terrain"
        check("Terrain Actor Exists", terrain_label in actor_labels)

        # ── 2. Terrain has StaticMeshComponent with BlockAll collision ────────
        for a in actors:
            if a.get_actor_label() == terrain_label:
                smc = a.get_component_by_class(unreal.StaticMeshComponent)
                check("Terrain Has SMC", smc is not None)
                if smc:
                    check("Terrain Collision Profile",
                          smc.get_collision_profile_name() == "BlockAll",
                          f"(got: {{smc.get_collision_profile_name()}})")
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
                                  f"(got: {{flag}})")

                        mat = mesh.get_material(0)
                        check("Terrain Material Assigned", mat is not None)
                        if mat:
                            check("Terrain Material Is PBR",
                                  "M_Forest_Ground_PBR" in mat.get_path_name(),
                                  f"(got: {{mat.get_path_name()}})")

        # ── 3. Lighting & Sky Actors ─────────────────────────────────────────
        if "{time_of_day}" != "night":
            sun_actor = next((a for a in actors if a.get_actor_label() == f"{{LEVEL_NAME}}_Sun"), None)
            check("Sun Light Exists", sun_actor is not None)
            if sun_actor:
                sun_comp = sun_actor.get_component_by_class(unreal.DirectionalLightComponent)
                check("Sun Intensity is 6.0 in Day", sun_comp.get_editor_property("intensity") == 6.0)
                check("Sun Casts Shadows in Day", sun_comp.get_editor_property("cast_shadows") == True)
                check("Sun Atmosphere Light is True in Day", sun_comp.get_editor_property("atmosphere_sun_light") == True)

        if "{time_of_day}" == "night":
            moon_actor = next((a for a in actors if a.get_actor_label() == f"{{LEVEL_NAME}}_Moon"), None)
            check("Moon Light Exists", moon_actor is not None)
            if moon_actor:
                moon_comp = moon_actor.get_component_by_class(unreal.DirectionalLightComponent)
                check("Moon Intensity is 2.0 (Locked Exposure Night)", moon_comp.get_editor_property("intensity") == 2.0)
                check("Moon Atmosphere Light is True", moon_comp.get_editor_property("atmosphere_sun_light") == True)
                check("Moon Index is 0", moon_comp.get_editor_property("atmosphere_sun_light_index") == 0)
                check("Moon Casts Shadows", moon_comp.get_editor_property("cast_shadows") == True)

        check("Sky Atmosphere Exists", f"{{LEVEL_NAME}}_SkyAtmosphere" in actor_labels)
        check("Volumetric Cloud Exists", f"{{LEVEL_NAME}}_VolumetricCloud" in actor_labels)
        if "{time_of_day}" != "night":
            check("Sky Sphere Exists", f"{{LEVEL_NAME}}_SkySphere" in actor_labels)
        check("Sky Light Exists", f"{{LEVEL_NAME}}_SkyLight" in actor_labels)
        check("Fog Exists", f"{{LEVEL_NAME}}_Fog" in actor_labels)

        ppv_actor = next((a for a in actors if a.get_actor_label() == f"{{LEVEL_NAME}}_PostProcess"), None)
        check("PostProcess Exists", ppv_actor is not None)
        if ppv_actor:
            settings = ppv_actor.get_editor_property("settings")
            min_bright = settings.get_editor_property("auto_exposure_min_brightness")
            bias = settings.get_editor_property("auto_exposure_bias")
            priority = ppv_actor.get_editor_property("priority")
            
            check("PostProcess Priority is 10.0", priority == 10.0)
            
            expected_min = 1.0 if "{time_of_day}" == "night" else 0.03
            check(f"PostProcess Min Exposure is {{expected_min}}", abs(min_bright - expected_min) < 0.01)
            
            # Check bias
            check(f"PostProcess Bias is 0.0", abs(bias - 0.0) < 0.01)

        check("Player Start Exists", f"{{LEVEL_NAME}}_PlayerStart" in actor_labels)

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
                        check(f"{{spec_name}} Instance Count",
                              inst_count == expected_count,
                              f"(expected {{expected_count}}, got {{inst_count}})")
                        check(f"{{spec_name}} Collision Profile",
                              root.get_collision_profile_name() == "BlockAll")
                    break
            check(f"{{spec_name}} Actor Exists", found)

        check("Total Tree Instances",
              total_tree_instances == EXPECTED_TREE_COUNT,
              f"(expected {{EXPECTED_TREE_COUNT}}, got {{total_tree_instances}})")

        # ── Summary ──────────────────────────────────────────────────────────
        unreal.log_warning("")
        unreal.log_warning("=" * 60)
        if failed == 0:
            unreal.log_warning(f"[VERIFY] ✅ ALL {{total}} CHECKS PASSED!")
        else:
            unreal.log_error(f"[VERIFY] ❌ {{failed}}/{{total}} CHECKS FAILED!")
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

    ''')

    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w") as f:
        f.write(script)


if __name__ == "__main__":
    main()
