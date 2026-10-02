"""The game's UI: the UMG screens and BP_GraphicsMenuHUD, the AHUD that drives
them, and BP_GraphicsTuner, the HUD's component that applies a quality
preset. build_graphics_menu.py is the entry point and still owns BeginPlay,
Tick, the DrawHUD skeleton and the wanderers' canvas bars.

The screens (widget trees, authored through the UMGToolSet plugin)
  umg_consts      screen paths, the widget names the HUD writes, labels, layout,
                  palette -- constants only
  umg_author      building a Widget Blueprint's tree from Python: add, style, slot
  wbp_parts       WBP_MenuRow (caret, label, value) and WBP_InventorySlot
  wbp_hud         WBP_HUD: survival bars (bottom left), kills, banner, inventory
                  grid with HP and stamina under it, FPS; an icon by every bar
  wbp_screens     WBP_MainMenu (title + settings pages), WBP_PauseMenu, WBP_DeathMenu

The HUD graph that shows and writes them
  ui_graph        creating the screens at BeginPlay; SetText/SetVisibility/rows helpers
  menu_screens    which screen is up: main menu (+ its keys), death menu, alive,
                  M panel (its rows unless a tuning tab is open; Up/Down/Enter)
  hud_stats       HP bar and number, the kill counter
  hud_flash       a stat bar's group blinking while the bar is low
  stamina_bar     the stamina bar's fill, amber while sprinting
  survival_bars   hunger/thirst/temperature fills and the debuff names
  hud_inventory   the inventory grid and the equipped weapon's name
  fps             the FPS readout, always on screen
  profile_draw    the save-and-exit countdown banner
  settings_page   the settings page's values and hint; pushing settings onto the weapon

Still drawn on the HUD canvas (placed per frame)
  canvas          generated art for the canvas draws, _draw_texture
  reticle         the crosshair: centred, red when blocked, gap = the gun's cloud;
                  left out down a gun's sights, except in debug mode
  reticle_checks  the verifier's checks for that (the sights gate)
  scope           the sniper's glass, and when it replaces the crosshair

Input, settings and state
  presets         the quality presets' names and the CSV's default one;
                  picking one sets Quality
  menu_nav        Up/Down caret movement and the accept keys, shared by pages;
                  what a key poll gains from the wheel; Tick's test for a
                  taken M-panel row (the rows have no hotkeys)
  menu_still      Tick: the controller ignores move input while the M panel
                  is open, so the arrows only work the menu
  cursor_consts   the mouse cursor in the menus: its buttons, variables, rules
  cursor          DrawHUD: showing the cursor while a menu is up, the row
                  under it (by geometry), what a click on it raises, and a
                  tab's BACK row
  settings_rows   settings screen constants: SLIDERS, row order, KEY_POOL
  settings_input  rebinding capture, slider nudges, BACK, the save
  difficulty      the DIFFICULTY row (EASY/MEDIUM/SURVIVOR) and its push onto
                  the GameMode, which gameplay reads
  profile_consts  the saved profile and the save-and-exit countdown: names, numbers
  profile_asset   BP_Profile, the SaveGame a character is kept in between sessions
  player_parts    the pawn's health/weapon/survival components and the GameMode,
                  cast once for the profile's read and write
  profile_write   the player's stats and inventory into BP_Profile, and the save
  profile_read    BP_Profile back onto the player: stats, and the saved items
                  spawned in place of the issued loadout
  save_exit       the HUD Tick fragment: delete the profile on death, load it once
                  a game starts, X starts the 15 s exit, a hit calls it off
  dev_consts      the dev-all-guns cheat: its row, flags, the guns
  dev_guns        the cheat's Tick fragment: its M panel row gives one of every
                  gun not carried (run from save_exit, after the countdown)
  loot_consts     the loot window: keys (Tab, Up/Down, Enter), variables, widget names
  loot_find       Tick: the nearest dead body in reach, loot or none -> LootTarget
  loot_take       Tick: the selected item out of the body and into the bag
  loot_kneel      Tick: the open window is the weapon component's Searching (the
                  kneel), and the controller ignores move input meanwhile
  loot_tick       the loot window's Tick fragment: find, keys, serve a take,
                  kneel (run after save_exit's)
  loot_draw       DrawHUD: the loot prompt, and the window's icon rows and caret
  wbp_loot        WBP_HUD's loot prompt and window (called from wbp_hud)
  legal_consts    the proprietary notices' words and places, WATERMARK_RECIPIENT
  wbp_legal       WBP_MainMenu's LegalNotice and WBP_HUD's Watermark (called
                  from wbp_screens and wbp_hud)
  tune_tab        TuneTab: what a tuning tab is called (its M panel row,
                  variables, widgets, words, save command, where it sits,
                  whether its list scrolls and whether the save is a row of
                  its own); the shared arrows and Enter
  tune_tabs       TABS: the four tabs, in M panel order
  tune_consts     the GUN TUNING tab: variables, widget names, GUN_TAB
  tune_tick       Tick: any tab's keys, nudge and save (author_tab_flow), and
                  the gun table onto every carried gun (run after loot_tick's)
  tune_draw       DrawHUD: a tab's panel, the subject and its values, the
                  caret, BACK, a scrolling list kept on the caret's row
  tune_save       run in the game by the save: the live table into
                  combat/gun_tuning.csv
  wbp_tune        WBP_PauseMenu's four tuning panels (called from wbp_screens)
  monster_tune_consts  the MONSTER TUNING tab: variables, widget names,
                  the creatures' controller classes, MONSTER_TAB
  monster_tune_tick    Tick: the tab's flow, then each creature's row onto
                  every live controller of its class (run after tune_tick's)
  monster_tune_save    run in the game by the save: the live table into
                  npc/monster_tuning.csv
  world_tune_consts    the WORLD TUNING tab: variables, widget names,
                  WORLD_TAB
  world_tune_tick      Tick: the tab's flow, then the lengths and a moved hour
                  onto the day/night cycle and its clock back as the hour
                  (run after monster_tune_tick's)
  world_tune_save      run in the game by the save: the day and night lengths
                  into world/world_tuning.csv

Graphics: what a preset is, the tab that tunes it, the component that applies it
  gfx_stats            the graphics table: each stat's label, unit (percent,
                  metres), step, limits, per-preset defaults and how it is
                  applied; graphics_tuning.csv, which also names the default
                  preset
  gfx_tune_consts      the GRAPHICS TUNING tab: variables, widget names,
                  GFX_TAB; BP_GraphicsTuner's path and variables;
                  BP_GraphicsSave's path, slot and fields
  gfx_tune_tick        Tick: the tab's flow, the pick kept as Quality, the look
                  spread over the presets, the table handed to the tuner
                  and, on a change, kept in the player's save
                  (run after world_tune_tick's)
  gfx_tune_save        run in the game by SAVE DEFAULT: the live table, and
                  the picked preset as the default, into graphics_tuning.csv
  gfx_save             BP_GraphicsSave, the SaveGame the player's pick and
                  Custom row are kept in; BeginPlay's load of it, Tick's save
  gfx_tuner            BP_GraphicsTuner, the HUD's component: Tick applies a
                  dirty row -- the scalability level, a console command per cvar
  gfx_tuner_read       one stat of the applied preset, in the tuner's graph,
                  as the table has it or as the engine takes it
  gfx_tuner_foliage    the tuner's grass and tree cells: draw distances
                  (metres, whatever the view distance), density tiers,
                  grass lighting
  gfx_tuner_sky        the tuner's look multipliers onto BP_DayNightCycle

verify_graphics_menu.py's checks, beside it because it is over budget
  umg_checks         the screens' trees and the graph that creates and writes them
  hud_bar_checks     the stat bars' places, icons and low-bar blink
  difficulty_checks  the DIFFICULTY row and its push
  profile_checks     the saved profile and save and exit
  dev_guns_checks    the dev-all-guns row, key and the five spawns
  loot_checks        the loot window: scan, keys, take, widgets
  legal_checks       the title screen's notice and the HUD's watermark
  tune_checks        the gun tuning tab: table, CSV on the guns, panel, save, writes
  world_tune_checks    the world tuning tab: panel, save, the cycle's Sets
  cursor_checks      the mouse cursor: shown when, the row tests, the clicks
  pause_checks       the M panel as a menu: rows taken by caret or click (no
                     hotkeys), one menu at a time, BACK, the scrolling list,
                     the player held still
  monster_tune_checks  the monster tuning tab: table, CSV on the controllers,
                     panel, save, writes
  gfx_checks         the graphics tuning tab: table, units, CSV, panel (corner,
                     title), the M panel's title, the hand-over to the tuner
  gfx_tuner_checks   BP_GraphicsTuner: each stat reaching what it names
  gfx_save_checks    BP_GraphicsSave, its load and save in the HUD graph, the
                     CSV's default preset, the graphics tab's SAVE DEFAULT row
"""
