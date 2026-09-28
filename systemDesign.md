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
`Content/Input`, `Content/LevelPrototyping`), and "largely untouched" turns out to be
measurable: of those 171 files, **168 are byte-identical to the UE 5.8.3 install** and three
are patched in place by builders — `ABP_Unarmed`, `BP_ThirdPersonCharacter` and
`BP_ThirdPersonGameMode`.

That is why the repository is code only. Nothing under `Content/` is committed except
`Content/Python`: the stock files are restored by copying them out of the engine, and
everything else is written by a script in `Scripts/`. `Scripts/forest_generator/asset_sources.py`
is the table of which is which, `Scripts/sync_assets.py` is the tool that acts on it, and
`assets/` (git-ignored) holds downloads and generator scratch. Verified 2026-09-27 by
deleting the four stock directories and rebuilding: 356/356 weapons, 60/60 HUD, 148/148 level.

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
     ──► grass_placement.scatter_grass ──► npc_placement.place_npc
     ──► verification.run_all_checks (27 offline checks; exits 1 on failure)
     ──► verification_report.json
     ──► emit grass_<Level>.json  (instance transforms, read at import time)
     ──► emit import_<Level>.py   (build the level in-editor)
     ──► emit verify_<Level>.py   (141 in-editor assertions)
     ──► print the two UnrealEditor-Cmd commands
```

CLI flags: `--size <meters>` (required), `--name` (default `Lvl_Forest_<size>m`),
`--seed` (42), `--grid` (default auto), `--time-of-day {day,night}` (default `day`),
`--grass-density` (1.2 clumps/m²), `--grass-height` (50 cm), `--grass-patchiness` (0.25),
`--no-grass`, `--no-npc`, `--npc-min-distance <metres>`, `--json-report`.

Output dir: `Scripts/generated_levels/<LevelName>/` holding
`SM_<Level>_Terrain.obj`, `grass_<Level>.json`, `import_<Level>.py`, `verify_<Level>.py`,
`verification_report.json`. The grass sidecar is gitignored — it is ~3 MB for a 200 m map
and fully regenerable from the seed.
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

### 3.2b Grass placement — `forest_generator/grass_placement.py`

Knee-high grass across the whole map, deterministic from the same `--seed`
(XOR-decorrelated from the tree RNG so changing grass settings never moves a tree).

**Distribution.** A jittered stratified grid, cell edge = `sqrt(1/density)` metres, one
candidate per cell placed uniformly inside it. That guarantees coverage everywhere, which a
plain uniform-random scatter does not. A `patchiness` term then drops a cell and doubles a
cell at *equal* probability (0.25 each by default), so thin and thick patches appear while the
expected density stays exactly as requested. Candidates are rejected inside a 150 cm ring
around the PlayerStart and within 90 cm of a trunk (trees are bucketed into a hash grid, so
the rejection test is O(1) per clump). Coverage runs to 97 % of the half-extent.

**Height — the part that matters.** The source scans are photogrammetry with no authored
real-world size: measured from their bounds they are only **14.7–32.3 cm** tall. So the module
never bakes a scale. Each `PlacedGrass` carries a `target_height_cm` (what the clump should
measure in world space) plus independent height and width multipliers; the generated import
script divides that target by the mesh's *actual* `get_bounds().box_extent.z * 2` at plant
time. "Knee high" therefore stays true if an asset is ever re-exported at a different size.

**Layering.** `DEFAULT_GRASS_SPECS` is two layers, nine HISM actors:

| Layer | Species | `height_ratio` | Result at the 50 cm default |
|---|---|---|---|
| Knee | `Tall_A/B/C`, `Clump_C`, `Mid_A` | 0.92–1.00 | ~46–50 cm, ~77 % of clumps |
| Understory | `Under_Mid_B`, `Under_Large_A/B`, `Under_Clump_A` | 0.52–0.60 | shin height, breaks the silhouette |

The split is driven by the *measured* mesh heights recorded on each spec as
`nominal_mesh_height_cm`: the tallest scans carry the knee layer because reaching 50 cm from a
15 cm clump needs a 3.4× upscale and the blades read as coarse. As built, the worst upscale is
2.34× and the offline `Grass Upscale Factor` check fails the build past **2.4×**. Per-instance
jitter is height ×0.85–1.20 (tightened per species where the upscale budget is thin), width
×0.90–1.18, and a ±4° lean so the field does not look stamped.

200 m at the defaults ⇒ **44,368 clumps**, 1.11/m² realised against 1.20 requested (the
difference is the spawn ring, the trunk rings and the coverage inset).

### 3.2c NPC placement — `forest_generator/npc_placement.py`

One wandering NPC per level, spawned somewhere random and walking to the player.

**Spawn point.** Rejection sampling (up to 400 attempts) against four constraints: at least
55 % of the usable radius away from the PlayerStart so the walk is a real journey; at least
220 cm clear of any trunk; inside 88 % of the half-extent; and — preferred rather than
required — with at least one tree straddling the straight line to the player, so the detour
behaviour is actually exercised. Candidates are drawn uniformly *by area* over the annulus
(`sqrt` on the radius) so they do not bunch toward the centre. The first obstructed candidate
wins; if none is found in 400 tries the best legal candidate is used and the check reports the
clear line instead of failing. Seeded `seed ^ 0x4E7C`, so it is decorrelated from trees and
grass. Z is `terrain_z + 88 cm` (the stock Character capsule half-height) and yaw faces the
player.

Trunk radius is approximated as `15 cm × tree scale` — a proxy used only for spawn clearance
and the line-of-sight test, never for collision, which comes from the real mesh.

### 3.2d NPC Blueprints — `Scripts/build_npc_blueprints.py`

> Since 2026-09-28 the builder is a thin entry point over the `Scripts/npc/` package, and the
> controller patrols until a sense (hurt, sight, touch, sound) flips it to the chase below —
> see §3.2f for how patrol, the senses, noise and the agro ranges are implemented.

These two assets depend on nothing per-level, so they live in their own idempotent script
rather than the generated one; the import script imports it and calls
`ensure_npc_blueprints()`. UE 5.8 exposes genuine Blueprint graph authoring to Python
(`unreal.BlueprintGraphEditor`), so both are built and compiled from code.

`BP_ForestWandererAI` — parent `AIController`. Event graph:

```
[Event BeginPlay] --exec--> [Branch: IsValid(Get Controlled Pawn)?]
                                   |true                      |false
                                   v                          |
                     [Branch: both ends on the navmesh?]      |
                          |true              |false           |
                          v                  v                |
                    [MoveToActor]      [MoveToLocation,       |
                          |             no pathfinding]       |
                          '--------.---------'                |
                                   v                          |
                             [Delay 0.5s] <-------------------'
                                   |
                                   '--> back to the IsValid gate
