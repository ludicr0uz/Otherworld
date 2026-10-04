"""BP_HealthComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, FLOAT, VECTOR, Var, array, cls, obj
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

TABLE = (
    Health, MaxHealth, Dead, DespawnOnDeath, RespawnClass, AmmoClass, DropClasses,
    RespawnPoint, HurtSounds, DeathSounds, HeardDamageTime,
)
