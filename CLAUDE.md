# Otherworld — Claude quick reference

Unreal Engine **5.8** project on macOS. Everything is driven by **Unreal Python** automation;
there is no C++ module. See `systemDesign.md` for the detailed architecture.

## Hard rules

1. **Never** open or edit `.uasset` / `.umap` as text. All asset work goes through the
   `unreal` Python API (or the editor UI).
2. Automation scripts live in `Scripts/` (run headless) or `Content/Python/`
   (auto-discovered by the editor; `init_unreal.py` runs at startup).
3. Asset prefixes: `SM_ SK_ M_ MI_ T_ BP_ WBP_ ST_ A_ Cue_`; levels `Lvl_`.
4. Absolute paths only when invoking the editor — the Bash tool resets cwd between calls.

## Run a script headless

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" \
  "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Otherworld.uproject" \
  -ExecutePythonScript="<abs path to .py>" -NoUI -stdout
```
Logs from generated scripts are prefixed `[GEN]` (import) / `[VERIFY]` (checks).

## The level generator (the main thing here)

`Scripts/generate_forest_level.py` — pure Python, no `unreal` import. It computes terrain,
tree, grass and NPC placement, runs 27 offline checks, then **code-generates** two Unreal
Python scripts into `Scripts/generated_levels/<LevelName>/`.

```bash
python3 Scripts/generate_forest_level.py --size 200 --time-of-day night
# flags: --size <meters, required> --name --seed (42) --grid --time-of-day {day,night}
#        --grass-density (1.2/m²) --grass-height (50 cm) --grass-patchiness (0.25)
#        --no-grass --no-npc --npc-min-distance <m> --json-report
```
Then run the printed `import_<Level>.py` (builds the level) and `verify_<Level>.py`
(103 in-engine checks) through UnrealEditor-Cmd. Generation is deterministic for a given seed.

Grass transforms do **not** live in the generated script — there are tens of thousands of
them, so they go to a gitignored `grass_<Level>.json` sidecar the import script reads.

Support package `Scripts/forest_generator/`: `terrain.py` (heightfield + OBJ),
`tree_placement.py` (`DEFAULT_TREE_SPECS`, scatter), `grass_placement.py`
(`DEFAULT_GRASS_SPECS`, stratified scatter), `npc_placement.py` (NPC spawn point +
**walk speed / nav agent constants**), `verification.py` (offline suite),
`lighting.py` (**time-of-day presets — edit here to tune day/night**).

## The NPC

`Scripts/build_npc_blueprints.py` builds two Blueprints under `/Game/Forest/NPC` **from
Python** — no hand editing — and is idempotent, so re-generating a level reuses them:

- `BP_ForestWandererAI` (AIController). Event graph, authored via `unreal.BlueprintGraphEditor`:
  `BeginPlay → MoveToActor(Get Player Pawn) → Delay 0.5s → back to MoveToActor`.
  `MoveToActor` does the pathfinding, which is what makes it walk *around* trees.
- `BP_ForestWanderer` (Character). Mirrors the **player's** rig exactly — `SKM_Quinn_Simple`
  + `ABP_Unarmed`, mesh at z −89 and yaw 270 — because that combination is known to animate.
  `use_acceleration_for_paths` **must be True**: with it False, `ApplyRequestedMove` sets
  velocity directly and leaves `Acceleration` at zero, and `ABP_Unarmed` gates on
  `GroundSpeed > threshold AND GetCurrentAcceleration() != 0` — so the NPC glides along in its
  idle pose. That is the cause of "moves but never animates"; the mesh/anim_mode dials are not.
  Auto-possessed by the controller above.

Run it standalone with `-ExecutePythonScript` to rebuild the assets after editing it.

## The graphics menu

`Scripts/build_graphics_menu.py` builds `/Game/UI/BP_GraphicsMenuHUD` (parent `AHUD`) and
points `BP_ThirdPersonGameMode.HUDClass` at it. That game mode is `GlobalDefaultGameMode` and
no generated level overrides it, so the menu is in every level without placing an actor or
touching a `.umap`. **M** toggles the panel, **1 / 2 / 3** pick Low / Medium / High.

It also draws the player's HP bar (see "The shotgun and health").

`Scripts/verify_graphics_menu.py` reads the saved assets back — 27 checks. Run it after any
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
`Scripts/verify_weapons_and_combat.py` reads the saved assets back (**68 checks**).
It supersedes `build_shotgun_and_health.py`, which is kept only as history — do not run it.

**Controls:** left click fires · **Q** cycles weapons · **G** drops · **E** picks up.
(1/2/3 and M belong to the graphics menu, so the weapon keys stay clear of them.)

| asset | what it is |
|-------|------------|
| `BP_WeaponItem` | Actor. The base class: every property the weapon component reads (Damage, PelletCount, SpreadDegrees, WeaponRange, MuzzleOffset, GripLocation/Rotation, FireSound, AimPose, SlotColor, DisplayName, Dropped). No geometry, no graph. |
| `BP_Shotgun` | child: 7 primitives, 8 pellets × 9 dmg, 5° cone, 40 m, rifle ready pose |
| `BP_Pistol` | child: 5 primitives, 1 shot × 26 dmg, 1° cone, 60 m, pistol ready pose, different grip angle |
| `BP_WeaponComponent` | on the player: Inventory (5 slots), equip/switch/fire/drop/pick up |
| `BP_HealthComponent` | Health/MaxHealth + death, despawn and respawn |
| `BP_BloodSplash` | 5 emissive spheres that swell over 0.45 s and self-destruct |
| `Audio/A_ShotgunFire`, `A_PistolFire` | synthesised by `Scripts/make_weapon_sounds.py` (pure Python — the project ships no audio and `/Engine` has no usable gunshot) |

**Weapons are Actors, not components.** The old shotgun was a component tree welded to the
character's mesh, which cannot be dropped — there is no way to leave a component behind in the
world. Making a weapon an Actor is what makes drop, pick-up and switching fall out naturally:
equipping is an attach, dropping is a detach. `BP_Shotgun`/`BP_Pistol` derive from
`BP_WeaponItem` so `Inventory` is one typed array and firing reads its stats off whatever is
held, with one cast and no per-weapon branching.

**Equipping is authored once.** `NeedsRefresh` is set by BeginPlay, switch, drop and pick-up;
Tick's last block consumes it and runs the single equip sequence. Weapons are spawned once at
BeginPlay and then hidden/shown, never destroyed, so a weapon keeps its identity across
switches and dropping can hand the very same actor to the world.

**The pellet cone starts at the muzzle**, not the camera. Tracing from the camera is the usual
third-person shortcut, but the camera sits on a boom *behind* the player, which is exactly why
the spread appeared to come from behind their shoulder. The origin is now
`TransformLocation(weapon transform, MuzzleOffset)` and only the *direction* comes from the
camera. `verify_weapons_and_combat.py` asserts a trace is fed by a `TransformLocation` node.

**Death and respawn live on the health component**, driven by three defaults rather than by
subclassing: `DespawnOnDeath` (false on the player, so the player just sits at 0),
`RespawnClass`, and `SpawnOrigin` captured at BeginPlay. At 0 HP the NPC spawns a replacement
on a random navmesh point within 40 m *of where it started* and destroys itself. The
replacement carries the same component with the same defaults, so the cycle sustains itself
with nothing tracking it. `auto_possess_ai` is set to `PlacedInWorldOrSpawned` on
`BP_ForestWanderer` or a spawned wanderer would have no AI controller.

### The ready pose — and why it is a slot, not a state machine

The project ships a full Mannequin set (`MF_Rifle_Idle_ADS`, `MF_Pistol_Idle_ADS`, directional
rifle/pistol walk and jog, aim offsets) but **only one Anim Blueprint**, `ABP_Unarmed`, which
uses none of it. A rifle locomotion state machine cannot be authored from Python: `UBlendSpace`
exposes **no sample-authoring API at all**, so the directional sets cannot be assembled into the
blend spaces such a graph needs.

What *is* possible is playing into a slot. `ABP_Unarmed`'s AnimGraph is
`StateMachine → Slot(DefaultSlot) → ControlRig → Root`, and that slot is **full-body** — played
as-is, an ADS idle freezes the legs and the character slides. So `patch_anim_blueprint()`
inserts a **Layered blend per bone** with a `spine_01` branch filter:

```
StateMachine --+---------------------------> LayeredBoneBlend.BasePose ---+
               |                                                          |--> ControlRig
               +--> Slot(DefaultSlot) ------> LayeredBoneBlend.BlendPose --+
