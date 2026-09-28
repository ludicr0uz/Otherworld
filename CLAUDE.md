# Otherworld — Claude quick reference

Unreal Engine **5.8** project on macOS. Everything is driven by **Unreal Python** automation;
there is no C++ module. See `systemDesign.md` for the detailed architecture.

## Hard rules

1. **Never** open or edit `.uasset` / `.umap` as text. All asset work goes through the
   `unreal` Python API (or the editor UI).
2. Automation scripts live in `Scripts/` (run headless), `Scripts/dev/` (tooling for driving
   the editor, not content) or `Content/Python/` (auto-discovered by the editor;
   `init_unreal.py` runs at startup and starts `uepy_inbox`).
3. Asset prefixes: `SM_ SK_ M_ MI_ T_ BP_ WBP_ ST_ A_ Cue_`; levels `Lvl_`.
4. Absolute paths only when invoking the editor directly — the Bash tool resets cwd between
   calls. (`Scripts/dev/uepy.py` resolves its own arguments, so relative paths are fine there.)

## The repository is code only — a fresh clone has no Content/

Nothing under `Content/` is committed except `Content/Python`. A clone gives you the
`.uproject`, the scripts, the config and the docs; the ~1 GB of assets is rebuilt locally.
This is deliberate: every `.uasset` in the project is either stock engine content or
written by a script, so committing them stores a derived artefact that a Blueprint
recompile changes the bytes of on every build.

```bash
python3 Scripts/sync_assets.py --status         # what is present, what is missing
python3 Scripts/sync_assets.py --plan           # the full from-nothing order
python3 Scripts/sync_assets.py --restore-stock  # copy the engine's template assets in
python3 Scripts/sync_assets.py --verify         # checksum them against what was recorded
```

`Scripts/forest_generator/asset_sources.py` is the table that makes this work: for every
directory under `Content/` it names the one thing that produces it. Three kinds —

| kind | restored by | verified by |
|---|---|---|
| **stock** — 171 files, 126 MB, ships with UE 5.8 | `sync_assets.py --restore-stock` | sha256, in `stock_checksums.json` |
| **generated** — everything else under `Content/` | the builder named in the table | the verifier suite, 564 checks |
| **cache** — downloads, in git-ignored `assets/` | `fetch_weapon_sounds.py` | the fetcher's own cached-file report |

**Three stock files are patched in place by builders** and so belong to both kinds:
`ABP_Unarmed` (the LayeredBoneBlend that keeps `DefaultSlot` on the upper body),
`BP_ThirdPersonCharacter` and `BP_ThirdPersonGameMode`. They are *restored* by copying the
engine's copy and *verified* by the suite, never by checksum — a Blueprint recompile is not
byte-deterministic, so two correct builds of the same graph differ by hundreds of bytes.
`--verify` excludes them by name and says so.

**Everything that is not code lives in `assets/`, which is git-ignored:** `assets/cache/sounds`
(300 MB of CC0 firearm recordings), `assets/cache/scanned` (2.3 GB of scanned meshes and
textures), `assets/generated` and `assets/generated_realistic` (generator scratch). Never
commit an archive — GitHub hard-rejects any file over 100 MB, and the 185 MB `firearm_library.7z`
in `assets/cache/sounds` is exactly the file that would trip it.

**A fresh clone must arm the guard**, because `core.hooksPath` is local config and does not
travel with the repository:

```bash
git config core.hooksPath Scripts/dev/hooks
```

`Scripts/dev/hooks/pre-commit` refuses any staged file over 5 MB or carrying a content
extension (`.uasset .umap .7z .zip .wav .fbx .png …`). `git commit --no-verify` overrides it.

Proved end to end on 2026-09-27: the four stock directories were deleted, re-copied from
UE 5.8.3 and rebuilt, and the suite came back **356/356 weapons, 60/60 HUD, 148/148 level**.

## Run a script — fast

**Default to `Scripts/dev/uepy.py`.** A cold `UnrealEditor-Cmd` costs **35-45 s of boot and
shutdown no matter what the script does** — a script that dies on line 13 still burns ~33 s.
That overhead, not the work, is what makes iteration slow: a session with 18 launches spends
ten minutes booting. `uepy.py` sends the script to an **editor that is already open** over the
Python plugin's remote-execution channel (~1 s), and cold-boots only when nothing is listening,
so the same command works either way.

```bash
python3 Scripts/dev/uepy.py Scripts/build_npc_blueprints.py
python3 Scripts/dev/uepy.py Scripts/verify_weapons_and_combat.py Scripts/verify_graphics_menu.py
python3 Scripts/dev/uepy.py -c "import unreal; unreal.log_warning('hi')"
python3 Scripts/dev/uepy.py --list          # which editors are listening?
python3 Scripts/dev/uepy.py --game --seconds 25   # headless -game run + error summary
python3 Scripts/dev/uepy.py --cold <script> # force a fresh editor
```
Several targets in one invocation share **one** connection or **one** boot — three verifiers
cost one boot, not three. Exit code is non-zero if any target raised. `--game` kills the run on
a timer and counts `Blueprint Runtime Error` / `Accessed None` / `NPC-SPAWN` / `NPC-FELL` for you.

`--project <path>` points it at another project. Do not push asset builders while PIE is
running — recompiling a Blueprint under the running game leaves you observing neither build;
`uepy.py` detects PIE and refuses unless given `--allow-pie`.

#### Two transports, and why there are two

`uepy.py` tries, in order: **the inbox**, then **multicast remote execution**, then a cold boot.

1. **The inbox** (`Content/Python/uepy_inbox.py`, started from `init_unreal.py`) is a
   request/result directory under `Saved/uepy/` that the editor polls on its Slate tick. No
   network, no permissions. **This is the transport that works on this machine**: measured
   round trip **0.24 s**, against 22-45 s for a cold boot. It captures `print()` *and*
   `unreal.log_warning` (by wrapping `unreal.log*` for the duration of the job — the Python API
   exposes the log *directory* but not the log *filename*, so tailing the log file silently
   captures nothing when the editor was started with `-abslog`).
2. **The engine's own remote execution** is tried next. It needs a UI editor (a `-NoUI`
   commandlet never registers) and `bRemoteExecution=True` under
   `[/Script/PythonScriptPlugin.PythonScriptPluginSettings]`, read at startup. **It cannot work
   on this machine**: discovery is UDP multicast on 239.0.0.1:6766, and multicast is not
   delivered here even to a listener in the same process tree — proven with a plain Python
   sender/receiver pair, no Unreal involved, on both `lo0` and `en0`. macOS Local Network
   privacy drops it silently; the editor's socket is bound (`lsof -iUDP:6766` confirms) and
   ticking, and never hears a ping. Granting Terminal and Unreal Editor "Local Network" access
   in System Settings → Privacy & Security may revive it; the inbox does not care either way.

**Activating the inbox in an editor that is already open** (it loads at startup, so an editor
started before this existed has no inbox): in the editor's Output Log, switch the command box to
*Python* and run `import uepy_inbox; uepy_inbox.start()`. A restart does it automatically.
The module can be hot-reloaded without restarting:
`import importlib, uepy_inbox; uepy_inbox.stop(); importlib.reload(uepy_inbox); uepy_inbox.start()`.

The raw form, still correct and what `uepy.py` falls back to:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" \
  "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Otherworld.uproject" \
  -ExecutePythonScript="<abs path to .py>" -NoUI -stdout
