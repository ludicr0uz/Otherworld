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
       It reads the task file again after each task, so an item added to `tasks.md` during a
       run is run in that run, and a waiting one ticked or deleted there is not.
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
   | weapons, inventory, health, death, blood, bullet impacts, audio, hit boxes, chopping trees for wood, the matches, the use key and the stick that burns, the knife or axe heated at a fire | `build_`/`verify_weapons_and_combat.py` | `Scripts/combat/CLAUDE.md` |
   | NPCs: behaviour tree, pack, patrol and agro | `build_`/`verify_npc_blueprints.py` | `Scripts/npc/CLAUDE.md` |
   | the menu (the title's, and M's in play), graphics presets and tuning, settings, HUD | `build_`/`verify_graphics_menu.py` | `Scripts/graphics_menu/CLAUDE.md` |
   | survival: GAS, debuffs, on-hit effects and bleeding, forage, the campfire | `build_`/`verify_survival.py`, `place_forage.py` | `Scripts/survival/CLAUDE.md` |
   | level generator, navmesh, trees and grass | `generate_forest_level.py` | `Scripts/forest_generator/CLAUDE.md` |
| day and night: world config, sun, moon, sky | `build_`/`verify_day_night.py` | `Scripts/world/CLAUDE.md` |
| corpse loot: loot tables, the roll, the loot window | `build_survival.py` (tables), `probe_corpse_loot.py` | `Scripts/loot/CLAUDE.md` |
| item icons: each item's inventory icon, rendered from its 3D model; the I panel's portrait of the character | `build_item_icons.py` (run outside the editor) | `Scripts/item_icons/CLAUDE.md` |
| generated bodies: describing one, the rig check, the import that normalises it, swapping the player onto it | `asset_pipeline/fetch_monsters.py`, `rig_compat.py`, `swap_player_body.py` | `Scripts/asset_pipeline/CLAUDE.md` |
| clothing: the eight garments, wearing and taking off, the I panel, the test garments | `build_`/`verify_clothing.py`, `probe_clothing.py` | `Scripts/clothing/CLAUDE.md` |

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
python3 Scripts/dev/uepy.py --game --windowed --probe <probe>   # rendered, in a 1280x720 window
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

