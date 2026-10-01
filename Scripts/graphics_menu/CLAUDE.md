# The graphics menu, settings and HUD

`Scripts/build_graphics_menu.py` builds the four UMG screens (`WBP_HUD`, `WBP_MainMenu`,
`WBP_PauseMenu`, `WBP_DeathMenu`, from the parts `WBP_MenuRow` and `WBP_InventorySlot`) and
`/Game/UI/BP_GraphicsMenuHUD`, the `AHUD` that drives them, and sets
`BP_ThirdPersonGameMode.HUDClass` to it. That game mode is the global default, so the HUD is in
every level. Run `Scripts/verify_graphics_menu.py` after every edit. It is the only thing that
catches pin literals that compile but mean something else. After a change to what a screen
shows, also run `uepy.py --game --probe Scripts/probes/probe_umg_screens.py` (and
`probe_hud_low_flash.py` for the bars).

This package holds the fragments. The entry point itself is still 1.2k lines, over budget, so
split it before extending it.

**The keys:**
- **M** toggles the panel.
- **1 / 2 / 3 / 4** pick the Low / Medium / High / Ultra presets.
- **D** toggles debug mode (the FPS readout, wanderer numbers, pellet tracers and impact
  damage, the wanderers' sight cones).
- **X** (panel open) starts save and exit.
- **K** (panel open) is the dev-all-guns cheat (below).
- **T** (panel open) opens the GUN TUNING tab (below).
- **N** (panel open) opens the MONSTER TUNING tab (below).
- **O** (panel open) opens the WORLD TUNING tab (below). Opening any tuning tab shuts the
  other two.
- **Tab** (near a looted body) opens the loot window; **Up/Down** and **Enter** in it
  (`loot_tick.py`; the rules are `Scripts/loot/CLAUDE.md`).
- **The mouse** works every menu too (below).

## The mouse cursor (`cursor.py`, `cursor_consts.py`)

The cursor shows while a menu is up: the title and settings pages, the death menu, and in
play the M panel (with its tuning tabs) and the loot window. Otherwise it is hidden and the
mouse is the camera's.

| menu | cursor over a row | left click | wheel |
|---|---|---|---|
| title | the caret goes there | Enter on that row | |
| settings | the caret goes there | a bind row: arms the capture; BACK: back; a slider or the difficulty: one step up | Left / Right |
| M panel | a second caret lights | that row's key (1-4, D, X, K, T, N, O) | |
| tuning tab | the caret goes there | one step up; on the hint line: save | Left / Right |
| loot window | the caret goes there | take | |
| death menu | | on the hint line: restart | |

- **The HUD is still the controller.** No widget is hit-testable. A row is under the cursor
  when `IsUnderLocation(row.GetCachedGeometry, CursorPos)`, tested in a ForLoop over the stack
  (`author_row_cursor`), and a click is `LeftMouseButton` polled off the controller.
- **DrawHUD, not Tick:** the title and death screens are paused. `author_cursor_read` (top of
  the frame) stores `CursorPos` and `CursorMoved`; each menu's fragment then tests its own rows.
- **A resting cursor does not hold the caret.** The caret follows only when the mouse moved
  or clicked, so Up/Down still work with the cursor parked on a row.
- **A click only raises flags, which the menu's keys already serve:** `CursorAccept` (title,
  settings, death: `_emit_accept` lowers it), `PauseClick` (the M panel row; Tick's key polls
  are `or_pause_click`, and DrawHUD lowers it at the top of the next frame), the tabs'
  `nudge`/`save` flags and `LootTakeRequested`. That is what lets a probe click.
- **The wheel is two more keys** OR'd into the Left/Right polls (`menu_nav.or_wheel`), not
  the right button: that is the shoulder aim, and the M panel does not pause.
- **Shown is Game-and-UI, hidden is Game-only** (`author_cursor_mode`), switched only when
  `CursorWanted != CursorShown`. Without the Game-only call the camera stays dead after a
  menu closes until the next click.
- **A click on a row is not a shot.** While the cursor shows in a running game, DrawHUD sets
  the weapon component's `TriggerSpent` every frame (`author_hold_fire`); its Tick keeps a
  spent press spent while the fire key is down (`combat/docs/firing_gate.md`).