[Get Player Pawn 0] --ReturnValue--> [MoveToActor.Goal]
                    --GetActorLocation--> [MoveToLocation.Dest]
```

The `IsValid` gate exists because a controller's `BeginPlay` fires before possession: on the
first pass `Get Controlled Pawn` is None, `MoveToActor` silently does nothing, and the melee
chain spliced in below reads `GetActorLocation` off None — which the VM logs as an
`Accessed None ... CallFunc_K2_GetPawn_ReturnValue` error, once per spawned NPC. It must gate
the *exec* flow rather than join the melee `AND`, because `BooleanAND` evaluates both pins and
so would pull the pure location chain regardless.

The second branch projects **both** ends of the chase onto the navmesh through
`K2_ProjectPointToNavigation` with a tight 200 × 200 × 400 cm query box
(`NAV_REACHABLE_EXTENT_CM`) and falls back to `MoveToLocation` with `bUsePathfinding=false` and
`bProjectDestinationToNavigation=false` when either misses. It exists because the navmesh and
the terrain are not the same shape to the centimetre — Recast will not build on the steepest
corner ramp — and it used to matter far more, when the volume covered only 0.85 of the map and
left a 15 m dead ring. §3.2e has that story. The fallback is a *move request*, not
`AddMovementInput`: it path-follows, so it survives between loop iterations, where an input
nudge would move the NPC one frame in thirty.

`MoveToActor` (`bUsePathfinding=true`, `AcceptanceRadius=150`) is what routes the NPC around
trees. Re-issuing it on a loop rather than once means it follows a moving player and
self-heals if the first request fires before the navmesh or the player pawn exists — which it
will, because the navmesh is built at game start. A `Delay` loop is used rather than a timer
because it needs no `self` reference and no delegate node.

Two API notes worth keeping: a freshly created Blueprint already carries a *disabled*
`ReceiveBeginPlay` node, so the graph is enabled by finding that node and connecting to it
(`find_event_node("ReceiveBeginPlay")`) rather than adding one; and display names do not
resolve — the member name is what the lookup takes.

`BP_ForestWanderer` — parent `Character`. Mannequin `SKM_Manny_Simple` + `ABP_Unarmed` so the
walk animates, mesh dropped 89 cm to the capsule's feet and yawed −90°, `max_walk_speed`
**600 cm/s** — the engine default, which is a run, and the top of `ABP_Unarmed`'s blend space,
so the legs jog rather than play a walk sped up (it was 110 cm/s while the NPC was scenery
rather than a threat),
`orient_rotation_to_movement`, `ai_controller_class` = the controller above and
`auto_possess_ai = PLACED_IN_WORLD_OR_SPAWNED`. Behaviour constants live in
`npc_placement.py` — which imports no `unreal` — so the host-side generator can bake them
into the verification checks without an editor.

### 3.2e Navigation

The import script spawns a `NavMeshBoundsVolume` sized by `npc_placement.compute_nav_bounds`
plus a `RecastNavMesh`. **How that volume is sized is the single most load-bearing detail in
the NPC feature**, and getting it wrong is silent.

**The level must not contain saved nav data.** This was the root cause of the NPC never
moving, and it masqueraded as several other bugs. A headless editor never finishes an async
navmesh bake, so a `RecastNavMesh` saved from the import script carries *empty* serialised
tiles. At game start the engine finds those structurally valid and reuses them instead of
building — 0 tiles, every `MoveToActor` returns `Failed`, and the NPC stands still forever.

What made it so slippery: it appeared to work immediately after any change to the nav bounds,
because the changed parameters no longer matched the serialised ones and the engine logged

```
Warning: Recreating dtNavMesh instance (RecastNavMesh_0) due mismatch in number of bytes
required to store serialized maxTiles (serialized: 1083, 11 bits) vs calculated required (972, 10 bits)
```

and rebuilt from scratch. Every "successful" run during development was an accident of having
just retuned the bounds; once they settled, it silently stopped building and stayed broken.

The fix is for the import script to destroy every `RecastNavMesh` **as its last action before
`save_current_level()`** — the navigation system re-creates nav data whenever the level is
open, so stripping it any earlier accomplishes nothing — and to let the navigation system
create the mesh at load instead. `Config/DefaultEngine.ini` sets
`[/Script/NavigationSystem.RecastNavMesh] RuntimeGeneration=Dynamic` as a **class default**,
because the nav system overwrites per-actor values with class defaults on registration (the
same reset that clobbers `AgentRadius`).

This is not assertable from the editor: opening a level always materialises a nav actor in
memory, so a check cannot tell "saved on disk" from "created on load". The runtime grep for
`Building tile` is the only real gate.

**Recast also generates nothing at all if the volume is too large.** No warning, no error, no
`LogRecast` output — the navmesh registers, `CalculateMaxTilesCount` runs, and then no tile is
ever built, so every query fails with `InitPathfinding start point not on navmesh` and the NPC
stands still forever. The first implementation sized Z as a fraction of map width, giving
±4000 cm on a 200 m map, and produced **zero** tiles. Measured envelope:

| Volume | Result |
|---|---|
| ±10000 cm XY, 8000 cm Z span | **0 tiles** — NPC immobile, 862 consecutive `Failed` |
| ±9200 cm XY, 2007 cm Z span | **0 tiles** — NPC immobile (not reproducible today; see below) |
| ±8500 cm XY, 1500 cm Z span | 176 tiles — NPC walks to the player |
| ±8500 cm XY, 1479 cm Z span | 324 tiles — NPC walks 51 m and stops at the player |
| ±10000 cm XY, 4586 cm Z span | navmesh reaches the terrain edge on all 48 sampled headings |

The last row is the current configuration, and it invalidates the conclusion the first four
were used to draw. Reading the second row as an *XY* limit produced `NAV_MAX_HALF_XY_CM` =
8500 — and with it a 15 m ring of walkable terrain with no navigation data on it, which is
where the NPCs stopped following (§4). Re-measured one dial at a time, by resizing the volume
in a live editor, running `RebuildNavigation` and then projecting points onto the result, the
limit is in **Z alone**: 4586 cm builds, 8000 cm does not. The ±9200 / 2007 row is most likely
the stale-`RecastNavMesh` bug below wearing a different hat — it predates the strip-before-save
fix — but it has not been reproduced, so it stays in the table as measured rather than being
quietly deleted.

`NAV_MAX_VERTICAL_SPAN_CM` (5000) and `NAV_MAX_HALF_XY_CM` (10000) now sit *at* the
measured-good point rather than below it, and `NAV_COVERAGE_FRACTION` is 1.0. They are still
**empirical**, not derived: UE 5.8 exposes neither `tile_size_uu` nor a readable tile limit to
Python. If a navmesh ever comes up empty, change one dial, rebuild, and project at it.

Two consequences for how the volume is computed:

- **Size Z from the terrain, not the map.** `compute_nav_bounds` walks `grid_z` and takes the
  actual min/max elevation, then adds headroom that must exceed the agent height (144 cm) or
  the ground beneath the ceiling reads as too low to stand in.
- **Sample the box, corners included.** This used to sample an inscribed disk, so that the
  corner ramps — ~40 m tall on this terrain — could not inflate the Z band. That is a saving
  only if a tall band is fatal, and it is not until 8000 cm. What the disk actually bought was
  corners sticking up through the volume's ceiling, non-navigable. The box is what gets built,
  so the box is what gets sampled.

The cap only bites on a map wider than 200 m, where the navmesh would again be a central
island — so `npc_usable_radius()` clamps the NPC's spawn radius to the same cap, and both
`place_npc()` and the offline checks call it so they cannot drift apart. On the maps that
exist, `EDGE_MARGIN_FRACTION` (0.80) binds first and the cap is slack.

Two further findings shaped this:

- **The nav system overwrites the agent config.** `agent_radius`/`agent_height` set on the
  RecastNavMesh are replaced by the navigation system's default agent (35 cm / 144 cm) when
  the nav data registers, so a per-actor override does not survive a load. The constants
  therefore *match* those defaults rather than pretending otherwise; widening the inset around
  trunks means changing Project Settings → Navigation System → Supported Agents. A 35 cm inset
  still clears the NPC's 34 cm capsule, and tree spacing is ≥ 125 cm.
- **A headless bake never completes.** `-ExecutePythonScript` does not tick the editor, so
  async tile generation makes no progress and a path query right after setup returns `None`.
  Generated levels therefore set `runtime_generation = DYNAMIC` (this property *does* stick)
  and the navigation system builds the mesh at game start — which is the right model for
  procedural content anyway.

The consequence for verification: the rig can be asserted, but whether a path is actually
found can only be confirmed in PIE. See §6.

### 3.2f Patrol, senses and noise (agro)

A wanderer has two states, held in one `Aggro` bool on its AI controller. It spawns
**patrolling** (every respawn too, since each spawn gets a fresh controller) and switches to
**aggro**, the chase-and-swing loop of 3.2d, when a sense detects the player. Nothing switches
it back.

**Where things live**

| concern | code | numbers |
|---|---|---|
| the patrol/aggro switch | `npc/agro.py` | — |
| hurt, sight, touch, hearing | `npc/senses.py` | `forest_generator/npc_agro.py` (`AgroSettings`, per creature) |
| patrol setup and stroll | `npc/patrol.py` | same `AgroSettings` row |
| the noise record (vars) | `combat/game_state.py` | — |
| writing a noise | `combat/noise.py` (`_author_make_noise`) | `COMBAT` noise fields, `combat/tuning.py` |
| gunshot noise | `combat/weapon_component/shot_noise.py` | `SHOT_VOLUME_CM` → `ShotVolume` on each weapon |
| footstep noise | `combat/footsteps.py` | `COMBAT.footstep_noise_*` |
| checks | `npc/verify.py`, `combat/verify/noise.py` | — |

All numbers are **baked into pin literals** at build time, like every other NPC and combat
number (see 3.2d and §5). Each creature already has its own controller for its attack clip, so
each creature's controller also carries its own senses. Changing a number means editing the
table and re-running `build_weapons_and_combat.py` (emitters) and/or `build_npc_blueprints.py`
(listeners).

#### The heartbeat

The switch is spliced into the controller's existing 0.5 s loop, between the stats/voice block
and the chase. There is no second Tick:

```
possessed? -> stats + voice -> patrol setup (once per life)
           -> [Aggro?] yes ------------------------------------> chase + swing -> Delay 0.5 s
                 no  -> [player pawn valid?] no ----------------> patrol step --> Delay 0.5 s
                         yes -> hurt? -> sight? -> touch? -> sound?
                                 any yes -> AggroReason = <sense>, Aggro = true,
                                            MaxWalkSpeed = RunSpeed,
                                            PrintWarning "[NPC-AGRO] <sense> -- <actor>"
                                            -> chase + swing (this same heartbeat)
                                 all no  -> patrol step -> Delay 0.5 s