- **The player:** a Meshy-generated adventurer in skin-tight shorts (`SKM_Adventurer03`; which body is one setting, `asset_pipeline/player_body.py`) holding an issued shotgun, pistol, knife, axe, box of matches and stick. The SMG,
  assault rifle and sniper are found as drops. The rifle is the FPS Weapon Bundle's AK 47 and
  the sniper its AS Val with a scope and the SMG its SMG11 (Fab models); the shotgun and pistol are Quaternius's
  Shotgun_3 and Pistol_1 (CC0, `asset_pipeline/import_quaternius.py`). A gun is carried lowered, in the hand of the stock idle and jog, and comes up into its
  ready pose for an aim, a shot, a reload or the guard (`combat/weapon_component/carry.py`).
  The player's default movement is a jog, at 4 m/s, played by the jog clip (`combat/player_gait.py`), and they can sprint at 6 (a full stamina bar lasts 8 s and refills in a little over 8: `combat/player_tuning.csv`; forwards only: within 60° of the way they face, `combat/sprint_tuning.py`), aim over the shoulder or, with a gun, down
  the sights (the sniper's is its scope; the knife, the axe and the other items have none, so with one of them in hand the sights key is the use key and does not aim: `combat/weapon_component/use.py`), reload and eat, block (F; a swing from the front does a
  quarter damage and costs stamina), punch with empty hands (left click, `MM_Attack_01`), slash with the knife in hand (left click,
  `A_KnifeSlash`, a clip keyed from Python; the knife is the FPS Weapon Bundle's M9; the axe, Quaternius's Survival Pack one, swings the same slash for now, and every third blow of it on a tree leaves a piece of wood beside the trunk, a pick-up for the bag: `combat/weapon_component/chop.py`), light a campfire (left click with the matches in hand and wood in the bag: the wood is spent and a fire stands in front of the player for 3 minutes, warming them within 4 m: `combat/weapon_component/light.py`, `survival/campfire.py`), light the stick at a campfire (the use key with it in hand, within 3 m of a fire: it burns for 2 minutes, carried up like a torch and lighting the ground round it, then is a stick again) and hold the burning stick out in front (the use key held: `combat/stick.py`, `combat/weapon_component/torch.py`), heat the knife or the axe at a campfire (E on the fire with it in hand: its metal glows red for 20 s, and while it does the use key cauterises a bleed and its blow does double damage to a wendigo: `combat/heat.py`, `combat/weapon_component/heat.py`, `cauterize.py`, `hot_blow.py`), crouch (C) and go prone (Z), both quieter and slower and played by Quaternius Universal Animation Library
  clips (the crawl is its face-down swim: the packs have no crawl), throw whatever is in hand (hold V to
  cock the arm and see the arc, click to throw, let V go to call it off; the throw goes where the reticle is: the knife is held by its blade for it (`combat/knife.py` `knife_throw_grip`); the arc stands under the reticle and ends on the point it rests on, and only at a point out of the item's reach, or at the sky, is it the lob tipped over the view (`combat/weapon_component/throw_launch.py`); while V is held the arm waits cocked, in Quaternius UAL2's `OverhandThrow` stopped where its hand is furthest back, and the click plays the clip on from there (`throw_ready.py`, `combat/throw_pose.py`), the item leaving the hand 0.12 s later, tumbling end over end through the air and landing as a pick-up; the knife and the axe go out flat and fast instead of lobbed, spinning forward edge first like a throwing axe, and a thrown knife or axe takes 50 or 75 HP off a body it strikes (1.5 times that in the head, as a bullet does) and stays in it, attached to the bone it struck, alive or dead, and stays lodged in a tree it strikes within reach; E within reach of the blade takes it back: `combat/weapon_component/throw_windup.py`, `throw_flight.py`, `throw_strike.py`, `combat/throw_tuning.py`), interact with one thing at a time (E: of those in reach, the one nearest the
  point the reticle rests on; an item lying there is picked up, and a campfire heats the knife or the axe in hand: `combat/weapon_component/interact.py`), and carries
  things in slots (`combat/slot_tuning.py`): the hand (the held item, centre bottom of the screen), four weapon slots under it (primary and secondary for the long guns, the pistol's, the melee's; no captions: an empty one shows a translucent silhouette of its kind, a rifle, a rifle, a pistol, a knife; 1-4 bring one to hand and the same key again puts it away, Q the next one) and a 10-slot backpack, bottom right under the worn garments, always shown (5-9 bring its first five to hand; **I** opens the I panel, where the arrows and Enter, or a click, bring a bag slot's item to hand, and an item is dragged from slot to slot, only a weapon into a weapon slot). A pick-up goes into the bag, or into empty hands with the bag full; with the bag full and something in hand nothing is picked up. A gun in hand goes back to its weapon slot when another item is brought up. The guard is a procedural pose (no clip exists), as are crouch and prone on the mannequin fallback.
  Each gun has its own accuracy cloud and recoil, both steadied by the shoulder aim, crouch and
  prone; down the sights a shot goes exactly to the centre, and the reticle opens with the cloud.
  Down the sights the view runs along the gun's own sight line (the front sight's tip is the
  centre of the screen, in any pose), so there the reticle is drawn only in debug mode; the
  hip and the shoulder aim keep it. Bringing the sights up is one motion from the key: the camera
  travels from where it is onto the sights, zooming as it goes, and the view stays on the
  target while the gun rises into it
  (`combat/weapon_component/seat.py`). Down any gun's sights the player's own head is
  hidden, so it never stands in the sight picture (`combat/weapon_component/head_hide.py`).
  The aim sways slowly, sights and shot together
  (`combat/sway_tuning.py`; steadier crouched and prone; how fast is each gun's `sway_rate` on the
  GUN SETTINGS tab). Holding Left Alt down the sights holds the breath, all but stilling the sway for up to 5 s,
  after which the player is winded and sways harder until it refills (`combat/weapon_component/breath.py`). Down the sights the left hand is
  held on the gun (an IK onto a point in the right hand's space), so both hands move with
  it (`combat/support_hand.py`). A hit taken down the sights plays
  no flinch, so the view stays on the target (`combat/weapon_component/steady.py`).
  The pistol reloads every 8 shots from an endless reserve. A bullet that hits a body throws
  blood; one that hits the scenery throws chips and dust off the surface (`BP_BulletImpact`).
  A body is hit only where its physics bodies are, and those are fitted to the model
  (`combat/hit_bodies.py`): a round past the head, inside the capsule, is a miss.
- **The wanderers:** ten zombies and wendigos that patrol until they notice the player, then
  chase and melee, each driven by a Behavior Tree (`BT_ForestWandererAI_<Creature>`). Between two
  swings a wanderer backs off a little and sidesteps round the player, facing them. A campfire draws the zombies: one on patrol within 200 m of a burning fire is Drawn, walks to it at its patrol walk and stands by it until it burns out, and still goes aggro if it notices the player on the way (`npc/drawn.py`, `forest_generator/npc_drawn.py`). A wendigo
  hunts before it chases: aggro, it roars (the Mixamo zombie scream, and one of its roar
  sounds), comes in round the player in an arc, tree to tree, waiting behind each trunk, and
  from 10 m charges straight at them (`npc/stalk.py`, `forest_generator/npc_stalk.py`). It runs the arc at 169% of its run speed (faster than the player sprints), and the way round turns about every 4–9 s. Only a tree whose trunk is at least 45 cm wide is cover (never a sapling); with no such tree ahead it runs on in the open without stopping; and further than 150 m from the player it runs straight at them, at that same speed (`npc/stalk_cover.py`). One the player has shot is enraged: no roar and no arc, it charges straight at them, for good. Fire held out at a wendigo (the player's `FireWard`: the burning stick, raised by the use key) keeps it from attacking: within 7 m and in front of the player it circles them instead, turning about every 2–4.5 s, attacks once it is more than 90° round the fire, and after 30 s of being held off runs away for 12 s and hunts again (`npc/ward.py`, `forest_generator/npc_ward.py`). Held off, it roars twice, standing: once 13–17 s in, and once at the 30 s, before it runs; a blow it lands on the player starts the 30 s over (`npc/ward_roar.py`). A wendigo's blow has a 33% chance of leaving the player bleeding: 50 HP drained over 3 minutes, named BLEEDING on the HUD; a second wound restarts it, and a heated blade stops it (`survival/on_hit.py`, the on-hit table any attack can be given a row in). A killed one is replaced 10 s later, 75–100 m away, and leaves a ragdoll corpse.
  The zombie idles, shambles, runs and swings with Mixamo's zombie packs
  (`asset_pipeline/import_mixamo.py`, zips in `assets/cache/mixamo/`); the wendigo keeps the
  mannequin's set, plus that pack's scream for its roar.
- **Corpse loot:** a wanderer the player kills carries what its loot table rolls (for now, water:
  a canteen at 50%). Near any body, loot or none, **Tab** kneels the player over it (Quaternius
  UAL's `Fixing_Kneeling`) and opens a loot window showing what it carries as item icons;
  Up/Down pick and Enter takes the item into the bag (`Scripts/loot/CLAUDE.md`).
- **The HUD:** UMG screens driven by an `AHUD`: HP, stamina, hunger, thirst and temperature
  bars, a kill counter, an FPS readout that is always on (debug mode or not), the inventory grid, the menu, the death menu
  and a settings page, all of them worked by the mouse cursor as well as the keys (hover picks a row, a click takes it, the wheel adjusts). There is one menu, off the top left: the game opens on it, paused, and M brings the same one up in play, where it pauses nothing (`graphics_menu/menu_main.py`). Its rows have no hotkeys: Up/Down and Enter, or a click, take one, and while it is open the arrows do not walk the character. Its rows: new game, which starts the game from the title and in play reads resume and shuts the menu; settings, which opens the settings page in the rows' place; debug mode, which draws each pellet's trajectory and each wanderer's aggro cone in the world; save and exit; a dev-all-guns cheat; a GUN SETTINGS tab that changes each gun's numbers live, and the knife's and the axe's throw (its arc and the damage a thrown one does), and saves them to `Scripts/combat/gun_tuning.csv`, which the weapons build reads; a MONSTER SETTINGS tab that does the same for each creature's senses, patrol, speed, melee and health, and for the wendigo's hunt (charge range, catch-up range, hunting speed, the wait behind a tree, how often it turns) and what fire does to it (range, cone, ring, circling speed, how often it turns, how long it is held off and runs), a scrolling list saved to `Scripts/npc/monster_tuning.csv`, which the NPC build reads; a PLAYER SETTINGS tab that changes the jog's and the sprint's speed and how long the stamina bar lasts and refills, saved to `Scripts/combat/player_tuning.csv`, which the weapons build reads; a WORLD SETTINGS tab that sets the time of day the day's and night's lengths and how fast the night cools the player, all but the hour saved to `Scripts/world/world_tuning.csv`; and a GRAPHICS SETTINGS tab, the one place the Low / Medium / High / Custom preset is picked, that changes each preset's numbers live (resolution, shadows, view distance in percent, grass and tree draw distance in metres, grass density, leaves, fog) and the look shared by all four (brightness, sun, moon, stars, ambient light, fog density), saved by its SAVE DEFAULT row to `Scripts/graphics_menu/graphics_tuning.csv`, which holds every default: each preset's numbers and which preset a new player starts on; and exit game, which quits to the desktop, saving nothing. Save and exit and the cheat need a game in play, and say so on the title. Custom is the player's own: it and the picked preset persist between sessions (`graphics_menu/gfx_save.py`). An open tab stands in place of the menu's rows and has a BACK row, as the settings page does; the graphics tab sits bottom right, five rows at a time behind a scroll bar. The settings page holds the difficulty (EASY / MEDIUM / SURVIVOR,
  default EASY). On EASY a mushroom also heals 10 HP; the other levels change nothing yet.
- **Clothing:** a hat, glasses, a shirt, a jacket, gloves, pants, boots and a backpack, one
  slot each. A garment picked up goes into the bag; the fire key with it in hand wears it
  (out of the bag, into its slot; one already worn there goes back into the bag). The worn
  garments are shown bottom right, always, over the backpack, as icons: one inventory slot per
  garment, its icon in it or, while nothing is worn there, its translucent silhouette. With **I**
  open, Up/Down and Enter (or a click) take one off into the bag, the mouse drags a worn garment
  onto the hand or a bag slot and a carried one onto the worn slots to wear it
  (`combat/weapon_component/wear_drag.py`), and a portrait of the character, facing
  forward, stands left of the panel (a render of the player's body: `item_icons/portrait.py`). Only the state exists: nothing is drawn worn and wearing changes nothing. The body
  the garments will be drawn on is generated: the adventurer in skin-tight shorts
  (`SKM_Adventurer03`, Meshy), which the player now wears
  (`Scripts/asset_pipeline/CLAUDE.md`). One of
  each lies 3 m in front of the start on `Lvl_Forest_200m` (`Scripts/clothing/CLAUDE.md`).
- **Item icons:** every item's icon, in the inventory grid and in the loot window, is a
  picture of its own 3D model, lit and fitted to the slot by `Scripts/build_item_icons.py`
  and drawn untinted (`Scripts/item_icons/CLAUDE.md`). A new or re-modelled item gets its
  icon from a re-run.
- **Proprietary notices:** the game is Ellivian Inc.'s (`LICENSE.txt`). The title and settings
  pages carry a copyright and confidentiality notice, and every screen a faint
  `ELLIVIAN INC. · CONFIDENTIAL` watermark, bottom right; `WATERMARK_RECIPIENT`
  (`graphics_menu/legal_consts.py`) stamps a shared build with who it was given to.
- **Wind:** the grass and the trees sway in the wind (world-position offset in their materials,
  `forest_generator/wind.py`), each clump and tree along a heading of its own that veers about
  the prevailing wind, in gusts that cross the map in patches; the graphics menu's GRAPHICS SETTINGS tab switches it on or off
  per preset, sets how far off it still moves, and its strength and speed
  (`graphics_menu/gfx_tuner_wind.py`).
- **The maps:** `Lvl_Forest_200m` (the editor's startup map, for debugging) and
  `Lvl_Forest_1000m` (`GameDefaultMap`: what a packaged game boots). Food and water lie
  in both.
- **Day and night:** a clock turns the sun and the moon across the sky. The day and the night
  are 4 minutes each for now (`Scripts/world/world_config.py`). The night is moonlit, dim and
  starry: the stars are the real ones (the Yale Bright Star Catalogue, as seen from 45° north:
  Orion, the Pleiades, the Pole Star), small dots beside the moon (`Scripts/world/star_map.py`). A level starts at a random time of day. At night the player's temperature falls
  slowly (0.1 a second; `Scripts/world/night_cold.py`); beside a campfire it rises (1 a second).
- **Save and exit:** the menu's save-and-exit row saves the character's stats and inventory, but not its
  location, after 15 s, then returns to the main menu. The character stands still meanwhile. A hit calls it off. The next game loads
  the profile, and death deletes it (`Scripts/graphics_menu/CLAUDE.md`).
- **Death:** once the player or a wanderer is dead (or at 0 HP), nothing it could do runs: the
  weapon component's Tick stops at its dead gate, the loot window shuts, and every step of a
  wanderer's tree refuses (`probes/probe_dead_no_actions.py`).
- **Known gaps:** a low temperature does nothing yet. Feel checks that need a play session are listed per package.

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
- **`-nullrhi` can't prove anything that touches the window or viewport.** `--game
  --windowed` renders: widgets get their geometry and the engine calls `DrawHUD` itself
  (`probe_menu_cursor_window.py`). Python still reads a widget's cached geometry as zeros.
- **Diagnosing a frozen editor:** run `sample <pid> 5 -file /tmp/hang.txt` and read the
  `GameThread` stack. `ps -o %cpu` separates a spin (100%) from a deadlock (0%).

### Config

- **An unknown `.ini` key, or a wrong section name, is silently ignored.** If a flag seems to do
  nothing, find the owning class and its `config=` file in the engine source.
- **The GameplayAbilities plugin and the gameplay tags are read only at editor startup.**