- **Python reads a widget's cached geometry back as zeros**, in any run. A probe cannot aim
  at a row; `probe_menu_cursor_window.py` sweeps the cursor down the screen instead.
- **Probes:** `probe_menu_cursor.py` (headless: shown and hidden per screen, the held fire
  press, each flag served) and
  `uepy.py --game --windowed --probe Scripts/probes/probe_menu_cursor_window.py` (a real
  window: every row of the M panel, title and settings pages found under the cursor). The
  windowed one moves the machine's pointer for a few seconds.
- **Still needs a play session:** the click and the wheel themselves, the cursor's look, and
  how losing the mouse-look while the M panel or the loot window is open feels.

## The UMG screens

- **The HUD is the controller, the widgets are views.** `BP_GraphicsMenuHUD` reads the game and
  polls every key; the widgets hold no logic beyond `WBP_MenuRow`'s PreConstruct. BeginPlay
  creates all four screens and adds them to the viewport (`ui_graph.py`); every `DrawHUD`
  shows the one the frame is on and writes the live values (`SetText`, `SetPercent`,
  `SetVisibility`).
- **Which screen:** `GameStarted` false → `WBP_MainMenu` (its title or settings panel by
  `MenuPage`); `PlayerDead` → `WBP_DeathMenu`; otherwise `WBP_HUD`'s `Body`, plus
  `WBP_PauseMenu` while `MenuOpen`. `WBP_HUD` itself is never hidden, so its `Fps` text (outside
  `Body`) shows over every screen.
- **Shown means `HitTestInvisible`, never `Visible`.** No widget may take a click or hover away
  from the game viewport; every key is polled off the controller, and so is the mouse
  (`cursor.py` finds the row by its geometry). The verifier asserts it.
- **Labels live in the designer.** Each menu line is a `WBP_MenuRow` whose `LabelText`,
  `LabelWidth` and `LabelColor` are set per instance (`wbp_screens.py`) and applied by its
  PreConstruct. The HUD writes only the caret (`SetRenderOpacity` 1 on the selected row, 0 on the
  rest: one ForLoop over the rows) and the value column. **Row order is MenuRow's order**:
  `SETTINGS_ROW_LABELS` must match `settings_rows.py`'s row numbers, which the verifier checks.
- **Anchored, not computed.** Each element is anchored to its corner or edge (survival bars
  bottom-left, kills and FPS top-right, banner top-centre, inventory, HP and stamina
  bottom-centre, menus centred). UMG scales them with the DPI curve (1.0 at a 1080 px shortest side).
- **Still on the canvas:** the reticle and the sniper's scope (placed off the viewport centre
  and sized by the gun's cloud every frame) and the wanderers' bars (one per wanderer, placed by
  projecting its head). The task allowed it; a widget per wanderer would need a pool or a
  widget component on the NPC.
- **Probe:** `probe_umg_screens.py` calls `ReceiveDrawHUD` itself (a `-nullrhi` run never
  renders, so the engine never does) and reads the widgets back.

## Presets (`presets.py`)

| preset | scalability | `r.ShadowQuality` | `r.ScreenPercentage` | grass shadows + DF/indirect |
|---|---|---|---|---|
| Low | 0 | 1 | 70 | off |
| Medium | 1 | 2 | 85 | off |
| High | 3 (Epic) | 3 | 100 | off |
| Ultra | 3 (Epic) | 3 | 100 | **on** |

- **The console commands are needed.** `DefaultEngine.ini` pins `r.ShadowQuality=3` at
  project-setting priority, which outranks scalability. A console command outranks both.
- **Grass lighting is per component, not a cvar.** When `Quality != GrassQualityApplied`, the
  first Tick block walks every actor tagged `OW_Grass`. The grass-lit presets must stay at the
  top of the table, which is asserted.
- **BeginPlay applies `DEFAULT_PRESET` (Low).** Settings are never saved, so every launch starts
  at Low.
- **In PIE these cvars stick to the editor viewport.** Restore it with
  `r.ScreenPercentage 100` and `r.ShadowQuality 3`.
- **Never call `GameUserSettings.ApplySettings`.** It applies resolution too, which hangs the Mac
  editor in PIE at 100% CPU. Use `ApplyNonResolutionSettings()`. The verifier asserts this. A
  `-nullrhi` run cannot catch the hang.

## Settings screen

