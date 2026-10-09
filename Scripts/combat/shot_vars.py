"""The shot and the reload as server requests (task M19): the events' names,
the two counters that reconcile a client's predicted rounds, and the server's
grace on the cooldown. Constants only; the graphs are
weapon_component/shot.py.

    owning client                         server
    the trigger's gate passes  ------->   Server_Fire(AimPoint)
      kick, the shot's sound                AsksServed + 1
      (not the authority:) a round          Held, alive, a gun, a round,
      off Loaded, NextFireTime,             cooled?  no --> nothing
      AsksSent + 1                          a round, NextFireTime, the draw in
                                            the cloud, the pellets from ITS
                                            muzzle to AimPoint, damage, noise
    R                          ------->   Server_Reload
      (not the authority:) ReloadNow,       AsksServed + 1, ReloadNow
      AsksSent + 1

AsksServed replicates to the owner. While it is behind AsksSent the server has
not yet answered everything this client did, so a record that arrives is
older than the client's own count: the view (view.py) leaves the rounds alone
and takes them again once the two agree. A shot the server refused is counted
served too, which is what hands its round back.
"""

from uebp.vars import BOOL, INT, REP_NOTIFY, VECTOR, Var

SERVER_FIRE = "Server_Fire"
AIM_PARAM = "AimPoint"
FIRE_PARAMS = ((AIM_PARAM, VECTOR),)
SERVER_RELOAD = "Server_Reload"
# The reload itself, a plain event: the server's from Server_Reload, and the
# owning client's own call, which is its prediction.
RELOAD_NOW = "ReloadNow"
SERVER_EVENTS = (SERVER_FIRE, SERVER_RELOAD)

# The owning client's: fire and reload asks it has sent.
AsksSent = Var("AsksSent", INT, 0)
# The server's, replicated to the owner: asks it has answered, fired or not.
AsksServed = Var("AsksServed", INT, 0, rep=REP_NOTIFY)
# A probe's stand-in for the reload key (tick.py's FireForced is the trigger's).
ReloadForced = Var("ReloadForced", BOOL, False)

TABLE = (AsksSent, AsksServed, ReloadForced)

# How early, by the server's clock, a shot may arrive and still be fired. A
# client fires on its own clock and its packets do not arrive evenly, so two
# honest shots can reach the server closer together than FireInterval. The
# cooldown is then stamped from the later of now and the old deadline, so
# over any stretch the rate is still the gun's own.
FIRE_GRACE_S = 0.1
