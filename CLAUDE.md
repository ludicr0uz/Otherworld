# Otherworld — Claude quick reference

An Unreal Engine **5.8** project on macOS, driven entirely by **Unreal Python** automation.
There is no C++ module. `systemDesign.md` holds the detailed architecture.

## Hard rules

1. **Never** open or edit `.uasset`/`.umap` as text. Go through the `unreal` Python API.
2. **Where scripts live:**
   - `Scripts/` holds builders, verifiers and generators.
   - `Scripts/dev/` holds editor tooling:
     - `uepy.py` runs scripts (its pieces are `uepylib/`);
     - `dev-team` runs a queue of tasks, one headless Claude session each (its pieces are
       `devteam/`). A session started that way has no one to ask, so it decides and reports
       instead. The one exception is a Fab asset (see "Fab assets" below).
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
   | weapons, inventory, health, death, blood, audio, hit boxes | `build_`/`verify_weapons_and_combat.py` | `Scripts/combat/CLAUDE.md` |
   | NPCs: AI loop, pack, patrol and agro | `build_`/`verify_npc_blueprints.py` | `Scripts/npc/CLAUDE.md` |
   | graphics menu, settings, HUD | `build_`/`verify_graphics_menu.py` | `Scripts/graphics_menu/CLAUDE.md` |
   | survival: GAS, debuffs, forage | `build_`/`verify_survival.py`, `place_forage.py` | `Scripts/survival/CLAUDE.md` |
   | level generator, navmesh, trees and grass | `generate_forest_level.py` | `Scripts/forest_generator/CLAUDE.md` |

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
  `nodes.py`). Constants modules stay separate from the modules that author graphs.
- **The map:** the package's `__init__.py` docstring lists every module in one line each. Keep it
  current. Each module's docstring says what it owns and why.
- **Explicit imports only.** No `import *` and no re-exporting facades.
- **No import cycles.** Imports flow constants → `graph.py` → builders → entry point.
- **Verifiers mirror builders.** `verify/<area>.py` holds self-contained `check_*` functions.
  Values shared between sections go in `verify/fixtures.py`, and no section reads state that
  another section left behind.

**Working in it:**
- Find the owner from the `__init__` map. `grep -rn '^def \|^[A-Z_]* =' Scripts/combat` is a
  cheap symbol index.
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

## The repository is code only

**Nothing under `Content/` is committed except `Content/Python`.** Every asset is either stock
engine content or written by a script. `forest_generator/asset_sources.py` maps each `Content/`
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
- **What's been acquired** is `Scripts/asset_pipeline/fab_library.json` (tracked: the
  restore recipe, since the imported assets are not committed). The user records an
  addition with `fab_library.py --add <name> --url <listing> --at /Game/<folder>`.
- **Licences:** each entry records the listing's licence (`--license`). Don't ship an
  asset whose entry has none; ask the user what it is.

**Everything that isn't code goes in git-ignored `assets/`.** Never commit an archive: GitHub
rejects files over 100 MB. After a fresh clone, arm the guard:
`git config core.hooksPath Scripts/dev/hooks`. The pre-commit hook refuses files over 5 MB and
content extensions (override with `--no-verify`).

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
- **`$UEPY_COLD=1`** forces every run cold. dev-team sets it, and closes the project's editors
  before each task.
- **`--game`** counts `Blueprint Runtime Error`, `Accessed None`, `NPC-SPAWN` and `NPC-FELL`.
- **PIE:** `uepy.py` refuses to run while PIE is running, unless given `--allow-pie`. Never
  rebuild Blueprints under a running game.
- **Log prefixes:** builders log with `[GEN]`, verifiers with `[VERIFY]`.
- **Editor log:** `~/Library/Logs/Unreal Engine/OtherworldEditor/Otherworld.log`, not
  `Saved/Logs`. The previous session is rolled to `Otherworld-backup-<ts>.log`.

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
2. **Right-size `-game` runs.** 25 s is enough for spawn bugs.
3. **Scope verification to what you changed.** Run the full sweep (level, weapons, NPC, HUD,
   survival) once before calling the work done.
4. **For a guard, zero errors proves nothing.** A gate that never opens logs the same as one that
   works. Probe the positive case too, with a probe in `Scripts/probes` (below).
5. **Batch several scripts into one `uepy.py` call.**

## Current state

- **The player:** a Meshy-generated adventurer holding an issued shotgun and pistol. The SMG,
  assault rifle and sniper are found as drops. The player can sprint, aim over the shoulder or down
  the sights (the sniper's is its scope), reload and eat, block (F; a swing from the front does a
  quarter damage and costs stamina), crouch (C) and go prone (Z), both quieter and slower, and has
  a 10-slot inventory. Crouch, prone and the guard are procedural poses (no clip exists).
  Each gun has its own accuracy cloud and recoil, both steadied by the shoulder aim, crouch and
  prone; down the sights a shot goes exactly to the centre, and the reticle opens with the cloud.
- **The wanderers:** ten zombies and wendigos that patrol until they notice the player, then
  chase and melee. They respawn 75–100 m away and leave ragdoll corpses.
- **The HUD:** UMG screens driven by an `AHUD`: HP, stamina, hunger, thirst and temperature
  bars, a kill counter, the inventory grid, the main menu, the death menu, the graphics (M) menu
  and a settings screen, which holds the difficulty (EASY / MEDIUM / SURVIVOR,
  default EASY). On EASY a mushroom also heals 10 HP; the other levels change nothing yet.
- **The maps:** `Lvl_Forest_200m` (the startup map) and `Lvl_Forest_1000m`, both at night. Food
  and water lie in both.
