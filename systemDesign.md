# Otherworld — System Design

The high-level design of the Otherworld Unreal Engine 5.8 project: what the game is, how
its systems fit together, and where the architecture is going. It is the document to read
for a change that spans systems or for the long view; a small change inside one system
needs only that system's `CLAUDE.md` (the root `CLAUDE.md`, "Where things are written
down", says which document holds what). Section 0 is kept current by the task that
changes what the game does; the numbered sections after it are the design of each
pipeline and are revised when the design changes.

---

## 0. The game today, system by system

A third-person survival shooter in a generated forest, single player or as a client of a
dedicated server from one code path, chosen on the title menu. The player moves by Epic's
motion matching; zombies and wendigos hunt them. Each paragraph names the package whose
`CLAUDE.md` holds the rules and the files.

**The player** (`Scripts/combat/CLAUDE.md`; the body: `Scripts/asset_pipeline/CLAUDE.md`).
A Meshy-generated adventurer (`SKM_Adventurer03`, one setting in `asset_pipeline/player_body.py`)
issued a shotgun, pistol, knife, axe, matches and a stick; the SMG, assault rifle and sniper
are found as drops (Fab models; the shotgun and pistol are Quaternius CC0). Movement is the
Game Animation Sample's motion matching on a hidden UEFN mannequin, nothing hand-animated;
the sprint, prone, aim-walk, slide and stamina are the C++ movement component's, predicted
on the owning client and decided by the server (`Source/CLAUDE.md`). The player jogs at
4 m/s and sprints at 6 (forwards only), aims over the shoulder or down a gun's sights, holds
breath down the sights, reloads, eats, blocks, punches, stabs with the knife, chops with the
axe (every third blow on a tree leaves wood), lights a campfire with matches and wood,
lights the stick at a fire and holds it out as a torch, heats a blade at a fire (cauterises a
bleed, double damage to a wendigo for 20 s), crouches, goes prone, slides, mantles the
sample's traversal blocks, throws whatever is in hand (a thrown knife or axe wounds, stays
in the body or a tree, and is taken back with E), and interacts with the nearest thing in
reach. Items lying near the player glimmer. Each gun has its own accuracy cloud, recoil and
sway, steadied by stance and the aim; a headshot draws an X round the reticle. Bodies are
hit only where their fitted physics bodies are.

**The inventory** (`Scripts/combat/CLAUDE.md`, "The slots"; the panel:
`Scripts/graphics_menu/CLAUDE.md`, `Scripts/clothing/CLAUDE.md`). The hand, four weapon
slots (primary, secondary, pistol, melee; 1-4) and a ten-slot backpack (5-9, Q cycles it).
I opens the panel: keys or mouse bring an item to hand, a right click uses it (a garment is
worn, a gun goes to a weapon slot; on the hand's slot, or with the use key, what is in hand
is eaten, drunk or struck), drag moves items between slots, and a drop outside the
panel sets the item down. The character's portrait beside it is the player in the jacket,
pants and boots they wear. A pick-up goes to a free weapon slot of its kind, else the bag,
else empty hands.

**The wanderers** (`Scripts/npc/CLAUDE.md`). Ten zombies and wendigos on Behavior Trees:
patrol until they notice a player, then chase and melee, sidestepping between swings. Each
hunts one player, chosen among the living ones near it and kept until they die or leave,
then the nearest; its AI runs on the server alone and its sounds and clips reach every
machine by Multicast. What it hears is a list of recent noises the server keeps, one per
maker, so players firing far apart each draw the wanderers near them, and a wanderer that
hears a noise hunts whoever made it. A
burning campfire draws patrolling zombies within 200 m. A wendigo hunts before it chases:
roars, comes in tree to tree round the player, charges from 10 m, charges at once if the
player runs 30 m or shoots it; fire held out keeps it circling and eventually drives it off
for a while; its blow has a 33% chance of a 3-minute bleed. In single player a killed wanderer is replaced
10 s later, 75-100 m away; on a server the count is a budget instead (M29): each player has up
to the level's count of each creature near them, sent in 75-100 m away where no player is
looking, taken out when no player is within 200 m, under a cap for the whole server
(`Scripts/npc/CLAUDE.md`, "Population by mode"). Either way a dead one leaves a ragdoll corpse that can be looted (`Scripts/loot/CLAUDE.md`:
loot tables, Tab kneels and opens the loot window).

