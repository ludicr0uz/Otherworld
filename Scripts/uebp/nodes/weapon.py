"""uebp.nodes.weapon -- the weapon component's native parent (C++, the
Otherworld module: Source/Otherworld/Public/OtherworldWeaponComponentBase.h),
which BP_WeaponComponent is a child of (task W1). The shot's server half:
the request, the pellets, and the two events the graph hangs its cosmetics
on (combat/weapon_component/shot.py, firing.py, impact.py).
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
