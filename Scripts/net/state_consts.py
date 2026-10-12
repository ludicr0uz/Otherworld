"""Where state lives once there is more than one machine: the two Blueprints
that hold what a client reads, and their variables. Constants only; state.py
builds them, state_graph.py is how a graph reaches them.

    BP_OtherworldPlayerState  one per player, replicated to everyone: what is
                              that player's alone (the kills, of wanderers
                              and of other players, "is dead")
    BP_OtherworldGameState    one per world, replicated: what every machine
                              reads the same (debug mode, the difficulty,
                              the world's clock, whether the developer's
                              tuning is allowed here); and, on the server
                              alone, the tuned tables waiting to be applied

The GameMode keeps what only the server reads (the gun-drop streams, the
spawn counter: combat/game_state.py): a client has no GameMode. The noises
the wanderers hear are a native list written there alone (combat/noise.py).

The variables keep the names they had on the GameMode (combat/game_state.py,
combat/difficulty.py), which the weapon component's own DebugMode copy and
the probes share.
"""

from combat.difficulty import DIFFICULTY_VAR
from combat.game_state import DEBUG_MODE_VAR, KILL_COUNT_VAR, PLAYER_DEAD_VAR
from uebp.vars import BOOL, FLOAT, INT, REPLICATED, Var, array

# Beside the health component whose death graph writes them: the weapons
# build makes both, and forest_generator/asset_sources.py names one builder
# per content directory.
PLAYER_STATE_BP_PATH = "/Game/Weapons/BP_OtherworldPlayerState"
PLAYER_STATE_CLASS_PATH = f"{PLAYER_STATE_BP_PATH}.BP_OtherworldPlayerState_C"
GAME_STATE_BP_PATH = "/Game/Weapons/BP_OtherworldGameState"
GAME_STATE_CLASS_PATH = f"{GAME_STATE_BP_PATH}.BP_OtherworldGameState_C"

# --- BP_OtherworldPlayerState ------------------------------------------------
# The wanderers this player killed: the HUD's corner and the death menu's score.
Kills = Var(KILL_COUNT_VAR, INT, 0, rep=REPLICATED)
# This player's character is dead: what their HUD draws the death menu from.
Dead = Var(PLAYER_DEAD_VAR, BOOL, False, rep=REPLICATED)
# The other players' characters this player killed (combat/player_kill.py):
# a count of its own beside the wanderers', since a fight between players is
# scored apart from the forest's.
PLAYER_KILL_COUNT_VAR = "PlayerKillCount"
PlayerKills = Var(PLAYER_KILL_COUNT_VAR, INT, 0, rep=REPLICATED)
PLAYER_TABLE = (Kills, Dead, PlayerKills)

# --- BP_OtherworldGameState --------------------------------------------------
# The developer overlays (tracers, sight cones, wanderer numbers) are on.
DebugMode = Var(DEBUG_MODE_VAR, BOOL, False, rep=REPLICATED)
# The world's difficulty (combat/difficulty.py; 0 is EASY).
Difficulty = Var(DIFFICULTY_VAR, INT, 0, rep=REPLICATED)
# The world's clock (M30; world/world_clock.py). The server's BP_DayNightCycle
# owns the time of day and publishes it here as three numbers that change only
# when someone moves the clock or a length: a client's cycle works its own
# Clock out from them and the server's world time, which the engine's
# GameState already replicates. Nothing is sent per frame.
#   WorldClockOffset   the cycle's Clock when the server's world time was 0,
#                      wrapped into the cycle: Clock = (offset + time) % cycle
#   WorldDayLength     the server's DayLengthSeconds; 0 until it has published
#   WorldNightLength   the server's NightLengthSeconds
WORLD_CLOCK_OFFSET_VAR = "WorldClockOffset"
WORLD_DAY_LENGTH_VAR = "WorldDayLength"
WORLD_NIGHT_LENGTH_VAR = "WorldNightLength"
WorldClockOffset = Var(WORLD_CLOCK_OFFSET_VAR, FLOAT, 0.0, rep=REPLICATED)
WorldDayLength = Var(WORLD_DAY_LENGTH_VAR, FLOAT, 0.0, rep=REPLICATED)
WorldNightLength = Var(WORLD_NIGHT_LENGTH_VAR, FLOAT, 0.0, rep=REPLICATED)
WORLD_CLOCK = (WorldClockOffset, WorldDayLength, WorldNightLength)
# The developer's tuning may change this world's gameplay tables (M32): true
# in single player, on a server only one started with -AllowDevTuning. The
# machine that owns the GameState writes it once, at BeginPlay
# (graphics_menu/game_tuner.py, from the C++ ServerAllowsDevTuning); every
# client's tuning tabs read it, and the server asks it again before it takes
# a table (combat/weapon_component/tune_ask.py).
DEV_TUNING_VAR = "DevTuning"
DevTuning = Var(DEV_TUNING_VAR, BOOL, False, rep=REPLICATED)
# The tables a client's tab sent and the server took, one per gameplay tab,
# in combat/ask_consts.TUNE_TABLES order: an inbox, on the server alone. The
# server's tuner (BP_GameTuner, a component of this Blueprint) empties each
# into its own table and applies it; empty = nothing waiting.
TunedGuns = Var("TunedGuns", array(FLOAT))
TunedMonsters = Var("TunedMonsters", array(FLOAT))
TunedWorld = Var("TunedWorld", array(FLOAT))
TunedPlayer = Var("TunedPlayer", array(FLOAT))
TUNED = (TunedGuns, TunedMonsters, TunedWorld, TunedPlayer)
GAME_TABLE = (DebugMode, Difficulty, *WORLD_CLOCK, DevTuning, *TUNED)

# The GameMode's class defaults that name the two.
GAME_STATE_PROP = "game_state_class"
PLAYER_STATE_PROP = "player_state_class"
