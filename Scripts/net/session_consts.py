"""The session: which server this process is joining or on, and why the last
one ended. Constants only; game_instance.py builds the Blueprint that holds
them, graphics_menu/mode_*.py is the menu that reads and writes them.

They live on the GameInstance because nothing else outlives a travel: a join
that fails, or a server that drops the player, loads the title's level again
with a new HUD, and the reason has to be there for it to show.
"""

from uebp.vars import BOOL, STRING, Var

GAME_INSTANCE_BP_PATH = "/Game/UI/BP_OtherworldGameInstance"
GAME_INSTANCE_CLASS_PATH = f"{GAME_INSTANCE_BP_PATH}.BP_OtherworldGameInstance_C"
# DefaultEngine.ini's [/Script/EngineSettings.GameMapsSettings] GameInstanceClass
# names it; with the asset missing the engine falls back to a plain one.
GAME_INSTANCE_INI = f"GameInstanceClass={GAME_INSTANCE_CLASS_PATH}"

# What the Multiplayer page's address field holds for a player who never
# changed it: the engine's default port on this machine.
DEFAULT_SERVER_ADDRESS = "127.0.0.1:7777"
# BP_Settings' field for it (combat/settings_vars.py): the local settings,
# never the character's profile.
SERVER_ADDRESS_VAR = "ServerAddress"

# The server being joined or played on; empty in single player and once the
# player has left. Up at a title's BeginPlay, it says the session ended
# without the player leaving it.
JoinAddress = Var("JoinAddress", STRING, "")
# Why the last join failed or the last session dropped; empty when it did not.
NetReason = Var("NetReason", STRING, "")
# A join is under way: the title still stands, waiting for the server.
Connecting = Var("Connecting", BOOL, False)
TABLE = (JoinAddress, NetReason, Connecting)

# ENetworkFailure's enumerators (the Switch node's exec pins) -> what the
# player is told. One not listed reads REASON_OTHER.
NET_REASONS = {
    "ConnectionLost": "the connection to the server was lost",
    "ConnectionTimeout": "the connection to the server timed out",
    "FailureReceived": "the server refused the connection",
    "OutdatedClient": "this game is older than the server",
    "OutdatedServer": "the server is older than this game",
    "PendingConnectionFailure": "could not reach the server",
    "NetGuidMismatch": "this game does not match the server",
    "NetChecksumMismatch": "this game does not match the server",
}
REASON_OTHER = "the network connection failed"
# A travel that failed (a bad address, a level this game does not have), with
# the engine's name for the failure after it.
REASON_TRAVEL = "could not join the server: "
# A title reached with JoinAddress still up and no failure reported.
REASON_CLOSED = "the connection was closed"

# The engine's console commands: leaving a server on purpose, and giving up a
# join that has not connected yet.
LEAVE_COMMAND = "disconnect"
CANCEL_COMMAND = "cancel"
