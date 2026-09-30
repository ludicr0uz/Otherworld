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
- **D** toggles debug mode.
- **X** (panel open) starts save and exit.
- **K** (panel open) is the dev-all-guns cheat (below).

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
  from the game viewport; every key is polled off the controller. The verifier asserts it.
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
  Enter/Space. Mouse clicks are not accepted, since there is no cursor.
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
- **A hit calls it off.** A wanderer's swing stamps the player's `BP_HealthComponent.LastDamageTime`
  (`npc/melee.py`), and the countdown stops when that passes `ExitStartedAt`. The starvation
  drain lowers Health without stamping it, so it is not a hit.
- **Loading:** the first Tick of a started game (after NEW GAME, or at once with `-nomenu`) on
  which the weapon component's Inventory is non-empty sets `ProfileChecked` and, if the slot
  exists, applies it: stats back, the issued loadout destroyed, the saved items spawned with
  `Dropped = false`, then `NeedsRefresh` so the component equips them itself. Gating on the
  loadout keeps the issued guns from being added after the saved ones.
- **Death deletes the slot.** `Health <= 0` on Tick, once (`ProfileForgotten`). Tick, not
  DrawHUD: the death pause comes after a 2.2 s settle, and a `-nullrhi` probe never draws.
- **Probe:** `uepy.py --game --probe Scripts/probes/probe_save_exit.py`. It covers a hit
  calling the exit off, the save, the reload and restore, a crafted inventory replacing the
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