- **Save and exit:** X in the M panel saves the character's stats and inventory, but not its
  location, after 15 s, then returns to the main menu. A hit calls it off. The next game loads
  the profile, and death deletes it (`Scripts/graphics_menu/CLAUDE.md`).
- **Known gaps:** temperature moves nothing yet. `GameDefaultMap` still points at the old
  `Lvl_Forest`. Feel checks that need a play session are listed per package.

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

### Authoring Blueprint graphs from Python (`combat/graph.py` has the helpers)

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
- **Probe PrintStrings:** splice them in, don't just connect. An exec output holds one link, so a
  plain connect severs the rest of the chain.
- **Components:**
  - A component added through the SCS isn't a property on the CDO. Its defaults live on the
    subobject template (`SubobjectDataBlueprintFunctionLibrary.get_object`).
  - `delete_subobject` doesn't cascade, so delete the whole subtree.
  - `rename_subobject` fails silently, so assert the name.
  - Handles go stale after any sibling delete, so re-gather after each one.
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

### Collision

- **UE's stock `Pawn` profile and `CharacterMesh` both IGNORE Visibility.** A Visibility trace
  passes silently through a Character. `combat/hit_zones.make_shootable()` sets the capsule to
  Block, and the verifier guards it.

### Headless runs and probes

**Checking behaviour in the running game: write a probe.** Don't hand-roll a `-game` run plus
inbox polling. One command boots the level, runs the probe once the player exists, prints each
check and ends the run as soon as the probe does (about 20 s):

```bash
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_consume_heal.py
```

- **Shape:** a probe defines `probe(p)`, a generator. `yield 0.3` waits 0.3 s of game time,
  `yield lambda: cond()` waits for a condition, and `p.check(label, ok, detail)` records a
  result. `p` has the lookups (`pawn`, `component`, `game_mode`, `hud`, `actor_of`,
  `send_event`, `get`, `set`). `Scripts/probes/probe_consume_heal.py` is the model.
- **Writing a Blueprint variable on a live instance:** list it in the probe's
  `WRITABLE = [(bp_path, var)]`. `probes/boot.py` makes it Instance Editable and recompiles, in
  memory for that run only, before the level loads. Nothing on disk changes and no builder
  re-run is needed.
- **Keep probes:** they are checked in, so the next change to the same behaviour re-runs them.
- **Poking a running game by hand:** start `uepy.py --game --seconds 120` and send scripts with
  `uepy.py --in-game <script>`. A game has its own inbox, `Saved/uepy/game`, so it never takes a
  job meant for the editor.

- **World time in `-nullrhi -game` advances by a fixed tiny step per frame.**
  - A 2–3 s `Delay` may never elapse in a 30 s run. Keep probe delays well under a second, and
    measure upstream of long delays.
  - Heavy per-frame logging slows the game itself, so gate probes down to one actor.
  - Cross-check `GetTimeSeconds` against wall clock before reading "it did not happen".
- **Isolate the thing under test.** For example, kill the player at BeginPlay rather than waiting
  for the pack: 40 decisive seconds instead of 3 inconclusive minutes.
- **A `-game` process runs `init_unreal.py`.** That is how probes start, and how
  `uepy.py --in-game` reaches a running game.
  - There is no world context there, and `EditorLevelLibrary.get_game_world` SIGSEGVs. Use
    `unreal.find_object(None, "/Game/Maps/<L>.<L>")` to get the world.
- **Python can't write a Blueprint variable on an instance** unless it is Instance Editable, and
  the `Set*PropertyByName` functions aren't exported. Probes handle this with `WRITABLE` (above).
  What that rests on:
  - **Instance Editable plus compile, unsaved, works in `-game`**, but only if the Blueprint
    stays referenced. Opening a level garbage-collects an unreferenced Blueprint, and it
    reloads from disk without the edit. `boot.py` holds them.
  - **Write with `set_editor_property(name, value, PropertyAccessChangeNotifyMode.NEVER)`.**
    The default notifies PostEditChange, which on a live component re-runs the owner's
    construction script. The actor gets fresh components, so the one you wrote is a dead copy
    that never ticks again.
  - **Never use the console's `set <Class> <Prop> <value>` in a game.** It writes every object
    of the class, including the CDO, and re-runs construction scripts: it set off an endless
    NPC respawn storm. `setnopec` did nothing to a PIE instance and logged nothing.
  - PIE started from Python begins **paused**. Call `GameplayStatics.set_game_paused(w, False)`.
- **A `-game` inbox heartbeat can go quiet for seconds.** The game beats once a frame, and a
  headless frame can be slow. uepy allows a game 30 s (an editor 6 s), and it treats a beat from
  a dead pid as silence.
- **In a cold run, `print()` doesn't reach the log.** Use `unreal.log_warning`. The inbox captures
  both.
- **Sort numbered actors on their trailing integer, never on the label string,** or `_10` lands
  between `_1` and `_2`.
- **Killing a `-game` run on a timer** produces a `SIGSEGV` with `GracefulTerminationHandler` in
  the stack. That isn't a gameplay fault.
- **`-nullrhi` can't prove anything that touches the window or viewport.**
- **Diagnosing a frozen editor:** run `sample <pid> 5 -file /tmp/hang.txt` and read the
  `GameThread` stack. `ps -o %cpu` separates a spin (100%) from a deadlock (0%).

### Config

- **An unknown `.ini` key, or a wrong section name, is silently ignored.** If a flag seems to do
  nothing, find the owning class and its `config=` file in the engine source.
- **The GameplayAbilities plugin and the gameplay tags are read only at editor startup.**