- **The main menu:** NEW GAME and SETTINGS rows, navigated with Up/Down and chosen with
  Enter/Space, or by a click on the row.
- **The settings page:**
  - mouse sensitivity (Left/Right, clamped to a minimum above zero);
  - DIFFICULTY: EASY / MEDIUM / SURVIVOR (Left/Right cycle it; default EASY). Saved as the int
    `BP_Settings.Difficulty` and copied onto the GameMode's `Difficulty` every `DrawHUD`
    (`difficulty.py`). Only EASY does anything yet (the mushroom heal). `-nullrhi` runs no
    `DrawHUD`, so a headless game keeps the GameMode's own default, EASY;
  - the keybinds, one row per `BIND_VARS` entry (Enter arms a capture; the next key from `KEY_POOL` becomes the bind;
    navigation keys are not in the pool);
  - BACK.
- **`BP_Settings`** is a `USaveGame` saved to slot `OtherworldSettings` on **every change**.
  - `build_weapons_and_combat.py` builds it, because both consumers need the class and that
    builder runs first.
  - **Branch on `Capturing` before activating the row.** Enter stays "just pressed" for that
    whole frame.
  - **The HUD pushes the settings into `BP_WeaponComponent` every `DrawHUD`.** The component never
    loads the save. Its CDO key defaults stay valid for a pawn with no HUD.
  - **`BP_Settings.Binds` is indexed by `BIND_VARS` (`combat/tuning.py`).** Reordering it rebinds
    every existing save. BeginPlay refills the array when its length isn't `len(BIND_VARS)`.

## Save and exit, and the saved profile

`save_exit.py` (the Tick fragment; `__init__.py` maps the rest) runs every Tick, after the grass
sync:

- **X with the panel open** closes it and starts a 15 s countdown (`EXIT_SECONDS`), drawn top
  centre (`profile_draw.py`). When it runs out, the player's stats and inventory go into a fresh
  `/Game/UI/BP_Profile` (a `USaveGame`, slot `OtherworldProfile`) and the current level reopens,
  which opens on the main menu.
- **Stored:** Health, Stamina, Hunger, Thirst, Temperature, the kill count, the equipped slot,
  and each carried item's class, `Loaded` and `Reserve`. **Never the location**; the verifier
  asserts BP_Profile has no other field.
