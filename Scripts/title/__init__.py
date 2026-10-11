"""The title level: a stage of its own that the game opens on, with no forest
loaded, where the menu stands over the player's character in the gear the
saved profile wears (graphics_menu/title_figure.py dresses it). New Game
opens the play level (menu_main.py); save and exit comes back here.

  paths   the level's path and name, the play level New Game opens, the
          stage's actor labels and numbers (camera, lights, the floor and its
          matte) -- constants
  stage   build_title_level.py's steps: the level made or emptied, the floor
          (its material written under /Game/Title),
          the lights and exposure, the camera the title is seen through, the
          PlayerStart the figure spawns on, saved
  checks  verify_title_level.py's checks: the level and each of those actors
"""
