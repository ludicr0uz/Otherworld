# Otherworld — System Design

Detailed reference for the Otherworld Unreal Engine 5.8 project. `CLAUDE.md` is the
token-cheap summary; read this file only when you need the details.

---

## 1. Project shape

```
Otherworld/
├── Otherworld.uproject        # UE 5.8; plugins below
├── CLAUDE.md / GEMINI.md      # agent rules (GEMINI.md = original, for Antigravity)
├── systemDesign.md            # this file
├── Config/                    # *.ini
├── Content/                   # game assets (binary)
├── Scripts/                   # external automation, run via UnrealEditor-Cmd
└── Saved/ Intermediate/ DerivedDataCache/   # gitignored
```

Enabled plugins: `ModelingToolsEditorMode` (editor-only), `GameplayStateTree`,
`PythonScriptPlugin`, `EditorScriptingUtilities`, `ProceduralMeshComponent`,
`PCG`, `PCGGeometryScriptInterop`.

No C++ source module exists — the project is Blueprint + Python only. It started from the
Third Person template (`Content/ThirdPerson`, `Content/Characters/Mannequins`,
`Content/Input`, `Content/LevelPrototyping` are template leftovers and largely untouched).

### Content layout that matters

| Path | Contents |
|---|---|
| `Content/Maps/` | `Lvl_Forest_200m.umap` (generator output), `Lvl_Forest.umap` (older hand/template level) |
| `Content/Forest/Materials/` | 16 master materials incl. `M_Forest_Ground_PBR`, `M_Master_Foliage`, `M_Master_Bark`, `M_NightSky_Starfield` |
| `Content/Forest/Materials/Instances/` | 54 MIs — per-mesh tree/foliage instances + `MI_NightSky_Starfield` |
| `Content/Forest/Scanned/` | ~18 downloaded photoscan kits (`*_1k/{StaticMeshes,Materials,Textures}`) — fir, island trees, ferns, grass, moss, shrubs, rocks, stumps |
| `Content/Forest/Meshes/` | 10 early procedurally-built meshes (`SM_PineTree_01`, …), superseded by the scanned kits |
| `Content/Forest/Test/` | import target for the generated terrain mesh |
| `Content/Python/` | `init_unreal.py` (startup banner), `generate_forest_level.py` (older template-based level builder — **not** the current generator) |
| `Content/ThirdPerson/Lvl_ThirdPerson.umap` | template level; uses One File Per Actor, hence the large `__ExternalActors__` tree |

---

## 2. Automation model

Two execution contexts, and they must not be confused:

**A. Pure Python (host interpreter).** `Scripts/generate_forest_level.py` and the
`Scripts/forest_generator/` package. No `unreal` import, so it runs instantly, is unit-testable,
and does all math/verification offline.

**B. Unreal Python (in-editor interpreter).** Everything that touches assets. Either a
hand-written script in `Scripts/`, or a **generated** script under
`Scripts/generated_levels/<Level>/`. Invoked headless:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" \
  "<abs>/Otherworld.uproject" -ExecutePythonScript="<abs>/script.py" -NoUI -stdout
```

Subsystems used throughout: `EditorAssetSubsystem`, `EditorActorSubsystem`,
`LevelEditorSubsystem`, `AssetToolsHelpers.get_asset_tools()`, `MaterialEditingLibrary` (`mel`).

Because the shell resets cwd between tool calls, **always pass absolute paths** to
UnrealEditor-Cmd; a relative `.uproject` fails with
`LogProjectManager: Error: Failed to open descriptor file`.

`Scripts/` additionally contains ~110 historical one-off scripts (`inspect_*`, `fix_*`,
`build_*`, `download_*`, `verify_*`, `test_*`) plus their captured `*_out.txt` logs. They
document how the forest assets were built and are useful as API examples, but they are not a
maintained interface.

---

## 3. Level generator pipeline

Entry point: `Scripts/generate_forest_level.py` (~890 lines, half of which are the two
embedded script templates).

```
CLI ──► terrain.generate_terrain_obj ──► tree_placement.scatter_trees
     ──► verification.run_all_checks (12 offline checks; exits 1 on failure)
     ──► verification_report.json
     ──► emit import_<Level>.py   (build the level in-editor)
     ──► emit verify_<Level>.py   (47 in-editor assertions)
     ──► print the two UnrealEditor-Cmd commands
