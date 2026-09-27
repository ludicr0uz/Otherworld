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
# flags: --size <meters, required> --name --seed (42) --grid --time-of-day {day,night}
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
  `BeginPlay → [possessed? no → Delay] → MoveToActor(Get Player Pawn) → [in reach and off
  cooldown? → swing] → Delay 0.5s → back to the gate`.
  `MoveToActor` does the pathfinding, which is what makes it run *around* trees. The melee check
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

The **spawn band is clamped to the navigable island**, and the clamp is loud rather than silent:
`npc_usable_radius` caps at 80 m on a 200 m map (nav coverage is capped — see
`NAV_MAX_HALF_XY_CM`), so `Lvl_Forest_200m` spawns its ten at **75.0–78.0 m**, and both the
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
samples the furthest was 8512 cm, the navmesh island edge, well inside the ±10000 cm terrain.

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

`Scripts/verify_graphics_menu.py` reads the saved assets back — 60 checks. Run it after any
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

Note the consequence in PIE: these are global cvars, so whichever preset is active when you stop
PIE is what your editor viewport keeps. `r.ScreenPercentage 100` and `r.ShadowQuality 3` restore
it.

## Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds everything under `/Game/Weapons` and installs it;
`Scripts/verify_weapons_and_combat.py` reads the saved assets back (**289 checks**).
It supersedes `build_shotgun_and_health.py`, which is kept only as history — do not run it.

**Controls:** left click fires · **Q** cycles weapons · **G** drops · **E** picks up ·
**Shift** sprints · **R** reloads, and restarts from the death menu.
(1/2/3, M and D belong to the graphics menu, so the weapon keys stay clear of them.)

**R** is shared between reload and restart, and that is safe rather than lucky: Event Tick does
not run while the game is paused, so the weapon component is not listening on any frame the
death menu is on screen. The menu polls its own copy from `DrawHUD`, which *is* renderer-driven
and does run paused.

| asset | what it is |
|-------|------------|
| `BP_WeaponItem` | Actor. The base class: every property the weapon component reads (Damage, PelletCount, SpreadDegrees, WeaponRange, MuzzleOffset, GripLocation/Rotation, FireSound, **DryFireSound, ReloadSound**, AimPose, SlotColor, DisplayName, Dropped, UsesAmmo, MagazineSize, Loaded, Reserve, FireInterval, ReloadSeconds, NextFireTime). No geometry, no graph. |
| `BP_Shotgun` | child: 7 primitives, 8 pellets × 18 dmg, 5° cone, 40 m, rifle ready pose, 5+15 rounds, 0.85 s, 1.6 s reload. **Issued.** |
| `BP_Pistol` | child: 5 primitives, 1 × 26 dmg, 1° cone, 60 m, pistol ready pose, unlimited ammo, 0.18 s. **Issued.** |
| `BP_SMG` | child: 7 primitives, 1 × **12** dmg, 2.6° cone, 45 m, 30+90 rounds, **0.09 s**, 1.9 s reload. **Found only.** |
| `BP_AssaultRifle` | child: 8 primitives, 1 × **24** dmg, 1.4° cone, 90 m, 30+90 rounds, 0.14 s, 2.1 s reload. **Found only.** |
| `BP_SniperRifle` | child: 10 primitives, 1 × **120** dmg, 0.2° cone, 200 m, 5+15 rounds, **1.6 s**, 2.6 s reload. **Found only.** |
| `BP_AmmoPickup` | 2 brass shells a killed wanderer leaves behind; walked into, not pressed for |
| `BP_WeaponComponent` | on the player: Inventory (5 slots), equip/switch/fire/reload/drop/pick up, **sprint + stamina** |
| `BP_HealthComponent` | Health/MaxHealth, the damage stamp, death — despawn and respawn for a wanderer, **the death sequence and the pause** for the player |
| `BP_BloodSplash` | 10 emissive spheres thrown out along the hit normal, arcing down as they swell, over 0.7 s |
| `Audio/A_*Fire` × 5, `A_DryFire`, `A_Reload` | synthesised by `Scripts/make_weapon_sounds.py` (pure Python — the project ships no audio and `/Engine` has no usable gunshot) |

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

At 0 HP the player's health component used to do nothing at all — `DespawnOnDeath` is false
for them, and that arm of the death branch simply ended, so they sat at 0 while the pack kept
swinging. It now runs:

```
DisableMovement -> MM_Death_Front_01 into FullBodySlot -> Delay 2.2s
    -> GameMode.PlayerDead = true -> "[PLAYER-DEAD] killed with N" -> SetGamePaused(true)
```

Four things in that order, each for a reason:

- **DisableMovement, not DisableInput.** The body has to stop where it fell, but the HUD polls
  the restart key off the same PlayerController, and turning input off risks it.
- **`FullBodySlot`, a second slot.** `DefaultSlot` is filtered to the upper body so the aim
  pose leaves the legs walking (see the ABP patch), and a death played into it folds the chest
  over legs that are still standing. The new slot sits **after** the layered blend, where it
  overrides everything. Getting one made from Python has a trick to it — see the gotcha below.
- **The delay comes before the pause.** `MM_Death_Front_01` runs about 1.9 s; pausing on top of
  it freezes the player mid-stumble, which reads as a hang rather than as a death.
