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

Graphs are authored with `Scripts/uebp` (root `CLAUDE.md`): no coordinates, node paths from
`uebp.nodes`, the HUD's own variables by their row in `hud_vars.py` (`MV.MenuOpen`).

This package holds the fragments. The entry point itself is still 1.2k lines, over budget, so
split it before extending it.

**There is one menu** (`WBP_PauseMenu`, titled **OTHERWORLD**, off the top left at
`PAUSE_POS`). The game opens on it, paused, and **M** brings the same one up in play, where
it pauses nothing. The code and the notes below still call it "the M panel".

**The keys:**
- **M** toggles the menu in play: the only key it has. On the title it cannot be shut.
- **Up / Down go round**, in the menu, the settings page and every tab: Down on the bottom
  row is the top row, Up on the top row the bottom one (`menu_nav._emit_row_nav`,
  `tune_tick._author_keys`: `(row + step) mod rows`, Up's step the row count less one). The
  loot window and the I panel still stop at their ends.
- **Up / Down** move the menu's caret and **Enter** takes the row it is on; a click on a
  row takes it too. **No row has a hotkey** (the 1-4, D, X, K, T, N, O and P keys are gone).
- **Escape is BACK**, in every menu that has somewhere to go back to (below: "Escape").
- **The rows:** `Single Player` (on the title it opens the Single Player page, whose one
  row is `New Game`, or `Continue Game` with a saved profile; in single player it reads
  `Resume` and shuts the menu; as a client in play the row is not there: collapsed, and the
  caret goes round it, `mode_draw.author_mode_words`), `Multiplayer` (on the title it opens the Multiplayer page: the server's
  address and `Join Server`; in play it does nothing and says `from the title`), `Controls` (the settings page, titled
  **CONTROLS**; the code still calls it the settings page), `Debug Settings` (the DEBUG SETTINGS tab, below;
  not the FPS readout, which is always on), `Dev All Guns` (in play only: on the title the row is collapsed and the caret goes past it, `mode_draw.author_mode_words`), `Gun Settings`,
  `Monster Settings`, `World Settings`, `Player Settings`, `Sound Settings`, `Graphics Settings`, and last
  the one way out (`EXIT_ACTION`): on the title it reads `Exit Game` and quits to the desktop,
  saving nothing; in play it reads `Save and Exit`, in single player and as a client of a
  server alike, and starts the 15 s countdown (below: "Save and exit"). The quality presets are not
  rows: Low / Medium / High / Custom is the graphics tab's first row.
- **The settings page or a tuning tab stands in place of the menu's rows**, and its **BACK**
  row, its top row, returns to them (below: "The M panel as a menu").
- **Tab** (near any body) kneels and opens the loot window; **Up/Down** and **Enter** in it
  (`loot_tick.py`; the rules are `Scripts/loot/CLAUDE.md`).
- **I** opens the inventory (the I panel): the worn garments and the backpack, bottom
  right, are always shown, and I puts the caret and the mouse on them and the character's
  portrait left of them (`wear_*.py`, `inv_*.py`, `Scripts/clothing/CLAUDE.md`). **Up/Down** run the
  caret over the worn slots, then the bag's slots; **Enter** takes a garment off, or brings
  a bag slot's item to hand; the mouse drags an item from slot to slot, a worn garment
  onto the hand or a bag slot, or a carried one onto the worn grid (below). A right
  click on a slot uses its item, and on the hand's slot (or with the use key) what is in
  hand is eaten, drunk, struck or worn. The portrait is the player in what is worn. It does not
  pause, holds the walk while open, and hides under the menu; with the loot window open
  too, the arrows and Enter are the loot window's. **1-9** are the weapon component's
  (`combat/slot_tuning.py`).
- **The mouse** works every menu too (below).

What each feature built, measured and proved is in `docs/history/menu.md`, moved there word
for word. A bullet here that is only its bold line and a link, or a heading with only a
link under it, names its part there.

## One menu: the title's and M's (`menu_main.py`, `menu_screens.author_title`)

- **The title is the menu held open, on the title level.** `Lvl_Title` (`Scripts/title`,
  `build_title_level.py`; `DefaultEngine.ini`'s `GameDefaultMap`) is a stage of its own,
  a piece of the forest at night with the play level not loaded: a flat floor in the
  forest's ground, the 215 trees the 1 km level has within 60 m of its middle
  (`title/forest.py`), the forest's static night (moon, starfield, sky light, fog, the
  night's exposure range; no day/night clock), a PlayerStart and a
  CameraActor player 0 takes as the level comes up. The GameMode spawns the player's
  character there as anywhere, and that is the figure on the title. While `GameStarted`
  is false DrawHUD hides the HUD's `Body` and the death menu, sets `MenuOpen` and goes
  on to the same fragment that draws the menu in play (`author_pause_menu`). There is no
  title page: `WBP_MainMenu` holds only the settings page and the legal notice, and goes
  up and down with the menu.
- **Only the title level shows the title.** BeginPlay tests `GetCurrentLevelName` against
  `title/paths.TITLE_LEVEL_NAME` beside the `-nomenu` switch (`title_checks.py`): on any
  other level, or with the switch, `GameStarted` is set at once, so the forest always
  comes up in play. Nothing is paused on the title: the stage has nothing to pause, and
  the character idles live (a paused world would freeze it in whatever pose its first
  frames reached). The HUD neither pauses nor ticks while paused any more; the one
  `SetGamePaused` left in its graph is the death menu's unpause before it opens the title level.
- **The figure is dressed from the profile** (`title_figure.py`, Tick's title arm, once:
  `TitleDressed`): when the pawn's parts cast and the weapon component has issued the
  loadout, `DoesSaveGameExist` on the profile's slot, `LoadGameFromSlot`, and each saved
  `WornClasses` entry worn again through `ViewWorn` (`profile_read._author_rewear`, the
  same loop the load in play runs), which draws the hoodie, the jeans and the shoes on
  the MetaHuman. No profile: a fresh character, in the pants it starts in (the weapon
  component's own BeginPlay wears them: `Scripts/clothing/CLAUDE.md`, "The starting
  pants"). Either way, the issued
  gun is then stowed, once (`TitleStowed`), when something is held (`AskMove` from the
  hand to the primary slot, the HUD's second `AskMove`; the gun reaches the hand a frame
  or more after the loadout is issued, and a move asked sooner finds the hand empty):
  the figure holds nothing. Nothing else of the profile is read on the
  title. `probe_title_figure.py` (`uepy.py --game --title`) is the whole path: in the
  starting pants and empty-handed, then dressed from a written profile, then New Game.
- **The first row** (`START_ACTION`) lowers `MenuOpen` in play (`resume`); on the title it
  opens the Single Player page (below: "The two modes"), whose two rows call
  `OpenLevel` and nothing else (`menu_main._author_new_game`): Survival
  `title/paths.PLAY_LEVEL`, the 1 km forest, and Horde Mode `HORDE_LEVEL`,
  `Lvl_Horde_Survival` (both in `DefaultGame.ini`'s `MapsToCook`, since the cooker
  cannot follow a name). The title stands, its page up, until the level
  replaces it, and the new level's HUD opens in play and loads the profile if there is
  one (`save_exit._author_load_once`): one profile for both modes, since it holds the
  character and no place. DrawHUD writes the Survival row's label every frame:
  `Survival`, or `Continue Survival` while the saved profile exists
  (`mode_draw._author_single`: `DoesSaveGameExist` on the profile's slot, asked every
  frame, because save and exit writes it and a death deletes it under a live HUD).
- **`settings`** sets `MenuPage` to the settings page and `MenuRow` to 0. The page
  (`WBP_MainMenu.SettingsPanel`, at `PAUSE_POS` like the menu) shows while `MenuPage` says
  so and the menu's `Panel` is collapsed; its BACK row sets `MenuPage` back. In play the
  page does not pause either, and its accept keys include Space, which also jumps.
- **`exit game`** is the last row on the title: `QuitGame` for the owning player, the one
  such node in the graph, behind the row's Branch and then the title's arm of one on
  `GameStarted` (`menu_main._author_quit`). In play the same row is save and exit and
  quits nothing; DrawHUD writes its label every frame off `GameStarted`
  (`mode_draw.author_mode_words`).
- **What needs a game in play is kept off the title:** Tick splits on `GameStarted`
  (`author_in_play`), and save and exit (with the profile load, the death wipe and the
  cheat) and the loot window run only in play. On the title the cheat's value column reads
  `in game only` (`IN_GAME_ACTIONS`). The tuning tabs and debug work on the title.
- **M is polled only in play** (a Branch on `GameStarted`, then the key): the title's menu
  has nothing under it to go back to.
- **The pause is single player's, and death's alone now.** The death pause is
  `net.pause.author_pause` (`combat/death.py`): a Branch on IsStandalone in front of its
  `SetGamePaused(true)`. As a client of a server there is no title at all (below). The
  HUD ticks either way, `menu_still.py` holds the walk and `author_hold_fire` the fire
  press while the menu is open, and the death menu's unpause (`author_unpause`) is a plain
  call, a no-op where nothing paused. `probe_net_menu_overlay.py` (`uepy.py --net`) is
  the client's half, with `--windowed` for the fire press, which DrawHUD holds.
- **Probes:** `probe_main_menu.py` holds a title up by hand on its level under `-nomenu`,
  pauses the game itself and shows both halves: with the HUD not ticking a taken row is
  not served, ticking it is; the mode rows open their pages; in play the first row only
  shuts the menu. It never takes the Single Player page's row (that opens the forest)
  nor the last row on the title: that is exit game, and would end the run (the verifier
  holds the quit to the title). `probe_umg_screens.py` reads what the title shows.
- **A probe's game sees the real title only when asked:** `uepy.py --game` passes
  `-nomenu`; `--title` leaves it off, on the title level (`LEVEL = "/Game/Maps/Lvl_Title"`
  in the probe; `docs/headless_runs.md#title`). `probe_title_single.py` is the real
  BeginPlay path: the menu up, Single Player and Survival served, the forest up and
  playing; `probe_title_horde.py` the same through Horde Mode to the horde level; `probe_title_figure.py` the figure and its gear.
- **Still needs a play session:** the keys themselves on the title, exit game from a real
  session, and how the title reads with the figure behind it.

## The two modes (`mode_consts.py`, `mode_draw.py`, `mode_tick.py`, `wbp_modes.py`)

The title's first two rows are the modes, each a page in the rows' place. The strategy is
`serversupportsysdesign.md` 4.8; the session's side is `Scripts/net/CLAUDE.md`.

- **A page is a value of `MenuPage`**, like the settings page (`PAGE_SINGLE`, `PAGE_MULTI`):
  a panel of `WBP_PauseMenu` at `PAUSE_POS`, `MenuRow` its caret, BACK its top row and its
  last number. `mode_consts.Page` describes one; a third page is a row of `PAGES` and its
  fragment.
- **A page's row is taken through `PageClick`**, as the menu's own are through
  `PauseClick`: DrawHUD raises it (Enter on the caret's row, or a click), Tick serves
  `mode_tick.page_row_taken(page, row)`, DrawHUD lowers it at the top of the next frame. A
  probe takes a row by writing it (`probes/title.py`).
- **BACK and Escape** are `cursor.author_back_row` with `closed=PAGE_TITLE`: one gate.
- **Single Player** holds the two single-player modes, Survival (row 0, the old start) and
  Horde Mode (row 1). Neither is reachable as a client: the page is the title's, and a
  server serves the 1 km forest.
- **Multiplayer:**
  - **The address is `BP_Settings.ServerAddress`** (default `127.0.0.1:7777`): the local
    settings, never the profile. It is saved when a join is asked for.
  - **It is typed on its row**: while the caret is there, DrawHUD walks `AddressKeys` (a
    ForEachLoop, as the rebind capture walks `KeyPool`) and appends `AddressChars[i]` for
    each key that went down; Backspace takes one off. Letters, digits, `.`, `-`, and `:` on
    the semicolon's key. No widget is focusable here, so there is no text box.
  - **Join Server** notes the session on the GameInstance (`JoinAddress`, `Connecting`,
    no `NetReason`) and calls `OpenLevel(address)`. The title stands, its status line
    reading `connecting to <address> ...`, until the server's level replaces it.
  - **Leaving the page while it connects** gives the join up (the engine's `cancel`).
  - **The status line otherwise shows `NetReason`**: why the last join failed or the last
    session dropped (`net/game_instance.py` writes it from the engine's two failure
    events). A failure reloads the title's level; that HUD's BeginPlay finds the session
    ended and opens on this page, the caret on Join Server.
- **A client has no title.** BeginPlay asks IsStandalone before anything of the title: off
  its false arm `GameStarted` is set, as `-nomenu` sets it. So a client is never paused or
  blocked by a title, whether it joined from this page or with an address on the command
  line.
- **In play the menu says the mode** (`PauseMode`, under the title: `SINGLE PLAYER` or
  `MULTIPLAYER`). As a client its last row is `Save and Exit` too: the same row asks the
  same countdown of the client's own weapon component (`save_exit.author_exit_row`, called
  from `mode_tick.author_mode_in_play`), and once the component says `ExitDue` the HUD
  (once: `ExitLeaving`) clears the session and the engine's `disconnect` returns the
  process to the title. Nothing is saved there yet (the server's save is M35), and the
  countdown is the client's copy's: the server does not know of it, so it holds an honest
  client still and no more. **The profile's whole
  fragment (`save_exit.py`: the load, save and exit, the wipe on death, and the cheat
  chained after it) runs in standalone only** (`mode_tick.author_mode_in_play`), so a
  server's character never reads the single-player profile and leaving never writes it.
- **IsStandalone is false on the title while a join is pending.** Nothing on the title
  but the pause asks it (the last row's label is off `GameStarted`).
- **Probes:** `probe_title_single.py`, `probe_title_horde.py` and `probe_join_dead_address.py`
  (`uepy.py --game --title`: the real title, no `-nomenu`), `probe_net_title.py`
  (`--net --title --windowed --clients 1`), and `probe_main_menu.py` and
  `probe_umg_screens.py` for the pages under a title held up by hand.
- **Still needs a play session:** typing an address with real keys (no probe can press
  one), the click on each page's rows and BACK, and how the pages read.

## Escape (`cursor_consts.ESCAPE_KEY`, `menu_nav.escape_pressed`)

Escape goes back one step, from any row:

| what is up | Escape | where |
|---|---|---|
| a tuning tab | shuts the tab, back to the menu's rows | DrawHUD (`cursor.author_back_row`, ORed with BACK's click and Enter) |
| the controls page, a capture armed | calls the capture off, binding nothing | DrawHUD (`settings_input._author_capture`, before the key pool's loop) |
| the controls page | back to the menu's rows (the same `Set MenuPage` as its BACK row) | DrawHUD (`settings_input`) |
| a mode page (Single Player, Multiplayer) | back to the menu's rows; a join under way is given up | DrawHUD (`cursor.author_back_row`), then Tick (`mode_tick._author_give_up`) |
| the menu's own rows, in play | shuts the menu, as M and `Resume` do | Tick (`menu_main._author_escape`) |
| the menu's own rows, on the title | nothing: there is nothing under it | |

- **One press, one step.** Escape is "just pressed" for the whole frame, and Tick runs before
  DrawHUD: Tick's shut tests what is up *now* (`MenuOpen`, `MenuPage` on the rows, no tab's
  flag), so the press that DrawHUD will spend on a tab or the page does not also take the
  menu down.
- **Not rebindable:** it is not in `KEY_POOL`, like the arrows.
- The loot window and the I panel keep their own keys (Tab, I) and close lines; Escape does
  nothing to them. The death menu has nothing to go back to.
- **In the editor's PIE, Escape ends the session** (the editor's own shortcut) before the
  game sees it. A `-game` run or a packaged build has no such binding.
- **No probe:** nothing can press a key in a probe's game. `escape_checks.py` checks the
  graph (each poll, what it gates, and the menu shut's test of what is up).
- **Still needs a play session:** every row of the table above.

## The M panel as a menu (`menu_screens.py`, `menu_nav.py`, `menu_still.py`)

Moved word for word: `docs/history/menu.md#the-m-panel-as-a-menu`.

## The mouse cursor (`cursor.py`, `cursor_consts.py`)

Moved word for word: `docs/history/menu.md#the-mouse-cursor`.

## Full screen on the Mac (`Config/Mac/MacGameUserSettings.ini`, `Source/Otherworld/Private/OtherworldMacFullScreen.cpp`)

- **The game runs borderless (`WindowedFullscreen`) and captures its display while it is
  in front.** Borderless on the Mac is a macOS full-screen Space, where the Dock and the
  menu bar are only auto-hidden and the hot corners stay live: a shown cursor reaches the
  screen's edge and brings them up. The game module captures the display the full-screen
  window is on (`CGDisplayCapture`) and puts the window above the capture's shield
  (`OtherworldMacFullScreen`, game only, not the editor): the engine's exclusive mode,
  less the change of display mode, so the size stays native. The capture is given back
  when another app comes forward or the window leaves full screen. What was tried
  before it: `docs/history/menu.md`, "What keeps macOS out is a captured display".
- **Two things the capture needs beside it** (same file). Command-Tab: a captured display
  takes it away, so the capture is not held while Command is down, and comes back when
  the key goes up with the game still in front. The window's own title bar: in a Space
  AppKit keeps it in a separate window above the screen (`NSToolbarFullScreenWindow`)
  and slides it down when the pointer is at the top; that window is emptied and takes no
  clicks. The engine cannot make the Mac's game window borderless
  (`PLATFORM_SUPPORTS_BORDERLESS_WINDOW` is 0, so `bUseBorderlessWindow` does nothing).
- **A captured display shows nothing but the game:** a game hung under a debugger or on
  an assert holds the screen until its process dies (kill it from another display or
  over ssh).
- **Exclusive `Fullscreen` cannot take every size (UE 5.8.3, measured 12 Oct 2026).** In that
  mode the engine accepts a size only from its own list of display modes, and that list
  keeps one height per width, the shortest (`FMetalDynamicRHI::RHIGetAvailableResolutions`,
  a filter for notched MacBooks). A size not in it becomes the list's first entry
  (`EnsureValidFullscreenResolution`, `SceneViewport.cpp`). On a 2560x1440 monitor that also
  offers 2560x1080:

  | asked | in the list | got |
  |---|---|---|
  | 1920x1080 | yes | 1920x1080 |
  | 2560x1080 | yes | 2560x1080 |
  | 2560x1440 (native) | no | 800x600 |

  Config, the console and a menu row all pass that check: none can reach a size it drops.
  Any monitor with two modes of one width whose native is the taller is affected (1440p
  beside 2560x1080, 1920x1200 beside 1920x1080, a notched panel's full height).
- **So a window-mode or resolution row may offer exclusive sizes only from
  `GetSupportedFullscreenResolutions`** (the same list), never "native", and borderless
  stays the default. Borderless and windowed are not checked: borderless is always the
  desktop's size. The rendered size is separate (the resolution-scale row).
- **A row that changes the window must not run in the editor:** `ApplySettings` and
  `ApplyResolutionSettings` drive `SWindow::SetWindowMode`, which hangs Mac PIE (below:
  "Presets").
- **Tried with a real mouse (12 Oct 2026, 2560x1440 monitor with the laptop beside it):**
  nothing comes up at the left edge, the top or the bottom-right corner, and Command-Tab
  goes away and back. Not tried: the laptop's screen alone. The log line `display N
  captured` says the capture was taken, `display N released` that it was given back. The
  order of what was tried: `docs/history/menu.md`, "What keeps macOS out".

## The UMG screens

- **The HUD is the controller, the widgets are views.** `BP_GraphicsMenuHUD` reads the game and
  polls every key; the widgets hold no logic beyond `WBP_MenuRow`'s PreConstruct. BeginPlay
  creates all four screens and adds them to the viewport (`ui_graph.py`); every `DrawHUD`
  shows the one the frame is on and writes the live values (`SetText`, `SetPercent`,
  `SetVisibility`).
- **Which screen:** `GameStarted` false → the menu alone, held open (`Body` hidden);
  `PlayerDead` → `WBP_DeathMenu` (in standalone `[R]` or a click opens the title level,
  `TITLE_LEVEL`, onto the main menu, as save and exit does: no retry, New Game starts again);
  otherwise `WBP_HUD`'s `Body`. In either of the first and
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

Moved word for word: `docs/history/menu.md#presets-and-the-graphics-settings-tab`.

- **Engine quality is one row per group** (`gfx_stats.GROUP_STATS`, ten of them, each 0-3),
  applied by that group's setter on GameUserSettings and `ApplyNonResolutionSettings`,
  only when it moved (`gfx_tuner._author_groups`). A cvar row wins over its group because
  a console command outranks scalability; **never console-set an `sg.*` variable**, which
  would take the group out of the setter's reach. Never `ApplySettings`.
- **What the three shipped presets are today** (`graphics_tuning.csv`; the table in the
  history file is what they began as):
  - **Low:** every group 0, the shadow maps level 0's.
  - **Medium (G2):** every group **2** (it was 1), the three shadow rows level 2's
    (`SHADOW_BY_LEVEL`: 2048, 1024, 4 cascades), resolution 85%, view distance 70%,
    **grass drawn to 300 m and trees to 400 m** (180 and 180 before), four grass layers,
    no grass shadows. `gfx_stats._LEVELS` is `(0, 2, 3, 3)`, the fallback for a missing
    CSV, held to the CSV by `dev/tests/test_gfx_stats.py`.
  - **High:** every group 3. Custom starts as High with the grass lit, and is the
    player's: a change to a shipped row never rewrites a saved Custom row.
- **The grass density row goes to 8 (F1), and no preset draws past 4.** It is the count of
  `grass_cells.GRASS_TIERS`; layers 5-8 are near-only tiers (fading out by 12-22 m at High's
  distances) that only the slider unhides, so the shipped rows and their cost are as they
  were. Only the 200 m map plants them: on the 1 km map (four tiers, `grass_look.
  HELD_TIER_COUNT`) layers 5-8 draw what 4 does.
- **Medium is no longer the cheap preset: level 2 doubles its frame.** Measured windowed on
  the 16 GB Mac, noon, the perf audit's forest spot, by `probes/probe_medium_reach.py`
  (it nudges the live rows from the old ones to the new and measures each; `--map` for
  the 1 km level):

  | Medium's rows | 200 m map | 1 km map |
  |---|---|---|
  | groups 1, 180 m / 180 m (before G2), grass at 1.1/m² | 13.8 ms | 21.9 ms |
  | the same rows, the 200 m map's grass at 2.2/m² | 16.4 ms | 22.1 ms |
  | groups 2 and their shadow maps | 31.7 ms | 36.2 ms |
  | and grass 300 m, trees 400 m (Medium today) | 32.4 ms | 38.1 ms |

  So the level is +14 to +15 ms on either map, the distances under 1 ms on the 200 m map
  (it is 283 m corner to corner) and +1.9 ms on the 1 km map, the doubled grass +2.6 ms.
  **Medium is over 33 ms on the 1 km map** (38 ms, 26 fps) and just under it on the 200 m
  one; High there is 46.8 ms. G2 reports it and does not tune it back.
- **A draw distance row is metres on the ground, and nothing cuts shorter.** The tuner
  divides the view distance out (`gfx_tuner_foliage.py`), so at Medium the grass's base
  layer fades out at 300.0 m and the trees at 400.1 m with the cells' own max draw
  distance 130 m and 160 m further (432.5 m and 558.8 m after `r.ViewDistanceScale`
  0.7). `probe_medium_reach.py` checks those numbers, then pictures two cells from 255 m
  (350 m for trees) shown and hidden with everything else that grows hidden and the fog
  off: grass at 265–300 m and trees at 360–400 m are drawn on both maps, and nothing of
  either from past its cell's distance. The fade is a thinning: at 265–300 m a tenth of
  the clumps are left. A HISM also culls by cluster, so some trees are still drawn 20 m
  past the row.
- **A new row moves `STAT_COUNT`, and a save of another length is another build's.** Add
  the old layout to the load (`gfx_save.author_legacy_row`, `gfx_stats.LEGACY_COLUMNS`) or
  every player's Custom row is dropped. Probe: `probe_gfx_groups.py` (`--windowed`).

## Settings screen

- **The way in:** the menu's `settings` row, on the title or in play (above: "One menu").
- **The settings page:**
  - BACK, the top row (a row of its own, `SettingsBack`; `MenuRow`'s number for it is the
    last, `BACK_ROW`: above, "The M panel as a menu");
  - mouse sensitivity (Left/Right, clamped to a minimum above zero);
  - DIFFICULTY: EASY / MEDIUM / SURVIVOR (Left/Right cycle it; default EASY). Saved as the int
    `BP_Settings.Difficulty` and copied onto the GameState's `Difficulty` every `DrawHUD`
    (`difficulty.py`), where this machine owns the GameState: a client plays at the server's. Only EASY does anything yet (the mushroom heal). `-nullrhi` runs no
    `DrawHUD`, so a headless game keeps the GameState's own default, EASY;
  - the keybinds, one row per `BIND_VARS` entry (Enter arms a capture; the next key from `KEY_POOL` becomes the bind;
    navigation keys are not in the pool).
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

- **The countdown is the character's, not the HUD's.** The weapon component holds
  `ExitPending`, `ExitAt`, `ExitStartedAt`, `ExitCalledOffAt` and `ExitDue` and runs the
  15 s, the freeze and the call-off on its own Tick (`combat/weapon_component/save_exit.py`;
  `Scripts/net/CLAUDE.md`, "A screen asks"). The HUD asks for it (`AskSaveExit`), draws its
  clock, and leaves when it is due.
- **The panel's `save and exit` row** closes it and asks for the 15 s countdown (`EXIT_SECONDS`,
  `combat/ask_consts.py`), drawn top centre (`profile_draw.py`). When the component says
  `ExitDue`, the HUD (once: `ExitLeaving`) puts the player's stats and inventory into a fresh
  `/Game/UI/BP_Profile` (a `USaveGame`, slot `OtherworldProfile`) and opens the title level,
  which opens on the main menu.
- **Stored:** Health, Stamina, Hunger, Thirst, Temperature, the kill count, the equipped slot,
  and each carried item's class, `Loaded`, `Reserve` and `Slot` (`ITEM_FIELDS`: where it
  was carried; a profile saved before slots had no `ItemSlot`, and loads with the first
  item in hand and the rest in the bag), and each worn slot's class (`WornClasses`, indexed
  like the weapon component's `Worn`, none where nothing is worn; a profile saved before
  it loads wearing nothing). **Never the location**; the verifier
  asserts BP_Profile has no other field.
- **Nothing holds the character still during the countdown, and its movement is never
  disabled.** Whatever would move it calls the exit off instead, and one that was moving
  when it asked brakes to a stand. Until 13 Oct 2026 the countdown called
  `DisableMovement` every Tick: the motion matching's Foot Placement node reads a movement
  mode that is not walking as "in the air" and stops fitting the feet to the ground, so on
  a slope the legs snapped flat as the countdown began and back when it ended (39 cm at
  one foot on a 25 degree slope). `probes/probe_save_exit_legs.py` stands on a slope and
  holds the feet where they stood. Looking around still works, and so do the stance keys.
- **A hit, a move key, the trigger or leaving the ground calls it off.** A move key is the
  pawn's last movement input, the trigger is the trigger's tap (`trigger.py`, FireForced
  too), and off the ground is the movement not `IsMovingOnGround` (a jump, a climb, an
  exit asked for in the air). A wanderer's swing stamps
  the player's `BP_HealthComponent.LastDamageTime` (`npc/melee.py`), and the countdown stops when
  that passes `ExitStartedAt`. The starvation
  drain lowers Health without stamping it, so it is not a hit. A death calls it off too
  (the dead gate lowers `ExitPending`).
- **Loading:** the first Tick of a started game (after NEW GAME, or at once with `-nomenu`) on
  which the weapon component's Inventory is non-empty sets `ProfileChecked` and, if the slot
  exists, applies it: stats back, the issued loadout destroyed, the saved items spawned with
  `Dropped = false`, the saved garments worn again (one call of the weapon component's
  `ViewWorn` per slot: it spawns the class into `Worn[slot]` hidden, as a wear leaves it,
  and draws it on the body; `probes/probe_clothing_save.py`), then `NeedsRefresh` so the
  component equips them itself. Gating on the
  loadout keeps the issued guns from being added after the saved ones.
- **Death deletes the slot,** what was worn with the bag. `Health <= 0` on Tick, once (`ProfileForgotten`). Tick, not
  DrawHUD: the death pause comes after a 2.2 s settle, and a `-nullrhi` probe never draws.
- **Probe:** `uepy.py --game --probe Scripts/probes/probe_save_exit.py`. It covers the stand, a
  hit, a move key and the trigger calling the exit off and freeing the pawn, the save, the reload and restore, a crafted inventory replacing the
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
- **Not on the title.** The row is collapsed until `GameStarted` and shown from then on
  (`mode_draw.author_mode_words`, with the first row's own collapse); a caret that Up or Down
  brought to it is moved on to the row above or below in the same frame
  (`mode_checks._check_no_cheat_row`). Probe, rendered (DrawHUD does it, and `-nullrhi` draws
  none): `uepy.py --game --title --windowed --probe Scripts/probes/probe_title_no_cheat_row.py`.
- **Probe:** `uepy.py --game --probe Scripts/probes/probe_dev_all_guns.py` writes the request
  flag (no keyboard in a probe). Taking the row by hand needs a play session.
- **Single player only (M32).** The request is lowered on any machine, but the guns are given
  only where the HUD's machine has authority over the GameState
  (`net/state_graph.owned_game_state`): a client's HUD spawning items would make ghosts the
  server never heard of. A server that allows tuning still grants none; that would be an
  `Ask…` event of its own.

## The tuning tabs by mode (M32; `tune_mode.py`, `game_tuner.py`, `game_tuner_consts.py`)

Four tabs tune the game (`TuneTab.gameplay`, which names the tab's entry of
`combat/ask_consts.TUNE_TABLES`: GUN, MONSTER, WORLD, PLAYER); SOUND and GRAPHICS tune this
machine and are the same in both modes. Whether the game may be tuned is one replicated bool
on the GameState, `DevTuning`, written at BeginPlay by the machine that owns it from the
native `ServerAllowsDevTuning` (`Source/CLAUDE.md`): true in single player, and on a server
only one started with `-AllowDevTuning`.

| | single player | client, server allows | client, server refuses |
|---|---|---|---|
| a nudge of a stat on a gameplay tab | the cell moves; the table is kept (`tune_keep`) | the cell moves; `AskTune(table index, the whole table)` goes to the server; nothing is kept | nothing moves, nothing is touched |
| the hint line | the tab's own | the tab's own | `tune_tab.READ_ONLY_HINT`, which says why |
| the kept table at BeginPlay | loaded | not loaded (a Branch on IsStandalone in `tune_keep.author_load_tab`) | not loaded |

- **The server's half is `BP_GameTuner`,** a component of `BP_OtherworldGameState` built by
  this build (`game_tuner.install_game_tuner` adds it; the weapons build must have run). It
  holds the four tables under the HUD's own variable names, so the tabs' apply fragments
  author the same nodes in either graph. Tick, with authority: an inbox of the GameState
  (`state_consts.TUNED`, written by `AskTune` only where `DevTuning`) that is as long as its
  table replaces the table and raises its Touched flag, and is emptied either way; then the
  applies run, the guns' and the player's once per `BP_ThirdPersonCharacter` in the world
  (`tune_tick.author_onto_pawn`, `player_tune_tick.author_onto_pawn`).
- **In single player the tuner applies nothing:** no inbox is ever written, so nothing is
  touched, and the HUD's own applies are the ones that run, as before M32.
- **What a server tune does not reach:** the other clients' own copies of a gun's numbers or
  a speed (theirs change when the server's value replicates or corrects them, not before),
  and the other clients' tabs, which go on showing their own tables. The client that tuned
  applies its table to its own copies at once.
- **The whole table is sent,** the world tab's hour cell with it, so a nudge of the day's
  length also sets the server's clock to the client's reading of it.
- **The guns tab's grip rows are read-only with the rest** on a server that refuses, though
  they tune only this machine's picture.
- **Enter's save runs Python** (`tune_save`), which a shipped client does not have; in the
  editor binary it writes the client's own CSV, never the server's.
- **Verified by** `tune_mode_checks.py` (the gate before each gameplay tab's cell write, the
  send, the hint, the standalone load, the tuner) and `combat/verify/asks.check_tune_ask`.
- **Probes:** `probe_net_dev_tuning.py`, one file for both cases
  (`uepy.py --net --clients 2 [--server-arg AllowDevTuning] --probe …`: the nightly sweep
  runs the refusing case only), and `probe_dev_tuning_single.py` for single player.

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

Moved word for word: `docs/history/menu.md#the-i-panel`.

## What the tuning tabs keep (`tune_keep.py`, `tune_keep_consts.py`)

Every tab's table but GRAPHICS SETTINGS' persists between sessions, from one place. A tab
only names itself: `TuneTab.kept` (default true), and from it `keep_slot` and `built_var`.

- **The CSV is the default, the save is what was moved since.** The build bakes the CSV into
  the HUD's table (`<Values>`) and into a second copy no nudge moves (`<Values>Built`).
- **A nudge saves** (`author_keep_tab`, in `tune_tick._author_nudge`): `/Game/UI/BP_TuneSave`
  (a `USaveGame`: `KeptTable`, `KeptBuilt`) into the tab's slot, `OtherworldTune_<action>`.
  No Python, so it works in a packaged build, where Enter's CSV save cannot run.
- **BeginPlay loads** (`author_load_kept`, after the graphics save): only a save whose
  `KeptBuilt` is this build's built table. So a CSV that changed since (by Enter and a
  build, or by hand and a build) wins, and a save never hides it.
- **A loaded table raises the tab's Touched flag**, because the assets hold the CSV's
  numbers: the tab's apply is what puts the save's on the guns, creatures, player and
  cycle. WORLD SETTINGS applies while open *or touched* for this.
- **`TuneTab.unkept_cells`** are never read back (the world tab's hour: the live clock).
- **A new tab is kept by default.** Give it an apply that runs on Touched, nothing else.
- **An apply returns every exec tail, a loop's `Completed` too.** The tabs' fragments are
  chained on Tick and the menu's own rows come last. The gun apply once left its loop's
  `Completed` loose: with a kept gun save loaded, Tick ended there every frame, and the
  title's rows went dead (no new game) until the save was deleted. `tune_checks` and
  `probe_main_menu.py` (the first row with the gun table touched) guard it.
- **Probes never see the developer's saves:** `probes/boot.py` sets the slots aside for the
  run, clears them after each probe and puts them back (`probes/kept_slots.py`).
- **To drop a save:** delete `Saved/SaveGames/OtherworldTune_*.sav`. There is no reset row.
- **Checks:** `tune_keep_checks.check_kept` (which also runs `gfx_save_checks`).
- **Still needs a play session:** a nudge, quit, relaunch, and the number is still there.

## The DEBUG SETTINGS tab (`debug_tune_*.py`)

A tab like the others (a `TuneTab` in `TABS`, laid out by `wbp_tune`, its keys and nudge
`tune_tick`'s), over one subject, `overlays`, and three switches, each OFF or ON (the tab's
`words`: `tune_draw` shows the word, not the number; min 0, max 1, step 1):

- **Monster vision & agro** sets the GameState's `DebugMode`: the sight cones (now drawn
  with thickness 0, a hairline: `npc/paths.SIGHT_CONE_THICKNESS`), the `[NPC-AGRO]` log, the
  wanderers' numbers.
- **Shot trajectory** sets the GameState's `DebugShots` (replicated): the pellet tracers,
  the impact damage numbers, the crosshair down the sights (the HUD's `ShotsOn`, copied as
  `DebugOn` is).
- **Shot log** sets the GameState's `DebugShotLog`: every shot the authority judges is
  written to the log as `SHOT-LOG` lines, read by name by the C++
  (`Source/Otherworld/Private/OtherworldShotLog.h`; `combat/docs/firing_gate.md`, "Debug mode").

The switches are applied once per change (`DebugTuneTouched`), only where this machine owns
the GameState, so a probe's direct write on the GameState stands. They are kept between
sessions like any kept tab (`tune_keep.py`); `BP_Settings` no longer holds a debug flag.
The tab's save row is **FULL STATS**, a cheat: Health, Stamina (and the movement's, by
`SetStamina`), Hunger, Thirst and Temperature to their maximums, where the GameState is
owned; it runs no Python. `debug_tune_checks.py` verifies it,
`probes/probe_debug_tab.py` plays it.

## The GUN SETTINGS tab (`tune_*.py`, `wbp_tune.py`)

Its save works in a packaged build: `TuneTab.native_csv` (the gun tab's alone) makes
`tune_tick._author_save` branch on `CanRunPython` into the C++ `SaveTuningCsv`
(`Scripts/combat/CLAUDE.md`, "Tuning"). Proved on a packaged Development build on 14 Oct
2026, driven by `-ExecCmds="set BP_GraphicsMenuHUD_C_2147482301 TuneRow 1, ... TuneNudge 1,
... TuneSaveRequested True"` (the title's HUD instance; `set` on an object name writes that
object alone): the shotgun's damage moved 22 to 23 in the file and nothing else. macOS
refuses synthetic keys here (no Accessibility grant).


Moved word for word: `docs/history/menu.md#the-gun-settings-tab`.

## The MONSTER SETTINGS tab (`monster_tune_*.py`)

Moved word for word: `docs/history/menu.md#the-monster-settings-tab`.

## The PLAYER SETTINGS tab (`player_tune_*.py`)

Moved word for word: `docs/history/menu.md#the-player-settings-tab`.

Its rows are `combat/player_tuning.PLAYER_STATS`. Two of them, the sights' zoom-in and raise
(`sight_zoom_in_s`, `sight_raise_s`), go down to 0 and are copied onto the weapon component's
`SightZoomIn` and `SightRaise` as they are (`player_tune_tick` kind `COPY`), not replicated:
the aim runs on the owning machine (`combat/docs/aiming.md`).

## The SOUND SETTINGS tab (`sound_tune_*.py`)

Moved word for word: `docs/history/menu.md#the-sound-settings-tab`.

## The WORLD SETTINGS tab (`world_tune_*.py`)

Moved word for word: `docs/history/menu.md#the-world-settings-tab`.

## HUD

Moved word for word: `docs/history/menu.md#hud`.

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
