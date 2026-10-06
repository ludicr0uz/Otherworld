"""Where state lives once there is more than one machine: the two Blueprints
that hold what a client reads, and their variables. Constants only; state.py
builds them, state_graph.py is how a graph reaches them.

    BP_OtherworldPlayerState  one per player, replicated to everyone: what is
                              that player's alone (the kills, "is dead")
    BP_OtherworldGameState    one per world, replicated: what every machine
                              reads the same (debug mode, the difficulty)

The GameMode keeps what only the server reads (the noise record, the gun-drop
streams, the spawn counter: combat/game_state.py): a client has no GameMode.

The variables keep the names they had on the GameMode (combat/game_state.py,
combat/difficulty.py), which the weapon component's own DebugMode copy and
the probes share.
"""

from combat.difficulty import DIFFICULTY_VAR
from combat.game_state import DEBUG_MODE_VAR, KILL_COUNT_VAR, PLAYER_DEAD_VAR
from uebp.vars import BOOL, INT, Var

# Beside the health component whose death graph writes them: the weapons
# build makes both, and forest_generator/asset_sources.py names one builder
# per content directory.
PLAYER_STATE_BP_PATH = "/Game/Weapons/BP_OtherworldPlayerState"
PLAYER_STATE_CLASS_PATH = f"{PLAYER_STATE_BP_PATH}.BP_OtherworldPlayerState_C"
GAME_STATE_BP_PATH = "/Game/Weapons/BP_OtherworldGameState"
GAME_STATE_CLASS_PATH = f"{GAME_STATE_BP_PATH}.BP_OtherworldGameState_C"

# --- BP_OtherworldPlayerState ------------------------------------------------
# The wanderers this player killed: the HUD's corner and the death menu's score.
Kills = Var(KILL_COUNT_VAR, INT, 0)
# This player's character is dead: what their HUD draws the death menu from.
Dead = Var(PLAYER_DEAD_VAR, BOOL, False)
PLAYER_TABLE = (Kills, Dead)

# --- BP_OtherworldGameState --------------------------------------------------
# The developer overlays (tracers, sight cones, wanderer numbers) are on.
DebugMode = Var(DEBUG_MODE_VAR, BOOL, False)
# The world's difficulty (combat/difficulty.py; 0 is EASY).
Difficulty = Var(DIFFICULTY_VAR, INT, 0)
GAME_TABLE = (DebugMode, Difficulty)

# The GameMode's class defaults that name the two.
GAME_STATE_PROP = "game_state_class"
PLAYER_STATE_PROP = "player_state_class"
