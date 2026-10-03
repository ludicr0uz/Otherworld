# The menu (the title's, and M's in play), settings and HUD

`Scripts/build_graphics_menu.py` builds the four UMG screens (`WBP_HUD`, `WBP_MainMenu`,
`WBP_PauseMenu`, `WBP_DeathMenu`, from the parts `WBP_MenuRow` and `WBP_InventorySlot`),
`/Game/UI/BP_GraphicsTuner` (the component that applies a quality preset) and
`/Game/UI/BP_GraphicsMenuHUD`, the `AHUD` that drives them, and sets
`BP_ThirdPersonGameMode.HUDClass` to it. That game mode is the global default, so the HUD is in
every level. Run `Scripts/verify_graphics_menu.py` after every edit. It is the only thing that
catches pin literals that compile but mean something else. After a change to what a screen
shows, also run `uepy.py --game --probe Scripts/probes/probe_umg_screens.py` (and
`probe_hud_low_flash.py` for the bars).

This package holds the fragments. The entry point itself is still 1.2k lines, over budget, so
split it before extending it.

**There is one menu** (`WBP_PauseMenu`, titled **OTHERWORLD**, off the top left at
`PAUSE_POS`). The game opens on it, paused, and **M** brings the same one up in play, where
it pauses nothing. The code and the notes below still call it "the M panel".

**The keys:**
- **M** toggles the menu in play: the only key it has. On the title it cannot be shut.
- **Up / Down** move the menu's caret and **Enter** takes the row it is on; a click on a
  row takes it too. **No row has a hotkey** (the 1-4, D, X, K, T, N, O and P keys are gone).
