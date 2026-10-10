"""BP_WeaponComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE. A name a constants module owns (``*_tuning.py``, ``paths.py``) is
imported from it; one a graph module used to own is named here, and that
module's ``*_VAR`` is this row. A default the builder alone can make (a class
it was handed, a clip it loads) is in its own short dict.
"""

from uebp.vars import (
    BOOL, FLOAT, INT, KEY, NAME, REPLICATED, REP_NOTIFY, VECTOR, Var, array, cls, key, obj,
)
from combat.paths import FIRE_WARD_VAR, ITEM_CLASS_PATH, THROW_ARC_CLASS_PATH
from combat.ask_consts import (
    EXIT_AT_VAR, EXIT_CALLED_OFF_VAR, EXIT_DUE_VAR, EXIT_PENDING_VAR, EXIT_STARTED_VAR, NEVER)
from combat.headshot_tuning import HEADSHOT_NEVER, HEADSHOT_TIME_VAR
from combat.breath_tuning import (
    BREATH_FORCED_VAR, BREATH_HELD_VAR, BREATH_HOLD_S, BREATH_SCALE_VAR, BREATH_VAR,
    WINDED_VAR,
)
from combat.carry_tuning import LOWERED_VAR, POSE_LOWERED_VAR, RAISE_FORCED_VAR
from combat.chop_tuning import (
    CHOP_COUNT_VAR, CHOP_ITEM_VAR, CHOP_TREE_VAR, WOOD_CLASS_VAR, WOOD_SPOT_VAR,
)
from combat.heat_tuning import BLOW_DAMAGE_VAR
from combat.light_tuning import CAMPFIRE_CLASS_VAR, LIGHT_WOOD_VAR, MATCHES_CLASS_VAR
from combat.seat_tuning import LOOK_VAR, SEAT_VAR, SEATED_VAR, SIGHTS_FORCED_VAR
from combat.slot_tuning import (
    DROP_ITEM_VAR, DROP_REQUEST_VAR, DROP_WANT_VAR, HAND_FROM_VAR, HAS_ROOM_VAR,
    MOVE_DST_VAR, MOVE_FROM_VAR, MOVE_SRC_VAR, MOVE_TO_VAR, NEXT_REQUEST_VAR, NO_REQUEST,
    SLOT_ITEMS_VAR, SLOT_KEYS, SLOT_PICK_VAR, SLOT_REQUEST_VAR, SLOT_WANT_VAR,
    STARTER_HAND_FROM,
)
from combat.sprint_tuning import (
    BASE_SPEED_VAR, SPRINT_AHEAD_VAR, SPRINT_FORCED_VAR, SPRINT_SPEED_VAR,
    STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from combat.sway_tuning import SWAY_RATE, SWAY_RATE_VAR, SWAY_VARS
from combat.torch_tuning import NEAR_FIRE_VAR, STICK_CLASS_VAR, WARD_CARRY_VAR, WARD_ITEM_VAR
from combat.tuning import COMBAT, POLLED_BINDS
from combat.use_tuning import USE_PRESSED_VAR, USE_WAS_VAR, USING_VAR
from combat.wear_tuning import (
    NOT_CLOTHING, TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_ITEM_VAR, WEAR_REQUEST_VAR, WORN_VAR,
)

_ITEM = obj(ITEM_CLASS_PATH)
_CLIP = obj("/Script/Engine.AnimSequenceBase")
_ACTOR = obj("/Script/Engine.Actor")

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
HeadshotTime = Var(HEADSHOT_TIME_VAR, FLOAT, HEADSHOT_NEVER, rep=REP_NOTIFY)
Stamina = Var("Stamina", FLOAT, COMBAT.max_stamina)
MaxStamina = Var("MaxStamina", FLOAT, COMBAT.max_stamina)
Sprinting = Var("Sprinting", BOOL, False)
# The guard (block.py). Read by the fire gate, and by every wanderer's
# swing, which also writes Stamina here when the guard takes the hit.
Blocking = Var("Blocking", BOOL, False, rep=REPLICATED)
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
ItemClass = Var("ItemClass", cls(ITEM_CLASS_PATH))
BloodClass = Var("BloodClass", cls("/Script/Engine.Actor"))
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
# pickup.py: the item a take puts in the inventory, which is the one asked for,
# or a fresh one of its class where that one was placed in the level (task A2).
TakeItem = Var("TakeItem", obj(ITEM_CLASS_PATH))
# local.py: this machine's controller of the owner, or none; whether this Tick
# may read keys; and whether the first local frame's caches are taken.
LocalPC = Var("LocalPC", obj("/Script/Engine.PlayerController"))
LocalInput = Var("LocalInput", BOOL, False)
LocalReady = Var("LocalReady", BOOL, False)
# Save and exit's countdown (save_exit.py): the HUD's banner reads it, and
# leaves once ExitDue.
ExitPending = Var(EXIT_PENDING_VAR, BOOL, False)
ExitAt = Var(EXIT_AT_VAR, FLOAT, 0.0)
ExitStartedAt = Var(EXIT_STARTED_VAR, FLOAT, NEVER)
ExitCalledOffAt = Var(EXIT_CALLED_OFF_VAR, FLOAT, NEVER)
ExitDue = Var(EXIT_DUE_VAR, BOOL, False)

# Sprint. The HUD reads Stamina/MaxStamina for the bar under the player's HP
# bar; BaseSpeed is overwritten on the first frame of BeginPlay with the
# character's own walk speed, which is this same number (player_pace.py). The
# sprint's speed and the stamina's two rates are variables so the PLAYER
# SETTINGS tab can write them.
BaseSpeed = Var(BASE_SPEED_VAR, FLOAT, COMBAT.jog_speed_cms)
SprintSpeed = Var(SPRINT_SPEED_VAR, FLOAT, COMBAT.sprint_speed_cms)
StaminaDrain = Var(STAMINA_DRAIN_VAR, FLOAT, COMBAT.stamina_drain_per_s)
StaminaRegen = Var(STAMINA_REGEN_VAR, FLOAT, COMBAT.stamina_regen_per_s)
SprintSpent = Var("SprintSpent", BOOL, False)
SprintAhead = Var(SPRINT_AHEAD_VAR, BOOL, False)
# Fire held out in front of the player: a lit stick, raised by the use key
# (torch.py writes it every frame). Read only by the wanderers afraid of fire
# (npc/ward.py).
FireWard = Var(FIRE_WARD_VAR, BOOL, False)
# The use key (use.py): held on an item with no sights, its press, and last
# frame's answer. And its one kind, the stick (torch.py): whether a press
# found a campfire in reach, the stick that is raised and the pose to put
# back on it.
Using = Var(USING_VAR, BOOL, False)
UsePressed = Var(USE_PRESSED_VAR, BOOL, False)
UseWas = Var(USE_WAS_VAR, BOOL, False)
NearFire = Var(NEAR_FIRE_VAR, BOOL, False)
WardItem = Var(WARD_ITEM_VAR, _ITEM)
WardCarryPose = Var(WARD_CARRY_VAR, obj("/Script/Engine.AnimSequence"))
# Standing, crouched or prone (stance.py, whose STAND the builder defaults it
# to). Written only by the stance block; the movement component and the
# footsteps are told from it.
Stance = Var("Stance", INT)
# Held.TwoHanded, or false with nothing held: copied behind an IsValid Branch
# once a frame so the guard pose never reads a null Held. And Held.SupportPoint,
# copied beside it (weapon_component/support_hand.py).
HeldTwoHanded = Var("HeldTwoHanded", BOOL, False)
HeldSupportPoint = Var("HeldSupportPoint", VECTOR)
# A body is being searched: the HUD writes it while its loot window is open,
# and the pose weights kneel the body from it.
Searching = Var("Searching", BOOL, False)
# The camera's own share of the sights (seat.py): the latch that says the gun
# is up, how far the camera has gone onto it and turned onto its sight line,
# and the probes' stand-in for the sights key.
SightSeated = Var(SEATED_VAR, BOOL, False)
SightSeat = Var(SEAT_VAR, FLOAT, 0.0)
SightLook = Var(LOOK_VAR, FLOAT, 0.0)
SightsForced = Var(SIGHTS_FORCED_VAR, BOOL, False)
# The sight sway (sway.py): its clock, and how far it has turned the view.
SWAY = tuple(Var(name, FLOAT, 0.0) for name in SWAY_VARS)
# Its rate (the held gun's) and the held breath (breath.py): the breath left,
# held this frame, winded, the scale it puts on the sway's width, and the
# probes' stand-in for the key.
SwayRate = Var(SWAY_RATE_VAR, FLOAT, SWAY_RATE)
Breath = Var(BREATH_VAR, FLOAT, BREATH_HOLD_S)
BreathScale = Var(BREATH_SCALE_VAR, FLOAT, 1.0)
BreathHeld = Var(BREATH_HELD_VAR, BOOL, False)
Winded = Var(WINDED_VAR, BOOL, False)
BreathForced = Var(BREATH_FORCED_VAR, BOOL, False)
# The polled keys, as variables rather than as pin literals. Nothing in this
# component loads them: the HUD pushes the player's binds in every DrawHUD
# frame (graphics_menu/settings_page._author_push_settings), which keeps the
# component free of any cast to the HUD and of any knowledge that a save file
# exists. The defaults are therefore also the standalone fallback: a weapon
# component on an actor with no HUD in front of it still plays with the keys
# tuning.py documents.
BINDS = tuple(Var(name, KEY, key(k)) for name, k in POLLED_BINDS)
# The slots (slot_tuning.py): the number keys, SlotItems (the sync's view),
# where the hand's item came from (the issued shotgun's slot), whether a
# pick-up fits, and the requests, all NO_REQUEST at rest.
SLOT_BINDS = tuple(Var(name, KEY, key(k)) for name, k, _slot in SLOT_KEYS)
SlotItems = Var(SLOT_ITEMS_VAR, array(_ITEM))
HandFrom = Var(HAND_FROM_VAR, INT, STARTER_HAND_FROM)
SLOT_REQUESTS = tuple(Var(name, INT, NO_REQUEST) for name in (
    SLOT_PICK_VAR, SLOT_REQUEST_VAR, SLOT_WANT_VAR, MOVE_FROM_VAR, MOVE_TO_VAR,
    MOVE_SRC_VAR, MOVE_DST_VAR, DROP_REQUEST_VAR, DROP_WANT_VAR, NEXT_REQUEST_VAR))
HasRoom = Var(HAS_ROOM_VAR, BOOL, True)
# What the ready pose should reflect (carry.py writes it) and what it
# currently does. The pair is what makes the pose edge-triggered (see
# ready_pose.py); the two match, so the first frame sees no edge and does not
# re-equip for nothing.
Lowered = Var(LOWERED_VAR, BOOL, False)
PoseLowered = Var(POSE_LOWERED_VAR, BOOL, False)
RaiseForced = Var(RAISE_FORCED_VAR, BOOL, False)
# Accuracy (accuracy.py): the cloud, the kick's scale and the reticle's size,
# written once a frame. ShotDirection is the one draw of a shot's direction
# inside the cloud, stored because the cone is pure and every pellet of the
# shotgun must share it.
AimSpread = Var("AimSpread", FLOAT, 0.0)
RecoilScale = Var("RecoilScale", FLOAT, 0.0)
ReticleSpread = Var("ReticleSpread", FLOAT, 0.0)
ShotDirection = Var("ShotDirection", VECTOR)
# The fire press that ate an item, until it is released; see consume.py.
TriggerSpent = Var("TriggerSpent", BOOL, False)
# The clothing worn, one entry per wear_tuning.WEAR_SLOTS slot (grown by the
# first wear into it), the I panel's take-off request, and the garment and
# slot a wear or a take-off is moving (wear.py).
Worn = Var(WORN_VAR, array(_ITEM))
WearItem = Var(WEAR_ITEM_VAR, _ITEM)
# The item a drag out of the inventory is setting down (drop_request.py).
DropItem = Var(DROP_ITEM_VAR, _ITEM)
TakeOffSlot = Var(TAKE_OFF_VAR, INT, NOT_CLOTHING)
TakeOffTo = Var(TAKE_OFF_TO_VAR, INT, NOT_CLOTHING)
WearRequest = Var(WEAR_REQUEST_VAR, INT, NOT_CLOTHING)
WearSlot = Var("WearSlot", INT, NOT_CLOTHING)
# The dead gate's answer (dead.py), and a probe's stand-ins for the fire, the
# sprint and the aim keys.
OwnerDead = Var("OwnerDead", BOOL, False)
FireForced = Var("FireForced", BOOL, False)
# The world's time at the fire action's last press (trigger.py); never, at rest.
FirePressedAt = Var("FirePressedAt", FLOAT, -1.0)
SprintForced = Var(SPRINT_FORCED_VAR, BOOL, False)
AimForced = Var("AimForced", BOOL, False)
# The GameMode's DebugMode, cached at the moment of firing so the pellet loop
# can branch on a plain bool instead of casting eight times.
DebugMode = Var("DebugMode", BOOL, False)
# The bone the current pellet struck and where it landed (hit_zones.py).
HitBone = Var("HitBone", NAME)
HitPoint = Var("HitPoint", VECTOR)
# What the player is issued (inventory.STARTER_CLASS_VARS), the builder's to
# fill. Typed as "class of BP_WeaponItem", not "class of Actor": SpawnActor's
# return pin takes its type from its Class pin, and an Actor-typed return
# cannot be added to an array of BP_WeaponItem.
ShotgunClass = Var("ShotgunClass", cls(ITEM_CLASS_PATH))
PistolClass = Var("PistolClass", cls(ITEM_CLASS_PATH))
KnifeClass = Var("KnifeClass", cls(ITEM_CLASS_PATH))
AxeClass = Var("AxeClass", cls(ITEM_CLASS_PATH))
MatchesClass = Var(MATCHES_CLASS_VAR, cls(ITEM_CLASS_PATH))
StickClass = Var(STICK_CLASS_VAR, cls(ITEM_CLASS_PATH))
# BP_BulletImpact, and what a strike of the matches spawns (light.py): that
# one is left None here, build_survival.py fills it in.
ImpactClass = Var("ImpactClass", cls("/Script/Engine.Actor"))
CampfireClass = Var(CAMPFIRE_CLASS_VAR, cls("/Script/Engine.Actor"))
# The empty-handed punch (punch.py): its clip on the worn rig, the press
# queued for the swing, the cooldown, and the blow still to land.
PunchAnim = Var("PunchAnim", _CLIP)
PunchQueued = Var("PunchQueued", BOOL, False)
PunchPending = Var("PunchPending", BOOL, False)
NextPunchTime = Var("NextPunchTime", FLOAT, 0.0)
PunchDueTime = Var("PunchDueTime", FLOAT, 0.0)
# What the knife's blow takes off the body it met (hot_blow.py).
BlowDamage = Var(BLOW_DAMAGE_VAR, FLOAT, 0.0)
# The knife's slash (knife.py): the same four, on the knife's own clip; and
# the axe's own clip, with the ready pose that says the axe is in hand.
KnifeAnim = Var("KnifeAnim", _CLIP)
AxeAnim = Var("AxeAnim", _CLIP)
AxePose = Var("AxePose", _CLIP)
KnifeQueued = Var("KnifeQueued", BOOL, False)
KnifePending = Var("KnifePending", BOOL, False)
NextKnifeTime = Var("NextKnifeTime", FLOAT, 0.0)
KnifeDueTime = Var("KnifeDueTime", FLOAT, 0.0)
# Interact (interact.py): the candidate nearest the reticle's point so far
# (any actor: an item is one kind of it), its distance to that point (the
# builder defaults it to interact.INTERACT_NO_GAP), and the probe's stand-in
# for the key.
InteractTarget = Var("InteractTarget", _ACTOR)
InteractGap = Var("InteractGap", FLOAT)
InteractForced = Var("InteractForced", BOOL, False)
CrouchForced = Var("CrouchForced", BOOL, False)
# The throw (throw.py): the aim and the launch it stores, the item in the
# air, and the arc actor it draws on.
ThrowAiming = Var("ThrowAiming", BOOL, False)
ThrowKeyForced = Var("ThrowKeyForced", BOOL, False)
ThrowClickForced = Var("ThrowClickForced", BOOL, False)
Thrown = Var("Thrown", _ITEM, rep=REPLICATED)
ThrowStart = Var("ThrowStart", VECTOR)
ThrowVelocity = Var("ThrowVelocity", VECTOR)
ThrowLast = Var("ThrowLast", VECTOR)
ThrowTime = Var("ThrowTime", FLOAT, 0.0)
# What the thrown item's fall to the ground ignores (throw_strike.py), the
# bone of the body the blade is set into, None for no bone, and where on that
# bone's body.
ThrowPast = Var("ThrowPast", array(_ACTOR))
ThrowBone = Var("ThrowBone", NAME)
ThrowSkin = Var("ThrowSkin", VECTOR)
# Its wind-up (throw_windup.py): the clip, the item it is throwing and when
# the hand lets go; and the pose the arm waits in while the key is held
# (throw_ready.py). The builder fills the clips where the skin has them.
ThrowAnim = Var("ThrowAnim", _CLIP)
ThrowReadyAnim = Var("ThrowReadyAnim", _CLIP)
ThrowWinding = Var("ThrowWinding", _ITEM)
ThrowDueTime = Var("ThrowDueTime", FLOAT, 0.0)
# Chopping a tree (chop.py): the tree being cut, the blows on it, where the
# wood lands, and the wood.
ChopTree = Var(CHOP_TREE_VAR, obj("/Script/Engine.PrimitiveComponent"))
ChopItem = Var(CHOP_ITEM_VAR, INT, -1)
ChopCount = Var(CHOP_COUNT_VAR, INT, 0)
WoodSpot = Var(WOOD_SPOT_VAR, VECTOR)
WoodClass = Var(WOOD_CLASS_VAR, cls(ITEM_CLASS_PATH))
# Lighting a campfire (light.py): the piece of wood the strike burns.
LightWood = Var(LIGHT_WOOD_VAR, _ITEM)
ThrowArc = Var("ThrowArc", obj(THROW_ARC_CLASS_PATH))
ThrowArcClass = Var("ThrowArcClass", cls(THROW_ARC_CLASS_PATH))

# Declared first, before the other tables of the component (fx, look, record,
# shot, strike): the builder keeps that order.
CORE = (
    Inventory, Held, EquippedIndex, NeedsRefresh, OwnerMesh, AimPoint, AimValid, AimBlocked,
    Stamina, MaxStamina, Sprinting, Blocking, BaseFOV, CurrentFOV, TargetFOV, Aiming,
    SightAiming, AimZoom, SightBlend, MouseSensitivity, ScopeSensitivity, BaseYawScale,
    BasePitchScale, RecoilDebt, RecoilYawDebt, RecoilYawKick, ItemClass,
    BloodClass, HeadshotTime, SwingSounds, ChopSounds, MatchSounds, ThrowSounds, ThrowSharpSounds,
    PunchHitSounds, BladeHitSounds, LodgeSounds, HeadKillSounds, BreathSounds, BreathNextTime,
    HandledItem, TakeItem, LocalPC, LocalInput, LocalReady, ExitPending, ExitAt, ExitStartedAt,
    ExitCalledOffAt, ExitDue,
)
# ...and these after them.
STATE = (
    BaseSpeed, SprintSpeed, StaminaDrain, StaminaRegen, SprintSpent, SprintAhead, FireWard,
    Using, UsePressed, UseWas, NearFire, WardItem, WardCarryPose, Stance, HeldTwoHanded,
    HeldSupportPoint, Searching, SightSeated, SightSeat, SightLook, SightsForced, *SWAY,
    SwayRate, Breath, BreathScale, BreathHeld, Winded, BreathForced, *BINDS, *SLOT_BINDS,
    SlotItems, HandFrom, *SLOT_REQUESTS, HasRoom, Lowered, PoseLowered, RaiseForced,
    AimSpread, RecoilScale, ReticleSpread, ShotDirection, TriggerSpent, Worn, WearItem,
    DropItem, TakeOffSlot, TakeOffTo, WearRequest, WearSlot, OwnerDead, FireForced,
    FirePressedAt,
    SprintForced, AimForced, DebugMode, HitBone, HitPoint, ShotgunClass, PistolClass,
    KnifeClass, AxeClass, MatchesClass, StickClass, ImpactClass, CampfireClass, PunchAnim,
    PunchQueued, PunchPending, NextPunchTime, PunchDueTime, BlowDamage, KnifeAnim, AxeAnim,
    AxePose, KnifeQueued, KnifePending, NextKnifeTime, KnifeDueTime, InteractTarget,
    InteractGap, InteractForced, CrouchForced, ThrowAiming, ThrowKeyForced, ThrowClickForced,
    Thrown, ThrowStart, ThrowVelocity, ThrowLast, ThrowTime, ThrowPast, ThrowBone, ThrowSkin,
    ThrowAnim, ThrowReadyAnim, ThrowWinding, ThrowDueTime, ChopTree, ChopItem, ChopCount,
    WoodSpot, WoodClass, LightWood, ThrowArc, ThrowArcClass,
)
TABLE = CORE + STATE