```

The senses are a chain of **exec branches**, not one boolean OR. `BooleanAND`/`OR` do not
short-circuit and pure nodes are evaluated by whatever reads them, so a single expression would
run the line-of-sight trace and the GameMode cast every heartbeat whatever the cheaper senses
said, and it could not report which sense fired.

#### Patrol

*Setup, once per life, on the first heartbeat with a pawn:* `PatrolHome` = the pawn's location
(the centre of its circle, so a respawn patrols around its new spot); `RunSpeed` = the pawn's
current `MaxWalkSpeed` (this already includes the creature's speed multiplier and the level's
per-instance gait variance); `MaxWalkSpeed = RunSpeed × patrol_speed_scale`.

*Step, on every patrolling heartbeat:* once `now ≥ NextPatrolTime`, it sets
`PatrolTarget = GetRandomReachablePointInRadius(PatrolHome, patrol_radius_cm).RandomLocation`
and `NextPatrolTime = now + random(repick_min, repick_max)`. If `|PatrolTarget − PatrolHome| ≤
radius × 1.1 + 200 cm`, it calls `SimpleMoveToLocation(PatrolTarget)`.

- The query is **pure**, so each output read would re-run it. Only `RandomLocation` is read,
  once, into a variable, and `ReturnValue` is never read.
- The distance guard replaces `ReturnValue`. On failure the query returns the origin it was
  given; with no navigation system it returns the zero vector, which is the player's spawn
  point, and the guard refuses that.
- `SimpleMoveToLocation` is used rather than a second `MoveToActor`/`MoveToLocation`, because
  the level verifier asserts the chase has exactly one of each.
- Speed is always written from the stored `RunSpeed`. Scaling the live `MaxWalkSpeed` would
  compound on every write.

#### The four senses

Let `P` be the pawn location, `Q` the player location, `F` the pawn's forward vector and `A` the
creature's `AgroSettings`.

| sense | condition | cost |
|---|---|---|
| hurt | `BP_HealthComponent.DamagedByPlayer` (the flag the kill count trusts) | cast + read |
| sight | `\|Q−P\| ≤ A.vision_range_cm` **and** `F · unit(Q−P) ≥ cos(A.vision_half_angle_deg)` **and** `LineOfSightTo(player)` | 1 visibility trace |
| touch | `\|Q−P\| ≤ A.touch_range_cm`, from any direction | distance |
| sound | see below | GameMode cast |

`F` is the facing, and while patrolling that is the walking direction
(`orient_rotation_to_movement`). The player can therefore approach from behind unseen, but not
touch it. `LineOfSightTo` is the controller's own function and traces from the pawn's eyes, so
tree trunks block sight.

#### Sound: one noise record, owned by whatever made the noise

The emitters (weapon component, footstep component) and the listeners (every controller) share
no reference to each other, so the noise is published on the GameMode. The GameMode is already
the world-scoped wiring point for the spawn and kill counters.

| GameMode variable | meaning |
|---|---|
| `NoiseTime` | world time of the write |
| `NoiseLocation` | where the noise was made (muzzle, player's feet) |
| `NoiseRange` | all-round reach in cm, at hearing scale 1.0 |
| `NoiseDirection` | unit vector of the cone (gunshot only) |
| `NoiseConeRange` | reach inside the cone; 0 = no cone |
| `NoiseConeCos` | cos of the cone's half-angle |

**Write rule** (`_author_make_noise`). With `loud(x) = max(x.Range, x.ConeRange)`:

```
write  iff  now − NoiseTime ≥ COMBAT.noise_hold_s            (record is stale)
       or   loud(new) ≥ loud(record)                          (new noise is at least as loud)
