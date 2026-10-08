"""The RPC guard's table (task A5): how often a connection may ask each
Server event, when its refusals close it, and which aim the server takes.
Constants only; net/guard.py authors the calls, combat/install.py writes the
numbers onto the player's guard component (C++: UOtherworldRpcGuard), and
combat/verify/guard.py keeps this table and the events in step.

A token bucket per event per connection: RATES[event] tokens a second, at most
BURST_S seconds of them held, so what a hitch or a late packet bunches up
still passes and a flood does not. A new Server event gets a row here (the
verifier fails without one), and DEFAULT_RATE is only what the component
falls back on for a name it was never told.

The fire rate is the fastest gun's as built (gun_tuning.csv); a gun made
faster than that on the GUN SETTINGS page of a running server would be
refused its extra rounds until the next weapons build.
"""

from combat.ask_consts import SERVER_ASKS
from combat.fire_vars import SERVER_EVENTS as FIRE_EVENTS
from combat.gun_tuning import read_table
from combat.weapon_component.look_vars import SERVER_SET_LOOK
from combat.shot_vars import SERVER_FIRE, SERVER_RELOAD
from combat.strike_vars import SERVER_EVENTS as STRIKE_EVENTS
from combat.tuning import SERVER_CONSUME
from combat.wear_tuning import SERVER_WEAR

GUARD_COMPONENT = "RpcGuard"

# Asks a second.
FIRE_SLACK = 1.2
FASTEST_INTERVAL_S = min(row["interval"] for row in read_table().values() if "interval" in row)
FIRE_RATE = FIRE_SLACK / FASTEST_INTERVAL_S
ASK_RATE = 10.0
LOOK_RATE = 30.0
DEFAULT_RATE = 5.0
BURST_S = 1.0

RATES = {
    SERVER_FIRE: FIRE_RATE,
    SERVER_SET_LOOK: LOOK_RATE,
    **{name: ASK_RATE for name in SERVER_ASKS},
    **{name: DEFAULT_RATE for name in
       (SERVER_RELOAD, *STRIKE_EVENTS, *FIRE_EVENTS, SERVER_WEAR, SERVER_CONSUME)},
}

# More refusals than this within KICK_S closes the connection.
KICK_REFUSALS = 100
KICK_S = 10.0
# The close reason the kicked client is sent, and the server's log lines.
CLOSE_REASON = "ClosedByRpcGuard"
LOG_REFUSED = "RPC-REFUSED"
LOG_KICKED = "RPC-KICKED"

# The aim a shot may name: inside a cone along the server's copy's view,
# opening by AIM_CONE_DEG from a disc AIM_SIDE_CM wide that stands AIM_BACK_CM
# behind its eyes (the camera's boom and shoulder offset, combat/camera.py,
# with room: a near point is off the eyes' own line), and no further than the
# reticle's own trace reaches. Not the gun's range: an honest reticle rests on
# whatever the camera sees, a kilometre out for the sky, and the server's
# pellets stop at the gun's range whatever the point.
AIM_CONE_DEG = 20.0
AIM_BACK_CM = 300.0
AIM_SIDE_CM = 150.0
AIM_MAX_CM = 105000.0

# The component's properties (snake case for Python) -> their values.
NUMBERS = {
    "default_rate": DEFAULT_RATE, "burst_seconds": BURST_S,
    "kick_refusals": KICK_REFUSALS, "kick_seconds": KICK_S,
    "aim_cone_degrees": AIM_CONE_DEG, "aim_back_cm": AIM_BACK_CM,
    "aim_side_cm": AIM_SIDE_CM, "aim_max_cm": AIM_MAX_CM,
}
