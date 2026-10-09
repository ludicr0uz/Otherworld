"""forest_generator package.

  asset_sources       where every non-code byte in Content/ comes from
  bush_placement      Deterministic, intermittent walk-through bushes
  foliage_meshes      Procedural grass-patch and bush geometry
  grass_cells         How grass is cut into map cells, and how far each cell and clump is drawn
  grass_placement     Deterministic knee-high grass scattering
  lighting            Time-of-day lighting presets for generated forest levels
  npc_agro            How a wanderer notices the player, and how it passes the time until then
  npc_drawn           A fire draws the zombies: one burning within reach, and a zombie that has not noticed the player leaves its ...
  npc_placement       Deterministic spawn point for the wandering forest NPC
  npc_stalk           How a wendigo hunts: it roars, comes in round the player from tree to tree, hiding behind each, and charges ...
  npc_strafe          What a hunting wanderer does between two swings: it gives ground and steps round the player instead of ...
  npc_voice           Who keeps quiet until it hunts: a wendigo on patrol makes no sound
  npc_ward            Fire holds a wendigo off: while the player holds a lit stick out at it, it does not attack
  terrain             Procedural terrain mesh generator (pure Python, no Unreal dependency)
  tree_cells          How far trees are drawn, and the cells they are planted in
  tree_meshes         The tree meshes the levels plant: cut-down copies of the scans
  tree_placement      Deterministic tree scattering with exact terrain snapping
  undergrowth_checks  Offline checks for the generated foliage meshes, the grass density tiers and the bushes
  verification        Pure-Python verification suite for generated forest levels
  wind                Wind in the grass and the trees: the numbers
"""
