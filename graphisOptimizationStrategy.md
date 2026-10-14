# Graphics optimization strategy

Performance audit of Otherworld on a MacBook Pro (Apple M2 Pro, 16-core GPU, 16 GB), UE 5.8.3, measured 2026-10-01.

## Verdict

The trees are the problem, and by a wide margin: on the 1 km map at Medium they take about 26 ms of a 35 ms frame. The cause is their triangle density, not the masked leaves the code comments blame. Medium at 30–40 FPS is reachable today with one existing setting; High needs the tree assets fixed first.

Nothing in the project was changed by the audit. The numbers come from two throwaway benchmark probes run as a standalone `-game` in a 1280×720 window, standing in the densest tree cluster at noon.

## Where the reported numbers come from

The reported figures (30–40 FPS on Low, about 15 on Medium, less on High) match the 1 km map, not the 200 m one:

| Preset | 200 m map, 720p | 1 km map, 720p | 1 km map, Retina-equivalent pixels |
|---|---|---|---|
| Low | 93 fps | 38 fps | 23 fps |
| Medium | 65 fps | 29 fps | 16 fps |
| High | 17–23 fps | 4 fps | 3 fps |

- **Map size:** at Medium's 180 m tree draw distance, far more trees are in range on the 1 km map (1,700 trees, 108 within 35 m of the test spot) than on the 200 m one (68 trees in total).
- **Pixel count:** the presets' resolution is a percentage of the window, so 85% of a Retina-sized viewport is several times the pixels of a 720p window. That alone takes Medium from 29 to 16 fps.

## What the frame is spent on (1 km, Medium, 35 ms)

| Change | Frame time | FPS |
|---|---|---|
| Baseline | 35.0 ms | 29 |
| Trees hidden | 8.7 ms | 115 |
| Tree coarseness 2 (`r.Nanite.MaxPixelsPerEdge`) | 25.9 ms | 39 |
| Tree coarseness 4 | 18.9 ms | 53 |
| Shadows off | 33.3 ms | 30 |
| Leaf cut-outs off | 33.5 ms | 30 |
| Retina pixels | 64.7 ms | 15.5 |
| Retina pixels + coarseness 4 | 35.8 ms | 28 |

- **Hardware rasterization:** the GPU profile shows 20 ms in Nanite's `HW Rasterize (Triangles)` and about 0.01 ms in its software rasterizer. Nanite's compute rasterizer is doing essentially no work on this Mac, so every tiny triangle goes through the hardware path. Why was not established; `r.Nanite.ComputeRasterization` reads 1.
- **Things that cost almost nothing:** on the 200 m map, hiding all grass changed nothing, and fog, clouds, sky capture, SSAO and DFAO were within noise.
- **Leaf cut-outs:** turning the mask off saves at most 1.5 ms at Medium. The comments in `forest_generator/tree_cells.py` and `forest_import/trees.py` calling masked leaves the dominant cost do not match the measurement.

## The trees against industry expectations

| Mesh | Source triangles | Non-Nanite fallback | Planted scale |
|---|---|---|---|
| `fir_tree_01_a` | 4.18 M (5.4 M vertices) | 1,581 | 1.8–3.8× |
| `SM_tree_small_02` | 2.06 M | 2,301 | 2.5–4.2× |
| `SM_island_tree_01` | 1.60 M | 4,249 | 2.0–3.6× |
| `SM_island_tree_02` | 1.07 M | 4,158 | 2.0–3.6× |
| `pine_sapling_small_a` | 143 k | 3,405 | 3.0–5.5× |

For comparison, from general knowledge rather than anything measured here:

- **Classic game tree:** roughly 10–40 k triangles at LOD0, three to five LODs, and a billboard or impostor past about 100 m.
- **Nanite-authored game tree:** a few hundred thousand triangles, with leaves modelled as opaque geometry.

Against that, these trees fall short in four ways:

