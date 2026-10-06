"""BP_WeaponComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, FLOAT, INT, VECTOR, Var, array, cls, obj
from combat.paths import ITEM_CLASS_PATH
from combat.headshot_tuning import HEADSHOT_NEVER, HEADSHOT_TIME_VAR
from combat.tuning import COMBAT

Inventory = Var("Inventory", array(obj(ITEM_CLASS_PATH)))
Held = Var("Held", obj(ITEM_CLASS_PATH))
EquippedIndex = Var("EquippedIndex", INT, 0)
NeedsRefresh = Var("NeedsRefresh", BOOL, True)
OwnerMesh = Var("OwnerMesh", obj("/Script/Engine.SkeletalMeshComponent"))
# Where this frame's shot lands, and whether there is anything to draw a
# reticle on. Nothing else writes them. The HUD reads AimValid alone: the
# reticle is always white, so AimBlocked (the muzzle's line stopped short of
# what the camera sees) colours nothing any more.
AimPoint = Var("AimPoint", VECTOR)
AimValid = Var("AimValid", BOOL)
AimBlocked = Var("AimBlocked", BOOL)
# When a round or a thrown blade last struck a head (headshot.py): the HUD
# draws an X round the reticle for a moment after it.
HeadshotTime = Var(HEADSHOT_TIME_VAR, FLOAT, HEADSHOT_NEVER)
Stamina = Var("Stamina", FLOAT, COMBAT.max_stamina)
MaxStamina = Var("MaxStamina", FLOAT, COMBAT.max_stamina)
Sprinting = Var("Sprinting", BOOL, False)
# The guard (block.py). Read by the fire gate, and by every wanderer's
# swing, which also writes Stamina here when the guard takes the hit.
Blocking = Var("Blocking", BOOL, False)
# Aiming down the sights. BaseFOV is cached off the camera at BeginPlay for
# the same reason BaseSpeed is cached off the movement component; CurrentFOV
# is stored because FInterpTo's input is its own previous output, and
# TargetFOV because the two arms of the zoom branch must write one value
# that one interpolation then reads.
BaseFOV = Var("BaseFOV", FLOAT)
CurrentFOV = Var("CurrentFOV", FLOAT)
TargetFOV = Var("TargetFOV", FLOAT)
# Aiming is either aim key (the cone and the recoil read it); SightAiming
# is the down-the-sights key alone (the camera and the scope read it).
# AimZoom is the zoom being aimed at, stored so the walk slowdown's
# ease-out divides by the zoom being let go of; SightBlend is how far the
# camera has travelled from the boom to the sight (weapon_component/sights).
Aiming = Var("Aiming", BOOL)
SightAiming = Var("SightAiming", BOOL, False)
# A divisor (AimZoom - 1) from the first frame, so never 1.0.
AimZoom = Var("AimZoom", FLOAT, COMBAT.shoulder_zoom)
SightBlend = Var("SightBlend", FLOAT, 0.0)
# Mouse sensitivity, and the two controller scales it multiplies. Both
# bases are cached off the PlayerController at BeginPlay -- BasePitchScale
# especially, because the engine ships it negative and a literal would
# invert the look. See the ADS block for what the zoom does to them.
# ScopeSensitivity is the scope's extra multiplier on top of the zoom's
# own slowdown -- the settings screen's second row, pushed like the first.
# 1.0 is "exactly what the controller already does", because the two
# base scales this multiplies are the controller's own. A player who
# never opens the settings screen therefore gets the stock feel.
MouseSensitivity = Var("MouseSensitivity", FLOAT, COMBAT.mouse_sensitivity_default)
ScopeSensitivity = Var("ScopeSensitivity", FLOAT, COMBAT.ads_scope_sens_scale)
# Both overwritten on the first frame of BeginPlay. Seeded with the
# engine's own defaults, signs included, so that a BeginPlay that
# somehow never ran leaves the look working rather than dead.
BaseYawScale = Var("BaseYawScale", FLOAT, 2.5)
BasePitchScale = Var("BasePitchScale", FLOAT, -2.5)
# Recoil. RecoilDebt/RecoilYawDebt are what has been kicked and not yet
# given back, recovered toward zero every frame; RecoilYawKick holds the
# one draw of the sideways component for the frame it is fired on, because
# RandomFloatInRange is pure and a second read would be a second number.
RecoilDebt = Var("RecoilDebt", FLOAT, 0.0)
RecoilYawDebt = Var("RecoilYawDebt", FLOAT, 0.0)
RecoilYawKick = Var("RecoilYawKick", FLOAT, 0.0)
# How many rounds this reload moves, computed once and read back three
# times. See _author_reload for why it cannot just be recomputed.
ReloadTake = Var("ReloadTake", INT, 0)
ItemClass = Var("ItemClass", cls(ITEM_CLASS_PATH))
BloodClass = Var("BloodClass", cls("/Script/Engine.Actor"))
AxeClass = Var("AxeClass")
KnifeClass = Var("KnifeClass")
PistolClass = Var("PistolClass")
ReticleSpread = Var("ReticleSpread")
ShotgunClass = Var("ShotgunClass")
Stance = Var("Stance")
# The component's own sounds, a few takes each (Sound/sound_weapons.py, sound_items.py).
SwingSounds = Var("SwingSounds", array(obj("/Script/Engine.SoundBase")))
ChopSounds = Var("ChopSounds", array(obj("/Script/Engine.SoundBase")))
MatchSounds = Var("MatchSounds", array(obj("/Script/Engine.SoundBase")))
ThrowSounds = Var("ThrowSounds", array(obj("/Script/Engine.SoundBase")))
ThrowSharpSounds = Var("ThrowSharpSounds", array(obj("/Script/Engine.SoundBase")))
PunchHitSounds = Var("PunchHitSounds", array(obj("/Script/Engine.SoundBase")))
BladeHitSounds = Var("BladeHitSounds", array(obj("/Script/Engine.SoundBase")))
LodgeSounds = Var("LodgeSounds", array(obj("/Script/Engine.SoundBase")))
# Sound/sound_weapons.py, sound_world.py and sound_items.py: a thrown axe's
# kill by the head; the breath of a spent sprint and when it may next be
# heard; the item a slot move handled this frame, whose HandleSounds play.
HeadKillSounds = Var("HeadKillSounds", array(obj("/Script/Engine.SoundBase")))
BreathSounds = Var("BreathSounds", array(obj("/Script/Engine.SoundBase")))
BreathNextTime = Var("BreathNextTime", FLOAT, 0.0)
HandledItem = Var("HandledItem", obj(ITEM_CLASS_PATH))
# local.py: this machine's controller of the owner, or none; whether this Tick
# may read keys; and whether the first local frame's caches are taken.
LocalPC = Var("LocalPC", obj("/Script/Engine.PlayerController"))
LocalInput = Var("LocalInput", BOOL, False)
LocalReady = Var("LocalReady", BOOL, False)

TABLE = (
    Inventory, Held, EquippedIndex, NeedsRefresh, OwnerMesh, AimPoint, AimValid, AimBlocked,
    Stamina, MaxStamina, Sprinting, Blocking, BaseFOV, CurrentFOV, TargetFOV, Aiming,
    SightAiming, AimZoom, SightBlend, MouseSensitivity, ScopeSensitivity, BaseYawScale,
    BasePitchScale, RecoilDebt, RecoilYawDebt, RecoilYawKick, ReloadTake, ItemClass,
    BloodClass, HeadshotTime, SwingSounds, ChopSounds, MatchSounds, ThrowSounds, ThrowSharpSounds,
    PunchHitSounds, BladeHitSounds, LodgeSounds, HeadKillSounds, BreathSounds, BreathNextTime,
    HandledItem, LocalPC, LocalInput, LocalReady,
)
