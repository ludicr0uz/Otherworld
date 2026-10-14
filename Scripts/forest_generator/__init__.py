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
  npc_population      How many wanderers a server keeps: the budget that follows the players (per player, per server, the range)
  npc_ward            Fire holds a wendigo off: while the player holds a lit stick out at it, it does not attack
  terrain             Procedural terrain mesh generator (pure Python, no Unreal dependency)
  tree_cells          How far trees are drawn, and the cells they are planted in
  tree_meshes         The tree meshes the levels plant: cut-down copies of the scans
  tree_placement      Deterministic tree scattering with exact terrain snapping
  undergrowth_checks  Offline checks for the generated foliage meshes, the grass density tiers and the bushes
  verification        Pure-Python verification suite for generated forest levels
  wind                Wind in the grass and the trees: the numbers

  tree_lods  Which levels plant the trees with a LOD chain and an impostor, and which mesh that is

  undergrowth_meshes  The meshes the grass and the bushes are planted from

  low_leaves  Which trees have leaves low enough to walk into, so that passing one is heard as passing a bush is ...

  grass_look  The dark, ground-filling grass: its colours, the ground's under it, which mesh is planted, and which ...

  grass_patch   The grass patch: copies of the library clump, turned and offset, merged into one mesh 1.1-1.2 m across
  pivot_images  The two image files the grass patch's pivot textures are imported from (forest_generator/grass_patch.py)

  grass_regions  Where each grass type grows: one smooth noise field per type, and the mix of types at a point read off them

  grass_sidecar  Write the grass and bush instances to the JSON sidecar the level import reads (forest_import/grass.py, ...
  horde_checks   Offline checks for a Horde Survival level (horde_layout.py): the ring is as dense as asked, the clearing ...
  horde_layout   The Horde Survival level's shape: a dense ring of forest, a sparse clearing in the middle, and a fort of ...

  npc_horde  The Horde Survival level's difficulty: how many monsters it holds, rising a level every three minutes of play
"""