- **Density:** they are 50–200× a classic LOD0 and several times a Nanite game tree. They look like offline or archviz scans rather than game assets.
- **No LOD chain:** each has one LOD, and per the project's notes the auto fallback has zero leaf triangles, so there is no cheap far representation.
- **Masked cards on Nanite:** the leaf material is masked, two-sided, with subsurface, which is the combination Nanite handles worst.
- **Upscaling:** planting at 2–5.5× enlarges every triangle on screen, so Nanite keeps finer clusters for longer.

The one thing in their favour is that no material uses world position offset, so there is no wind cost.

## Highest-leverage changes, in order

1. **Raise tree coarseness to 2 on Low and Medium.** It is already a column in `Scripts/graphics_menu/graphics_tuning.csv` (`tree_coarseness`), set to 1 on every preset. This alone takes 1 km Medium from 29 to 39 fps at 720p. Check the canopy by eye; 4 gives 53 fps but will be visibly coarser.
2. **Cap the internal resolution.** Make the resolution row mean a fixed pixel budget rather than a percentage of whatever the window is. At Retina size, Medium needs both this and coarseness to hold 30 fps.
3. **Replace or rebuild the tree assets.** This is the real fix and the only route to High. Either:
   - trim the Nanite data on the existing scans (keep-triangle percent or trim error) to a few hundred thousand triangles each, a one-off rebuild; or
   - swap in game-ready trees with real LODs and impostors, which would have to be acquired by the user via Fab.

   With trees at a fraction of today's cost, Medium has room for 60 fps, since everything else fits in under 9 ms.
4. **Redefine High.** It jumps from engine quality 1 straight to 3 (Epic). On the 200 m map that adds a 4096×2048 shadow atlas re-rasterizing the trees (shadows off saves 14 ms of 43) and Epic Lumen (off saves 11.5 ms; one level down saves 8). After the tree fix, High at engine level 2 with two cascades is plausible at 30 fps; today it is not.
5. **Leave grass, fog, clouds, sky capture and AO alone.** They are not where the time goes.

One thing to verify before trusting Lumen at High: the tree meshes have distance fields disabled, and the project turns off Lumen's mesh SDF and screen traces. Lumen may therefore be paying for lighting that barely sees the trees. This was not tested.

## Supporting measurements: 200 m map

Forest spot, noon, 1280×720 window.

Medium, one change at a time (the first five against a 15.3 ms baseline, the rest against 19.3 ms; see limits below):

| Change | Frame time |
|---|---|
| Baseline | 15.3 ms |
| Trees hidden | 8.3 ms (120 fps cap) |
| Grass hidden | 15.4 ms |
| Leaf cut-outs off | 15.9 ms |
| Shadows off | 14.9 ms |
| Baseline with two cascades | 19.3 ms |
| Screen 60% | 17.4 ms |
| Screen 100% | 20.6 ms |
| TSR at 60% | 18.9 ms |
| Tree coarseness 2 | 14.1 ms |
| Tree coarseness 4 | 11.0 ms |
| Sky capture, fog, clouds, DFAO, SSAO off (each) | 19.2–19.3 ms |
| GI and reflection method 0 | 17.6 ms |

High, one change at a time (43.5 ms baseline):

| Change | Frame time |
|---|---|
| Trees hidden | 19.6 ms |
| Shadows off | 29.2 ms |
| Lumen GI and reflections off | 32.0 ms |
| Lumen at engine level 2 | 35.6 ms |
| Screen 67% | 35.4 ms |
| TSR at 67% | 39.1 ms |
| Leaf cut-outs off | 39.6 ms |
| Volumetric fog off | 41.2 ms |
| Sky capture or clouds off | 43.0–43.2 ms |

GPU profile at High: 9.1 ms Nanite visibility buffer (8.1 ms hardware raster), 12.7 ms shadow depths (10.7 ms hardware raster of Nanite shadows into a 4096×2048 atlas).

## Limits of the measurement