```

There is one record, so a new noise replaces the old one. The hold stops a footstep from
erasing a gunshot before every wanderer has had a heartbeat to check it. That only works while
`noise_hold_s` (0.6 s) is longer than the heartbeat (`NPC_REPATH_SECONDS`, 0.5 s), and the
combat verifier asserts that inequality.

**Hearing test** (listener, `_author_hearing`), with `h = A.hearing_scale`, `L =
NoiseLocation` and `d = |P − L|`:

```
recent  = now − NoiseTime ≤ noise_hold_s
round   = d ≤ NoiseRange · h
cone    = d ≤ NoiseConeRange · h   and   NoiseDirection · unit(P − L) ≥ NoiseConeCos
heard   = recent and (round or cone)
```

- `recent` stops a wanderer that strolls into range later from hearing an old noise.
- The noise decides how far it carries; the listener contributes only `h`.
- Distances are 3D, from the noise source to the capsule centre. NPC ground heights on the
  200 m map vary by about 7 m, so this is within about 1% of horizontal distance.

**Emitters**

| noise | `NoiseRange` | cone | written |
|---|---|---|---|
| gunshot | held weapon's `ShotVolume` | `ShotVolume × shot_noise_cone_range_scale` (1.6), `cos(shot_noise_cone_half_angle_deg = 30°)`, direction = the pellets' own muzzle→AimPoint vector | after the pellet loop, every shot |
| footstep | `speed × footstep_noise_range_cm / footstep_noise_reference_speed_cms` (1200/600 = 2.0 s) | none (`NoiseConeRange` = 0) | on each footfall, **player only** (`IsPlayerControlled`; the wanderers use the same component) |

The shot's cone uses `_author_fire`'s returned direction pin, not a recomputed copy, so the
cone always points along the line the pellets were traced.

#### Effective ranges

Per creature (`NPC_AGRO`):

| | vision | half-angle | touch | hearing | patrol radius | patrol speed | re-pick |
|---|---|---|---|---|---|---|---|
| Zombie | 20 m | 50° | 2.5 m | 1.0× | 15 m | 0.30 × run | 6–12 s |
| Wendigo | 35 m | 65° | 3.0 m | 1.4× | 30 m | 0.30 × run | 8–16 s |

Gunshots (`SHOT_VOLUME_CM`), showing reach at hearing scale 1.0 (zombie) / 1.4 (wendigo):

| gun | all round | inside the 30° cone | heard from the player start (avg of 10)* |
|---|---|---|---|
| Sniper | 150 / 210 m | 240 / 336 m | 10 |
| Rifle | 90 / 126 m | 144 / 202 m | 9.9 |
| Shotgun | 85 / 119 m | 136 / 190 m | 8.7 |
| SMG | 50 / 70 m | 80 / 112 m | 0.6 |
| Pistol | 35 / 49 m | 56 / 78 m | 0 |

\* All-round only, over `Lvl_Forest_200m`'s ten spawn points with each wanderer anywhere in its
patrol circle. The pack starts 75–78 m out, just inside rifle and shotgun range, so from the
centre those two wake nearly as many as the sniper. From a corner the sniper reaches 7–10 and
the rifle/shotgun 3–6. The cone only reaches what lies within 30° of the aim, not the whole
ring.

Footsteps: 12 m at a 600 cm/s run, 18 m at the 900 cm/s sprint, 6 m at the half-speed ADS walk
(× 1.4 for a wendigo).

These are agro ranges only. The audio attenuation profiles that set how loud shots *sound*
(§5) are separate and unchanged.

#### Verification

- `verify_npc_blueprints.py` (100 checks) tests each controller against its own creature's
  row: variable types, spawning with `Aggro` false, a single flip to true, the four reasons,
  the chase reachable only through the switch, both speed writes derived from `RunSpeed`, the
  pure query read once, the guard, and every sense literal. It tells equal literals apart by
  which distance they measure (the wendigo's 35 m sight equals its 35 m patrol guard).
- `combat/verify/noise.py` checks the record's types, each gun's `ShotVolume` and their order,
  both writers' stale-or-louder guard and fields, the cone sharing the pellets' direction, the
  player-only footstep gate, and `noise_hold_s > NPC_REPATH_SECONDS`.
- Runtime (headless `-game`, probes through the inbox): patrol stayed inside its circles and
  never approached an idle player. Each sense flipped the right wanderer: sight, touch, hurt,
  an all-round noise, a cone aimed at an NPC, and the player's real footsteps 8 m behind one.
  A 5 m noise 25 m away and an NPC behind a shot fired away from it did not flip. The gunshot's
  own write has **not** run live, because a headless run cannot press the trigger (raw-key
  polling, no Python input injection); it shares its writer with the footsteps, which are
  proven.

#### Limits and next dials

- **No way back to patrol.** Losing interest would be a new `AgroSettings` field and a branch
  on the yes arm of `[Aggro?]`.
- **One record means one noise per ~0.6 s window.** Two simultaneous noises in different
  places keep only the louder. A list would need an array on the GameMode and a loop in every
  listener.
- **Sound ignores occlusion.** A shot carries through trees and terrain, while sight does not.
- **No pack alerting.** One wanderer going aggro does not alert its neighbours.

### 3.3 Offline verification — `forest_generator/verification.py`

`run_all_checks` → `VerificationReport` (`CheckResult` list, `summary`, `all_passed`,
`to_json`). 19 checks, all of which must pass before any editor work happens:

- **Terrain (5):** OBJ validity, bounds ±5 %, flat spawn zone, upward normals,
  barycentric consistency.
- **Trees (7):** count sanity, in-bounds, not floating, not buried, vertical, spacing,
  spawn-zone clear.
- **Grass (7, skipped under `--no-grass`):** density within 70–105 % of the request;
  in-bounds; seated on the mesh (terrain Z re-derived for a 500-clump sample and compared
  against the recorded value and the sink); knee height (the knee layer must average inside
  ±30 % of the target and no clump may exceed 1.6×); upscale factor ≤ 2.4×; coverage —
  every cell of a 12×12 grid over the map contains grass, which is what "throughout the
  level" actually means; species spread.
- **NPC (8, skipped under `--no-npc`):** placed at all; within the usable bounds; far enough
  from the player to have a journey; clear of trunks; grounded (capsule centre exactly one
  half-height above the re-derived terrain Z); and route-obstructed — reports whether a tree
  blocks the direct line. That last one passes either way by design, since a clear line can
  be legitimate on a sparse map, but it tells you whether the detour behaviour is being
  exercised. Plus `Nav Bounds Sane` (vertical span within the measured envelope) and
  `NPC Inside Nav Bounds` (the capsule's *feet* — pathfinding queries feet, not centre — lie
  inside the volume, and nav coverage is not narrower than the NPC's spawn radius).

### 3.4 Generated import script

`_write_unreal_import_script` emits, in order:

1. **Import OBJ** → `/Game/Forest/Test/SM_<Level>_Terrain` (`AssetImportTask`, replace+save);
   Nanite disabled, `collision_trace_flag = CTF_USE_COMPLEX_AS_SIMPLE`, `allow_cpu_access`,
   material `M_Forest_Ground_PBR`.
2. **Level** `/Game/Maps/<Level>` — load if it exists and destroy every actor whose label
   starts with the level name, `HISM_Tree` or `HISM_Grass` (idempotent re-generation),
   else `new_level`.
3. **Terrain actor** — `StaticMeshActor`, `BlockAll`, `QUERY_AND_PHYSICS`, static.
4. **Lighting & sky** — fully driven by the embedded preset (§4).
5. **Trees** — placements inlined as a `TREE_DATA` literal, grouped by spec; one actor per
   species carrying a `HierarchicalInstancedStaticMeshComponent` as its root, `BlockAll`,
   static, shadow-casting, materials set by slot index, then one `add_instance` per tree.
5b. **Grass** — transforms are *not* inlined (tens of thousands of them); the script reads
   `grass_<Level>.json`, whose instances are flat rounded arrays
   `[spec_idx, x, y, z, yaw, pitch, roll, height_mul, width_mul, target_h_cm]` against an
   interned spec-name table. One HISM actor per species, `NoCollision` (grass must never
   block the player), cull distances 6000–9000 cm, shadow-casting. Per species the script
   reads the mesh bounds once, then per instance sets
   `scale = (unit·width_mul, unit·width_mul, target_h / mesh_height)`. If bounds come back
   unusable it logs an error and falls back to scale 1.0 rather than emitting giant grass.
6. **PlayerStart** at `(0, 0, 100)`.
7. **Navigation + NPC** — `NavMeshBoundsVolume` scaled to the map, `RecastNavMesh` with
   `runtime_generation = DYNAMIC`, then `build_npc_blueprints.ensure_npc_blueprints()` and the
   NPC actor spawned at the computed transform (§3.2c–e).
8. `save_current_level()`.

All spawned actors are labelled `<LevelName>_<Role>` (`_Terrain`, `_Sun`/`_Moon`,
`_SkyAtmosphere`, `_SkySphere`, `_SkyLight`, `_Fog`, `_PostProcess`, `_PlayerStart`) —
that convention is what makes step 2's cleanup and the verify script's lookups work. The
NPC rig follows it too: `_NavBounds`, `_NavMesh`, `_NPC_Wanderer`.

### 3.5 Generated verify script

`_write_unreal_verify_script` emits a `check(name, condition, detail)` harness and 101
assertions over the *saved* level: terrain actor/component/collision/Nanite/material, the
full lighting rig against the preset (§4.3), tree HISM counts per species, PlayerStart, and
per grass species — actor exists, instance count, `NoCollision`, and a **knee-height proof**:
50 instance transforms are sampled and `scale.z × mesh bounds height` must land inside the
min/max target height the offline pass recorded for that species. That last check is the one
that would catch a mis-scaled asset, since nothing offline can see the mesh.

The NPC block asserts both Blueprint assets exist; that the character's `ai_controller_class`
points at the controller, `auto_possess_ai` is `PLACED_IN_WORLD_OR_SPAWNED`, `max_walk_speed`
is the 600 cm/s run, and the mesh and anim class are set; that the controller's melee literals
(range, damage, interval) and its `NextAttackTime` cooldown variable survived the save, since an
unset pin compiles as a swing for 0 damage at a range of 0; that **each** of the five placed
actors is a `Character` at its expected transform and inside the spawn band; and that
the nav bounds cover the map and the navmesh's `runtime_generation` is `DYNAMIC`.
The nav block asserts the volume's XY and Z extents and centre match what the generator
computed, that the vertical span is inside the measured envelope, and that the NPC's feet sit
inside the volume.
Prints `[VERIFY] ✅ ALL 141 CHECKS PASSED!` or a list of failures.

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

## 5. The run loop — damage, ammunition, sprint, death

The level generator above knows nothing about any of this; it is built by
`Scripts/build_weapons_and_combat.py` and `Scripts/build_graphics_menu.py` onto assets that
every generated level picks up through `BP_ThirdPersonGameMode`. CLAUDE.md carries the
reasoning; this is the shape.

**Four values on the GameMode, because Blueprints have no statics** and each has to outlive
every actor that touches it — including the player's own components, which die with them:

| variable | written by | read by |
|---|---|---|
| `NpcSpawnCount` | each wanderer's `BeginPlay` | the next wanderer, for its number |
| `NpcKillCount` | the death path, *only* when `DamagedByPlayer` | the HUD corner and the death menu |
| `PlayerDead` | the player's death path | the HUD, to draw the menu instead of the HUD |
| `DebugMode` | **D** in the graphics menu | the weapon component (tracers) and the HUD (NPC numbers) |

`DebugMode` is on the GameMode rather than on the HUD that toggles it for the same reason as
the rest: `BP_WeaponComponent` is the other reader, and a component cannot reach a HUD
variable. Both readers take one cheap copy — the weapon component once per shot, the HUD once
per `DrawHUD` — rather than casting per pellet or per wanderer. The HUD's copy (`DebugOn`) also
gives the cast-failed path a real answer, since that path reaches the same drawing code and a
`Get` off an invalid object is an `Accessed None` per wanderer per frame.

**Two stamps on the health component,** both written by the pellet that landed
(`_author_impact`) and by nothing else:

```
LastDamageTime    GetTimeSeconds() at the hit;  the HUD shows a wanderer's bar for 5 s after it
DamagedByPlayer   true;  the guard that separates a kill from the safety net's own deaths
```

`DamagedByPlayer` is the load-bearing one. The under-the-world net writes `Health = 0` and lets
the ordinary death path run, so without the guard every wanderer the terrain lost would score.
Measured both ways: five wanderers killed with the flag report `killed with 5`, the same five
without it report `killed with 0`.

**The death branch now has two arms.** `DespawnOnDeath` decides which:

```
Health <= 0, not already Dead
   |
   +-- DespawnOnDeath  --> [DamagedByPlayer? -> NpcKillCount += 1
   |                                          -> spawn BP_AmmoPickup (2 shells)
   |                                          -> roll 10%: spawn one of DropClasses,
   |                                             cast to BP_WeaponItem, Dropped = true]
   |                       --> respawn --> destroy
   |
   '-- otherwise (the player)
          DisableMovement   <-- also reached by the world-floor net below
          -> MM_Death_Front_01 into FullBodySlot
          -> Delay 2.2 s                       (the animation is ~1.9 s)
          -> GameMode.PlayerDead = true
          -> "[PLAYER-DEAD] killed with N"
          -> SetGamePaused(true)