```

CLI flags: `--size <meters>` (required), `--name` (default `Lvl_Forest_<size>m`),
`--seed` (42), `--grid` (default auto), `--time-of-day {day,night}` (default `day`),
`--json-report`.

Output dir: `Scripts/generated_levels/<LevelName>/` holding
`SM_<Level>_Terrain.obj`, `import_<Level>.py`, `verify_<Level>.py`, `verification_report.json`.
Re-running with the same seed reproduces byte-identical output.

### 3.1 Terrain — `forest_generator/terrain.py`

`make_elevation_fn(world_size_cm)` returns a closure. All thresholds are scaled from a
reference 400 m map (`s = world_size_cm / 40000`), so a 200 m map is a proportional slice:

- flat spawn disk, radius `4500·s` cm → `z = 0` exactly
- beyond it, `sin(x/P)·cos(y/P)·A` hills with `P = 3200·s`, `A = 380·s`
- perimeter ramp: `((dist − 8000·s)/9500·s)² · 1750·s` added past the onset radius

`grid_size_for_world` targets ~5–6 m quads (`world_cm/600`, clamped 16…128); a 200 m map gives
a 34×34 grid → 2312 verts / 4620 tris. `generate_terrain_obj` writes a Wavefront OBJ with
per-vertex normals; `get_exact_mesh_z(x, y, …)` reproduces the **same barycentric interpolation
on the same triangulation** the mesh uses, which is what lets trees sit exactly on the surface
rather than on the analytic height field.

### 3.2 Tree placement — `forest_generator/tree_placement.py`

`DEFAULT_TREE_SPECS` — 5 `TreeSpec` entries, each naming a scanned mesh, its ordered material
slots, density, scale range and root-sink:

| Spec | Mesh kit | /hectare | Scale |
|---|---|---|---|
| `HISM_Tree_Leafy_Island_01` | `island_tree_01` | 7.0 | 2.0–3.6 |
| `HISM_Tree_Leafy_Island_02` | `island_tree_02` | 7.0 | 2.0–3.6 |
| `HISM_Tree_Fir_A` | `fir_tree_01` (LOD0) | 11.0 | 1.8–3.8 |
| `HISM_Tree_Pine_A` | `pine_sapling_small` | 5.0 | 3.0–5.5 |
| `HISM_Tree_Deciduous` | `tree_small_02` | 4.0 | 2.5–4.2 |

`scatter_trees(seed=42)` uses `random.Random(seed)`: count = density × area in hectares;
each tree gets a polar position between `min_dist_from_center` and 85 % of the half-extent
(then clamped to 95 %), a random yaw, a random uniform scale, and
`sink_cm = sink_base_cm · scale / sink_ref_scale` subtracted from the exact mesh Z so roots
bury instead of hovering. Returns `PlacedTree` records (both `terrain_z` and `placed_z` are
kept so verification can check hover *and* burial independently). 200 m ⇒ 136 trees.

### 3.3 Offline verification — `forest_generator/verification.py`

`run_all_checks` → `VerificationReport` (`CheckResult` list, `summary`, `all_passed`,
`to_json`). The 12 checks: OBJ validity, terrain bounds ±5 %, flat spawn zone, upward normals,
tree count sanity, in-bounds, not floating, not buried, vertical, spacing, spawn-zone clear,
barycentric consistency. A failure aborts before any editor work happens.

### 3.4 Generated import script

`_write_unreal_import_script` emits, in order:

1. **Import OBJ** → `/Game/Forest/Test/SM_<Level>_Terrain` (`AssetImportTask`, replace+save);
   Nanite disabled, `collision_trace_flag = CTF_USE_COMPLEX_AS_SIMPLE`, `allow_cpu_access`,
   material `M_Forest_Ground_PBR`.
2. **Level** `/Game/Maps/<Level>` — load if it exists and destroy every actor whose label
   starts with the level name or `HISM_Tree` (idempotent re-generation), else `new_level`.
3. **Terrain actor** — `StaticMeshActor`, `BlockAll`, `QUERY_AND_PHYSICS`, static.
4. **Lighting & sky** — fully driven by the embedded preset (§4).
5. **Trees** — placements inlined as a `TREE_DATA` literal, grouped by spec; one actor per
   species carrying a `HierarchicalInstancedStaticMeshComponent` as its root, `BlockAll`,
   static, shadow-casting, materials set by slot index, then one `add_instance` per tree.
6. **PlayerStart** at `(0, 0, 100)`.
7. `save_current_level()`.

All spawned actors are labelled `<LevelName>_<Role>` (`_Terrain`, `_Sun`/`_Moon`,
`_SkyAtmosphere`, `_SkySphere`, `_SkyLight`, `_Fog`, `_PostProcess`, `_PlayerStart`) —
that convention is what makes step 2's cleanup and the verify script's lookups work.

### 3.5 Generated verify script

`_write_unreal_verify_script` emits a `check(name, condition, detail)` harness and 47
assertions over the *saved* level: terrain actor/component/collision/Nanite/material, the
full lighting rig against the preset (§4.3), tree HISM counts per species, and PlayerStart.
Prints `[VERIFY] ✅ ALL 47 CHECKS PASSED!` or a list of failures.

---

## 4. Time-of-day system

### 4.1 Data

`Scripts/forest_generator/lighting.py` holds `TIME_OF_DAY_PRESETS` as **plain dicts** (no
classes, no `unreal` types) precisely so they can be `json.dumps`'d into the generated script
and re-read there with `LIGHTING = json.loads(r"""…""")`. `get_preset(name)` raises
`ValueError` listing valid keys.

| Block | `day` | `night` |
|---|---|---|
| `sun.label_suffix` | `Sun` | `Moon` |
| `sun.intensity` (lux) | 6.0 | 0.12 |
| `sun.color` (sRGB) | 255,248,235 | 170,195,255 |
| `sun.pitch` / `yaw` | −50 / −30 | −32 / 120 |
| `sky_light.intensity` | 1.2 | 3.0 |
| `sky_light.real_time_capture` | True | True |
| `sky_dome.material` | `/Engine/EngineSky/M_SimpleSkyDome` | `M_NightSky_Starfield` |
| `sky_dome.build_starfield` | False | True (+ `star_brightness` 2.5, `night_sky_color` 0.004/0.008/0.022, `star_tiling` 2×1) |
| `volumetric_cloud.enabled` | True | False |
| `fog.density` | 0.02 | 0.035 |
| `fog.inscattering_color` | 0.45,0.55,0.65 | 0.015,0.025,0.055 |
| `fog.volumetric_extinction_scale` | 1.0 | 0.6 |
| `post_process` min/max/bias | 0.03 / 2.0 / 0.5 | 0.004 / 0.6 / 1.6 |

To add a preset (e.g. `dusk`), add a dict with the same keys — the CLI `choices` and the
generated scripts pick it up with no other edits.

### 4.2 How night is lit

The requirement was that the starry sky itself provides the (low) illumination:

- `ensure_starfield_material(cfg)` builds `/Game/Forest/Materials/M_NightSky_Starfield` if
  absent, via `MaterialEditingLibrary`:
  `TextureCoordinate(u/v tiling)` → `TextureSampleParameter2D "StarsTexture"`
  (`/Engine/EngineSky/T_Sky_Stars`) → `Multiply` by `ScalarParameter "StarBrightness"` →
  `Add` `VectorParameter "NightSkyColor"` → `MP_EMISSIVE_COLOR`, then `recompile_material`
  and save. The material is `MSM_UNLIT`, `two_sided`, and **`is_sky = True`**.
- `MI_NightSky_Starfield` is then created/re-parented and carries `StarBrightness` /
  `NightSkyColor` so they can be tweaked in-editor without regenerating.
- The `is_sky` tag does two things: exponential height fog leaves the dome alone, and the
  SkyLight's **Real Time Capture** treats the dome's emissive as sky lighting. So the
  starfield's own emission becomes the scene's ambient — that is the light source.
- A 0.12-lux bluish DirectionalLight (`atmosphere_sun_light = True`) sits low in the sky to
  give trees readable silhouettes and soft shadows; volumetric clouds are switched off so
  nothing occludes the stars; the auto-exposure floor drops to 0.004 with +1.6 bias so a dim
  scene stays legible without turning into fake daylight.

Engine sky-dome materials (`M_SimpleSkyDome`, `M_AdvancedSkyDome`) expose no star or texture
parameters — verified by introspection — which is why a project-owned material was necessary.

### 4.3 Preset-driven verification

The verify script re-reads the same `LIGHTING` dict, so checks follow the preset rather than
hardcoded values: directional light exists under the preset's label and matches intensity /
`atmosphere_sun_light` / shadow casting; VolumetricCloud presence matches
`volumetric_cloud.enabled`; SkyLight intensity + real-time capture; and for night, dome
material is the starfield MI, its base is unlit and `is_sky`, and `StarBrightness` matches
(read back with `get_material_instance_scalar_parameter_value`) — for day, the dome material
simply matches the preset path. Exposure min/max/bias are compared with a float tolerance.

---

## 5. Conventions & pitfalls

- **Template braces.** The generated scripts come from `textwrap.dedent(f'''…''')`, so every
  literal `{` `}` in emitted Python must be doubled. This is the single easiest way to break
  the generator.
- **Version-tolerant property writes.** `try_set(obj, prop, value)` logs a warning instead of
  raising; `try_set_first(obj, [names…], value)` takes the first property that exists. Needed
  because UE 5.4+ renamed `fog_inscattering_color` → `fog_inscattering_luminance`. A clean
  import log has **no** `(skipped …)` lines — treat one as a real signal.
- **Idempotency.** Base materials are only created when missing; material instances are always
  re-parented and re-parameterised; level actors are wiped by label prefix before respawn.
- **Terrain collision.** Nanite must be off and the trace flag set to
  `CTF_USE_COMPLEX_AS_SIMPLE`, otherwise the player falls through or lands on a coarse hull.
- **Determinism.** Same `--seed` ⇒ same terrain and same tree transforms. Change the seed, not
  the placement code, when you want a different forest.
- **Verify after importing.** The offline suite cannot see collision, materials or actors;
  the in-editor script is the real gate.

---

## 6. Status (as of 2026-09-24)

- Git: branch `night-mode`, working tree clean, head `e5745e9 night mode initial`
  (adds `lighting.py`, the generator rewrite, the regenerated night scripts and a `.gitignore`).
- `/Game/Maps/Lvl_Forest_200m` — 200 m, seed 42, 136 trees over 5 species, **night** preset.
  Offline 12/12, in-editor 47/47, import log clean.
- New engine assets from that run: `M_NightSky_Starfield`, `MI_NightSky_Starfield`.
- The `day` path was regression-checked with a throwaway 100 m level (12/12, both emitted
  scripts parse, day-only asset references present) and the throwaway removed.
- Not verified programmatically: how the night scene actually *looks*. Tune
  `star_brightness`, moon `intensity`, and `auto_exposure_bias` in `lighting.py` by eye.