- **The rows:** `New Game` (in play it reads `Resume` and shuts the menu), `Settings` (the
  settings page), `Debug` (wanderer numbers, pellet tracers and impact damage,
  the wanderers' sight cones; not the FPS readout, which is always on), `Save and Exit`, `Dev All Guns`, `Gun Settings`,
  `Monster Settings`, `World Settings`, `Player Settings`, `Graphics Settings`, `Exit Game` (quits to the desktop,
  saving nothing). The quality presets are not
  rows: Low / Medium / High / Custom is the graphics tab's first row.
- **The settings page or a tuning tab stands in place of the menu's rows**, and its **BACK**
  row returns to them (below: "The M panel as a menu").
- **Tab** (near any body) kneels and opens the loot window; **Up/Down** and **Enter** in it
  (`loot_tick.py`; the rules are `Scripts/loot/CLAUDE.md`).
- **I** opens the inventory (the I panel): the backpack shows under the worn garments,
  bottom right, and the character's portrait left of them (`wear_*.py`, `inv_*.py`, `Scripts/clothing/CLAUDE.md`). **Up/Down** run the
  caret over the worn rows, then the bag's slots; **Enter** takes a garment off, or brings
  a bag slot's item to hand; the mouse drags an item from slot to slot (below). It does not
  pause, holds the walk while open, and hides under the menu; with the loot window open
  too, the arrows and Enter are the loot window's. **1-9** are the weapon component's
  (`combat/slot_tuning.py`).
- **The mouse** works every menu too (below).

## One menu: the title's and M's (`menu_main.py`, `menu_screens.author_title`)

- **The title is the menu held open.** While `GameStarted` is false DrawHUD hides the HUD's
  `Body` and the death menu, sets `MenuOpen` and goes on to the same fragment that draws
  the menu in play (`author_pause_menu`). There is no title page: `WBP_MainMenu` holds only
  the settings page and the legal notice, and goes up and down with the menu.
- **The HUD ticks under the title's pause.** Every row is served on Tick, and Event Tick
  does not run in a paused world, so BeginPlay calls `SetTickableWhenPaused(true)` on the
  HUD (and on its tuner component, so a preset picked on the title is applied there) on
  its way to the pause. The first row takes it back before it unpauses, so the death
  screen's pause still stops Tick, as it always did.
- **The first row** (`START_ACTION`) lowers `MenuOpen`; on the title it then sets
  `GameStarted`, stops the paused tick and unpauses, last. DrawHUD writes its label every
  frame: `new game` or `resume`.
- **`settings`** sets `MenuPage` to the settings page and `MenuRow` to 0. The page
  (`WBP_MainMenu.SettingsPanel`, at `PAUSE_POS` like the menu) shows while `MenuPage` says
  so and the menu's `Panel` is collapsed; its BACK row sets `MenuPage` back. In play the
  page does not pause either, and its accept keys include Space, which also jumps.
- **`exit game`** is `QuitGame` for the owning player: the one such node in the graph.
- **What needs a game in play is kept off the title:** Tick splits on `GameStarted`
  (`author_in_play`), and save and exit (with the profile load, the death wipe and the
  cheat) and the loot window run only in play. On the title those rows' value column reads
  `in game only` (`IN_GAME_ACTIONS`). The tuning tabs and debug work on the title.
- **M is polled only in play** (a Branch on `GameStarted`, then the key): the title's menu
  has nothing under it to go back to.
- **Probes:** `probe_main_menu.py` pauses the game itself and shows both halves: with the
  HUD not ticking a taken row is not served, ticking it is; save and exit does nothing
  there; the first row starts the game, and in play only shuts the menu.
  `probe_umg_screens.py` reads what the title shows.
- **A probe's game never sees the real title:** `uepy.py --game` passes `-nomenu`, and
  `probes/boot.py` waits 0.5 s of game time before the first probe, which the title's
  pause (0.25 s in) never reaches. The real BeginPlay path was checked once by hand
  (a windowed run without `-nomenu` and with that wait at 0: paused, the menu up, a row
  served, new game unpausing, exit game ending the process).
- **Still needs a play session:** the keys themselves on the title, exit game from a real
  session, and how the title reads with the paused level behind it.

## The M panel as a menu (`menu_screens.py`, `menu_nav.py`, `menu_still.py`)

- **A row is an action, not a key.** `umg_consts.PAUSE_ROW_ACTIONS` names each row's action in
  row order. Taking row *i* (Enter on the caret's row, or a click) sets `PauseClick = i` in
  DrawHUD; the next Tick, the fragment that owns the action sees
  `menu_nav.pause_row_taken(action)` and serves it; DrawHUD lowers `PauseClick` at the top of
  the next frame. A probe takes a row by writing `PauseClick`.
- **`PauseRow` is the caret.** Up / Down and Enter are polled in DrawHUD (`_author_pause_keys`),
  only while no tab and no settings page is open. Enter, not Space: the panel does not pause, and Space jumps.
- **One menu on screen.** `WBP_PauseMenu.Panel` (the panel's own artwork and rows) is
  collapsed while the settings page is up or any tab's open flag is, and the page or the open tab's panel shows instead; the four
  developer tabs sit where the panel does (`TUNE_POS`), the graphics tab in the corner.
- **BACK is a `WBP_MenuRow` under each tab's list**, the caret's last stop
  (`TuneTab.back_row`: one past the list, or two in the graphics tab, whose SAVE DEFAULT
  row comes between). A click on it, or Enter with the caret on it, lowers
  the tab's open flag. **That is DrawHUD's** (`cursor.author_back_row`), though the rest of a
  tab's keys are Tick's: Enter is "just pressed" for the whole frame, the panel's own Enter is
  polled in DrawHUD *before* the tab's fragment and only while no tab is open, so the Enter
  that shuts a tab cannot also take the row the panel's caret was left on (which would open the
  tab again). For the same reason Tick's save Enter, Left and Right skip the BACK row.
- **Opening a tab puts its caret on its first row.** M with a tab open shuts the panel and
  leaves the tab's flag up, so M again comes back to the tab.
- **The open panel holds the player still** (`menu_still.py`): `SetIgnoreMoveInput` on
  `MenuOpen`'s edges, as the loot window does (the two counts stack). The stock input mapping
  walks on the arrows as well as WASD, so Up / Down on a row also walked the character.
- **A scrolling list** (`TuneTab.visible_rows`, the graphics tab's 5): the rows box is a
  `ScrollBox` inside a `SizeBox` `visible_rows x TUNE_ROW_H` high, bar always shown.
  - Nothing is hit-testable, so the bar is a picture and the HUD scrolls: every DrawHUD,
    `ScrollWidgetIntoView(child at the caret's row)`, unanimated.
  - The wheel is Up / Down there (the caret moves, the list follows), not Left / Right.
  - **A row scrolled out of the window keeps its geometry**, and lies over the hint and BACK
    below: the row test is ANDed with "the cursor is over the box" (`author_row_cursor`'s
    `within`).
  - `TUNE_ROW_H` (22.5) is a `WBP_MenuRow`'s desired height read off a rendered run
    (`get_desired_size()` works in a windowed `-game`; cached geometry still reads zeros).
- **Probes:** `probe_menu_cursor.py` (a taken row served once, the tab in the panel's place,
  BACK's caret, the walk taken and given back) and the windowed `probe_menu_cursor_window.py`
  (the graphics tab's five rows under the cursor and no more, the list scrolled to its end).
- **Still needs a play session:** Enter and the arrows themselves, the click on BACK, the
  wheel in the scrolling list, and how the corner panel reads.

## The mouse cursor (`cursor.py`, `cursor_consts.py`)

The cursor shows while a menu is up: the menu (on the title and in play, with its settings
page and tuning tabs), the death menu, the loot window and the I panel. Otherwise it is hidden and the
mouse is the camera's.

| menu | cursor over a row | left click | wheel |
|---|---|---|---|
| settings | the caret goes there | a bind row: arms the capture; BACK: back; a slider or the difficulty: one step up | Left / Right |
| M panel | the caret goes there | takes the row (as Enter does) | |
| tuning tab | the caret goes there | one step up; on the hint line: save (the graphics tab: on its SAVE DEFAULT row); on BACK: back to the panel | Left / Right (the graphics tab: Up / Down, its list scrolls) |
| loot window | the caret goes there | take; on the `[TAB] close` line: shut | |
| I panel | the caret goes there (a worn row) | take that garment off; on the `[I] inventory` line: shut; on a slot: bring it to hand; a press on one slot and a release on another: move it there | |
| death menu | | on the hint line: restart | |

- **The HUD is still the controller.** No widget is hit-testable. A row is under the cursor
  when `IsUnderLocation(row.GetCachedGeometry, CursorPos)`, tested in a ForLoop over the stack
  (`author_row_cursor`), and a click is `LeftMouseButton` polled off the controller.
- **DrawHUD, not Tick:** the title and death screens are paused. `author_cursor_read` (top of
  the frame) stores `CursorPos` and `CursorMoved`; each menu's fragment then tests its own rows.
- **A resting cursor does not hold the caret.** The caret follows only when the mouse moved
  or clicked, so Up/Down still work with the cursor parked on a row.
- **A click only raises flags, which the menu's keys already serve:** `CursorAccept` (
  settings, death: `_emit_accept` lowers it), `PauseClick` (the M panel row; Tick's fragments
  test `pause_row_taken`, and DrawHUD lowers it at the top of the next frame), the tabs'
  `nudge`/`save` flags and `LootTakeRequested`. That is what lets a probe click.
- **Every menu that can be shut has a button for it.** The M panel's first row in play is
  `resume` (it lowers `MenuOpen`, as M does), and every tuning tab has BACK. The loot window's `LootClose` line lowers
  `LootOpen` (`loot_draw.py`), and Tick stands the player up off that edge as after Tab. The
  settings page has its BACK row. The title's menu and the death screen have nothing to shut.
- **The wheel is two more keys** OR'd into the Left/Right polls (`menu_nav.or_wheel`; in a
  scrolling tab, the Up/Down polls), not the right button: that is the shoulder aim, and the
  M panel does not pause.
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
  window: every row of the M panel, in play and on the title, and of the settings page found under the cursor). The
  windowed one moves the machine's pointer for a few seconds.
- **Still needs a play session:** the click and the wheel themselves, the loot window's
  close line under a real cursor (no probe can aim at it), the cursor's look, and
  how losing the mouse-look while the M panel or the loot window is open feels.

## The UMG screens

- **The HUD is the controller, the widgets are views.** `BP_GraphicsMenuHUD` reads the game and
  polls every key; the widgets hold no logic beyond `WBP_MenuRow`'s PreConstruct. BeginPlay
  creates all four screens and adds them to the viewport (`ui_graph.py`); every `DrawHUD`
  shows the one the frame is on and writes the live values (`SetText`, `SetPercent`,
  `SetVisibility`).
- **Which screen:** `GameStarted` false → the menu alone, held open (`Body` hidden);
  `PlayerDead` → `WBP_DeathMenu`; otherwise `WBP_HUD`'s `Body`. In either of the first and
  last, `WBP_PauseMenu` while `MenuOpen` (its own rows, or the settings page, by
  `MenuPage`, or the open tuning tab in their place), with `WBP_MainMenu` up beside it.
  `WBP_HUD` itself is never hidden, so its `Fps` text (outside
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
  bottom-centre, the death menu centred, the menu and its settings page off the top left at
  `PAUSE_POS`). UMG scales them with the DPI curve (1.0 at a 1080 px shortest side).
- **The proprietary notices** (`legal_consts.py`, `wbp_legal.py`; the game is Ellivian Inc.'s,
  see `LICENSE.txt`) are static designer text that no graph touches. `WBP_MainMenu`'s
  `LegalNotice` (copyright and confidentiality lines) sits bottom-centre on Root, outside the
  settings panel, so it is up whenever the menu is: on the title and behind M. `WBP_HUD`'s `Watermark` sits bottom-right on Root, outside `Body` like `Fps`, so it is
  over every screen, in the corner the inventory strip and the loot window leave free.
  **Stamping a shared build:** set `WATERMARK_RECIPIENT` and re-run the build; it adds an
  `ISSUED TO` line (empty = no line). Neither is a variable: a live probe reaches them as
  children of a variable sibling's parent (`probe_legal_notices.py`, windowed, which also
  saves the `shot showui` pictures).
- **Still on the canvas:** the reticle and the sniper's scope (placed off the viewport centre
  and sized by the gun's cloud every frame) and the wanderers' bars (one per wanderer, placed by
  projecting its head). The task allowed it; a widget per wanderer would need a pool or a
  widget component on the NPC.
- **Probe:** `probe_umg_screens.py` calls `ReceiveDrawHUD` itself (a `-nullrhi` run never
  renders, so the engine never does) and reads the widgets back.

## Presets and the GRAPHICS SETTINGS tab (`gfx_*.py`, `presets.py`)

A preset is **one row of the graphics table** (`gfx_stats.GFX_STATS`, 28 numbers), and
`graphics_tuning.csv` is the tracked copy. The defaults are what the presets always did:

| preset | engine quality | `r.ShadowQuality` | `r.ScreenPercentage` | view distance | grass / tree draw distance | grass layers | grass shadows + DF/indirect |
|---|---|---|---|---|---|---|---|
| Low | 0 | 1 | 70 | 40% | 28 m / 120 m | 1 | off |
| Medium | 1 | 2 | 85 | 60% | 42 m / 180 m | 2 | off |
| High | 3 (Epic) | 3 | 100 | 100% | 70 m / 300 m | 3 | off |
| Custom (starts as) | 3 (Epic) | 3 | 100 | 100% | 70 m / 300 m | 4 | **on** |

**The M panel's `Graphics Settings` row** opens the tab (`GfxTuneOpen`). The subject row is
the preset: Left/Right there pick Low / Medium / High / Custom, and it is the only place a
preset is picked. The rows under it are that preset's numbers. Under the list, the
**SAVE DEFAULT** row (Enter on it, or a click) saves all four presets, and the picked one
as the default, to `Scripts/graphics_menu/graphics_tuning.csv`, which the next build bakes
into the HUD. Enter on a number saves nothing in this tab.

- **The CSV is the defaults, all of them.** Each preset's numbers, and in its `default`
  column (1 on one row; `gfx_stats.default_preset`, `presets.DEFAULT_PRESET`) the preset a
  player with no save starts on. No file or no mark: Low. The CSV is read at build time, so
  a SAVE DEFAULT shows in a game after the next `build_graphics_menu.py`.
- **Custom is the player's own preset, and it persists** (`gfx_save.py`). It took Ultra's
  place and its defaults. Every change of the pick or of a number goes into
  `/Game/UI/BP_GraphicsSave` (a `USaveGame`, slot `OtherworldGraphics`: `SavedQuality` and
  `SavedTable`, the whole table) from the hand-over in `gfx_tune_tick.py`. BeginPlay sets
  `Quality` to the CSV's default, then lays the save over it: the saved pick, and **only
  Custom's row** of the saved table. Low, Medium and High are the CSV's for every player; a
  session's nudges to them last the session unless SAVE DEFAULT writes them.
  - **The first hand-over of a session is not saved** (`GfxQualityApplied` still -1): it is
    what was just loaded. So a player who never touches the tab has no save file.
  - **A saved table of another length is ignored**, pick and all: it is another build's
    (`STAT_COUNT` moved), and its Custom row would land on the wrong stats.
  - **A look number nudged on any preset is in Custom's row too** (the spread, below), so
    it is kept with Custom and comes back when Custom is picked. SAVE DEFAULT writes the
    look of the picked preset, the one on screen, to every row of the CSV.
  - **The save is a Blueprint SaveGame, so it works in a packaged build;** SAVE DEFAULT is
    Python and does not.
  - **`SavedQuality`, not `Quality`:** the verifier counts the HUD's own `Set Quality`
    nodes by title.

- **The tab is small and out of the way:** bottom right (`TuneTab.corner`), a 13 pt title, five
  rows at a time behind a scroll bar (above: "A scrolling list").
- **The table is in a person's units.** A scale is a percentage (100 = the engine's own) and
  `Stat.scale` (0.01) turns it back into what the cvar or the cycle takes
  (`gfx_tuner_read.applied`). The draw distances are **metres**.
