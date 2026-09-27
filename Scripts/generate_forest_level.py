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
  3. Picks a spawn point for a wandering NPC that walks to the player
  4. Runs 25 offline verification checks
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
from forest_generator.npc_placement import (
    NPC_VARIANTS,
    gait_scale_for_index,
    place_npcs,
    spawn_band,
    compute_nav_bounds,
    NAV_MAX_VERTICAL_SPAN_CM,
    NPC_RUN_SPEED_CMS,
    NPC_CAPSULE_HALF_HEIGHT_CM,
    NAV_AGENT_RADIUS_CM,
    NAV_AGENT_HEIGHT_CM,
    NPC_COUNT,
    NPC_SPAWN_MIN_DISTANCE_CM,
    NPC_SPAWN_MAX_DISTANCE_CM,
    NPC_MELEE_RANGE_CM,
    NPC_MELEE_DAMAGE,
    NPC_MELEE_INTERVAL_S,
    NAV_REACHABLE_EXTENT_CM,
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
    parser.add_argument("--no-npc", action="store_true",
                        help="Skip the wandering NPCs")
    parser.add_argument("--npc-count", type=int, default=NPC_COUNT,
                        help=f"How many wanderers to spawn (default: {NPC_COUNT})")
    parser.add_argument("--npc-min-distance", type=float, default=None,
                        help=f"Inner edge of the spawn band, in metres "
                             f"(default: {NPC_SPAWN_MIN_DISTANCE_CM / 100.0:.0f})")
    parser.add_argument("--npc-max-distance", type=float, default=None,
                        help=f"Outer edge of the spawn band, in metres "
                             f"(default: {NPC_SPAWN_MAX_DISTANCE_CM / 100.0:.0f}; "
                             f"both edges are clamped to the navigable radius)")
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
    if args.no_npc:
        print(f"  NPCs: disabled")
    else:
        band_lo, band_hi, _clamped = spawn_band(
            world_size_cm,
            min_distance_cm=(args.npc_min_distance * 100.0
                             if args.npc_min_distance is not None
                             else NPC_SPAWN_MIN_DISTANCE_CM),
            max_distance_cm=(args.npc_max_distance * 100.0
                             if args.npc_max_distance is not None
                             else NPC_SPAWN_MAX_DISTANCE_CM))
        print(f"  NPCs: {args.npc_count} wanderers, spawning "
              f"{band_lo / 100.0:.0f}-{band_hi / 100.0:.0f} m out, running at "
              f"{NPC_RUN_SPEED_CMS:.0f} cm/s, {NPC_MELEE_DAMAGE:.0f} dmg melee "
              f"every {NPC_MELEE_INTERVAL_S:.1f} s inside {NPC_MELEE_RANGE_CM / 100.0:.0f} m")
    print(f"{'═' * 60}\n")

    # ── Step 1: Generate terrain mesh ────────────────────────────────────
    obj_path = os.path.join(output_dir, f"SM_{level_name}_Terrain.obj")
    print(f"[1/6] Generating terrain mesh → {obj_path}")
    terrain = generate_terrain_obj(obj_path, world_size_cm, grid_size=args.grid)
    grid_size = terrain["grid_size"]
    grid_z = terrain["grid_z"]
    print(f"       Grid: {grid_size}×{grid_size} ({grid_size**2} quads)")
    print(f"       File: {terrain['bytes']:,} bytes")

    # ── Step 2: Scatter trees ────────────────────────────────────────────
    print(f"\n[2/6] Scattering trees (seed={args.seed})...")
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
        print(f"\n[3/6] Grass generation disabled (--no-grass)")
        placed_grass = []
    else:
        print(f"\n[3/6] Scattering knee-high grass "
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

    # ── Step 4: Place the wandering NPCs ─────────────────────────────────
    if args.no_npc:
        print(f"\n[4/6] NPCs disabled (--no-npc)")
        placed_npcs = []
    else:
        print(f"\n[4/6] Placing {args.npc_count} wandering NPC(s)...")
        band_lo, band_hi, clamped = spawn_band(
            world_size_cm,
            min_distance_cm=(args.npc_min_distance * 100.0
                             if args.npc_min_distance is not None
                             else NPC_SPAWN_MIN_DISTANCE_CM),
            max_distance_cm=(args.npc_max_distance * 100.0
                             if args.npc_max_distance is not None
                             else NPC_SPAWN_MAX_DISTANCE_CM))
        if clamped:
            # Loud, because the requested band is a gameplay decision and the
            # navigable radius silently overriding it would be a surprise.
            print(f"       ⚠️  Band clamped to {band_lo / 100.0:.1f}-"
                  f"{band_hi / 100.0:.1f} m — the navigable radius on a "
                  f"{world_size_m:.0f} m map cannot hold the full request")
        placed_npcs = place_npcs(
            world_size_cm=world_size_cm,
            grid_z=grid_z,
            grid_size=grid_size,
            seed=args.seed,
            placed_trees=placed_trees,
            count=args.npc_count,
            min_distance_cm=band_lo,
            max_distance_cm=band_hi,
        )
        if not placed_npcs:
            print("       ⚠️  No legal NPC spawn point found.")
        for i, npc in enumerate(placed_npcs, start=1):
            print(f"       NPC {i}: ({npc.x:.0f}, {npc.y:.0f}, {npc.spawn_z:.0f}) cm, "
                  f"yaw {npc.yaw_deg:.0f}°, "
                  f"{npc.distance_to_player_cm / 100.0:.1f} m out, "
                  f"nearest trunk {npc.nearest_trunk_cm:.0f} cm, "
                  f"{npc.blocking_trees} blocking tree(s), "
                  f"{npc.attempts} attempt(s)")

    nav_bounds = None
    if placed_npcs:
        nav_bounds = compute_nav_bounds(world_size_cm, grid_z, grid_size)
        print(f"       Nav volume: +/-{nav_bounds['half_xy_cm']:.0f} cm XY, "
              f"Z {nav_bounds['center_z_cm'] - nav_bounds['half_z_cm']:.0f}..."
              f"{nav_bounds['center_z_cm'] + nav_bounds['half_z_cm']:.0f} cm "
              f"(terrain {nav_bounds['terrain_min_z_cm']:.0f}..."
              f"{nav_bounds['terrain_max_z_cm']:.0f})")

    # ── Step 5: Run verification ─────────────────────────────────────────
    print(f"\n[5/6] Running verification suite...")
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
        placed_npcs=placed_npcs,
        expect_npc=not args.no_npc,
        expected_npc_count=args.npc_count,
        nav_bounds=nav_bounds,
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

    # ── Step 6: Write the grass sidecar + Unreal scripts ─────────────────
    # Tens of thousands of transforms would bloat the generated script, so the
    # grass instances live in their own JSON file the import script reads.
    grass_data_path = os.path.join(output_dir, f"grass_{level_name}.json")
    _write_grass_data(grass_data_path, placed_grass)
    if placed_grass:
        print(f"\n       Grass data → {grass_data_path} "
              f"({os.path.getsize(grass_data_path):,} bytes)")


    print(f"\n[6/6] Writing Unreal import script...")
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
        placed_npcs=placed_npcs,
        nav_bounds=nav_bounds,
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
        placed_npcs=placed_npcs,
        nav_bounds=nav_bounds,
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
    placed_npcs,
    nav_bounds,
    lighting: dict,
):
    """Generate a self-contained Unreal Python script that imports everything."""

    npc_json = json.dumps([
        {
            "x": round(npc.x, 2),
            "y": round(npc.y, 2),
            "z": round(npc.spawn_z, 2),
            "yaw": round(npc.yaw_deg, 2),
        } for npc in (placed_npcs or [])
    ])
    nav_bounds_json = json.dumps(
        {k: round(v, 2) for k, v in nav_bounds.items()} if nav_bounds else None)

    # Grass mesh/material table, keyed by HISM actor label
    grass_configs = {
        s.name: {"mesh": s.mesh_path, "mats": list(s.material_paths)}
        for s in DEFAULT_GRASS_SPECS
    }
    grass_configs_json = json.dumps(grass_configs)
    scripts_dir = SCRIPTS_DIR
    nav_agent_radius = NAV_AGENT_RADIUS_CM
    nav_agent_height = NAV_AGENT_HEIGHT_CM

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
        import sys
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

        # ── 7. Navigation + wandering NPC ────────────────────────────────────
        NPC_SPAWNS = json.loads(r"""{npc_json}""")
        NAV_BOUNDS = json.loads(r"""{nav_bounds_json}""")
        SCRIPTS_DIR = r"{scripts_dir}"
        NAV_AGENT_RADIUS = {nav_agent_radius}
        NAV_AGENT_HEIGHT = {nav_agent_height}

        if NPC_SPAWNS:
            unreal.log_warning(
                f"[GEN] 7. Building navigation and spawning "
                f"{{len(NPC_SPAWNS)}} NPC(s)...")

            # NavMeshBoundsVolume's default brush is a 200 cm cube, so scaling
            # the actor by world_size/200 makes it cover the map exactly.
            # Sized from the terrain band the NPC can actually walk on, NOT
            # from the map width.  Recast voxelises the full height of every
            # tile, so an over-tall volume silently yields no tiles at all and
            # nothing is ever navigable.
            nav_volume = editor_actor_sub.spawn_actor_from_class(
                unreal.NavMeshBoundsVolume,
                unreal.Vector(0.0, 0.0, NAV_BOUNDS["center_z_cm"]))
            nav_volume.set_actor_label(f"{{LEVEL_NAME}}_NavBounds")
            # The default brush is a 200 cm cube, i.e. 100 cm half-extent.
            nav_volume.set_actor_scale3d(unreal.Vector(
                NAV_BOUNDS["half_xy_cm"] / 100.0,
                NAV_BOUNDS["half_xy_cm"] / 100.0,
                NAV_BOUNDS["half_z_cm"] / 100.0,
            ))

            # Deliberately do NOT place a RecastNavMesh actor.
            #
            # A headless editor never finishes an async navmesh bake, so any
            # RecastNavMesh saved from here carries EMPTY serialised tile data.
            # At game start the engine finds that data structurally valid and
            # reuses it instead of building -- 0 tiles, every MoveTo fails, and
            # the NPC never moves.  It only ever appeared to work right after a
            # nav-bounds change, because the changed parameters no longer matched
            # the serialised ones and the engine logged
            #   "Recreating dtNavMesh instance ... due mismatch in ... maxTiles"
            # and rebuilt.  Once the bounds settled, it silently stopped again.
            #
            # Leaving no nav data in the level makes the navigation system create
            # it at load, which always builds (324 tiles here).  Runtime
            # generation is Dynamic via Config/DefaultEngine.ini, since the nav
            # system overwrites per-actor values with class defaults anyway.
            # (the actual removal happens immediately before the save below --
            #  the navigation system re-creates nav data while the level is open,
            #  so removing it any earlier accomplishes nothing)

            # The NPC Blueprints are level-independent, so they live in their
            # own idempotent builder script rather than being re-emitted here.
            if SCRIPTS_DIR not in sys.path:
                sys.path.insert(0, SCRIPTS_DIR)
            import build_npc_blueprints
            from forest_generator.npc_placement import (
        gait_scale_for_index, variant_for_index)
            # force=True: the builder updates assets IN PLACE and is idempotent,
            # so re-running it is cheap -- and without it an existing
            # BP_ForestWanderer is reused wholesale and no property change in
            # build_npc_blueprints.py ever reaches the asset via this path.
            npc_variants = build_npc_blueprints.ensure_npc_variants(force=True)
            npc_classes = {{
                key: unreal.BlueprintEditorLibrary.generated_class(bp)
                for key, bp in npc_variants.items()
            }}

            # One actor per spawn point, labelled _NPC_Wanderer_<creature>_<n>.
            # The labels are what verify_<Level>.py matches on: it filters on
            # the _NPC_Wanderer prefix and sorts on the TRAILING number, so the
            # creature name goes in the middle -- appended, it would be read as
            # the index, every wanderer would sort as 0, and the pairwise
            # position checks would compare each NPC against the wrong spawn.
            # 1-based to line up with the generator's own console output.
            for i, spawn in enumerate(NPC_SPAWNS, start=1):
                variant = variant_for_index(i)
                npc_actor = editor_actor_sub.spawn_actor_from_class(
                    npc_classes[variant.key],
                    unreal.Vector(spawn["x"], spawn["y"], spawn["z"]),
                    # Keywords, not positional: unreal.Rotator is (roll, pitch, yaw).
                    unreal.Rotator(pitch=0.0, yaw=spawn["yaw"], roll=0.0),
                )
                npc_actor.set_actor_label(
                    f"{{LEVEL_NAME}}_NPC_Wanderer_{{variant.key}}_{{i}}")

                # Break the lockstep. See gait_scale_for_index -- rate and walk
                # speed move together so the stride stays planted.
                gait = gait_scale_for_index(i)
                npc_actor.get_editor_property("mesh").set_editor_property(
                    "global_anim_rate_scale", gait)
                move = npc_actor.get_editor_property("character_movement")
                move.set_editor_property(
                    "max_walk_speed",
                    move.get_editor_property("max_walk_speed") * gait)
                unreal.log_warning(
                    f"[GEN]    NPC {{i}} ({{variant.key}}) at ({{spawn['x']:.0f}}, "
                    f"{{spawn['y']:.0f}}, {{spawn['z']:.0f}})")
            unreal.log_warning(
                "[GEN]    navmesh is built by the navigation system at game "
                "start (no nav data saved in the level)")
            unreal.log_warning(
                f"[GEN]    Nav volume: +/-{{NAV_BOUNDS['half_xy_cm']:.0f}} cm XY, "
                f"Z span {{NAV_BOUNDS['half_z_cm'] * 2.0:.0f}} cm "
                f"centred {{NAV_BOUNDS['center_z_cm']:.0f}}")
        else:
            unreal.log_warning("[GEN] 7. NPCs skipped (none placed).")

        # ── 8. Save ─────────────────────────────────────────────────────────
        # Strip nav data as the very last action: the navigation system
        # re-creates a RecastNavMesh whenever the level is open, and anything
        # saved here carries EMPTY serialised tiles that the game then reuses
        # instead of building (see section 7).
        stripped = 0
        for a in list(editor_actor_sub.get_all_level_actors()):
            if isinstance(a, unreal.RecastNavMesh):
                editor_actor_sub.destroy_actor(a)
                stripped += 1
        unreal.log_warning(f"[GEN] Stripped {{stripped}} RecastNavMesh actor(s) before save")
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
    placed_npcs,
    nav_bounds,
    lighting: dict,
):
    """Generate an Unreal Python script that verifies the level after import."""

    npc_json = json.dumps([
        {
            "x": round(npc.x, 2),
            "y": round(npc.y, 2),
            "z": round(npc.spawn_z, 2),
            "yaw": round(npc.yaw_deg, 2),
            "distance_cm": round(npc.distance_to_player_cm, 2),
        } for npc in (placed_npcs or [])
    ])
    variants_json = json.dumps([
        {"key": v.key, "blueprint": v.blueprint, "mesh": v.mesh,
         "anim_bp": v.anim_bp, "melee": v.melee,
         "ai_blueprint": v.ai_blueprint} for v in NPC_VARIANTS])
    npc_gaits = json.dumps([gait_scale_for_index(i)
                            for i in range(1, len(placed_npcs or []) + 1)])
    npc_run_speed = NPC_RUN_SPEED_CMS
    npc_melee_range = NPC_MELEE_RANGE_CM
    nav_reachable_extent = NAV_REACHABLE_EXTENT_CM
    npc_melee_damage = NPC_MELEE_DAMAGE
    npc_melee_interval = NPC_MELEE_INTERVAL_S
    nav_agent_radius = NAV_AGENT_RADIUS_CM
    nav_bounds_json = json.dumps(
        {k: round(v, 2) for k, v in nav_bounds.items()} if nav_bounds else None)
    nav_max_span = NAV_MAX_VERTICAL_SPAN_CM
    capsule_half = NPC_CAPSULE_HALF_HEIGHT_CM

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
        instances (including that grass really is knee high), the NPC and its
        navigation rig, and the time-of-day lighting rig.
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
        EXPECTED_NPCS = json.loads(r"""{npc_json}""")
        EXPECTED_NPC_RUN_SPEED = {npc_run_speed}
        EXPECTED_VARIANTS = json.loads(r"""{variants_json}""")
        # Per-instance gait multipliers -- see npc_placement.gait_scale_for_index.
        EXPECTED_NPC_GAITS = json.loads(r"""{npc_gaits}""")
        EXPECTED_MELEE_RANGE = {npc_melee_range}
        EXPECTED_MELEE_DAMAGE = {npc_melee_damage}
        EXPECTED_MELEE_INTERVAL = {npc_melee_interval}
        EXPECTED_NAV_AGENT_RADIUS = {nav_agent_radius}
        EXPECTED_REACHABLE_EXTENT = {nav_reachable_extent}
        EXPECTED_NAV_BOUNDS = json.loads(r"""{nav_bounds_json}""")
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

        # ── 6. Navigation + NPCs ─────────────────────────────────────────────
        if EXPECTED_NPCS:
            npc_actors = []
            nav_bounds = None
            nav_mesh = None
            for a in actors:
                lbl = a.get_actor_label()
                if lbl.startswith(f"{{LEVEL_NAME}}_NPC_Wanderer"):
                    npc_actors.append(a)
                elif lbl == f"{{LEVEL_NAME}}_NavBounds":
                    nav_bounds = a
                elif lbl == f"{{LEVEL_NAME}}_NavMesh":
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
                check(f"Asset Exists {{path.rsplit('/', 1)[-1]}}",
                      editor_asset_sub.does_asset_exist(path))

            # Each creature must animate against ITS OWN skeleton. Sharing one
            # skeleton across monsters is what put the wendigo's forward neck
            # pitch on the zombie and left its head hanging off the front of
            # its chest -- and nothing errored, at build time or at runtime.
            # This is the check that would have caught it.
            seen_skeletons = {{}}
            for variant in EXPECTED_VARIANTS:
                bp = editor_asset_sub.load_asset(variant["blueprint"])
                if not bp:
                    check(f"{{variant['key']}} Blueprint Loads", False)
                    continue
                cdo = unreal.get_default_object(
                    unreal.BlueprintEditorLibrary.generated_class(bp))
                comp = cdo.get_editor_property("mesh")
                mesh = comp.get_editor_property("skeletal_mesh_asset")
                anim_cls = comp.get_editor_property("anim_class")
                mesh_skel = mesh.get_editor_property("skeleton") if mesh else None

                check(f"{{variant['key']}} Wears Its Own Mesh",
                      mesh is not None and variant["mesh"].endswith(mesh.get_name()),
                      f"(got {{mesh.get_name() if mesh else None}})")

                anim_skel = None
                if anim_cls:
                    anim_bp = editor_asset_sub.load_asset(variant["anim_bp"])
                    if anim_bp:
                        anim_skel = anim_bp.get_editor_property("target_skeleton")
                check(f"{{variant['key']}} Anim BP Matches Its Skeleton",
                      anim_skel is not None and anim_skel == mesh_skel,
                      f"(mesh on {{mesh_skel.get_name() if mesh_skel else None}}, "
                      f"anim BP on {{anim_skel.get_name() if anim_skel else None}})")

                melee = editor_asset_sub.load_asset(variant["melee"])
                check(f"{{variant['key']}} Attack Clip Matches Its Skeleton",
                      melee is not None
                      and melee.get_editor_property("skeleton") == mesh_skel,
                      f"(clip on "
                      f"{{melee.get_editor_property('skeleton').get_name() if melee else None}})")

                if mesh_skel:
                    seen_skeletons.setdefault(mesh_skel.get_name(), []).append(
                        variant["key"])

            shared = {{k: v for k, v in seen_skeletons.items() if len(v) > 1}}
            check("Each Creature Has Its Own Skeleton", not shared,
                  f"(shared: {{shared}} -- one of these wears another's bind pose)")

            npc_bp = editor_asset_sub.load_asset("/Game/Forest/NPC/BP_ForestWanderer")
            if npc_bp:
                cdo = unreal.get_default_object(
                    unreal.BlueprintEditorLibrary.generated_class(npc_bp))
                ai_cls = cdo.get_editor_property("ai_controller_class")
                check("NPC AI Controller Class",
                      ai_cls is not None and "ForestWandererAI" in str(ai_cls),
                      f"(got {{ai_cls}})")
                check("NPC Auto Possess AI",
                      cdo.get_editor_property("auto_possess_ai") ==
                      unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
                mv = cdo.get_editor_property("character_movement")
                speed = mv.get_editor_property("max_walk_speed")
                check("NPC Runs At The Player",
                      close(speed, EXPECTED_NPC_RUN_SPEED, 0.5),
                      f"(expected {{EXPECTED_NPC_RUN_SPEED}} cm/s, got {{speed}})")
                check("NPC Orients To Movement",
                      mv.get_editor_property("orient_rotation_to_movement") is True)
                mesh_comp = cdo.get_editor_property("mesh")
                check("NPC Has Skeletal Mesh",
                      mesh_comp.get_editor_property("skeletal_mesh_asset") is not None)
                check("NPC Animation Mode Blueprint",
                      mesh_comp.get_editor_property("animation_mode") ==
                      unreal.AnimationMode.ANIMATION_BLUEPRINT,
                      f"(got {{mesh_comp.get_editor_property('animation_mode')}})")
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
                names = {{str(v) for v in BEL.list_member_variable_names(ai_bp, False)}}
                check("NPC Melee Cooldown Variable", "NextAttackTime" in names,
                      f"(variables: {{sorted(names)}})")
                for label, value in (("Range", EXPECTED_MELEE_RANGE),
                                     ("Damage", EXPECTED_MELEE_DAMAGE),
                                     ("Interval", EXPECTED_MELEE_INTERVAL)):
                    check(f"NPC Melee {{label}} Literal",
                          any(close(float(v), value, 0.01)
                              for v in literals
                              if v.replace(".", "", 1).replace("-", "", 1).isdigit()),
                          f"(expected {{value}})")
                check("NPC Melee Plays An Attack Montage",
                      any("MM_Attack" in v for v in literals))
                check("NPC Melee Uses The Upper-Body Slot",
                      any(v == "DefaultSlot" for v in literals))
                check("NPC Graph Compiles Clean",
                      ed is not None and not ed.list_nodes_with_errors())
                # Debugging the chase means splicing PrintStrings into this
                # graph (it is the only way to see what the AI is measuring),
                # so guard against one being left behind.
                check("No Leftover Debug PrintStrings In The AI Graph",
                      not [n for n in nodes
                           if "PrintString" in
                           " ".join(str(BEL.get_node_title(n)).split())])
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
                    return {{str(PIN.get_pin_name(q))
                            for q in BEL.list_input_pins(n)}}
                moves = [n for n in nodes
                         if {{"Goal", "AcceptanceRadius"}} <= ins(n)]
                check("NPC Chase Has One Move Order", len(moves) == 1,
                      f"(got {{len(moves)}})")
                if moves:
                    drivers = [PIN.get_owning_node(q) for q in
                               BEL.find_execute_pin(moves[0]).list_connected_pins()]
                    check("NPC Chase Is Gated On Possession",
                          bool(drivers) and all(
                              d.get_class().get_name() == "K2Node_IfThenElse"
                              for d in drivers),
                          f"(driven by {{[d.get_class().get_name() for d in drivers]}})")
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
                          if {{"Dest", "bUsePathfinding"}} <= ins(n)]
                check("NPC Has A Straight-Line Move Order", len(direct) == 1,
                      f"(got {{len(direct)}})")
                if direct:
                    def lit(node, pin):
                        return str(PIN.get_pin_value(
                            BEL.find_input_pin(node, pin)))
                    check("Straight-Line Order Does Not Pathfind",
                          lit(direct[0], "bUsePathfinding") == "false",
                          f"(got {{lit(direct[0], 'bUsePathfinding')}})")
                    # The whole bug, restated: projecting the destination back
                    # onto the navmesh walks the NPC to the island edge and
                    # stops it there, which is exactly what it used to do.
                    check("Straight-Line Order Keeps The Real Destination",
                          lit(direct[0], "bProjectDestinationToNavigation")
                          == "false",
                          f"(got {{lit(direct[0], 'bProjectDestinationToNavigation')}})")
                    check("Pathfinding Order Still Pathfinds",
                          lit(moves[0], "bUsePathfinding") == "true"
                          if moves else False)
                # Both ends are tested -- the player may have walked off the
                # navmesh, and so may the wanderer.
                projections = [n for n in nodes
                               if {{"Point", "QueryExtent"}} <= ins(n)]
                check("Reachability Tests Both Ends Of The Chase",
                      len(projections) == 2, f"(got {{len(projections)}})")
                # A loose query box answers "yes, reachable" for a player ten
                # metres outside the island by snapping to its edge, which is
                # the dead zone with extra steps.  A tight one in Z reports a
                # player standing squarely ON the navmesh as being off it,
                # because the point is a capsule centre and a Recast polygon
                # can sit most of a metre under the real ground.
                extents = [n for n in nodes if {{"X", "Y", "Z"}} <= ins(n)]
                want_extent = [f"{{v:.1f}}" for v in EXPECTED_REACHABLE_EXTENT]
                check("Reachability Query Box Matches The Constant",
                      any([str(PIN.get_pin_value(BEL.find_input_pin(n, a)))
                           for a in ("X", "Y", "Z")] == want_extent
                          for n in extents),
                      f"(expected {{want_extent}})")
                # One branch, feeding both move orders: the pathfinding one on
                # True and the straight line on False.
                if direct and moves:
                    def driver_of(node):
                        pins = BEL.find_execute_pin(node).list_connected_pins()
                        return {{PIN.get_owning_node(q) for q in pins}}
                    shared = driver_of(moves[0]) & driver_of(direct[0])
                    check("One Branch Chooses Between The Two Move Orders",
                          len(shared) == 1 and next(iter(shared)).get_class()
                          .get_name() == "K2Node_IfThenElse",
                          f"(shared drivers: {{len(shared)}})")

            # -- The placed actors --
            check("NPC Count",
                  len(npc_actors) == len(EXPECTED_NPCS),
                  f"(expected {{len(EXPECTED_NPCS)}}, got {{len(npc_actors)}})")
            for i, (actor, want) in enumerate(zip(npc_actors, EXPECTED_NPCS),
                                              start=1):
                loc = actor.get_actor_location()
                check(f"NPC {{i}} Spawn Location",
                      close(loc.x, want["x"], 1.0)
                      and close(loc.y, want["y"], 1.0)
                      and close(loc.z, want["z"], 1.0),
                      f"(expected {{want['x']:.0f}},{{want['y']:.0f}},{{want['z']:.0f}} "
                      f"got {{loc.x:.0f}},{{loc.y:.0f}},{{loc.z:.0f}})")
                dist = (loc.x ** 2 + loc.y ** 2) ** 0.5
                check(f"NPC {{i}} In The Spawn Band",
                      close(dist, want["distance_cm"], 2.0),
                      f"({{dist / 100.0:.1f}} m from the player start)")
                check(f"NPC {{i}} Is A Character",
                      isinstance(actor, unreal.Character))

            # -- Navigation rig --
            check("Nav Bounds Volume Exists", nav_bounds is not None)
            if nav_bounds and EXPECTED_NAV_BOUNDS:
                origin, extent = nav_bounds.get_actor_bounds(False)
                want_xy = EXPECTED_NAV_BOUNDS["half_xy_cm"]
                want_z = EXPECTED_NAV_BOUNDS["half_z_cm"]
                check("Nav Bounds XY Extent",
                      close(extent.x, want_xy, 2.0) and close(extent.y, want_xy, 2.0),
                      f"(expected +/-{{want_xy:.0f}}, got {{extent.x:.0f}}x{{extent.y:.0f}})")
                check("Nav Bounds Z Extent",
                      close(extent.z, want_z, 2.0),
                      f"(expected +/-{{want_z:.0f}}, got {{extent.z:.0f}})")
                check("Nav Bounds Centred On Terrain",
                      close(origin.z, EXPECTED_NAV_BOUNDS["center_z_cm"], 2.0),
                      f"(expected z {{EXPECTED_NAV_BOUNDS['center_z_cm']:.0f}}, "
                      f"got {{origin.z:.0f}})")
                # The bug that made the NPC immobile: an over-tall volume makes
                # Recast generate no tiles at all.
                check("Nav Bounds Vertical Span Sane",
                      extent.z * 2.0 <= {nav_max_span},
                      f"(span {{extent.z * 2.0:.0f}} cm, limit {nav_max_span:.0f})")
                # Lockstep guard: every wanderer must have its own gait, and
                # its animation rate must match its ground speed or its feet
                # skate.  A regression here is invisible in a screenshot and
                # obvious in motion, which is exactly why it is checked.
                gaits, mismatched = [], []
                for i, actor in enumerate(npc_actors, start=1):
                    want = EXPECTED_NPC_GAITS[i - 1]
                    rate = actor.get_editor_property("mesh").get_editor_property(
                        "global_anim_rate_scale")
                    speed = actor.get_editor_property(
                        "character_movement").get_editor_property("max_walk_speed")
                    gaits.append(round(rate, 4))
                    if not (close(rate, want, 0.001)
                            and close(speed, EXPECTED_NPC_RUN_SPEED * want, 0.5)):
                        mismatched.append(
                            f"NPC {{i}} rate {{rate:.3f}} speed {{speed:.1f}} "
                            f"(wanted {{want:.3f}} / "
                            f"{{EXPECTED_NPC_RUN_SPEED * want:.1f}})")
                check("NPC Gaits Are Staggered", len(set(gaits)) == len(gaits),
                      f"(rates {{sorted(gaits)}} -- duplicates march in lockstep)")
                check("NPC Anim Rate Matches Ground Speed", not mismatched,
                      "; ".join(mismatched))

                # Every NPC must stand inside the volume or it has no navmesh.
                outside = []
                for i, actor in enumerate(npc_actors, start=1):
                    loc = actor.get_actor_location()
                    feet_z = loc.z - {capsule_half}
                    if not (abs(loc.x) <= want_xy and abs(loc.y) <= want_xy
                            and abs(feet_z - origin.z) <= want_z):
                        outside.append(f"NPC {{i}} at ({{loc.x:.0f}},{{loc.y:.0f}},"
                                       f"feet {{feet_z:.0f}})")
                check("NPCs Inside Nav Bounds", not outside,
                      f"(volume {{origin.z - want_z:.0f}}..{{origin.z + want_z:.0f}}"
                      f"{{'; outside: ' + ', '.join(outside) if outside else ''}})")
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