```
Logs from generated scripts are prefixed `[GEN]` (import) / `[VERIFY]` (checks).

### Cold runs while the editor is open — the staleness trap

A running editor **does not see** asset changes a cold `UnrealEditor-Cmd` writes to disk. There
is no filesystem watcher for packages: the `PackageReload` machinery in the engine is driven
only by source control (sync/revert), and the auto-reimport watcher covers *source* files
(fbx/png), never `.uasset`. So a cold run and an open editor silently diverge, three ways:

1. **You test the old build.** PIE spawns from the objects already in memory, so a playtest
   after a cold rebuild exercises the *previous* Blueprint. Conclusions drawn from it are
   worthless, and nothing in the log says so.
2. **The editor can overwrite the script's work.** It still holds the old package in memory. Any
   save that touches it — an autosave of a dirty package, Save All, a property nudge — writes
   that stale state back over the new bytes. The build is silently reverted.
3. **New assets are invisible** until the asset registry rescans
   (`AssetRegistry.scan_paths_synchronous`/`scan_modified_asset_files`).

**The fix is to not have two copies.** `uepy.py` with a live editor (via the inbox) executes
*inside that editor's own process*, so there is one authority for what the asset is and
divergence cannot happen. That is a correctness reason to prefer it, not just a speed one — and
the reason the inbox is worth having even though the engine ships its own remote execution.

If a cold run while the editor is open is unavoidable: afterwards, reload the packages in the
editor (`unreal.EditorLoadingAndSavingUtils.reload_packages([...])` — verified to exist;
`EditorAssetSubsystem.reload_asset` does **not**), or restart it. Make sure nothing is dirty
first: reloading discards in-memory changes, which is the point. Never cold-run a builder while
PIE is active.

### Iteration guidelines (what actually costs time)

1. **Never guess an engine API name across a boot.** A wrong guess (`break_pin_link` →
   `break_single_pin_link`, node title `"Is Valid"` → `"IsValid"`) costs a full launch per
   attempt. Dump the candidates **in the same script that uses them** — `dir(...)`, node titles,
   pin names — with a fallback, or read the engine source: `remote_execution.py` and the plugin
   headers under `Engine/Plugins/.../PythonScriptPlugin/Source` are on disk and free to grep.
2. **`print()` does not reach the headless log** — use `unreal.log_warning`. A discovery run
   whose output you cannot see is a wasted 40 s.
3. **Right-size `-game` runs.** Spawn-path bugs show in the first two seconds; 25 s is plenty.
   Only respawn *statistics* justify 90 s+.
4. **Scope verification to the blast radius.** AI-graph change → the level verifier. Run the
   full sweep (level + weapons + HUD) once before calling a session done, not per edit.
5. **Zero errors is not proof of a fix** when the fix is a guard: a gate that never opens looks
   identical in the log to a gate that works. Measure the positive case too (see the possession
   gate in *The NPCs*, proven with a 410-opens probe), then remove the probe by re-running the
   builder.
6. **Batch.** When a cold boot is unavoidable, put every script for that boot on one `uepy.py`
   command line.

## The level generator (the main thing here)

`Scripts/generate_forest_level.py` — pure Python, no `unreal` import. It computes terrain,
tree, grass and NPC placement, runs 27 offline checks, then **code-generates** two Unreal
Python scripts into `Scripts/generated_levels/<LevelName>/`.

```bash
python3 Scripts/generate_forest_level.py --size 200 --time-of-day night
# flags: --size <meters, required> --name --seed (42) --grid --time-of-day {night,day} (night)
#        --grass-density (1.2/m²) --grass-height (50 cm) --grass-patchiness (0.25)
#        --no-grass --no-npc --npc-count (10) --npc-min-distance (75 m)
#        --npc-max-distance (100 m) --json-report
```
Then run the printed `import_<Level>.py` (builds the level) and `verify_<Level>.py`
(141 in-engine checks) through UnrealEditor-Cmd. Generation is deterministic for a given seed.

Grass transforms do **not** live in the generated script — there are tens of thousands of
them, so they go to a gitignored `grass_<Level>.json` sidecar the import script reads.

Support package `Scripts/forest_generator/`: `terrain.py` (heightfield + OBJ),
`tree_placement.py` (`DEFAULT_TREE_SPECS`, scatter), `grass_placement.py`
(`DEFAULT_GRASS_SPECS`, stratified scatter), `npc_placement.py` (NPC spawn band +
**run speed / melee / nav agent constants**), `verification.py` (offline suite),
`lighting.py` (**time-of-day presets — edit here to tune day/night**).

## The NPCs

`Scripts/build_npc_blueprints.py` builds two Blueprints under `/Game/Forest/NPC` **from
Python** — no hand editing — and is idempotent, so re-generating a level reuses them. Every
number they use (run speed, melee, spawn band) lives in
`Scripts/forest_generator/npc_placement.py`, which imports no `unreal`, so the offline
generator and its checks read exactly what the editor builds.

- `BP_ForestWandererAI` (AIController). Event graph, authored via `unreal.BlueprintGraphEditor`:
  `BeginPlay → [possessed? no → Delay] → [both ends on the navmesh? yes → MoveToActor(Get
  Player Pawn) / no → MoveToLocation, no pathfinding] → [in reach and off cooldown? → swing]
  → Delay 0.5s → back to the gate`.
  `MoveToActor` does the pathfinding, which is what makes it run *around* trees; the
  straight-line branch beside it is the net described under **Following to the edge**. The melee check
  is spliced into that same loop rather than given a Tick of its own — the loop is already the
  NPC's heartbeat, and two of them can disagree about whether the chase is still running.
  The possession gate is load-bearing: a controller's `BeginPlay` runs **before** it possesses
  its pawn, so the first pass has none, and the melee chain's `GetActorLocation` then reads a
  location off None — one `Accessed None … CallFunc_K2_GetPawn_ReturnValue` runtime error per
  spawned NPC, reported against the swing `Branch`. It has to be an exec branch *ahead of*
  `MoveToActor`, not an extra `IsValid` in the melee `AND`: `BooleanAND` reads both its pins, so
  it would pull the location chain anyway (see the pure-node gotcha below). Closing the gate
  costs one `Delay` — possession has happened by the time the loop re-enters.
- `BP_ForestWanderer` (Character). Mirrors the **player's** rig exactly — `SKM_Quinn_Simple`
  + `ABP_Unarmed`, mesh at z −89 and yaw 270 — because that combination is known to animate.
  `use_acceleration_for_paths` **must be True**: with it False, `ApplyRequestedMove` sets
  velocity directly and leaves `Acceleration` at zero, and `ABP_Unarmed` gates on
  `GroundSpeed > threshold AND GetCurrentAcceleration() != 0` — so the NPC glides along in its
  idle pose. That is the cause of "moves but never animates"; the mesh/anim_mode dials are not.
  Auto-possessed by the controller above.

Run it standalone with `-ExecutePythonScript` to rebuild the assets after editing it. It
rebuilds the AI graph by default now (`rebuild=True`): the old "already authored — reusing"
guard meant no edit to the builder ever reached the asset once it existed.

### The pack: ten, running, at 75–100 m

| dial (`npc_placement.py`) | value | why |
|---|---|---|
| `NPC_COUNT` | 10 | one actor per spawn point, labelled `<Level>_NPC_Wanderer_<n>` |
| `NPC_RUN_SPEED_CMS` | 600 | UE's own default `MaxWalkSpeed` and the top of `ABP_Unarmed`'s blend space, so the legs jog rather than play a walk too fast. Measured: 75 m closed in ~15 s |
| `NPC_SPAWN_MIN/MAX_DISTANCE_CM` | 7500 / 10000 | far enough that the player never opens their eyes next to one |
| `NPC_MIN_SEPARATION_CM` | 600 | they all path to the same target, so a clump never unclumps |
| `NPC_ACCEPTANCE_RADIUS_CM` | 120 | **must stay below** `NPC_MELEE_RANGE_CM`, or the NPC parks outside its own reach and never lands a hit |
| `NPC_MELEE_RANGE_CM` | 200 | centre-to-centre between two 34 cm capsules ≈ an arm's length of air |
| `NPC_MELEE_DAMAGE` / `_INTERVAL_S` | 10 / 1.5 | balanced against the **pack**, not one attacker — see below |

The **spawn band is clamped**, and the clamp is loud rather than silent:
`npc_usable_radius` caps at 80 m on a 200 m map — `EDGE_MARGIN_FRACTION` (0.80), the same
margin the trees respect, so a wanderer never starts on the bare outer ramp — and so
`Lvl_Forest_200m` spawns its ten at **75.0–78.0 m**, and both the
generator's console output and the `NPC Spawn Band` check report the band they actually used.
`spawn_band()` is the only thing that decides it, so the check cannot drift from the placement.

**Balance is a property of the pack.** They spawn in one band and arrive within a few seconds
of each other, so one wanderer's numbers are very nearly multiplied by `NPC_COUNT`. Measured in
a `-game` run: 12 damage every 1.2 s was 50 dps for a pack of five and killed a 100 HP player in
**two seconds**, before a shot could be fired. 10 every 1.5 s is 6.7 dps each. This is the kind
of thing that cannot be read off the graph — it needed the running game.

**Raising `NPC_COUNT` to 10 doubled that**: ~67 dps, about a second and a half of standing
still. The melee numbers were **not** retuned to compensate — the pack is meant to be something
you run from, and sprint (900 cm/s against their 600) is the answer the player now has. If it
wants softening, `NPC_MELEE_DAMAGE` and `NPC_MELEE_INTERVAL_S` are the dials, and both are in
`npc_placement.py` where the checks read them.

**Respawns obey the band too, and land on walkable ground.** `BP_HealthComponent`'s death path
used to put a replacement within 40 m of where the dead one *started*; it now picks a random
bearing and distance in the same 75–100 m band **measured from the player's current location**.
Without that, "always 75–100 m away" held only until the first kill. The population stays at
ten with nothing tracking it.

That band point is a **request, never a spawn location**, and the difference is the bug that
dropped wanderers through the world:

1. the request is stored in `RespawnPoint` — it *must* be a variable, because
   `K2_ProjectPointToNavigation` is pure and re-evaluates per output pin read, so a request
   wired straight in would roll fresh random numbers for the `ReturnValue` branch and for the
   `ProjectedLocation` read, and project two different points;
2. it is projected onto the navmesh (`RESPAWN_PROJECT_EXTENT`, a 30 × 30 × 100 m search box —
   wide in XY so a point overshooting the navigable island snaps back to its edge, tall in Z
   because the request carries the *player's* height);
3. only the projected point is spawned at, lifted by the capsule half height (88 cm).

`RESPAWN_ATTEMPTS` (2) independent bearings are tried; only if both fail does it fall back to
any navigable point near the player, and if even that fails the dead wanderer is removed and
**not** replaced. Losing one of ten is visible and recoverable; a replacement under the terrain
is neither.

**And the navmesh Z is not the ground.** Recast voxelises the terrain and simplifies the result,
so its polygon can sit most of a capsule below the real surface — measured at up to 86 cm low,
which left 3% of respawns under-seated and 0.2% more than half buried. A capsule that starts
inside a thin one-sided terrain surface depenetrates *through* it, which is the "still falling
through" case. So the projected point's XY is kept and its **Z is re-derived by tracing onto the
actual collision geometry** (`RESPAWN_TRACE_UP`/`_DOWN`), then lifted by the capsule half height.
The trace starts only 2 m up on purpose: from far overhead it would hit a tree canopy and seat
the wanderer in the branches. The spawn also uses `AdjustIfPossibleButAlwaysSpawn`, so a capsule
clipping a trunk is nudged clear rather than left interpenetrating.

Measured over matched 80 s `-game` runs with a roaming player and heavy death rates (~1840
respawns each), against the generator's own heightfield:

| | worst clearance | half-buried | fell through |
|---|---|---|---|
| navmesh Z | 35.4 cm | 1 | 0 |
| traced Z | **51.3 cm** | **0** | 0 |

(88 cm = capsule seated exactly on the ground.) Nothing spawns outside the map: over 1847
samples the furthest was 8512 cm, well inside the ±10000 cm terrain. (That run predates the
full-map navmesh below, when 8500 cm was where the navmesh stopped.)

**And a net under all of it.** Any NPC below `WORLD_FLOOR_Z` (−1000 cm, well under the terrain's
−185 cm floor) is named in the log, written off as dead and replaced within a frame — verified
by teleporting wanderers to z = −5000 and watching 13 of them get caught and replaced. It is a
net, not the fix: "the capsule ended up inside geometry" has more causes than the one measured.

### Numbered wanderers, and the spawn log

Every wanderer takes the next number from a counter on `BP_ThirdPersonGameMode`
(`NpcSpawnCount`) as it spawns, stores it in its own `BP_HealthComponent.NpcId`, and writes one
line to the log. The HUD draws that same number beside the floating health bar, so anything seen
on screen can be looked up afterwards:

```
[NPC-SPAWN] #7 at X=8511.005 Y=-585.336 Z=753.045
[NPC-FELL] ERROR #2 fell to X=-0.178 Y=-0.322 Z=-5000.092 — spawned at X=4241.230 Y=6260.280 Z=526.093
```

The fall report carries **both** positions, and the spawn one is the half worth having: where it
fell to is always "somewhere under the map", while where it was put is the thing that has to be
explained. Both lines quote the same stored `SpawnedAt`, so they cannot disagree.

`SpawnedAt` is recorded for diagnosis only — respawn points are computed from the player, never
from it. (The old `SpawnOrigin`, which *did* anchor respawns to it, is gone on purpose.)

**Severity:** the fall report uses `PrintWarning`, because Blueprint cannot log at Error severity
at all — there is no `PrintStringWithSeverity` or `LogError` node, and a real `UE_LOG(…, Error)`
needs a C++ module this project does not have. Warning is the highest the Kismet library offers;
it colours the line in the Output Log and trips the editor's warning filter, and the literal
`ERROR` token in the text makes it greppable as one regardless. Both lines stay off the screen —
there they would cover the HUD they exist to explain. The log is at
`~/Library/Logs/Unreal Engine/OtherworldEditor/Otherworld.log`; `grep NPC-` it, or watch the
Output Log in the editor. The counter lives on the GameMode because Blueprints have no statics
and it must be one number per session, shared across every wanderer that ever exists; the HUD
reads each NPC's own copy, so it never needs telling that one died and another replaced it.

Note the ordering trap in how the number is taken: set `NpcId` **first**, then write the counter
back from the stored `NpcId`. The obvious order — bump the counter, then set `NpcId` from the
same `+1` node — numbers the first wanderer 2, because the add is pure and re-evaluates against
the already-bumped count. It is the same trap as the navmesh queries below.

### Following to the edge of the map

The pack used to lose interest at an invisible line. Walk out past ~85 m and the wanderers
stuttered, stopped, and milled about at a boundary nothing on screen marks; cross it and they
stayed out there rather than coming back in.

The cause was the navmesh, not the AI. The `NavMeshBoundsVolume` was sized at 0.85 of the map
with a hard cap of ±8500 cm, so a 15 m ring of perfectly walkable terrain — wider at the
corners — had no navigation data on it at all. A player standing in the ring could not be
pathed to, and because `MoveToActor` is issued with `bAllowPartialPath` the request did not
*fail*: it succeeded, at the nearest point that was on the navmesh. The NPC ran to the island
edge, arrived, and stood there. The stutter was the same fact seen twice a second: the
reachability test flickered as the pack straddled the boundary, and each flip cancelled the
move order the other branch had just issued.

**The fix is a navmesh that covers the whole terrain.** The cap was believed to be a Recast
tile-pool limit, on the strength of one measurement that moved two variables at once
(±9200 cm XY *and* a 2007 cm vertical span → zero tiles). Re-measured properly — resize the
volume in a live editor, `RebuildNavigation`, then project points onto the result — ±10000 cm
XY with the 4586 cm band this terrain's corner ramps actually ask for builds fine, and the
navmesh reaches the terrain edge on **all 48 sampled headings**, none short by even 4 m. The
limit that is real is in Z alone: an 8000 cm span still builds nothing. `NAV_COVERAGE_FRACTION`
is now 1.0, `NAV_MAX_VERTICAL_SPAN_CM` 5000, and `compute_nav_bounds` samples the **box**,
corners included, because the box is what gets built — sampling an inscribed disk was what
left the corners poking out through the volume's ceiling.

The straight-line fallback stays, demoted to what it should always have been: a net for the
last metre or two of corner ramp that Recast refuses to build on because it is too steep.
Twice a second the loop projects **both** ends of the chase onto the navmesh — the player may
have walked off it, and so may the wanderer — and if either misses, it re-issues the same move
order with `bUsePathfinding` off. That still path-follows, so it persists between loop
iterations; `AddMovementInput` would move the NPC for one frame in thirty. Two pins carry the
whole point: the query box is a tight 200 cm in XY (a loose one answers "yes, on the navmesh"
for a player 15 m outside it by snapping to the edge — the bug, restated) and 400 cm in Z (a
Recast polygon can sit 86 cm under the real ground and the projected point is a capsule centre
another 88 cm above it); and `bProjectDestinationToNavigation` **must stay false**, because
true is the dead zone written a different way.

**Proof it follows now.** Headless `-game`, player teleported to x=9500 and again to x=9800 —
2 m from the edge of the world, deep inside what used to be the dead ring. Both runs: the
player's own position projects onto the navmesh, all ten wanderers close at the full 600 cm/s,
and by t=17 s five of them are standing 76–150 cm away, inside melee range. Zero Accessed
None, zero Blueprint runtime errors, zero falls.

### The melee attack

```
MoveToActor --> [distance <= 200 cm  AND  now >= NextAttackTime]
                  true  --> NextAttackTime = now + 1.5
                        --> PlaySlotAnimationAsDynamicMontage(MM_Attack_01, DefaultSlot)
                        --> player's BP_HealthComponent.Health -= 10  (clamped at 0)
                  false ----------------------------------------------> Delay 0.5s
