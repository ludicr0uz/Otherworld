"""The game's UI: the UMG screens and BP_GraphicsMenuHUD, the AHUD that drives
them. build_graphics_menu.py is the entry point and still owns BeginPlay,
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
  menu_screens    which screen is up: main menu (+ its keys), death menu, alive, M panel
  hud_stats       HP bar and number, the kill counter
  hud_flash       a stat bar's group blinking while the bar is low
  stamina_bar     the stamina bar's fill, amber while sprinting
  survival_bars   hunger/thirst/temperature fills and the debuff names
  hud_inventory   the inventory grid and the equipped weapon's name
  fps             the debug-mode FPS readout
  profile_draw    the save-and-exit countdown banner
  settings_page   the settings page's values and hint; pushing settings onto the weapon

Still drawn on the HUD canvas (placed per frame)
  canvas          generated art for the canvas draws, _draw_texture
  reticle         the crosshair: centred, red when blocked, gap = the gun's cloud
  scope           the sniper's glass, and when it replaces the crosshair

Input, settings and state
  presets         the quality presets, applying one, the grass-lighting sync
  grass_tiers     showing/hiding grass tiers per preset
  menu_nav        Up/Down caret movement and the accept keys, shared by pages
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
  dev_consts      the dev-all-guns cheat: its key (K), row label, flags, the guns
  dev_guns        the cheat's Tick fragment: K in the M panel gives one of every
                  gun not carried (run from save_exit, after the countdown)

verify_graphics_menu.py's checks, beside it because it is over budget
  umg_checks         the screens' trees and the graph that creates and writes them
  hud_bar_checks     the stat bars' places, icons and low-bar blink
  difficulty_checks  the DIFFICULTY row and its push
  profile_checks     the saved profile and save and exit
  dev_guns_checks    the dev-all-guns row, key and the five spawns
"""
