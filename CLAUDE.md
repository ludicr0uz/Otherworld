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

`Scripts/verify_graphics_menu.py` reads the saved assets back — 21 checks. Run it after any
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

## Current state

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