- **A metre is a metre at any view distance.** The engine multiplies every cull distance by
  `r.ViewDistanceScale`, so the tuner's ratio to the level's own distances is
  `metres / (FULL_VIEW_M x view distance % / 100)` (`gfx_tuner_foliage._wanted`;
  `FULL_VIEW_M`: grass 70 m, the base tier's fade end, trees 300 m). The applied variables
  hold that ratio, so nudging the view distance re-walks the cells. The grass metres are the
  base layer's; the thicker layers and the bushes keep their proportion to it.
- **An old CSV is in the old units.** A `graphics_tuning.csv` saved before this (0.4, 1.0)
  reads as 0.4% and 1 m; the tracked one was rewritten.

- **Performance rows are per preset:** engine quality (the scalability level), resolution,
  shadow quality and distance (%), view distance (%), grass and tree draw distance (metres),
  grass density (layers 1-4), grass shadows, leaf cut-outs
  (`r.Nanite.ProgrammableRaster`: off draws every leaf card solid), tree coarseness
  (`r.Nanite.MaxPixelsPerEdge`), fog and volumetric fog on/off, GI, reflections, AA,
  wind on/off and wind distance (metres; below).
- **Look rows are one number for all four presets:** brightness (`r.ExposureOffset`, in
  EV), sunlight, sun disc, moonlight, moon disc, stars, ambient light and fog density,
  each a percentage of what `world_config` sets, and wind strength and wind speed, each a
  percentage of `forest_generator/wind.py`'s. A nudge writes the picked preset's look
  into every row (`gfx_tune_tick._author_spread`), and the CSV is read from the first.
- **Two owners.** The HUD holds the table and the tab (`gfx_tune_tick.py`, on the shared
  tab machine). `BP_GraphicsTuner`, an ActorComponent on the HUD (`gfx_tuner*.py`), turns a
  row into the engine's state. The HUD hands it `Values`, `Preset` and `Dirty` whenever a
  number was touched or `Quality != GfxQualityApplied`.
- **Picking a preset only sets `Quality`.** BeginPlay's default and the tab's preset row
  both reach the engine through that one hand-over, on the next Tick.
  `GfxQualityApplied` starts at -1, so the first Tick of every session applies whatever
  BeginPlay left in `Quality` (the saved pick, else the CSV's default).
- **The console commands are needed.** `DefaultEngine.ini` pins `r.ShadowQuality` (and the
  GI, reflection and AA methods) at project-setting priority, which outranks scalability.
  A console command outranks both. One command per cvar stat, on every apply.
- **Grass and tree numbers are per component, not cvars.** The tuner walks the cells
  (`gfx_tuner_foliage.py`), each walk only when its own number moved: grass by the
  `OW_Grass` tag, density tiers by `OW_GrassTier<n>`, trees as "an instanced-mesh root
  that is not grass" (the levels carry no tree tag).
- **A cell's distance is scaled by wanted / applied** (ratios, above), read off the component, so a level
  reload (fresh components, fresh HUD) starts again from 1. Its max draw distance moves by
  the same centimetres as the fade's end, not by the ratio: it includes a fixed reach to
  the cell's corner (`grass_cells.cell_max_draw_cm`).
- **`Multiply_IntFloat` truncates.** It is promoted to a wildcard typed by the int, so a
  1.1 ratio became 1 and a 0.9 became 0. Convert the int and multiply floats; the verifier
  checks it.
- **The look rows are variables on `BP_DayNightCycle`** (`SunScale`, `MoonScale`, ...;
  `Scripts/world/CLAUDE.md`), written by `gfx_tuner_sky.py`. A level without a cycle keeps
  its static sky.
- **Wind** (`gfx_tuner_wind.py`; what moves is `Scripts/forest_generator/CLAUDE.md`).
  The grass's and the trees' materials carry it as world-position offset, read from
  `MPC_Wind`'s `Strength` and `Speed`. The wind row walks every instanced-mesh cell
  (`SetEvaluateWorldPositionOffset`), so off takes the offset's cost away too, not only
  the motion; the strength is also zeroed. The wind distance is each cell's
  `SetWorldPositionOffsetDisableDistance`: an instance further off stands still. It is
  plain metres from the camera, and the defaults (50 / 80 / 120 / 200 m) are long
  because a 30 m one left every tree in a rendered shot still. Strength and speed go to
  `MPC_Wind` on every apply. A speed nudge jumps the sway once (time x speed).
  Leaf cut-outs off (`r.Nanite.ProgrammableRaster 0`) stops Nanite evaluating WPO too, so
  it stills the wind as well. Probe: `probe_wind.py` (9 checks).
- **The tab has maximums** (`GfxTuneMaxs`, an `FMin` after the shared `FMax`; the other
  tabs have none). An `FClamp` would be read as a settings slider.
- **`r.ExposureOffset` is a cheat cvar**: it moves in the editor binary (PIE, `-game`),
  not in a shipping build. The save is Python, so the tab is a dev tool anyway.
- **In PIE the cvars stick to the editor viewport.** Restore it by picking High in a game,
  or with `r.ScreenPercentage 100`, `r.ShadowQuality 3`, `r.Fog 1`.
- **Never call `GameUserSettings.ApplySettings`.** It applies resolution too, which hangs the Mac
  editor in PIE at 100% CPU. Use `ApplyNonResolutionSettings()`. The verifier asserts this. A
  `-nullrhi` run cannot catch the hang.
- **The verifier's whole-graph scans see none of this in the HUD:** the HUD graph holds no
  console command, scalability call or tag walk (asserted), which is why the apply is a
  component of its own.
- **Probe:** `probe_graphics_tuning.py` (23 checks: with no save, the CSV's default
  applied at the start, a preset
  switch, cvars, both draw distances in metres, the same metres after a view distance
  nudge, layers, shadows, the sun and the moon scaled, the
  look spread over the presets, SAVE DEFAULT's CSV and default preset, the panel, Custom
  in the save and back after the level reopens while Medium is the built table's again).
  It reopens the level twice (`open_level`, once with no save and once with one), and sets
  aside the CSV and `Saved/SaveGames/OtherworldGraphics.sav` and puts them back.
  `OW_GFX_SHOTS=1` with `--windowed` saves a picture of the panel.
  `probe_menu_cursor_window.py` (windowed) sweeps the cursor onto SAVE DEFAULT, then BACK.
- **Run a tab's probe in a game of its own.** Batched after `probe_umg_screens.py` in one
  `--game` call, the monster and world probes time out: that probe leaves the game on the
  title page.
- **Still needs a play session:** what each number does to the frame rate and
  the picture (a headless run renders nothing), and whether the limits are the useful ones.

## Settings screen

- **The way in:** the menu's `settings` row, on the title or in play (above: "One menu").
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

- **The panel's `save and exit` row** closes it and starts a 15 s countdown (`EXIT_SECONDS`), drawn top
  centre (`profile_draw.py`). When it runs out, the player's stats and inventory go into a fresh
  `/Game/UI/BP_Profile` (a `USaveGame`, slot `OtherworldProfile`) and the current level reopens,
  which opens on the main menu.
- **Stored:** Health, Stamina, Hunger, Thirst, Temperature, the kill count, the equipped slot,
  and each carried item's class, `Loaded`, `Reserve` and `Slot` (`ITEM_FIELDS`: where it
  was carried; a profile saved before slots had no `ItemSlot`, and loads with the first
  item in hand and the rest in the bag). **Never the location**; the verifier
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
- **Still needs a play session:** taking the row by hand and the 15 s at real speed (the probe
  writes the countdown's variables), and how the banner reads.

## The dev-all-guns cheat (`dev_guns.py`, `dev_consts.py`)

A testing aid on the M panel. **Its row** (`dev-all-guns`) raises the HUD's
`DevAllGunsRequested`; the next Tick (run from `save_exit.py`, after the countdown) lowers it and,
for each of the five guns, the knife and the axe in `DEV_GUN_CLASS_PATHS`, spawns one if none is carried and fewer
items than slots are carried (`SLOT_COUNT`: the slot sync puts a gun in the bag, the hand or its weapon slot): `Dropped = false`, `Inventory += it`, then `NeedsRefresh`. The held item
stays held, as with a pick-up; asking twice adds nothing.

- **`profile_checks` tells its `Set Dropped`/`Set NeedsRefresh` apart from the cheat's** (the
  cheat's item comes through a cast; its refresh follows no `Set EquippedIndex`).
- **Probe:** `uepy.py --game --probe Scripts/probes/probe_dev_all_guns.py` writes the request
  flag (no keyboard in a probe). Taking the row by hand needs a play session.

## The loot window (`loot_*.py`, `wbp_loot.py`)

Run from Tick after save and exit; the design is `Scripts/loot/CLAUDE.md`. Traps met here:

- **Every `Clamp` node in this graph is read as a settings slider** by the verifier, so the
  window clamps `LootSel` with `Min` then `Max`.
- **The take reuses the cheat's pattern** (spawn, cast, `Dropped`, `Inventory += it`,
  `NeedsRefresh`). `dev_guns_checks._looting` tells the take's nodes apart from the cheat's.
- **Probe:** `probe_corpse_loot.py` calls `ReceiveDrawHUD` itself to read the window.
- **`WBP_MenuRow` has an `Icon`** after its value, collapsed; only the loot rows show it. It is
  named as the inventory slot's is, so "Get Icon" alone does not say which: tell the loot
  row's brush by its `Texture` coming out of an array.
- **The kneel** (`loot_kneel.py`) runs on every tail of the loot Tick, so a lost body also
  stands the player up. It is the HUD's 17th `GetComponentByClass`.

## The I panel (`wear_*.py`, `wbp_wear.py`)

What the player wears; the design is `Scripts/clothing/CLAUDE.md`. Run from Tick after the
loot window, in play only. Traps met here:

- **The HUD only asks.** Enter or a click raises `WearTakeOffRequested`; Tick lowers it and
  writes `WearSel` into the weapon component's `TakeOffSlot`, which serves it on its own
  Tick. A probe opens the panel and takes off by writing the HUD's three variables.
- **Its own dead gate and its own walk edge** (`WearStill`): `loot_checks` and
  `pause_checks` pick out the loot's and the menu's from theirs.
- **It adds two `GetComponentByClass`** (the take-off's and the rows'): the HUD has 20.
- **The worn rows are always up** (bottom right, in the `Kit` over the bag, at
  `KIT_SCALE`); only the caret, the mouse and the bag wait for `WearOpen`. Shut, the
  cursor is hidden and a click is a shot, so no click is read there.
- **The caret runs on into the bag:** `WearSel` 0-7 are the worn rows, 8-17 the bag's
  slots (`inv_consts.BAG_SEL_FIRST`); Enter on a bag slot sets the weapon component's
  `SlotRequest` instead of `TakeOffSlot`.
- **The drag is DrawHUD's** (`inv_drag.py`): the slot under the cursor is `InvOver` (the
  three grids are three row lists to `author_row_cursor`), a press on a filled slot sets
  `InvDragFrom`, and the release asks the weapon component for the move (`MoveTo`, then
  `MoveFrom`) or, on the same slot, for that slot in hand (`SlotRequest`). The component
  decides what fits. Its press and release are read with `InvOver`/`InvDragFrom`, not a
  geometry test of their own: `cursor_checks._on_slot` allows that.
- **The character's portrait** (`WearPortrait`, `wbp_wear.author_wear_portrait`): a picture
  of the player's body from the front, a canvas child of `Body` left of the Kit (not in
  it: `umg_checks` holds the Kit to its two children). `hud_inventory.py` shows it on the
  bag's own condition (WearOpen and no menu). The picture is a render
  (`Scripts/item_icons/CLAUDE.md`), so it does not change with what is worn or held.
  `probe_inventory_window.py` (windowed) saves the screen with it up.