- **The character can't move during the countdown.** Every Tick it waits, the pawn's
  `CharacterMovement` gets `DisableMovement` (keyed off `ExitPending`, not the X press, so the
  probe's variable writes freeze it too). Looking around still works.
- **A hit calls it off**, and `SetMovementMode(Walking)` frees the pawn. A wanderer's swing stamps
  the player's `BP_HealthComponent.LastDamageTime` (`npc/melee.py`), and the countdown stops when
  that passes `ExitStartedAt`. The starvation
  drain lowers Health without stamping it, so it is not a hit.
- **Loading:** the first Tick of a started game (after NEW GAME, or at once with `-nomenu`) on
  which the weapon component's Inventory is non-empty sets `ProfileChecked` and, if the slot
  exists, applies it: stats back, the issued loadout destroyed, the saved items spawned with
  `Dropped = false`, then `NeedsRefresh` so the component equips them itself. Gating on the
  loadout keeps the issued guns from being added after the saved ones.
- **Death deletes the slot.** `Health <= 0` on Tick, once (`ProfileForgotten`). Tick, not
  DrawHUD: the death pause comes after a 2.2 s settle, and a `-nullrhi` probe never draws.
- **Probe:** `uepy.py --game --probe Scripts/probes/probe_save_exit.py`. It covers the freeze, a
  hit calling the exit off and freeing the pawn, the save, the reload and restore, a crafted inventory replacing the
  issued one, and the delete on death. It sets aside any real profile on disk and puts it back.
- **Still needs a play session:** the X key itself and the 15 s at real speed (the probe
  writes the countdown's variables), and how the banner reads.

## The dev-all-guns cheat (`dev_guns.py`, `dev_consts.py`)

A testing aid on the M panel's last row. **K with the panel open** raises the HUD's
`DevAllGunsRequested`; the next Tick (run from `save_exit.py`, after the countdown) lowers it and,
for each of the five guns and the knife in `DEV_GUN_CLASS_PATHS`, spawns one if none is carried and the bag has
room (`INVENTORY_SIZE`): `Dropped = false`, `Inventory += it`, then `NeedsRefresh`. The held item
stays held, as with a pick-up; asking twice adds nothing.

- **K, not G:** the weapon component polls its keys whether the panel is open or not, so G would
  also drop the held gun.
- **`profile_checks` tells its `Set Dropped`/`Set NeedsRefresh` apart from the cheat's** (the
  cheat's item comes through a cast; its refresh follows no `Set EquippedIndex`).
- **Probe:** `uepy.py --game --probe Scripts/probes/probe_dev_all_guns.py` writes the request
  flag (no keyboard in a probe). The K key itself needs a play session.

## The loot window (`loot_*.py`, `wbp_loot.py`)

Run from Tick after save and exit; the design is `Scripts/loot/CLAUDE.md`. Traps met here:

- **Every `Clamp` node in this graph is read as a settings slider** by the verifier, so the
  window clamps `LootSel` with `Min` then `Max`.
- **The take reuses the cheat's pattern** (spawn, cast, `Dropped`, `Inventory += it`,
  `NeedsRefresh`). `dev_guns_checks._looting` tells the take's nodes apart from the cheat's.
- **Probe:** `probe_corpse_loot.py` calls `ReceiveDrawHUD` itself to read the window.

## The GUN TUNING tab (`tune_*.py`, `wbp_tune.py`)

A developer tab beside the M panel: **T with the panel open** toggles `TuneOpen`. Up/Down pick
the gun row or one of the 19 stat rows (`combat/gun_tuning.TUNE_STATS`); Left/Right change the
gun, or move the stat one step (never under its minimum); **Enter** saves
`Scripts/combat/gun_tuning.csv`.

- **The table lives on the HUD:** `TuneValues` (guns x stats, flattened), `TuneWeapons`,
  `TuneSteps`, `TuneMins`, all baked from `_weapon_specs()` (so from the CSV) at build time.
- **Applied every Tick once touched** (`TuneTouched`): each carried item whose `DisplayName` is
  in `TuneWeapons` gets all 19 variables (ints rounded). Every Tick rather than per nudge, so a
  gun picked up afterwards gets the tuning too. Guns lying in the world get it when picked up.
- **The save is Python**, through `PythonScriptLibrary.ExecutePythonCommand`
  (`TUNE_SAVE_COMMAND` → `tune_save.save()`), which reads the live HUD's table. Blueprint can't
  write a file. So it works in the editor, PIE and `-game` of the editor binary, not in a
  packaged build: a dev tool. `TuneSaved` shows "saved to ..." until the next change.
- **The keys only raise flags** (`TuneNudge`, `TuneSaveRequested`), which is what lets
  `probe_gun_tuning.py` tune and save. It backs up the CSV and puts it back.
- **Still needs a play session:** the keys themselves and how the 20-row panel reads.
- **The machine is shared with MONSTER TUNING:** the keys, nudge and save are
  `tune_tick.author_tab_flow` over a `TuneTab` (`tune_tab.py`); the panel is `tune_draw` and
  `wbp_tune` over the same. Only the apply differs. The verifier tells the two save calls apart
  by their command.

## The MONSTER TUNING tab (`monster_tune_*.py`)

**N with the panel open** toggles `MonTuneOpen` (and shuts `TuneOpen`; T shuts this one). The
creature row, then the 13 stats of `npc/monster_tuning.MONSTER_STATS`: aggro range, aggro cone
(half-angle), hearing, touch range, patrol radius, patrol speed, the patrol re-pick window, run
speed, damage per hit, melee range, time between swings, health. Same keys as GUN TUNING;
**Enter** saves `Scripts/npc/monster_tuning.csv`.

- **Each number is a `Tune*` variable on the creature's AI controller** (`npc/tuned.py`), which
  every NPC graph reads instead of a pin literal. The HUD's table (`MonTuneValues`, creatures x
  stats) is baked from `monster_specs()` (so the CSV) at build time.
- **Applied every Tick once touched** (`MonTuneTouched`): for each creature, `GetAllActorsOfClass`
  of its controller class, a cast, and 13 Sets from the table (the cell index is a literal on
  `Array_Get`, known at build time). A wanderer spawned or respawned later gets it within a Tick.