- One camera position per map, 2.2 s per sample, noon lighting; the 200 m toggles were also run only at noon.
- The 200 m Low figures at the spawn point hit the 120 fps display cap, so they are lower bounds.
- On the 200 m run, a shadow revert left Medium with two cascades instead of one (about +4 ms), so later toggles there compare against a 19.3 ms baseline. The 1 km run is clean.
- The benchmark probes are now `Scripts/probes/probe_perf_audit.py` and `probe_perf_audit_1km.py`; results go to `Saved/uepy/bench/`.

## Step 1 result: the lighter fir (2026-10-01)

The fir was the heaviest mesh and a third of the forest. The level now plants `SM_Fir_C` (505 k triangles, a re-pivoted copy of `fir_tree_01_c`) at 1.1–1.7× instead of `fir_tree_01_a` (4.18 M) at 1.8–3.8×. Same spot, same scatter, 1 km map, 720p:

| Preset | Before | After |
|---|---|---|
| Low | 26.6 ms (38 fps) | 17.9 ms (56 fps) |
| Medium | 34.9 ms (29 fps) | 24.3 ms (41 fps) |
| Medium, Retina-equivalent pixels | 59.4 ms (17 fps) | 43.4 ms (23 fps) |
| High | 252 ms (4 fps) | 80 ms (12.5 fps) |
| Medium, trees hidden | 8.4 ms | 8.4 ms |

Trees at Medium went from about 26 ms to about 16 ms. The four other species are unchanged, and are what steps 2 and 3 address. The scans under `/Game/Forest/Scanned` are untouched; the levels as they were are in `assets/backup/2026-10-01_before_tree_optimization/`.

## Steps 2 and 3 result: every tree a cut-down copy (2026-10-01)

All five species are now planted from copies under `/Game/Forest/Trees`, built by `Scripts/forest_import/tree_assets.py` from the recipes in `Scripts/forest_generator/tree_meshes.py`. The scans are untouched.

| Mesh | Scan | Planted copy |
|---|---|---|
| Fir (`SM_Fir_C`) | 4.18 M (`fir_tree_01_a`) | 197 k |
| Deciduous (`SM_TreeSmall_02`) | 2.06 M | 240 k |
| Island tree 1 (`SM_IslandTree_01`) | 1.60 M | 195 k |
| Island tree 2 (`SM_IslandTree_02`) | 1.07 M | 135 k |
| Pine sapling (`SM_PineSapling_A`) | 143 k | 33 k |

Same spot, 1 km map, 720p:

| Preset | Audit | Step 1 | Steps 2 and 3 |
|---|---|---|---|
| Low | 26.6 ms (38 fps) | 17.9 ms (56 fps) | 12.0 ms (83 fps) |
| Medium | 34.9 ms (29 fps) | 24.3 ms (41 fps) | 17.4 ms (57 fps) |
| Medium, Retina-equivalent pixels | 59.4 ms (17 fps) | 43.4 ms (23 fps) | about 35 ms (28 fps) |
| High | 252 ms (4 fps) | 80 ms (12.5 fps) | 56 ms (18 fps) |

The last column was measured with the editor open, which adds a millisecond or two of noise; Low and Medium repeated within 0.5 ms over three runs.

What the measurements changed about the plan:

- **Nanite's own trim (step 2 as written) was not worth using.** Keep-triangles at 19% with Preserve Area was within noise of the untouched scan. Preserve Area alone costs about 2 ms.
- **Triangles per leaf barely matter.** Simplifying every leaf from 24 triangles to 4, keeping all of them, cut the source mesh five-fold and the trees' frame time by 15%: Nanite was already drawing distant leaves coarsely.
- **Leaf count is what costs.** Dropping half the leaves and growing the rest 1.4x, with Preserve Area off, took the trees from 16 ms to about 9 ms and reads the same at walking distance. A quarter of the leaves at twice the size is about 1.5 ms cheaper again and reads coarse up close.
- **The compute rasteriser cannot be switched on.** `r.Nanite.MinPixelsPerEdgeHW` and `r.Nanite.ComputeRasterization` change nothing on this Mac.

