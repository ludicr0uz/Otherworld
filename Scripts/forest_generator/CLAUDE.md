# The level generator

`Scripts/generate_forest_level.py` is pure Python, with no `unreal` import. It computes the
terrain, trees, grass and NPC placement, and runs the offline checks. Then it **code-generates**
`import_<Level>.py` and `verify_<Level>.py` into `Scripts/generated_levels/<Level>/`. Run those
two through `uepy.py`. Generation is deterministic for a given seed. The entry point is 1.8k
lines, over budget, so split it before extending it.

```bash
python3 Scripts/generate_forest_level.py --size 200 --time-of-day night
# --size <m, required> --name --seed (42) --grid --time-of-day {night,day}
# --tree-density (0.5 × count_per_hectare) --grass-density (1.2/m²) --grass-height (50 cm)
# --grass-patchiness (0.25) --no-grass --no-npc --npc-count (10)
# --npc-min-distance (75 m) --npc-max-distance (100 m) --json-report
```

## Modules

The generator's code lives in this package. The level-side import code is in
`Scripts/forest_import/`.

| module | owns |
|---|---|
| `terrain.py` | heightfield and OBJ |
| `tree_placement.py` | `DEFAULT_TREE_SPECS` and the scatter (`MIN_TREE_SPACING_CM` 150, checked through a spatial hash) |
| `tree_meshes.py` | the meshes the trees are planted from: a recipe per species (`TREE_MESH_RECIPES`) that cuts a scan down. `forest_import/tree_assets.py` builds them under `/Game/Forest/Trees`; the level import calls it |
| `tree_lods.py` | which levels plant the trees' other build, a LOD chain ending in an impostor (`TREE_LOD_LEVELS`: the 1 km map, and the title level, which plants that map's middle trees: `Scripts/title/forest.py`), and where that mesh is |
| `grass_placement.py` | `DEFAULT_GRASS_SPECS` and a stratified scatter |
| `bush_placement.py` | `DEFAULT_BUSH_SPECS` and the clustered scatter |
| `undergrowth_meshes.py` | the two library meshes the grass and the bushes are planted from, and the packages of each that the repository carries ("Rendering gotchas", below) |
| `npc_placement.py` | NPC numbers (see `Scripts/npc/CLAUDE.md`) |
| `npc_agro.py` | sense and patrol numbers |
| `npc_strafe.py` | the step a wanderer takes between two swings |
| `wind.py` | the wind's numbers: `MPC_Wind`, amplitudes and frequencies. `forest_import/wind.py` writes it into the materials (below) |
| `lighting.py` | time-of-day presets (star_brightness 2.5, sun 0.12, exposure bias 1.6) and `SHADOW_DISTANCE_CM`. The level's rig is the static sky; at runtime `BP_DayNightCycle` replaces it and reuses these values (`Scripts/world/CLAUDE.md`) |
| `verification.py` | the offline suite (over budget) |
| `asset_sources.py` | what produces each `Content/` directory, and `RESTORE_ORDER` |

## The two maps

- **`Lvl_Forest_200m`** (`--size 200`):
  - night, 68 trees, ~41k grass clumps, 328 bushes, ten NPCs at 75–79 m;
  - it is the `EditorStartupMap`: the debug map.
- **`Lvl_Forest_1000m`** (`--size 1000`, tree density 0.5):
  - 1,700 trees, ~1.0 M grass clumps, 8,239 bushes;
  - its trees are the LOD build, not the Nanite one ("Rendering gotchas", below);
  - it is the `GameDefaultMap`: what a packaged or standalone run boots;
  - the `.umap` is 185 MB;
  - the import takes about a minute. `uepy.py` reports that the editor stopped responding, but
    the job keeps going; read the editor log.

**Terrain past 200 m is a different shape** (`terrain._make_large_elevation_fn`). The radial
bowl's corners outgrow the navmesh's Z limit, so larger maps use:
- hills faded in over a 40 m ring, under 6 m tall;
- a 60 m-wide, 20 m-tall rim based on box distance.