**The HUD and the one menu** (`Scripts/graphics_menu/CLAUDE.md`). UMG screens on an `AHUD`:
the five bars (HP, stamina, hunger, thirst, temperature), kill counters, an FPS readout,
the inventory grid, the menu, the death menu and the settings page, all keyboard and mouse.
The game opens on a title level of its own (`Lvl_Title`, `Scripts/title`: a lit stage with
the player's character in the saved profile's garments, empty-handed); M opens the same menu in play. Its
rows: Single Player (New Game / Continue Game opens `Lvl_Forest_1000m`), Multiplayer (a
server address and Join Server), Controls (rebinding, difficulty EASY/MEDIUM/SURVIVOR),
Debug, Dev All Guns, the GUN / MONSTER / PLAYER / SOUND / WORLD / GRAPHICS SETTINGS tabs
(live tuning, each saved to a tracked CSV the matching build reads), and Exit Game on the
title or Save and Exit in play (a 15 s countdown, cancelled by a hit, a move or the
trigger; saves stats, inventory and worn garments, not the location; death deletes the
profile). Pausing is single player's alone; as a client of a server the same screens are
overlays over a running world. Every screen carries Ellivian Inc.'s confidentiality
watermark.

**Clothing** (`Scripts/clothing/CLAUDE.md`). Eight garments, one slot each, shown as icons
bottom right; the jacket, pants and boots are drawn on the body (to everyone on a server),
the rest are not. A fresh player starts in the pants, worn, on the title and in play.
**Item icons** (`Scripts/item_icons/CLAUDE.md`) are studio renders of each
item's own model, made outside the editor by `build_item_icons.py`.

**Sound** (`Scripts/Sound/CLAUDE.md`). Every sound is a recording chosen by ear; one
package with a table per area (weapons, monsters, items, world) and one build after any
change. The forest has day and night beds faded by the clock.

**The world** (`Scripts/world/CLAUDE.md`, `Scripts/forest_generator/CLAUDE.md`). Two
generated maps, `Lvl_Forest_200m` (the editor's startup map) and `Lvl_Forest_1000m` (what a
packaged game plays). A clock turns the sun and moon; day and night are 4 minutes each for
now, the night moonlit under the real stars, and a level starts at a random hour. The clock
has one owner: the server's (single player's own), which every client's sky and wind follow
through the GameState (`Scripts/net/CLAUDE.md`, "One world clock"). At night
the player's temperature falls; a campfire warms them. Grass and trees sway in a wind the
graphics tab tunes. What players leave in the world (items set down or thrown, a blade in
a tree, cut wood, bodies, fires) is there for whoever joins a server later, and on a server
each kind has a lifetime and a cap so a long-running world does not fill up; single player
keeps what is left until it is taken (`Scripts/net/CLAUDE.md`, "Things left in the world").

**Death** (`Scripts/combat/docs/health.md`, `Scripts/net/CLAUDE.md`). Nothing a dead body
could do runs. In single player death ends the game: the world pauses on the death menu and
the profile is deleted. As a client of a server the player's gear goes onto the body, which
anyone can loot, and the server respawns them 10 s later at a random PlayerStart. Players
can hurt players; a player kill is counted apart from monster kills.

**Known gaps.** A low temperature does nothing yet. Traversal has nothing to climb (no
traversable block is placed in either map) and is unproven as a client of a server. The
guns' ready poses and the weapon layers' clips are retargeted from Lyra, Mixamo and
Quaternius, none played by hand. Each package's `CLAUDE.md` lists the feel checks that
still need a play session.

---

## 1. Project shape

```
Otherworld/
├── Otherworld.uproject        # UE 5.8; plugins below
├── CLAUDE.md                  # agent rules; "Where things are written down" lists the documents
├── systemDesign.md            # this file
├── Config/                    # *.ini
├── Content/                   # game assets (binary)
├── Scripts/                   # external automation, run via UnrealEditor-Cmd
└── Saved/ Intermediate/ DerivedDataCache/   # gitignored
```