Trees are now about 9 ms of a 17.4 ms Medium frame; the 8 ms target is not met by the assets alone. What is left, measured on the new trees at Medium:

| Change | Saves |
|---|---|
| Tree coarseness 2 (1.5) | about 4.5 ms (3.5 ms) |
| Tree draw distance 180 m to 120 m | about 2.8 ms |
| Shadows off | about 2.5 ms |
| Non-Nanite fallback instead of Nanite | 2 to 5 ms, with a visibly thinner crown; a proper LOD chain would be needed |

Not done: a hand-built LOD chain and impostors. The fallback measurement says a classic path would beat Nanite on this hardware, so that is the next thing to build if Medium needs more.

## The tall fir put back (2026-10-01)

The small fir of step 1 read as thin poles, so the fir is `fir_tree_01_a` again, at its old 1.8–3.8× size, as a cut-down copy (`SM_Fir_A`): 6% of its 812 thousand needle cards, grown 3× to half the crown's old area, 205 k triangles in place of 4.18 M. The other four species are as in the table above. Same spot, 1 km map, 720p, no editor open:

| Preset | Audit | Small fir | Tall fir (current) |
|---|---|---|---|
| Low | 26.6 ms (38 fps) | 12.0 ms (83 fps) | 11.0 ms (91 fps) |
| Medium | 34.9 ms (29 fps) | 17.4 ms (57 fps) | 21.3 ms (47 fps) |
| Medium, Retina-equivalent pixels | 59.4 ms (17 fps) | about 35 ms (28 fps) | 39.5 ms (25 fps) |
| High | 252 ms (4 fps) | 56 ms (18 fps) | 95 ms (10.5 fps) |

The tall fir costs about 4 ms at Medium over the small one, and cutting it further does not get that back: at 2.5% of the cards and 30% of the area it was still 3 ms over. A tree that size fills the screen. On these trees tree coarseness 2 saves about 2 ms at Medium and coarseness 4 about 6 ms (60 fps).

## LOD chain and impostors on the 1 km map (2026-10-12)

The "next thing to build" above is built. `Scripts/build_game_ready_mesh.py trees` (`Scripts/mesh_lod/`) cuts each of the five trees into a second build under `/Game/Forest/TreesLOD`: no Nanite, three mesh LODs (about 40 k, 16 k and 6 k triangles, starting at 0, 30 and 60 m) and from 110 m an impostor of three crossed cards. `Lvl_Forest_1000m` now plants that build (`forest_generator/tree_lods.py`); the 200 m and probe levels stay on Nanite. Cells and cull distances are unchanged.

Same spot as before (the densest cluster, noon, 720p, no editor open), one probe run on the level as committed and on the level re-imported:

| Preset | Nanite trees | LOD trees |
|---|---|---|
| Low | 16.7 ms (60 fps) | 15.9 ms (63 fps) |
| Medium | 22.4 ms (45 fps) | 21.0 ms (48 fps) |
| Medium, trees hidden | 12.8 ms | 12.0 ms |
| High | 99.7 ms (10 fps) | 46.3 ms (22 fps) |

These two columns compare with each other, not with the tables above: the game has changed since 1 October (Low was 11.0 ms then).

What the measurements say:

- **High halves.** It draws the full 300 m, and that is where the impostors and the low LODs do their work.
- **Low and Medium are within noise.** The trees-hidden row differs by 0.8 ms between the two runs, which is most of the gap; at the spawn clearing Medium showed no difference. The 2 to 5 ms the fallback measurement promised did not appear at Medium.
- **Trees are still about 9 ms of a 21 ms Medium frame** on either build.

What it costs in looks:

