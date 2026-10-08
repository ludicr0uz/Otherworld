"""uebp.nodes.level -- the game's own net library (C++, the Otherworld
module: Source/Otherworld/Public/OtherworldNetLibrary.h): what a graph asks
about an actor's place on the network (task A2).
"""

NET_LIBRARY = "/Script/Otherworld.OtherworldNetLibrary"

# Actor -> ReturnValue: was it placed in the level (a startup actor every
# machine loads), rather than spawned? The take destroys such an item.
FN_IS_LEVEL_ACTOR = NET_LIBRARY + ".IsLevelActor"
