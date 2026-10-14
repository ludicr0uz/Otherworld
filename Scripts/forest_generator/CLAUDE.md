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
| `grass_placement.py` | `DEFAULT_GRASS_SPECS` and a stratified scatter; with several specs it picks each spot's by `grass_regions`, and plants a spot `density_scale` times |
| `grass_regions.py` | where each grass type grows (F2): one value-noise field per type, the type whose field is highest owns the ground, close fields mix (`RegionMix`, pure Python) |
| `bush_placement.py` | `DEFAULT_BUSH_SPECS` and the clustered scatter |
| `grass_look.py` | the dark, ground-filling grass: the colours of its material instance and of the ground under it (each with its reason), the levels that have the colour (`DARK_GRASS_LEVELS`: the 200 m and 1 km maps) and the ones that plant the patch (`PATCH_GRASS_LEVELS`: the 200 m map alone; `grass_specs_for(level)`), the density a level is held at when the default moves (`HELD_DENSITY_PER_SQM`: the 1 km map at 1.1/m²; `density_for(level)`, the generator's default for `--grass-density`), and the seven grass types of a varied level (`VARIED_GRASS_LEVELS`, `LOW_GRASS_TYPES`: F2). `forest_import/grass_look.py` builds the instances and patches the ground material from it ("Rendering gotchas", below) |
| `undergrowth_meshes.py` | the library meshes the grass and the bushes are planted from (the clump, the bush and the six low grasses of F2), the grass patch made of one (`GRASS_PATCH`), and the packages of each that the repository carries ("Rendering gotchas", below) |
| `grass_patch.py` | the grass patch's numbers (G3): the seven copies of the clump, their LOD chain and its distances, and the Pivot Painter 2 texels moved with each copy, each with its reason. `forest_import/grass_patch.py` builds it (`Scripts/build_grass_patch.py`) and verifies it |
| `pivot_images.py` | the two image files the patch's pivot textures are imported from (a half-float EXR, an 8-bit PNG), in plain Python |
| `npc_placement.py` | NPC numbers (see `Scripts/npc/CLAUDE.md`) |
| `npc_agro.py` | sense and patrol numbers |
| `npc_strafe.py` | the step a wanderer takes between two swings |
| `wind.py` | the wind's numbers: `MPC_Wind`, amplitudes and frequencies. `forest_import/wind.py` writes it into the materials (below) |
| `lighting.py` | time-of-day presets (star_brightness 2.5, sun 0.12, exposure bias 1.6) and `SHADOW_DISTANCE_CM`. The level's rig is the static sky; at runtime `BP_DayNightCycle` replaces it and reuses these values (`Scripts/world/CLAUDE.md`) |
| `verification.py` | the offline suite (over budget) |
| `asset_sources.py` | what produces each `Content/` directory, and `RESTORE_ORDER` |

## The two maps

- **`Lvl_Forest_200m`** (`--size 200`):
  - night, 68 trees, 289,450 grass clumps of seven types on 162,534 spots (4.4/m² requested
    over eight layers, F1; F2's six low grasses plant up to two clumps a spot, the patch one;
    the first four layers were G2's 81,697 at 2.2), 328 bushes, ten NPCs at 75–79 m;
  - it is the `EditorStartupMap`: the debug map.
- **`Lvl_Forest_1000m`** (`--size 1000`, tree density 0.5):
  - 1,700 trees, 1,025,988 grass clumps of seven types (one a spot), 8,239 bushes; its
    grass is 2,800 cell actors (seven types × four tiers × 100 cells; 400 with one type);
  - its grass is held at 1.1/m² (`grass_look.HELD_DENSITY_PER_SQM`), half the default: at
    2.2 it would be about 2.05 million clumps and a `.umap` of about 360 MB (170 bytes a clump: the grass is
    nearly all of today's 185). Regenerating it without `--grass-density` keeps 1.1;
  - its trees are the LOD build, not the Nanite one ("Rendering gotchas", below);
  - it is the `GameDefaultMap`: what a packaged or standalone run boots;
  - the `.umap` is 181 MB;
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
the day/night cycle actor. The import also rebuilds the dark grass's material instances and
re-applies the ground's tint (`forest_import/grass_look.py`), on whichever level it runs.

**The first game runs after an import are slow, and prove nothing about the frame.** The
game rebuilds what the import invalidated while it plays: three windowed runs after G2's
import measured 100–200 ms a frame (one stalled) where the fourth measured 32. Run a
measuring probe twice, and with no editor holding the 1 km level beside it (a warm editor
that imported a level is 13 GB, most of it in swap on this machine).

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
- **Seven grass types on the two forest maps, by region (F2).** On a level in
  `grass_look.VARIED_GRASS_LEVELS` the scatter plants the level's meadow (the patch on the
  200 m map, the clump on the 1 km) and six of the pack's low grasses
  (`undergrowth_meshes.LOW_GRASS_MESHES`, `lowGrass_01_02` … `07_03`: 22–93 cm tall, 456–1,416
  triangles), each spec `HISM_Grass_Low_<tag>` (the `HISM_Grass` prefix is what the import's
  sweeps match) drawn with its own dark instance, `/Game/Forest/Materials/MI_LowGrass_<tag>_Dark`
  (a child of the pack's `lowGrass_<tag>_Mat`, `GRASS_SCALARS` and a tint of its own).
  - **Where:** `grass_regions.RegionMix` gives each type a value-noise field (40 m regions,
    a 15 m octave so the edges wander) and weights a spot's draw by exp(20 × field − top):
    over the 1 km map one type holds over 70% of the ground on about half of it, none holds
    half on about a sixth (the mixed seams), and each leads on 13–16%. The same mix for all
    tiers, so a region's near layers are its far ones' type.
  - **Coverage:** the six are narrower than the 1.2 m patch at their heights, so on the patch
    level each spot of one is planted `patch_density` times (1.5–2, each its own place in the
    spot's cell; `GrassSpec.density_scale`), and the offline density check counts spots. On
    the 1 km map they are wider than the clump: one a spot.
  - The probe level keeps the one clump (`grass_specs_for` gives it `DEFAULT_GRASS_SPECS`).
- **Grass and bushes are one library mesh each, planted where its Fab pack put it**
  (`undergrowth_meshes.py`): `grass_02_09_mesh` (60 cm tall, 54 cm across, 2,152 triangles)
  and `SM_Bush_02` (1.95 m tall, 3.5 m across, 1,304 triangles).
  - Neither is Nanite. Each has four mesh LODs and a masked two-sided material, and a cell
    draws the mesh's own materials unless its spec names one (the default specs name none).
  - **The 200 m map's grass is the dark patch (G3); the 1 km map's is the dark clump
    (G2); the probe level's is the pack's clump.** `grass_look.py` holds it in two lists. A
    level in `DARK_GRASS_LEVELS` draws its clumps with
    `/Game/Forest/Materials/MI_Grass_02_09_Dark`, our instance of the pack's
    `grass_02_09_Mat`. A level in `PATCH_GRASS_LEVELS` plants the patch,
    `/Game/Forest/Undergrowth/SM_Grass_Patch` (`HISM_Grass_Patch`), in place of the clump,
    at the same count, places, height and 0.85–1.20× width, drawn with
    `MI_Grass_Patch_Dark` (a child of the dark instance).
    - **The patch** (`grass_patch.py`, built by `uepy.py Scripts/build_grass_patch.py`,
      committed): seven copies of the clump, unstretched, one in the middle and six round
      it 40 cm out with uneven turns, 1.1 × 1.2 m and 49 cm tall. Its LODs are the clump's
      own lower LODs (render data only: the pack's LOD1–3 are engine reductions): 7× LOD2
      (3,766 triangles), from 3 m 7× LOD3 (1,883), from 6 m 3× LOD3 1.6× wide (807), from
      10 m 1× LOD3 2.4× wide (269, the clump's last). Nearly every instance on screen is
      at its last LOD, so that one costs what a clump did; the switch distances are
      nominal (a HISM leaves a LOD at 1.78 × radius / screen size, `screen_sizes`).
      It is lower than the clump (60 cm) because the pack's LOD2 has lost the tallest
      blades; planting scales it to knee height as it did the clump.
    - **The patch has its own pivot textures, or it would bend about the wrong points.**
      The pack's wind is Pivot Painter 2: UV set 1 picks the blade's texel of
      `grass_02_09_PIV` (pivot in the mesh's space, parent index as the half float whose
      bits are index + 1024) and `_VEC` (axis × 0.5 + 0.5, length / 2048). The patch's
      `T_Grass_Patch_PIV`/`_VEC` hold one band of the clump's texels per placement, moved
      as that copy is, and each copy's UV set 1 points into its band. The images are
      written by `pivot_images.py` (no numpy in the editor) to
      `assets/generated/undergrowth` and imported with the pack's textures' settings.
      `verify_grass_patch` holds each blade's root as far from its pivot as the same
      blade of the clump (a reduced blade can sit 13 cm above its pivot, so a fixed
      tolerance fails); fed the clump's own pivots it fails 648 blades.
    - **The patch needs a re-import; the colour does not.** To give a level the patch, add
      its name to `PATCH_GRASS_LEVELS`, regenerate and re-import it. To colour one, add it to
      `DARK_GRASS_LEVELS`, regenerate its scripts (the clumps do not move: the 1 km map's
      sidecar came out byte for byte the same) and run `uepy.py Scripts/recolour_grass.py`
      (`forest_import/grass_recolour.py`): it sets the override the import would have set
      on each grass cell and saves the level, with nothing planted again and so no forage,
      garments, sky or sound beds to put back. It did the 1 km map's 400 cells in 3 s.
    - **The density is 4.4 clumps/m² over eight tiers (F1; 2.2 over four since G2, 1.1
      before),** `grass_placement.DEFAULT_DENSITY_PER_SQM`, split by `grass_cells.
      GRASS_TIERS`' shares (`tier_densities`: each tier its share of the shares the level
      plants). Tiers 0-3 are G2's to the clump (same density, seed and places, same fades);
      tiers 4-7 are each 0.55/m², fade out by 22, 18, 15 and 12 m at 100% (scaled by the
      menu's grass distance like the rest), and have `min_preset` 4, past every preset:
      only the menu's grass density row, now 1-8, draws them. So eight layers double four's
      clumps where the ground shows between them, and nothing changes for a shipped
      preset. A level held to fewer tiers is in `grass_look.HELD_TIER_COUNT` (the 1 km map,
      four: eight would add a million clumps); the generator plants `tiers_for(level)`. Only the 200 m map has it: the 1 km map is held at
      1.1 ("The two maps", above).
    - **What the pack's `MA_Grass` does with the instance's numbers:** base colour is
      `desaturate(variation(albedo × Brightness) × Tint.rgb, 1 − Saturation)`. **`Tint`'s
      alpha is wired to nothing** (the pack ships it 0; only the RGB output is linked).
      The subsurface colour is the albedo × `Subsurface Strengh` (the pack's spelling),
      **not tinted**: lower it and `Subsurface Saturation` too, or a backlit clump stays
      spring green. `ColorVariation` turns the hue per clump: on a dull olive the pack's
      0.02 shows as teal and maroon clumps, so it is 0.005.
    - **The ground is brought to the grass's hue, on every level.** `M_Forest_Ground_PBR`
      has no authoring script (the generator only assigns it), so
      `forest_import/grass_look.py` patches it in place: a `Desaturation` and a `Multiply`
      between the old base colour and the output, driven by the parameters
      `GroundSaturation` and `GroundTint`. It finds its own nodes on a second run. The
      material is shared: the 1 km, probe and title levels' ground is dark too.
    - **Auto exposure answers a darker ground by opening up.** At noon the frame is lifted
      until the ground reads tan again and, taken too far (grass brightness 0.20, ground
      tint 0.085), the sky and the leaves burn out. Judge the colours at night and against
      the trees, not by the noon ground alone.
    - The level verifier holds the instance to its parent, its numbers and its
      dependencies, the cells to the material their spec names, and the ground to its tint
      (`verify_grass_look`, thirteen checks: five for the six low grasses' instances). `probes/probe_grass_look.py` (windowed; its
      docstring has the command) measures the frame with the grass shown and hidden at
      Medium and High and takes the pictures: 2.8 ms at Medium and 0.7 ms at High, against
      2.5 and 1.0 for the narrow clumps, which is inside what two runs differ by. At G2's
      2.2/m² the same grass is 5.4 ms at Medium and 2.1 at High on the 200 m map (3.0 and
      1.1 at 1.1/m² the same day); the 1 km map's, recoloured, 5.7 and 0.9 (3.4 and 1.3
      before, its Medium then drawing 180 m of it, not 300). The patch (G3) is 7.0 ms at
      Medium and 2.4 at High (6.3 and 1.9 the same day for the wide clump), twice over:
      at the 7 ms line, reported and not tuned.
    - **How far it is drawn is the menu's row, and it is a thinning, not an edge.** A cell
      fades its instances out between the tier's cull start and end, which the tuner
      scales to the preset's `grass_distance` (`graphics_menu/gfx_tuner_foliage.py`); the
      cell's own max draw distance (`grass_cells.cell_max_draw_cm`) stands 130 m past it
      at Medium's 300 m and never cuts first, and the mesh's last LOD has no end.
      `probes/probe_medium_reach.py` (windowed; `--map` for the 1 km level) holds both
      numbers and pictures two cells from 255 m with their grass shown and hidden: at
      265–300 m about a tenth of the clumps are left, a pixel and a half each.
  - **They sway by their pack's wind, not `MPC_Wind`.** The graphics menu's wind strength and
    speed do not reach them; its world-position-offset switch still does.
  - **The packs are git-ignored but these two meshes are committed.** `.gitignore`
    re-includes exactly the packages each needs (41 files, 118 MB, of which the grass pack's
    8k atlas is 109 MB; F2's six low grasses added 19 of them, 1.4 MB, sharing the atlas). To plant another library mesh, add its record and its packages to
    `undergrowth_meshes.py` and its `gitignore_lines()` to `.gitignore`;
    `dev/tests/test_undergrowth_meshes.py` holds the two together, and the level verifier
    fails if a mesh references a package outside its list.
  - Nothing writes to a pack asset (the dark instance is a new asset in our folder).
    `forest_import/undergrowth_assets.py` only checks them:
    the import stops if one is missing, and the verifier re-measures height, LOD count and
    triangles, so a pack update that changes the mesh fails there.
  - **A grass clump is a third of the width of the generated patch it replaced,** so at the
    patches' count (about 1/m² with every tier drawn, the 1 km map's today) the ground is
    tufts with terrain between them, wherever the narrow clump is planted. Grass is scaled to the target height from the mesh's real bounds at plant time;
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
