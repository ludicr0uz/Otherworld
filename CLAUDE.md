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
tree and grass placement, runs 19 offline checks, then **code-generates** two Unreal Python
scripts into `Scripts/generated_levels/<LevelName>/`.

```bash
python3 Scripts/generate_forest_level.py --size 200 --time-of-day night
# flags: --size <meters, required> --name --seed (42) --grid --time-of-day {day,night}
#        --grass-density (1.2/m²) --grass-height (50 cm) --grass-patchiness (0.25)
#        --no-grass --json-report
```
Then run the printed `import_<Level>.py` (builds the level) and `verify_<Level>.py`
(84 in-engine checks) through UnrealEditor-Cmd. Generation is deterministic for a given seed.

Grass transforms do **not** live in the generated script — there are tens of thousands of
them, so they go to a gitignored `grass_<Level>.json` sidecar the import script reads.

Support package `Scripts/forest_generator/`: `terrain.py` (heightfield + OBJ),
`tree_placement.py` (`DEFAULT_TREE_SPECS`, scatter), `grass_placement.py`
(`DEFAULT_GRASS_SPECS`, stratified scatter), `verification.py` (offline suite),
`lighting.py` (**time-of-day presets — edit here to tune day/night**).

## Current state

- Branch `night-mode`, clean. Latest commit `e5745e9 night mode initial`.
- `/Game/Maps/Lvl_Forest_200m` is generated in **night** mode: 136 trees / 5 species,
  44,368 knee-high grass clumps / 9 species, moon light 0.12 lux, emissive starfield sky
  dome as the ambient light source. Offline 19/19 and in-engine 84/84 checks pass.
- Night-sky dials live in `Scripts/forest_generator/lighting.py`: `star_brightness` (2.5),
  sun `intensity` (0.12), `auto_exposure_bias` (1.6).
- `Scripts/` also holds ~110 older one-off inspect/fix scripts from earlier iterations.
  They are history, not API — prefer the generator + `forest_generator/` package.

## Gotchas learned the hard way

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
