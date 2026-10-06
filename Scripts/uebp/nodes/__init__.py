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
  palette.py  palette nodes (events, casts, break/make) and the standard, actor
              and component macros
"""
