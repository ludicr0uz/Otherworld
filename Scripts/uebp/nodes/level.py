"""uebp.nodes.level -- the game's own net library (C++, the Otherworld
module: Source/Otherworld/Public/OtherworldNetLibrary.h): what a graph asks
about an actor's place on the network (task A2).
"""

NET_LIBRARY = "/Script/Otherworld.OtherworldNetLibrary"

# Actor -> ReturnValue: was it placed in the level (a startup actor every
# machine loads), rather than spawned? The take destroys such an item.
FN_IS_LEVEL_ACTOR = NET_LIBRARY + ".IsLevelActor"

# -> ReturnValue: may the developer's tuning change this world's gameplay
# tables? Single player yes, a server only with -AllowDevTuning, a client no
# (it reads the GameState's DevTuning, which the server writes from this).
FN_SERVER_ALLOWS_DEV_TUNING = NET_LIBRARY + ".ServerAllowsDevTuning"
