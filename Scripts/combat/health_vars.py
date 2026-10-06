"""BP_HealthComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, FLOAT, INT, VECTOR, Var, array, cls, obj
from combat.tuning import COMBAT

Health = Var("Health", FLOAT, COMBAT.start_health)
MaxHealth = Var("MaxHealth", FLOAT, COMBAT.start_health)
Dead = Var("Dead", BOOL, False)
DespawnOnDeath = Var("DespawnOnDeath", BOOL, False)
RespawnClass = Var("RespawnClass", cls("/Script/Engine.Actor"))
# What a killed wanderer leaves on the ground. Typed as a class rather than
# hard-coded in the graph so this component still compiles when
# BP_AmmoPickup does not exist yet -- which is the case every time this
# builder runs from scratch, because the pickup casts to BP_WeaponComponent
# and so has to be built after it. main() fills the default in afterwards.
AmmoClass = Var("AmmoClass", cls("/Script/Engine.Actor"))
# The weapons a kill can leave behind, class-of-Actor for the same reason
# AmmoClass is, and filled by main() once every weapon blueprint exists.
# Empty is a legal state and means "no weapon ever drops" -- the graph
# checks the length before it draws an index.
DropClasses = Var("DropClasses", array(cls("/Script/Engine.Actor")))
# Where the replacement will appear. Written three times on the way to the
# spawn -- the request, then whichever navmesh point it resolved to -- so
# that the random draw and the nav query are each evaluated exactly once.
RespawnPoint = Var("RespawnPoint", VECTOR)
# The player's voice (voice.py): the takes of a grunt and of a death cry, and
# the last blow already grunted at. The time has no default here: it is
# NEVER_DAMAGED, as LastDamageTime's is, and the builder gives both.
HurtSounds = Var("HurtSounds", array(obj("/Script/Engine.SoundBase")))
DeathSounds = Var("DeathSounds", array(obj("/Script/Engine.SoundBase")))
HeardDamageTime = Var("HeardDamageTime", FLOAT)
# The low-health heartbeat, and when it may next be played (Sound/sound_world.py).
HeartbeatSounds = Var("HeartbeatSounds", array(obj("/Script/Engine.SoundBase")))
HeartbeatNextTime = Var("HeartbeatNextTime", FLOAT, 0.0)
# Damage (damage.py). Who struck the last blow, and with what: the controller
# a kill is credited to, and the weapon, the thrown blade or the wanderer.
# The server's alone: a client has no controller but its own.
LastInstigator = Var("LastInstigator", obj("/Script/Engine.Controller"))
LastCause = Var("LastCause", obj("/Script/Engine.Actor"))
# How many blows have taken health off this body. Replicated beside Health,
# and what tells a client a blow from a drain; SeenHits is the count a client
# has already answered.
HitCount = Var("HitCount", INT, 0)
SeenHits = Var("SeenHits", INT, 0)
# This machine has run the death path. Its own, never replicated: Dead is the
# server's word and can arrive before this copy's Tick has seen Health at 0.
DeathPlayed = Var("DeathPlayed", BOOL, False)
# A dead player's respawn on a server (player_respawn.py): how long after the
# death's settle the new body comes. A variable, so a probe can shorten it;
# its default is the builder's (death.PLAYER_RESPAWN_WAIT).
PlayerRespawnWait = Var("PlayerRespawnWait", FLOAT)
# ...and whose it is: the body's controller, kept before it lets go of the
# body (GetController is pure, and answers None from then on).
RespawnFor = Var("RespawnFor", obj("/Script/Engine.Controller"))

TABLE = (
    Health, MaxHealth, Dead, DespawnOnDeath, RespawnClass, AmmoClass, DropClasses,
    RespawnPoint, HurtSounds, DeathSounds, HeardDamageTime, HeartbeatSounds, HeartbeatNextTime,
    LastInstigator, LastCause, HitCount, SeenHits, DeathPlayed, PlayerRespawnWait,
    RespawnFor,
)