- **The log line exists because the menu cannot be seen headlessly.** A paused game and a game
  where the death path silently did nothing produce identical logs otherwise.

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

### Blood

Ten emissive spheres in a cone, and the **actor** is animated rather than the spheres:

```
position = Origin + Forward * 130 cm/s * Age - Z * 260 * Age^2
scale    = 0.55 + Jitter + 2.6 * sin(pi * Age / 0.7)
```

`_author_impact` spawns the splash rotated so its forward **is the surface normal it hit**
(`MakeRotFromX`), so blood comes out of the wound rather than along a world axis, and a shot to
the chest and one to the back throw it opposite ways. The parabola is what makes it read as
blood instead of an expanding ball; the sine does grow-then-vanish in one pure expression, with
no branch and no Timeline (whose curve asset cannot be authored from Python). `Jitter` is one
`RandomFloatInRange` **stored in a variable** — pure, so a second read would be a second dice
roll, and without it a shotgun's eight pellets into one torso read as a single big sphere.

The cone layout is generated from a fixed seed at build time, which is how the verifier can
recompute it and compare component by component.

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

### Weapon sounds, including the two that are not shots

`Scripts/make_weapon_sounds.py` is pure Python and synthesises all seven WAVs. The five gunshots
come from `_shot()` — crack (bright noise, fast decay) + body (low-passed noise) + thump (a sine
swept downward) — differing only in tail length and thump depth. Broadly: the longer and deeper
the tail, the bigger the gun. The SMG is almost all crack (0.26 s, because at 0.09 s between
rounds a longer tail turns a burst into mush); the sniper is almost all boom (1.30 s).

The other two are **mechanical**, and come from a different generator. A hammer falling on an
empty chamber and a shell going into a tube are metal hitting metal with no powder behind them,
so `_clack()` lays one or more damped metallic *rings* into a buffer at given offsets. The ring
is what makes it read as metal — noise alone is a pop. `A_DryFire` is one event at 2.8 kHz over
0.14 s; `A_Reload` is three (two shells in, then the pump closing) over 0.9 s, so the sound
finishing is roughly the cue that the weapon is live again.

Both are **shared by every weapon** — one hammer sounds much like another — but they still live
on `BP_WeaponItem` as `DryFireSound` / `ReloadSound` rather than on the component, because that
is a fact about the *defaults* and not about the shape of the data. The graphs read all three
sounds off `Held`, so a new weapon stays a row in `_weapon_specs()`.

**Where each one is gated is the whole design:**

- **The click** hangs off the False arm of the ready gate — the one place that knows the trigger
  was pulled and the shot did not happen. Two reasons lead there and only one deserves a sound,
  so the condition is `empty AND cooled`, not just `empty`. Clicking while merely between shots
  would click on most frames of a held SMG trigger. No cooldown is stamped: `FIRE_KEY` is polled
  with `WasInputKeyJustPressed`, so one click of the mouse is one click of the hammer.
- **The clack** plays on the True arm of the reload only. On the False arm — an unlimited weapon,
  or a full magazine — nothing moves, and a sound there would be the game claiming it had done
  something it had not, while the pause that normally follows a reload also would not happen.

### Debug mode

One bool on the GameMode (`DebugMode`), toggled with **D** in the graphics menu, **off by
default**. It turns on the two developer overlays: the **pellet tracers** drawn from the muzzle,
and the **wanderer's number** beside its health bar. Both are instrumentation, and
instrumentation is not what the game looks like.

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
  `build_weapons_and_combat.py` — **187/187** in-engine checks, **60/60** HUD checks.
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
  transition or like a pop.
- `EditorStartupMap` is `/Game/Maps/Lvl_Forest_200m`. `GameDefaultMap` is still
  `/Game/Maps/Lvl_Forest` — a packaged or standalone run boots the old level.
- Branch `night-mode`, clean. Latest commit `e5745e9 night mode initial`.
- `/Game/Maps/Lvl_Forest_200m` is generated in **night** mode: 136 trees / 5 species,
  44,368 knee-high grass clumps / 9 species, **ten NPCs at 75.0-78.0 m** from the player,
  moon light 0.12 lux, emissive starfield sky dome as the ambient light source.
  Offline 28/28 and in-engine 141/141 checks pass.
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
- **Recast fails silently when the nav volume is too big** — no warning, no error, just zero
  tiles and an NPC that cannot move (`InitPathfinding start point not on navmesh`). Measured
  envelope: ±8500 cm XY with a 1500 cm vertical span builds 176–324 tiles and works;
  ±9200 cm / 2007 cm builds **nothing**. `NAV_MAX_HALF_XY_CM` and
  `NAV_MAX_VERTICAL_SPAN_CM` in `npc_placement.py` encode that. Size the volume from the
  **terrain elevation band**, sampled over a *disk*, never from map width — the square's
  corners sit 1.41x further out where this terrain's edge ramp is ~40 m tall.
- To watch the NPC actually move, run the map headless and read the log:
  `UnrealEditor-Cmd <uproject> /Game/Maps/<Level> -game -nullrhi -unattended -forcelogflush
  -LogCmds="LogNavigation Verbose" -abslog=<path>` then grep for `Building tile` (should be
  hundreds) and `not on navmesh` (should stop after the first second or two). `-stdout`
  block-buffers and UE writes no `Saved/Logs` under it, so `-abslog` is required.
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