- **What "immediately" means per stat:** senses, patrol and melee take effect on the
  wanderer's next tree pass (0.5 s). The Chase and Stroll steps rewrite `MaxWalkSpeed` every
  pass, so speeds do too. Health is re-applied when `TuneHealth` differs from the controller's
  `AppliedHealth`: a live wanderer jumps to the new maximum, **full**.
- **The CSV feeds two builds:** `build_npc_blueprints.py` (the controllers' defaults), then
  `build_graphics_menu.py` (the HUD's table). `verify_npc_blueprints` and `monster_tune_checks`
  compare against the CSV, so a saved tuning passes them once rebuilt. The level verifiers pin
  the melee numbers at generation time: tuning those fails "NPC Melee ... (TuneMelee...)" until
  the level is regenerated.
- **The verifier's whole-graph scans exclude this tab:** the wanderer-bar scan skips
  `ForestWandererAI` classes, and the Binds read-by-index check skips `Get MonTuneValues`.
- **Probe:** `probe_monster_tuning.py` (12 checks: the live write, the floor, the wendigos
  untouched, a speed and a health nudge reaching the pawn, the wrap, the CSV, the panel). It
  backs up the CSV and puts it back.
- **Still needs a play session:** the N key, how the 14-row panel reads, and how a tuned
  wanderer feels.

## The WORLD TUNING tab (`world_tune_*.py`)

**O with the panel open** toggles `WorldTuneOpen`. One subject row (`world`), then
`world/world_tuning.WORLD_STATS`: the time of day (hours, step 0.5), the day's length and the
night's (seconds, step 30). Same keys as GUN TUNING; **Enter** saves the two lengths to
`Scripts/world/world_tuning.csv` (the hour is never saved: a level starts at a random one).

- **The hour is a 24-hour dial over the cycle's `Clock`:** sunrise 06:00, sunset 18:00, each
  half 12 hours whatever its length (`world_config.clock_to_hour`/`hour_to_clock`, which the
  graph mirrors with two `MapRangeClamped` each way).
- **Only while the tab is open,** each Tick: `GetActorOfClass(BP_DayNightCycle)`, a cast, then
  the lengths onto it (once touched), then `Clock := hour_to_clock(WorldTuneValues[0])` **only
  when that cell differs from `WorldTuneHourSeen`**, then the live clock read back into both.
  Writing the hour every Tick would stop time; the read-back is what makes a nudge step from
  the hour on screen.
- **The CSV feeds** `world_config` (so `build_day_night.py`, the cycle's defaults, then
  `build_graphics_menu.py`, the HUD's table). `verify_day_night` checks the lengths against it.
- **The verifier's whole-graph scans exclude this tab:** the Binds read-by-index check skips
  `Get WorldTuneValues`, and the scalability-level scan skips `MapRangeClamped` (it has a
  `Value` pin).
- **Probe:** `probe_world_tuning.py` (7 checks: the random start, the hour on the dial, a nudge,
  crossing into the other half, a length, the CSV, the panel). It backs up the CSV and puts it
  back.
- **Still needs a play session:** the O key, and how the sky looks when the hour jumps.

## HUD

**What it shows each frame:**

- **Bottom-left:** the FOOD / H2O / TEMP bars, vertical and filling from the bottom
  (`survival_bars.py`), each over its icon and label; STARVING and DEHYDRATED stack above
  them, read from the ASC's tags. Vertical bars use `T_UI_BarV`/`T_UI_BarTrackV`
  (`ui_art/vertical_bars.py`): the horizontal art stood upright shades along the bar, so a
  nearly empty fill showed only its dark foot and read as another colour.
- **Every bar has a stat icon** (`ui_art/stat_icons.py`: white glyphs, tinted the bar's
  fill colour in the Image widget) and sits with it in a group widget (`HpStat`, `StaStat`,
  `<Stat>Stat`). **Low bars blink** (`hud_flash.py`): under `LOW_FRACTION` (25%) the group's
  render opacity drops to `FLASH_DIM` every other half-beat at `FLASH_HZ`, on
  `GetRealTimeSeconds` so it still blinks under the paused M panel. Real time moves only
  between frames, so a probe must draw once a frame to see it
  (`probe_hud_low_flash.py`).
- **Top-right:** the kill counter, and the FPS readout in debug mode only.
- **Wanderers:** a projected health bar over each one, plus its number in debug mode.
- **Bottom:** the 10-slot inventory grid, in two rows of five (`INVENTORY_COLUMNS`, 84 x 59
  slots, `hud_inventory.py`), with loaded/reserve counts for weapons that use ammo. Slot *i*
  shows `Inventory[i]`, read only behind `IsValidIndex`; a slot past the end is emptied every
  frame. Under the grid, side by side in the `Vitals` row: HP (icon, bar, number,
  `hud_stats.py`) and stamina (icon, bar, `stamina_bar.py`); all in one bottom-anchored
  stack in `WBP_HUD`.
- **Centre:** the reticle or scope (`reticle.py`). The reticle's four ticks stand off by the held
  gun's accuracy cloud: `ReticleSpread` (weapon component) × half the viewport width, capped at
  `RETICLE_SPREAD_MAX` with an `FMin` (an `FClamp` would be read as a settings slider).
- **When the player is dead:** only the death menu. `DrawHUD` branches on `GameMode.PlayerDead`
  first.

**Rules:**

- **Anchor widgets; lay out the canvas layers from the viewport size.** Read slot colour, name
  and ammo from each item's own `SlotColor`/`DisplayName`/`UsesAmmo`/`Loaded`/`Reserve`. The HUD
  keeps no list of weapons.
- **A wanderer's bar shows only for 5 s after it is hurt** (`LastDamageTime`, default −1000). It
  is gated on `NOT Dead`.
- **`NpcKillCount` lives on the GameMode** and only counts kills with `DamagedByPlayer` set.
- **The FPS readout counts real time over a 0.5 s window.** Never drive a HUD element with a
  `stat` command: `stat fps` is a toggle, and in PIE its state outlives the session. The verifier
  rejects it.
- **The death menu and the restart key are handled in `DrawHUD`,** because Tick is paused.
- **A cast-failed path still reaches the rest of the HUD with a real value** (e.g. `DebugOn`
  false). Never read off an invalid object there.

## Gotchas specific to this graph

### Authoring the widget trees (`umg_author.py`)

- **The way in is the UMGToolSet plugin** (`Engine/Plugins/Experimental/Toolsets`, enabled for
  the editor only in `Otherworld.uproject`). Its functions are `AICallable`, not
  `BlueprintCallable`, so they have no Python methods; reach them with
  `unreal.get_default_object(unreal.UMGToolSet).call_method("AddWidget", (...))`. It needs an
  editor restart after enabling.
- **Rebuilding empties the tree in place** (remove the root: it takes its subtree) and wipes the
  event graph **first**: a node reading a widget variable stops compiling the moment the tree
  empties. Recreating the asset would strand the HUD's variables typed to it.
- **`AddWidget` sanitises a clashing name** into `Name_0`; `add()` asserts the name, because the
  HUD finds widgets by name. Mark every widget the HUD writes as a variable.
- **`SlateBrush.image_size` is a `DeprecateSlateVector2D`**, which takes no `Vector2D` and has
  no `.x`: write it with `import_text("(X=..,Y=..)")`, read it with `export_text()`.
- **A `SlateColor` default can't go through `_apply_defaults`**: `_same()` walks `to_tuple()`,
  which nests a `LinearColor`. Compare `export_text()`.
- **A `Text` pin literal reads back as `NSLOCTEXT("", "<key>", "<words>")`**;
  `umg_checks.text_literal` extracts the words.
- **Macro and library pin names:** the `ForLoop` macro's exec input is `execute` (the
  `ForEachLoop`'s is `Exec`); `Array_IsValidIndex` takes `IndexToTest`;
  `ProgressBar.SetFillColorAndOpacity` takes `InColor`.
- **Seeing a screen:** a `-nullrhi` probe proves the values, not the look. A `-game` run without
  `-nullrhi` (`-windowed -ResX=1280 -ResY=720`) renders on this Mac, and the console command
  `shot showui` saves the viewport with its widgets to `Saved/Screenshots/MacEditor/`.

### The HUD graph

- **`FKey` pin defaults are the bare key name** (`M`, `One`), not `(KeyName="M")`. Struct text
  compiles and never matches.
- **Nodes are identified by input-pin signature** in the verifier. `get_node_title` is fine for
  variable nodes (`Get DebugMode`) but ambiguous for calls, e.g. `Array_Get` is just `Get`.
