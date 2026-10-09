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
  row, its top row, returns to them (below: "The M panel as a menu").
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

What each feature built, measured and proved is in `docs/history/menu.md`, moved there word
for word. A bullet here that is only its bold line and a link, or a heading with only a
link under it, names its part there.

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

Moved word for word: `docs/history/menu.md#the-m-panel-as-a-menu`.

## The mouse cursor (`cursor.py`, `cursor_consts.py`)

Moved word for word: `docs/history/menu.md#the-mouse-cursor`.

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

Moved word for word: `docs/history/menu.md#presets-and-the-graphics-settings-tab`.

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

## The GUN SETTINGS tab (`tune_*.py`, `wbp_tune.py`)

Moved word for word: `docs/history/menu.md#the-gun-settings-tab`.

## The MONSTER SETTINGS tab (`monster_tune_*.py`)

Moved word for word: `docs/history/menu.md#the-monster-settings-tab`.

## The PLAYER SETTINGS tab (`player_tune_*.py`)

Moved word for word: `docs/history/menu.md#the-player-settings-tab`.

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