```

- The cooldown is wall-clock (`GetTimeSeconds`) and lives on the **controller**, so ten
  wanderers keep ten independent timers instead of hitting in lockstep.
- The swing plays into `DefaultSlot`, which `build_weapons_and_combat.py`'s layered blend makes
  upper-body only — so the NPC swings while still running. Without that patch the montage is
  full body; it still reads as an attack, so it is not a hard dependency.
- Damage is applied by **writing `Health` on the player's component**, exactly as the pellets do.
  `ApplyDamage`/`AnyDamage` is an *Actor* event and would need a graph on
  `BP_ThirdPersonCharacter`, whose Enhanced Input template graph the Python API cannot partially
  rebuild.
- **Every exit of the melee chain reconnects to the Delay** — the hit, and both cast-failure
  pins. A dangling cast-failure pin ends the chase loop on the first swing and freezes the NPC
  forever, and it would only show up in a level where the player has no health component.
- If `BP_HealthComponent` does not exist, the melee half is skipped with a log line and the NPC
  just chases. The cast node needs the class loaded, or its palette name reads like a typo.

## The graphics menu

`Scripts/build_graphics_menu.py` builds `/Game/UI/BP_GraphicsMenuHUD` (parent `AHUD`) and
points `BP_ThirdPersonGameMode.HUDClass` at it. That game mode is `GlobalDefaultGameMode` and
no generated level overrides it, so the menu is in every level without placing an actor or
touching a `.umap`. **M** toggles the panel, **1 / 2 / 3** pick Low / Medium / High, **D**
toggles debug mode.

It also draws the player's HP bar (see "The shotgun and health").

`Scripts/verify_graphics_menu.py` reads the saved assets back — 102 checks. Run it after any
edit to the builder; it is the only thing that catches pin values that compile but don't mean
what they look like (see the `FKey` gotcha below).

Each preset sets an overall scalability level *and* two console commands:

| preset | scalability | `r.ShadowQuality` | `r.ScreenPercentage` |
|--------|-------------|-------------------|----------------------|
| Low    | 0 (Low)     | 1                 | 70                   |
| Medium | 1 (Medium)  | 2                 | 85                   |
| High   | 3 (Epic)    | 3                 | 100                  |

High maps to Epic, not to 2, because Epic is what the project already runs at — the top preset
has to be the current look, not a downgrade. The console commands are **not** redundant:
`DefaultEngine.ini` pins `r.ShadowQuality=3` under `[/Script/Engine.RendererSettings]`, which is
`SetByProjectSetting` priority and outranks `SetByScalability`, so `SetOverallScalabilityLevel`
cannot move shadows at all (the editor logs `was ignored as it is lower priority`). A console
command is `SetByConsole`, which outranks both. `r.ScreenPercentage` is in no scalability group
and is the biggest GPU lever on a forest this dense.

`BeginPlay` **applies** `DEFAULT_PRESET` (Low) rather than merely pointing the caret at it — the
panel can only tell the truth about current quality if it is the thing that established it. The
menu does not call `SaveSettings`, so a choice lasts the session and every launch starts at Low
again.

### The settings screen, and what survives a restart

The **main menu** has two rows now — **NEW GAME** and **SETTINGS** — moved with **Up/Down** and
taken with **Enter/Space**. The left mouse button is no longer an accept key: with no cursor and
no hit test a click cannot say which row it means.

The settings page is nine rows on the same panel: **mouse sensitivity** (Left/Right, stepped by
`MOUSE_SENSITIVITY_STEP` and clamped to `MOUSE_SENSITIVITY_MIN..MAX` — a floor above zero,
because a sensitivity of 0 is a mouse that cannot navigate back off the page that set it), the
**seven keybinds**, and **BACK**. Enter on a bind row arms a capture; the next key in `KEY_POOL`
that goes down becomes the bind. The navigation keys are deliberately *not* in that pool — a
menu whose own keys can be bound away is a menu that can be locked shut.

All of it lives in **`BP_Settings`**, a `USaveGame` written to slot `OtherworldSettings` **on
every change** rather than on leaving the page: a game quit from the settings screen still has
to remember what was set. It is built by `build_weapons_and_combat.py`, not by the menu's own
builder, because **both** of its consumers must be able to name the class and the weapons script
runs first — that is what avoids a GameInstance and a build-order cycle.

Two things about it are load-bearing and easy to undo by accident:

- **The capture poll is branched on `Capturing` BEFORE the row is activated.** Enter is what
  arms a capture and Enter is still "just pressed" for the rest of that frame, so a poll that
  ran after the activation would bind the accept key to the row the caret was on — a settings
  screen that eats itself the first time it is used.
- **`BP_WeaponComponent` is PUSHED the values every `DrawHUD` frame**; it never loads the save
  and never casts back to the HUD. Its seven `Key` variables (`BIND_VARS`) keep CDO defaults
  equal to the keys documented below, so a pawn with no HUD in front of it still plays. Pushed
  from `DrawHUD` and not from Tick for the usual reason: the menu is a paused world.
- **`BP_Settings.Binds` is indexed, not keyed.** `BIND_VARS` in `build_weapons_and_combat.py` is
  the contract — reorder it and every save already on disk silently rebinds itself. The HUD's
  BeginPlay refills the array whenever its length is not exactly seven, which is what a save
  written by an older build looks like.

Note the consequence in PIE: these are global cvars, so whichever preset is active when you stop
PIE is what your editor viewport keeps. `r.ScreenPercentage 100` and `r.ShadowQuality 3` restore
it.

## Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds everything under `/Game/Weapons` and installs it;
`Scripts/verify_weapons_and_combat.py` reads the saved assets back (**480 checks**).
It supersedes `build_shotgun_and_health.py`, which is kept only as history — do not run it.

**Controls (the defaults — all seven are rebindable on the settings screen):** left click
fires — **held**, on the SMG and the assault rifle · right click aims · **Q** cycles weapons ·
**G** drops · **E** picks up · **Shift** sprints · **R** reloads, and restarts from the death
menu. (1/2/3, M and D belong to the graphics menu, so the weapon keys stay clear of them.)
These are CDO defaults on `BP_WeaponComponent`, pushed over every frame by the HUD from
`BP_Settings` — see "The settings screen" above.

**R** is shared between reload and restart, and that is safe rather than lucky: Event Tick does
not run while the game is paused, so the weapon component is not listening on any frame the
death menu is on screen. The menu polls its own copy from `DrawHUD`, which *is* renderer-driven
and does run paused.

| asset | what it is |
|-------|------------|
| `BP_WeaponItem` | Actor. The base class: every property the weapon component reads (Damage, PelletCount, SpreadDegrees, WeaponRange, MuzzleOffset, GripLocation/Rotation, FireSound, DryFireSound, ReloadSound, AimPose, SlotColor, DisplayName, Dropped, UsesAmmo, **Automatic**, MagazineSize, Loaded, Reserve, FireInterval, ReloadSeconds, NextFireTime, AdsZoom, Scoped, **RecoilPitch**). No geometry, no graph. |
| `BP_Shotgun` | child: 7 primitives, 8 pellets × 18 dmg, 5° cone, 40 m, rifle ready pose, 5+15 rounds, 0.85 s, 1.6 s reload. **Issued.** |
| `BP_Pistol` | child: 5 primitives, 1 × 26 dmg, 1° cone, 60 m, pistol ready pose, unlimited ammo, 0.18 s. **Issued.** |
| `BP_SMG` | child: 7 primitives, 1 × **12** dmg, 2.6° cone, 45 m, 30+90 rounds, **0.09 s**, 1.9 s reload. **Automatic. Found only.** |
| `BP_AssaultRifle` | child: 8 primitives, 1 × **24** dmg, 1.4° cone, 90 m, 30+90 rounds, 0.14 s, 2.1 s reload. **Automatic. Found only.** |
| `BP_SniperRifle` | child: 10 primitives, 1 × **120** dmg, 0.2° cone, 200 m, 5+15 rounds, **1.6 s**, 2.6 s reload. **Found only.** |
| `BP_AmmoPickup` | 2 brass shells a killed wanderer leaves behind; walked into, not pressed for |
| `BP_WeaponComponent` | on the player: Inventory (5 slots), equip/switch/fire/reload/drop/pick up, **sprint + stamina** |
| `BP_HealthComponent` | Health/MaxHealth, the damage stamp, death — despawn and respawn for a wanderer, **the death sequence and the pause** for the player |
| `BP_BloodSplash` | 19 small lit droplets thrown out along the hit normal, each on its own velocity under drag and real gravity, over 0.45 s |
| `Audio/A_*Fire` × 5, `A_DryFire`, `A_ReloadShotgun`, `A_ReloadRifle`, `A_ReloadPistol` | **cut from CC0 recordings of real firearms** by `Scripts/fetch_weapon_sounds.py`. `Scripts/make_weapon_sounds.py`, which synthesised the earlier set, is kept as history and is no longer wired in |

**Weapons are Actors, not components.** The old shotgun was a component tree welded to the
character's mesh, which cannot be dropped — there is no way to leave a component behind in the
world. Making a weapon an Actor is what makes drop, pick-up and switching fall out naturally:
equipping is an attach, dropping is a detach. `BP_Shotgun`/`BP_Pistol` derive from
`BP_WeaponItem` so `Inventory` is one typed array and firing reads its stats off whatever is
held, with one cast and no per-weapon branching.

**That claim has now been tested.** The SMG, assault rifle and sniper were added as three rows
in `_weapon_specs()` plus three part tables, and **not one node changed** in `_author_fire`,
`_author_reload` or the fire gate: pellet count, spread, range, interval, magazine size and
reload time were already parameters those graphs read off `Held`. The only new code the three
needed is the code for *finding* one, which is a property of the drop and not of the weapon.

**Equipping is authored once.** `NeedsRefresh` is set by BeginPlay, switch, drop and pick-up;
Tick's last block consumes it and runs the single equip sequence. Weapons are spawned once at
BeginPlay and then hidden/shown, never destroyed, so a weapon keeps its identity across
switches and dropping can hand the very same actor to the world.

### Where to tune combat, and recoil

**`COMBAT`, a frozen `CombatConfig` dataclass at the top of
`Scripts/build_weapons_and_combat.py`, is the one place the global combat numbers live** —
lethality (`start_health`, `head_multiplier`, `limb_multiplier`), sprint and stamina, the ADS
zoom/interp/cone figures, the mouse-sensitivity limits and compensation, and recoil. Change a
field, re-run the builder. There is no in-editor equivalent on purpose: every one of these
numbers is a *pin literal* baked into a compiled graph, and nothing under `Content/` is
committed, so a designer's edit to a generated DataAsset would be erased by the next build and
was never in the repository to begin with. The verifier asserts that the loose module constants
this replaced are **gone**, so there can be no second, stale copy.

Per-weapon numbers deliberately stay in `_weapon_specs()`. A sixth weapon is still a row.

**Aiming costs half the walking speed** (`ads_move_speed_scale`), and it is applied as a
*second* `MaxWalkSpeed` write, layered in `_author_ads` on top of the one `_author_sprint`
already makes earlier in the same Tick. That ordering is why letting go of the aim key needs
no code at all: sprint writes the speed unconditionally every frame, so the first frame the
ADS branch does not run, the player is back at `BaseSpeed`. The write is gated on
`not Sprinting AND IsValid(Held)` — the same "not sprinting" pin the zoom is gated on, so the
two writes can never disagree about a frame, and a valid `Held` because the factor reads
`AdsZoom`.

It **eases**, on the scope overlay's fade curve rather than on the key:

```
progress = FClamp((BaseFOV / CurrentFOV - 1) / (AdsZoom - 1), 0, 1)
MaxWalkSpeed = BaseSpeed * Lerp(1, ads_move_speed_scale, progress)
```

Note the division by `AdsZoom - 1`, which the mouse-sensitivity slowdown deliberately does
*not* do. Normalising means full ADS is exactly half speed on the 4x scope and on 1.5x irons
alike. Un-normalised — the raw `CurrentFOV/BaseFOV` the mouse uses — the sniper would be
slower on its legs than the pistol, which is a zoom factor leaking into a mechanic that has
nothing to do with zoom. Wanted for the mouse, wrong for the legs.

The trap is the *other* way of writing it: scaling the **live** `MaxWalkSpeed` instead of
`BaseSpeed`. This runs every frame, so that version compounds to a standstill in about a
second, and it looks completely correct in the graph. The verifier walks the write's data
inputs and asserts `BaseSpeed` is up there and `MaxWalkSpeed` is not.

Proved at runtime with a temporary probe forcing `Aiming` off a sine of the world clock and
logging the resulting speed each frame: held, it converged on 300.024 cm/s against a 600 cm/s
base at FOV 60.0016 (i.e. 0.50004x, the residual being the interpolation's own tail);
oscillated, the speed tracked the FOV up and down with no second code path. The probe was
removed by re-running the builder, and the verifier now asserts `Aiming` is driven by the aim
bind and by nothing standing in for it.

**Recoil** kicks the view up by the weapon's own `RecoilPitch` and sideways by a random
±`recoil_horizontal_ratio` of it, charges both to `RecoilDebt`/`RecoilYawDebt`, and pays them
back on Tick with `FInterpTo` toward zero at `recoil_recovery_speed`:

| weapon | kick | |
|---|---|---|
| Sniper | **2.4°** | one visible jolt, then 1.6 s to recover |
| Shotgun | **2.2°** | |
| Assault rifle | 0.85° | 6°/s sustained — the one that walks off target |
| SMG | 0.45° | 5°/s sustained, stays controllable |
| Pistol | 0.30° | |

Only `recoil_recovery_fraction` (0.7) of each recovery step reaches the view. The debt always
settles, so nothing accumulates across a magazine, but **30% of every kick stays in the
player's aim** — that is what makes a burst climb and have to be pulled back down, rather than
springing exactly home between rounds. Aiming down the sights multiplies the whole kick by
`recoil_ads_scale` (0.65), through the same `SelectFloat` shape the cone uses.

**The trap: never `AddPitchInput` / `AddControllerPitchInput`.** Both accumulate into
`RotationInput`, which `APlayerController` multiplies by its deprecated `InputPitchScale` — and
that is precisely the handle the mouse-sensitivity setting writes every frame. Recoil routed
through it would be a fifth of its size for a player on 0.2 and three times its size for a
player on 3.0. `_author_turn_view` reads `GetControlRotation`, adds the delta and writes
`SetControlRotation` instead; the controller's own `LimitViewPitch` re-clamps the result on the
next `UpdateRotation`, so a kick taken while already looking near-vertical cannot tip the camera
over the top.

Two evaluation-order traps, both load-bearing and both invisible in a correct-looking graph:
`RandomFloatInRange` is **pure**, so the sideways draw is made once into `RecoilYawKick` and
read from there — inline it twice and the view swings one way while the accumulator is charged
another, and the recovery never cancels the kick. And the recovery **turns the view before it
writes the debts**, because a give-back computed from `Get RecoilDebt` after the `Set` would
read the value it had just been reduced to and come out as zero.

Proved at runtime with a temporary probe (a seeded debt, re-seeded on settle, printing the
control rotation): 1232 frames of smooth two-axis recovery, pitch and yaw holding their seeded
3:5 ratio to four figures, 0 runtime errors. The probe was removed by re-running the builder.

### Aiming: the hybrid, and the reticle

Neither obvious origin works on its own. **Muzzle-only** is geometrically honest and
unplayable — the barrel sits below and to the side of the camera, so shots land off the
crosshair, and a player standing beside a wall shoots the wall while their crosshair is on an
enemy in the open. **Camera-only** is playable and looks broken — the camera is on a boom
*behind* the shoulder, so the cone visibly fans out from behind the player.

So Tick resolves the aim **every frame, before the trigger is even checked** (the reticle has to
be right on the frames where nothing is fired, which is most of them):

```
camera location + forward * AIM_TRACE_RANGE  --LineTrace-->  AimPoint   what is being aimed at
muzzle --LineTrace--> AimPoint                               AimPoint   can the gun reach it?
                                                             AimBlocked  if it stopped short
```

Step 2 is not a safety check bolted on — it is the same line the pellets fly down, so the
reticle cannot promise a hit the shot will not make. Firing then only has to spread a cone
around `Normal(AimPoint - muzzle)`; `PelletCount`/`SpreadDegrees` make a 1-shot pistol and an
8-pellet shotgun the same code path. This is **hitscan**; a projectile version would keep the
identical aim resolve and fire a velocity along `AimPoint - muzzle` instead of tracing it.

`BP_WeaponComponent` publishes `AimPoint` / `AimValid` / `AimBlocked`. The **reticle is nailed
to the centre of the viewport**, which is not a compromise: the aim ray is cast along the
camera's forward vector, and that *is* the centre of the screen. Drawing it at the projected
`AimPoint` instead was tried and reverted — that point is a world position on whatever surface
the ray lands on, so the crosshair slid under its own parallax and jumped between a near trunk
and the ground behind it. A crosshair you aim with has to hold still. Only its **colour** still
reflects the world: red when the muzzle's line is blocked short of what the camera can see.

A weapon whose `Scoped` flag is set — the sniper, and only the sniper — draws a **scope overlay
instead of that crosshair**, never as well as it: the screen goes black except for a circular
field of view with an etched duplex reticle in it. The art is one square texture
(`T_UI_Scope`, an opaque black field with the hole punched through its alpha), drawn as a square
of the viewport's **height** with the two leftover side strips filled with black rects. Stretched
to the viewport its hole would be an ellipse, and drawn any smaller the corners of the world
would show past it. The whole thing fades on
`clamp((BaseFOV / CurrentFOV − 1) / (AdsZoom − 1), 0, 1)` — how far the camera has actually
travelled toward this weapon's zoom, *not* the `Aiming` flag, so the glass and the zoom are one
animation with nothing to keep in step. `Scoped` is a separate fact from `AdsZoom` on purpose:
a weapon is free to be a 4× with irons or a 2× with glass.

The camera boom is **over the right shoulder** (`aim_camera()`: arm 260 cm, socket offset
`(0, 55, 60)`), because a centred third-person boom points the reticle straight at the player's
own back. The boom is shortened as well as offset — pushing a 400 cm arm sideways swings the
camera wide enough that the player's shoulder crosses the centre again when they turn.

Only the pellet traces are drawn (`TRACE_DEBUG_SECONDS`). The two aim traces run every frame
and would paint the screen solid.

### How a weapon is oriented in the hand

Two independent things had to be right, and each one looked like the other's bug.

**1. `HandGrip_R` carries the weapon's forward on its +Y axis, not its +X.** Measured in the
actor's space:

| pose | socket +Y | socket +X |
|---|---|---|
| `MM_Idle` (arms down) | (0.07, 0.07, **−0.99**) — at the floor | (0.06, −1.00, −0.06) |
| `MF_Rifle_Idle_ADS` | (**0.97**, 0.14, 0.21) — down the sights | (0.19, **−0.94**, −0.27) |
| `MF_Pistol_Idle_ADS` | (**0.99**, 0.06, 0.14) — down the sights | (0.06, **−1.00**, −0.01) |

A hand at the side points its weapon axis at the floor; a hand in a ready pose points it where
the player is looking. +X does neither — it reads ~0.94 to the player's **left**.

**2. The layered blend must run in mesh-space rotation mode**
(`mesh_space_rotation_blend = True`). In the default local-space mode the aim pose's arms are
hung off whatever the *locomotion* hips are doing, so the ready pose loses its own pelvis yaw
(component yaw −35.0 in the ADS pose vs −92.0 in idle). Measured in a running game, that put the
barrel a constant **21° to the player's left**: body yaw 44.6, gun yaw 23.3, every frame. In
mesh space the blended bones keep the ready pose's own component-space orientation. After the
fix, body −29.400 / gun −29.47, body −32.200 / gun −32.17 — under half a degree.

`GripRotation` is then solved per weapon against that weapon's own sampled ready pose: rotate
the weapon's +X onto whatever socket-space direction *is* the player's forward, keeping it
upright. Solving it (rather than using a flat 90° yaw) also removes the few degrees each ready
pose is authored off-centre.

**The weapon is rigidly attached and never rotated on its own.** Driving its rotation from the
aim point each frame was tried and reverted: the gun swivels out of the hand and spins a full
turn as the camera comes round. What aims it is the character — `face_the_camera()` sets
`use_controller_rotation_yaw` and clears `orient_rotation_to_movement`, so the body follows the
camera's yaw and the ready pose keeps the arms down the sights. Verified at runtime: body yaw,
control yaw and camera yaw are equal to the last decimal, every frame.

Two honest limits: there is **no aim offset**, so the gun does not pitch with the camera (the
hybrid aim still puts the shot on the reticle); and the legs play the **unarmed forward gait**,
so strafing reads as running forward while sliding sideways — a strafe set needs blend spaces,
which cannot be authored from Python.

**This took three wrong fixes, and the reason is worth remembering: static derivation kept
agreeing with itself.** Each round produced a self-consistent grip, asserted it in both builder
and verifier, and shipped a gun pointing sideways — because the error was downstream of
everything being checked. What settled it was instrumenting `Tick` with `PrintString` and
reading actual yaws out of a `-game` run. When two rounds of static reasoning disagree with
what the screen shows, measure the running game.

### Sprint, and what it costs

**Shift** runs at 900 cm/s while stamina lasts — 4 s from full, refilling at 12/s once it is
let go. The pack runs at 600, so sprinting is the one way to open a gap, and the asymmetry
between the drain and the refill is what stops it being the only way you ever move.

It lives on `BP_WeaponComponent` rather than on the character for the reason every other key
here does: `BP_ThirdPersonCharacter`'s graph is the Enhanced Input template, which the Python
API cannot partially rebuild. It also belongs there — **the weapon is what has to refuse**:
the fire gate is `pressed AND armed AND NOT Sprinting`.

The whole block is authored **without a Branch**:

```
Sprinting     = ShiftDown AND Stamina > 0
MaxWalkSpeed  = SelectFloat(SPRINT_SPEED_CMS, BaseSpeed,        Sprinting)
Stamina      += SelectFloat(-drain,           +regen, Sprinting) * DeltaSeconds,  clamped
```

Two arms of an if would be the same two writes with different numbers in them, and the pair
could drift; `SelectFloat` picks the number and one write applies it.

**Sprinting drops the ready pose**, and there is no new animation behind that. The ready pose
is the weapon's `AimPose` played as a dynamic montage into `DefaultSlot`, which
`patch_anim_blueprint()` made upper-body-only; running with it still playing is a character
sprinting with the barrel levelled at the horizon and the arms locked. The fix is to **stop the
slot** — with nothing playing into it the layered blend has nothing to override the locomotion
state machine with, so `ABP_Unarmed`'s own run cycle comes through and the weapon goes along in
the hand socket where it is attached.

Mechanically it is one term added to the equip branch's condition
(`IsValid(Held) AND NOT Sprinting`) plus an **edge trigger** in Tick:

```
if Sprinting != PoseSprinting:        # only the frames where they disagree
    PoseSprinting = Sprinting
    NeedsRefresh  = true              # ...which routes back into the one equip block