```

**The world floor feeds that same branch.** Any owner below `WORLD_FLOOR_Z` (−1000 cm) has
`Health` written to 0, which runs the ordinary death path; `DespawnOnDeath` gates only the
`[NPC-FELL]` log line, which quotes an `NpcId` and a spawn point the player has not got. That
one relocated AND is the whole of "the player dies if they walk off the edge" — no KillZ, no
teleport, and exactly one way to die in the game.

`FullBodySlot` is a **second** Slot node in `ABP_Unarmed`, inserted between the layered blend
and the ControlRig. `DefaultSlot` sits *inside* the blend and is filtered to the upper body, so
the aim pose can leave the legs walking — a death played into it folds the chest over legs that
are still standing.

**Ammunition lives on `BP_WeaponItem`,** not on the weapon component, because a weapon here is
a droppable actor: a half-empty shotgun left on the ground has to still be half empty when it is
picked up again. Seven fields — `UsesAmmo`, `MagazineSize`, `Loaded`, `Reserve`, `FireInterval`,
`ReloadSeconds`, `NextFireTime` — and the difference between the shotgun (5 + 15 shells, 0.85 s,
1.6 s reload, 8 × 18 damage) and the pistol (`UsesAmmo` false) is entirely a row in
`_weapon_specs()`. Nothing in any graph branches on a weapon's name.

That was a design claim until three more weapons were added to test it. **The SMG, assault rifle
and sniper cost three rows in `_weapon_specs()` and three part tables, and changed no node in
`_author_fire`, `_author_reload` or the fire gate** — pellet count, spread, range, interval,
magazine size and reload time were already the parameters those graphs read off `Held`. The
sniper's 120 × 1 at 0.2° over 200 m and the SMG's 12 × 1 every 0.09 s run the same code path as
the shotgun's 8 × 18 cone.

`NextFireTime` is a **world-time deadline**, and both the interval between shots and the cost of
a reload push it out; there is no reloading state, no timer and no flag that can disagree with
itself. The fire gate is **two nested Branches** rather than one folded condition, because every
ammunition and cooldown test reads a property off `Held` and a Branch's condition is pulled on
every frame, including the frames where nothing is equipped.

```
(tapped(LMB) OR holding(LMB)) AND Held valid AND NOT Sprinting
   '-- ((NOT UsesAmmo OR Loaded > 0) AND now >= NextFireTime)
       AND (tapped OR (holding AND Held.Automatic))
          -> Loaded -= 1;  NextFireTime = now + FireInterval
          -> cache GameMode.DebugMode;  sound;  one trace per pellet