- **Close up the trees are coarser than the Nanite ones:** fewer, larger, brighter leaves and a thinner crown. LOD0 is 40 k triangles against the Nanite tree's 33–240 k.
- **Firs at middle distance (LOD1 and LOD2) show bare boughs** sticking out of the needles.
- **The impostors at long range read well.** `SM_IslandTree_02`'s shows several trunks, because its trunk leans off the pivot.

Pictures of both builds from five viewpoints: `assets/generated/mesh_lod/level_compare/` (`nanite_*.png`, `lod_*.png`; git-ignored).

Not measured: night, Retina-equivalent pixels, the distance each LOD actually switches at, and chopping a tree in the new level.

Open choice: the close-range look is not paid for at Low and Medium. Building LOD0 from the full source (`--set lod0_triangles=250000`, then a re-import) should bring trees within 30 m close to the Nanite ones; whether the High gain survives that depends on how much of it comes from the distant trees, which is not yet measured. The other option is to take the level back to Nanite (remove it from `TREE_LOD_LEVELS` and re-import) and keep the LOD build for a High-only or lower-end path.

`probe_perf_audit_1km.py` no longer runs to the end: it waits for the Low preset at start, and the game starts on the saved preset. These numbers came from a scratch probe that sets each preset itself.

## Library grass and bushes (2026-10-12)

The grass and the bushes are no longer the generated opaque Nanite meshes. Both forest levels now plant one mesh each out of a Fab pack, with the pack's material (`forest_generator/undergrowth_meshes.py`): `grass_02_09_mesh` from the optimized Grass Library and `SM_Bush_02` from Light Foliage. Neither is Nanite; each has four mesh LODs and a masked material. Counts, cells, tiers and cull distances are unchanged.

Same spot and probe as the tree table above (densest cluster, noon, 720p), on the 1 km map with the LOD trees:

| Preset | Generated grass and bushes | Library grass and bushes |
|---|---|---|
| Low | 15.9 ms (63 fps) | 14.6–15.0 ms (67–69 fps) |
| Medium | 21.0 ms (48 fps) | 20.5–21.9 ms (46–49 fps) |
| High | 46.3 ms (22 fps) | 44.9–46.4 ms (22 fps) |

The left column is the earlier run, so the two are an hour and a re-import apart; the differences are within what two runs of one build differ by. At Medium, hiding the new grass saved 3.4 ms in one run and 5.5 ms in another; hiding the bushes saved nothing measurable; hiding the trees still saves about 9 ms.

What changed is the look, not the frame time:

- **The grass is tufts, not a field.** A clump is 54 cm across where a generated patch was 1.1 m, so at the same one clump per square metre about a sixth of the ground is covered at Ultra and less below. Covering the ground as before would take about seven times the instances (7 million on the 1 km map), which the map file and the frame cannot carry; widening each clump, or a wider mesh from the same pack, is the cheaper way.
- **The bushes are larger and read as shrubs:** 1.5–2.1 m tall and up to 3.8 m across, against 1.2–1.65 m before.
- **The wind is the packs' own.** The menu's wind strength and speed no longer move the grass and bushes.
- **The grass pack's atlas is three 8k textures (109 MB on disk)** for the one clump the levels use.

Pictures at each preset: `assets/generated/undergrowth/` (git-ignored). Not measured: night, Retina-equivalent pixels, texture memory.

### Dark, wide grass on the 200 m map (G1, 2026-10-13)

The widening named above is done, on `Lvl_Forest_200m` only (`forest_generator/grass_look.py`). The same 40,521 clumps stand in the same places at the same height, each 1.55–2.10× wide in place of 0.85–1.20×: the clumps' summed footprint goes from 17% of the ground to 55%, about 16% to 42% once overlap is allowed for. They draw with `MI_Grass_02_09_Dark`, our instance of the pack's material, and the shared ground material is tinted to the same olive. Instances, triangles, tiers, cull distances and the bushes are unchanged.

`probes/probe_grass_look.py`, windowed at 1280×720, the perf audit's spot (the densest tree cluster) at noon, the grass cells alone hidden and shown, each state twice:

| Preset | | Grass shown | Grass hidden | Grass costs |
|---|---|---|---|---|
| Medium | before | 15.88, 15.79 ms | 13.38, 13.26 ms | 2.5 ms |
| Medium | after | 14.02, 13.97 ms | 11.20, 11.17 ms | 2.8 ms |
| High | before | 43.34, 43.13 ms | 42.21, 42.30 ms | 1.0 ms |
| High | after | 41.91, 41.99 ms | 40.87, 41.60 ms | 0.7 ms |

- **3.2× the masked area per clump cost nothing that can be measured:** +0.3 ms at Medium and −0.3 ms at High, where two runs of one state differ by up to 0.7 ms. Well under the 7 ms that would have stopped the change.
- **The whole frame is about 2 ms shorter after, with the grass hidden too.** That is not the grass. The two runs are a re-import and an hour apart, and the ground is darker; which of them it is was not found.
- **This profile draws all four grass tiers at Medium (16 cells in range) and three at High (12),** before and after. Not looked into here.
- **Auto exposure undoes a dark albedo at noon.** With grass and ground both dark it opens up until the ground reads tan again; with the grass at brightness 0.20 and the ground tint at 0.085 the sky and the leaves burnt out, so the values stop at 0.24 and 0.11. At night the same values read dark. A darker noon is the exposure's or the sun's to give, not the albedo's.
- **The pack's `Tint` alpha does nothing** (linked to no input of `MA_Grass`), its subsurface colour is not tinted and needs its own two parameters lowered, and its `ColorVariation` at the shipped 0.02 shows as teal and maroon clumps on a dull olive (0.005 now).
- **Blades do not read as oversized at 1.8×:** a clump reads as a wider tussock, so the width was not brought down.

