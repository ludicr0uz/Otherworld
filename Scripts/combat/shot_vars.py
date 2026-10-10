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
      AsksSent + 1                          (rounds moved:) Reloaded

AsksServed replicates to the owner. While it is behind AsksSent the server has
not yet answered everything this client did, so a record that arrives is
older than the client's own count: the view (view.py) leaves the rounds alone
and takes them again once the two agree. A shot the server refused is counted
served too, which is what hands its round back.
"""

from uebp.vars import BOOL, INT, REP_NOTIFY, Var

# The shot's request is the native base's (task W1: C++,
# OtherworldWeaponComponentBase::Server_Fire; uebp/nodes/weapon.py), and so are
# its refusals, the round it spends and the deadline it stamps. The graph has
# no event of this name: a shot let through comes back as SHOT_FIRED, and each
# of its pellets as PELLET_FLEW.
SERVER_FIRE = "Server_Fire"
AIM_PARAM = "AimPoint"
SHOT_FIRED = "ShotFired"
PELLET_FLEW = "PelletFlew"
# The reload's request is the native base's too (task W2), and so is the
# reload itself, a plain function: the server's from Server_Reload, and the
# owning client's own call, which is its prediction. It works out how many
# rounds move once (its ReloadTake, no node of the graph's), and a reload that
# moved rounds comes back as RELOADED, for the clack.
SERVER_RELOAD = "Server_Reload"
RELOAD_NOW = "ReloadNow"
RELOADED = "Reloaded"
SERVER_EVENTS = (SERVER_FIRE, SERVER_RELOAD)
# The base's functions, which the graph has no event named as.
NATIVE_FUNCTIONS = (SERVER_FIRE, SERVER_RELOAD, RELOAD_NOW)

# Loaded, Reserve and NextFireTime are not rows here or on the component: a
# magazine and a deadline are a gun's own, so they are BP_WeaponItem's
# variables (combat/item_vars.py). The server's writes of Loaded and
# NextFireTime for a shot, and a reload's of Loaded, Reserve and NextFireTime
# on either machine, are C++'s, by name (weapon_component/native.py), with the
# record marked as combat/dirty.py requires of any write (MarkInventoryDirty).
# The graph's own are the owning client's predicted round and deadline.

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
