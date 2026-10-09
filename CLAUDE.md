# Otherworld — Claude quick reference

An Unreal Engine **5.8** project on macOS, driven entirely by **Unreal Python** automation.
The game is authored by those scripts; the C++ in `Source/` is small (a runtime module with
the player's predicted movement states, and an editor module of helpers for the scripts) and
must be compiled before the editor opens (`Source/CLAUDE.md`). `systemDesign.md` holds the detailed
architecture.

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
     - The gate also runs a probe set beside the verifiers (`Scripts/probes/sets.py`: `SMOKE`
       by default, `--gate-probes FULL|none`): `probe:<name>` rows in the baseline table, a probe
       that newly fails fails the task. A probe that fails in its batch is re-run alone and the
       solo verdict stands (`devteam/probe_gate.py`).
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
   | weapons, inventory, the glimmer over an item on the ground, health, death, blood, bullet impacts, audio, hit boxes, chopping trees for wood, the matches, the use key and the stick that burns, the knife or axe heated at a fire | `build_`/`verify_weapons_and_combat.py` | `Scripts/combat/CLAUDE.md` |
   | NPCs: behaviour tree, pack, patrol and agro | `build_`/`verify_npc_blueprints.py` | `Scripts/npc/CLAUDE.md` |
   | the menu (the title's, and M's in play), graphics presets and tuning, settings, HUD | `build_`/`verify_graphics_menu.py` | `Scripts/graphics_menu/CLAUDE.md` |
   | survival: GAS, debuffs, on-hit effects and bleeding, forage, the campfire | `build_`/`verify_survival.py`, `place_forage.py` | `Scripts/survival/CLAUDE.md` |
   | level generator, navmesh, trees and grass | `generate_forest_level.py` | `Scripts/forest_generator/CLAUDE.md` |
| day and night: world config, sun, moon, sky | `build_`/`verify_day_night.py` | `Scripts/world/CLAUDE.md` |
| corpse loot: loot tables, the roll, the loot window | `build_survival.py` (tables), `probe_corpse_loot.py` | `Scripts/loot/CLAUDE.md` |
| item icons: each item's inventory icon, rendered from its 3D model; the I panel's portrait of the character | `build_item_icons.py` (run outside the editor) | `Scripts/item_icons/CLAUDE.md` |
| generated bodies: describing one, the rig check, the import that normalises it, swapping the player onto it | `asset_pipeline/fetch_monsters.py`, `rig_compat.py`, `swap_player_body.py` | `Scripts/asset_pipeline/CLAUDE.md` |
| the Game Animation Sample (the motion-matching clips, databases and anim blueprint, copied under `/Game/GAS`; the player's base movement since G3): what came across, the redirects it loads by, the four packages patched after the copy, the plugins and settings it needs | `asset_pipeline/import_gas.py`, `gas_paths.py`, `check_gas_load.py` | `Scripts/asset_pipeline/CLAUDE.md` ("The Game Animation Sample") |
| the player's melee clips (C2): the knife's and the axe's swing and ready pose are Mixamo's (the downloads in `assets/cache/mixamo`, `mixamo_paths.PLAYER_CLIPS`), retargeted onto the player's skeleton and baked into `/Game/Weapons/Anims` with the right fist closed and each swing cut to strike when the timed blow lands; how the swing picks the axe's clip on every machine (the ready pose in hand) | `asset_pipeline/import_mixamo_player.py`, `mixamo_player.py`, `combat/melee_clips.py`, `combat/verify/melee_clips.py` | `Scripts/combat/CLAUDE.md` ("The melee clips") |
| Lyra (the user's copy under `/Game/Sourced/Lyra`, a Fab pack, not committed; the redirect it loads by; which of its clips the game plays, retargeted onto the player's skeleton: the punch, and the guns' ready poses, its rifle and pistol ADS idles) | `asset_pipeline/import_lyra.py`, `lyra_paths.py`, `combat/shotgun_hold.py` | `Scripts/asset_pipeline/CLAUDE.md` ("Lyra"), `Scripts/combat/CLAUDE.md` ("The gun poses") |
| the skeleton bridge (how the GAS clips reach the MetaHuman: the hidden mesh is the sample's UEFN mannequin, `SKM_UEFN_Player`, with a second retargeter from it; worn by the game since G3): the choice, what it costs the sockets, the clips and the hit bodies | `asset_pipeline/build_gas_bridge.py`, `gas_player_mesh.py`, `measure_gas_bridge.py`, `probes/probe_gas_idle.py` | `Scripts/asset_pipeline/CLAUDE.md` ("The skeleton bridge") |
| the player's base movement: motion matching (the sample's anim blueprint patched where it lies to read our CharacterMovementComponent; the one switch `GAS_LOCOMOTION`; its own server branch; the silent foley component; what it costs in memory) | `combat/gas_locomotion.py`, `gas_locomotion_consts.py`, `combat/skin.py`, `probes/probe_gas_locomotion.py`, `probe_net_gas_locomotion.py` | `Scripts/combat/CLAUDE.md` ("The motion-matching base") |
| the weapon layers over it (G4): everything a weapon, a stance or a hit does to the body is a second anim blueprint, `ABP_WeaponLayers`, linked into the motion-matching one (`PlayerSkin.anim_bp` against `base_anim_bp`); how a graph or a probe reaches its instance (the tag, `p.pose_instance`); the game's clips retargeted onto the UEFN skeleton; why no clip played into a slot may have root motion | `combat/weapon_layers.py`, `weapon_layers_consts.py`, `combat/verify/weapon_layers.py`, `asset_pipeline/retarget_to_uefn.py` | `Scripts/combat/CLAUDE.md` ("The weapon layers") |
| crouch, slide and traversal from the sample (G5): the crouch as the motion matching's own Stance, the slide (a fourth predicted state of the C++ movement, posed by the sample's slide loop), the sample's traversal component behind the jump key; one switch each (`GAS_CROUCH`, `GAS_SLIDE`, `GAS_TRAVERSAL`); why the sample's montage slot is in the pose line only while a traversal plays; what is not proven on a server | `combat/gas_moves_tuning.py`, `gas_moves.py`, `gas_traversal.py`, `gas_traversal_slot.py`, `combat/verify/gas_moves.py`, `probes/probe_gas_traversal.py`, `probe_net_slide.py` | `Scripts/combat/CLAUDE.md` ("Crouch, slide and traversal from the sample") |
| clothing: the eight garments, wearing and taking off, the I panel, the test garments | `build_`/`verify_clothing.py`, `probe_clothing.py` | `Scripts/clothing/CLAUDE.md` |
| sound: every sound of the game, which Blueprint variable plays which takes, how far each carries, how loud each is, the beds, the player's voice, the listener | `build_sound.py` (the one build after a change to any of them) | `Scripts/Sound/CLAUDE.md` |
| sourcing sounds: the fetchers and the synthesiser, cutting candidates from the downloaded packs, the page that plays and rates them (all run outside the editor) | `Scripts/Sound/*.py` | `Scripts/Sound/sound_candidates/__init__.py` |
| predicted movement: sprint, prone and the aim-walk, their speeds and the stamina, decided by the player's C++ movement component on the owning client and the server alike; what a graph may hand it and read off it, the reparented player character, the correction count | `combat/player_move.py`, `uebp/nodes/move.py`, `probes/probe_net_move_states.py` | `Source/CLAUDE.md` ("Predicted movement"), `Scripts/combat/docs/stance.md` |
| the C++ modules: the `Otherworld` runtime module (the player's movement component; the history of hit boxes and the rewound shot trace; the load test's counters; the RPC guard), the editor-only `OtherworldEditor` (what the builders need and Python cannot reach) and the Editor, Game, Client and Server targets; the compile command, its time and the Xcode it needs | `Source/Otherworld/Otherworld.Build.cs`, `Source/OtherworldEditor/`, `Source/*.Target.cs` | `Source/CLAUDE.md` |
| the two modes on the title: the Single Player and Multiplayer pages, the server address, joining and leaving a server, the reason a join failed, the session kept on the GameInstance | `graphics_menu/mode_tick.py`, `net/game_instance.py`, `probes/probe_net_title.py` | `Scripts/graphics_menu/CLAUDE.md` ("The two modes"), `Scripts/net/CLAUDE.md` |
| multiplayer conventions: the authority pattern, what a screen may do (it asks: one `Ask…` event on the weapon component per action, `combat/ask_consts.py`, called through `graphics_menu/ask.py`; a HUD graph writes no request and takes nothing itself), where state lives (per player on `BP_OtherworldPlayerState`, shared on `BP_OtherworldGameState`, server-only on the GameMode, which a client never reads: `net/state_graph.py`), who is nearby (a world actor or a wanderer asks the living players, all of them or the nearest: `net/players.py`, never `GetPlayerPawn(0)`), whose keys a graph reads (the local player's: a HUD's owning controller, the weapon component's `LocalPC` behind its local gate, `combat/weapon_component/local.py`; never `GetPlayerController(0)`), the three mode questions, what may differ between single player and a server (the pause, authored only by `net/pause.py`), how another player's character is posed (the stance off the movement component, the engine's view pitch, and three replicated variables the owning machine reports: `combat/weapon_component/look.py`), what a player carries (the server's item actors, written down as one plain-data record on a frame that changed them, `combat/record_vars.py`: a C++ struct on its own component, `Source/Otherworld/Public/OtherworldInventoryRecord.h`, marked by `combat/dirty.py` behind every node that changes what is carried, which the owning client's item actors are made from, read through the inventory library with no Blueprint copy: `combat/weapon_component/view.py`, and which a save writes as bytes, a version first: `ToBytes`/`FromBytes`, `probes/probe_record_bytes.py`; the slots' asks are Server events), how a gun is fired (the owning client asks with `Server_Fire(AimPoint)` and `Server_Reload` and predicts its own round, cooldown and kick; the server traces from its own muzzle, hurts and spends: `combat/weapon_component/shot.py`, `combat/shot_vars.py`; and judges a remote shooter's pellets against where every character stood when the shooter fired, its round trip ago, within a cap: lag compensation, in C++, `combat/lag_tuning.py`, `probes/probe_net_lag_hits.py`), how anything else is hurt or taken (a swing, the guard and the use key, a throw and the take of an item are Server events too, `combat/strike_vars.py`: the server sweeps, decides `Blocking` and `FireWard` from its own stamina and stick, flies the thrown item, which it makes a replicated actor, `combat/item_world.py`, and gives a taken one to the first who asks), what lies in the world and who gets it (every item lying there is the server's actor, replicated from its own Tick, `combat/item_world.py`; the drop and the loot window's take are Server events too, `combat/weapon_component/drop_request.py`, `loot_take.py`; of two players asking for one item or one row of a body the first gets it), what a player's body needs (hunger, thirst and temperature are the server's survival component's, replicated to their owner alone; the debuffs and the bleed are effects on the character's ability system, which replicates; eating is `Server_Consume`, and `GA_ConsumeItem` runs on the server only; both components live on the character, not the PlayerState: `Scripts/survival/CLAUDE.md`, "On a server"), what changes the world (a campfire lit with the matches, a stick lit at it, a blade heated, a bleed cauterised: a Server event each, `combat/fire_vars.py`; the campfire is a replicated actor, a tree's wood the server's blow, and a burning stick or a hot blade is the server's item's, told by the record and never timed by a client), who a player may hurt (anyone with a health component, another player's character included, through the one `TakeHit`; a player killed by a player is a player kill on the killer's PlayerState, `combat/player_kill.py`), which random draws are state (rolled once, by the server) and which cosmetic (`net/random_consts.py`: a new draw gets a row), how everyone sees and hears a fight (every sound, clip and burst of a player's shot, reload, swing or throw is an `Fx_`/`Multicast_` pair on the weapon component, told by the server and predicted by the owner: `combat/fx_vars.py`, `combat/weapon_component/fx.py`; a new one goes in a pair, never at the site that decides it), what the server sends each client and how often (the one table `net/relevancy_consts.py`, written onto the class defaults by the builders; the replication graph in C++, `Source/Otherworld/Public/OtherworldReplicationGraph.h`; an item lying still is dormant and the graphs that change its state wake it, `combat/item_world.py`; a take destroys a placed item, so a late joiner sees it gone: `probes/probe_net_late_join.py`), what a dedicated server does with a body it never draws (it poses the mesh the game runs on by how near a player is, `combat/server_pose.py`, `combat/pose_tuning.py`, C++ `OtherworldServerPose.h`, and ticks no other skinned mesh on it; each anim graph has one IsDedicatedServer branch, `combat/server_anim.py`, and whatever is for the eye goes on its client arm; a shot's impacts are one `Multicast_ShotHits`, `combat/weapon_component/shot_hits.py`: "What the server spends on bodies it never draws"), writing a `--net` probe, what a Server event checks before it runs (the RPC guard, a C++ component on the player every Server event asks first through `net/guard.py`: how often, a token bucket per event per connection, `net/guard_consts.py`, whose refusals log `RPC-REFUSED` and past a threshold kick the connection, and for a shot whether its `AimPoint` is one the server's copy's view could rest on; a new Server event gets a row and the fragment, `combat/verify/guard.py`, `probes/probe_net_guard.py`), what the spike found broken on a client, system by system, and what a server costs at 8 to 62 players (the load harness `uepy.py --net --bots N`, its bots, `probes/bots.py`, and its numbers: "Measured at scale", before and after the relevancy pass) | `probes/probe_net_load.py`, `probe_net_server_pose.py`, `probe_net_late_join.py`, `probes/probe_net_see_each_other.py`, `probe_net_look.py`, `probe_net_menu_overlay.py`, `probe_net_living_players.py`, `probe_net_local_input.py`, `probe_net_loot_roll.py`, `probe_net_inventory.py`, `probe_net_fire.py`, `probe_net_throw.py`, `probe_net_take.py`, `probe_net_melee.py`, `probe_net_pvp.py`, `probe_net_fx.py`, `probe_net_campfire.py`, `probe_net_survival.py`, `probe_net_guard.py`, `probe_asks.py` | `Scripts/net/CLAUDE.md` |
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
  current. Each module's docstring says what it owns and why.
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
python3 Scripts/dev/uepy.py --probes-for [paths]   # the probes a change can affect (default: git diff); --dry-run lists them
python3 Scripts/dev/uepy.py --game --windowed --probe <probe>   # rendered, in a 1280x720 window
python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_join.py   # a server and 2 clients, see below
python3 Scripts/dev/uepy.py --net --clients 1 --lag 120 --probe Scripts/probes/probe_net_move_states.py   # with 120 ms of lag
python3 Scripts/dev/uepy.py --net --clients 2 --bots 32 --trace --probe Scripts/probes/probe_net_load.py   # the load test: 32 server-driven bots, an Insights trace
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
  Its report, `--lag MS`, `--bots N` and `--trace`, the log files and the memory it takes
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
   expecting the small level to make a launch cheap. A batch shares a world: ~100 probes in
   one `--game` launch stall (the same on the 200 m level), so run big sets in chunks.
3. **Scope verification to what you changed.** Run the full sweep (level, weapons, NPC, HUD,
   survival) once before calling the work done.
4. **For a guard, zero errors proves nothing.** A gate that never opens logs the same as one that
   works. Probe the positive case too, with a probe in `Scripts/probes` (below).
5. **Batch several scripts into one `uepy.py` call.**

## Current state

The whole of it, system by system, is `docs/current_state.md` (the player, the wanderers,
corpse loot, the HUD and menu, clothing, item icons, sound, wind, the maps, day and night,
save and exit, death, the known gaps). In a line: a third-person survival shooter in a
generated forest, single player or as a client of a dedicated server from one code path;
the player moves by Epic's motion matching, and zombies and wendigos hunt them.

## Gotchas learned the hard way

### Evaluation order

- **Pure nodes re-evaluate once per output read.** Any node without an exec pin behaves this
  way, including const `BlueprintCallable`s such as `WasInputKeyJustPressed`, the navmesh queries
  and `MakeOutgoingSpec`. Consequences:
  - A random chain read twice gives two different numbers.
  - A value recomputed after its inputs change gives a new answer. For example, a counter bumped
    and then read back numbers from 2, and `ReloadTake` recomputed after `Loaded` rose gave free
    ammo.
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
    (`HV.Health`) or its `*_VAR` constant, never by a bare string.
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
