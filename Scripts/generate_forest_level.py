#!/usr/bin/env python3
"""
generate_forest_level.py — End-to-end forest level generator + verifier.

Usage:
    python3 Scripts/generate_forest_level.py --size 200
    python3 Scripts/generate_forest_level.py --size 400 --name Lvl_BigForest --seed 99
    python3 Scripts/generate_forest_level.py --size 200 --time-of-day night
    python3 Scripts/generate_forest_level.py --size 200 --grass-density 2.0 --grass-height 55

This script:
  1. Generates a terrain OBJ mesh (pure Python)
  2. Scatters trees and knee-high grass with exact terrain snapping (pure Python)
  3. Runs 18+ offline verification checks
  4. Writes an Unreal Python script to import everything into the editor
  5. Prints a command to run the import inside UnrealEditor-Cmd
"""

import argparse
import json
import os
import sys
import textwrap
from collections import Counter

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
from forest_generator.grass_placement import (
    scatter_grass,
    DEFAULT_GRASS_SPECS,
    DEFAULT_DENSITY_PER_SQM,
    DEFAULT_PATCHINESS,
    KNEE_HEIGHT_CM,
)
from forest_generator.verification import run_all_checks
from forest_generator.lighting import (
    TIME_OF_DAY_PRESETS,
    get_preset,
    STARS_TEXTURE_PATH,
)


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
    parser.add_argument("--time-of-day", type=str, default="day",
                        choices=sorted(TIME_OF_DAY_PRESETS.keys()),
                        help="Lighting preset: 'day' (bright sun) or 'night' "
                             "(starry sky providing low luminosity)")
    parser.add_argument("--grass-density", type=float, default=DEFAULT_DENSITY_PER_SQM,
                        help=f"Grass clumps per square metre "
                             f"(default: {DEFAULT_DENSITY_PER_SQM})")
    parser.add_argument("--grass-height", type=float, default=KNEE_HEIGHT_CM,
                        help=f"Knee height in cm the dominant grass layer is "
                             f"scaled to (default: {KNEE_HEIGHT_CM:.0f})")
    parser.add_argument("--grass-patchiness", type=float, default=DEFAULT_PATCHINESS,
                        help=f"0 = perfectly even grass, ->1 = heavily clustered "
                             f"(default: {DEFAULT_PATCHINESS})")
    parser.add_argument("--no-grass", action="store_true",
                        help="Skip grass generation entirely")
    parser.add_argument("--json-report", type=str, default=None,
                        help="Path to write JSON verification report")
    args = parser.parse_args()

    world_size_m = args.size
    world_size_cm = world_size_m * 100.0
    level_name = args.name or f"Lvl_Forest_{int(world_size_m)}m"
    lighting = get_preset(args.time_of_day)

    output_dir = os.path.join(SCRIPTS_DIR, "generated_levels", level_name)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'═' * 60}")
    print(f"  Forest Level Generator — {level_name}")
    print(f"  Map size: {world_size_m}m × {world_size_m}m")
    print(f"  Seed: {args.seed}")
    print(f"  Time of day: {lighting['label']}")
    if args.no_grass:
        print(f"  Grass: disabled")
    else:
        print(f"  Grass: {args.grass_density:.2f}/m2, knee height {args.grass_height:.0f} cm")
    print(f"{'═' * 60}\n")

    # ── Step 1: Generate terrain mesh ────────────────────────────────────
    obj_path = os.path.join(output_dir, f"SM_{level_name}_Terrain.obj")
    print(f"[1/5] Generating terrain mesh → {obj_path}")
    terrain = generate_terrain_obj(obj_path, world_size_cm, grid_size=args.grid)
    grid_size = terrain["grid_size"]
    grid_z = terrain["grid_z"]
    print(f"       Grid: {grid_size}×{grid_size} ({grid_size**2} quads)")
    print(f"       File: {terrain['bytes']:,} bytes")

    # ── Step 2: Scatter trees ────────────────────────────────────────────
    print(f"\n[2/5] Scattering trees (seed={args.seed})...")
    placed_trees = scatter_trees(
        world_size_cm=world_size_cm,
        grid_z=grid_z,
        grid_size=grid_size,
        seed=args.seed,
    )

    # Count per spec
    counts = Counter(t.spec_name for t in placed_trees)
    for name, cnt in sorted(counts.items()):
        print(f"       {name}: {cnt} instances")
    print(f"       TOTAL: {len(placed_trees)} trees")

    # ── Step 3: Scatter knee-high grass ──────────────────────────────────
    if args.no_grass:
        print(f"\n[3/5] Grass generation disabled (--no-grass)")
        placed_grass = []
    else:
        print(f"\n[3/5] Scattering knee-high grass "
              f"({args.grass_density:.2f}/m2, {args.grass_height:.0f} cm)...")
        placed_grass = scatter_grass(
            world_size_cm=world_size_cm,
            grid_z=grid_z,
            grid_size=grid_size,
            seed=args.seed,
            density_per_sqm=args.grass_density,
            knee_height_cm=args.grass_height,
            patchiness=args.grass_patchiness,
            placed_trees=placed_trees,
        )
        grass_counts = Counter(g.spec_name for g in placed_grass)
        for name, cnt in sorted(grass_counts.items()):
            print(f"       {name}: {cnt:,} instances")
        print(f"       TOTAL: {len(placed_grass):,} grass clumps")

    # ── Step 4: Run verification ─────────────────────────────────────────
    print(f"\n[4/5] Running verification suite...")
    report = run_all_checks(
        level_name=level_name,
        world_size_cm=world_size_cm,
        obj_path=obj_path,
        grid_z=grid_z,
        grid_size=grid_size,
        placed_trees=placed_trees,
        placed_grass=placed_grass,
        grass_density_per_sqm=args.grass_density,
        knee_height_cm=args.grass_height,
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

    # ── Step 5: Write the grass sidecar + Unreal scripts ─────────────────
    # Tens of thousands of transforms would bloat the generated script, so the
    # grass instances live in their own JSON file the import script reads.
    grass_data_path = os.path.join(output_dir, f"grass_{level_name}.json")
    _write_grass_data(grass_data_path, placed_grass)
    if placed_grass:
        print(f"\n       Grass data → {grass_data_path} "
              f"({os.path.getsize(grass_data_path):,} bytes)")


    print(f"\n[5/5] Writing Unreal import script...")
    ue_script_path = os.path.join(output_dir, f"import_{level_name}.py")
    _write_unreal_import_script(
        ue_script_path,
        level_name=level_name,
        obj_path=obj_path,
        world_size_cm=world_size_cm,
        grid_size=grid_size,
        placed_trees=placed_trees,
        grass_data_path=grass_data_path,
        grass_count=len(placed_grass),
        lighting=lighting,
    )
    print(f"       Script → {ue_script_path}")

    # ── Write Unreal verification script ─────────────────────────────────
    ue_verify_path = os.path.join(output_dir, f"verify_{level_name}.py")
    _write_unreal_verify_script(
        ue_verify_path,
        level_name=level_name,
        world_size_cm=world_size_cm,
        grid_size=grid_size,
        placed_trees=placed_trees,
        placed_grass=placed_grass,
        lighting=lighting,
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


# ─── Grass sidecar writer ───────────────────────────────────────────────────

def _write_grass_data(path: str, placed_grass) -> None:
    """
    Write grass instance transforms to a compact JSON sidecar.

    One record per clump, and there are tens of thousands of them on a normal
    map — so spec names are interned into an index table and each instance is
    a flat rounded array:
        [spec_idx, x, y, z, yaw, pitch, roll, height_mul, width_mul, target_h_cm]
    """
    spec_names = sorted({g.spec_name for g in placed_grass})
    spec_idx = {n: i for i, n in enumerate(spec_names)}
    payload = {
        "specs": spec_names,
        "instances": [
            [
                spec_idx[g.spec_name],
                round(g.x, 1), round(g.y, 1), round(g.placed_z, 1),
                round(g.yaw_deg, 1), round(g.pitch_deg, 2), round(g.roll_deg, 2),
                round(g.height_scale, 3), round(g.width_scale, 3),
                round(g.target_height_cm, 2),
            ]
            for g in placed_grass
        ],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))


# ─── Unreal import script generator ─────────────────────────────────────────

def _write_unreal_import_script(
    script_path: str,
    level_name: str,
    obj_path: str,
    world_size_cm: float,
    grid_size: int,
    placed_trees,
    grass_data_path: str,
    grass_count: int,
    lighting: dict,
):
    """Generate a self-contained Unreal Python script that imports everything."""

    # Grass mesh/material table, keyed by HISM actor label
    grass_configs = {
        s.name: {"mesh": s.mesh_path, "mats": list(s.material_paths)}
        for s in DEFAULT_GRASS_SPECS
    }
    grass_configs_json = json.dumps(grass_configs)

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

    # Lighting preset is embedded as JSON so the Unreal script stays data-driven
    lighting_json = json.dumps(lighting)
    tod_key = lighting["key"]
    tod_label = lighting["label"]
    stars_texture = STARS_TEXTURE_PATH

    script = textwrap.dedent(f'''\
        """
        Auto-generated Unreal import script for {level_name}.
        Generated by generate_forest_level.py
        World size: {world_size_cm / 100.0}m × {world_size_cm / 100.0}m
        Time of day: {tod_label}
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
                if (lbl.startswith(LEVEL_NAME)
                        or lbl.startswith("HISM_Tree")
                        or lbl.startswith("HISM_Grass")):
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

        # ── 4. Spawn lighting & sky ({tod_label}) ─────────────────────────────
        unreal.log_warning("[GEN] 4. Setting up lighting and sky — {tod_label}")

        LIGHTING = json.loads(r"""{lighting_json}""")

        def srgb(c):
            return unreal.Color(r=c[0], g=c[1], b=c[2], a=255)

        def linear(c):
            return unreal.LinearColor(c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)

        def try_set(obj, prop, value, quiet=False):
            """Set an editor property, logging (not raising) if it is unavailable."""
            try:
                obj.set_editor_property(prop, value)
                return True
            except Exception as exc:
                if not quiet:
                    unreal.log_warning(f"[GEN]   (skipped {{prop}}: {{exc}})")
                return False

        def try_set_first(obj, props, value):
            """Set the first property name that exists (engine versions differ)."""
            for i, prop in enumerate(props):
                if try_set(obj, prop, value, quiet=(i < len(props) - 1)):
                    return True
            return False

        def ensure_starfield_material(cfg):
            """Build the unlit emissive starfield sky-dome material + instance."""
            base_path = cfg["material"]
            base_name = base_path.rsplit("/", 1)[-1]
            base_pkg = base_path.rsplit("/", 1)[0]
            base = editor_asset_sub.load_asset(base_path + "." + base_name)

            if not base:
                unreal.log_warning(f"[GEN]   Creating {{base_path}}")
                base = asset_tools.create_asset(
                    base_name, base_pkg, unreal.Material, unreal.MaterialFactoryNew()
                )
                # Unlit + two-sided + IsSky so height fog leaves it alone and the
                # SkyLight real-time capture treats it as sky lighting.
                try_set(base, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
                try_set(base, "two_sided", True)
                try_set(base, "is_sky", True)

                coord = mel.create_material_expression(
                    base, unreal.MaterialExpressionTextureCoordinate, -1100, 0)
                try_set(coord, "u_tiling", cfg["star_tiling"][0])
                try_set(coord, "v_tiling", cfg["star_tiling"][1])

                stars = mel.create_material_expression(
                    base, unreal.MaterialExpressionTextureSampleParameter2D, -820, 0)
                try_set(stars, "parameter_name", "StarsTexture")
                stars_tex = editor_asset_sub.load_asset("{stars_texture}")
                if stars_tex:
                    try_set(stars, "texture", stars_tex)
                else:
                    unreal.log_error("[GEN]   Missing star texture {stars_texture}")
                mel.connect_material_expressions(coord, "", stars, "UVs")

                brightness = mel.create_material_expression(
                    base, unreal.MaterialExpressionScalarParameter, -820, 300)
                try_set(brightness, "parameter_name", "StarBrightness")
                try_set(brightness, "default_value", cfg["star_brightness"])

                star_mul = mel.create_material_expression(
                    base, unreal.MaterialExpressionMultiply, -520, 60)
                mel.connect_material_expressions(stars, "", star_mul, "A")
                mel.connect_material_expressions(brightness, "", star_mul, "B")

                night_col = mel.create_material_expression(
                    base, unreal.MaterialExpressionVectorParameter, -520, 320)
                try_set(night_col, "parameter_name", "NightSkyColor")
                try_set(night_col, "default_value", linear(cfg["night_sky_color"]))

                add = mel.create_material_expression(
                    base, unreal.MaterialExpressionAdd, -240, 140)
                mel.connect_material_expressions(star_mul, "", add, "A")
                mel.connect_material_expressions(night_col, "", add, "B")
                mel.connect_material_property(add, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

                mel.recompile_material(base)
                editor_asset_sub.save_loaded_asset(base)

            # Instance carries the tweakable star brightness / night sky tint
            mi_name = "MI_NightSky_Starfield"
            mi_pkg = "/Game/Forest/Materials/Instances"
            mi_path = mi_pkg + "/" + mi_name
            mi = editor_asset_sub.load_asset(mi_path + "." + mi_name)
            if not mi:
                mi = asset_tools.create_asset(
                    mi_name, mi_pkg, unreal.MaterialInstanceConstant,
                    unreal.MaterialInstanceConstantFactoryNew()
                )
            try_set(mi, "parent", base)
            mel.set_material_instance_scalar_parameter_value(
                mi, "StarBrightness", cfg["star_brightness"])
            mel.set_material_instance_vector_parameter_value(
                mi, "NightSkyColor", linear(cfg["night_sky_color"]))
            editor_asset_sub.save_loaded_asset(mi)
            return mi

        # Directional Light (sun or moon) driving the Sky Atmosphere
        sun_cfg = LIGHTING["sun"]
        if sun_cfg["enabled"]:
            sun = editor_actor_sub.spawn_actor_from_class(
                unreal.DirectionalLight,
                unreal.Vector(0, 0, 5000),
                unreal.Rotator(pitch=sun_cfg["pitch"], yaw=sun_cfg["yaw"], roll=0),
            )
            sun.set_actor_label(f"{{LEVEL_NAME}}_{{sun_cfg['label_suffix']}}")
            sun_comp = sun.get_component_by_class(unreal.DirectionalLightComponent)
            if sun_comp:
                sun_comp.set_editor_property("intensity", sun_cfg["intensity"])
                sun_comp.set_editor_property("light_color", srgb(sun_cfg["color"]))
                sun_comp.set_editor_property("cast_shadows", sun_cfg["cast_shadows"])
                sun_comp.set_editor_property("atmosphere_sun_light", True)
                sun_comp.set_editor_property("atmosphere_sun_light_index", 0)
            unreal.log_warning(
                f"[GEN]   {{sun_cfg['label_suffix']}}: {{sun_cfg['intensity']}} lux "
                f"@ pitch {{sun_cfg['pitch']}}"
            )

        # SkyAtmosphere Component / Actor
        sky_atmo = editor_actor_sub.spawn_actor_from_class(
            unreal.SkyAtmosphere,
            unreal.Vector(0, 0, 0),
            unreal.Rotator(0, 0, 0),
        )
        sky_atmo.set_actor_label(f"{{LEVEL_NAME}}_SkyAtmosphere")

        # VolumetricCloud Actor (clear sky at night so stars stay visible)
        cloud_cfg = LIGHTING["volumetric_cloud"]
        if cloud_cfg["enabled"]:
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
        else:
            unreal.log_warning("[GEN]   Volumetric clouds disabled for this preset")

        # Sky Dome Mesh — daytime gradient, or the emissive starfield at night
        dome_cfg = LIGHTING["sky_dome"]
        if dome_cfg["enabled"]:
            sky_sphere_mesh = editor_asset_sub.load_asset("/Engine/EngineSky/SM_SkySphere.SM_SkySphere")
            if dome_cfg.get("build_starfield"):
                sky_sphere_mat = ensure_starfield_material(dome_cfg)
            else:
                mat_path = dome_cfg["material"]
                sky_sphere_mat = editor_asset_sub.load_asset(mat_path)
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
                    else:
                        unreal.log_error("[GEN]   Sky dome material failed to load!")
                    ss_comp.set_editor_property("relative_scale3d", unreal.Vector(400.0, 400.0, 400.0))
                    ss_comp.set_collision_profile_name("NoCollision")
                    ss_comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                    ss_comp.set_editor_property("cast_shadow", False)

        # Sky Light with Real Time Capture — at night this captures the emissive
        # starfield dome, so the stars themselves are the ambient light source.
        sky_cfg = LIGHTING["sky_light"]
        sky = editor_actor_sub.spawn_actor_from_class(
            unreal.SkyLight,
            unreal.Vector(0, 0, 5000),
            unreal.Rotator(0, 0, 0),
        )
        sky.set_actor_label(f"{{LEVEL_NAME}}_SkyLight")
        sky_comp = sky.get_component_by_class(unreal.SkyLightComponent)
        if sky_comp:
            sky_comp.set_editor_property("intensity", sky_cfg["intensity"])
            sky_comp.set_editor_property("real_time_capture", sky_cfg["real_time_capture"])

        # Exponential Height Fog with volumetric fog enabled
        fog_cfg = LIGHTING["fog"]
        fog = editor_actor_sub.spawn_actor_from_class(
            unreal.ExponentialHeightFog,
            unreal.Vector(0, 0, 500),
            unreal.Rotator(0, 0, 0),
        )
        fog.set_actor_label(f"{{LEVEL_NAME}}_Fog")
        fog_comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
        if fog_comp:
            fog_comp.set_editor_property("enable_volumetric_fog", fog_cfg["enable_volumetric"])
            try_set(fog_comp, "fog_density", fog_cfg["density"])
            # UE 5.4+ renamed this to fog_inscattering_luminance
            try_set_first(fog_comp,
                          ["fog_inscattering_luminance", "fog_inscattering_color"],
                          linear(fog_cfg["inscattering_color"]))
            try_set(fog_comp, "volumetric_fog_extinction_scale",
                    fog_cfg["volumetric_extinction_scale"])

        # Post Process Volume
        pp_cfg = LIGHTING["post_process"]
        ppv = editor_actor_sub.spawn_actor_from_class(
            unreal.PostProcessVolume,
            unreal.Vector(0, 0, 0),
            unreal.Rotator(0, 0, 0),
        )
        ppv.set_actor_label(f"{{LEVEL_NAME}}_PostProcess")
        ppv.set_editor_property("unbound", True)
        settings = ppv.get_editor_property("settings")
        settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
        settings.set_editor_property("auto_exposure_min_brightness",
                                     pp_cfg["auto_exposure_min_brightness"])
        settings.set_editor_property("auto_exposure_max_brightness",
                                     pp_cfg["auto_exposure_max_brightness"])
        settings.set_editor_property("auto_exposure_bias", pp_cfg["auto_exposure_bias"])
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

        # ── 5b. Plant knee-high grass ────────────────────────────────────────
        GRASS_DATA_PATH = r"{grass_data_path}"
        EXPECTED_GRASS_COUNT = {grass_count}
        GRASS_CONFIGS = json.loads(r"""{grass_configs_json}""")
        # Distance (cm) at which grass instances begin / finish fading out.
        GRASS_CULL_START = 6000
        GRASS_CULL_END = 9000

        if EXPECTED_GRASS_COUNT > 0 and os.path.isfile(GRASS_DATA_PATH):
            unreal.log_warning("[GEN] 5b. Planting knee-high grass...")
            with open(GRASS_DATA_PATH, "r") as _f:
                grass_payload = json.load(_f)

            grass_spec_names = grass_payload["specs"]
            grass_groups = defaultdict(list)
            for inst in grass_payload["instances"]:
                grass_groups[grass_spec_names[inst[0]]].append(inst)

            def create_grass_hism(name, mesh_path, mat_paths):
                """Like create_hism, but grass never blocks the player."""
                mesh = editor_asset_sub.load_asset(mesh_path)
                if not mesh:
                    unreal.log_error(f"[GEN] Missing grass mesh: {{mesh_path}}")
                    return None, 0.0
                actor = editor_actor_sub.spawn_actor_from_class(
                    unreal.Actor, unreal.Vector(0, 0, 0))
                actor.set_actor_label(name)
                comp = unreal.HierarchicalInstancedStaticMeshComponent(actor)
                comp.set_static_mesh(mesh)
                actor.set_editor_property("root_component", comp)
                comp.set_collision_profile_name("NoCollision")
                comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                comp.set_mobility(unreal.ComponentMobility.STATIC)
                comp.set_editor_property("cast_shadow", True)
                try_set(comp, "instance_start_cull_distance", GRASS_CULL_START)
                try_set(comp, "instance_end_cull_distance", GRASS_CULL_END)
                for idx, mp in enumerate(mat_paths):
                    mat_obj = editor_asset_sub.load_asset(mp)
                    if mat_obj:
                        comp.set_material(idx, mat_obj)

                # The scanned meshes have no authored real-world size, so derive
                # the scale that makes a clump exactly its target height.
                mesh_height = 0.0
                try:
                    bounds = mesh.get_bounds()
                    mesh_height = float(bounds.box_extent.z) * 2.0
                except Exception as exc:
                    unreal.log_warning(f"[GEN] Could not read bounds for {{name}}: {{exc}}")
                return comp, mesh_height

            total_grass = 0
            for spec_name, instances in grass_groups.items():
                config = GRASS_CONFIGS.get(spec_name)
                if not config or not instances:
                    continue
                comp, mesh_height = create_grass_hism(
                    spec_name, config["mesh"], config["mats"])
                if not comp:
                    continue
                if mesh_height <= 1.0:
                    unreal.log_error(
                        f"[GEN] {{spec_name}} has unusable bounds height "
                        f"{{mesh_height}}; falling back to scale 1.0")

                for inst in instances:
                    _, gx, gy, gz, yaw, pitch, roll, h_mul, w_mul, target_h = inst
                    if mesh_height > 1.0:
                        s_z = target_h / mesh_height
                        s_xy = (target_h / max(h_mul, 1e-3)) / mesh_height * w_mul
                    else:
                        s_z, s_xy = 1.0, 1.0
                    tf = unreal.Transform(
                        location=unreal.Vector(gx, gy, gz),
                        rotation=unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll),
                        scale=unreal.Vector(s_xy, s_xy, s_z),
                    )
                    comp.add_instance(tf)
                    total_grass += 1

                unreal.log_warning(
                    f"[GEN]    {{spec_name}}: {{len(instances)}} clumps "
                    f"(mesh height {{mesh_height:.1f}} cm)")

            unreal.log_warning(
                f"[GEN] Planted {{total_grass}} grass clumps across "
                f"{{len(grass_groups)}} species!")
        else:
            unreal.log_warning("[GEN] 5b. Grass skipped (none generated).")

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
    placed_grass,
    lighting: dict,
):
    """Generate an Unreal Python script that verifies the level after import."""

    tree_count = len(placed_trees)
    spec_counts = dict(Counter(t.spec_name for t in placed_trees))

    grass_count = len(placed_grass)
    grass_spec_counts = dict(Counter(g.spec_name for g in placed_grass))
    # Expected world height per grass species, used to prove "knee high" in-engine.
    grass_expected_heights = {}
    for g in placed_grass:
        lo, hi = grass_expected_heights.get(g.spec_name, (1e9, -1e9))
        grass_expected_heights[g.spec_name] = (
            min(lo, g.target_height_cm), max(hi, g.target_height_cm))

    lighting_json = json.dumps(lighting)
    tod_label = lighting["label"]

    script = textwrap.dedent(f'''\
        """
        Auto-generated Unreal verification script for {level_name}.
        Verifies collision, materials, actor presence, tree and grass HISM
        instances (including that grass really is knee high), and the
        time-of-day lighting rig.
        Time of day: {tod_label}
        """
        import json
        import unreal

        editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
        editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

        LEVEL_NAME = "{level_name}"
        WORLD_SIZE_CM = {world_size_cm}
        EXPECTED_TREE_COUNT = {tree_count}
        EXPECTED_SPEC_COUNTS = {json.dumps(spec_counts)}
        EXPECTED_GRASS_COUNT = {grass_count}
        EXPECTED_GRASS_SPEC_COUNTS = {json.dumps(grass_spec_counts)}
        EXPECTED_GRASS_HEIGHTS = {json.dumps(grass_expected_heights)}
        LIGHTING = json.loads(r"""{lighting_json}""")

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

        # ── 3. Lighting & Sky Actors (time of day: {tod_label}) ──────────────
        sun_cfg = LIGHTING["sun"]
        sky_cfg = LIGHTING["sky_light"]
        dome_cfg = LIGHTING["sky_dome"]
        cloud_cfg = LIGHTING["volumetric_cloud"]
        pp_cfg = LIGHTING["post_process"]

        sun_label = f"{{LEVEL_NAME}}_{{sun_cfg['label_suffix']}}"
        check("Directional Light Exists", sun_label in actor_labels, f"({{sun_label}})")
        check("Sky Atmosphere Exists", f"{{LEVEL_NAME}}_SkyAtmosphere" in actor_labels)
        check("Sky Sphere Exists", f"{{LEVEL_NAME}}_SkySphere" in actor_labels)
        check("Sky Light Exists", f"{{LEVEL_NAME}}_SkyLight" in actor_labels)
        check("Fog Exists", f"{{LEVEL_NAME}}_Fog" in actor_labels)
        check("PostProcess Exists", f"{{LEVEL_NAME}}_PostProcess" in actor_labels)
        check("Player Start Exists", f"{{LEVEL_NAME}}_PlayerStart" in actor_labels)

        cloud_present = f"{{LEVEL_NAME}}_VolumetricCloud" in actor_labels
        check("Volumetric Cloud Matches Preset",
              cloud_present == cloud_cfg["enabled"],
              f"(preset wants {{cloud_cfg['enabled']}}, found {{cloud_present}})")

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
                          f"(expected {{sun_cfg['intensity']}} lux, got {{inten}})")
                    check("Atmosphere Sun Light Enabled",
                          dlc.get_editor_property("atmosphere_sun_light"))
                    check("Directional Light Casts Shadows",
                          dlc.get_editor_property("cast_shadows") == sun_cfg["cast_shadows"])

            elif lbl == f"{{LEVEL_NAME}}_SkyLight":
                slc = a.get_component_by_class(unreal.SkyLightComponent)
                if slc:
                    inten = slc.get_editor_property("intensity")
                    check("Sky Light Intensity",
                          close(inten, sky_cfg["intensity"], 0.01),
                          f"(expected {{sky_cfg['intensity']}}, got {{inten}})")
                    check("Sky Light Real Time Capture",
                          slc.get_editor_property("real_time_capture") == sky_cfg["real_time_capture"])

            elif lbl == f"{{LEVEL_NAME}}_SkySphere":
                ssc = a.get_component_by_class(unreal.StaticMeshComponent)
                if ssc:
                    dome_mat = ssc.get_material(0)
                    check("Sky Dome Material Assigned", dome_mat is not None)
                    if dome_mat:
                        mat_path = dome_mat.get_path_name()
                        if dome_cfg.get("build_starfield"):
                            check("Sky Dome Is Starfield",
                                  "NightSky_Starfield" in mat_path,
                                  f"(got: {{mat_path}})")
                            base = dome_mat.get_base_material() if hasattr(dome_mat, "get_base_material") else None
                            src = base or dome_mat
                            try:
                                check("Starfield Material Is Unlit",
                                      src.get_editor_property("shading_model")
                                      == unreal.MaterialShadingModel.MSM_UNLIT)
                                check("Starfield Material Tagged IsSky",
                                      src.get_editor_property("is_sky"))
                            except Exception as exc:
                                check("Starfield Material Flags", False, f"({{exc}})")
                            try:
                                sb = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
                                    dome_mat, "StarBrightness")
                                check("Star Brightness Set",
                                      close(sb, dome_cfg["star_brightness"], 0.01),
                                      f"(expected {{dome_cfg['star_brightness']}}, got {{sb}})")
                            except Exception as exc:
                                check("Star Brightness Set", False, f"({{exc}})")
                        else:
                            check("Sky Dome Material Matches Preset",
                                  dome_cfg["material"].split(".")[0] in mat_path,
                                  f"(got: {{mat_path}})")

            elif lbl == f"{{LEVEL_NAME}}_PostProcess":
                st = a.get_editor_property("settings")
                check("Exposure Min Brightness",
                      close(st.get_editor_property("auto_exposure_min_brightness"),
                            pp_cfg["auto_exposure_min_brightness"], 1e-4),
                      f"(expected {{pp_cfg['auto_exposure_min_brightness']}})")
                check("Exposure Max Brightness",
                      close(st.get_editor_property("auto_exposure_max_brightness"),
                            pp_cfg["auto_exposure_max_brightness"], 1e-4),
                      f"(expected {{pp_cfg['auto_exposure_max_brightness']}})")
                check("Exposure Bias",
                      close(st.get_editor_property("auto_exposure_bias"),
                            pp_cfg["auto_exposure_bias"], 1e-4),
                      f"(expected {{pp_cfg['auto_exposure_bias']}})")

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
                            check(f"{{spec_name}} Instance Count",
                                  inst_count == expected_count,
                                  f"(expected {{expected_count}}, got {{inst_count}})")
                            # Grass must never block the player.
                            check(f"{{spec_name}} No Collision",
                                  str(root.get_collision_profile_name()) == "NoCollision",
                                  f"(got {{root.get_collision_profile_name()}})")

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
                                check(f"{{spec_name}} Knee Height",
                                      len(worst) == 0,
                                      f"(expected {{lo:.1f}}-{{hi:.1f}} cm, "
                                      f"sampled {{min(sampled):.1f}}-{{max(sampled):.1f}} cm)")
                        break
                check(f"{{spec_name}} Actor Exists", found)

            check("Total Grass Instances",
                  total_grass_instances == EXPECTED_GRASS_COUNT,
                  f"(expected {{EXPECTED_GRASS_COUNT}}, got {{total_grass_instances}})")

        # ── Summary ──────────────────────────────────────────────────────────
        unreal.log_warning("")
        unreal.log_warning("=" * 60)
        if failed == 0:
            unreal.log_warning(f"[VERIFY] ✅ ALL {{total}} CHECKS PASSED!")
        else:
            unreal.log_error(f"[VERIFY] ❌ {{failed}}/{{total}} CHECKS FAILED!")
        unreal.log_warning("=" * 60)
    ''')

    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w") as f:
        f.write(script)


if __name__ == "__main__":
    main()