```

`PoseSprinting` is what the pose currently reflects; `Sprinting` is what it should reflect.
Level-triggering this instead — re-equipping on every frame Shift is held — restarts the
montage sixty times a second, and the weapon strobes.

`BaseSpeed` is **cached from the character at BeginPlay, never written down here**. Measured
in a `-game` run it comes back as **600**, not the 500 a hardcoded "walk speed" would have
guessed — so the literal would have silently retuned the player the first time they sprinted,
and the symptom ("wrong speed, but only after sprinting once") would have pointed at the
sprint code rather than at the copy.

### Dying, and the menu

**Everything that dies collapses the same way, and it is a ragdoll.** One shared subgraph in
`BP_HealthComponent` (`_author_death_collapse`), walked into by both arms of the death branch:

```
DisableMovement -> Capsule.SetCollisionEnabled(NoCollision)
    -> Mesh.SetCollisionProfileName("Ragdoll") -> Mesh.SetAllBodiesSimulatePhysics(true)
```

**There is no death animation in this project and no honest way to make one.** Meshy's rigging
step generates a walk and a run and nothing else — nothing in `assets/cache/meshy`, and nothing
among the 21 clips retargeted per creature, ends on the ground. Epic's own `MM_Death_*` set, the
six clips the player used to play one of, is **hit reactions, not collapses**: measured off the
assets, every one of them is about a second long and ends with the pelvis at 83–88 cm and both
feet on the floor, having staggered 1.5–2 m backwards. That measurement is the whole diagnosis of
"the player gets up right away" — the dynamic montage blended out after 1.1 s, the locomotion
state machine underneath took the pose back, and he was standing again a second before the 2.2 s
pause arrived to freeze him there. Retargeting one of those onto the creatures was tried and
reverted: it produces a monster that staggers and stays up.

A ragdoll needs no asset. Every character here already carries a physics asset (`PA_Mannequin`,
`SKM_Zombie01_PhysicsAsset`, `SKM_Wendigo01_PhysicsAsset`) and it is not optional —
`install_hit_zones` reads the head and limb tables off those bodies, so a rig that could not
ragdoll could not be shot in the head either. The verifier asserts the physics asset and a body
count for both characters.

Order and reasons:

- **DisableMovement, not DisableInput.** CharacterMovement is still driving the capsule, and the
  HUD polls the restart key off the same PlayerController — turning input off risks it.
- **The capsule stops colliding, not the mesh.** It is the capsule, not the mesh, that blocks the
  player and that the pellets trace against (see `make_shootable`), so switching it off is both
  halves of "a corpse is not in the way": you walk through it and you cannot waste ammunition
  on it.
- **The profile before the simulation.** `Ragdoll` is what makes the bodies collide with the
  terrain and ignore Pawn; set it after simulation starts and the first frame resolves against
  `CharacterMesh`, which collides with nothing.
- **`SetAllBodiesSimulatePhysics`, never `SetSimulatePhysics`.** The latter is not a UFunction on
  `SkeletalMeshComponent` at all, and the `PrimitiveComponent` one would simulate the single root
  body — a creature-shaped brick toppling over.

### A wanderer's corpse: 60 seconds

`_author_corpse` runs on the `DespawnOnDeath` arm, after the kill has been counted and the
replacement is already out, so the pack is back to strength while the body is still falling:

```
GetController -> IsValid? -> DestroyActor(the controller) -> Owner.SetLifeSpan(60)
```

- **The AI controller is destroyed, not stopped.** The chase, the melee and the growls are one
  self-re-entering loop on the controller and *none of them consult the pawn's health* — a corpse
  whose controller survived would keep hitting the player from the floor. Destroying an
  `AController` unpossesses it on the way out, and it leaves nothing to leak one controller per
  kill over a session. `UnPossess` alone would close the loop's possession gate too, but that
  controller would sit there running its `Delay` for the rest of the game.
- **`SetLifeSpan`, not a `Delay`.** A latent action here belongs to the component of the actor it
  is waiting to destroy; `SetLifeSpan` is the engine's own timer for exactly this.
- **`GetController`, not the `Controller` member.** `APawn::Controller` is not
  `BlueprintReadOnly`: a get-variable node for it compiles as a warning today and an error in a
  future release.
- The HUD's floating health bar is gated on `NOT Dead` as well as on recency — a corpse was shot
  a moment ago by definition, so without that every body wears an empty bar for five seconds.

### The player's death

```
(the collapse above) -> Delay 2.2s -> GameMode.PlayerDead = true
    -> "[PLAYER-DEAD] killed with N" -> SetGamePaused(true)
```

- **The delay still comes before the pause, and it now does double duty.** Pausing stops physics
  as well as everything else, so it is also how long the ragdoll gets to settle; pausing early
  freezes the player mid-topple, which reads as a hang.
- **The body stays down because there is nothing left to stand it up.** No montage, so nothing to
  blend out of; the pause then holds it exactly as it fell until the level reopens. Measured in a
  `-game` run: the player's head sat at 151.9 cm for twelve seconds, and 2.20 s after death — the
  last frame before the pause — it was at 1.1 cm.
- **The log line exists because the menu cannot be seen headlessly.** A paused game and a game
  where the death path silently did nothing produce identical logs otherwise.
- `FullBodySlot` is still spliced into `ABP_Unarmed` and still asserted. Nothing plays into it
  now, and a slot with nothing playing passes its pose straight through, so it costs nothing —
  it is the only full-body slot either character has and the next thing that needs to override
  the legs will want it.

The menu itself is drawn by the HUD off `GameMode.PlayerDead`: **YOU DIED**, the final kill
count, and `[R] try again`, which unpauses and reopens the current level by name. Unpausing
**before** the open is load-bearing — a level opened into a paused world comes up paused with
nothing left able to unpause it. Reopening the level is also what resets the score, since the
counter lives on the GameMode and `OpenLevel` builds a new one.

**Polling the restart key from `DrawHUD`, not from Tick, is the whole reason the menu works.**
Event Tick does not run in a paused world — which is exactly the state the menu exists in — but
`DrawHUD` is called from the renderer every frame regardless, and `APlayerController` sets
`bTickEvenWhenPaused`, so its `PlayerInput` is still updated and `WasInputKeyJustPressed` still
answers.

**Walking off the edge of the world kills you.** Before, it did not: the terrain ends at
±10000 cm and a player who stepped past it fell forever, with no floor, no death and nothing to
do but quit. The fix reuses two things that already existed rather than adding a KillZ volume or
a teleport. `BP_HealthComponent` already ticked a **world floor** net at `WORLD_FLOOR_Z`
(−1000 cm, well under the terrain's −185 cm floor) to catch wanderers the terrain lost; that net
was AND-ed with `DespawnOnDeath`, so it only ever looked at NPCs. Removing that one AND is the
entire feature:

```
below WORLD_FLOOR_Z?
   |
   +-- yes --> [DespawnOnDeath? -> "[NPC-FELL] …"]   (the log line only)
   |            -> Health = 0                         (both arms land here)
   '-- no ---> carry on
```

The `DespawnOnDeath` test moved **inward**, from gating the net to gating the log line, because
the fall report quotes an `NpcId` and a spawn point the player does not have. Setting
`Health = 0` then drops the player into the ordinary death path above — animation, delay, menu —
so there is exactly one way to die in this game and falling is not a special case. Proved at
runtime: dropped off the edge, the player fell unaided to `hp=0.0 dead=True` under −1000 and
logged `[PLAYER-DEAD] killed with 0`.

The one thing that cannot be checked headlessly is how it *reads*: the camera watches the death
animation from ~8 m under the terrain, looking at its underside.

### Blood

Nineteen droplets — fourteen of spray in a 34 deg cone plus five slow fine ones that hang at the
wound — each 1–3 cm across, dark desaturated crimson (`M_Blood`, linear
`(0.150, 0.014, 0.012)` ≈ sRGB `#6C2825`), **lit and not emissive**, roughness 0.22 so the wet
highlight is what makes it readable at night. Every droplet flies the closed form of
`dv/dt = g - k*v` with `k = 3.6 /s` and real `g = 980 cm/s²`:

```
A(t)  = (1 - e^(-k t)) / k          # two scalars, computed once for the whole burst
B(t)  = (t - A) / k
local = Velocity * A + Fall * B     # one multiply-add per droplet, in a ForEachLoop
scale = built size * clamp((0.45 - Age) / 0.14, 0, 1)
```

**Each droplet carries its own launch velocity in its build-time relative location**, divided by
100 — so the baked number reads as m/s, there is no parallel table that can fall out of step with
the components, and the frame before `BeginPlay` runs the droplets are a 1–9 cm clump at the
wound instead of a nine-metre sphere. `BeginPlay` walks `GetComponentsByClass` once and fills
`Blobs` / `Velocity` / `Size` together, and caches gravity rotated into the actor's frame
(`Fall`) so no transform inverse runs per frame.

`_author_impact` spawns the splash rotated so its forward **is the surface normal it hit**
(`MakeRotFromX`), so blood comes out of the wound rather than along a world axis, and a shot to
the chest and one to the back throw it opposite ways. It also sizes the whole actor by
`clamp(Damage / 24, 0.65, 1.6)`, which scales launch distance and droplet size together.

The cone layout is generated from a fixed seed at build time, which is how the verifier can
recompute it and compare component by component.

**Why not Niagara.** UE 5.8 hands Python a `NiagaraSystem` with no emitter handles and no exposed
parameters, and the API that *can* build an emitter stack —
`UNiagaraExternalSystemEditorUtilities` (`AddEmitter`, `AddModule`, `SetStackInputData`) — is
plain C++ statics with no `UFUNCTION`, so none of it is callable. Duplicating a template such as
`/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst` yields an asset nothing can then
retune. Cascade is worse: the runtime classes survive but the editor module and every
`ParticleModule*` reflection type are gone. A system no script can rebuild is not allowed here,
so the droplets are components and the solver is in the graph.

**Trap.** The A pin of the Kismet math nodes will not hold a literal — `set_pin_value` reports
success and the pin reads back empty, which compiles as zero. `A = (1 - e^(-kt))/k` is therefore
written `(e^(-kt) - 1) / -k`, and the fade likewise, so every constant sits on a B pin.

### The player's body: a generated adventurer, not the mannequin

The player wears **`SKM_Adventurer01`**, a Meshy-generated photorealistic
adventurer — hooded field jacket, chest rig, gloves, worn boots — animated by
**`A_Adventurer01_ABP_Unarmed`**, which is `ABP_Unarmed` retargeted onto its
skeleton by the same `build_retarget.py` that dresses the monsters. It is
generated by `catalog.ADVENTURER` through the ordinary four Meshy stages
(preview → refine → remesh → rig, 40 credits) and is only the *player* because
`build_weapons_and_combat.py` wears it and `npc_placement.NPC_VARIANTS` does not
list it.

**Everything about the player's body is one record, `PlayerSkin`** — mesh, anim
BP, grip point, both ready poses, mesh offset and yaw. They used to be four
literals scattered through the weapons builder that happened to agree about the
mannequin. `player_skin()` resolves `SKIN_ADVENTURER` if all four of its assets
exist and falls back to `SKIN_QUINN` otherwise, all-or-nothing: `/Game/Sourced`
is git-ignored, so a clone that has not run the asset pipeline is a mannequin
again, and a *partly* resolved skin — the adventurer's mesh under the
mannequin's anim BP — compiles, runs, and stands in its bind pose forever.

**Why the animation was moved to the mesh and not the mesh to the skeleton.**
The obvious integration is to put the new body on `SK_Mannequin`, which
everything here already depends on. It is not reachable from this toolchain,
and this was established before a credit was spent:

- Meshy's rigging endpoint takes an input mesh and a height. There is no
  skeleton-convention parameter, so the result is always its own **24-bone
  Mixamo-named rig** — `Hips, Spine02, Spine01, Spine, LeftArm…LeftHand, neck,
  Head`, and **no fingers and no twist bones**.
- The FBX importer *merges* an incoming bone tree into the skeleton it is
  given. 24 differently-named bones do not merge into `SK_Mannequin`'s 161.
- UE 5.8 exposes **no skin transfer to Python**. `IKRetargetBatchOperation`
  retargets animation assets only, and `IKRetargeterController` has no mesh
  export — the editor's "retarget skeletal mesh" button has no scripted
  equivalent, and reaching the C++ behind it needs a module this project does
  not have.

So the risk was the other way round, and it turned out to be small, because the
three things that looked skeleton-bound are all rig-agnostic already:
`hit_zones()` derives head and limb tables from *whatever mesh the character is
wearing*, the ragdoll is `SetAllBodiesSimulatePhysics` on *that mesh's* physics
asset, and the locomotion is a retargeted anim BP that `fix_retargeted_abp()`
has re-pointed from `spine_01` at `Spine02`. Measured on the built asset: head
`Head` ×1.5, ten limb bodies ×0.75, `Hips/Spine01/Spine02/neck/LeftShoulder/
RightShoulder` ×1.0.