- **Still needs a play session:** dragging with a real mouse (no probe can aim at a cell),
  how the Kit reads over the watermark and beside the loot window on a 720p screen, and
  the 1-9 keys themselves.
- **The cursor's wish is an OR tree** (MenuOpen, LootOpen, WearOpen); `cursor_checks`
  walks it.

## The GUN SETTINGS tab (`tune_*.py`, `wbp_tune.py`)

A developer tab in the M panel's place: **its row** (`Gun Settings`) opens it (`TuneOpen`). Up/Down pick
the gun row or one of the 21 stat rows (`combat/gun_tuning.TUNE_STATS`); Left/Right change the
gun, or move the stat one step (never under its minimum); **Enter** saves
`Scripts/combat/gun_tuning.csv`.

- **The knife and the axe are subjects too,** after the five guns, with only their throw's
  rows: `throw arc` and `throw damage` (`combat/melee_tuning.py`). A stat that is not the
  shown weapon's own (`gun_tuning.columns_of`: a gun has no throw damage, a melee weapon
  nothing but its throw) shows a dash and a nudge on it does nothing.
  - `TuneLive` is the mask: a bool per cell, as `TuneValues`, baked by `tune_defaults()`.
    It is the tab's `live_var` (`tune_tab.py`; "" on the other three tabs): `tune_draw`
    picks the number or `TUNE_DASH` on it, and `_author_nudge` Branches on it before the
    write, so nothing is touched or marked unsaved.
  - The apply Branches on where the item is in `TuneWeapons` (the guns first): a gun
    takes `GUN_COLUMNS`, a melee weapon `MELEE_COLUMNS`. So `ThrowArcDegrees` has two
    Sets, and a knife is never given a gun's pellets or magazine.
  - The save writes each weapon's own columns and leaves the rest of its row empty.