```

**Automatic fire is the `Automatic` term in that inner condition and nothing else.** The outer
gate asks only what is answerable with no weapon in hand; the weapon-specific half is nested
inside, where `Held` is valid, because a Branch's condition is pulled every frame and reading
`Automatic` off `None` would be an `Accessed None` per frame of walking around empty-handed.
`BP_SMG` and `BP_AssaultRifle` set it; rate of fire stays entirely `FireInterval`.

**Three sounds per weapon, and two of them are about silence.** `FireSound`, `DryFireSound` and
`ReloadSound` all live on `BP_WeaponItem` and are read off `Held`. `ReloadSound` is genuinely
per-weapon — a pump, a magazine change, a slower hand-fed reload — while `DryFireSound` is
shared, which is a fact about the defaults and not about the shape of the data. All nine assets
are cuts from CC0 recordings of real firearms, produced by `Scripts/fetch_weapon_sounds.py`
(mono, because `PlaySoundAtLocation` can only spatialise one channel; level baked in per weapon,
so twelve overlapping SMG rounds do not clip). The click hangs off the **False arm of the ready
gate** and is gated on `empty AND cooled AND tapped` — the cooldown is the other reason the gate
refuses, and `tapped` is what stops a *held* empty trigger clicking sixty times a second. The clack plays on the **True
arm of the reload only**, because the False arm moves no rounds and costs no pause, so a sound
there would announce something that did not happen.

**Sprinting stops the ready pose rather than adding an animation.** The pose is `AimPose` played
as a dynamic montage into the upper-body-filtered `DefaultSlot`; stop the slot and the layered
blend has nothing left to override the locomotion state machine with, so `ABP_Unarmed`'s own run
cycle comes through and the weapon rides along in the hand socket. The equip branch gains
`AND NOT Sprinting`, and Tick raises `NeedsRefresh` **only on the frames `Sprinting` disagrees
with `PoseSprinting`** — level-triggering it restarts the montage every frame Shift is held.

**One kill in ten leaves a weapon.** Two independent draws: `RandomFloat < GUN_DROP_CHANCE`
decides *whether*, and `Array_Get(DropClasses, RandomInt(0, Length-1))` decides *which*, so the
rate and the table tune apart — a fourth findable weapon changes what a drop is worth, not how
often one happens. `DropClasses` is an array on `BP_HealthComponent` (typed class-of-Actor, for
the same reason `AmmoClass` is, and filled by `main()`), guarded by `Length > 0` so an unfilled
table drops nothing instead of indexing off the end. The roll sits on the same `DamagedByPlayer`
arm as the shells. `Dropped = true` on the spawned actor is the entire handover: from there it is
an ordinary weapon in the forest and `_author_pickup` needs no knowledge that drops exist.

**`BP_AmmoPickup`** measures its own distance to the player on its own Tick — a handful of
actors ticking beats a `GetAllActorsOfClass` sweep from the weapon component every frame — and
credits the weapon in the player's **hands** when that weapon takes ammunition, falling back to
the first such weapon in `Inventory` otherwise. The preference matters now that four of the five
weapons use ammunition: "first in the inventory" is the shotgun in slot 0, always. The `Held`
read sits behind a nested `IsValid` gate, not beside one in an `AND`, because `UsesAmmo` is a
pure pull and pulling it off `None` is an `Accessed None`. It destroys itself only once
`Credited` is set (`ForEachLoop` has no break pin, and a shotgun-less player must leave the
shells where they are).

**Sprint lives on `BP_WeaponComponent`,** with `Stamina` / `MaxStamina` / `Sprinting` /
`BaseSpeed`, because that is the component that has to refuse to fire while the key is held and
the one the HUD already casts to. `BaseSpeed` is read off the character at `BeginPlay` (600 in
this project, measured at runtime) and never hardcoded.

**The HUD's `DrawHUD` branches on `PlayerDead` first**, so the menu replaces the HUD rather
than covering it, and it polls the restart key itself — Event Tick does not run in a paused
world, which is the only state the menu exists in, while `DrawHUD` is called by the renderer
every frame and `APlayerController` ticks through a pause.

## 6. Conventions & pitfalls

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
- **Determinism.** Same `--seed` ⇒ same terrain, tree and grass transforms. Change the seed,
  not the placement code, when you want a different forest. The grass RNG is seeded
  `seed ^ 0x6A55` so grass settings can be retuned without disturbing tree placement.
- **Never hard-code a grass scale.** The scans carry no real-world size; derive it from
  `get_bounds()` at plant time (§3.2b).
- **Blueprint authoring is available from Python.** `BlueprintGraphEditor` +
  `BlueprintEditorLibrary` cover node creation, pin lookup, connection, variables, compile.
  Prefer it over hand-editing assets — and never over editing `.uasset` as text.
- **Foliage instance budgets.** ~44 k HISM instances at the default density is fine, but the
  count scales with map *area* — a 400 m map is 4× the clumps. Reach for `--grass-density`
  before reaching for a new scatter algorithm.
- **Verify after importing.** The offline suite cannot see collision, materials or actors;
  the in-editor script is the real gate.

---

## 7. Status (as of 2026-09-27)

- Git: branch `night-mode`, working tree clean, head `e5745e9 night mode initial`
  (adds `lighting.py`, the generator rewrite, the regenerated night scripts and a `.gitignore`).
- `/Game/Maps/Lvl_Forest_200m` — 200 m, seed 42, 136 trees over 5 species, 44,368 knee-high
  grass clumps over 9 species, **ten NPCs 75.0–78.0 m** from the player (every one of them
  with at least one tree blocking the direct line), **night** preset.
  Offline 28/28, in-editor **148/148**, import log clean. The `NavMeshBoundsVolume` covers the
  whole map (±10000 cm XY, 4580 cm band centred z 1905), so there is no navigation dead zone
  around the edge any more.
- Combat and HUD: **383/383** (`verify_weapons_and_combat.py`) and **60/60**
  (`verify_graphics_menu.py`). A 90 s `-game` run is clean — 0 runtime errors, 0 Accessed
  None, 10 spawns, 0 falls — and ends with the pack killing the player, which is the death
  path running end to end. The ammunition pickup was proved the same way: a `BP_AmmoPickup`
  dropped on the player took the shotgun's reserve from 15 to 17 and removed itself.
- Five weapons: `BP_Shotgun` and `BP_Pistol` issued at `BeginPlay`, `BP_SMG`,
  `BP_AssaultRifle` and `BP_SniperRifle` obtainable only as a 10% drop from a counted kill.
  The drop path was proved at runtime with a temporary probe and the chance forced to 1.0:
  ten forced kills left **12 `BP_WeaponItem` actors** (2 = the player's own) of which **10
  carried `Dropped = true`**, plus ten shell drops, with 0 errors and 0 `Accessed None`. The
  second number is the one that matters — counting actors proves a spawn happened, while the
  flag proves the cast behind it succeeded and the pick-up interface was written.
- **Nine** audio assets under `/Game/Weapons/Audio`, all cut from **CC0 recordings of real
  firearms** by `Scripts/fetch_weapon_sounds.py` (pure Python plus `curl`, `bsdtar` and
  `afconvert`; imports no `unreal`): five gunshots from five firearms in one library, three
  reloads (pump / magazine / hand-fed) and one lock click. The synthesiser it replaced,
  `make_weapon_sounds.py`, is gone. `Scripts/downloaded_sounds/` caches ~200 MB of source
  archives and is git-ignored.
- **Automatic fire:** `BP_SMG` and `BP_AssaultRifle` keep firing while the button is held,
  via one `Automatic` bool read behind the valid-`Held` gate. The other three are tap-only.
- **Falling off the level kills the player**, through the world-floor net that already caught
  wanderers (§5). Proved at runtime: `hp=0.0 dead=True` under −1000 cm and
  `[PLAYER-DEAD] killed with 0` in the log.
- **The pack follows to the edge of the map.** With the navmesh covering the whole terrain, a
  player teleported to x=9500 and again to x=9800 (2 m from the edge of the world) projects
  onto the navmesh, and all ten wanderers close at 600 cm/s — five inside melee range by
  t = 17 s, with 0 errors and 0 Accessed None.
- New assets from the NPC run: `/Game/Forest/NPC/BP_ForestWanderer`,
  `/Game/Forest/NPC/BP_ForestWandererAI`.
- **Pre-existing bug, unfixed and unrelated to the NPC work:** `scatter_trees` performs no
  minimum-spacing rejection — it draws independent polar coordinates — so some size/seed
  combinations fail the `Tree Spacing (>100cm)` check. `--size 300` with the default seed 42
  produces a 70 cm pair; 300 m with seed 99 passes, as does 200 m with seed 42. Reproduces
  with `--no-grass --no-npc`. The fix is rejection sampling (or a Poisson-disc scatter) in
  `tree_placement.scatter_trees`.
- New engine assets from that run: `M_NightSky_Starfield`, `MI_NightSky_Starfield`.
- The `day` path was regression-checked with a throwaway 100 m level (12/12, both emitted
  scripts parse, day-only asset references present) and the throwaway removed.
- Not verified programmatically: how the night scene actually *looks*. Tune
  `star_brightness`, moon `intensity`, and `auto_exposure_bias` in `lighting.py` by eye.
  The same applies to grass: the checks prove every clump is knee high, seated on the
  terrain, evenly covering the map and not over-stretched, but density and patchiness are
  taste calls — `--grass-density` and `--grass-patchiness` exist for that.
- **The NPC's walk is verified, but only out of process.** A headless `-ExecutePythonScript`
  run does not tick the editor, so no path can be queried from the generator's own checks.
  Running the map as a game does work, and is how the fix above was validated:

  ```
  UnrealEditor-Cmd <uproject> /Game/Maps/<Level> -game -nullrhi -unattended \
      -forcelogflush -LogCmds="LogNavigation Verbose" -abslog=<path>
  ```

  Grep for `Building tile` (hundreds when healthy, **zero** when the volume is oversized) and
  `not on navmesh` (a couple at startup, then silence). Note `-stdout` block-buffers and UE
  writes no `Saved/Logs` under it, so `-abslog` plus `-forcelogflush` are required — without
  them the log looks frozen at engine init while the process burns CPU.

  Last measured run on `Lvl_Forest_200m`: the NPC walked 51.7 m of path from
  (−1422, 5114) to (0, 187) in 27 s and held at the acceptance radius.

- **Walk speed: resolved.** It measured 192 cm/s against a configured 110 for as long as the
  navmesh was broken — with no navmesh, path following falls back to setting velocity
  directly, which bypasses `MaxWalkSpeed` *and* leaves `GetCurrentAcceleration()` at zero.
  With the navmesh building, the move is acceleration-driven and measures **100 cm/s**.
  The same zero-acceleration side effect is why `ABP_Unarmed` (whose `ShouldMove` is
  `GroundSpeed > 0 AND Acceleration != 0`) held the idle pose.

- Two fixes were tried for the idle-pose symptom *before* the navmesh cause was found, and
  both were measured to stop movement dead (0.0 m); neither is used, and both are recorded in
  `build_npc_blueprints.py` so they are not retried: setting
  `NavMovementProperties.use_acceleration_for_paths = True`, and driving the mesh with
  `ANIMATION_SINGLE_NODE` playing a walk clip (the single-node instance consumes root motion,
  and the template clips are root-locked, pinning the character in place).
- **Note on in-place blueprint updates.** `build_npc_blueprints.py` now updates assets in
  place rather than delete-and-recreate (deletion fails whenever the level or the other
  blueprint still references them). Consequence: every property must be set *explicitly* —
  deleting a line no longer reverts it, because the asset keeps its previous value.
- **Not reproduced — stopping at obstacles.** The route above had `path/straight = 1.008`,
  i.e. essentially straight, so no headless run has yet exercised a real detour. Navmesh
  carve inset is the agent radius (35 cm) against a 34 cm capsule, leaving ~1 cm of
  clearance, so a path hugging a trunk is a plausible jam point. Widening it means changing
  Project Settings → Navigation System → Supported Agents, since per-actor agent values are
  overwritten on registration.