**The grip is a bone, not a socket, and the rotation is solved rather than
written down.** The mannequin has a `HandGrip_R` socket sitting in its fist; a
Meshy rig has no sockets, and **Python cannot make one** — `SkeletalMeshSocket`
exposes both `SocketName` and `BoneName` read-only, so there is no way to say
which bone a new socket hangs off. `AttachToComponent` resolves a socket name
and a bone name out of the same namespace, so the weapon attaches to
`RightHand` instead, and `_BoneGrip` stands in for the socket everywhere the
builder asks one for its bone and its rotation. Identity rotation is not an
approximation: `_grip_rotation` *solves* for the transform that puts the barrel
on the player's forward in a given ready pose, so the hand bone's own frame is
taken out by the solve. Measured on the adventurer, the rifle pose's three hand
axes read 0.55, −0.78 and −0.31 along the player's forward — **no axis is the
aim**, which is exactly why the socket-era rule ("the weapon rides the socket's
+Y") could not be carried over, and the verifier now asserts that inverted fact.
What identity costs is position, not aim: the weapon hangs off the wrist joint
rather than the middle of the palm.

**The honest cost is the hand.** A 24-bone rig cannot close a fist, so the
adventurer holds its weapon with an open hand. This is a property of what
Meshy's rigger returns, not of the integration, and there is no asset in the
project that would fix it.

**The two ready poses are retargeted like everything else.**
`MF_Rifle_Idle_ADS` and `MF_Pistol_Idle_ADS` are played into `DefaultSlot` by
path at runtime, so — like `MM_Attack_01` — nothing references them and the
dependency walk cannot find them. They are named in `build_retarget.AIM_SOURCES`
and every creature gets a copy, which is why the retargeted set is now **23
clips** per character rather than 21.

**Build order matters, and it is self-bootstrapping.** The weapons builder
patches `ABP_Unarmed`; the retargeter copies that patched graph onto each
skeleton; the weapons builder then wears the result. On a from-nothing build
that is `build_weapons_and_combat.py` (mannequin fallback) → `fetch_monsters.py`
→ `import_characters.py` → `build_creature_materials.py` → `build_retarget.py`
→ `build_npc_blueprints.py` → `build_weapons_and_combat.py` again. The second
weapons run is what puts the player in the adventurer and re-solves all five
grips against it. **`build_retarget.py` deletes and rebuilds `Anims/<Creature>/`
every run**, so `build_npc_blueprints.py` has to follow it or the wanderers are
left pointing at anim classes that no longer exist — which shows up as four
failures in the *level* verifier, not the weapons one.

**Proved at runtime**, in a live `-game` session driven through the inbox (the
`-game` process runs `init_unreal.py` and therefore listens on `Saved/uepy`, so
`uepy.py` can question a running game the same way it questions the editor —
just not with `unreal.EditorLevelLibrary`, whose `get_game_world` SIGSEGVs
there; `unreal.find_object(None, "<map>.<map>")` returns the world instead):

| | evidence |
|---|---|
| animates | `SKM_Adventurer01` driven by `A_Adventurer01_ABP_Unarmed_C`; over 14 s of bounded shuttling at up to 600 cm/s the foot gap swept −7.2…+16.9 cm and crossed zero, i.e. the feet alternate |
| ragdolls | head 67.1 cm above the actor standing, **−78.0 cm** on the frame the death pause froze the world — a 145 cm collapse against an 88 cm capsule half-height |
| hit zones | live traces on the standing player: `Head`→`Head` ×1.5, both forearms→arm bodies ×0.75, both legs→leg bodies ×0.75, chest→`Spine02` ×1.0 |

**Looking at a generated character.** `Scripts/dev/render_character.py` renders
every skeletal mesh under `/Game/Sourced/Characters` to
`Saved/Renders/<Mesh>.png` through a SceneCapture2D — `take_high_res_screenshot`
needs a viewport and cannot run in this harness. Two traps: the world context is
**not** optional on `create_render_target2d`/`export_render_target` (pass `None`
and the capture still fills the target while the export writes nothing and says
nothing about it), and `show_only_actors` refuses `set_editor_property` on a
component template — `show_only_actor_components()` is the way in.

### Hit boxes

A pellet that hits a character does **1.5x** to the head, **0.75x** to an arm or a leg, and
1x anywhere else (pelvis, spine, neck, clavicles). The dials are `HEAD_MULTIPLIER` /
`LIMB_MULTIPLIER` and the zone roots `HEAD_ROOTS` / `LIMB_ROOTS`, all in
`build_weapons_and_combat.py`.

**The capsule still decides whether a character was hit; the physics asset decides where.**
The pellet trace stops at the capsule, as it always has, so the aim trace and the reticle are
untouched. `_author_hit_zone` then retraces **the same line** (the hit's own
`TraceStart`/`TraceEnd`) with `K2_LineTraceComponent` against the struck character's `Mesh`.
That tests the physics bodies of that one component only, and each body reports its bone.
It ignores collision channels, so `CharacterMesh` ignoring Visibility does not matter.
What does matter is that the mesh has query collision at all, or it has no bodies at
runtime. `install_hit_zones` raises if it does not. A pellet that clips the capsule but
threads between the limbs strikes no body, and counts as a 1x body hit, which is what
every hit was before.

**The tables live on the target, not the weapon.** `HeadBones` / `LimbBones` are Name arrays
on each character's `HealthComponent` template, derived at build time from **that
character's own mesh**. `hit_zones()` takes the body bones from the physics asset's
constraints (`SkeletalBodySetups` is protected from Python, but every body is one end of a
constraint). It then zones each bone by walking the real skeleton with `BoneIsChildOf` on a
transient component, so no bone list is typed out anywhere. For `PA_Mannequin` that is head
= `head`, limbs = 12 bodies (upper arm, forearm, hand, thigh, calf, foot on each side).
The multipliers are class defaults on `BP_HealthComponent`, and an un-zoned target (empty
tables) takes everything at 1x.

**The player is zoned too, but nothing traces at the player yet.** The wanderers' punch is
a range check with no hit location, and it deliberately stays a 1x body hit. The pack's
damage was balanced as it is (see *Balance is a property of the pack*). Anything that later
shoots at the player gets head and limb scaling with no graph change.

Proved beyond the graph: the verifier spawns a wanderer in the editor world and traces
through head, upper arm, forearm, thigh, shin and chest, and each lands on a body worth the
right multiplier. In PIE, against ten live wanderers (running and standing), the same traces
resolved head 1.5x, thigh and shin 0.75x and chest 1x on all 40 samples. So the bodies do
follow the animation. **Not yet proved:** a real trigger pull through the full graph. Headless
runs cannot press the mouse, so that needs a play session (a head shot with the pistol should
take a wanderer from 100 to 61).

### Hit reactions: a survivor flinches

A hit that does not kill plays a one-second stagger on the upper body, for the player and for
every wanderer. It is authored by `_author_hit_reaction` in `build_weapons_and_combat.py`, on
the **False** arm of `BP_HealthComponent`'s death branch, so nothing can ragdoll and flinch in
the same frame.

**The clips are Epic's `MM_Death_*` set, and they are not deaths.** All six are ~1 s long,
stagger 1.5–2 m backwards and end with the pelvis at 83–88 cm and both feet on the floor: they
are flinches, authored to blend into a ragdoll. That is why death here is a ragdoll and nothing
plays them at 0 HP, and why they fit a character that has been shot and survived.
`build_retarget.py` retargets all six onto every creature (`HIT_SOURCES`, `hit_paths()`).

**The order is a contract.** `NPC_HIT_REACTION_CLIPS` in `forest_generator/npc_placement.py` is
the one definition. `build_weapons_and_combat.HIT_REACTION_CLIPS` imports it, and the graph bakes
positions in it into pin literals:

```
(Front_01, Front_02, Front_03, Back_01, Left_01, Right_01)
HIT_DIR_FRONT = (0, 3)  HIT_DIR_BACK = (3, 1)  HIT_DIR_LEFT = (4, 1)  HIT_DIR_RIGHT = (5, 1)
```

If you reorder the tuple, a shot in the back plays a Left clip and nothing reports it. It is all
six or none. `hit_reactions()` returns an empty list unless every clip exists on the mesh's own
skeleton, because five of six would give the wrong clip rather than a missing one. An empty
array is guarded in the graph, so that character simply does not flinch.

```
Health < PrevHealth?                    polled on Tick, so every damage source reacts
  -> now >= NextReactTime?              cooldown: COMBAT.hit_react_cooldown_s (0.45 s)
    -> HitReactions not empty?
      -> f = LastHitFrom . forward, r = LastHitFrom . right
         f >= |r| Front (random 1 of 3) | -f > |r| Back | r > |f| Right | -r > |f| Left
      -> Montage into HitSlot at COMBAT.hit_react_rate (1.4x), blend COMBAT.hit_react_blend_s
      -> NextReactTime = now + cooldown
PrevHealth = Health                     on every arm
```

- **`LastHitFrom`** is a unit vector from the victim toward the source. The damage dealer writes
  it: `_author_impact` derives it from the pellet's impact normal, and the wanderers' punch
  derives it from the two actor locations already on its range check. Nobody has to write it,
  though. The zero vector makes both dots 0, and `>=` on the front test sends that case to
  Front. When the pack surrounds you, each hit comes from its own side.
- **The index is clamped** against the array's real length, so a short array cannot cause an
  `Array_Get` off the end.
- **`HitSlot` is a slot of its own** (`_ensure_hit_slot`), spliced after the aim blend through a
  second `LayeredBoneBlend` on the same spine root. The chest, arms and head take the hit, and
  the legs keep running. It cannot be `DefaultSlot`, because the weapon's ready pose is a
  9999-loop montage held there.
- **`_author_ready_pose_keepalive` is required, not belt and braces.** All slots share the
  default montage *group* (`USkeleton::SetSlotGroupName` is not reachable from Python in 5.8),
  so starting the flinch in `HitSlot` stops the ready pose in `DefaultSlot`. Before this
  existed, the first hit left the player holding the gun in the locomotion pose for the rest of
  the session. The keepalive restarts the ready pose from Tick when both slots are quiet. The
  `HitSlot`-quiet condition stops it from cancelling the flinch on its first frame.
- **Each wanderer variant's clips travel on its AI controller.** Every creature has its own
  skeleton, and Python cannot reach a child Blueprint's override of an inherited component
  (`InheritableComponentHandler`). So `NpcVariant.reactions` puts each variant's six on its
  controller, and they are copied onto the pawn's `HealthComponent` at possession, the same
  route per-variant health takes. Without this, every wanderer would carry `BP_ForestWanderer`'s
  clips, and the wendigos, whose skeleton is different, would never flinch.
- **The pose verifier exempts reaction clips** from "feet alternate" and "pelvis stays put",
  because a stagger breaks both on purpose. It also allows the head below the hips, which
  happens on the wendigo for about half a second as it doubles over. Upright, the pelvis band
  and head-above-feet are still enforced.

**Proved at runtime** with a temporary probe (`HIT_REACT_PROBE`, since removed; the verifier
asserts the switch is off and no probe token survives in any graph). In one 2026-09-28 session
it logged 200 reactions: 16 on the player and 184 on zombie and wendigo wanderers. All six
indices fired (Front 0/1/2: 52/49/51, Back 3, Left 32, Right 13), the ready pose was restarted
94 times, and there were 0 runtime errors. **Needs eyes in a play session:** how the upper-body
stagger reads with the gun raised, and whether 0.45 s under SMG fire looks like repeated
impacts rather than jitter.

### Ammunition

The shotgun starts with twenty shells — **five in the gun and fifteen spare**, not five plus
twenty. Every one of those numbers lives on `BP_WeaponItem`, and that placement is the design: a
weapon here is a *droppable actor*, so drop a half-empty shotgun, walk away, come back and pick
it up, and it is still half empty. A reserve on the weapon component would belong to the player
and would survive a gun that did not.

| field | shotgun | pistol | SMG | rifle | sniper |
|-------|---------|--------|-----|-------|--------|
| damage × pellets | 18 × 8 | 26 × 1 | 12 × 1 | 24 × 1 | **120 × 1** |
| `UsesAmmo` | true | **false** | true | true | true |
| `MagazineSize` / `Loaded` | 5 | 0 (never read) | 30 | 30 | 5 |
| `Reserve` | 15 | 0 | 90 | 90 | 15 |
| `FireInterval` | 0.85 s | 0.18 s | **0.09 s** | 0.14 s | **1.60 s** |
| `ReloadSeconds` | 1.6 s | — | 1.9 s | 2.1 s | 2.6 s |
| spread / range | 5° / 40 m | 1° / 60 m | 2.6° / 45 m | 1.4° / 90 m | **0.2° / 200 m** |

The pistol is the fallback and is deliberately unlimited. The shotgun does **8 × 18 = 144**, so
one connected shot kills a 100 HP wanderer and the 0.85 s interval is the whole balance of the
weapon; the sniper kills in one round and then makes you wait 1.6 s for the next; the SMG spends
nine rounds and most of a second to do the same thing.

Sustained DPS across the five spans **75 to 171** — a 2.3× band, asserted by the verifier. What
differs between the weapons is meant to be how the damage is *delivered*, not how much of it
there is: a weapon three times another's output is not a choice.

**There is no reloading state.** `NextFireTime` is a world-time deadline, and both the interval
between shots and the cost of a reload push it out. That means "cannot fire yet" has exactly one
meaning in the system and nothing has to decide which of two rules is in force — no timer, no
interrupt rule, no `bIsReloading` that can disagree with itself.

**The fire gate is two nested Branches, not one folded condition**, and that is not cosmetic.
`pressed AND armed AND NOT sprinting` is the outer one; the ammunition and cooldown tests are
inside it. Every one of those inner tests reads a property off `Held`, and a Branch's condition
is pulled **every frame** — including the frames where nothing is equipped. Folded together,
that is an `Accessed None` per frame forever.

**The reload's arithmetic is computed once and stored** in `ReloadTake`
(`Min(MagazineSize - Loaded, Reserve)`). Read it back after `Loaded` has gone up and it quietly
returns a smaller number, so the reserve is charged less than the magazine gained — the
pure-node trap in its most expensive form: free ammunition.

**A killed wanderer drops two shells**, on the same `DamagedByPlayer` arm the kill counter uses,
and for the same reason: the safety net writes `Health = 0` for anything that falls through the
world, and paying for that would turn a bug into an ammunition supply.

`BP_AmmoPickup` is **walked into, not pressed for** — `E` already picks weapons up, and a weapon
on the ground is a real choice (five slots are finite) where ammunition you obviously want is
not. The distance is measured **on the pickup**, not in the weapon component's Tick: there are at
most a handful of these on the ground, so one Tick each beats a `GetAllActorsOfClass` sweep every
frame whether any exist or not. `Credited` is the break `ForEachLoop` does not have — without it
a player carrying two shotguns would be paid twice. It only destroys itself once something has
actually taken it, so the shells are still there when a shotgun-less player later finds one.

Proved at runtime with a temporary probe: a pickup dropped on the player took the reserve from
**15 to 17** and removed itself, with zero blueprint errors and zero `Accessed None`.

### The three found weapons, and the 10% drop

The shotgun and the pistol are **issued** — spawned into the player's hands at BeginPlay. The
SMG, the assault rifle and the sniper are **found**: the only way to get one is to kill something
carrying it, which is what makes the rate a reason to keep fighting rather than a number in a
table.

```
one kill in ten leaves a weapon   GUN_DROP_CHANCE = 0.10
...drawn uniformly from three     so each individual gun is ~1 in 30
```

Two decisions, deliberately separate. **Whether** anything drops is one roll; **what** drops is
an index into `DropClasses` (an array on `BP_HealthComponent`, filled by `main()`). Keeping them
apart means the rate and the table tune independently — adding a fourth findable weapon changes
what a drop is *worth* and not how often one happens, which is not true of the obvious
alternative, one roll into a weighted table. It is also why the table is an array rather than
three variables and a `Switch`: a Switch grows a pin per weapon, and the array's length is
already the only number the draw needs.

Rolled on **the same `DamagedByPlayer` arm as the shells and the kill count** — the safety net
writes `Health = 0` for anything that falls through the world, and it must not be a weapon
dispenser.

`Dropped = true` on the spawned actor is the **entire** handover. From that moment it is an
ordinary weapon lying in the forest, and the `E` that picks up a gun the player threw away picks
this one up with no new code: nothing in `_author_pickup` knows these exist.

Guard worth keeping: the roll's condition is `lucky AND stocked`, where `stocked` is
`Length(DropClasses) > 0`. Without it `RandomIntegerInRange(0, -1)` feeds `Array_Get` an index
into nothing on any build where `main()` has not filled the table.

Proved at runtime with a temporary probe and the chance forced to 1.0: ten forced kills produced
**12 `BP_WeaponItem` actors** (2 = the player's own) and **10 of them flagged `Dropped`**, plus
ten `BP_AmmoPickup`s, with 0 blueprint errors and 0 `Accessed None`. Counting actors would only
have proved a spawn happened — the second number is the one that proves the cast behind it
succeeded and the pick-up interface was actually written.

### Weapon sounds: nine assets, cut from recordings of real firearms

`Scripts/fetch_weapon_sounds.py` **downloads and cuts** the nine WAVs; it does not synthesise
them. (`make_weapon_sounds.py`, which did, is gone — a synthesised gunshot reads as a
synthesised gunshot.) It is pure Python plus tools that ship with macOS: `curl` to fetch,
`bsdtar` to unpack the 7-Zip archive (libarchive reads 7z; there is no `7z` binary on a stock
Mac), `afconvert` to resample, and the stdlib `wave` module to cut. Downloads cache in
`Scripts/downloaded_sounds/` (~200 MB, git-ignored), output lands in
`Scripts/generated_assets/sounds/` alongside a generated `SOURCES.md`.

**Every source is CC0**, which was a hard filter rather than a preference: this project has no
credits screen, so a CC-BY pack cannot be used correctly no matter how good it sounds. The five
gunshots all come from *The Free Firearm Sound Library* — one Mossberg, one 1911, one Carl
Gustav M45, one AK-47, one Mosin Nagant — deliberately from the **same** library, because five
samples from five places differ in room and in distance before they differ in calibre. The four
handling sounds come from two CC0 OpenGameArt packs.

| asset | is | length |
|---|---|---|
| `A_ShotgunFire` / `A_PistolFire` / `A_SMGFire` / `A_RifleFire` / `A_SniperFire` | one report each, from the five firearms above | 0.60–1.60 s |
| `A_ReloadShotgun` | a pump being cocked | 0.47 s |
| `A_ReloadRifle` | magazine out, magazine in, bolt released | 1.56 s |
| `A_ReloadPistol` | a slower, hand-fed reload | 1.58 s |
| `A_DryFire` | one metallic lock click | 0.14 s |

**The reload is no longer one sound for five weapons.** `ReloadSound` is a per-weapon field:
the pump shotgun gets the pump, the SMG and the assault rifle share the magazine reload, and
the pistol and sniper share the slower one. `DryFireSound` *is* still shared — one hammer
falling on an empty chamber sounds much like another — which is a fact about the defaults, not
about the shape of the data. All three sounds live on `BP_WeaponItem` and are read off `Held`,
so a new weapon is still a row in `_weapon_specs()`.

Four decisions are baked into the samples rather than into the graph:

- **Mono, 44.1 kHz, 16-bit.** `PlaySoundAtLocation` spatialises by panning and attenuating, and
  it can only do that to a one-channel source. A stereo shot plays flat wherever it happens.
- **The level is baked in, per weapon.** The two automatics are cut quieter (peak < 0.80) than
  the single-shot weapons, because at 0.09 s between rounds up to twelve copies of the SMG
  sample overlap and equal-loudness samples would clip the mix. Zero graph nodes were spent on
  this; the verifier asserts `sample_length ÷ FireInterval ≤ 12` and the peak for each.
- **Shots are truncated mid-tail and faded (30% of the cut); handling sounds are not** — they
  already end in silence, and a 30% fade was ducking the reload's bolt release by 70%.
- **A burst guard, because one take fooled me.** `AK-47/C_29P.wav` is a four-round burst that
  reads as a single shot at a glance; shipped, it would have fired one bullet and played four.
  `_count_shots()` now counts onsets in every gunshot cut and raises unless there is exactly
  one, calibrated against known bursts (4, 9 and 10 rounds) and the loudest slapback echo in
  the library (0.61 of peak).

**Where each sound is gated is the whole design:**

- **The click** hangs off the False arm of the ready gate — the one place that knows the trigger
  was pulled and no shot happened. Its condition is `empty AND cooled AND tapped`, all three.
  Without `cooled` it would click on most frames of a held trigger; without `tapped` it clicks
  60 times a second on a held *empty* weapon, which is the automatic-fire change reaching into
  a graph that did not seem to care about it.
- **The clack** plays on the True arm of the reload only. On the False arm — an unlimited
  weapon, or a full magazine — nothing moves, and a sound there would be the game claiming it
  had done something it had not.

### Distance and direction: the three attenuation profiles

Every sound in the game is made by something standing somewhere, and every one of them fades
with distance and pans with direction. **None of that is hand-rolled.** It is three
`USoundAttenuation` assets in `/Game/Audio`, built by `build_sound_attenuations()` and named on
each `SoundWave` by `apply_attenuation()`:

| asset | full volume to | inaudible past | used by |
|---|---|---|---|
| `A_Att_Gunfire` | 2 m | **100 m** | the five gunshots |
| `A_Att_Creature` | 1.5 m | 40 m | growls, roars, melee thuds |
| `A_Att_Foley` | 1 m | 15 m | footsteps, the dry click, the reload clacks |

All three are `NATURAL_SOUND` (the engine's dB curve, reaching −60 dB at the edge), spherical,
and spatialised on the mixer's own panner. `A_Att_Gunfire` alone turns on the distance low-pass
(20 kHz → 2.5 kHz), which is why distant gunfire is a thump and not a crack.

**The trap this fixes, and it is a silent one.** A `USoundBase` whose `AttenuationSettings` is
`None` is *not* attenuated by some default — distance falloff and spatialisation are parsed out
of the attenuation settings and out of nothing else, so a sound without them plays at **full
volume, dead centre, from anywhere on the 200 m map**. Every call site was already
`PlaySoundAtLocation` and every sample was already mono; the audio was flat because no
attenuation asset existed at all.

**Set on the asset, not on the node.** `PlaySoundAtLocation` carries an `AttenuationSettings`
pin that overrides the `SoundBase`, but there are five call sites across three Blueprints
authored by two builders, so the pin is five chances to miss one. `apply_attenuation()` sweeps
the two audio *folders* and raises on a wave it has no profile for, so a sound added later
stops the build rather than shipping audible from everywhere.

**Nothing is 2D.** There are no menu clicks and the HUD is drawn silently, and the player's own
weapon is a third-person weapon in a third-person game — it is out there in the world at the
end of the player's arms, and the muzzle is ~1.5 m from the listener where the gunfire curve
is still 1.0. The player's own **footsteps** are the judgement call: they share the component
and the profile with the wanderers', so they attenuate over the ~3 m camera boom. Kept that
way, because the alternative is a second footstep path whose only job is to be wrong about
where the player's feet are.

**Two things worth knowing next time.** `dBAttenuationAtMax` is spelled `d_b_attenuation_at_max`
in Python. And `USoundBase.max_distance` is *not* a field the builder writes — the engine
caches it off whatever attenuation resolves, and it is what the audio device culls against, so
reading it back (10000 / 4000 / 1500) is end-to-end proof the link took rather than a re-read
of the struct that was just written. The runtime proof used the same machinery from the other
side: `AreAnyListenersWithinRange` — the test `PlaySoundAtLocation` itself makes — answered
true at 5 m and false at 16 m against the foley reach, true at 90 m and false at 105 m against
the gunfire reach, on all eleven footstep components in a live `-game` world. **It is an
impure node**: leave its exec pin unwired and the compiler prunes it and the pin reads as the
default `false`, which looks exactly like "nothing is audible anywhere".

### Holding the trigger: automatic weapons

`BP_SMG` and `BP_AssaultRifle` are automatic; the other three are not. **This cost no new
state.** `FireInterval` and `NextFireTime` were already consulted on every frame the trigger
was down, so the only question the change had to answer is whether a held button counts as a
new trigger pull. `Automatic` is one more bool on `BP_WeaponItem` and one more column in
`_weapon_specs()`; no graph branches on a weapon's name.

The care went into **where** the question is asked:

```
outer gate:   (tapped OR holding) AND Held valid AND NOT Sprinting
   '-- inner: (has ammo AND cooled) AND (tapped OR (holding AND Held.Automatic))
```

The outer gate asks only what can be answered with no weapon in hand — *is the trigger being
touched at all* — and the weapon-specific half sits inside, where `Held` is known valid. Read
`Automatic` in the outer condition and it is an `Accessed None` **every frame** the player
walks around empty-handed, because a Branch's condition is pulled every frame and a pure Get
re-evaluates per read. That is the same nested-Branch rule the ammunition gate already
follows, and the verifier now pins it: exactly one Branch's condition closure reads
`Automatic`, and that same closure also reads `Loaded` and `NextFireTime` — which is what
proves it sits behind the valid-`Held` gate rather than beside it.

`tapped` is `WasInputKeyJustPressed`, `holding` is `IsInputKeyDown`, both on `LeftMouseButton`;
OR-ing them is what makes a single-shot weapon still fire on a tap while an automatic keeps
firing. Rate of fire is entirely `FireInterval` — 0.09 s on the SMG, 0.14 s on the rifle — so
tuning an automatic is tuning a number, not a loop.

### Debug mode

One bool on the GameMode (`DebugMode`), toggled with **D** in the graphics menu, **off by
default**. It turns on three developer overlays: the **pellet tracers** drawn from the muzzle,
the **damage readout** at each impact, and the **wanderer's number** beside its health bar.
All three are instrumentation, and instrumentation is not what the game looks like.

The damage readout is a `DrawDebugString` at the pellet's impact point, drawn for the
tracer's `TRACE_DEBUG_SECONDS`. It reads `39.0 (x1.5)`: the health the target actually lost,
and the hit-box multiplier behind it. It only appears on things that carry a
`BP_HealthComponent`, because a tree takes no damage. A shotgun blast draws one number per
pellet that connected, so eight can stack on one torso.

It lives on the GameMode rather than on the HUD that toggles it because `BP_WeaponComponent`
draws the tracers, and a component cannot reach a HUD variable.

The tracer is a **separate `DrawDebugLine` behind a Branch**, not the trace node's own
`DrawDebugType`. That pin is an enum *literal* and an enum pin cannot be driven by a variable, so
"sometimes" is not expressible there at all; every trace in the file is now `None`.

Each reader takes one cheap copy rather than casting repeatedly: the weapon component reads the
flag off the GameMode **once per shot** and branches on its own cached bool per pellet; the HUD
copies it into `DebugOn` **once per `DrawHUD`**. The HUD's copy also exists so the cast-failed
path has a real answer (`false`) — that path reaches the same drawing code, and a `Get` off an
invalid object is an `Accessed None` per wanderer per frame.

### The HUD

`build_graphics_menu.py` draws, every frame: the player's HP bar and the stamina bar under it
(top-left), the **kill counter** (top-right), a projected health bar over every wanderer (with
its spawn number beside it **in debug mode only**), a 5-slot inventory strip centred along the
bottom — each slot showing its weapon's **rounds-loaded / rounds-in-reserve** if it uses
ammunition at all — and the centre reticle. Or, if the player is dead, **only the death menu** — the first thing `DrawHUD` does is
read `GameMode.PlayerDead` and branch, because a reticle and an inventory strip over a death
screen read as a game still being played.

**A wanderer's bar is hidden by default** and shown only for **5 s after something hurt it**.
Ten bars over ten chasing NPCs is most of the screen, and the bar is only ever *read* just
after a shot lands; the rest of the time it is clutter over the forest the player is aiming
into. The pellet stamps `LastDamageTime` on the health component it hit (`_author_impact`), the
HUD compares it against `GetTimeSeconds`, and the default of −1000 is what keeps every bar off
the screen at level start.

**The kill counter is on the GameMode** (`NpcKillCount`), not on anything that dies — it has to
outlive both the wanderers that earn it and the player's own components. It is incremented in
the death path only when `DamagedByPlayer` is set, which is the guard that matters: the
under-the-world safety net writes `Health = 0` down that same path, and nobody shot that.
Measured both ways in a `-game` run — five wanderers killed with the flag set report
`killed with 5`, the same five killed without it report `killed with 0`.

The **FPS readout in the top-right is not drawn here**: BeginPlay runs
`stat fps` (`FPS_COMMAND`), and the engine's own stat display puts itself in that corner. There
is no position to tune and no canvas call to collide with the HP bar — and the number is the
engine's smoothed frame time, not a `1/DeltaSeconds` recomputed on the HUD. Like the preset
cvars, it is global: a PIE session leaves `stat fps` on in the editor viewport, and `stat fps`
again turns it off. The strip and the reticle are both laid out from the viewport size, so they stay
centred at any window size. Slot colour and
name are read from each weapon's own `SlotColor`/`DisplayName`, and the ammunition readout off
its own `UsesAmmo`/`Loaded`/`Reserve` — so the HUD keeps no list of weapons to fall out of step
with, and no idea which of them is the one with a magazine. The strip is laid out from the viewport size so it stays
centred and bottom-anchored at any window size.

## Current state

- The player is a **Meshy-generated photorealistic adventurer** (`SKM_Adventurer01`,
  animated by a retargeted `A_Adventurer01_ABP_Unarmed`) rather than the Epic mannequin —
  see *The player's body* above for why the body moved to the animation and not the other
  way round, and for the one thing that cost: a 24-bone rig cannot close a fist, so the
  weapon is held in an open hand.
- The player carries a **shotgun and a pistol**, switchable with Q, droppable with G and
  recoverable with E; both weapons fire with sound, blood and muzzle-origin spread, and the
  character holds the matching ready pose while moving. **Shift sprints** at 900 cm/s against a
  4-second stamina bar and blocks firing while held. Every wanderer dies at 0 HP, respawns
  75-100 m from the player, and shows its health bar only for 5 s after being hit; **ten of
  them** chase at once. Kills are
  counted in the top-right. At 0 HP the **player** drops, the game pauses and a menu offers the
  final score and **R to try again**. The shotgun is **limited to 20 shells** (5 loaded, 15
  spare), does 8 × 18, waits 0.85 s between shots and reloads with **R**; killed wanderers drop
  **2 shells** that are picked up by walking over them; the pistol stays unlimited. **D** in the
  graphics menu toggles debug mode, which is the only thing that shows pellet tracers or the
  wanderers' numbers. Built by
  `build_weapons_and_combat.py` — **480/480** in-engine checks, **117/117** HUD checks.
  The **SMG and the assault rifle fire while the button is held**; the other three are
  tap-only. All nine weapon sounds are cuts from **CC0 recordings of real firearms**, with a
  reload per weapon class. A player who walks off the edge of the terrain now **dies** instead
  of falling forever, and the NPCs **follow to the edge of the map** — the navmesh covers the
  whole terrain, so the 15 m ring it used to leave uncovered is gone.
  Aiming is the camera/muzzle hybrid described above, with a reticle on the real impact point,
  and the held weapon is turned to face that point every frame.
- Proven in `-game` runs, not just in the graph: the player's death pauses the world (the
  health components' last Tick is at world t = 2.200635, exactly the delay, and there is **not
  one log line of any kind** afterwards); the kill counter counts shot wanderers and refuses
  fallen ones (5 vs 0 over identical deaths); `BaseSpeed` caches as **600**. A clean 90 s run
  is 0 runtime errors, 0 Accessed None, 10 spawns, 0 falls, and the pack killing the player.
  The ammunition pickup was proved the same way: a `BP_AmmoPickup` dropped on the player took
  the shotgun's reserve from **15 to 17** and removed itself, with no errors and no
  `Accessed None`.
- **The four newest features were proved at runtime, not only in the graph.** Automatic fire,
  the new audio and the off-the-edge death: a clean 30 s `-game` run with 0 errors, 0 Accessed
  None, 0 script warnings, 10 spawns, 0 falls, and a player dropped off the edge falling
  unaided to `hp=0.0 dead=True` with `[PLAYER-DEAD] killed with 0` logged. The navmesh fix: the
  player teleported to x=9500 and again to x=9800 — 2 m from the edge of the world — projects
  onto the navmesh, and all ten wanderers close at the full 600 cm/s, five of them standing
  76–150 cm away (inside melee range) by t=17 s.
- **Still unverified headlessly, and worth a play session:** everything that needs a key held
  or an eye on the screen — how sprint feels against a pack that runs at 600, whether the
  stamina bar reads clearly under the HP bar, whether the new blood spray looks like blood, and
  how the death menu sits on the screen. New to that list: whether 0.85 s between shots feels
  like weight or like lag, whether 20 shells against ten chasing NPCs is tight or merciless,
  whether the two brass shells are actually findable on a forest floor at night, and whether
  the slot's "3 / 15" is legible at that size. Also still open from before: how the reticle
  reads while moving, and how much the gun visibly detaches from the hand. New again with the
  three found weapons: whether the five silhouettes are actually distinguishable in a fist at
  3 m (the SMG is short, the rifle has a carry handle, the sniper has a scope and wood), whether
  the sniper's 1.6 s between shots is tense or just slow against a pack that closes 75 m in 15 s,
  whether one drop in ten feels like a reward or like nothing, whether a dropped gun floating
  ~1.3 m above where the corpse stood reads as a pickup or as a bug, whether the dry-fire click
  is audible over the pack, and whether dropping the ready pose mid-sprint looks like a
  transition or like a pop. New with the sounds and automatic fire: whether a held SMG trigger
  reads as a burst or as mush (0.09 s between rounds against a 0.60 s sample), whether the AK
  and the Mosin read as different guns out in the forest, whether the 0.47 s pump under a 1.6 s
  shotgun reload feels short, and whether dying ~8 m under the terrain — the camera watching
  the death animation from beneath the map — reads acceptably.
- `EditorStartupMap` is `/Game/Maps/Lvl_Forest_200m`. `GameDefaultMap` is still
  `/Game/Maps/Lvl_Forest` — a packaged or standalone run boots the old level.
- Branch `night-mode`, clean. Latest commit `e5745e9 night mode initial`.
- `/Game/Maps/Lvl_Forest_200m` is generated in **night** mode: 136 trees / 5 species,
  44,368 knee-high grass clumps / 9 species, **ten NPCs at 75.0-78.0 m** from the player,
  moon light 0.12 lux, emissive starfield sky dome as the ambient light source.
  Offline 28/28 and in-engine **148/148** checks pass. The `NavMeshBoundsVolume` now covers
  the whole map: ±10000 cm XY, a 4580 cm vertical band centred at z 1905.
- **Known pre-existing bug:** `scatter_trees` does no minimum-spacing rejection, so some
  size/seed combinations fail the `Tree Spacing (>100cm)` check (e.g. `--size 300` with the
  default seed 42 gives a 70 cm pair). 200 m/seed 42 and 300 m/seed 99 pass. Unfixed.
- The pack **runs**: measured in a `-game` run, all of them closed 75 m in ~15 s
  (`max_walk_speed` 600) and then landed melee hits. Time from level start to the player's
  death line is 18.0 s with five and 16.8 s with ten — the approach dominates, because a
  player standing still dies within a second of contact either way. Not seen headlessly, and
  worth a look in a play session: whether `MM_Attack_01` actually reads as a swing on the upper
  body while the legs keep running, and whether ten attackers crowd the screen (their health
  bars no longer do — those are hidden unless one was just hit).
- Night-sky dials live in `Scripts/forest_generator/lighting.py`: `star_brightness` (2.5),
  sun `intensity` (0.12), `auto_exposure_bias` (1.6).
- `Scripts/` also holds ~110 older one-off inspect/fix scripts from earlier iterations.
  They are history, not API — prefer the generator + `forest_generator/` package.

## Gotchas learned the hard way

- **An unknown key in an `.ini` section is silently ignored — including the section name.**
  `bRemoteExecution` belongs to `UPythonScriptPluginSettings` (`UCLASS(config=Engine)`, so
  `DefaultEngine.ini`); this project long declared it under
  `[/Script/PythonScriptPlugin.PythonScriptPluginUserSettings]`, a real class that has no such
  property, in *both* `DefaultEngine.ini` and `DefaultEditorPerProjectUserSettings.ini`. No
  warning, no log line, remote execution simply never on. When a config flag appears to do
  nothing, confirm the owning class and its `config=` target in the engine source
  (`Engine/Plugins/.../Private/*Settings.h`) before believing the setting.
  `bDeveloperMode` genuinely is a UserSettings key — the two live in different files.

- **UE's stock `Pawn` profile IGNORES the Visibility channel** — and so does `CharacterMesh`.
  A `LineTraceSingle` on `TraceTypeQuery1` (which *is* Visibility) therefore passes straight
  through a Character and reports **no hit**, indistinguishable from a genuine miss. Nothing
  logs it. This made the NPC unkillable through two rounds of debugging, and it also explains
  an earlier instrumented run where pellets hit terrain hundreds of times and applied damage
  zero times — that was wrongly blamed on range. `make_shootable()` in
  `build_weapons_and_combat.py` sets the capsule's Visibility response to Block and asserts
  the read-back; `verify_weapons_and_combat.py` guards it for both characters. Setting one
  channel response flips the profile from its preset to "Custom", which is expected.
  To test a collision change without a play session: spawn the actor into the **editor**
  world and run `unreal.SystemLibrary.line_trace_single` through it — and A/B it by reverting
  the response and re-tracing, which is what proved this fix rather than assuming it.
- The collision-response enum is **`unreal.CollisionResponseType.ECR_BLOCK`**;
  `unreal.CollisionResponse` is an unrelated *struct*, and
  `BodyInstance.collision_response_template` is not exposed. Read and write per-channel
  responses with the PrimitiveComponent methods
  `get_/set_collision_response_to_channel`, not through properties.

- **`get_basic_type_by_name("float")` silently declares an `int`.** So does `"double"`. The
  only spelling that yields a Blueprint float is **`"real"`**. The one clue is a
  `LogBlueprintEditorLib: Warning: Primitive type: float not recognized, defaulting to int`
  buried in the log; the variable compiles, saves, and reads back correctly for any integral
  default (100.0, 9.0, 4000.0 all survive the round trip), so it surfaces only once something
  needs a fraction. `verify_weapons_and_combat.py` guards this by asserting
  `isinstance(cdo.get_editor_property(var), float)` — an int property hands Python an `int`.
  `build_shotgun_and_health.py` has this bug throughout; it is superseded, not fixed.
- **`set_pin_value`'s return value is not a usable signal**, and a pin that quietly stays
  empty compiles as **zero**. Both builders' `_set()` now writes the pin and then *reads it
  back*, raising if the literal did not land — an empty numeric pin is accepted only when the
  value written was itself zero, since a blank literal genuinely is 0. Adding that guard
  immediately surfaced two live instances: the camera aim ray's 1 km length, and `DROP_FORWARD`,
  which meant dropped weapons had been landing on the player's own feet rather than 120 cm
  ahead. Both looked perfect in the graph.
- **UE 5 promotes `Multiply_VectorFloat` to a wildcard operator**, and with nothing connected
  its `B` pin is a **vector** — a struct pin, which takes no literal at all. Connecting a float
  works; setting a float *literal* silently does nothing. Multiply component-wise by a
  `MakeVector(R, R, R)` instead. This is the specific shape both bugs above took.
- **Struct pins reject `set_pin_value` outright.** Every format for an `FVector` pin
  (`"5,5,5"`, `"(X=5,Y=5,Z=5)"`, `"X=5 Y=5 Z=5"`, …) returns False and leaves the pin empty,
  which the compiler then reads as the **zero vector** — a zero scale on a spawn transform
  makes the actor invisible. Build constants with a `MakeVector` node instead (`_vec()`).
  `LinearColor` pins *do* accept `"(R=…,G=…,B=…,A=…)"`, which is why the HUD's colours work
  and makes the vector case easy to assume works too. The engine logs
  `Failed to set default value … on A`, but `set_pin_value`'s return is the real signal — and
  note it also returns False when the value you set equals the pin's existing default, so a
  False is not always a failure.
- **The mesh's reference pose is not the skeleton's.** `AnimPoseExtensions.get_reference_pose`
  takes a `Skeleton`, and for `SKM_Quinn_Simple` that returns `SK_Mannequin`'s pose, which is
  not what a spawned mesh shows. Comparing the two produced an apparent 40° disagreement that I
  briefly recorded here as "offline sampling disagrees with the engine" — it does not. Sampling
  `MM_Idle` offline gives HandGrip_R at `(-3.72, 3.28, 85.90)` and the live mesh reports
  `(-3.719, 3.275, 85.904)`. Compare like with like.
- **An animation pose can be sampled from Python**, which is what makes a derived grip
  possible: `AnimPoseExtensions.get_anim_pose_at_time(seq, t, AnimPoseEvaluationOptions())`
  then `get_bone_pose(pose, bone, AnimPoseSpaces.WORLD)`. Note `WORLD` there means **component**
  space — a pose has no world to be in. `SkeletalMesh.find_socket(name)` gives the socket's
  parent bone and relative transform (`SkeletalMesh.Sockets` itself is protected and
  unreadable), and `MathLibrary.compose_transforms(A, B)` is A-then-B, so
  `socket_component = compose(socket_relative, bone_component)`.
- **`BlueprintEditorLibrary` has no `get_function_name`.** To tell *which* function a call node
  wraps, use `get_node_title` — `"GetCameraLocation"`, `"vector * vector"`, `"MakeVector"`,
  `"Get AimPoint"`. Pin sets alone cannot separate two nodes that both take `self` and return a
  value, which is how `verify_weapons_and_combat.py` distinguishes the four traces.
- **A Slot node's palette entry is named after an already-registered slot**
  (`Animation|Montage|Slot'DefaultSlot'`), so a slot that does not exist yet cannot be asked
  for by name — every spelling of `Animation|Montage|Slot` returns None. Spawn the entry for an
  existing slot, rename the node's inner `node.slot_name`, and compile:
  `UAnimGraphNode_Slot::BakeDataDuringCompilation` calls `Skeleton->RegisterSlotNode` on
  whatever name it finds, so one compile does the registering. That is how `FullBodySlot` gets
  made. Runtime matching is by name only — `PlaySlotAnimationAsDynamicMontage` builds a
  transient montage whose track carries the slot name, and the node picks it up.
- **`BlueprintEditorLibrary.set_node_pos` takes an `IntPoint`**, while
  `create_node_from_name` takes a `Vector2D`. Passing the wrong one is a nativize TypeError,
  not a silent failure — but the two APIs sitting next to each other invites it.
- **AnimGraphs *are* authorable from Python; blend spaces are not.**
  `BlueprintGraphEditor.get_graph_editor_by_name(anim_bp, "AnimGraph")` returns a working
  editor: anim nodes can be created from the palette (`Animation|Blends|Layeredblendperbone`),
  wired, and compiled. But `UBlendSpace` exposes no sample-authoring API, so a locomotion
  graph that needs directional blend spaces cannot be built. `UBlueprint.FunctionGraphs` is
  not a UPROPERTY, so go through `get_graph_editor_by_name`, and note a bare
  `BlueprintGraphEditor(bp)` targets the **EventGraph** — on an Anim Blueprint that is the
  wrong graph and `list_all_nodes()` quietly returns the event graph's nodes.
- **A pose output pin legally feeds two pose inputs** through the API, and it compiles — so
  splitting locomotion into both a layered blend's base and a slot's source needs no cached
  pose pair.
- **An anim node's settings live on its inner `node` struct, and the read is a copy.**
  `blend.get_editor_property("layer_setup")` fails (it is not on the graph node); go through
  `node`, mutate, and **write the whole struct back**. Also: these structs `repr()` as `{}`
  even when populated, so verify by reading fields, not by printing.
- **The navmesh query nodes are PURE, and a failed one still hands you a location.**
  `K2_ProjectPointToNavigation` and `K2_GetRandomReachablePointInRadius` are const
  `BlueprintCallable`s, so UHT promotes them to pure: no exec pin, and **one evaluation per
  output pin read**. Two consequences, both of which compile and look right:
  a graph that reads the location output and ignores the bool spawns *something* at a garbage
  point when the query fails (this is what put respawned NPCs under the terrain — the location
  fell back to the raw input, carrying the player's Z); and driving such a node's input from a
  `RandomFloatInRange` chain re-rolls that chain for every output read, so the bool you branched
  on and the location you used describe different points. Store the input in a variable first,
  branch on the bool, and use the impure `K2_GetRandomLocationInNavigableRadius` when a *single*
  random evaluation matters.
- **A navmesh point is the ground; a Character's origin is its capsule centre.** Spawning a
  wanderer at a projected nav point without adding the 88 cm half height buries it to the waist.
- **`IsValid` refuses a class pin.** A class reference is a different pin category from an
  object reference; use `IsValidClass`. The failure is a bare "could not connect pins".
- **`SpawnActorFromClass`'s return pin takes its type from its `Class` pin.** A variable typed
  `class of Actor` yields an `Actor` return that cannot be added to an array of a subclass.
  Type the class variable to the class you actually want back.
- **A component added through the SCS is not a property on the CDO.** It is constructed per
  instance, so `get_default_object(bp).get_editor_property("HealthComponent")` is `None`.
  Authored per-Blueprint defaults live on the **subobject template** — reach it with
  `SubobjectDataBlueprintFunctionLibrary.get_object(data)`, which is also where they must be
  written.
- **`NavigationSystemV1` lives in `/Script/NavigationSystem`, not `/Script/Engine`.** The
  Engine path resolves to a *pinless* node rather than an error.
- **`timeout` on a `-game` run fakes a crash.** Killing the process produces
  `Assertion failed: Index>=0 && Index<NumBits [BitArray.h]` / `SIGSEGV` with
  `GracefulTerminationHandler` in the callstack — that *is* the signal handler running while
  the output device flushes, not a gameplay fault. Check the stack for
  `GracefulTerminationHandler` before chasing it.
- **`unreal.log` output does not reach `-stdout` reliably.** Use
  `-forcelogflush -abslog=<path>` and read the file; this is the same buffering caveat the
  navmesh section already notes.

- **Diagnosing a frozen editor:** `sample <pid> 5 -file /tmp/hang.txt`, then read the
  `GameThread` stack — it names the spinning call directly. `ps -o %cpu` separates a spin
  (100%) from a deadlock (0%). Logs are **not** in `Saved/Logs` here; they are at
  `~/Library/Logs/Unreal Engine/OtherworldEditor/Otherworld.log`, with the previous session
  rolled to `Otherworld-backup-<timestamp>.log` at startup.
- **Never call `GameUserSettings.ApplySettings` from gameplay.** It applies *resolution* as
  well, which fires the cvar sinks → `SystemResolutionSinkCallback` →
  `FSceneViewport::ResizeFrame` → `SWindow::SetWindowMode` → `FMacWindow::UpdateFullScreenState`,
  which pumps the Cocoa run loop waiting on a window-mode transition that never completes in
  PIE. The editor hangs at 100% CPU with no log line after `Bringing up level for play`.
  Use `ApplyNonResolutionSettings()`. `verify_graphics_menu.py` asserts ApplySettings appears
  nowhere.
- **`-nullrhi` cannot prove PIE works.** With no real window, `ResizeFrame` has nothing to
  resize, so the hang above passed a clean 70-second headless run. Headless runs verify
  gameplay logic, never anything that touches the window or the viewport.
- **A const `BlueprintCallable` is silently promoted to `BlueprintPure` by UHT.**
  `WasInputKeyJustPressed` and `IsInputKeyDown` are declared `BlueprintCallable` and `const`,
  and their nodes have **no exec pin** — so they are evaluated when something reads their
  output, and there is nothing to wire. Check `has_exec` before concluding a node "never
  runs".
- **Input polled from a component needs a late tick group.** `WasInputKeyJustPressed` reads
  `EventCounts`, which `UPlayerInput::ProcessInputStack` swaps out once per frame during the
  controller's `TG_PrePhysics` tick. A component defaults to `TG_PrePhysics` too, with no
  defined order against the controller. `AHUD` gets away with polling because it ticks later.
- **An enum pin is a literal and cannot be driven by a variable.** `LineTraceSingle`'s
  `DrawDebugType` is the case that bit: "draw the tracer only in debug mode" is not
  expressible on that pin at all, because there is nothing to connect a bool to. A `Select`
  node does not help either — the enum type has no Select. The fix is a separate
  `DrawDebugLine` behind a `Branch`, and every trace's own `DrawDebugType` set to `None`. The
  general rule: if a behaviour has to vary at runtime, it cannot live in a pin literal.

- **Folding a property read into a Branch condition evaluates it on every frame, including the
  frames where the object is null.** A Branch's condition is a pure pull, so
  `pressed AND armed AND Held.Loaded > 0` reads `Loaded` off `Held` whether or not `armed` is
  true — an `Accessed None` every frame the player is unarmed, forever, with the game otherwise
  working perfectly. The fix is to **nest a second Branch** rather than extend the condition:
  inside the first gate, the object has already been checked. This is the same pure-node
  hazard as the NPC melee gate, in its quietest form — nothing breaks, the log just fills up.

- **Storing a computed value matters most when the thing it is computed from is about to
  change.** The reload moves `Min(MagazineSize - Loaded, Reserve)` rounds. Recomputing that
  expression after `Loaded` has been raised returns a smaller number, so the reserve is charged
  less than the magazine gained — a pure-node re-evaluation bug whose symptom is *free
  ammunition*, which no test that only checks "did the reload work" would ever catch. It is
  written once into `ReloadTake` and read back three times.

- **A label sort is not an index sort, and it only breaks at ten.** The generated level
  verifier gathered the wanderers by label prefix and `sort`ed them as strings, then compared
  them pairwise against the expected spawn points. With five that is fine; with ten, `_10`
  sorts between `_1` and `_2`, so every NPC from the second on was compared against its
  neighbour's expected position and **18 checks failed while the placement was perfectly
  correct**. The tell was that all the "got" values were present, just shifted by one slot.
  Sort on the trailing integer.
- **World time in a `-nullrhi -game` run advances by a fixed small step per frame, not by
  wall clock.** Measured: ~0.6 ms of world time per frame whatever the frame rate. So slowing
  the frame rate puts the *game* into slow motion — a PrintString on a component Tick, firing
  from all six health components, dropped a run to ~14 fps and therefore to about **a
  twentieth of real time**. The pack then never crossed the 75 m to kill anyone and a 2.2 s
  delay never elapsed, in runs that looked simply "quiet". This is the probe changing the thing
  it is measuring, and it cost three inconclusive runs before it was spotted. Gate a per-frame
  probe down to one actor, and cross-check world time (`GetTimeSeconds`) against the log's wall
  clock before reading anything into "it did not happen".
- **A test that waits on the game is a test of the game.** The death pause was finally measured
  by killing the player at BeginPlay instead of waiting for the pack, and the kill counter by
  killing the original five at BeginPlay — the counter's own log line is then the whole
  assertion, and the same probe run twice (with and without `DamagedByPlayer`) reads 5 and 0.
  Isolating the thing under test from everything upstream of it turned a 3-minute inconclusive
  run into a 40-second decisive one.
- **When instrumenting a graph with PrintString, splice — do not just connect.** An exec
  *output* holds one link, so `then.try_create_connection(probe)` silently drops whatever
  came next and severs the rest of the chain. Capture the existing destinations first and
  reconnect them after the probe, or every measurement downstream reads zero and looks like
  a product bug.
- **`add_member_variable`'s default value silently does not apply.** It returns True, the
  compiler logs `Can't parse default value '100.0' … Property: Health`, and the property
  stays at **zero** — a health component that starts dead while every declaration reads
  100. UE 5.8 exposes no API for a *member* variable's default (only
  `set_local_variable_default_value`, for locals). Write the value onto the compiled class's
  CDO, recompile to bake it in, and read it back (`_apply_defaults` in
  `build_shotgun_and_health.py`). This was invisible in the graphics menu only because
  `MenuOpen` defaults to false and `Quality` to 0 — both already zero.
- **`delete_subobject` does not cascade, and `rename_subobject` fails silently.** Deleting a
  component root orphans its children; on the next run they still hold the names the new
  parts want, so the renames quietly fail, the parts come back as `StaticMesh1..13`, and the
  character grows a second nameless copy of the weapon every run. Delete the whole subtree
  (descendants are targets too), and assert the name landed after renaming.
- **Subobject handles go stale the moment any sibling is deleted.** Deleting a second handle
  from the same `k2_gather_subobject_data_for_blueprint` batch trips
  `Ensure condition failed: ParentNode` inside `RemoveNodeAndPromoteChildren`. Re-gather
  after every single delete.
- **`bCanEverTick` is not a UPROPERTY** and cannot be set from Python — but it does not need
  to be. `FKismetCompilerContext::SetCanEverTick` turns it on at compile time for any
  Blueprint whose first native parent is `AActor` or `UActorComponent` and whose Tick event
  has its exec pin **connected**. Leave Tick wired or the component silently stops firing.
- Cast nodes come from the palette as `Utilities|Casting|CastTo<ClassName>`, but **only for
  classes already loaded** — load the asset before listing or creating. The output pin is
  named with spaces inserted (`AsBP Health Component`), so match pin names loosely.
  `add_get_member_variable_node(name, class_path)` gives a node with a `self` pin, which is
  how a graph reads another object's variable once it has been cast.
- **UMG layout cannot be authored from Python** in 5.8: `UWidgetBlueprint::WidgetTree` is a
  protected `UPROPERTY`, so `get_editor_property("WidgetTree")` is refused and there is no
  editor subsystem exposing it. A Widget Blueprint's widgets can only be placed by hand. That
  is why the graphics menu is an `AHUD` drawing to the canvas — `DrawText`/`DrawRect` are
  ordinary BlueprintCallable functions, so the whole thing stays scriptable.
- **`FKey` pin defaults are the bare key name**, not struct text. `FKey` overrides
  `ExportTextItem` to write just `KeyName`, so a pin set to `(KeyName="M")` imports back as a
  key literally called `(`. It compiles, it saves, and the key silently never matches at
  runtime. Set the pin to `M` / `One` / `Two` / `Three`.
- `BlueprintEditorLibrary.get_node_title` returns an **empty string** for every node in 5.8's
  Python layer, and `list_all_nodes` hands back objects typed as the `K2Node` base, so
  `isinstance` against a subclass never matches either. Identify nodes by their input-pin
  signature instead (`verify_graphics_menu.py` does this).
- `add_call_function_node` returns a **pinless node, not `None`**, for a function path that does
  not resolve — including paths that exist in C++ but are not `BlueprintCallable`
  (`APlayerController::ConsoleCommand` is one; use
  `KismetSystemLibrary.ExecuteConsoleCommand`). The failure surfaces much later as
  `pin 'self' not found on `. Guard node creation by asserting the node has pins.
- Events other than the placeholders a fresh Blueprint ships with (BeginPlay, Tick) must come
  from the palette via `create_node_from_name` — e.g. `AddEvent|EventReceiveDrawHUD`,
  `AddEvent|EventTick`. `find_event_node` only finds what already exists.
- A builder whose "already authored, reusing" guard has no escape hatch means **no edit to the
  builder ever reaches the asset**. `build_graphics_menu.py` takes `rebuild=True`, wipes the
  graph with `remove_nodes`, and re-creates the event nodes from the palette.
- UE 5.8 renamed the height-fog property to `fog_inscattering_luminance`
  (was `fog_inscattering_color`). Use the `try_set_first([...])` helper pattern.
- Terrain mesh needs Nanite **off** + `CTF_USE_COMPLEX_AS_SIMPLE`, or collision is wrong.
- Generated scripts are built from `textwrap.dedent(f'''...''')` templates —
  **literal braces must be doubled** `{{ }}`.
- Engine sky-dome materials expose no star parameters; that is why `M_NightSky_Starfield`
  is built from scratch (unlit + two-sided + `is_sky`).
- The scanned grass meshes are only **15–32 cm** tall as authored, so knee height comes from
  scaling, not from the asset. The import script divides the target height by the mesh's
  actual bounds height at plant time; never hard-code a grass scale. The offline
  `Grass Upscale Factor` check keeps any species from being stretched past 2.4x, which is
  where blades start to read as coarse.
- Grass HISMs are `NoCollision` (they must not block the player) and cull at 60–90 m.
- UE 5.8 exposes real Blueprint graph authoring to Python (`BlueprintGraphEditor`:
  `add_call_function_node`, `find_event_node`, `try_create_connection`, pin helpers on
  `BlueprintEditorLibrary`). A fresh BP already has a disabled `ReceiveBeginPlay` node —
  find it, don't add it. See `build_npc_blueprints.py` for the working pattern.
- The navigation system **overwrites** `agent_radius`/`agent_height` on a RecastNavMesh with
  its default agent (35/144) when the nav data registers; per-actor values do not survive a
  load. Widen via Project Settings → Navigation System → Supported Agents, not on the actor.
- A headless editor never finishes an async navmesh bake, so generated levels set
  `runtime_generation = DYNAMIC` and the mesh builds at game start. That property *does*
  stick.
- **Never save a RecastNavMesh into a generated level.** A headless editor can't finish an
  async bake, so any nav data saved from it has EMPTY serialised tiles — and at game start the
  engine finds that structurally valid and *reuses* it rather than building. Result: 0 tiles,
  every `MoveTo` fails, NPC frozen. It appears to work right after any nav-bounds change,
  because the parameters then mismatch and the engine logs `Recreating dtNavMesh instance …
  due mismatch in … maxTiles` and rebuilds — then silently breaks again once bounds settle.
  The import script therefore strips every `RecastNavMesh` **immediately before saving** (the
  nav system re-creates one whenever the level is open, so removing it earlier is useless),
  and `Config/DefaultEngine.ini` sets `RuntimeGeneration=Dynamic` as a class default.
  This cannot be asserted from the editor — opening a level always materialises a nav actor.
  The only real gate is the runtime check below.
- **Recast fails silently when the nav volume is too TALL** — no warning, no error, just zero
  tiles and an NPC that cannot move (`InitPathfinding start point not on navmesh`). ±10000 cm
  XY with an 8000 cm vertical span builds **nothing**; the same ±10000 cm with the 4586 cm
  band this terrain actually needs builds and reaches the terrain edge everywhere. Size the
  volume from the **terrain elevation band**, never from map width. The width cap that used to
  sit at ±8500 cm was a misreading of one measurement that changed XY and Z together — and it
  cost the project a 15 m navigation dead zone around the whole map (see **Following to the
  edge of the map**). When a navmesh comes up empty, change *one* dial, rebuild, and project
  points at it; UE 5.8 exposes neither `tile_size_uu` nor a readable tile limit to Python, so
  guessing from the outside is all there is.
- **Measure a navmesh by projecting at it, not by reading its settings.** In a live editor,
  `vol.set_actor_scale3d(...)` → `execute_console_command(world, "RebuildNavigation")` → wait
  → `unreal.NavigationSystemV1.project_point_to_navigation(world, p, None, None, extent)` for
  a fan of headings answers "where does the navmesh actually end" in about a minute, which is
  the only question that matters and is not otherwise readable.
- To watch the NPC actually move, run the map headless and read the log:
  `UnrealEditor-Cmd <uproject> /Game/Maps/<Level> -game -nullrhi -unattended -forcelogflush
  -LogCmds="LogNavigation Verbose" -abslog=<path>` then grep for `Building tile` (should be
  hundreds) and `not on navmesh` (should stop after the first second or two). `-stdout`
  block-buffers and UE writes no `Saved/Logs` under it, so `-abslog` is required.
- **There is no world context in a `-game` Python probe** — `GameplayStatics.get_player_controller(None, 0)` returns None with a RuntimeWarning, and the pawn you would use as a context object is the thing you are asking for. `unreal.find_object(None, "/Game/Maps/Lvl_Forest_200m.Lvl_Forest_200m")` returns the live `UWorld`, and everything else follows from it. Also: `-ExecutePythonScript` is editor-only, so a `-game` boot needs `-ExecCmds="py /path/to/probe.py"`, and the path must contain **no spaces** — nested quoting through the shell mangles it.
- **World time in `-nullrhi -game` advances in tiny fixed steps**, so anything behind a 2 s `Delay` is impractical to observe in a probe. Measure something upstream of the delay instead — the health component's `Health`/`Dead`, not the GameMode's `PlayerDead`.
- **`BEL.list_input_pins` includes the `execute` pin**, so an upstream walk that is meant to find *data* dependencies will follow the exec chain backwards and reach every pure node in the graph. Filter `get_pin_name(pin) != "execute"`, or a check like "exactly one Branch reads `Automatic`" answers "five".
- **`Array_Get`'s displayed node title is the bare word `Get`** — identical to every variable
  getter in the graph. A verifier that matched the feeder of a spawn's Class pin by title found
  nothing and reported "0 weapon spawns" on a graph that had one. Pin sets are the only
  unambiguous handle for a call node: match on `{"TargetArray", "Index"}`, not on the title.
  (`BEL.get_node_title` is still the right tool for *variable* nodes — `Set Loaded`, `Get
  DebugMode` — where the name is in the title.)
- **`_same(None, None)` is `True`, so a mistyped asset path verifies clean.** `_apply_defaults`
  writes `eas.load_asset(path)` and reads it back; a path that resolves to nothing writes `None`,
  reads `None`, and passes — a gun that silently makes no noise, all the way through build,
  verify and ship. Every asset reference written as a default now goes through `_must_load()`,
  which raises on a miss. The general rule: a read-back check is only as good as its ability to
  distinguish "absent" from "absent".
- **An array default comes back as `unreal.Array`, not a `list`**, and its `repr` embeds an
  address, so `str(a) == str(b)` never holds. `_same` compares arrays element-wise through
  itself. Symptom before the fix: `default for DropClasses did not stick: <Array object at
  0x…> != [<Object '/Game/Weapons/BP_SMG…'>, …]` on a write that had in fact stuck perfectly.
- **A `Delay` in a headless `-nullrhi -game` run is measured in world time, which advances by a
  fixed tiny step per frame.** A 3 s delay may never elapse in a 30 s wall-clock session; 0.4 s
  does. Keep probe delays well under a second, and never read a headless run's silence as a
  failure of the thing behind the delay.
