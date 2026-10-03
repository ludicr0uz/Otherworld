"""BP_WeaponItem's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, FLOAT, VECTOR, Var, obj, struct

Damage = Var("Damage", FLOAT)
SpreadDegrees = Var("SpreadDegrees", FLOAT)
WeaponRange = Var("WeaponRange", FLOAT)
FireInterval = Var("FireInterval", FLOAT)
NextFireTime = Var("NextFireTime", FLOAT)
ReloadSeconds = Var("ReloadSeconds", FLOAT)
MuzzleOffset = Var("MuzzleOffset", VECTOR)
# Where the eye goes when this weapon is aimed down its sights, in the
# weapon's own space: on the sight line, behind the rear sight (on the
# scope's axis for the sniper). The camera is moved there from the
# shoulder boom; see weapon_component/sights.py. A variable for the same
# reason MuzzleOffset is -- the component reads it off Held.
SightOffset = Var("SightOffset", VECTOR)
# ...and what the eye looks at from there: the front sight's tip (the
# scope's objective). The camera is turned onto it, so the view runs down
# the sight line itself and the tip is the middle of the screen.
SightAim = Var("SightAim", VECTOR)
GripLocation = Var("GripLocation", VECTOR)
GripRotation = Var("GripRotation", struct("/Script/CoreUObject.Rotator"))
SlotColor = Var("SlotColor", struct("/Script/CoreUObject.LinearColor"))
# The weapon's own silhouette for the inventory strip, drawn by
# build_graphics_menu.py. On the item rather than in a table in the HUD for
# the same reason SlotColor and DisplayName are: adding a weapon stays a
# row in _weapon_specs() and the HUD never learns any weapon's name.
Icon = Var("Icon", obj("/Script/Engine.Texture2D"))
# Three sounds, not one, and all three live on the weapon for the same
# reason FireSound does: the graphs read them off Held, so a new weapon is
# a row in _weapon_specs() and nothing else. The dry-fire and reload
# assets happen to be shared by every weapon today -- that is a fact about
# the defaults, not about the shape of the data.
FireSound = Var("FireSound", obj("/Script/Engine.SoundBase"))
DryFireSound = Var("DryFireSound", obj("/Script/Engine.SoundBase"))
ReloadSound = Var("ReloadSound", obj("/Script/Engine.SoundBase"))
AimPose = Var("AimPose", obj("/Script/Engine.AnimSequence"))
# Held in both hands (the rifle ready pose). The guard reads it to raise
# the gun across the body instead of the fists (body_pose.py). False on
# the base, so the pistol and every consumable guard with the fists.
TwoHanded = Var("TwoHanded", BOOL)
# How far this weapon zooms when the right button is held. On the item for
# the same reason SpreadDegrees is -- the component reads it off Held and
# knows nothing about which weapon it is holding.
AdsZoom = Var("AdsZoom", FLOAT)
# Whether aiming this weapon puts a scope over the screen. A flag rather
# than "AdsZoom >= COMBAT.ads_zoom_scope": the zoom is how far the camera moves
# and the scope is what the sight looks like, and a future weapon is free
# to be a 4x with irons or a 2x with glass without either answer moving.
Scoped = Var("Scoped", BOOL)
# How far this weapon's shot is heard by the wanderers, in cm (see
# SHOT_VOLUME_CM in tuning.py). On the item so the shot's noise is read off
# Held like every other per-weapon number.
ShotVolume = Var("ShotVolume", FLOAT)
Automatic = Var("Automatic")
Consumable = Var("Consumable")
DisplayName = Var("DisplayName")
Dropped = Var("Dropped")
# A thrown blade left in a tree or a body (throw_strike.py sets it as it sets
# the item in). The pick-up reads it: taken back with empty hands, it goes to
# the hand, not to a slot (pickup.py), and stops being Lodged.
Lodged = Var("Lodged", BOOL)
InfiniteReserve = Var("InfiniteReserve")
Loaded = Var("Loaded")
MagazineSize = Var("MagazineSize")
Melee = Var("Melee")
PelletCount = Var("PelletCount")
PelletSpreadDegrees = Var("PelletSpreadDegrees")
RecoilPitch = Var("RecoilPitch")
RecoilSightsScale = Var("RecoilSightsScale")
RecoilYaw = Var("RecoilYaw")
Reserve = Var("Reserve")
UsesAmmo = Var("UsesAmmo")

TABLE = (
    Damage, SpreadDegrees, WeaponRange, FireInterval, NextFireTime, ReloadSeconds,
    MuzzleOffset, SightOffset, SightAim, GripLocation, GripRotation, SlotColor, Icon,
    FireSound, DryFireSound, ReloadSound, AimPose, TwoHanded, AdsZoom, Scoped, ShotVolume,
    Lodged,
)