- **The table lives on the HUD:** `TuneValues` (guns x stats, flattened), `TuneWeapons`,
  `TuneSteps`, `TuneMins`, all baked from `_weapon_specs()` (so from the CSV) at build time.
- **Applied every Tick once touched** (`TuneTouched`): each carried item whose `DisplayName` is
  in `TuneWeapons` gets every variable that is its own (ints rounded). Every Tick rather than per nudge, so a
  gun picked up afterwards gets the tuning too. Guns lying in the world get it when picked up.
- **The save is Python**, through `PythonScriptLibrary.ExecutePythonCommand`
  (`TUNE_SAVE_COMMAND` → `tune_save.save()`), which reads the live HUD's table. Blueprint can't
  write a file. So it works in the editor, PIE and `-game` of the editor binary, not in a
  packaged build: a dev tool. `TuneSaved` shows "saved to ..." until the next change.
- **The keys only raise flags** (`TuneNudge`, `TuneSaveRequested`), which is what lets
  `probe_gun_tuning.py` tune and save. It backs up the CSV and puts it back.
- **Still needs a play session:** the keys themselves, how the 22-row panel reads, and
  how the knife's and the axe's rows of dashes read above their two numbers.
- **The machine is shared with the other tabs:** the keys, nudge and save are
  `tune_tick.author_tab_flow` over a `TuneTab` (`tune_tab.py`); the panel is `tune_draw` and
  `wbp_tune` over the same. Only the apply differs. The verifier tells the two save calls apart
  by their command.

