# Otherworld — Claude quick reference

An Unreal Engine **5.8** project on macOS, driven entirely by **Unreal Python** automation.
The game is authored by those scripts; the C++ in `Source/` is small (a runtime module with
the player's predicted movement states, and an editor module of helpers for the scripts) and
must be compiled before the editor opens (`Source/CLAUDE.md`).

## Where things are written down

Four kinds of document, each with one job. Put a fact where a reader will need it, and
nowhere else; a second copy goes stale.

| document | holds | read when |
|---|---|---|
| this file | what every change needs: the hard rules, the code layout, how to run and verify a script, the gotchas that bite in any package; and the table below, which says where each system's notes are | always (it is loaded in every session) |
| `Scripts/<package>/CLAUDE.md` (and `Source/CLAUDE.md`) | what a change inside that system needs: its design rules, its files, its traps, its verifiers and probes. A package's `docs/*.md` are its topic notes, read only for the topic in hand; its `docs/history/` file is what each feature built, measured and proved, moved there word for word | before changing anything in that package |
| `systemDesign.md` | the high-level design: what the game is today, system by system (section 0, kept current), how the pipelines fit together, and the long-term architecture; the detail that a small change does not need | a change that spans systems, or the long view |
| `serversupportsysdesign.md` and the other root `*.md` plans | the strategy and the plan for one long piece of work | working on that piece |

A task that changes what the game does updates `systemDesign.md` section 0 and the owning
package's `CLAUDE.md`; it adds to this file only a rule that applies in every package.

## Hard rules

1. **Never** open or edit `.uasset`/`.umap` as text. Go through the `unreal` Python API.
2. **Where scripts live:**
   - `Scripts/` holds builders, verifiers and generators.
   - `Scripts/dev/` holds editor tooling:
     - `uepy.py` runs scripts (its pieces are `uepylib/`);
     - `dev-team` runs a queue of tasks, one headless Claude session each (its pieces are
       `devteam/`). A session started that way has no one to ask, so it decides and reports
       instead. The one exception is a Fab asset (see "Fab assets" below).
       It reads the task file again after each task, so an item added to `tasks.md` during a
       run is run in that run, and a waiting one ticked or deleted there is not.
     - Probes are opt-in for a run (`--probes [SET]` sweeps one after the last task;
       `--gate-probes SET` beside the verifiers after every task; `Scripts/probes/sets.py`):
       measured 8-10 Oct 2026, they cost 21 hours of launches for three defects found, while
       the verifiers found more in minutes. A session writes and runs a probe only for a
       change no verifier or unit test can see. The existing probes are swept nightly, apart
       from dev-team: `dev-team probes run [SET]` (FULL unless named; `devteam/nightly.py`),
       which writes the record (`dev-team probes` lists it) and a report under
       `Saved/DevTeam/probes-<stamp>/`. A probe that fails in its batch is re-run alone and
       the solo verdict stands (`devteam/probe_gate.py`).
     - Their unit tests: `python3 -m unittest discover -s Scripts/dev/tests`. Run them after
       changing anything in `Scripts/dev` or `Scripts/probes`.
   - `Scripts/probes/` holds probes: checks that run inside a headless game (see below).
   - `Content/Python/` is auto-loaded by the editor. `init_unreal.py` starts `uepy_inbox`.
3. **Asset prefixes:** `SM_ SK_ M_ MI_ T_ BP_ WBP_ ST_ A_ Cue_`. Levels use `Lvl_`.
4. **Use absolute paths when invoking the editor directly,** because the Bash tool resets cwd.
   `uepy.py` resolves relative paths itself.
5. **Keep modules small** (see below). Split a module before adding to one that is over budget.
6. **Before changing a system, read its package's `CLAUDE.md`.** It holds the design rules and
   traps for that system:

   | system | entry points | read |
   |---|---|---|
   | weapons, inventory, the glimmer over an item on the ground, health, death, blood, bullet impacts, audio, hit boxes, chopping trees for wood, the matches, the use key and the stick that burns, the knife or axe heated at a fire, the grip nudges (a CSV row per held item the running game reads: `Content/Tuning/grip_nudges.csv`, `combat/docs/aiming.md`) | `build_`/`verify_weapons_and_combat.py` | `Scripts/combat/CLAUDE.md` |
   | NPCs: behaviour tree, pack, patrol and agro, how many a server keeps (a budget that follows the players) | `build_`/`verify_npc_blueprints.py` | `Scripts/npc/CLAUDE.md` |
   | the menu (the title's, and M's in play), graphics presets and tuning, settings, HUD; the tuning tabs by mode (M32: a client's gameplay tables are the server's, `BP_GameTuner`, `-AllowDevTuning`) | `build_`/`verify_graphics_menu.py` | `Scripts/graphics_menu/CLAUDE.md` |
   | survival: GAS, debuffs, on-hit effects and bleeding, forage, the campfire | `build_`/`verify_survival.py`, `place_forage.py` | `Scripts/survival/CLAUDE.md` |
   | level generator, navmesh, trees and grass | `generate_forest_level.py` | `Scripts/forest_generator/CLAUDE.md` |
| day and night: world config, sun, moon, sky | `build_`/`verify_day_night.py` | `Scripts/world/CLAUDE.md` |
| the title level: the stage the game opens on with no forest loaded (`Lvl_Title`, `GameDefaultMap`), its camera, lights and floor; the figure on it, the player's character in the saved profile's garments (`graphics_menu/title_figure.py`); New Game opening the forest, save and exit coming back | `build_`/`verify_title_level.py`, `probes/probe_title_figure.py` | `Scripts/title/__init__.py`, `Scripts/graphics_menu/CLAUDE.md` ("One menu") |
| corpse loot: loot tables, the roll, the loot window | `build_survival.py` (tables), `probe_corpse_loot.py` | `Scripts/loot/CLAUDE.md` |
| item icons: each item's inventory icon, rendered from its 3D model; the I panel's portrait of the character | `build_item_icons.py` (run outside the editor) | `Scripts/item_icons/CLAUDE.md` |
| generated bodies: describing one, the rig check, the import that normalises it, swapping the player onto it | `asset_pipeline/fetch_monsters.py`, `rig_compat.py`, `swap_player_body.py` | `Scripts/asset_pipeline/CLAUDE.md` |
| the Game Animation Sample (the motion-matching clips, databases and anim blueprint, copied under `/Game/GAS`; the player's base movement since G3): what came across, the redirects it loads by, the four packages patched after the copy, the plugins and settings it needs | `asset_pipeline/import_gas.py`, `gas_paths.py`, `check_gas_load.py` | `Scripts/asset_pipeline/CLAUDE.md` ("The Game Animation Sample") |
| the player's melee clips (C2): the knife's and the axe's swing and ready pose are Mixamo's (the downloads in `assets/cache/mixamo`, `mixamo_paths.PLAYER_CLIPS`), retargeted onto the player's skeleton and baked into `/Game/Weapons/Anims` with the right fist closed and each swing cut to strike when the timed blow lands; how the swing picks the axe's clip on every machine (the ready pose in hand); one command to try another download in a role (`Scripts/dev/swap_clip.py <role> <fbx>`, the rows of `asset_pipeline/player_clips.csv`) | `dev/swap_clip.py`, `asset_pipeline/import_mixamo_player.py`, `mixamo_player.py`, `player_clips.py`, `combat/melee_clips.py`, `combat/verify/melee_clips.py` | `Scripts/combat/CLAUDE.md` ("The melee clips") |
| Lyra (the user's copy under `/Game/Sourced/Lyra`, a Fab pack, not committed; the redirect it loads by; which of its clips the game plays, retargeted onto the player's skeleton: the punch, and the guns' ready poses, its rifle and pistol ADS idles) | `asset_pipeline/import_lyra.py`, `lyra_paths.py`, `combat/shotgun_hold.py` | `Scripts/asset_pipeline/CLAUDE.md` ("Lyra"), `Scripts/combat/CLAUDE.md` ("The gun poses") |
| the skeleton bridge (how the GAS clips reach the MetaHuman: the hidden mesh is the sample's UEFN mannequin, `SKM_UEFN_Player`, with a second retargeter from it; worn by the game since G3): the choice, what it costs the sockets, the clips and the hit bodies | `asset_pipeline/build_gas_bridge.py`, `gas_player_mesh.py`, `measure_gas_bridge.py`, `probes/probe_gas_idle.py` | `Scripts/asset_pipeline/CLAUDE.md` ("The skeleton bridge") |
| the player's base movement: motion matching (the sample's anim blueprint patched where it lies to read our CharacterMovementComponent; the one switch `GAS_LOCOMOTION`; its own server branch; the silent foley component; what it costs in memory) | `combat/gas_locomotion.py`, `gas_locomotion_consts.py`, `combat/skin.py`, `probes/probe_gas_locomotion.py`, `probe_net_gas_locomotion.py` | `Scripts/combat/CLAUDE.md` ("The motion-matching base") |
| the weapon layers over it (G4): everything a weapon, a stance or a hit does to the body is a second anim blueprint, `ABP_WeaponLayers`, linked into the motion-matching one (`PlayerSkin.anim_bp` against `base_anim_bp`); how a graph or a probe reaches its instance (the tag, `p.pose_instance`); the game's clips retargeted onto the UEFN skeleton; why no clip played into a slot may have root motion | `combat/weapon_layers.py`, `weapon_layers_consts.py`, `combat/verify/weapon_layers.py`, `asset_pipeline/retarget_to_uefn.py` | `Scripts/combat/CLAUDE.md` ("The weapon layers") |
| crouch, slide and traversal from the sample (G5): the crouch as the motion matching's own Stance, the slide (a fourth predicted state of the C++ movement, posed by the sample's slide loop), the sample's traversal component behind the jump key; one switch each (`GAS_CROUCH`, `GAS_SLIDE`, `GAS_TRAVERSAL`); why the sample's montage slot is in the pose line only while a traversal plays; what is not proven on a server | `combat/gas_moves_tuning.py`, `gas_moves.py`, `gas_traversal.py`, `gas_traversal_slot.py`, `combat/verify/gas_moves.py`, `probes/probe_gas_traversal.py`, `probe_net_slide.py` | `Scripts/combat/CLAUDE.md` ("Crouch, slide and traversal from the sample") |
| clothing: the eight garments, wearing and taking off, the three drawn on the MetaHuman when worn (to every client on a server, and kept by a saved profile), the I panel, the test garments | `build_`/`verify_clothing.py`, `probe_clothing.py` | `Scripts/clothing/CLAUDE.md` |
| sound: every sound of the game, which Blueprint variable plays which takes, how far each carries, how loud each is, the beds, the player's voice, the listener | `build_sound.py` (the one build after a change to any of them) | `Scripts/Sound/CLAUDE.md` |
| sourcing sounds: the fetchers and the synthesiser, cutting candidates from the downloaded packs, the page that plays and rates them (all run outside the editor) | `Scripts/Sound/*.py` | `Scripts/Sound/sound_candidates/__init__.py` |
| input: the fire key as an Enhanced Input action (I1: `IA_Fire` and the game's own `IMC_Default` under `/Game/Weapons/Input`, added and bound by the native character, taken by the weapon component as a stamp its Tick reads; rebinding rewrites the context's key); every other key is still polled | `combat/input_assets.py`, `input_consts.py`, `combat/weapon_component/trigger.py`, `combat/verify/trigger.py`, `probes/probe_fire_action.py`, `probe_net_fire_action.py` | `Scripts/combat/CLAUDE.md` ("The fire key is not polled"), `Source/CLAUDE.md` ("The fire action") |
| predicted movement: sprint, prone and the aim-walk, their speeds and the stamina, decided by the player's C++ movement component on the owning client and the server alike; what a graph may hand it and read off it, the reparented player character, the correction count | `combat/player_move.py`, `uebp/nodes/move.py`, `probes/probe_net_move_states.py` | `Source/CLAUDE.md` ("Predicted movement"), `Scripts/combat/docs/stance.md` |
| the C++ modules: the `Otherworld` runtime module (the player's movement component; the history of hit boxes and the rewound shot trace; the load test's counters; the RPC guard; the weapon component's native parent, `UOtherworldWeaponComponentBase`, which holds the shot's server half: `Server_Fire`, the pellets' traces and their damage, W1; and the reload: `Server_Reload`, `ReloadNow` and how many rounds move, W2; the health component's, `UOtherworldHealthComponent`: `TakeHit`, `Die`, `Health` and `Dead` as RepNotify properties, the events `OnHealthChanged` and `OnDied` the graph hangs on, W3), the editor-only `OtherworldEditor` (what the builders need and Python cannot reach) and the Editor, Game, Client and Server targets; the compile command, its time and the Xcode it needs | `Source/Otherworld/Otherworld.Build.cs`, `Source/OtherworldEditor/`, `Source/*.Target.cs` | `Source/CLAUDE.md` |
| the two modes on the title: the Single Player and Multiplayer pages, the server address, joining and leaving a server, the reason a join failed, the session kept on the GameInstance | `graphics_menu/mode_tick.py`, `net/game_instance.py`, `probes/probe_net_title.py` | `Scripts/graphics_menu/CLAUDE.md` ("The two modes"), `Scripts/net/CLAUDE.md` |
| the asset browser: one HTML page of every static and skeletal mesh in the project (found by the asset registry at each run, nothing listed), in tabs (environment, structures, weapons, items, clothing, characters), its picture (photographed in the editor, lit outside it; a click opens it large, where a drag turns the mesh through 16 views shot round it), its triangles (Nanite and LOD 0), size, and the levels that use it; the category and the kind guessed from the path (`map_assets/kinds.py`) | `build_map_asset_browser.py --open` (run outside the editor), `scan_map_assets.py` | `Scripts/map_assets/__init__.py` |
| multiplayer conventions: authority, where state lives, Server events and the RPC guard, `Fx_`/`Multicast_` pairs, relevancy, what a dedicated server poses, writing a `--net` probe, the numbers at scale | `net/`, `probes/probe_net_*.py` | `Scripts/net/CLAUDE.md` |
| networked Blueprints: Server / Client / Multicast custom events, Replicated and RepNotify variables, actors and components that replicate, the nodes that ask which machine this is | `uebp/net.py`, `dev/check_net_authoring.py` | `Scripts/uebp/CLAUDE.md` |
| multiplayer: the strategy (`serversupportsysdesign.md`; section 4.8 is the rule that single player and multiplayer both ship, from one code path, chosen on the title menu), the task queue (`Scripts/dev/plans/multiplayer_tasks.md`), the GCP build VM and the engine source build | `Scripts/server/gcp/vm_create.sh`, `engine_clone.sh`, `engine_build.sh`, `vm.sh` | `Scripts/server/gcp/CLAUDE.md` |

## Code layout: small modules, one owner each

An agent pays for a file every time it reads it, and the old one-file weapons builder cost
sessions tens of millions of tokens.

**Budgets:**
- A module stays under **~500 lines**.
- A function stays under **~150 lines**. A graph-authoring `build_*`/`_author_*` function may
  reach ~250.
- Past a budget, split before adding. Either extract an `_author_<thing>(ed, exec_in, …)` fragment
  that returns the pins its caller wires on (e.g. `respawn._author_world_floor_net`), or move
  functions into a sibling module.

**Shape of a feature:**
- **Entry point:** `Scripts/<verb>_<feature>.py` is **thin**: path setup, purging cached project
  modules, and a `main()` that calls the steps in order.
- **Package:** the code lives in a package with one module per responsibility, named after what
  it owns: one Blueprint, one graph concern, or one constants table (`tuning.py`, `paths.py`,
  `<blueprint>_vars.py`). Constants modules stay separate from the modules that author graphs.
- **The map:** the package's `__init__.py` docstring lists every module in one line each. Keep it
  current (the dev unit tests fail a map that misses a module or names one that is gone;
  `python3 Scripts/dev/package_map.py --fix <package>` appends what is missing). Each module's
  docstring says what it owns and why.
- **Explicit imports only.** No `import *` and no re-exporting facades.
- **No import cycles.** Imports flow constants → `uebp` → builders → entry point.
- **Verifiers mirror builders.** `verify/<area>.py` holds self-contained `check_*` functions.
  Values shared between sections go in `verify/fixtures.py`, and no section reads state that
  another section left behind.

**Working in it:**
- Find the owner from the `__init__` map. `grep -n <name> Scripts/dev/symbols.txt` is the
  symbol index (every def, class and constant under `Scripts/`, every UCLASS/UFUNCTION under
  `Source/`; the pre-commit hook refreshes it). Grep it first, and batch independent reads
  into one command.
- **Moving code:** move it verbatim, then check that the verifier reports the same count and the
  same check lines as before.

**Over budget today** (split before extending):
- `build_graphics_menu.py` (1.2k lines)
- `generate_forest_level.py` (1.8k)
- `verify_graphics_menu.py`
- `forest_generator/verification.py`

**Stale imports:** the editor's Python outlives each job. `uepy_inbox` forgets `Scripts/` modules
before each job, and the entry points purge their own packages. An editor started before that
change needs its inbox hot-reloaded (see below).

## `Content/` is a Git LFS snapshot

**`Content/` is committed through Git LFS** (`.gitattributes`: every `.uasset` and `.umap` under
it), so a clone opens without a rebuild. A fresh clone needs `git lfs install` once. The scripts
stay the source: every asset is either stock engine content or written by a script, and a rebuilt
asset is committed like any other change. `forest_generator/asset_sources.py` maps each `Content/`
directory to whatever produces it:

| kind | restored by | verified by |
|---|---|---|
| stock (ships with UE 5.8) | `sync_assets.py --restore-stock` | sha256, `stock_checksums.json` |
| generated | the builder named in the table | the verifier suite |
| cache (downloads, git-ignored `assets/`) | e.g. `fetch_weapon_sounds.py` | the fetcher's report |
| fab (`Content/Fab`, packs in `/Game/<Pack>`) | **the user, by hand** (see below) | `fab_library.py --check` |

```bash
python3 Scripts/sync_assets.py --status | --plan | --restore-stock | --verify
```

**Three stock files are patched by builders:** `ABP_Unarmed`, `BP_ThirdPersonCharacter` and
`BP_ThirdPersonGameMode`. They are restored by copying and verified by the suite, never by
checksum, because a recompile isn't byte-deterministic.

### Fab assets: only the user can acquire them

Official models, animations and Megascans come from Fab through the Fab plugin
(installed in UE 5.8, imports under `/Game/Fab`) or the launcher's "Add to project"
(a pack lands in `/Game/<Pack>`). That needs the user's Epic sign-in, so:

- **Never** sign in, drive the Fab plugin or its browser, download from fab.com, or
  substitute a stand-in for an asset the task needs. Searching fab.com to pick a
  listing is fine.
- **Check what's already there first:** `assets/cache/fab/index.md` (library, counts,
  each skeleton and whether it has the mannequin's bones) and `index.json` (one asset
  per line: grep it). Rebuild with `uepy.py Scripts/asset_pipeline/fab_index.py`.
- **Need one that isn't there?** Ask the user for it and wait. In a dev-team session,
  end the report with `FAB-REQUIRED:` and one line per asset
  (`<name> | url: <listing> | at: /Game/<folder> | why: <reason>`). dev-team asks the
  user, records it and resumes the session (`Scripts/dev/devteam/fab.py`). A task can
  also declare `fab: <same line>` in `tasks.md` to be asked before it starts.
- **A downloaded pack is scanned before it reaches `Content/`:**
  `python3 Scripts/asset_pipeline/fab_scan.py <folder holding the pack's Content/> [--promote]`.
  The user adds the pack to a throwaway project (or leaves it in the vault cache,
  `/Users/Shared/UnrealEngine/Launcher/VaultCache/<pack>/data`), never straight to this one.
  The scan blocks anything that is not content (scripts, binaries, config, `Content/Python`),
  checks a vault pack against Epic's manifest, and lists assets that name Python, editor
  utilities, console commands or the network for a person to look at. `--promote` copies a
  clean pack to the same `/Game` path and never overwrites; `--verify` compares `Content/`
  with what was scanned. Code plugins are out of its scope.
- **A raw download has no `Content/`** (a listing taken as FBX, OBJ, GLB or USD: meshes and
  textures in the launcher's `VaultCache/FabLibrary/<Title>-<id>/`). It is checked and
  copied to `assets/cache/fab/raw/` by `fab_raw_scan.py <part of its name> --stage`
  (`--list` shows what the launcher holds; `--parts` keeps a kit's objects apart), then
  imported to `/Game/Fab/<Title>` by `uepy.py Scripts/asset_pipeline/fab_raw_import.py`,
  which records the listing too. Materials are guessed from the textures' file names and a
  USD stage comes in as its parts: read the `LOOK` lines of the log
  (`Scripts/asset_pipeline/fab_raw/__init__.py` is the map).
- **What's been acquired** is `Scripts/asset_pipeline/fab_library.json` (tracked: the
  restore recipe, since the imported assets are not committed). The user records an
  addition with `fab_library.py --add <name> --url <listing> --at /Game/<folder>`.
- **Licences:** each entry records the listing's licence (`--license`). Don't ship an
  asset whose entry has none; ask the user what it is.

**Everything that isn't code goes in git-ignored `assets/`.** Never commit an archive: GitHub
rejects files over 100 MB. After a fresh clone, arm the guard:
`git config core.hooksPath Scripts/dev/hooks`. The pre-commit hook refuses files over 5 MB and
content extensions unless Git LFS tracks them (override with `--no-verify`); the pre-push hook
beside it uploads the LFS objects.

## Run a script — fast

**Default to `Scripts/dev/uepy.py`.** A cold `UnrealEditor-Cmd` costs 35–45 s of boot however
little the script does. `uepy.py` runs the script inside the **already-open editor** in about
0.25 s, and cold-boots only when no editor is listening.

```bash
python3 Scripts/dev/uepy.py Scripts/build_npc_blueprints.py
python3 Scripts/dev/uepy.py Scripts/verify_weapons_and_combat.py Scripts/verify_graphics_menu.py  # one connection
python3 Scripts/dev/uepy.py -c "import unreal; unreal.log_warning('hi')"
python3 Scripts/dev/uepy.py --list                 # which editors are listening
python3 Scripts/dev/uepy.py --game --seconds 25    # headless -game run + error summary
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_consume_heal.py   # see below
python3 Scripts/dev/uepy.py --probes-for [paths]   # the probes a change can affect (default: git diff); detaches itself, --wait the run dir for one verdict table; --dry-run lists them
python3 Scripts/dev/uepy.py --verify-for [paths]   # only the verifiers a change maps to (default: git diff), warm; "none" for probes, docs, Scripts/dev
python3 Scripts/dev/uepy.py --game --windowed --probe <probe>   # rendered, in a 1280x720 window
python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_join.py   # a server and 2 clients, see below
python3 Scripts/dev/uepy.py --net --clients 1 --lag 120 --probe Scripts/probes/probe_net_move_states.py   # with 120 ms of lag
python3 Scripts/dev/uepy.py --net --clients 2 --bots 32 --trace --probe Scripts/probes/probe_net_load.py   # the load test: 32 server-driven bots, an Insights trace
python3 Scripts/dev/uepy.py --net --clients 2 --server-arg AllowDevTuning --probe Scripts/probes/probe_net_dev_tuning.py   # the server alone gets -AllowDevTuning
python3 Scripts/dev/uepy.py --game --title --probe Scripts/probes/probe_title_single.py   # the real title menu, see below
python3 Scripts/dev/uepy.py --net --clients 2 --detach --probe P   # start a --game/--net run, print its run dir, return at once
python3 Scripts/dev/uepy.py --wait <run dir> [--timeout S]       # block for its report (exit code of the run; fails on timeout)
python3 Scripts/dev/uepy.py --status               # detached runs (one at a time: a second --detach refuses)
python3 Scripts/dev/uepy.py --cold <script>        # force a fresh editor
python3 Scripts/dev/uepy.py --summary <scripts>    # one line per script + its failures
python3 Scripts/dev/uepy.py --close-editors        # save + quit this project's editors
```

- **Output:** `--summary` prints one line per script (verifier counts, time), then its failed
  checks, traceback tails and Python errors. The full output is saved under `Saved/uepy/runs/`
  and its path printed. Prefer it to piping through grep and tail. `--full` prints everything.
  `$UEPY_OUTPUT=summary` makes summary the default; dev-team sets it.
- **Exit code:** non-zero if any target raised **or any verifier reported a failed check**.
  The suites return normally when checks fail, so before this a failing sweep exited 0.
- **`$UEPY_COLD=1`** forces every run cold.
- **`$UEPY_SERVE=<dir>`** gives the caller a warm editor of its own: the first call boots a
  headless `UnrealEditor-Cmd` serving the inbox in `<dir>` (`uepylib/server.py`,
  `uepy_inbox.serve()`), later calls reuse it. dev-team sets it per session
  (`Saved/uepy/devteam`), closes the project's editors before each task, and stops the warm
  one before each verifier sweep.
  If a script crashes or hangs that editor, `uepy.py` kills it, boots a fresh one and runs the
  script again by itself (`uepylib/warm.py`), saying so in one line; don't kill or restart it by
  hand. A script it still reports as failed took two editors down in a row.
- **`--game`** counts `Blueprint Runtime Error`, `Accessed None`, `NPC-SPAWN` and `NPC-FELL`,
  and `INVENTORY-RECORD-STALE` (in `--net` too): what a player carries changed and nothing
  marked its record (`Scripts/combat/dirty.py`). Any of the last fails the run.
- **`--title`** (with `--game` or `--net`) keeps the title menu for a probe to work:
  `docs/headless_runs.md#title`.
- **`--net --clients N [--windowed] [--probe <probe>] [--seconds S]`** is the multiplayer
  check (`uepylib/net.py`): one dedicated server (the editor binary, `-server`) on `--map`
  (default `Lvl_Forest_200m`) and N clients that join it on `127.0.0.1` (`--port`, default
  17777), all started at once, about 40 s for a server and two clients.
  Its report, `--lag MS`, `--loss PCT`, `--bots N` and `--trace`, the log files and the memory it takes
  (a server and two `-nullrhi` clients are 12.9 GB of this machine's 16: close the editor
  first, and run one at a time): `docs/headless_runs.md#net`.
- **PIE:** `uepy.py` refuses to run while PIE is running, unless given `--allow-pie`
  (`--net` too). Never rebuild Blueprints under a running game.
- **Log prefixes:** builders log with `[GEN]`, verifiers with `[VERIFY]`.
- **Editor log:** `~/Library/Logs/Unreal Engine/OtherworldEditor/Otherworld.log`, not
  `Saved/Logs`. The previous session is rolled to `Otherworld-backup-<ts>.log`.
- **The published build's log** (it is sandboxed): `~/Library/Containers/com.YourCompany.Otherworld/Data/Library/Logs/Otherworld/Otherworld.log`,
  earlier runs beside it; its saved settings are under that container's
  `Library/Application Support/Epic/Otherworld/Saved/Config/Mac/`.

**The transport is the inbox** (`Content/Python/uepy_inbox.py`). It is a request/result
directory under `Saved/uepy/` that the editor polls, and it captures both `print()` and
`unreal.log*`.
- **Starting it by hand** in an editor that began before it existed: in the Output Log's Python
  box, run `import uepy_inbox; uepy_inbox.start()`.
- **Hot reload:** `uepy_inbox.stop(); importlib.reload(uepy_inbox); uepy_inbox.start()`.
- **The engine's own multicast remote execution** is tried next. It does not work on this machine,
  because macOS drops the multicast.

**Never cold-run a builder while an editor is open.** The editor doesn't see packages written to
disk:
- PIE tests the old build;
- an autosave writes the stale copy back over the new one;
- new assets stay invisible.

`uepy.py` avoids all three by running inside the editor's own process. If a cold run is
unavoidable, call `EditorLoadingAndSavingUtils.reload_packages([...])` afterwards, or restart the
editor.

**Iteration rules:**
1. **Never guess an engine API name across a boot.** Dump the candidates (`dir()`, pin names) in
   the same script, or grep the engine's plugin sources.
2. **Right-size `-game` runs.** 25 s is enough for spawn bugs. A probe launch boots
   `Lvl_Probe_50m` (18 trees, no grass), unless the probe declares `LEVEL = "/Game/Maps/..."`
   at module level (34 do, on `Lvl_Forest_200m`, each with its reason; the perf audits on theirs)
   or `--map` is given; probes on one level share one launch (`uepylib/probe_level.py`).
   **The fixed cost per launch** (measured, one cheap probe, 16 GB Mac): `--game` 40 s on the
   200 m level, 38 s on the probe level; `--net --clients 2` 74 s and 73 s. The level is only
   2–4 s of it: about 21 s is the engine's boot, ~7 s the Blueprints and anim graphs the
   Entry map loads before the level opens. So batch probes into one launch rather than
   expecting the small level to make a launch cheap. Between probes a single-player launch
   opens the level again (`Scripts/probes/boot.py`; measured 10 Oct 2026: 0.7–0.8 s on the
   probe level, 1.0–1.3 s on the 200 m level), so a probe's place in a batch cannot change
   its verdict: the player, the slots, the actors and the title are the level's own each
   time. Measured with it: 7 menu probes in one launch 51 s; the gate's 12-probe smoke set
   155 s over its two levels, the same forward and reversed. A network launch has no
   reset: order its probes so the fights come last. ~100 probes in one `--game` launch
   stall, so run big sets in chunks.
3. **Scope verification to what you changed.** `uepy.py --verify-for` runs only the verifiers
   the changed paths map to (`uepylib/probe_map.py`), and names none for a change to probes,
   docs or `Scripts/dev`. A verifier is 85 s cold, so never run one that reads nothing you
   wrote; dev-team's gate runs the whole suite around a session anyway. `--probes-for` is the
   same rule for probes, for the nightly sweep's triage: a task runs no existing probe (above).
4. **For a guard, zero errors proves nothing.** A gate that never opens logs the same as one that
   works. Probe the positive case too, with a probe in `Scripts/probes` (below).
5. **Batch several scripts into one `uepy.py` call.**

## Current state

In a line: a third-person survival shooter in a generated forest, single player or as a
client of a dedicated server from one code path; the player moves by Epic's motion
matching, and zombies and wendigos hunt them. System by system, with the package that owns
each: `systemDesign.md`, section 0.

## Gotchas learned the hard way

### Evaluation order

- **Pure nodes re-evaluate once per output read.** Any node without an exec pin behaves this
  way, including const `BlueprintCallable`s such as `WasInputKeyJustPressed`, the navmesh queries
  and `MakeOutgoingSpec`. Consequences:
  - A random chain read twice gives two different numbers.
  - A value recomputed after its inputs change gives a new answer. For example, a counter bumped
    and then read back numbers from 2, and the reload's take recomputed after `Loaded` rose gave
    free ammo (it is C++ now, worked out once).
  - A navmesh query's location output is garbage when its bool is false.

  **Store the value in a variable, branch on the bool, then read.** Check `has_exec` before
  concluding a node "never runs".
- **A Branch condition is pulled every frame, including frames where its object is null.** Never
  fold `Held.X` into `pressed AND armed AND …`: it logs an `Accessed None` every frame.
  **Nest a second Branch** instead.
- **Input polled from a component needs a late tick group.** `WasInputKeyJustPressed` is swapped
  during the controller's `TG_PrePhysics`. `AHUD` ticks later, which is why the HUD can poll.
- **Event Tick doesn't run while paused; `DrawHUD` does.**
- **An enum pin is a literal and can't be driven by a variable.** If a behaviour varies at
  runtime, it can't live in a pin literal. Use a Branch.

### Authoring Blueprint graphs from Python (`Scripts/uebp` has the helpers)

- **One authoring library, `Scripts/uebp`,** imported directly by every builder (its
  `__init__.py` maps it):
  - `uebp.graph`: `_node`, `_palette`, `_pin`, `_connect`, `_set` (takes a Python bool), and
    `out(n)`, `out(n, "Pin")`, `then(n)`, `else_(n)` for the plumbing pins.
  - `uebp.g._G`: the node shapes a long fragment repeats (`g.get`, `g.put`, `g.call`,
    `g.branch`). Write new fragments in it.
  - `uebp.nodes.<library>`: every `FN_*`/`NODE_*`/`MACRO_*` path, once. Add a path there,
    then run `python3 Scripts/dev/uepy.py --summary Scripts/dev/check_node_catalog.py`.
  - `uebp.net`: RPC custom events, replicated variables and what replicates
    (`Scripts/uebp/CLAUDE.md`).
  - `uebp.vars`: a Blueprint's variables are rows of its `<blueprint>_vars.py` table
    (`Var(name, type, default)`; a `Var` is its name). Name a variable by its row
    (`HV.Health`) or its `*_VAR` constant, never by a bare string. A fragment's own
    variables are a group of that table or a `TABLE` in its constants module
    (`cursor_consts.TABLE`), and it declares them with `declare(ed, TABLE)`: no builder
    calls `_declare` or `add_member_variable` (a dev unit test fails one that does).
    A row that replicates says so (`rep=REPLICATED`, `rep=REP_NOTIFY`); the builder still
    calls `net.replicate`.
  - `uebp.verify_vars`: `check_table(bp, TABLE, check)`, once per Blueprint in its
    suite's `var_tables` section, holds the Blueprint to its tables: each row's type,
    default and replication, and no variable beside them. A verifier does not re-state a
    variable by hand, and a new table (or a fragment's group) is added to that section's join.
- **No coordinates.** Nothing positions a node: `uebp.layout.arrange(ed)` lays the graph out
  before the compile. A new builder calls it once per graph it authors.
- **Refactoring the authoring code:** `python3 Scripts/dev/graph_fingerprint.py <label>`
  records every Blueprint with no positions; `graph_fingerprint_diff.py <a> <b>` must be
  empty when nothing structural was meant to change. `Scripts/dev/codemods/` holds the
  rewrites that got here (each has a dry run on a scratch copy).

- **Widget Blueprint layouts can be authored from Python,** through the editor-only UMGToolSet
  plugin (enabled in `Otherworld.uproject`) and `call_method`, since its functions have no
  Python glue. `graphics_menu/umg_author.py` wraps it; its CLAUDE.md lists the traps.

- **Declaring a float:** `get_basic_type_by_name("float")` and `"double"` silently declare an
  `int`. Use **`"real"`**. Verify the CDO value `isinstance(…, float)`.
- **Setting pin literals:**
  - `set_pin_value`'s return is not a signal, and an empty pin compiles as zero. `_set()` writes,
    then reads back and raises.
  - Struct pins (such as `FVector`) reject every literal. Use a `MakeVector` node. `LinearColor`
    does accept `"(R=…,G=…,B=…,A=…)"`.
  - `Multiply_VectorFloat` is promoted to a wildcard, and its unconnected B is a vector. Multiply
    by `MakeVector(r, r, r)` instead.
  - A Kismet math node's **A** pin won't hold a literal. Keep constants on B.
- **Member variable defaults:** `add_member_variable`'s default silently doesn't apply. Write the
  compiled CDO, recompile and read back with `_apply_defaults`. Every asset reference goes through
  `_must_load()`, because `_same(None, None)` is True and would pass a mistyped path.
- **Comparing arrays:** array defaults come back as `unreal.Array`, whose `repr` holds an
  address. Compare element by element.
- **Making nodes:**
  - `add_call_function_node` returns a **pinless node**, not `None`, for a path that doesn't
    resolve or isn't `BlueprintCallable` (e.g. `APlayerController::ConsoleCommand`). Assert the
    node has pins.
  - `NavigationSystemV1` lives in `/Script/NavigationSystem`.
  - Events other than a fresh BP's placeholders come from the palette via `create_node_from_name`
    (`AddEvent|EventTick`). A fresh BP ships a disabled `ReceiveBeginPlay`: find it, don't add it.
  - Cast nodes (`Utilities|Casting|CastTo<Class>`) exist only for **loaded** classes, and their
    output pin names contain spaces (`AsBP Health Component`), so match loosely.
  - `add_get_member_variable_node(name, class_path)` reads another object's variable through a
    `self` pin.
  - `set_node_pos` takes an `IntPoint`; `create_node_from_name` takes a `Vector2D`.
- **Pin types:**
  - `IsValid` refuses a class pin. Use `IsValidClass`.
  - `SpawnActorFromClass` types its return from the Class pin, so type the class variable to the
    class you want back.
- **Finding and identifying nodes:**
  - There is no `get_function_name`.
  - `get_node_title` names variable nodes (`Get DebugMode`) and many calls, but `Array_Get` is
    just `Get`. Match call nodes by their input-pin set (e.g. `{"TargetArray", "Index"}`).
  - `BEL.list_input_pins` includes `execute`. Filter it out when walking data dependencies.
  - **A RepNotify variable's Set node is titled `Set with Notify <Var>`,** not `Set <Var>`:
    a verifier that matches `Set <Var>` finds none the day the variable starts replicating.
    Match the head and the tail (`startswith("Set") and endswith(f" {var}")`).
  - **A literal equal to its pin's default isn't saved.** A `0.0` reads back as `"0.0"` in the
    editor that authored it and as `""` once loaded from disk, so a check that passes in the
    warm editor fails in the next one. Accept both, and re-run a new check in a fresh editor.
- **Probe PrintStrings:** splice them in, don't just connect. An exec output holds one link, so a
  plain connect severs the rest of the chain.
- **Components:**
  - A component added through the SCS isn't a property on the CDO. Its defaults live on the
    subobject template (`SubobjectDataBlueprintFunctionLibrary.get_object`).
  - `delete_subobject` doesn't cascade, so delete the whole subtree.
  - `rename_subobject` fails silently, so assert the name.
  - Handles go stale after any sibling delete, so re-gather after each one.
- **Anim graphs: a pose linked to two inputs plays everything under it twice as fast.**
  Python can link one pose output to two inputs (a blend's base and its slot's source) and
  the compile accepts it, but the engine updates and evaluates the node behind it once per
  link, each with the whole frame's time. Two such places in a row are four times: the
  player's run, jump and crouch played 3.4 times too fast until they were found. The
  builders still link plainly; `uebp/pose_share.py` `share(ed)` turns each into a cached
  pose before the last compile (`server_anim.py`, `gas_locomotion.py`), `unshare(ed)`
  takes them out before a builder walks the graph, and a verifier follows links with its
  `fed(pin)`. `verify/server_anim.check_no_fanout` fails a worn graph that has one;
  `probes/probe_gas_anim_speed.py` measures the legs against the ground.
- **Tick:** `bCanEverTick` isn't settable, but compiling turns it on when the Tick event's exec pin
  is **connected**. Leave Tick wired.
- **Rebuilds:** a builder whose "already authored, reusing" guard has no escape hatch never
  applies an edit. Builders take `rebuild=True` and wipe the graph.
- **Blueprint classes:** `Blueprint.get_blueprint_parent_class()` returns the parent. There is no
  `parent_class`, and no `get_super_class` on a generated class.
- **Actors:** use `destroy_actor()`, not `k2_destroy_actor`. There is no
  `begin_deferred_actor_spawn_from_class`.

### Skeletons and retargeting (`asset_pipeline/`)

- **`unreal.Quat()` is `(0, 0, 0, 0)`, not the identity.** Written as a retarget-pose offset, it
  collapsed every finger joint onto its knuckle. Spell out `unreal.Quat(0, 0, 0, 1)`.
- **A mesh's reference pose is not its skeleton's.** `SKM_Quinn_Simple` uses `SK_Mannequin`,
  whose reference pose is Manny's: about 10° apart at the hand. Read the mesh's pose through a
  component (`rig_util.mesh_ref_pose`).
- **A clip as shown is not a clip as sampled.** Compression drops tracks that only repeat the
  skeleton's reference pose, and the mesh's own reference pose fills them. The retargeter reads
  the pose as shown (`rig_util.visible_bone_xf`). Sampled raw, `MM_Idle`'s fingers read 15° off
  what it retargets.
- **`SkeletonModifier` adds bones and moves them,** but moving a bone that already exists never
  updates the skeleton's copy of it. `SkinWeightModifier` addresses the vertices of the mesh
  description, and a DynamicMesh copy lists the same ids first.

- **A blend space's samples cannot be moved, added or reordered from Python.** The write to
  `sample_data` saves, but the game reads samples by index out of data baked by
  `ResampleData`, which only the blend space editor's widget calls. Swapping a sample's clip
  or rate in place works. To change which clip plays at a speed, scale the speed the anim
  Blueprint feeds it (`combat/player_gait.py`).

### Collision

- **UE's stock `Pawn` profile and `CharacterMesh` both IGNORE Visibility.** A Visibility trace
  passes silently through a Character. `combat/hit_zones.make_shootable()` sets the capsule to
  Block, and the verifier guards it.

### Headless runs and probes

**Checking behaviour in the running game: write a probe** (`probe(p)`, a generator; the
model is `Scripts/probes/probe_consume_heal.py`, for `--net` `probe_net_join.py`), never a
hand-rolled `-game` run. The probe's shape, `WRITABLE`, network probes and every trap of a
headless game (world time under `-nullrhi`, writing a variable on a live instance, the
console's `set`, the inbox heartbeat): `docs/headless_runs.md#probes`.

### Config

- **An unknown `.ini` key, or a wrong section name, is silently ignored.** If a flag seems to do
  nothing, find the owning class and its `config=` file in the engine source.
- **The GameplayAbilities plugin and the gameplay tags are read only at editor startup.**
- **A full-screen game on a Mac with a notch loses its bottom edge** unless the app's
  `Info.plist` has `NSPrefersDisplaySafeAreaCompatibilityMode` true. The engine sizes the
  viewport to the whole screen (1800x1169 here), while macOS gives a full-screen window only
  the area under the notch (1800x1130): the bottom 39 px, the HUD's bars, fall off the screen.
  With the key macOS scales the whole window in under the notch. It is in
  `Build/Mac/Resources/Info.Template.plist` (tracked; the packaging copies its keys into the
  app), guarded by `Scripts/dev/tests/test_mac_plist.py`, and takes a re-package to reach a build.
- **The launcher icon** is cut from one picture (git-ignored `assets/icon/`) by
  `python3 Scripts/build_app_icons.py`, run outside the editor, into the three places the
  packaging reads, all tracked: `Build/Mac/Resources/Assets.xcassets` (Xcode compiles it in
  place of the engine's), `Build/Windows/Application.ico` (compiled into the exe) and
  `Content/Splash/Icon.bmp` (a Linux binary holds no icon: the game sets its window's from
  this loose file, staged by `DirectoriesToAlwaysStageAsNonUFS` in `DefaultGame.ini`). Each
  takes a re-package; `Scripts/dev/tests/test_app_icons.py` guards the files and the setting.
