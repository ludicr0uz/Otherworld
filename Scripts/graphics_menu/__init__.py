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
  survival_bars   hunger/thirst/temperature bars and the debuff names
  scope           the sniper's glass, and when it replaces the crosshair
  reticle         the crosshair: centred, red when blocked, gap = the gun's cloud
"""
