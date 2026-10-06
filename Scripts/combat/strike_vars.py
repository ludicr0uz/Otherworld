"""Melee, the guard, the use key, the throw and the take as server requests
(task M20): the events' names, what the owning machine reports and the server
keeps, and the server's limits. Constants only; the graphs are
weapon_component/punch.py, holds.py, throw.py and pickup.py.

    owning client                         server
    a swing is queued          ------->   Server_Punch / Server_Slash
      (not the authority:) its own          empty hands / a Melee item in a
      cooldown, the clip, the               living hand, not guarding, cooled?
      swing's sound                         the cooldown, the clip, and the
                                            blow due: ITS sweep, TakeHit (the
                                            hot blade's double off ITS item)
    the guard or the use key   ------->   Server_SetHolds(Guard, Use)
    changes                                 AskGuard, AskUse; each Tick
      Blocking, FireWard on its             Blocking = AskGuard AND ITS stamina
      own copy, from the keys               AND not sprinting; FireWard =
                                            AskUse AND ITS item in hand is Lit
    the throw's hand lets go   ------->   Server_Throw(Start, Velocity)
      the throw's sound                     a living hand with an item, nothing
                                            in the air, Start within reach of
                                            ITS copy, the speed capped at the
                                            item's own: the item leaves the
                                            inventory, replicates (InWorld) and
                                            flies; what it strikes is judged
    E on an item               ------->   Server_Take(Item)
                                            alive, Dropped, within reach, room:
                                            into the inventory

In single player the one machine has authority: nothing is predicted and each
Server event is a plain call.
"""

from combat.paths import ITEM_CLASS_PATH
from combat.tuning import INTERACT_RADIUS
from uebp.vars import BOOL, VECTOR, Var, obj

# --- melee ------------------------------------------------------------------
SERVER_PUNCH = "Server_Punch"
SERVER_SLASH = "Server_Slash"
# Two honest swings can arrive closer together than they were made.
STRIKE_GRACE_S = 0.1

# --- the guard and the use key ---------------------------------------------
SERVER_SET_HOLDS = "Server_SetHolds"
GUARD_PARAM, USE_PARAM = "Guard", "Use"
HOLDS_PARAMS = ((GUARD_PARAM, BOOL), (USE_PARAM, BOOL))
# What the owning machine last reported, and what the server was told.
SentGuard = Var("SentGuard", BOOL, False)
SentUse = Var("SentUse", BOOL, False)
AskGuard = Var("AskGuard", BOOL, False)
AskUse = Var("AskUse", BOOL, False)
# A probe's stand-in for the block key: false in every real game.
BlockForced = Var("BlockForced", BOOL, False)

# --- the throw ---------------------------------------------------------------
SERVER_THROW = "Server_Throw"
START_PARAM, VELOCITY_PARAM = "Start", "Velocity"
THROW_PARAMS = ((START_PARAM, VECTOR), (VELOCITY_PARAM, VECTOR))
# How far from the server's copy of the thrower a throw may start: the hand's
# reach, and what a sprinting client is ahead of the server's copy by.
THROW_START_REACH_CM = 300.0
# The item's own speed, and a little for the vector's rounding on the wire.
THROW_SPEED_SLACK = 1.02

# --- the take ----------------------------------------------------------------
SERVER_TAKE = "Server_Take"
ITEM_PARAM = "Item"
TAKE_PARAMS = ((ITEM_PARAM, obj(ITEM_CLASS_PATH)),)
# The interact's reach, and what a moving client is ahead of the server by.
TAKE_REACH_CM = INTERACT_RADIUS + 150.0

SERVER_EVENTS = (SERVER_PUNCH, SERVER_SLASH, SERVER_SET_HOLDS, SERVER_THROW, SERVER_TAKE)

TABLE = (SentGuard, SentUse, AskGuard, AskUse, BlockForced)
