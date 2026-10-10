"""BP_WeaponItem's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE. A name a constants module owns (``*_tuning.py``) is imported from it.
"""

from uebp.vars import (
    REPLICATED,
    BOOL, FLOAT, INT, NAME, ROTATOR, STRING, VECTOR, ZERO_ROTATOR, ZERO_VECTOR, Var, array, obj,
    struct,
)
from combat.chop_tuning import CHOPS_VAR
from combat.heat_tuning import COOL_VAR, HEAT_MATERIAL_VAR, HEATS_VAR, HOT_VAR
from combat.light_tuning import LIGHTS_VAR
from combat.seat_tuning import HAS_SIGHTS_VAR
from combat.slot_tuning import NOT_A_WEAPON, SLOT_VAR, UNPLACED, WEAPON_KIND_VAR
from combat.sway_tuning import SWAY_RATE, SWAY_RATE_VAR
from combat.throw_tuning import (
    LODGE_POINT_VAR, LODGE_TURN_VAR, THROW_DAMAGE_VAR, THROW_EDGE_ON_VAR,
    THROW_GRIP_LOC_VAR, THROW_GRIP_ROT_VAR, THROW_GRIP_VAR, THROW_PITCH_UP_DEG,
    THROW_PITCH_VAR, THROW_SPEED, THROW_SPEED_VAR, THROW_SPIN_DEG_S, THROW_SPIN_VAR,
)
from combat.torch_tuning import BURN_OUT_VAR, BURNS_VAR, LIT_VAR, USE_POSE_VAR
from combat.wear_tuning import (
    CLOTHING_SLOT_VAR, NOT_CLOTHING, WORN_MESH_VAR, WORN_PART_VAR,
)

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
# Two more, arrays of takes, on every item (Sound/sound_items.py binds them
# by the item's type): what it sounds like handled -- moved between slots,
# brought to hand, put away -- and used up (food eaten). Empty is silence.
HandleSounds = Var("HandleSounds", array(obj("/Script/Engine.SoundBase")))
UseSounds = Var("UseSounds", array(obj("/Script/Engine.SoundBase")))
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
# A thrown blade left in a tree or a body (throw_strike.py sets it as it sets
# the item in). The pick-up reads it: taken back with empty hands, it goes to
# the hand, not to a slot (pickup.py), and stops being Lodged.
Lodged = Var("Lodged", BOOL, rep=REPLICATED)
# Loose in the world, in the air or lying: set by the server as the item
# leaves a hand for it and lowered by the take (item_world.py). Replicated: a
# client's copy of the item is shown only while it is.
InWorld = Var("InWorld", BOOL, False, rep=REPLICATED)
# Whether the server has put the actor to sleep (NetDormancy DormantAll): an item
# lying still, or carried. Its own Tick decides (item_world.py); not replicated.
Dormant = Var("Dormant", BOOL, False)
DisplayName = Var("DisplayName", STRING)
PelletCount = Var("PelletCount", INT)
Dropped = Var("Dropped", BOOL, rep=REPLICATED)
# Ammunition. UsesAmmo false means the other four are never read (the
# consumables), and the fire gate short-circuits on it. InfiniteReserve is the
# pistol: a real magazine to reload, over a reserve that is never charged and
# never credited by shell pickups.
UsesAmmo = Var("UsesAmmo", BOOL)
MagazineSize = Var("MagazineSize", INT)
Loaded = Var("Loaded", INT)
Reserve = Var("Reserve", INT)
InfiniteReserve = Var("InfiniteReserve", BOOL)
# Held trigger or tapped trigger. Read only behind the fire gate, where Held
# is known valid -- a pure Get off a null self is an Accessed None every
# frame, and the outer gate's condition is pulled on frames where nothing is
# equipped at all.
Automatic = Var("Automatic", BOOL)
# Used rather than fired: the fire key sends CONSUME_EVENT_TAG and the item is
# spent (see weapon_component/consume.py). On the base class, not on
# BP_ConsumableItem, so the weapon component can ask without naming a class
# that is built after it.
Consumable = Var("Consumable", BOOL)
# Swung rather than fired: the fire key slashes with it
# (weapon_component/knife.py). The knife (knife.py).
Melee = Var("Melee", BOOL)
# Its blow bites a tree (weapon_component/chop.py): the axe. Read behind the
# blow's own IsValid(Held).
Chops = Var(CHOPS_VAR, BOOL)
# Struck rather than fired: the fire key lights a campfire with it
# (weapon_component/light.py). The matches. Read behind the fire gate, as
# Melee is.
Lights = Var(LIGHTS_VAR, BOOL)
# Aimed down its sights by the sights key: a gun. False on everything else,
# which that key aims over the shoulder (weapon_component/ads.py).
HasSights = Var(HAS_SIGHTS_VAR, BOOL)
# Lit at a campfire by the use key, and burning: the stick (stick.py,
# weapon_component/torch.py).
Burns = Var(BURNS_VAR, BOOL)
Lit = Var(LIT_VAR, BOOL, rep=REPLICATED)
# Heated at a campfire by the interact key, and hot: the knife and the axe
# (heat.py, weapon_component/heat.py).
Heats = Var(HEATS_VAR, BOOL)
Hot = Var(HOT_VAR, BOOL, rep=REPLICATED)
# The slot a garment is worn in (wear_tuning.WEAR_SLOTS' index), or
# NOT_CLOTHING: the weapon component wears an item whose slot is >= 0
# (weapon_component/wear.py). Scripts/clothing sets it on each garment.
ClothingSlot = Var(CLOTHING_SLOT_VAR, INT, NOT_CLOTHING)
# What a garment is drawn as, worn: the body component it fills and the
# skeletal mesh that goes there (clothing/specs.py Garment.worn). No name and
# no mesh on every other item, and on a garment nothing is drawn for. Data
# only: nothing reads them yet.
WornPart = Var(WORN_PART_VAR, NAME)
WornMesh = Var(WORN_MESH_VAR, obj("/Script/Engine.SkeletalMesh"))
# Where it is carried (slot_tuning: the hand, a weapon slot, a bag slot, or
# UNPLACED), and which weapon slot it belongs in (NOT_A_WEAPON on everything
# but the guns and the blades). weapon_component/slot_*.py.
Slot = Var(SLOT_VAR, INT, UNPLACED)
WeaponKind = Var(WEAPON_KIND_VAR, INT, NOT_A_WEAPON)
BurnOutTime = Var(BURN_OUT_VAR, FLOAT)
CoolTime = Var(COOL_VAR, FLOAT)
# The overlay a hot blade's model wears (heat.py). None on everything that
# does not heat.
HeatMaterial = Var(HEAT_MATERIAL_VAR, obj("/Script/Engine.MaterialInterface"))
# The pose a lit stick is raised in while the use key holds it out
# (weapon_component/torch.py). None on everything else.
UsePose = Var(USE_POSE_VAR, obj("/Script/Engine.AnimSequence"))
# Where this gun's ready pose has the left hand, in the right hand's bone
# space (support_hand.py): down the sights the hand is held there. Zero on the
# base; nothing holds a hand on an item that has no sights.
SupportPoint = Var("SupportPoint", VECTOR)
# Accuracy: the cloud a shot is drawn in and the kick it puts on the view,
# with their stance and aim factors. One variable per GUN_ACCURACY column
# (weapon_specs.ACCURACY_VARS says which), on the item for the same reason
# AdsZoom is. SpreadDegrees is above, with Damage.
SpreadShoulderScale = Var("SpreadShoulderScale", FLOAT)
SpreadCrouchScale = Var("SpreadCrouchScale", FLOAT)
SpreadProneScale = Var("SpreadProneScale", FLOAT)
PelletSpreadDegrees = Var("PelletSpreadDegrees", FLOAT)
RecoilPitch = Var("RecoilPitch", FLOAT)
RecoilYaw = Var("RecoilYaw", FLOAT)
RecoilShoulderScale = Var("RecoilShoulderScale", FLOAT)
RecoilSightsScale = Var("RecoilSightsScale", FLOAT)
RecoilCrouchScale = Var("RecoilCrouchScale", FLOAT)
RecoilProneScale = Var("RecoilProneScale", FLOAT)
# How fast the sights wander down them (sway_tuning.py): the component copies
# Held's each frame. The default is on the base, so an item with no sights has
# one too, though it never sways.
SwayRate = Var(SWAY_RATE_VAR, FLOAT, SWAY_RATE)
# How far a throw of this item is tipped up from the view, where the reticle
# rests on nothing it can reach (throw_launch.py reads it off Held). The
# default is on the base, so the knife, the food and the water throw on it
# too; a gun's own comes from its spec.
ThrowArcDegrees = Var(THROW_PITCH_VAR, FLOAT, THROW_PITCH_UP_DEG)
# How fast it leaves the hand and how fast it tumbles in the air, and whether
# it leaves squared up to the throw, edge first: a melee weapon's are its own
# (throw_tuning.MELEE_THROW).
ThrowSpeed = Var(THROW_SPEED_VAR, FLOAT, THROW_SPEED)
ThrowSpinDegS = Var(THROW_SPIN_VAR, FLOAT, THROW_SPIN_DEG_S)
ThrowEdgeOn = Var(THROW_EDGE_ON_VAR, BOOL, False)
# What a throw of it takes off a body it strikes, and how it sits lodged in a
# tree (weapon_component/throw_strike.py): a blade's are its own, and the
# base's 0 damage is what keeps every other item from doing either.
ThrowDamage = Var(THROW_DAMAGE_VAR, FLOAT, 0.0)
LodgeTurn = Var(LODGE_TURN_VAR, ROTATOR, ZERO_ROTATOR)
LodgePoint = Var(LODGE_POINT_VAR, VECTOR, ZERO_VECTOR)
# Held by the blade while the throw is cocked (throw_tuning.THROW_GRIP_VAR).
ThrowGrip = Var(THROW_GRIP_VAR, BOOL, False)
ThrowGripLocation = Var(THROW_GRIP_LOC_VAR, VECTOR, ZERO_VECTOR)
ThrowGripRotation = Var(THROW_GRIP_ROT_VAR, ROTATOR, ZERO_ROTATOR)