## The MONSTER SETTINGS tab (`monster_tune_*.py`)

**Its M panel row** opens it (`MonTuneOpen`; opening a tab shuts the others). The
creature row, then the 28 stats of `npc/monster_tuning.MONSTER_STATS`: aggro range, aggro cone
(half-angle), hearing, touch range, patrol radius, patrol speed, the patrol re-pick window, run
speed, damage per hit, melee range, time between swings, health; then the wendigo's hunt
(`hunt:` rows: the charge range, the catch-up range, the leg speed, the wait behind a tree, the
time between two turns) and what fire does to it (`fire:` rows: the range and the cone it is
held off in, the ring it circles on and how fast, the time between two turns, how long until it
gives up and how long it runs). Same keys as GUN SETTINGS; **Enter** saves
`Scripts/npc/monster_tuning.csv`.

- **The list scrolls:** 14 rows at a time behind a scroll bar (`MON_VISIBLE_ROWS`,
  `TuneTab.visible_rows`, as GRAPHICS SETTINGS's), so here the wheel moves the caret, not the
  value under it.
- **The `hunt:` and `fire:` rows are on every creature,** since the tab is one table of
  creatures x stats, but only a creature that hunts (`NPC_STALK_ROAR`) or fears fire
  (`NPC_WARD_FEARS`) has graphs that read them: on the zombie they change nothing.

- **Each number is a `Tune*` variable on the creature's AI controller** (`npc/tuned.py`), which
  every NPC graph reads instead of a pin literal. The HUD's table (`MonTuneValues`, creatures x
  stats) is baked from `monster_specs()` (so the CSV) at build time.
