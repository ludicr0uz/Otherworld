# The graphics menu, settings and HUD

`Scripts/build_graphics_menu.py` builds `/Game/UI/BP_GraphicsMenuHUD` (an `AHUD`) and sets
`BP_ThirdPersonGameMode.HUDClass` to it. That game mode is the global default, so the HUD is in
every level. Run `Scripts/verify_graphics_menu.py` after every edit. It is the only thing that
catches pin literals that compile but mean something else.

This package holds the fragments. The entry point itself is still 2.6k lines, over budget, so
split it before extending it.

**The keys:**
- **M** toggles the panel.
- **1 / 2 / 3 / 4** pick the Low / Medium / High / Ultra presets.
- **D** toggles debug mode.
- **X** (panel open) starts save and exit.

**Why a canvas and not UMG:** UMG layout cannot be authored from Python in 5.8, because
`WidgetTree` is protected. Everything is drawn with `DrawText`/`DrawRect`/`DrawTexture`.

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
  - the seven keybinds (Enter arms a capture; the next key from `KEY_POOL` becomes the bind;
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
    every existing save. BeginPlay refills the array when its length isn't seven.

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

## HUD

**What it draws each frame:**

- **Top-left:** the HP bar, the stamina bar, and the FOOD / H2O / TEMP bars (`survival_bars.py`).
  STARVING and DEHYDRATED are read from the ASC's tags.
- **Top-right:** the kill counter, and the FPS readout in debug mode only.
- **Wanderers:** a projected health bar over each one, plus its number in debug mode.
- **Bottom:** the 10-slot inventory strip, in two rows of five (`INVENTORY_COLUMNS`, 120 px
  slots), with loaded/reserve counts for weapons that use ammo.
- **Centre:** the reticle or scope (`reticle.py`). The reticle's four ticks stand off by the held
  gun's accuracy cloud: `ReticleSpread` (weapon component) × half the viewport width, capped at
  `RETICLE_SPREAD_MAX` with an `FMin` (an `FClamp` would be read as a settings slider).
- **When the player is dead:** only the death menu. `DrawHUD` branches on `GameMode.PlayerDead`
  first.

**Rules:**

- **Lay everything out from the viewport size.** Read slot colour, name and ammo from each item's
  own `SlotColor`/`DisplayName`/`UsesAmmo`/`Loaded`/`Reserve`. The HUD keeps no list of weapons.
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

- **`FKey` pin defaults are the bare key name** (`M`, `One`), not `(KeyName="M")`. Struct text
  compiles and never matches.
- **Nodes are identified by input-pin signature** in the verifier. `get_node_title` is fine for
  variable nodes (`Get DebugMode`) but ambiguous for calls, e.g. `Array_Get` is just `Get`.