TABLE = (
    Damage, SpreadDegrees, WeaponRange, FireInterval, NextFireTime, ReloadSeconds,
    MuzzleOffset, SightOffset, SightAim, GripLocation, GripRotation, SlotColor, Icon,
    FireSound, DryFireSound, ReloadSound, HandleSounds, UseSounds, AimPose, TwoHanded, AdsZoom, Scoped, ShotVolume,
    Lodged, InWorld, Dormant,
    DisplayName, PelletCount, Dropped, UsesAmmo, MagazineSize, Loaded, Reserve,
    InfiniteReserve, Automatic, Consumable, Melee, Chops, Lights, HasSights, Burns, Lit,
    Heats, Hot, ClothingSlot, WornPart, WornMesh, Slot, WeaponKind, BurnOutTime, CoolTime, HeatMaterial, UsePose,
    SupportPoint, SpreadShoulderScale, SpreadCrouchScale, SpreadProneScale,
    PelletSpreadDegrees, RecoilPitch, RecoilYaw, RecoilShoulderScale, RecoilSightsScale,
    RecoilCrouchScale, RecoilProneScale, SwayRate, ThrowArcDegrees, ThrowSpeed, ThrowSpinDegS,
    ThrowEdgeOn, ThrowDamage, LodgeTurn, LodgePoint, ThrowGrip, ThrowGripLocation,
    ThrowGripRotation,
)