- **Applied every Tick once touched** (`MonTuneTouched`): for each creature, `GetAllActorsOfClass`
  of its controller class, a cast, and 28 Sets from the table (the cell index is a literal on
  `Array_Get`, known at build time). A wanderer spawned or respawned later gets it within a Tick.
- **What "immediately" means per stat:** senses, patrol and melee take effect on the
  wanderer's next tree pass (0.5 s). The Chase and Stroll steps rewrite `MaxWalkSpeed` every
  pass, so speeds do too. Health is re-applied when `TuneHealth` differs from the controller's
  `AppliedHealth`: a live wanderer jumps to the new maximum, **full**. The hunt's and the
  fire's numbers are read on the pass that uses them: a leg under way keeps the wait and the
  turn time it threw, and takes a new speed on its next pass.
- **No row has a maximum.** The fire's cone goes through `DegCos`, as the aggro cone does: past
  180° it narrows again. A `min` row nudged over its `max` row still throws between the two.
- **The CSV feeds two builds:** `build_npc_blueprints.py` (the controllers' defaults), then
  `build_graphics_menu.py` (the HUD's table). `verify_npc_blueprints` and `monster_tune_checks`
  compare against the CSV, so a saved tuning passes them once rebuilt. The level verifiers pin
  the melee numbers at generation time: tuning those fails "NPC Melee ... (TuneMelee...)" until
  the level is regenerated.
- **The verifier's whole-graph scans exclude this tab:** the wanderer-bar scan skips
  `ForestWandererAI` classes, and the Binds read-by-index check skips `Get MonTuneValues`.
- **Probe:** `probe_monster_tuning.py` (12 checks: the live write, the floor, the wendigos
  untouched, a speed and a health nudge reaching the pawn, the wrap, the CSV, the panel). It
  backs up the CSV and puts it back. `probe_wendigo_tuning.py` (10 checks) does the same for
  the wendigo's rows: the nudge on every wendigo and no zombie, the floor, a leg run at the
  tuned speed, a charge from the tuned range, the CSV.
- **Still needs a play session:** how the scrolling panel reads, and how a tuned
  wanderer feels.

## The PLAYER SETTINGS tab (`player_tune_*.py`)

**Its menu row** opens it (`PlayerTuneOpen`). One subject row (`player`), then
`combat/player_tuning.PLAYER_STATS`: the jog's speed and the sprint's (m/s, step 0.25), how
long a full stamina bar sprints and how long an empty one refills (seconds, step 0.5). Same
keys as GUN SETTINGS; **Enter** saves `Scripts/combat/player_tuning.csv`.

- **The table is in a person's units, the component in its own.** Once touched
  (`PlayerTuneTouched`), every Tick: the pawn's `BP_WeaponComponent`, a cast, then
  `BaseSpeed` and `SprintSpeed` := m/s x 100, `StaminaDrainPerSecond` and
  `StaminaRegenPerSecond` := the component's `MaxStamina` / seconds
  (`player_tune_tick.APPLIES`; `combat/player_tuning.cms` and `per_second` are the build's
  same sums). Every Tick, so a respawned player takes it too. The rows' minimums (0.5) keep
  the divisions off zero.
- **The jog is `BaseSpeed`.** The sprint writes `MaxWalkSpeed` from it every frame, and the
  aim's slowdown and the low stances scale it, so one write moves all of them. The built
  jog is the character's own `MaxWalkSpeed` (`combat/player_pace.py`), which the
  component's BeginPlay caches.
- **The CSV feeds** `combat/tuning.COMBAT` (so `build_weapons_and_combat.py`: the character's
  walk speed and the component's defaults, then `build_graphics_menu.py`, the HUD's table).
  `verify_weapons_and_combat` (`combat/verify/sprint.py`) checks both against it.
- **The verifier's whole-graph scans exclude this tab:** the Binds read-by-index check skips
  `Get PlayerTuneValues`; the component-lookup count includes its one.
- **Probe:** `probe_player_tuning.py` (8 checks: the built jog, sprint and rates, the refill
  timed on the game's clock, a nudge of each row on the live player, the CSV, the panel). It
  backs up the CSV and puts it back.
- **Still needs a play session:** how a 4 m/s jog and a 6 m/s sprint feel against the
  wanderers (a zombie runs at 6), and how the jog clip reads at the slower speed.

## The WORLD SETTINGS tab (`world_tune_*.py`)

**Its M panel row** opens it (`WorldTuneOpen`). One subject row (`world`), then
`world/world_tuning.WORLD_STATS`: the time of day (hours, step 0.5), the day's length and the
night's (seconds, step 30), and the night's cold (Temperature points a second, step 0.01,
`world/night_cold.py`). Same keys as GUN SETTINGS; **Enter** saves all but the hour to
`Scripts/world/world_tuning.csv` (the hour is never saved: a level starts at a random one).

- **The hour is a 24-hour dial over the cycle's `Clock`:** sunrise 06:00, sunset 18:00, each
  half 12 hours whatever its length (`world_config.clock_to_hour`/`hour_to_clock`, which the
  graph mirrors with two `MapRangeClamped` each way).
- **Only while the tab is open,** each Tick: `GetActorOfClass(BP_DayNightCycle)`, a cast, then
  the lengths and the night's cold onto it (once touched), then `Clock := hour_to_clock(WorldTuneValues[0])` **only
  when that cell differs from `WorldTuneHourSeen`**, then the live clock read back into both.
  Writing the hour every Tick would stop time; the read-back is what makes a nudge step from
  the hour on screen.
- **The CSV feeds** `world_config` (so `build_day_night.py`, the cycle's defaults, then
  `build_graphics_menu.py`, the HUD's table). `verify_day_night` checks the lengths against it.
- **The verifier's whole-graph scans exclude this tab:** the Binds read-by-index check skips
  `Get WorldTuneValues`, and the scalability-level scan skips `MapRangeClamped` (it has a
  `Value` pin).
- **Probe:** `probe_world_tuning.py` (8 checks: the random start, the hour on the dial, a nudge,
  crossing into the other half, a length, the CSV, the panel). It backs up the CSV and puts it
  back.
- **Still needs a play session:** how the sky looks when the hour jumps.

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
- **Top-right:** the kill counter, and the FPS readout: always, debug mode or not
  (`fps.py`; visible in the designer, and no node shows or hides it).
- **Wanderers:** a projected health bar over each one, plus its number in debug mode.
- **Bottom centre:** the held item's name, the hand slot (`HandSlot`), and under it the four
  weapon slots in a row (`WeaponSlots`: primary, secondary, pistol, melee, captioned with
  their keys), 84 x 59 slots with loaded/reserve counts for weapons that use ammo
  (`hud_inventory.py`). Under them, side by side in the `Vitals` row: HP (icon, bar,
  number, `hud_stats.py`) and stamina (icon, bar, `stamina_bar.py`); all in one
  bottom-anchored stack in `WBP_HUD`.
- **Bottom right:** the `Kit`: the worn panel (always), and under it the backpack's ten
  slots in two rows of five, the top row captioned 5-9 (`BagSlots`, shown with I).
- **One loop draws every slot:** code *c* (`combat/slot_tuning.py`) is the hand's cell,
  a weapon cell or a bag cell (`SelectObject` over the three grids' `GetChildAt`, which is
  None past a grid's end), and shows the weapon component's `SlotItems[c]`, read behind
  `IsValidIndex` and then `IsValid`; an empty slot is emptied every frame. Lit: the hand's
  slot, the bag slot under the I panel's caret, and a drag's start.
- **Centre:** the reticle or scope (`reticle.py`). The reticle's four ticks stand off by the held
  gun's accuracy cloud: `ReticleSpread` (weapon component) × half the viewport width, capped at
  `RETICLE_SPREAD_MAX` with an `FMin` (an `FClamp` would be read as a settings slider).
  Down a gun's sights (the weapon component's `SightSeat` past `RETICLE_HIDE_SEAT`) the
  reticle is drawn only in debug mode: the gun's own sights are on the centre there
  (`reticle_checks.py`; a headless run draws nothing, so the look is
  `probe_sight_raise.py --windowed` with `OW_RAISE_SHOTS=1`).
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
- **One build per warm headless editor.** A second `build_graphics_menu.py` in the same
  `UEPY_SERVE` editor kills it without a crash report, while compiling `BP_GraphicsMenuHUD`
  (uepy says "the listener stopped responding"). Stop it first (`touch <dir>/stop`, then
  wait for its pid to exit: a call made while it is still shutting down fails the same
  way), or let the failed call be the stop: the next call boots a new one.
  **The same message at 0.0 s on the first call after a boot can be a build that is
  running.** Before any other call, wait for `[UI] done` in the editor log: the next call
  boots a second editor, which loads the assets before the first has saved them (a verifier
  there checks the old HUD), and both then serve one inbox. `kill -9` both afterwards.
- **Seeing a screen:** a `-nullrhi` probe proves the values, not the look. A `-game` run without
  `-nullrhi` (`-windowed -ResX=1280 -ResY=720`) renders on this Mac, and the console command
  `shot showui` saves the viewport with its widgets to `Saved/Screenshots/MacEditor/`.

### The HUD graph

- **`FKey` pin defaults are the bare key name** (`M`, `One`), not `(KeyName="M")`. Struct text
  compiles and never matches.
- **Nodes are identified by input-pin signature** in the verifier. `get_node_title` is fine for
  variable nodes (`Get DebugMode`) but ambiguous for calls, e.g. `Array_Get` is just `Get`.