The enabled plugins are listed in `Otherworld.uproject`. The ones that shape the game:
`PythonScriptPlugin` and `EditorScriptingUtilities` (everything is authored from Python),
`UMGToolSet` (widget layouts from Python), `GameplayAbilities` (survival), `PoseSearch`,
`Chooser`, `MotionWarping` and `AnimationLocomotionLibrary` (the Game Animation Sample's
motion matching), the `MetaHuman*` family (the player's body) and `ReplicationGraph`
(multiplayer). The editor-only ones (`ModelingToolsEditorMode`, `PCG`, `ProceduralMeshComponent`)
serve the forest generator.

The C++ in `Source/` is small and deliberate: the `Otherworld` runtime module (the player's
predicted movement, the hit history, the weapon and health components' native parents) and
the editor-only `OtherworldEditor` module of helpers the builders need (`Source/CLAUDE.md`);
the game itself is Blueprint authored from Python. It started from the
Third Person template (`Content/ThirdPerson`, `Content/Characters/Mannequins`,
`Content/Input`, `Content/LevelPrototyping`), and "largely untouched" turns out to be
measurable: of those 171 files, **168 are byte-identical to the UE 5.8.3 install** and three
are patched in place by builders — `ABP_Unarmed`, `BP_ThirdPersonCharacter` and
`BP_ThirdPersonGameMode`.

That is why the scripts are the source. `Content/` is committed as a Git LFS snapshot so a
clone opens without a rebuild, but every asset in it is either stock engine content or
written by a script in `Scripts/`, and a rebuilt asset is committed like any other change
(the rules: root `CLAUDE.md`, "`Content/` is a Git LFS snapshot").
`Scripts/forest_generator/asset_sources.py` is the table of which is which,
`Scripts/sync_assets.py` the tool that acts on it, and `assets/` (git-ignored) holds
downloads and generator scratch. Verified 2026-09-27 by deleting the four stock directories
and rebuilding: 356/356 weapons, 60/60 HUD, 148/148 level.

### Content layout that matters

| Path | Contents |
|---|---|
| `Content/Maps/` | the generated forests `Lvl_Forest_200m` (the editor's startup map) and `Lvl_Forest_1000m` (`GameDefaultMap`); `Lvl_Title` (the stage the game opens on, `Scripts/title`); the probe levels `Lvl_Probe_50m`, `Lvl_NavProbe`, `Lvl_NPCProbe`; `Lvl_Forest` (the retired template-era level) |
| `Content/Forest/` | the generator's assets: master materials and their instances (`Materials/`, including the night-sky dome), the downloaded photoscan kits (`Scanned/`: trees, ferns, grass, moss, shrubs, rocks, stumps), the terrain import target (`Test/`), the wanderers (`NPC/`) |
| `Content/Weapons`, `Content/UI`, `Content/GAS`, `Content/MetaHumans`, `Content/Fab`, `/Game/<Pack>` | the builders' output, system by system (`Scripts/forest_generator/asset_sources.py` maps every directory to what produces it); the Game Animation Sample copy; the player's MetaHuman; Fab packs the user acquired |
| `Content/Python/` | `init_unreal.py` (starts the inbox), `uepy_inbox.py` (the transport `uepy.py` uses), `generate_forest_level.py` (an older template-based builder, **not** the current generator) |
| `Content/ThirdPerson/` | template content, byte-identical to the install but for the three patched files above |

---

## 2. Automation model

Two execution contexts, and they must not be confused:

**A. Pure Python (host interpreter).** `Scripts/generate_forest_level.py` and the
`Scripts/forest_generator/` package. No `unreal` import, so it runs instantly, is unit-testable,
and does all math/verification offline.

**B. Unreal Python (in-editor interpreter).** Everything that touches assets: the builders
and verifiers in `Scripts/`, and the **generated** scripts under
`Scripts/generated_levels/<Level>/`. They run through `Scripts/dev/uepy.py`, which hands the
script to an already-open editor through the inbox (`Content/Python/uepy_inbox.py`) and
cold-boots `UnrealEditor-Cmd -ExecutePythonScript` only when none is listening (root
`CLAUDE.md`, "Run a script"). Behaviour in the running game is checked by probes, scripts
run inside a headless `-game` or `--net` launch (`Scripts/probes`, `docs/headless_runs.md`).

Subsystems used throughout: `EditorAssetSubsystem`, `EditorActorSubsystem`,
`LevelEditorSubsystem`, `AssetToolsHelpers.get_asset_tools()`, `MaterialEditingLibrary`,
and `BlueprintGraphEditor` behind `Scripts/uebp`, the one graph-authoring library.

**C. The build order.** Each system is one `build_<system>.py` over a package, each with a
`verify_<system>.py` that mirrors it (root `CLAUDE.md`, "Code layout"). Some builds depend
on another's assets: the NPC build after the survival build (it names `GE_Bleeding`), the
menu build after the weapons build (it bakes the gun tuning table), the day/night, forage
and clothing builds after a level import (which rebuilds the level from scratch). Each
package's `CLAUDE.md` states its order.

---

## 3. Level generator pipeline

Entry point: `Scripts/generate_forest_level.py` (over budget at 1.8k lines, half of which
are the two embedded script templates; split before extending).

```
CLI ──► terrain.generate_terrain_obj ──► tree_placement.scatter_trees
     ──► grass_placement.scatter_grass ──► bush_placement (thickets, no collision)
     ──► npc_placement.place_npc (the pack)
     ──► verification.run_all_checks (offline; exits 1 on failure)
     ──► verification_report.json
     ──► emit grass_<Level>.json  (instance transforms, read at import time)
     ──► emit import_<Level>.py   (build the level in-editor)
     ──► emit verify_<Level>.py   (in-editor assertions over the saved level)
     ──► print the two commands
```

The flags, with their defaults, are the header of `Scripts/forest_generator/CLAUDE.md`:
`--size` (required), `--name`, `--seed`, `--grid`, `--time-of-day` (night by default),
`--tree-density`, `--grass-density`, `--grass-height`, `--grass-patchiness`,
`--bush-clusters`, `--no-grass`, `--no-bushes`, `--no-npc`, `--npc-count`,
`--npc-min-distance`, `--npc-max-distance`, `--json-report`.

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

Past 200 m the terrain is a different shape (`_make_large_elevation_fn`): the radial bowl's
corners would outgrow the navmesh's Z limit, so larger maps use low hills faded in over a
40 m ring and a box-distance rim (`Scripts/forest_generator/CLAUDE.md`, "The two maps").

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

**Bushes** (`bush_placement.py`) are a third layer: loose clusters of one to four on a coarse
jittered grid with most cells left empty, so the floor alternates between open grass and
thickets. They never block (planted with no collision), and the player's or a wanderer's
passage through one is heard as a rustle (`Scripts/Sound/CLAUDE.md`).

### 3.2c NPC placement — `forest_generator/npc_placement.py`

A pack of wanderers (`--npc-count`, ten by default) spawned in a band round the PlayerStart
(`--npc-min-distance` / `--npc-max-distance`, 75–100 m), each a zombie or a wendigo
(`forest_generator/npc_placement.py` holds every movement, melee and spawn-band number).

**Each spawn point** is rejection sampled (up to 400 attempts) against four constraints:
inside the band; at least 220 cm clear of any trunk; inside 88 % of the half-extent; and —
preferred rather than required — with at least one tree straddling the straight line to the
player, so the detour behaviour is exercised. Candidates are drawn uniformly *by area* over
the annulus (`sqrt` on the radius) so they do not bunch toward the centre. The first
obstructed candidate wins; if none is found the best legal candidate is used and the check
reports the clear line instead of failing. Seeded `seed ^ 0x4E7C`, so it is decorrelated from
trees and grass. Z is `terrain_z + 88 cm` (the stock Character capsule half-height) and yaw
faces the player.

Trunk radius is approximated as `15 cm × tree scale` — a proxy used only for spawn clearance
and the line-of-sight test, never for collision, which comes from the real mesh.

### 3.2d NPC Blueprints — `Scripts/build_npc_blueprints.py`

The wanderers depend on nothing per level, so they are their own idempotent build over the
`Scripts/npc` package, run after `build_survival.py`; the generated import script only
places the pack. Each creature (zombie, wendigo) is a `BP_ForestWanderer` character driven
by its own `AIController` Blueprint whose brain is a Behavior Tree of step tasks: patrol
until a sense fires, then chase and swing, the wendigo's hunt and its fear of fire, the
zombie drawn to a campfire, the corpse. Every tunable number (senses, patrol, speeds,
melee, health, the hunt, the fire) is a `Tune*` variable on the controller defaulted from
`Scripts/npc/monster_tuning.csv`, so the MONSTER SETTINGS tab can change it live; the rest
are literals from `forest_generator/npc_*.py`, which import no `unreal` so the offline
generator checks what gets built. The design, the tree, each step and its verifier:
`Scripts/npc/CLAUDE.md`.

### 3.2e Navigation

The import script spawns a `NavMeshBoundsVolume` sized by `npc_placement.compute_nav_bounds`
plus a `RecastNavMesh`. Two rules carry the whole feature, and breaking either is silent:

- **The level must not contain saved nav data.** A headless editor never finishes an async
  navmesh bake, so a `RecastNavMesh` saved from a script carries *empty* tiles that the game
  reuses instead of building: 0 tiles, every move `Failed`, the pack stands still. The
  import script destroys every `RecastNavMesh` as its last action before the save, runtime
  generation is `Dynamic` (set in the level and as a class default in `DefaultEngine.ini`,
  because the nav system overwrites per-actor values on registration), and every later save
  goes through `world/level_save.py`, which strips it again. It is not assertable from the
  editor, which always materialises a nav actor on open; `Scripts/dev/check_saved_navmesh.py`
  reads the maps on disk.
- **Recast builds nothing if the volume is too tall.** No warning, no `LogRecast` line; the
  limit is in Z alone, measured one dial at a time by resizing the volume, rebuilding and
  projecting points at the result:

  | Volume | Result |
  |---|---|
  | ±10000 cm XY, 8000 cm Z span | **0 tiles** |
  | ±8500 cm XY, 1500 cm Z span | 176 tiles |
  | ±8500 cm XY, 1479 cm Z span | 324 tiles |
  | ±10000 cm XY, 4586 cm Z span | the navmesh reaches the terrain edge on all 48 sampled headings |

  So `compute_nav_bounds` sizes Z from the terrain's real elevation band (the box sampled,
  corners included) plus headroom above the agent height, `NAV_MAX_VERTICAL_SPAN_CM` (5000)
  sits at the measured-good point, and `NAV_COVERAGE_FRACTION` is 1.0: the volume covers the
  whole terrain, so the pack follows to its edge. The limits are empirical: UE 5.8 exposes
  neither `tile_size_uu` nor a readable tile limit to Python.

The nav system also replaces `agent_radius`/`agent_height` with its default agent
(35 cm / 144 cm) on registration, so the constants match those defaults; widening the inset
round trunks means Project Settings → Navigation System → Supported Agents. On the 1 km map
tiles build nearest-first at game start: the spawn band in about 8 s, the whole map in about
2 min. The editor's and PIE's own traps, and how to measure a navmesh:
`Scripts/forest_generator/CLAUDE.md`, "Navmesh".

### 3.2f Patrol, senses and noise (agro)

A wanderer has two states, held in one `Aggro` bool on its controller: it spawns
**patrolling** (every respawn too, since each spawn gets a fresh controller) and switches to
**aggro** when a sense detects the player. The senses are a chain of exec branches in the
controller's heartbeat, not one boolean OR, so the cheap ones (hurt, touch) run before the
visibility trace and the noise read, and the one that fired is reported:

| sense | condition |
|---|---|
| hurt | the health component's `DamagedByPlayer` (the flag the kill count trusts) |
| sight | within the creature's vision range and half-angle, with line of sight from the pawn's eyes (trunks block it) |
| touch | within touch range, from any direction |
| sound | a noise of the list below, heard; the wanderer hunts its maker |

The ranges, the patrol radius and speed and the re-pick times are per creature in
`monster_tuning.csv` (3.2d). The patrol step picks a random reachable point round
`PatrolHome` with a pure navigation query read once into a variable, and guards the result
by distance, because on failure the query returns its origin. `Scripts/npc/CLAUDE.md`,
"Patrol and agro", has the graph and its verifier.

**Sound is a short list of recent noises, one per maker, kept by the server (M28).** The
emitters (the weapon component's shot, the footstep component) and the listeners (every
controller) share no reference, so a noise is published on the world: a native world
subsystem, `UOtherworldNoiseList` (`Source/Otherworld`, `OtherworldNoise.h`), behind two
nodes, `MakeNoise` (`combat/noise.py`) and `HearNoise` (`npc/senses.py`). An entry is who
made it, its time, location, all-round reach, and for a gunshot a cone (direction, reach,
cosine of the half-angle). It is written only where the world has a GameMode (the server, or
a single-player game); on a client the node does nothing. With `loud(x) = max(reach, cone
reach)`, a maker's noise replaces **that maker's** entry iff the entry is older than
`noise_hold_s` (0.6 s) or the new noise is at least as loud; the hold keeps a footstep from
erasing its maker's gunshot before every wanderer has had a heartbeat (0.5 s) to check it,
and the combat verifier asserts that inequality. Another maker's noise lands beside it, so
two players firing at once are two entries; entries past the hold are dropped at each write
(128 at most). A listener hears the **nearest** entry that is recent and whose all-round
reach or cone holds it, both scaled by its own `hearing_scale`, and is told who made it: the
sound sense sets the wanderer's `Target` to that player. A gunshot's reach is the weapon's
`ShotVolume` (the GUN SETTINGS tab's row); a footstep's scales with speed and is written for
players only.

Limits by design: there is no way back to patrol (a "calm" would be a branch on the aggro
arm); one maker's entry keeps only the louder of its two simultaneous noises; sound ignores occlusion
while sight does not; one wanderer going aggro does not alert its neighbours. Since then the
wendigo's hunt and the campfire's draw were added on the same heartbeat
(`Scripts/npc/CLAUDE.md`), and the queued N1/N2 tasks move sight and hearing onto AI
Perception.

### 3.3 Offline verification — `forest_generator/verification.py`

`run_all_checks` → `VerificationReport` (`CheckResult` list, `summary`, `all_passed`,
`to_json`). Every check must pass before any editor work happens (the bush checks are
`undergrowth_checks.py`):

- **Terrain:** OBJ validity, bounds ±5 %, flat spawn zone, upward normals,
  barycentric consistency.
- **Trees:** count sanity, in-bounds, not floating, not buried, vertical, spacing (a
  spatial hash with redraws keeps trunks ≥ `MIN_TREE_SPACING_CM` apart), spawn-zone clear.
- **Grass (skipped under `--no-grass`):** density within 70–105 % of the request;
  in-bounds; seated on the mesh (terrain Z re-derived for a 500-clump sample and compared
  against the recorded value and the sink); knee height (the knee layer must average inside
  ±30 % of the target and no clump may exceed 1.6×); upscale factor ≤ 2.4×; coverage —
  every cell of a 12×12 grid over the map contains grass, which is what "throughout the
  level" actually means; species spread.
- **NPCs (skipped under `--no-npc`):** each placed; inside the spawn band and the usable
  bounds; clear of trunks; grounded (capsule centre exactly one half-height above the
  re-derived terrain Z); and route-obstructed — reports whether a tree blocks the direct
  line. That last one passes either way by design, since a clear line can be legitimate on a
  sparse map, but it tells you whether the detour behaviour is being exercised. Plus `Nav
  Bounds Sane` (vertical span within the measured envelope) and `NPC Inside Nav Bounds` (the
  capsule's *feet* — pathfinding queries feet, not centre — lie inside the volume, and nav
  coverage is not narrower than the spawn band).

### 3.4 Generated import script

`_write_unreal_import_script` emits, in order:

1. **Import OBJ** → `/Game/Forest/Test/SM_<Level>_Terrain` (`AssetImportTask`, replace+save);
   Nanite disabled, `collision_trace_flag = CTF_USE_COMPLEX_AS_SIMPLE`, `allow_cpu_access`,
   material `M_Forest_Ground_PBR`.
2. **Level** `/Game/Maps/<Level>` — load if it exists and destroy every actor whose label
   starts with the level name, `HISM_Tree` or `HISM_Grass` (idempotent re-generation),
   else `new_level`.
3. **Terrain actor** — `StaticMeshActor`, `BlockAll`, `QUERY_AND_PHYSICS`, static.
4. **Lighting & sky** — the static rig, fully driven by the embedded preset (§4); the
   day/night cycle that replaces it at runtime is `build_day_night.py`'s, run after the
   import, as are `place_forage.py` and `build_clothing.py`.
5. **Trees** — placements inlined as a `TREE_DATA` literal and handed to
   `forest_import/trees.py:plant_trees`, which plants **one HISM actor per species per
   100 m map cell** (`forest_generator/tree_cells.py`, the same cells as grass), labelled
   `<spec>__±ix_±iy`: `BlockAll`, static, shadow-casting, materials set by slot index. Each
   cell fades its trees out at 250–300 m (times `r.ViewDistanceScale`) and drops out whole
   past its max draw distance. Tree HISMs stay on Nanite (`disallow_nanite` pinned off):
   the meshes' auto-built fallbacks have no leaf triangles, so classic rendering draws
   bare trees. Past 60 m (`TREE_LEAF_MASK_DISTANCE_CM`, via `nanite_pixel_programmable_distance`)
   the leaves are drawn without their opacity mask, which is far cheaper on Nanite.
5b. **Grass** — transforms are *not* inlined (tens of thousands of them); the script reads
   `grass_<Level>.json`, whose instances are flat rounded arrays
   `[spec_idx, x, y, z, yaw, pitch, roll, height_mul, width_mul, target_h_cm]` against an
   interned spec-name table, and hands it to `forest_import/grass.py:plant_grass`. That
   plants **one HISM actor per species per 100 m map cell** (`forest_generator/grass_cells.py`;
   900 actors on the 1 km map, labelled `<spec>__±ix_±iy`, tagged `OW_Grass`) so whole cells
   drop out at the primitive level. Each cell is `NoCollision`, instance cull 6000–9000 cm,
   primitive max draw distance `GRASS_CELL_MAX_DRAW_CM` (sized so no cell vanishes before its
   own clumps fade even at Low's 0.4 view-distance scale), and saved **unlit** — no shadow,
   no distance-field or dynamic indirect lighting; the graphics presets switch
   those on at runtime per preset (`graphics_menu/presets.py`). Per species the mesh bounds are read once, then per instance
   `scale = (unit·width_mul, unit·width_mul, target_h / mesh_height)`. If bounds come back
   unusable it logs an error and falls back to scale 1.0 rather than emitting giant grass.
6. **PlayerStart** at `(0, 0, 100)`.
7. **Navigation + the pack** — `NavMeshBoundsVolume` scaled to the map, `RecastNavMesh` with
   `runtime_generation = DYNAMIC`, then each wanderer spawned at its computed transform
   (§3.2c–e; the Blueprints are the NPC build's, §3.2d).
8. Save, with the nav data stripped first (§3.2e).

All spawned actors are labelled `<LevelName>_<Role>` (`_Terrain`, `_Sun`/`_Moon`,
`_SkyAtmosphere`, `_SkySphere`, `_SkyLight`, `_Fog`, `_PostProcess`, `_PlayerStart`) —
that convention is what makes step 2's cleanup and the verify script's lookups work. The
NPC rig follows it too: `_NavBounds`, `_NavMesh`, and one label per wanderer.

### 3.5 Generated verify script

`_write_unreal_verify_script` emits a `check(name, condition, detail)` harness and its
assertions over the *saved* level: terrain actor/component/collision/Nanite/material, the
full lighting rig against the preset (§4), tree HISM counts per species, PlayerStart, and
per grass species — actor exists, instance count, `NoCollision`, and a **knee-height proof**:
50 instance transforms are sampled and `scale.z × mesh bounds height` must land inside the
min/max target height the offline pass recorded for that species. That last check is the one
that would catch a mis-scaled asset, since nothing offline can see the mesh.

The NPC block asserts the Blueprint assets exist and are wired (controller class, auto
possess, the mesh and anim class), that **each** placed wanderer is a `Character` at its
expected transform and inside the spawn band, and that the nav bounds cover the map and the
navmesh's `runtime_generation` is `DYNAMIC`. The nav block asserts the volume's XY and Z
extents and centre match what the generator computed, that the vertical span is inside the
measured envelope, and that every wanderer's feet sit inside the volume. The chase and the
melee are the level verifier's too (`Scripts/npc/CLAUDE.md`).
Prints `[VERIFY] ✅ ALL N CHECKS PASSED!` or a list of failures.

---

## 4. Time of day

Two layers, built by two scripts:

- **The generated level's static rig** comes from `forest_generator/lighting.py`:
  `TIME_OF_DAY_PRESETS` (`day`, `night`), plain dicts so they can be `json.dumps`'d into the
  generated import and verify scripts. A preset holds the sun or moon light (intensity,
  colour, pitch and yaw, shadow distance), the sky light, the dome material, the fog, the
  volumetric cloud switch and the exposure range. The verify script re-reads the same dict,
  so its lighting checks follow the preset rather than hard-coded values. To add a preset,
  add a dict with the same keys. The night preset's dome is a project-owned unlit `is_sky`
  material (the engine's sky domes expose no star parameters), whose emissive the real-time
  SkyLight captures: the sky itself is the night's ambient light.
- **The day/night cycle** (`Scripts/build_day_night.py`, `Scripts/world`) is what the game
  plays: a clock that turns a Movable sun and moon across the sky, a real-time SkyLight, one
  opaque dome whose material draws the day gradient, the sunset, the discs and the real
  stars (the Yale Bright Star Catalogue from 45° north), the fog and two post-process
  grades. At BeginPlay it destroys the static rig, which the builder only tags; the level's
  verifier still checks the generated rig, and a level without a cycle still plays at
  night. Day and night lengths and the night's cold are `world_tuning.csv`'s. Re-run the
  build after any level import, which rebuilds the level from scratch.
  `Scripts/world/CLAUDE.md` has the design and the numbers.

---

## 5. The run loop: where the game's state lives

The combat, survival, inventory and menu systems are built onto assets every generated
level picks up through `BP_ThirdPersonGameMode` (the global default game mode, whose HUD
class is the menu's). The level generator knows nothing of them. Their design is in the
packages (`Scripts/combat/CLAUDE.md` and its `docs/`: aiming, stance, health, the firing
gate; `Scripts/survival`, `Scripts/loot`, `Scripts/graphics_menu`); the shot, the reload,
health and death, and the player's movement states are C++ (`Source/CLAUDE.md`). What
belongs here is the one cross-cutting rule.

**State lives where every machine that needs it can read it**, because the game is one code
path for single player and for a client of a dedicated server, and a client has no GameMode
(`serversupportsysdesign.md` 4.2; the full table and the three questions to ask of any new
variable: `Scripts/net/CLAUDE.md`, "Where state lives"). Blueprints have no statics, and
each of these outlives every actor that touches it, the player's own components included:

| variable | on | written by | read by |
|---|---|---|---|
| `NpcSpawnCount` | the GameMode (server only) | each wanderer's `BeginPlay` | the next wanderer, for its number |
| the wanderer population (a server's only) | `UOtherworldPopulation`, a world subsystem that does nothing in single player | each AI controller on possession (`RegisterWanderer`, with its creature's budget) | its own pass, once a second: who is removed, who is spawned |
| the noise list | `UOtherworldNoiseList`, a world subsystem (written on the server only) | whatever made a noise (`MakeNoise`) | every controller's hearing (`HearNoise`) |
| `NpcKillCount`, `PlayerKillCount`, `PlayerDead` | `BP_OtherworldPlayerState`, replicated | the death path on the server, a kill credited only when `DamagedByPlayer` or the striker was a player | that player's HUD and death menu |
| `DebugMode` | `BP_OtherworldGameState`, replicated | the HUD's BeginPlay and the menu's debug row, where the machine owns the GameState | the weapon component (tracers), the HUD, the wanderers' AI (cones) |

Health is the value a cheater most wants, so only the server changes it and every blow says
who struck it (`TakeHit` on the health component's native parent; its `Health` and `Dead`
replicate with notify). `DamagedByPlayer` is the load-bearing stamp: the world-floor net
under the map writes `Health = 0` and lets the ordinary death path run, so without it every
wanderer the terrain lost would score. A weapon is a droppable actor, so its ammunition
(`Loaded`, `Reserve`, the magazine, the intervals) lives on `BP_WeaponItem` and a half-empty
gun left on the ground is still half empty when picked up; nothing in any graph branches on a
weapon's name, and every per-weapon number is a row of `gun_tuning.csv`.

---

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
- **A broken navmesh hides as a speed bug.** With no navmesh, path following sets velocity
  directly, which bypasses `MaxWalkSpeed` and leaves `GetCurrentAcceleration()` at zero
  (a configured 110 cm/s measured 192, and `ABP_Unarmed`'s `ShouldMove` held the idle
  pose). With tiles building, the move is acceleration-driven and measures as configured.
  Grep a `-game` log for `Building tile` before tuning any speed.
- **In-place Blueprint updates keep old values.** The builders update assets in place
  (deleting fails while the level or another Blueprint references them), so every property
  must be set explicitly: removing a line from a builder no longer reverts it.
