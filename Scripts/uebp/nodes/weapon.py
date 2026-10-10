"""uebp.nodes.weapon -- the weapon component's native parent (C++, the
Otherworld module: Source/Otherworld/Public/OtherworldWeaponComponentBase.h),
which BP_WeaponComponent is a child of (task W1). The shot's server half:
the request, the pellets, and the two events the graph hangs its cosmetics
on (combat/weapon_component/shot.py, firing.py, impact.py); and the reload
(task W2): its request, the reload itself and the event for its clack.
"""

WEAPON_BASE_CLASS = "/Script/Otherworld.OtherworldWeaponComponentBase"

# self, AimPoint: the owning client's trigger, a reliable Server RPC with a
# _Validate. The guard, the gun's own refusals, the round and the deadline.
FN_SERVER_FIRE = WEAPON_BASE_CLASS + ".Server_Fire"
# self, Gun, Muzzle, Direction, Pellets, SpreadDegrees, Range, Damage,
# MaxRewindSeconds, ExtraRewindSeconds: each pellet traced (ShotTrace), a body
# struck handed its damage (TakeHit), and told as PelletFlew.
FN_FIRE_PELLETS = WEAPON_BASE_CLASS + ".FirePellets"
# -> AimPoint: a shot the server let through, its round spent.
NODE_EVENT_SHOT_FIRED = "AddEvent|Otherworld|Shot|EventShotFired"
# -> Start, Stop, bStopped, Point, Normal, bHurt, bScenery, Bone, bHead,
# Damage, Worth: one pellet, for the eye.
NODE_EVENT_PELLET_FLEW = "AddEvent|Otherworld|Shot|EventPelletFlew"
# self: the owning client's R, a reliable Server RPC. The guard, the count,
# then ReloadNow.
FN_SERVER_RELOAD = WEAPON_BASE_CLASS + ".Server_Reload"
# self: the reload on this machine's copy of the held gun (the take worked
# out once, the magazine, the reserve, the deadline, the record's mark).
FN_RELOAD_NOW = WEAPON_BASE_CLASS + ".ReloadNow"
# A reload that moved rounds.
NODE_EVENT_RELOADED = "AddEvent|Otherworld|Shot|EventReloaded"
# The local player's fire action went down (I1; not told while paused).
NODE_EVENT_FIRE_PRESSED = "AddEvent|Otherworld|Input|EventOnFirePressed"
# The base's own property: the fire action is down.
FIRE_HELD = "FireHeld"
# self, Key: the mapping context's one key for the fire action (the owner's
# OtherworldCharacter::SetFireKey; nothing when it already is that key).
FN_SET_FIRE_KEY = WEAPON_BASE_CLASS + ".SetFireKey"
