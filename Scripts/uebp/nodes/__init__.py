"""uebp.nodes -- the one catalog of node paths every builder authors with:
function paths (FN_*), palette nodes (NODE_*) and macros (MACRO_*), one
module per engine library. Checked against the editor by
Scripts/dev/check_node_catalog.py.

  math.py     KismetMathLibrary: arithmetic, comparison, vectors, rotators; INF
  array.py    KismetArrayLibrary
  system.py   the other static libraries: system, string, text, input,
              material, GameplayStatics, user settings
  ai.py       AIModule and the navigation system
  gas.py      GameplayAbilities
  umg.py      UMG widgets and their libraries
  actor.py    member functions of engine classes: actors, components,
              controllers, the HUD, anim instances
  move.py     the game's own movement library (C++, Source/Otherworld): the
              sprint key, the stance and the aim handed to the player's
              movement component, its state read back, the server's writes
  shot.py     the game's own shot library (C++, Source/Otherworld): the
              pellet's trace, rewound to the shooter's view on a server (M22)
  level.py    the game's own net library (C++, Source/Otherworld): whether an
              actor was placed in the level, which the take destroys (A2)
  pose.py     the game's own pose library (C++, Source/Otherworld): how often a
              dedicated server poses a body it never draws (A4)
  inventory.py  the game's own inventory library (C++, Source/Otherworld): a
              graph's word that what a player carries changed, so the server
              writes its record that frame (A3a)
  palette.py  palette nodes (events, casts, break/make) and the standard, actor
              and component macros
"""
