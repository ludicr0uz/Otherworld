"""Pieces of the graphics menu (BP_GraphicsMenuHUD) split out of
build_graphics_menu.py, which is still the entry point and owns the rest.

  presets         the quality presets, applying one, the grass-lighting sync
  grass_tiers     showing/hiding grass tiers per preset
  fps             the debug-mode FPS readout
  canvas          generated art, font, panel text palette, _draw_texture
  menu_nav        Up/Down caret movement and the accept keys, shared by pages
  settings_rows   settings screen constants: SLIDERS, row layout, KEY_POOL
  settings_page   drawing the settings page; pushing settings onto the weapon
  settings_input  rebinding capture, slider nudges, BACK, the save
  difficulty      the DIFFICULTY row (EASY/MEDIUM/SURVIVOR) and its push onto
                  the GameMode, which gameplay reads
  difficulty_checks  verify_graphics_menu.py's checks for that row and push
  stamina_bar     the stamina bar, centred at the bottom under the inventory strip
  survival_bars   hunger/thirst/temperature bars and the debuff names
  scope           the sniper's glass, and when it replaces the crosshair
  reticle         the crosshair: centred, red when blocked, gap = the gun's cloud
  profile_consts  the saved profile and the save-and-exit countdown: names, numbers
  profile_asset   BP_Profile, the SaveGame a character is kept in between sessions
  player_parts    the pawn's health/weapon/survival components and the GameMode,
                  cast once for the profile's read and write
  profile_write   the player's stats and inventory into BP_Profile, and the save
  profile_read    BP_Profile back onto the player: stats, and the saved items
                  spawned in place of the issued loadout
  save_exit       the HUD Tick fragment: delete the profile on death, load it once
                  a game starts, X starts the 15 s exit, a hit calls it off
  profile_draw    the panel's save-and-exit row and the countdown banner
  profile_checks  verify_graphics_menu.py's checks for all of the above
"""
