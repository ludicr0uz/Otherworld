# The menu and HUD: the history, feature by feature

What each part of the menu, the settings and the HUD built, measured and proved, moved verbatim out of
`Scripts/graphics_menu/CLAUDE.md` (which keeps the rules, the traps and a pointer to each part here).
A heading here is the heading the text stood under there.

<a id="the-m-panel-as-a-menu"></a>
## The M panel as a menu (`menu_screens.py`, `menu_nav.py`, `menu_still.py`)

- **A row is an action, not a key.** `umg_consts.PAUSE_ROW_ACTIONS` names each row's action in
  row order. Taking row *i* (Enter on the caret's row, or a click) sets `PauseClick = i` in
  DrawHUD; the next Tick, the fragment that owns the action sees
  `menu_nav.pause_row_taken(action)` and serves it; DrawHUD lowers `PauseClick` at the top of
  the next frame. A probe takes a row by writing `PauseClick`.
- **`PauseRow` is the caret.** Up / Down and Enter are polled in DrawHUD (`_author_pause_keys`),
  only while no tab and no settings page is open. Enter, not Space: the panel does not pause, and Space jumps.
- **One menu on screen.** `WBP_PauseMenu.Panel` (the panel's own artwork and rows) is
  collapsed while the settings page is up or any tab's open flag is, and the page or the open tab's panel shows instead; the five
  developer tabs sit where the panel does (`TUNE_POS`), the graphics tab in the corner.
- **BACK is a `WBP_MenuRow` over each tab's list, its top row**, and on the settings page
  too (`SettingsBack`, over `SettingsRows`). **Its number in the caret's order is still the
  last** (`TuneTab.back_row`: one past the list, or two in the graphics tab, whose SAVE
  DEFAULT row, under the list, comes before it; `settings_rows.BACK_ROW`). The caret goes
  round, so the stop after the last is the one over the first: Up from the first row is
  BACK, Down from BACK the first row. That keeps a list's rows numbered from 0, as its
  box's children are, with BACK a widget outside the box. Opening a tab or the page puts
  the caret on row 0, the first row under BACK. A scrolling list stays where it is while
  the caret is on BACK (`tune_draw._author_follow`): the cursor crosses BACK on its way
  down to a row. A click on it, or Enter with the caret on it, lowers
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
  - **The bar is dragged** (`tune_scroll.py`): a left press inside the box that lands on no
    row is on the bar (the ScrollBox draws it beside its rows), and raises `ScrollGrab`.
    While it is up and the button down, `ScrollAt` is how far down the box the cursor is
    (0..1); the list's offset is that as a whole number of rows (`SetScrollOffset`, the
    thumb's centre under the cursor) and the caret is kept inside the window, because the
    follow above would pull the list back to a caret left outside it. Vertical only: once
    held, the cursor's X is not read.
  - The scroll is served from `ScrollGrab`/`ScrollAt`, also on the frame the button comes
    up, which is what lets `probe_menu_scroll.py` drag without a mouse.
  - Its sum is plain arithmetic and Min / Max: `verify_graphics_menu.py` counts every
    FClamp and MapRangeClamped of the HUD as a slider's or the clock's.
  - **A row scrolled out of the window keeps its geometry**, and lies over BACK above and
    the hint below: the row test is ANDed with "the cursor is over the box" (`author_row_cursor`'s
    `within`).
  - `TUNE_ROW_H` (22.5) is a `WBP_MenuRow`'s desired height read off a rendered run
    (`get_desired_size()` works in a windowed `-game`; cached geometry still reads zeros).
- **Probes:** `probe_menu_cursor.py` (a taken row served once, the tab in the panel's place,
  BACK's caret, the walk taken and given back) and the windowed `probe_menu_cursor_window.py`
  (the graphics tab's five rows under the cursor and no more, the list scrolled to its end);
  `probe_menu_scroll.py` (the bar dragged to the bottom, the middle and the top in both
  scrolling tabs, the caret brought along, the list staying put once let go).
- **Still needs a play session:** Enter and the arrows themselves (the caret going round
  at both ends: no probe can press a key, `pause_checks.py` checks the graph), the click on BACK,
  dragging the bar with a real mouse (no probe can press a button), and how the corner
  panel reads.

<a id="the-mouse-cursor"></a>
## The mouse cursor (`cursor.py`, `cursor_consts.py`)

The cursor shows while a menu is up: the menu (on the title and in play, with its settings
page and tuning tabs), the death menu, the loot window and the I panel. Otherwise it is hidden and the
mouse is the camera's.

| menu | cursor over a row | left click |
|---|---|---|
| settings | the caret goes there | a bind row: arms the capture; BACK: back; a slider or the difficulty: one step up |
| M panel | the caret goes there | takes the row (as Enter does) |
| tuning tab | the caret goes there | one step up; on the hint line: save (the graphics tab: on its SAVE DEFAULT row); on BACK: back to the panel; held on a scrolling list's bar: drags the list |
| loot window | the caret goes there | take; on the `[TAB] close` line: shut |
| I panel | the caret goes there (a worn slot) | on a worn slot: take that garment off; on the `[I] inventory` line: shut; on a slot: bring it to hand; a press on one slot and a release on another: move it there (a worn garment off into it, a carried one onto the worn grid worn) |
| death menu | | on the hint line: restart |

**The wheel does nothing in any menu**: no key poll reads it (it turned a value or moved a
caret whenever the mouse was nudged), and the verifier checks nothing polls its keys.

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
- **Shown is Game-and-UI, hidden is Game-only** (`author_cursor_mode`), switched only when
  `CursorWanted != CursorShown`. Without the Game-only call the camera stays dead after a
  menu closes until the next click.
- **On the title the mode is given again every frame** the left button is up (`_on_title`:
  wanted, `GameStarted` false, button up). A launched build's window becomes the active one
  some frames in, and the viewport's launch capture then took the mouse over a mode set once
  before it: the title took no click until a key or a switch of windows. For the same reason
  `bCaptureMouseOnLaunch` is False in `DefaultInput.ini` (the game opens on a menu; Game-only
  takes the mouse when play starts). Not while the button is down: a press holds the capture
  a drag needs.
  - **Do not call `SetFocusToGameViewport` there:** every frame, it left `CursorRow` empty at
    the end of the frame (`probe_menu_cursor_window.py` found no row on the title).
- **The mouse at launch (fixed by config; a real mouse has yet to confirm it).** In the
  published build the user found the mouse "not within the game window" from launch until
  they switched to another app and back. The title's every-frame mode (above) did not cure it.
  - **The cause is UE 5.8's GCMouse path for the look.** In high-precision mode (Game-only,
    cursor hidden) `FMacApplication` takes mouse movement from `FAppleMouseController`'s
    GCMouse handlers and skips AppKit's mouse-moved path. The handlers are bound once, as
    the application is made (before the window is the active one), and bound again only
    when `bMouseInputNeedsReassociation` is set, which only a deactivation of the app does
    (`ReassociateMouseInput`, `SetHighPrecisionMouseMode`). A launch with no deactivation
    before play starts never binds them again: no look until a switch of apps.
  - **The build's log shows it** (path in the root `CLAUDE.md`; `LogViewport` and
    `LogAppleController` are Verbose in `DefaultEngine.ini` `[Core.Log]`). A good start of
    play reads `HighPrecisionMouseMode Enabled`, `[HandleMouseConnected] …` twice,
    `[SetEnabled] Enabling`. The faulty one (13:06 on 4 Oct 2026) read `Enabled` alone, and
    the other lines came 7 s later, after the switch of apps.
  - **The fix:** `Slate.MacUseNewMouseControllerMovement=False` in `DefaultEngine.ini`
    `[ConsoleVariables]`: AppKit handles every mouse movement, as before 5.8, and no
    controller is made. It is read-only and read as the application is made, so it can be
    set nowhere else (not from a Blueprint, not from the console). With it on, a log has no
    `HandleMouseConnected` and no `[SetEnabled]` line at all.
  - **It cannot be reproduced by a session with the screen locked:** no app becomes the
    active one, Slate then skips every capture, and nothing can move or press the mouse. If
    the user still sees it, read the new log for the lines above before anything else.
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
- **Still needs a play session:** the click itself (and, in a packaged build, the first
  click on the title straight after launch, with no key pressed), the loot window's
  close line under a real cursor (no probe can aim at it), the cursor's look, and
  how losing the mouse-look while the M panel or the loot window is open feels.

<a id="presets-and-the-graphics-settings-tab"></a>
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
  `SetWorldPositionOffsetDisableDistance`: an instance further off stands still. Wind is
  off by default on Low, Medium and High and on only on Custom (once Ultra). The distance is
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
  `probe_menu_cursor_window.py` (windowed) sweeps the cursor onto BACK, down the rows, then SAVE DEFAULT.
- **Run a tab's probe in a game of its own.** Batched after `probe_umg_screens.py` in one
  `--game` call, the monster and world probes time out: that probe leaves the game on the
  title page.
- **Still needs a play session:** what each number does to the frame rate and
  the picture (a headless run renders nothing), and whether the limits are the useful ones.

<a id="the-i-panel"></a>
## The I panel (`wear_*.py`, `wbp_wear.py`)

What the player wears; the design is `Scripts/clothing/CLAUDE.md`. Run from Tick after the
loot window, in play only. Traps met here:

- **The HUD only asks.** Enter or a click raises `WearTakeOffRequested`; Tick lowers it and
  calls the weapon component's `AskTakeOff(WearSel, into the bag)` (`ask.py`), which raises
  `TakeOffSlot`; the component serves it on its own Tick. A probe opens the panel and takes off by writing the HUD's three variables.
- **Its own dead gate and its own walk edge** (`WearStill`): `loot_checks` and
  `pause_checks` pick out the loot's and the menu's from theirs.
- **It adds two `GetComponentByClass`** (the take-off's and the rows'): the HUD has 20.
- **The worn slots and the bag are always up** (bottom right, the `Kit`); only the caret,
  the mouse and the portrait wait for `WearOpen`. Shut, the cursor is hidden and a click
  is a shot, so no click is read there.
- **A worn slot is a `WBP_InventorySlot`,** as a bag slot is: `WearSlots`, two rows of
  four, cell *i* showing `Worn[i]`'s own `Icon` and no text. `wear_draw.py` fills it with
  `hud_inventory`'s two fragments (`ammo=False`: the verifier counts one ammunition
  read, the slots'). The caret is the lit slot, not a `>`.
- **An empty slot's silhouette is the slot's own:** `WBP_InventorySlot.GhostTexture`,
  Instance Editable, set per cell in `WBP_HUD` (`wbp_parts.slot_grid(ghosts=…)`) and put
  into the `Ghost` image by the slot's PreConstruct, as a menu row's label is. It is drawn
  at `COL_GHOST`'s alpha. The weapon slots' are drawn glyphs of the kind, not any item's
  icon: a rifle, a rifle, a pistol and a knife (`inv_consts.WEAPON_GHOSTS`,
  `T_UI_Ghost_<Kind>`, drawn by `ui_art/slot_ghosts.py` as the stat icons are; after a
  change run `build_ui_art.py`, `import_ui_art.py`, then the menu build). A worn slot's
  is its garment's icon (`wear_consts.WEAR_GHOSTS`); the hand and the bag have none. The HUD shows it in an
  empty slot only where the texture is valid, and collapses it in a filled one. The
  weapon slots have no captions any more.
- **The caret runs on into the bag:** `WearSel` 0-7 are the worn slots, 8-17 the bag's
  slots (`inv_consts.BAG_SEL_FIRST`); Enter on a bag slot sets the weapon component's
  `SlotRequest` instead of `TakeOffSlot`.
- **The drag is DrawHUD's** (`inv_drag.py`): the slot under the cursor is `InvOver` (the
  four grids, `inv_consts.DRAG_BOXES`, are four row lists to `author_row_cursor`; a worn
  cell *i* is code `WORN_CODE_FIRST + i`, the HUD's own, and moves `WearSel`), a press on
  a filled slot sets `InvDragFrom`, and the release asks the weapon component: slot to
  slot the move (`MoveTo`, then `MoveFrom`); a worn garment onto a slot the take-off into
  it (`TakeOffTo`, then `TakeOffSlot`); a slot's item onto the worn grid the wear
  (`WearRequest`: into the garment's own slot, whichever cell it lands on); on the same
  slot, that slot in hand (`SlotRequest`) or, worn, the take-off Enter asks for
  (`WearTakeOffRequested`); over no slot and outside the inventory (none of
  `inv_consts.INV_AREAS`, the Kit and the hand's and weapons' grids, under the cursor), the
  item set down on the ground (`DropRequest`, the drag's own code: a worn cell's is the
  component's too); between two slots, nothing. The component decides what fits. Its press and release are
  read with `InvOver`/`InvDragFrom`, not a geometry test of their own:
  `cursor_checks._on_slot` allows that. It runs before the worn slots are drawn, so the
  caret and the drag's start are lit the same frame.
- **A drag carries its item's icon on the cursor** (`inv_carry.py`): `DragIcon`, one Image
  on `WBP_HUD`'s root (last, so over everything), its centre on the canvas's corner and its
  render translation the cursor's place in the Body's space (`AbsoluteToLocal` of
  `CursorPos`), its brush the dragged item's `Icon`.
  - **The look is held while a drag is on:** the cursor shows in Game-and-UI, where the
    left button held captures the mouse and the view turned with the drag.
    `SetIgnoreLookInput` counts its calls, so it is made on the drag's edges only
    (`InvLookHeld`), as the walk's is.
  - **`author_carry_end` runs on every path of the panel's draw,** not only the open one:
    a drag is called off (and the look given back) when I shuts the panel, the menu comes
    up or the player dies with the button still down.
  - `probe_inventory_drag.py` checks the drops, the look and the icon headless;
    `probe_inventory_window.py` (windowed) puts the cursor mid-window and saves the screen
    with the icon on it.
- **A click on a worn slot is the release, not the press:** the press starts the drag,
  so a take-off on the press would leave nothing to drag.
- **The character's portrait** (`WearPortrait`, `wbp_wear.author_wear_portrait`): a picture
  of the player's body from the front, a canvas child of `Body` left of the Kit (not in
  it: `umg_checks` holds the Kit to its two children). `hud_inventory.py` shows it on the
  bag's own condition (WearOpen and no menu). The picture is a render
  (`Scripts/item_icons/CLAUDE.md`), so it does not change with what is worn or held.
  `probe_inventory_window.py` (windowed) saves the screen with it up.
- **Still needs a play session:** dragging with a real mouse (no probe can aim at a cell:
  `probe_clothing_drag.py` and `probe_inventory_drag.py` write the component's requests
  and the HUD's `InvDragFrom` instead: whether the view really stays still under a held
  button, and the release outside the inventory), the silhouettes'
  alpha on a bright ground,
  how the Kit reads over the watermark and beside the loot window on a 720p screen, and
  the 1-9 keys themselves.
- **The cursor's wish is an OR tree** (MenuOpen, LootOpen, WearOpen); `cursor_checks`
  walks it.

<a id="the-gun-settings-tab"></a>
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

<a id="the-monster-settings-tab"></a>
## The MONSTER SETTINGS tab (`monster_tune_*.py`)

**Its M panel row** opens it (`MonTuneOpen`; opening a tab shuts the others). The
creature row, then the 29 stats of `npc/monster_tuning.MONSTER_STATS`: aggro range, aggro cone
(half-angle), hearing, touch range, patrol radius, patrol speed, the patrol re-pick window, run
speed, damage per hit, melee range, time between swings, health; then the wendigo's hunt
(`hunt:` rows: the charge range, the catch-up range, how far the player may run before it
charges, the leg speed, the wait behind a tree, the
time between two turns) and what fire does to it (`fire:` rows: the range and the cone it is
held off in, the ring it circles on and how fast, the time between two turns, how long until it
gives up and how long it runs). Same keys as GUN SETTINGS; **Enter** saves
`Scripts/npc/monster_tuning.csv`.

- **The list scrolls:** 14 rows at a time behind a scroll bar (`MON_VISIBLE_ROWS`,
  `TuneTab.visible_rows`, as GRAPHICS SETTINGS's): the list follows the caret, and the mouse drags
  its bar.
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

<a id="the-player-settings-tab"></a>
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

<a id="the-sound-settings-tab"></a>
## The SOUND SETTINGS tab (`sound_tune_*.py`)

**Its menu row** opens it (`SoundTuneOpen`). One subject row (`volume`), then
`Sound/catalog.SOUND_STATS`: one row per sound (25: the footsteps, each gun's shot, the
dry click, the reloads, the melee hit and swing, the chop, the growl, the roar, the player's
hit and death, the match, the campfire, a blade's hit, a thrown blade in a body, a throw and
the three beds, the wind's at 0), behind a scroll bar
(`SOUND_VISIBLE_ROWS`, 14 at a time, as MONSTER SETTINGS), its volume as a multiplier (step
0.05, from 0 to 4, the engine's own ceiling for a source: the tab has maximums, `SoundTuneMaxs`). Same keys as GUN SETTINGS;
**Enter** saves `Scripts/Sound/sound_tuning.csv` (then `build_sound.py` bakes it into the HUD).

- **The apply is the game's sound mix** (`sound_tune_tick._author_apply`; what a class and
  the mix are: `Scripts/Sound/CLAUDE.md`): `SetBaseSoundMix(A_Mix_Game)`, then one
  `SetSoundMixClassOverride` per row, its class and the mix as pin literals, its volume
  the row's cell, no fade.
- **It runs on the HUD's first Tick, tab or no tab** (`SoundTuneApplied` false), which is
  what gives a game its volumes at all: no asset holds one. Then only after a nudge:
  `SoundTuneTouched` is **lowered again** once the mix is told, unlike the gun, monster and
  player tabs', because the mix is the audio device's and outlives a respawn. Each level's
  HUD tells it again.
- **The CSV feeds** `build_graphics_menu.py` alone (the HUD's table). A nudge is in the next
  game without it (the tab's save slot, `tune_keep.py`); a hand-edited CSV needs the build.
- **The verifier's whole-graph scans exclude this tab:** the Binds read-by-index check skips
  `Get SoundTuneValues`.
- **Probe:** `probe_sound_tuning.py` (6 checks: the first Tick's apply, each class's volume
  as the audio device reports it, two nudges reaching the device, the stop at 0, the CSV,
  the panel). It backs up the CSV and puts it back.
- **Still needs a play session:** how loud the footsteps are at 0.4 against the guns and
  the growls, and how the 14-row panel reads.

<a id="the-world-settings-tab"></a>
## The WORLD SETTINGS tab (`world_tune_*.py`)

**Its M panel row** opens it (`WorldTuneOpen`). One subject row (`world`), then
`world/world_tuning.WORLD_STATS`: the time of day (hours, step 0.5), the day's length and the
night's (seconds, step 30), the night's cold (Temperature points a second, step 0.01,
`world/night_cold.py`), and the item highlight (1 on, 0 off: whether an item on the ground
glimmers, `world/item_highlight.py`). Same keys as GUN SETTINGS; **Enter** saves all but the hour to
`Scripts/world/world_tuning.csv` (the hour is never saved: a level starts at a random one).

- **The hour is a 24-hour dial over the cycle's `Clock`:** sunrise 06:00, sunset 18:00, each
  half 12 hours whatever its length (`world_config.clock_to_hour`/`hour_to_clock`, which the
  graph mirrors with two `MapRangeClamped` each way).
- **Only while the tab is open,** each Tick: `GetActorOfClass(BP_DayNightCycle)`, a cast, then
  the lengths, the night's cold and the item highlight onto it (once touched), then `Clock := hour_to_clock(WorldTuneValues[0])` **only
  when that cell differs from `WorldTuneHourSeen`**, then the live clock read back into both.
  Writing the hour every Tick would stop time; the read-back is what makes a nudge step from
  the hour on screen.
- **An on/off row is a number held between 0 and 1.** The tab's cells are floats, so the item
  highlight steps by 1 from a minimum of 0 to a maximum of 1: the tab has maximums
  (`WorldTuneMaxs`, `world_tuning.WORLD_MAXS`; every other row's is `NO_MAX`), as the graphics
  tab does. A new switch is a row with its maximum at 1.
- **The CSV feeds** `world_config` (so `build_day_night.py`, the cycle's defaults, then
  `build_graphics_menu.py`, the HUD's table). `verify_day_night` checks the lengths against it.
- **The verifier's whole-graph scans exclude this tab:** the Binds read-by-index check skips
  `Get WorldTuneValues`, and the scalability-level scan skips `MapRangeClamped` (it has a
  `Value` pin).
- **Probe:** `probe_world_tuning.py` (8 checks: the random start, the hour on the dial, a nudge,
  crossing into the other half, a length, the CSV, the panel). It backs up the CSV and puts it
  back. `probe_item_glimmer.py` steps the item highlight's row off and back on, past
  both ends, and saves it.
- **Still needs a play session:** how the sky looks when the hour jumps.

<a id="hud"></a>
## HUD

**What it shows each frame:**

- **Bottom-left:** the hunger, thirst and temperature bars, vertical and filling from the bottom
  (`survival_bars.py`), each over its icon (no caption: the icon names it); STARVING and DEHYDRATED stack above
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
  weapon slots in a row (`WeaponSlots`: primary, secondary, pistol, melee; no captions:
  an empty one shows its kind's translucent silhouette), 84 x 59 slots with loaded/reserve counts for weapons that use ammo
  (`hud_inventory.py`). Under them, side by side in the `Vitals` row: HP (icon, bar,
  number, `hud_stats.py`) and stamina (icon, bar, `stamina_bar.py`); all in one
  bottom-anchored stack in `WBP_HUD`.
- **Bottom right:** the `Kit`, always shown: the worn slots (`WearSlots`, two rows of four,
  a garment's icon or its silhouette), and under them the backpack's ten slots in two rows
  of five, the top row captioned 5-9 (`BagSlots`).
- **One loop draws every slot:** code *c* (`combat/slot_tuning.py`) is the hand's cell,
  a weapon cell or a bag cell (`SelectObject` over the three grids' `GetChildAt`, which is
  None past a grid's end), and shows the weapon component's `SlotItems[c]`, read behind
  `IsValidIndex` and then `IsValid`; an empty slot is emptied every frame, down to its
  silhouette if it has one. Lit: the hand's
  slot, the bag slot under the I panel's caret, and a drag's start.
- **Centre:** the reticle or scope (`reticle.py`). The reticle's four ticks stand off by the held
  gun's accuracy cloud: `ReticleSpread` (weapon component) × half the viewport width, capped at
  `RETICLE_SPREAD_MAX` with an `FMin` (an `FClamp` would be read as a settings slider).
  Down a gun's sights (the weapon component's `SightSeat` past `RETICLE_HIDE_SEAT`) the
  reticle is drawn only in debug mode: the gun's own sights are on the centre there
  (`reticle_checks.py`; a headless run draws nothing, so the look is
  `probe_sight_raise.py --windowed` with `OW_RAISE_SHOTS=1`).
  The reticle is **always white**: one literal colour, nothing picked off the aim (it used to
  turn red on the weapon component's `AimBlocked`). A headshot is said by a shape instead:
  `hit_marker.py` draws an X (four `AHUD::DrawLine` strokes on the diagonals, the reticle's
  white) for `HEADSHOT_MARK_SECONDS` after the weapon component's `HeadshotTime`. It hangs off
  every arm of the reticle that has the component (crosshair, crosshair left out down the
  sights, scope, empty hands after a thrown knife), so it is drawn whatever is on the centre.
- **When the player is dead:** only the death menu. `DrawHUD` branches on `PlayerDead` of the owning
  controller's PlayerState (`net/state_graph.py`); with no PlayerState yet (a client's first
  frames) the player counts as alive.
  It shows two scores off that PlayerState, each on a line of its own: `Monster Kills`
  (`NpcKillCount`) and `Player Kills` (`PlayerKillCount`, M15: `combat/player_kill.py`).

**Rules:**

- **Anchor widgets; lay out the canvas layers from the viewport size.** Read slot colour, name
  and ammo from each item's own `SlotColor`/`DisplayName`/`UsesAmmo`/`Loaded`/`Reserve`. The HUD
  keeps no list of weapons.
- **A wanderer's bar shows only for 5 s after it is hurt** (`LastDamageTime`, default −1000). It
  is gated on `NOT Dead`.
- **`NpcKillCount` lives on the player's PlayerState** (replicated: a client's HUD reads its
  own; `probe_net_player_state.py`) and only counts kills with `DamagedByPlayer` set.
- **The FPS readout counts real time over a 0.5 s window.** Never drive a HUD element with a
  `stat` command: `stat fps` is a toggle, and in PIE its state outlives the session. The verifier
  rejects it.
- **The death menu and the restart key are handled in `DrawHUD`,** because Tick is paused.
  The restart is standalone's: as a client of a server the hint reads `DEATH_HINT_SERVER`
  and neither the key nor a click does anything, until the server's respawn lowers
  `PlayerDead` and the HUD's body is back (`death_checks.py`, `probes/probe_net_death.py`).
- **A cast-failed path still reaches the rest of the HUD with a real value** (e.g. `DebugOn`
  false). Never read off an invalid object there.
