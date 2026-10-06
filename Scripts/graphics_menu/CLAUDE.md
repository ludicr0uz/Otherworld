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
- **Up / Down** move the menu's caret and **Enter** takes the row it is on; a click on a
  row takes it too. **No row has a hotkey** (the 1-4, D, X, K, T, N, O and P keys are gone).
- **Escape is BACK**, in every menu that has somewhere to go back to (below: "Escape").
- **The rows:** `Single Player` (on the title it opens the Single Player page, whose one
  row is `New Game`, or `Continue Game` with a saved profile; in play it reads `Resume` and
  shuts the menu), `Multiplayer` (on the title it opens the Multiplayer page: the server's
  address and `Join Server`; in play it does nothing and says `from the title`), `Controls` (the settings page, titled
  **CONTROLS**; the code still calls it the settings page), `Debug` (wanderer numbers, pellet tracers and impact damage,
  the wanderers' sight cones; not the FPS readout, which is always on), `Save and Exit`
  (as a client of a server it reads `Leave Server`), `Dev All Guns`, `Gun Settings`,
  `Monster Settings`, `World Settings`, `Player Settings`, `Graphics Settings`, `Exit Game` (quits to the desktop,
  saving nothing). The quality presets are not
  rows: Low / Medium / High / Custom is the graphics tab's first row.
- **The settings page or a tuning tab stands in place of the menu's rows**, and its **BACK**
  row returns to them (below: "The M panel as a menu").
- **Tab** (near any body) kneels and opens the loot window; **Up/Down** and **Enter** in it
  (`loot_tick.py`; the rules are `Scripts/loot/CLAUDE.md`).
- **I** opens the inventory (the I panel): the worn garments and the backpack, bottom
  right, are always shown, and I puts the caret and the mouse on them and the character's
  portrait left of them (`wear_*.py`, `inv_*.py`, `Scripts/clothing/CLAUDE.md`). **Up/Down** run the
  caret over the worn slots, then the bag's slots; **Enter** takes a garment off, or brings
  a bag slot's item to hand; the mouse drags an item from slot to slot, a worn garment
  onto the hand or a bag slot, or a carried one onto the worn grid (below). It does not
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
- **The first row** (`START_ACTION`) lowers `MenuOpen` in play (`resume`); on the title it
  opens the Single Player page (below: "The two modes"), whose row sets `GameStarted`,
  stops the paused tick and unpauses, last (`menu_main._author_new_game`). DrawHUD writes
  that row's label every frame: `new game`, or `continue game` while the saved profile
  exists (`mode_draw._author_single`: `DoesSaveGameExist` on the profile's slot, asked
  every frame, because save and exit writes it and a death deletes it under a live HUD).
  The row does the same either way: a started game loads the profile if there is one.
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
- **The pause is single player's.** BeginPlay's pause is `net.pause.author_pause`: a Branch
  on IsStandalone in front of the one `SetGamePaused(true)`, so as a client of a server the
  title is an overlay over a running world. Nothing else differs there: the HUD ticks
  either way, `menu_still.py` holds the walk and `author_hold_fire` the fire press while
  the menu is open (neither ever depended on the pause), and the two unpauses
  (`author_unpause`: the first row's, the restart's) are plain calls, a no-op where nothing
  paused. `menu_main_checks` checks the Branch; `probe_net_menu_overlay.py` (`uepy.py --net`)
  is the client's half, with `--windowed` for the fire press, which DrawHUD holds.
- **Probes:** `probe_main_menu.py` pauses the game itself and shows both halves: with the
  HUD not ticking a taken row is not served, ticking it is; save and exit does nothing
  there; the first row starts the game, and in play only shuts the menu.
  `probe_umg_screens.py` reads what the title shows.
- **A probe's game sees the real title only when asked:** `uepy.py --game` passes
  `-nomenu`; `--title` leaves it off, and `probes/boot.py` then takes the title's pause
  (0.25 s in) for the level being up. `probe_title_single.py` is the real BeginPlay path:
  paused, the menu up, Single Player and New Game served, the game unpausing and playing.
- **Still needs a play session:** the keys themselves on the title, exit game from a real
  session, and how the title reads with the paused level behind it.

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
- **Single Player** holds today's entry exactly: its row is the old first row's start.
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
  `MULTIPLAYER`), and as a client its exit row reads `Leave Server`: the session is cleared
  and the engine's `disconnect` returns the process to the title. **The profile's whole
  fragment (`save_exit.py`: the load, save and exit, the wipe on death, and the cheat
  chained after it) runs in standalone only** (`mode_tick.author_mode_in_play`), so a
  server's character never reads the single-player profile and leaving never writes it.