**Grass transforms live in a git-ignored `grass_<Level>.json` sidecar,** not in the generated
script.

**After an import, re-run `place_forage.py`, `build_clothing.py` and `build_day_night.py`.** The
import rebuilds the level from scratch, which drops the forage, the garments lying in it and
the day/night cycle actor.

## Navmesh

- **The volume covers the whole terrain.**
  - `NAV_COVERAGE_FRACTION` is 1.0, and `NAV_MAX_HALF_XY_CM` is 50000.
  - `compute_nav_bounds` samples the **box**, corners included.
  - `NAV_MAX_VERTICAL_SPAN_CM` is 5000.
- **Recast silently builds zero tiles when the volume is too TALL** (for example 8000 cm), but XY
  size is fine. Size the volume from the terrain's elevation band.
- **At runtime on the 1 km map, tiles build nearest-first:**
  - the spawn band is ready at about 8 s;
  - the whole map takes about 2 min.
- **Never save a `RecastNavMesh` into a generated level.**
  - A headless editor can't finish the async bake, so the saved tiles are empty. The game then
    reuses them: 0 tiles, and frozen NPCs.
  - The import script strips nav data immediately before saving, and runtime generation is
    `DYNAMIC`, set in the level and in `DefaultEngine.ini`.
  - **Any later save puts one back,** because the editor re-creates the actor whenever the
    level is open. A game world loads it and never builds a tile: only nav data the game
    spawns itself is rebuilt at start. PIE hides it (it copies the editor's tiles); a packaged
    or `-game` run has wanderers that never leave their spawn.
  - So scripts save a level through `world/level_save.py` (`save_level`), which strips it, and
    `uepy.py --close-editors` strips it from a dirty level. A save by hand in the editor
    (Ctrl+S) still writes it.
  - `python3 Scripts/dev/check_saved_navmesh.py` reads the maps on disk and says which carry
    one. Run it before packaging.
- **The editor and PIE need `bForceRebuildOnLoad=True`** (`DefaultEngine.ini`).
  - `-game` spawns a fresh RecastNavMesh and builds it.
  - The editor treats the one it re-creates on open as loaded, skips the load-time rebuild and
    stays at 0 tiles.
  - PIE copies the editor's navmesh and builds nothing of its own. Without the flag, every
    wanderer's patrol query fails in PIE and the pack stands still.
  - PIE gets only the tiles that exist when Play is pressed. The 1 km map needs about 2 min after
    opening. Check with `project_point_to_navigation` at the NPCs' spawn points.
- **The nav system overwrites `agent_radius`/`agent_height` with its default agent.** To change
  them, widen Supported Agents in the project settings.
- **Measure a navmesh by projecting points at it,** not by reading its settings:
  1. Resize the volume.
  2. Run `RebuildNavigation`.
  3. Call `NavigationSystemV1.project_point_to_navigation` across a fan of headings.

  Use the terrain's exact Z, because a downward trace lands on canopies. Change one dial at a
  time.

## Rendering gotchas

- **The terrain mesh needs Nanite off plus `CTF_USE_COMPLEX_AS_SIMPLE`.**
- **Grass HISMs:**
  - one per species per 100 m cell (`grass_cells.py`, `forest_import/grass.py`), labelled
    `<spec>__±ix_±iy`, tagged `OW_Grass`;
  - no collision, saved unlit;
  - they cull at 60–90 m × `r.ViewDistanceScale`.
- **Grass and bushes are one library mesh each, planted where its Fab pack put it**
  (`undergrowth_meshes.py`): `grass_02_09_mesh` (60 cm tall, 54 cm across, 2,152 triangles)
  and `SM_Bush_02` (1.95 m tall, 3.5 m across, 1,304 triangles).
  - Neither is Nanite. Each has four mesh LODs and a masked two-sided material, and a cell
    draws the mesh's own materials (the specs name none).
  - **They sway by their pack's wind, not `MPC_Wind`.** The graphics menu's wind strength and
    speed do not reach them; its world-position-offset switch still does.
  - **The packs are git-ignored but these two meshes are committed.** `.gitignore`
    re-includes exactly the packages each needs (22 files, 116 MB, of which the grass pack's
    8k atlas is 109 MB). To plant another library mesh, add its record and its packages to
    `undergrowth_meshes.py` and its `gitignore_lines()` to `.gitignore`;
    `dev/tests/test_undergrowth_meshes.py` holds the two together, and the level verifier
    fails if a mesh references a package outside its list.
  - Nothing writes to a pack asset. `forest_import/undergrowth_assets.py` only checks them:
    the import stops if one is missing, and the verifier re-measures height, LOD count and
    triangles, so a pack update that changes the mesh fails there.
  - **A grass clump is a third of the width of the generated patch it replaced,** so at the
    same count (about 1/m² with every tier drawn) the ground is tufts with terrain between
    them. Grass is scaled to the target height from the mesh's real bounds at plant time;
    the offline check caps the upscale at 2.4×.
  - **The generated patches and bushes are still in the tree but no level plants them:**
    `foliage_meshes.py`, `forest_import/foliage_assets.py` and `/Game/Forest/Procedural`.
    The level import no longer builds them.
  - After changing a bush spec's mesh, run
    `uepy.py --only footsteps Scripts/build_weapons_and_combat.py`: the footstep component
    holds the bush meshes for the rustle (`Scripts/Sound/CLAUDE.md`), and
    `verify_weapons_and_combat.py` fails until it is rebuilt.
- **A tree with low leaves rustles as a bush does** (`low_leaves.py`: each tree's leaf slot
  and lowest leaf, and the rule that picks the pine sapling alone). After a recipe or a
  tree spec's scale changes, run its unit test (`dev/tests/test_low_leaves.py`) and the
  same footsteps build: `verify_weapons_and_combat.py` measures each built mesh's lowest
  leaf against the table. **A tree's leaves are in its collision:** it is cooked from the
  Nanite fallback, which keeps about a tenth of them, so a sapling is pushed into, not
  walked through.
- **Trees are cut-down copies of dense scans.** The scans (0.14–4.2 M triangles, 13–112 MB) stay
  under `/Game/Forest/Scanned` as imported; the levels plant the copies under
  `/Game/Forest/Trees` (33–240 k triangles), in the same per-cell HISMs as the grass
  (`tree_cells.py`, `forest_import/trees.py`).
  - Never write to a mesh under `/Game/Forest/Scanned`, and never plant one. To change a tree,
    change its recipe in `tree_meshes.py`; the next import rebuilds it (the five take about two
    minutes, then are skipped until a recipe changes).
  - **Never set a field on the struct a scan's `get_editor_property("nanite_settings")`
    returns.** It is still bound to the mesh: the edit lands on the scan in memory and marks
    its package dirty, and the editor then offers to save (or, after a crash, to restore) it
    over the original. Build a fresh `unreal.MeshNaniteSettings()`. The level verifier's
    "Scan Left Unmodified" checks guard this.
  - What a tree costs is how many leaves it has, not how many triangles each leaf has: Nanite
    here rasterises everything in hardware and draws a crown leaf by leaf. A recipe drops a
    share of the leaves and grows the rest. The numbers behind each choice are in the
    `tree_meshes.py` docstring and `graphisOptimizationStrategy.md`.
  - Re-measure with `Scripts/probes/probe_perf_audit_1km.py`, with no editor open: an open
    editor's viewport shares the GPU and moves the numbers by a millisecond or two.
  - Never switch Nanite off on a scan: it takes 25+ minutes per mesh in the game-thread
    simplifier.
  - `disallow_nanite` on the tree HISMs draws the fallback mesh, which is thinner in the crown
    than the Nanite one. Measured, it is 2–5 ms cheaper than Nanite on this Mac, but it has no
    LODs and nothing uses it.
  - `get_number_verts` and `get_num_triangles` report the fallback's count, not the mesh's.
  - Trees fade out at 250–300 m × `r.ViewDistanceScale`. Collision and the navmesh still cover
    every tree.
- **The 1 km map plants a second build of the same five trees,** under
  `/Game/Forest/TreesLOD`: no Nanite, three mesh LODs (about 40 k, 16 k and 6 k triangles,
  starting at 0, 30 and 60 m) and from 110 m an impostor, three crossed cards with a picture
  of the tree.
  - `tree_lods.py` names the levels (`TREE_LOD_LEVELS`); `forest_import/trees.py` swaps the
    mesh when it plants and checks the other set of things when it verifies. A level changes
    build by a line there and a re-import. The 200 m and probe levels stay on Nanite.
  - The meshes are built from `/Game/Forest/Trees` by
    `python3 Scripts/build_game_ready_mesh.py trees`, outside the editor (`mesh_lod/`; about
    2.5 minutes, skipped until a setting changes). The level import does not build them: it
    stops, naming that command, if one is missing. After a tree's recipe changes, run it with
    `--force` and re-import the level.
  - A cell's instances change LOD together, at the distance for the middle of that cell's
    scales (`FHierarchicalStaticMeshSceneProxy`, `AverageScale`), so the same species can
    switch a third nearer or further from one cell to the next.
  - The Nanite settings on a cell (`disallow_nanite`, the leaf mask distance) do not apply
    to these and are not set; the cull distances are the same.
- **Past `TREE_LEAF_MASK_DISTANCE_CM` (60 m), leaves draw without their opacity mask.** This is a
  performance trade; tune it by eye.
- **Wind is world-position offset** (`wind.py`, `forest_import/wind.py`), scaled by
  `MPC_Wind.Strength` and `.Speed`, which the graphics menu sets
  (`Scripts/graphics_menu/CLAUDE.md`, "Wind"). Its time is the material's own plus
  `MPC_Wind.TimeOffset`, which `BP_DayNightCycle` writes so that every machine of a server
  is at one point of the sway (`Scripts/world/CLAUDE.md`, "One clock"); 0 as built:
  - **Nothing is pushed straight along `DIRECTION`**, which is only the prevailing wind. Each
    clump's and each tree's heading veers off it: by a field that drifts over the ground (two
    crossing wave trains, `GUST_HEADINGS`, so it changes in patches) plus an angle of the
    instance's own (`PerInstanceRandom`). The gusts are the same two trains, and a tree also
    rocks across its heading. The numbers are the `*_VEER_*`, `*_SCATTER_TURNS` and
    `*_CROSS_*` constants; `verify_wind` checks each material turns its heading.
  - `M_ProcFoliage` (the generated grass and bushes, which no level plants now) leans and
    sways by its vertex alpha, in gusts across the field; it is rebuilt whole by
    `foliage_assets.build_material`. The library grass and bushes are not on it.
  - **`M_Master_Bark` and `M_Master_Foliage` have no builder** (it was deleted), so the wind
    is **patched** into them: every node it adds has the desc `OW_Wind`, and a re-run deletes
    those first. Both bend by `(local height / 15 m)^2` (the mesh's origin is the trunk
    base), so trunk, branches and leaves move together; the leaves flutter on top. The rocks,
    stumps, shrubs and ferns on these masters get the same bend, which is tiny at their height.
  - The level import runs it (`ensure_wind`), and the level verifiers check it
    (`verify_wind`); standalone: `uepy.py Scripts/forest_import/wind.py`.
  - `PreSkinnedPosition` is the local position under Nanite too. A tree that does not move
    in a shot is most likely past the WPO disable distance the graphics menu set.
- **The directional light's shadow range is set through
  `dynamic_shadow_distance_movable_light`,** even though the light is Stationary, because
  static lighting is off.
- **`M_NightSky_Starfield` is built from scratch** (unlit, two-sided, `is_sky`), because the
  engine sky materials expose no star parameters.
- **UE 5.8 renamed the fog property to `fog_inscattering_luminance`.** Use `try_set_first([...])`.
- **Generated scripts come from `textwrap.dedent(f'''...''')` templates,** so double any literal
  braces.
