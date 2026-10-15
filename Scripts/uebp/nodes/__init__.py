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
  weapon.py   the weapon component's native parent (C++, Source/Otherworld):
              the shot's request, its pellets, and the two events the graph
              hangs its cosmetics on (W1)
  health.py   the health component's native parent (C++, Source/Otherworld):
              the blow, the death, and the two events the graph hangs a
              client's side and the death path on (W3)
  noise.py    the game's own noise list (C++, Source/Otherworld): a noise
              added for the wanderers to hear, and a listener's question (M28)
  leftover.py  the server's list of what is left in the world (C++,
              Source/Otherworld): an actor left there, with its kind's lifetime and
              cap, and one taken out of it (M31)
  population.py  the wanderers' population budget (C++, Source/Otherworld): a
              wanderer registered with its creature's caps; a server's alone (M29)
  guard.py    the game's own RPC guard (C++, Source/Otherworld): what every
              Server event asks first, and the shot of its AimPoint (A5)
  level.py    the game's own net library (C++, Source/Otherworld): whether an
              actor was placed in the level, which the take destroys (A2)
  pose.py     the game's own pose library (C++, Source/Otherworld): how often a
              dedicated server poses a body it never draws (A4)
  inventory.py  the game's own inventory library (C++, Source/Otherworld): a
              graph's word that what a player carries changed, so the server
              writes its record that frame (A3a)
  grip.py     the game's own grip library (C++, Source/Otherworld): where a
              held item sits under the grip socket, its Grip and its row of
              the nudge table, and the tuning tab's reads and writes of it (H2)
  tuning.py   the game's own tuning library (C++, Source/Otherworld): a tuning
              tab's save to a CSV where there is no Python (a packaged build)
  locomotion.py  what the player's motion-matching anim blueprint reads its
              character through: the movement component, and the Game
              Animation Sample's structs and enums
  palette.py  palette nodes (events, casts, break/make) and the standard, actor
              and component macros
"""
