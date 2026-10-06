"""Who is nearby: the function library every world actor and wanderer asks,
its path and its two functions. Constants only; players.py builds it and is
how a graph calls it.

    BPL_Players   LivingPlayers          every living player's pawn
                  NearestLivingPlayer    the one nearest a point, or none
"""

# Beside the player state it reads (state_consts.py): the weapons build makes
# it, and forest_generator/asset_sources.py names one builder per directory.
PLAYERS_BP_PATH = "/Game/Weapons/BPL_Players"
PLAYERS_CLASS_PATH = f"{PLAYERS_BP_PATH}.BPL_Players_C"

LIVING_FN = "LivingPlayers"
NEAREST_FN = "NearestLivingPlayer"
FN_LIVING_PLAYERS = f"{PLAYERS_CLASS_PATH}:{LIVING_FN}"
FN_NEAREST_LIVING_PLAYER = f"{PLAYERS_CLASS_PATH}:{NEAREST_FN}"

# The functions' pins.
POINT_PIN = "Point"
PLAYERS_PIN = "Players"
PLAYER_PIN = "Player"

# What a verifier sees on a call node (BEL.get_node_title).
LIVING_TITLE = LIVING_FN
NEAREST_TITLE = NEAREST_FN
