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
