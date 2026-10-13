"""The title level: a stage of its own that the game opens on, with the play
level not loaded, where the menu stands over the player's character in the
gear the saved profile wears (graphics_menu/title_figure.py dresses it). The
stage is a piece of the forest at night: a flat floor in the forest's ground,
the play level's own middle trees round a clearing, under the forest's static
night (no clock: it stays night). New Game opens the play level
(menu_main.py); save and exit comes back here.

  paths   the level's path and name, the play level New Game opens, the
          stage's actor labels and numbers (camera, the floor, how far out
          the trees are kept, which lighting preset) -- constants
  forest  the trees: the forest's scatter run again at the play level's size
          and seed, kept within TREE_RADIUS_CM of the middle, where it is
          thickest -- pure Python, held to the play level's generated import
          by a dev unit test (test_title_forest)
  stage   build_title_level.py's steps: the level made or emptied, the floor,
          the trees (forest_import/trees.py plants them, from the LOD build),
          the night (forest_generator/lighting.py's preset: moon, starfield
          dome, sky light, fog, exposure), the camera the title is seen
          through, the PlayerStart the figure spawns on, saved
  checks  verify_title_level.py's checks: the level and each of those actors

Regenerating the play level with another seed, size or tree density moves
its trees: the unit test fails until forest.py names the new numbers, and
build_title_level.py is run again. probes/probe_title_forest.py checks the
running title, and with --windowed saves a picture of it.
"""