Pictures (git-ignored, `assets/generated/undergrowth/`): `g1_<Low|Medium|High>_<noon|night>_<across|down>.png`, and the same twelve from before as `g1_before_…`. Not done: the 1 km map (its grass is the pack's until the pictures are seen; its ground is already the dark one), Retina-equivalent pixels, Low's frame time.

### Medium at level 2, grass to 300 m, twice the grass, the 1 km map's colour (G2, 2026-10-13)

Four changes, measured apart. Medium's ten engine quality groups go from level 1 to 2 with that level's shadow maps (2048 for the sun and moon, 1024 for other lights, 4 cascades). Medium draws the grass to 300 m and the trees to 400 m (180 m and 180 m before). The grass density default goes from 1.1 to 2.2 clumps/m² with the tier shares unchanged, so every grass layer setting draws twice the clumps; only `Lvl_Forest_200m` is regenerated at it (81,697 clumps where 40,521 were, its `.umap` 14.4 MB where 7.4 was). `Lvl_Forest_1000m` keeps its 1,025,988 clumps, their places and their narrow width (`grass_look.HELD_DENSITY_PER_SQM`) and gains the dark material alone, set on its 400 grass cells in place (`Scripts/recolour_grass.py`), with no re-import.

`probes/probe_medium_reach.py` (new; windowed at 1280×720, the perf audit's spot, noon) nudges Medium's live rows from the old ones to the new and measures each state twice, so the shares can be told apart in one run:

| Medium's rows | 200 m map, before | 200 m map, after (2.2/m²) | 1 km map, before | 1 km map, after (recoloured) |
|---|---|---|---|---|
| groups 1, grass 180 m, trees 180 m | 13.85, 13.77 ms | 16.43, 16.42 ms | 22.00, 21.82 ms | 22.16, 21.95 ms |
| groups 2 and their shadow maps | 28.26, 28.22 ms | 32.84, 30.63 ms | 35.52, 35.60 ms | 36.22, 36.10 ms |
| and grass 300 m, trees 400 m | 28.06, 29.08 ms | 32.36, 32.48 ms | 37.54, 37.55 ms | 38.10, 38.00 ms |

- **Level 2 is the cost: +14.4 ms on the 200 m map and +13.7 ms on the 1 km map,** about doubling Medium's frame. Which of the ten groups carries it was not measured (`probe_gfx_groups.py` can move them one at a time).
- **The longer draw distances cost +2.0 ms on the 1 km map and nothing measurable on the 200 m map,** which is 283 m corner to corner, so little stands past the old 180 m.
- **Twice the grass costs +2.6 ms at the old rows and about +3 ms at the new ones** on the 200 m map.
- **Medium is over 33 ms on the 1 km map: 38.1 ms (26 fps), where it was 21.9 ms (46 fps).** On the 200 m map it is 32.4 ms, just under. It is reported here and not tuned back; the cheapest lever by these numbers is the level, not the distances or the grass.

`probes/probe_grass_look.py`, the grass cells alone hidden and shown, each state twice, before and after on the same day:

| Map | Preset | | Grass shown | Grass hidden | Grass costs |
|---|---|---|---|---|---|
| 200 m | Medium | before | 14.13, 13.83 ms | 11.06, 11.01 ms | 3.0 ms |
| 200 m | Medium | after | 32.71, 31.56 ms | 27.99, 25.41 ms | 5.4 ms |
| 200 m | High | before | 41.57, 41.56 ms | 40.42, 40.43 ms | 1.1 ms |
| 200 m | High | after | 42.21, 42.75 ms | 40.33, 40.40 ms | 2.1 ms |
| 1 km | Medium | before | 22.10, 22.03 ms | 18.70, 18.60 ms | 3.4 ms |
| 1 km | Medium | after | 38.43, 38.12 ms | 32.50, 32.61 ms | 5.7 ms |
| 1 km | High | before | 46.79, 47.24 ms | 45.71, 45.77 ms | 1.3 ms |
| 1 km | High | after | 46.83, 46.86 ms | 45.80, 46.16 ms | 0.9 ms |

- **High did not move on the 1 km map** (its rows and that map's clumps are the same; only the material changed) and gained 1 ms on the 200 m map, the doubled grass.
- **The 1 km map's grass costs more at Medium after (5.7 ms against 3.4) with the same clumps:** Medium now draws 300 m of it where it drew 180 m, under level 2's shadows.
- **The distances are real.** At Medium the grass's base layer fades out at 300.0 m and the trees at 400.1 m, and the cells' own max draw distance stands at 432.5 m and 558.8 m, so neither it nor a mesh LOD cuts shorter than the row. Pictured from 255 m (grass) and 350 m (trees) with only two cells shown, then hidden: the grass at 265–300 m differs over 501 pixels of the 1 km map's frame (6 between two frames of one state) and 2,954 on the 200 m map; the trees at 360–400 m over 10,281 and 4,057. From past the cells' own distance nothing differs. The fade is a thinning, so at 265–300 m about a tenth of the clumps are left, each a pixel and a half: it reads as a tone on the ground, not as blades.
- **The three game runs straight after the re-import measured 100–200 ms a frame and one stalled:** the game was rebuilding what the import had invalidated, with a 13 GB editor in swap beside it. The numbers above are from the runs after.
- **Doubling the 1 km map too would be about 2.05 million clumps and a `.umap` of about 360 MB** (170 bytes a clump, measured on the 200 m map; today's is 185 MB), and by the 200 m map's numbers some 3 ms more at Medium. Not done here.

Pictures (git-ignored, `assets/generated/undergrowth/`): the twelve of the 200 m map as `g2_<Low|Medium|High>_<noon|night>_<across|down>.png`, the same twelve of the 1 km map as `g2_1km_…` (`g2_1km_Medium_noon_across.png` and `g2_1km_Medium_night_across.png` are the two looking across its ground), and the reach pictures as `g2_reach_<level>_<grass|tree>_<near|far>_<shown|hidden>.png`. Not measured: night frame times, which group of level 2 costs what, a packaged build.