```

`DefaultSlot` becomes upper-body-only, and `PlaySlotAnimationAsDynamicMontage(AimPose,
"DefaultSlot", LoopCount=9999)` puts the arms and chest in the ready pose while the legs keep
walking, running and jumping. One new node, one rewire. It is idempotent (it checks for an
existing `LayeredBoneBlend`) and verified at runtime, not just statically.

**Consequence:** every montage played on `DefaultSlot` is now upper-body-only for this
skeleton. Nothing here plays a full-body montage (the NPC despawns rather than playing a death
animation), but a future death or knockdown animation needs its own slot.
Note also that the shipped `MM_Pistol_Fire_Montage` targets a slot called **"Arms"** which does
not exist in this AnimGraph — it would play at zero weight.

### The HUD

`build_graphics_menu.py` draws, every frame: the player's HP bar (top-left), a projected health
bar over every wanderer, and a 5-slot inventory strip centred along the bottom. Slot colour and
name are read from each weapon's own `SlotColor`/`DisplayName`, so the HUD keeps no list of
weapons to fall out of step with. The strip is laid out from the viewport size so it stays
centred and bottom-anchored at any window size.

## Current state

- The player carries a **shotgun and a pistol**, switchable with Q, droppable with G and
  recoverable with E; both weapons fire with sound, blood and muzzle-origin spread, and the
  character holds the matching ready pose while moving. The NPC has a floating health bar,
  dies at 0 HP and respawns elsewhere on the navmesh. Built by
  `build_weapons_and_combat.py` — 68/68 in-engine checks, 29/29 HUD checks, and a runtime
  `-game` pass with 0 accessed-none in which spawn, attach and the aim montage were all
  confirmed to execute.
- Not verified headlessly, and worth a look in a play session: how the two weapons *sit* in
  the hand, whether the pistol grip angle reads right, and how the blood splash looks.
- `EditorStartupMap` is `/Game/Maps/Lvl_Forest_200m`. `GameDefaultMap` is still
  `/Game/Maps/Lvl_Forest` — a packaged or standalone run boots the old level.
- Branch `night-mode`, clean. Latest commit `e5745e9 night mode initial`.
- `/Game/Maps/Lvl_Forest_200m` is generated in **night** mode: 136 trees / 5 species,
  44,368 knee-high grass clumps / 9 species, one NPC 58 m from the player, moon light
  0.12 lux, emissive starfield sky dome as the ambient light source.
  Offline 25/25 and in-engine 101/101 checks pass.
- **Known pre-existing bug:** `scatter_trees` does no minimum-spacing rejection, so some
  size/seed combinations fail the `Tree Spacing (>100cm)` check (e.g. `--size 300` with the
  default seed 42 gives a 70 cm pair). 200 m/seed 42 and 300 m/seed 99 pass. Unfixed.
- The NPC walks 51.7 m to the player at a measured **100 cm/s** (`max_walk_speed` 110).
- Night-sky dials live in `Scripts/forest_generator/lighting.py`: `star_brightness` (2.5),
  sun `intensity` (0.12), `auto_exposure_bias` (1.6).
- `Scripts/` also holds ~110 older one-off inspect/fix scripts from earlier iterations.
  They are history, not API — prefer the generator + `forest_generator/` package.

## Gotchas learned the hard way

- **`get_basic_type_by_name("float")` silently declares an `int`.** So does `"double"`. The
  only spelling that yields a Blueprint float is **`"real"`**. The one clue is a
  `LogBlueprintEditorLib: Warning: Primitive type: float not recognized, defaulting to int`
  buried in the log; the variable compiles, saves, and reads back correctly for any integral
  default (100.0, 9.0, 4000.0 all survive the round trip), so it surfaces only once something
  needs a fraction. `verify_weapons_and_combat.py` guards this by asserting
  `isinstance(cdo.get_editor_property(var), float)` — an int property hands Python an `int`.
  `build_shotgun_and_health.py` has this bug throughout; it is superseded, not fixed.
- **Struct pins reject `set_pin_value` outright.** Every format for an `FVector` pin
  (`"5,5,5"`, `"(X=5,Y=5,Z=5)"`, `"X=5 Y=5 Z=5"`, …) returns False and leaves the pin empty,
  which the compiler then reads as the **zero vector** — a zero scale on a spawn transform
  makes the actor invisible. Build constants with a `MakeVector` node instead (`_vec()`).
  `LinearColor` pins *do* accept `"(R=…,G=…,B=…,A=…)"`, which is why the HUD's colours work
  and makes the vector case easy to assume works too. The engine logs
  `Failed to set default value … on A`, but `set_pin_value`'s return is the real signal — and
  note it also returns False when the value you set equals the pin's existing default, so a
  False is not always a failure.
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