- **IsStandalone is false on the title while a join is pending.** The exit row's label
  flips to `Leave Server` under the open page (unseen); nothing else on the title asks it.
- **Probes:** `probe_title_single.py` and `probe_join_dead_address.py`
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
  - **A row scrolled out of the window keeps its geometry**, and lies over the hint and BACK
    below: the row test is ANDed with "the cursor is over the box" (`author_row_cursor`'s
    `within`).
  - `TUNE_ROW_H` (22.5) is a `WBP_MenuRow`'s desired height read off a rendered run
    (`get_desired_size()` works in a windowed `-game`; cached geometry still reads zeros).
- **Probes:** `probe_menu_cursor.py` (a taken row served once, the tab in the panel's place,
  BACK's caret, the walk taken and given back) and the windowed `probe_menu_cursor_window.py`
  (the graphics tab's five rows under the cursor and no more, the list scrolled to its end);
  `probe_menu_scroll.py` (the bar dragged to the bottom, the middle and the top in both
  scrolling tabs, the caret brought along, the list staying put once let go).
- **Still needs a play session:** Enter and the arrows themselves, the click on BACK,
  dragging the bar with a real mouse (no probe can press a button), and how the corner
  panel reads.

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
    `BP_Settings.Difficulty` and copied onto the GameState's `Difficulty` every `DrawHUD`
    (`difficulty.py`), where this machine owns the GameState: a client plays at the server's. Only EASY does anything yet (the mushroom heal). `-nullrhi` runs no
    `DrawHUD`, so a headless game keeps the GameState's own default, EASY;
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

- **The countdown is the character's, not the HUD's.** The weapon component holds
  `ExitPending`, `ExitAt`, `ExitStartedAt`, `ExitCalledOffAt` and `ExitDue` and runs the
  15 s, the freeze and the call-off on its own Tick (`combat/weapon_component/save_exit.py`;
  `Scripts/net/CLAUDE.md`, "A screen asks"). The HUD asks for it (`AskSaveExit`), draws its
  clock, and leaves when it is due.
- **The panel's `save and exit` row** closes it and asks for the 15 s countdown (`EXIT_SECONDS`,
  `combat/ask_consts.py`), drawn top centre (`profile_draw.py`). When the component says
  `ExitDue`, the HUD (once: `ExitLeaving`) puts the player's stats and inventory into a fresh
  `/Game/UI/BP_Profile` (a `USaveGame`, slot `OtherworldProfile`) and reopens the current level,
  which opens on the main menu.
- **Stored:** Health, Stamina, Hunger, Thirst, Temperature, the kill count, the equipped slot,
  and each carried item's class, `Loaded`, `Reserve` and `Slot` (`ITEM_FIELDS`: where it
  was carried; a profile saved before slots had no `ItemSlot`, and loads with the first
  item in hand and the rest in the bag). **Never the location**; the verifier
  asserts BP_Profile has no other field.
- **The character can't move during the countdown.** Every Tick it waits, the pawn's
  `CharacterMovement` gets `DisableMovement` (keyed off `ExitPending`, not the ask, so the
  probe's variable writes freeze it too). Looking around still works.
- **A hit calls it off**, and `SetMovementMode(Walking)` frees the pawn. A wanderer's swing stamps
  the player's `BP_HealthComponent.LastDamageTime` (`npc/melee.py`), and the countdown stops when
  that passes `ExitStartedAt`. The starvation
  drain lowers Health without stamping it, so it is not a hit. A death calls it off too
  (the dead gate lowers `ExitPending`).
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
