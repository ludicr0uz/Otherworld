"""
build_weapons_and_combat.py -- weapons, inventory, aiming, damage and death.

Run inside the editor:
    UnrealEditor-Cmd <uproject> \
      -ExecutePythonScript="<abs>/Scripts/build_weapons_and_combat.py" -NoUI -stdout

Supersedes build_shotgun_and_health.py, which built a single shotgun welded to
the character. Everything that file installed is removed by this one (see
_uninstall_old_shotgun) -- keep the old script only as history.

WHAT THIS BUILDS
----------------
/Game/Weapons
  M_Gunmetal, M_GunWood, M_Blood   flat materials
  Audio/A_ShotgunFire, A_PistolFire  imported from assets/generated/sounds
  BP_WeaponItem     Actor. The base class: every variable the weapon component
                    reads lives here, so the component casts once and never
                    branches per weapon type.
  BP_Shotgun        child of BP_WeaponItem: 7 primitives, 8 pellets, 5 deg cone
  BP_Pistol         child of BP_WeaponItem: 5 primitives, 1 shot, tight, held
                    at a different angle with a different ready pose
  BP_HealthComponent  Health/MaxHealth + death, despawn and respawn
  BP_WeaponComponent  inventory of 5, equip/switch/fire/drop/pick up
  BP_BloodSplash    short-lived red burst spawned at each impact

WHY WEAPONS ARE ACTORS NOW
--------------------------
The old shotgun was a component tree bolted onto the character's mesh, which
cannot be dropped: there is no way to leave a component behind in the world.
A weapon that has to exist both in a hand and on the ground is an Actor. That
one change is what makes drop, pick up and switching fall out naturally --
equipping is an attach, dropping is a detach.

BP_Shotgun and BP_Pistol derive from BP_WeaponItem rather than being two
unrelated Blueprints so that Inventory can be a single typed array and the
firing code can read Damage/Spread/Range/FireSound off whatever is held. The
alternative -- two sibling classes -- would need a cast and a duplicate branch
per weapon in every graph that touches a weapon.

HOW THE WEAPON IS ORIENTED
--------------------------
The weapon is rigidly attached to HandGrip_R and never rotated on its own. What
points it at the crosshair is the character: the body follows the camera's yaw
(face_the_camera) and the ready pose puts the arms down the sights, so the
barrel tracks the crosshair while staying in the fist.

Two things have to be right for that to hold, and each one looked like the
other's bug:

  * HandGrip_R carries the weapon's forward on its **+Y** axis, not its +X.
    _grip_rotation() has the measurements; aiming down +X puts the barrel 90
    degrees across the player's body.
  * The layered blend has to run in **mesh-space rotation** mode, or the ready
    pose's arms inherit the locomotion hips and lose their own pelvis yaw --
    worth a constant 21 degrees to the left. See patch_anim_blueprint().

Neither is visible in a static check of the grip: both rounds of solving it
produced self-consistent numbers and a gun pointing sideways. What settled it
was PrintString on Tick and reading yaws out of a -game run.

THE AIM POSE (the part with a real constraint behind it)
--------------------------------------------------------
The project ships a full Mannequin animation set: MF_Rifle_Idle_ADS,
MF_Pistol_Idle_ADS, directional rifle/pistol walk and jog, aim offsets. What it
does *not* ship is any Anim Blueprint that uses them -- ABP_Unarmed is the only
one, and it drives the unarmed locomotion state machines only.

Authoring a rifle locomotion state machine from Python is not possible: UBlendSpace
exposes no sample-authoring API at all, so the directional walk/jog sets cannot be
assembled into the blend spaces a locomotion graph would need.

What *is* possible is playing an animation into a slot. ABP_Unarmed's AnimGraph
has exactly one Slot node, DefaultSlot, sitting full-body between the locomotion
state machine and the Control Rig. Played as-is, an ADS idle would override the
legs too and the character would slide around in a frozen aim pose.

So patch_anim_blueprint() inserts a Layered blend per bone between the state
machine and the Control Rig: base pose = locomotion, blend pose = DefaultSlot,
branch filter = spine_01. DefaultSlot becomes upper-body-only, and
PlaySlotAnimationAsDynamicMontage(MF_Rifle_Idle_ADS, "DefaultSlot") then puts
the arms and chest in the ready pose while the legs keep walking, running and
jumping normally. One new node, one rewire, and it compiles.

Consequence worth knowing: every montage played on DefaultSlot is now
upper-body-only for this skeleton. Nothing in this project plays a full-body
montage (the NPC despawns rather than playing a death animation), but a future
death or knockdown animation would need its own slot.

BP_WeaponComponent event graph:

  [BeginPlay] --> cache Character + Mesh
              --> spawn BP_Shotgun and BP_Pistol into Inventory
              --> Equip(0)

  [Tick] --> Branch WasInputKeyJustPressed(LeftMouseButton) --> Fire
         --> Branch WasInputKeyJustPressed(Q)               --> cycle equipped
         --> Branch WasInputKeyJustPressed(G)               --> drop held
         --> Branch WasInputKeyJustPressed(E)               --> pick up nearest

  Tick also resolves the aim every frame, before the trigger is even looked at,
  because the reticle depends on it:

    camera -> LineTrace -> AimPoint      what the crosshair is resting on
    muzzle -> LineTrace -> AimPoint      can the gun actually reach it?
                                         if not, AimPoint moves to the wall and
                                         AimBlocked goes true (red reticle)

  Fire: muzzle world location  -> Start
        AimPoint - muzzle      -> direction
        N pellets in a cone    -> LineTraceSingle each
        hit -> BP_BloodSplash at the impact + Health -= Damage

THE HYBRID AIM (why there are two traces and not one)
------------------------------------------------------
Aiming from the muzzle alone is geometrically honest and unplayable: the barrel
is below and to the side of the camera, so shots land off the crosshair, and a
player beside a wall shoots the wall while the crosshair is on an enemy in the
open. Aiming from the camera alone is playable and looks broken: the camera is
on a boom behind the shoulder, so the cone fans out from behind the player.

The camera picks *what* is aimed at; the muzzle decides whether the gun can
reach it, and the pellets then fly down that same muzzle line. The wall check is
not an extra safety net -- it is the same trace the pellets use, which is what
lets the reticle promise only hits the shot can actually make.

This is hitscan: the pellets resolve in the frame they are fired. A projectile
version would use the identical aim resolve and fire a velocity along
(AimPoint - muzzle) instead of tracing it.
"""

import dataclasses
import math
import os
import random
import sys

import unreal

# The NPC tuning lives in the pure-Python placement module (no `unreal` import),
# so the level generator and its offline checks read exactly the numbers the
# editor builds with. The respawn band below is the same one initial placement
# uses -- a replacement wanderer has to obey "75-100 m away" too, or the rule
# holds only until the first kill.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_ui_art import ICON_NAME_FOR                            # noqa: E402
from forest_generator.npc_placement import (                      # noqa: E402
    NPC_SPAWN_MIN_DISTANCE_CM,
    NPC_SPAWN_MAX_DISTANCE_CM,
    NPC_RESPAWN_NAV_SNAP_CM,
    NPC_CAPSULE_HALF_HEIGHT_CM,
    NPC_HIT_REACTION_CLIPS,
)

# ─── Paths ───────────────────────────────────────────────────────────────────

WEAPON_DIR = "/Game/Weapons"
AUDIO_DIR = f"{WEAPON_DIR}/Audio"
# Where Scripts/asset_pipeline/import_ui_art.py puts the generated HUD art.
UI_ART_DIR = "/Game/UI/Art"
MAT_METAL = f"{WEAPON_DIR}/M_Gunmetal"
MAT_WOOD = f"{WEAPON_DIR}/M_GunWood"
MAT_BLOOD = f"{WEAPON_DIR}/M_Blood"
MAT_BRASS = f"{WEAPON_DIR}/M_Brass"

ITEM_BP_PATH = f"{WEAPON_DIR}/BP_WeaponItem"
SHOTGUN_BP_PATH = f"{WEAPON_DIR}/BP_Shotgun"
PISTOL_BP_PATH = f"{WEAPON_DIR}/BP_Pistol"
SMG_BP_PATH = f"{WEAPON_DIR}/BP_SMG"
RIFLE_BP_PATH = f"{WEAPON_DIR}/BP_AssaultRifle"
SNIPER_BP_PATH = f"{WEAPON_DIR}/BP_SniperRifle"
HEALTH_BP_PATH = f"{WEAPON_DIR}/BP_HealthComponent"
WEAPON_COMP_BP_PATH = f"{WEAPON_DIR}/BP_WeaponComponent"
BLOOD_BP_PATH = f"{WEAPON_DIR}/BP_BloodSplash"
AMMO_BP_PATH = f"{WEAPON_DIR}/BP_AmmoPickup"
# The settings SaveGame. It lives beside the weapons rather than under /Game/UI
# because this file builds it, and Scripts/forest_generator/asset_sources.py
# names exactly one builder per content directory -- a second directory owned by
# a second script is the thing that table exists to prevent.
SETTINGS_BP_PATH = f"{WEAPON_DIR}/BP_Settings"
# One slot, index 0. There are no profiles and no per-level settings: a keybind
# the player set once has to be there the next time the game is opened, which is
# the whole requirement.
SETTINGS_SLOT = "OtherworldSettings"
SETTINGS_USER_INDEX = 0

CHARACTER_BP_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"
GAME_MODE_BP_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
NPC_BP_PATH = "/Game/Forest/NPC/BP_ForestWanderer"
ABP_PATH = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"

CHARACTER_CLASS_PATH = f"{CHARACTER_BP_PATH}.BP_ThirdPersonCharacter_C"
GAME_MODE_CLASS_PATH = f"{GAME_MODE_BP_PATH}.BP_ThirdPersonGameMode_C"
NPC_CLASS_PATH = f"{NPC_BP_PATH}.BP_ForestWanderer_C"
ITEM_CLASS_PATH = f"{ITEM_BP_PATH}.BP_WeaponItem_C"
HEALTH_CLASS_PATH = f"{HEALTH_BP_PATH}.BP_HealthComponent_C"
WEAPON_COMP_CLASS_PATH = f"{WEAPON_COMP_BP_PATH}.BP_WeaponComponent_C"
BLOOD_CLASS_PATH = f"{BLOOD_BP_PATH}.BP_BloodSplash_C"
AMMO_CLASS_PATH = f"{AMMO_BP_PATH}.BP_AmmoPickup_C"
SETTINGS_CLASS_PATH = f"{SETTINGS_BP_PATH}.BP_Settings_C"

# The mechanical sounds. All of these, and the five gunshots, are now cut from
# CC0 recordings of real firearms by Scripts/fetch_weapon_sounds.py -- see that
# file for the sources and for why every one of them is public domain rather
# than merely free.
#
# The click stays SHARED by all five weapons: a hammer falling on an empty
# chamber genuinely is the same noise in every receiver, and five copies would
# be five things to keep in step for no audible gain.
#
# The reload does NOT, and that is the one thing the real recordings changed
# about the shape of this data. When it was a synthesised clack, one sound for
# five weapons was defensible because none of them sounded like anything in
# particular. A pump shotgun, a magazine swap and a hand-fed reload are three
# different actions that take three different lengths of time, and the weapon
# already carried a per-weapon ReloadSound slot -- so which one to play is now
# a column in _weapon_specs() like every other difference between guns.
SND_DRY_FIRE = f"{AUDIO_DIR}/A_DryFire"
SND_RELOAD_SHOTGUN = f"{AUDIO_DIR}/A_ReloadShotgun"   # 0.47 s -- a pump cocked
SND_RELOAD_RIFLE = f"{AUDIO_DIR}/A_ReloadRifle"       # 1.56 s -- mag out, mag in, bolt
SND_RELOAD_PISTOL = f"{AUDIO_DIR}/A_ReloadPistol"     # 1.58 s -- slower, hand-fed

# The sound assets this builder imports, and the only list of them. Retiring
# A_Reload (the single shared synthesised clack) is deliberate and is handled
# by retire_old_assets(): a builder that simply stops referencing an asset
# leaves it on disk forever.
#
# Split in two because the two halves carry different distances -- a gunshot is
# heard across the map and a magazine change is not -- and SOUND_ATTENUATION
# below is keyed off the split rather than off a second hand-written list.
GUNSHOT_NAMES = ("A_ShotgunFire", "A_PistolFire", "A_SMGFire", "A_RifleFire",
                 "A_SniperFire")
HANDLING_NAMES = ("A_DryFire", "A_ReloadShotgun", "A_ReloadRifle",
                  "A_ReloadPistol")
SOUND_NAMES = GUNSHOT_NAMES + HANDLING_NAMES
RETIRED_SOUNDS = (f"{AUDIO_DIR}/A_Reload",)

# ── Foley and creature voices ────────────────────────────────────────────────
#
# A second folder, not /Game/Weapons/Audio, because these are not weapon
# sounds: footsteps belong to anything with legs and the growls belong to the
# monsters. They are imported by the same function for the same reason the
# gunshots are -- it is the only importer that exists -- but nothing about them
# is a weapon.
#
# The .wav files come from Scripts/make_creature_sounds.py, which synthesises
# rather than cutting from recordings; that file's docstring says why that is
# the right call for these and the wrong one for gunfire.
CREATURE_AUDIO_DIR = "/Game/Audio"
FOOTSTEP_NAMES = tuple(f"A_Footstep_{i:02d}" for i in (1, 2, 3, 4))
MELEE_HIT_NAMES = tuple(f"A_MeleeHit_{i:02d}" for i in (1, 2, 3))
CREATURE_VOICE_NAMES = (tuple(f"A_ZombieGrowl_{i:02d}" for i in (1, 2, 3))
                        + tuple(f"A_WendigoRoar_{i:02d}" for i in (1, 2, 3)))
CREATURE_SOUND_NAMES = FOOTSTEP_NAMES + MELEE_HIT_NAMES + CREATURE_VOICE_NAMES

# ── How far each of them carries ─────────────────────────────────────────────
#
# Nothing in this project had a USoundAttenuation asset until now, and a
# USoundBase whose AttenuationSettings is None is NOT "attenuated by default".
# Distance falloff and spatialisation are both parsed out of the attenuation
# settings and out of nothing else, so a sound without them plays at full
# volume, dead centre, from anywhere on a 200 m map. That -- not the call
# sites, which were already PlaySoundAtLocation -- is why the audio was flat.
#
# Three profiles rather than one, because how far a noise carries is a fact
# about the noise. A rifle report across a forest and a boot in leaf litter
# differ by orders of magnitude, and one shared falloff has to be wrong for at
# least one of them: sized for the gun, every footstep in the level is audible;
# sized for the boot, a sniper shot from 60 m away is silent.
#
# NATURAL_SOUND is the engine's dB-based curve and is the realistic one: volume
# falls with the logarithm of distance the way sound pressure actually does,
# reaching ATT_DB_AT_MAX at the edge. Linear and Inverse are mixing tools, not
# physics.
#
# Spatialisation stays on SPATIALIZATION_DEFAULT -- the mixer's own panner.
# SPATIALIZATION_HRTF is the other option the enum offers, but it is a request
# for a binaural *plugin*, and with none installed the mixer falls back to the
# panner anyway; asking for it would be a line that claims something the build
# does not do. Panning is what makes the audio directional, and it needs the
# sources to be mono, which fetch_weapon_sounds.py and make_creature_sounds.py
# already guarantee and the verifier already asserts.
ATT_DB_AT_MAX = -60.0
# The distance low-pass, for the profiles that ask for it. 20 kHz is "no
# filtering at all", so the near end is deliberately the full band and only the
# far end is dulled.
ATT_LPF_NEAR_HZ = 20000.0
ATT_LPF_FAR_HZ = 2500.0
# The brief's ceiling: nothing in the game may be audible from further than
# 100 m. UE units are centimetres, and the falloff is measured from the EDGE of
# the full-volume sphere, so the audible radius is radius + falloff.
AUDIBLE_LIMIT_CM = 10000.0


@dataclasses.dataclass(frozen=True)
class AttenuationProfile:
    """One USoundAttenuation asset.

    ``radius_cm`` is the sphere inside which the sound is at full volume --
    roughly "at arm's length from the thing making it" -- and ``falloff_cm``
    the distance beyond that over which it fades to ATT_DB_AT_MAX.

    ``air_absorption`` turns on the engine's distance low-pass. Only the
    gunshots use it: high frequencies are the first thing air eats, which is
    why distant gunfire is a thump rather than a crack, and it is only over
    tens of metres that the effect exists at all.
    """

    name: str
    radius_cm: float
    falloff_cm: float
    air_absorption: bool = False

    @property
    def path(self):
        return f"{CREATURE_AUDIO_DIR}/{self.name}"

    @property
    def audible_cm(self):
        return self.radius_cm + self.falloff_cm


# 100 m exactly -- the loudest thing in the game spends the whole allowance.
ATT_GUNFIRE = AttenuationProfile("A_Att_Gunfire", 200.0, 9800.0,
                                 air_absorption=True)
# 40 m: far enough that a wanderer is heard before it is seen through the
# trees, short enough that ten of them spread over the map are not all audible
# at once.
ATT_CREATURE = AttenuationProfile("A_Att_Creature", 150.0, 3850.0)
# 15 m. Footsteps, the dry click and the reload clack: small mechanical noises
# that in the real world do not reach the next clearing.
ATT_FOLEY = AttenuationProfile("A_Att_Foley", 100.0, 1400.0)
ATTENUATIONS = (ATT_GUNFIRE, ATT_CREATURE, ATT_FOLEY)

# Which sound gets which, and the only table that says so. Every sound in the
# game is a WORLD sound -- something in the level made it, at a place -- so
# every one is spatialised. There is no 2D exception to make: the HUD is drawn
# with DrawText and DrawTexture and is silent, there are no menu clicks, and
# the one sound that might conventionally stay flat, the player's own weapon,
# is a third-person weapon in a third-person game -- it is visibly out there in
# the world at the end of the player's arms, and the muzzle is ~1.5 m from the
# listener, where the gunfire curve is still 1.0 anyway.
#
# The player's own FOOTSTEPS are the judgement call. They share the component
# and therefore the profile with the wanderers', which means they attenuate
# too; at the third-person camera's ~3 m that costs a little volume the player
# did not ask to lose. Kept spatialised regardless, because the alternative is
# a second non-attenuated footstep path whose only purpose is to be wrong about
# where the player's feet are, and because a step that pans as you turn is the
# cheapest cue in the game that the audio is placed at all.
SOUND_ATTENUATION = dict(
    [(n, ATT_GUNFIRE) for n in GUNSHOT_NAMES]
    + [(n, ATT_FOLEY) for n in HANDLING_NAMES + FOOTSTEP_NAMES]
    + [(n, ATT_CREATURE) for n in MELEE_HIT_NAMES + CREATURE_VOICE_NAMES])

# ─── What the player is wearing ──────────────────────────────────────────────
#
# The player used to be SKM_Quinn_Simple and nothing else could be said about
# it: the mesh, the ready poses, the grip socket and the bone the aim pose is
# blended from were four literals scattered through this file that all happened
# to describe the Epic mannequin. They are one record now, because changing the
# player's body means changing all four together or not at all.
#
# ── Why the adventurer is on its own skeleton, and not on SK_Mannequin ──
#
# The obvious integration -- generate a new mesh and bind it to the skeleton
# everything here already depends on -- is not reachable from this toolchain,
# and it was probed before a credit was spent rather than after:
#
#   * Meshy's rigging endpoint takes an input mesh and a height and nothing
#     else. There is no skeleton-convention parameter, so what comes back is
#     always its own 24-bone Mixamo-named rig (measured: Hips, Spine02..Spine,
#     LeftArm..LeftHand, neck, Head -- no fingers, no twist bones).
#   * Re-binding that mesh at import time is not a matter of asking: the FBX
#     importer merges the incoming bone tree into the supplied skeleton, and
#     24 differently-named bones do not merge into SK_Mannequin's 161.
#   * And UE 5.8 exposes no skin transfer to Python. IKRetargetBatchOperation
#     retargets *animation* assets only; IKRetargeterController has no mesh
#     export, so the editor's "retarget skeletal mesh" button has no scripted
#     equivalent. A project with no C++ module cannot reach the C++ that does it.
#
# So the animation moves to the mesh instead of the mesh to the skeleton --
# exactly what the monsters already do, through build_retarget.py -- and the
# three things that made that sound dangerous turn out to be rig-agnostic
# already: hit_zones() derives its tables from whatever mesh the character is
# wearing, the ragdoll is SetAllBodiesSimulatePhysics on whatever physics asset
# that mesh carries, and the locomotion is a retargeted copy of ABP_Unarmed
# that fix_retargeted_abp() has already re-pointed at the new spine.
#
# What is genuinely lost is finger articulation: a 24-bone rig cannot close a
# fist, so the adventurer's hand holds its weapon open rather than gripped.
# That is a known cost of the only route that exists, recorded here rather than
# discovered later.
@dataclasses.dataclass(frozen=True)
class PlayerSkin:
    """The player's body: mesh, animation, and where a weapon sits in it."""

    mesh: str
    anim_bp: str
    # Attachment point for the held weapon. A socket where the rig has one; a
    # BONE name otherwise -- AttachToComponent resolves either out of the same
    # namespace, and Python cannot mint a socket (SkeletalMeshSocket's
    # SocketName and BoneName are both read-only, checked).
    grip: str
    aim_rifle: str
    aim_pistol: str
    # Mesh component transform inside the actor. The template's own numbers;
    # they are a property of a 1.8 m humanoid standing in an 88 cm capsule
    # facing +X, not of the mannequin, which is why the Meshy skin reuses them.
    mesh_z: float = -89.0
    mesh_yaw: float = 270.0


SKIN_QUINN = PlayerSkin(
    mesh="/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple",
    anim_bp="/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed",
    grip="HandGrip_R",
    aim_rifle="/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS",
    aim_pistol="/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS",
)

# Built by Scripts/asset_pipeline: fetch_monsters.py -> import_characters.py ->
# build_retarget.py. Every path here is under /Game/Sourced, which is
# git-ignored, so a checkout that has never run the pipeline has none of it and
# falls back to the mannequin above -- the same bargain build_npc_blueprints.py
# strikes, and for the same reason: a player who looks wrong is a far better
# failure than a build that stops.
ADVENTURER = "Adventurer01"
SKIN_ADVENTURER = PlayerSkin(
    mesh=f"/Game/Sourced/Characters/SKM_{ADVENTURER}/SKM_{ADVENTURER}",
    anim_bp=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/A_{ADVENTURER}_ABP_Unarmed",
    grip="RightHand",
    aim_rifle=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/"
              f"A_{ADVENTURER}_MF_Rifle_Idle_ADS",
    aim_pistol=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/"
               f"A_{ADVENTURER}_MF_Pistol_Idle_ADS",
)


def player_skin():
    """The adventurer if the pipeline has produced all of it, else the mannequin.

    All four assets or none: a skin resolved piecemeal is the failure that
    cannot be read off a log -- the adventurer's mesh wearing the mannequin's
    anim BP compiles, runs, and stands in the reference pose forever.
    """
    eas = _assets()
    want = (SKIN_ADVENTURER.mesh, SKIN_ADVENTURER.anim_bp,
            SKIN_ADVENTURER.aim_rifle, SKIN_ADVENTURER.aim_pistol)
    missing = [p for p in want if not eas.does_asset_exist(p)]
    if not missing:
        return SKIN_ADVENTURER
    if len(missing) < len(want):
        _log(f"note: the adventurer skin is incomplete ({len(missing)} of "
             f"{len(want)} assets missing, first {missing[0]}) — wearing the "
             "mannequin. Run Scripts/asset_pipeline to build it.")
    return SKIN_QUINN

CUBE = "/Engine/BasicShapes/Cube"          # 100 cm box
CYLINDER = "/Engine/BasicShapes/Cylinder"  # 100 cm tall, 50 cm radius, axis +Z
SPHERE = "/Engine/BasicShapes/Sphere"      # 100 cm diameter

SOUND_SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "generated", "sounds")

# ─── Tuning ──────────────────────────────────────────────────────────────────

INVENTORY_SIZE = 5

# Polled keys.  1/2/3 and M belong to the graphics menu, so the weapon keys stay
# clear of them.
#
# Every one of them is polled on the weapon component's Tick rather than bound
# as an input action, for the same reason: BP_ThirdPersonCharacter's graph is
# the Enhanced Input template, and adding an IA asset plus an IMC entry is not
# authorable from Python. Sprint lives on the *weapon* component specifically
# because that is the thing that has to refuse to fire while it is held down.
FIRE_KEY = "LeftMouseButton"
AIM_KEY = "RightMouseButton"
SWITCH_KEY = "Q"
DROP_KEY = "G"
PICKUP_KEY = "E"
SPRINT_KEY = "LeftShift"

PICKUP_RADIUS = 250.0      # cm; how close you must be to press E
DROP_FORWARD = 120.0       # cm in front of the player a dropped weapon lands

# --- footsteps ---------------------------------------------------------------
# One component, on the player and on every wanderer, because a footfall is a
# fact about having legs and not about which side you are on.
#
# Driven by DISTANCE TRAVELLED, not by a timer. That is the whole design: a
# timer has to be told how fast its owner is moving and gets it wrong the
# moment anything else changes the speed, and three things already do -- sprint
# (900 vs 600), the per-instance gait variance, and the wendigo's 1.15x. An
# accumulator over ground covered needs to know none of them and cannot
# disagree with any of them; the faster something moves, the sooner it has
# covered a stride.
#
# 160 cm is one footfall of a run at 600 cm/s, which works out at about 3.7
# steps a second. It is a compromise across the speed range -- the same stride
# at a walk is slightly long -- and a compromise is the right answer here,
# because the alternative is a speed-to-stride curve that nobody can hear.
#
# The remainder is CARRIED rather than reset to zero when a step fires, or the
# effective stride would be "160 cm plus however far this frame happened to
# take us", which makes the step rate depend on framerate.
FOOTSTEP_STRIDE_CM = 160.0
# Below this the owner is shuffling against a wall, not walking.
FOOTSTEP_MIN_SPEED_CMS = 40.0
FOOTSTEP_BP_PATH = f"{WEAPON_DIR}/BP_FootstepComponent"

# ─── The combat config ───────────────────────────────────────────────────────
#
# One named structure for the global combat tuning, and it is a Python
# dataclass rather than a UserDefinedStruct or a DataAsset on purpose.
#
# Every number in here is BAKED INTO A GRAPH at build time: the cone scale is a
# SelectFloat pin literal, the recoil recovery speed an FInterpTo pin literal,
# the sensitivity limits FClamp literals in the settings screen. A struct asset
# a designer edited in the editor would have to be *read* at runtime instead --
# an asset load, a null guard and a member read in front of every one of those
# pins, in a project where each of those nodes is placed and wired by hand from
# Python.
#
# And it would not survive being edited. Nothing under Content/ is committed
# (see CLAUDE.md): every asset in this project is derived and is rebuilt from
# these scripts on a fresh clone. An in-editor edit to a generated DataAsset is
# erased the next time the builder runs and was never in the repository to
# begin with -- so "tunable in the editor without re-running Python" is a
# promise this architecture cannot keep, and pretending otherwise would lose
# somebody's tuning pass rather than save them a build.
#
# So tuning combat means editing this object and re-running
# build_weapons_and_combat.py. That is the same workflow as the project's two
# other tuning homes, forest_generator/lighting.py (the time-of-day presets)
# and forest_generator/npc_placement.py (run speed, melee reach) -- and it is
# the one that gets checked, because the verifier reads these fields back out
# of the compiled graphs.
#
# Frozen, so no builder can quietly write a number back into it and leave the
# verifier asserting a value the graph never saw.
#
# PER-WEAPON numbers deliberately do NOT live here. Damage, spread, range, fire
# interval, magazine size and recoil are columns in _weapon_specs(), which is
# what keeps a sixth weapon a row in a table rather than a code change. This is
# the other half: what is true of a fight whatever is being held.
@dataclasses.dataclass(frozen=True)
class CombatConfig:
    """The global, tunable combat parameters -- the one place to change them."""

    # --- what it takes to kill and to die ------------------------------------
    start_health: float = 100.0
    # Where on the body a shot landed. The capsule decides *whether* a pellet
    # hit a character; the physics asset's bodies decide where (see hit_zones).
    # Anything the zones do not name -- neck, clavicles, torso -- is worth 1.0.
    head_multiplier: float = 1.5
    limb_multiplier: float = 0.75

    # --- sprint and stamina --------------------------------------------------
    # The walking speed is NOT here: BeginPlay caches whatever the character's
    # MaxWalkSpeed already is into BaseSpeed and restores that. A literal would
    # silently fight any later change to the character's own default.
    sprint_speed_cms: float = 900.0
    max_stamina: float = 100.0
    # 4 s of sprint from full, a little over 8 s to refill. Deliberately
    # asymmetric: sprint is the escape from a pack that runs at 600 cm/s, so it
    # has to be worth spending and it has to cost something to have spent.
    stamina_drain_per_s: float = 25.0
    stamina_regen_per_s: float = 12.0

    # --- aiming down the sights ----------------------------------------------
    # What ADS does is narrow the camera's field of view and tighten the
    # weapon's cone. The zoom factor is per weapon (AdsZoom on BP_WeaponItem)
    # because the sniper's is a scope and everything else's is a set of irons:
    # 4x against 1.5x is the difference the player is buying when they pick the
    # rifle up. These two are the values that table chooses between.
    #
    # BaseFOV is cached at BeginPlay from whatever the camera already has,
    # exactly as BaseSpeed caches MaxWalkSpeed.
    ads_zoom_irons: float = 1.5
    ads_zoom_scope: float = 4.0
    # The FOV is NOT snapped. FInterpTo at this speed takes about a fifth of a
    # second to arrive, which is short enough to feel instant and long enough
    # that a 4x snap does not read as a teleport. CurrentFOV is stored rather
    # than recomputed because FInterpTo needs its own previous output.
    ads_interp_speed: float = 12.0
    # Aiming is worth something mechanically, not only visually: the cone
    # shrinks to a third. The shotgun's 5 degrees becomes 1.7, which still
    # patterns, and the sniper's 0.2 becomes 0.07, which is academic -- the
    # weapons this matters to are the automatics in the middle.
    ads_spread_scale: float = 0.34
    # And what it costs in mobility: at full ADS the player walks at half
    # speed. Aiming is meant to be a commitment -- the cone is a third as wide
    # and the camera is inside a scope, so the price is that you cannot also
    # be going anywhere.
    #
    # Applied as a fraction of BaseSpeed, never of the CURRENT walk speed: the
    # write runs every frame, so scaling what is already there would compound
    # to a standstill in about a second. And it eases in along the zoom's own
    # curve rather than snapping with the button, for the reason
    # ads_sens_compensation below eases -- except that the interpolant here is
    # normalised by the weapon's own AdsZoom, so full ADS is exactly this
    # number on irons and on the scope alike. The sensitivity one deliberately
    # is NOT normalised, because "a 4x scope slows the mouse more" is wanted
    # and "a 4x scope slows the legs more" is not.
    ads_move_speed_scale: float = 0.50

    # --- mouse sensitivity, and what aiming does to it -----------------------
    # The player's look input is the Enhanced Input template's IA_Look, which
    # lands on AddControllerYawInput / AddControllerPitchInput -- and those
    # still multiply by APlayerController's InputYawScale / InputPitchScale on
    # their way into RotationInput. That pair is marked deprecated in UE5, but
    # the setters are BlueprintCallable and they are the ONLY per-frame handle
    # on look speed that does not require editing BP_ThirdPersonCharacter's
    # input graph, which the Blueprint graph API cannot partially rebuild.
    #
    # Their values are CACHED at BeginPlay rather than written down here, for
    # the same reason as BaseSpeed and BaseFOV. It matters more here than
    # anywhere else: the engine's default pitch scale is NEGATIVE (-2.5), so a
    # literal positive number would silently invert the player's vertical look.
    mouse_sensitivity_default: float = 1.0
    mouse_sensitivity_min: float = 0.20
    mouse_sensitivity_max: float = 3.00
    mouse_sensitivity_step: float = 0.05
    # How much of the zoom aiming gives back in slower mouse movement.
    #
    # Driven off CurrentFOV / BaseFOV, not off a flag, which buys three things
    # for one node: the slowdown is per weapon without anything per weapon
    # being written (a 4x scope slows the mouse more than 1.5x irons because
    # its FOV is narrower), it EASES IN along the same FInterpTo curve the zoom
    # does rather than snapping the instant the button goes down, and letting
    # go restores it by the same curve with no second code path.
    #
    # 1.0 would be full compensation: the crosshair would then cross the same
    # number of PIXELS per centimetre of mouse at any zoom, which at 4x reads
    # as the mouse having gone dead. 0.0 would be none at all, which at 4x
    # throws the crosshair off the far side of the scope. 0.75 is the usual
    # compromise, and works out at 0.75x sensitivity down the irons and 0.44x
    # down the scope.
    ads_sens_compensation: float = 0.75

    # --- recoil --------------------------------------------------------------
    # A shot kicks the view up by the weapon's own RecoilPitch (a column in
    # _weapon_specs(), because how hard a gun kicks is the gun's business) and
    # sideways by a random fraction of it, and the kick is then paid back over
    # the following fraction of a second.
    #
    # Applied by READING AND WRITING THE CONTROL ROTATION, never with
    # AddPitchInput / AddControllerPitchInput. That route multiplies by
    # APlayerController's deprecated InputPitchScale -- which is exactly the
    # handle the mouse-sensitivity setting above drives -- so a player on 0.2
    # sensitivity would get a fifth of the recoil and a player on 3.0 would be
    # thrown at the sky. Recoil is a property of the weapon and must not move
    # when a settings slider does. SetControlRotation bypasses RotationInput
    # entirely, and the engine's own LimitViewPitch re-clamps the result inside
    # ViewPitchMin/Max on the controller's next UpdateRotation, so a kick taken
    # while already looking near-vertical cannot push the camera over the top.
    #
    # The accumulator is RecoilDebt: what has been kicked and not yet given
    # back. Recovery is an FInterpTo of the debt toward zero, so it is fast at
    # first and settles rather than stopping dead.
    recoil_recovery_speed: float = 7.0
    # ...and only this much of each frame's recovery is handed back to the
    # view. The rest of the debt still decays -- the accumulator always returns
    # to zero, so nothing can build up across a magazine -- but 30% of every
    # kick is left in the player's aim for good. That is the difference between
    # a gun and a screen shake: a burst walks up the target and has to be
    # pulled back down, instead of springing exactly home between rounds.
    recoil_recovery_fraction: float = 0.70
    # Aiming down the sights steadies the weapon, conventionally and here. One
    # multiplier over the whole kick, vertical and horizontal together, applied
    # with the same SelectFloat shape the cone uses -- deliberately not a
    # second per-weapon column, because "shouldering a gun steadies it" is a
    # fact about shoulders and not about which gun.
    recoil_ads_scale: float = 0.65
    # The horizontal kick, as a fraction of the vertical, drawn uniformly in
    # [-r, +r] per shot. Pure vertical recoil reads as a mechanism; a little
    # unpredictable sideways is what makes a burst feel like it is fighting
    # back. Kept well under 1 so the climb is still recognisably upward.
    recoil_horizontal_ratio: float = 0.35

    # --- flinching (taking a hit and living) ---------------------------------
    # Anything that takes damage and survives plays a one-second stagger on its
    # upper body, picked by which side the hit came from. See the hit-reaction
    # block below HIT_SLOT for what it is made of and why it is upper body.
    #
    # The cooldown is the load-bearing number of the three. The reaction is
    # triggered by a per-frame "is Health lower than it was last frame" poll, so
    # without one the SMG (one round every 0.09 s) would restart the montage
    # eleven times a second and the target would stand in the first two frames
    # of a flinch forever -- a vibration, not a reaction. 0.45 s is a little
    # over half the clip at the rate below: consecutive hits still re-trigger,
    # visibly, but only after the previous stagger has read.
    hit_react_cooldown_s: float = 0.45
    # Faster than authored. The clips are ~1.0 s of stagger-and-recover, which
    # is a long time to have your chest yanked around in a firefight; 1.4x
    # brings it to ~0.7 s, which still reads and gets the arms back under the
    # player's control sooner.
    hit_react_rate: float = 1.4
    # In and out. Short enough to look like an impact -- a hit that eases in
    # over a quarter of a second reads as a stumble, not a bullet -- and long
    # enough not to pop the chest between two poses in one frame.
    hit_react_blend_s: float = 0.08


COMBAT = CombatConfig()


# --- shotgun ammunition ------------------------------------------------------
# Ammunition lives on BP_WeaponItem, not on the weapon component, because a
# weapon is a droppable actor here: drop a half-empty shotgun, walk away, come
# back and pick it up, and it still has to be half empty. Reserve on the
# component would belong to the player and would survive a gun that did not.
#
# "Starting 20" is read as twenty shells in total, not twenty plus a free
# magazine: five are in the gun and fifteen are spare.
SHOTGUN_MAGAZINE = 5
SHOTGUN_RESERVE = 15
# Enough of a pause that the shotgun is a decision and not a hose -- it now does
# 8 x 18 = 144 damage to a wanderer with 100 HP, so one connected shot is a
# kill and the interval is the whole balance of the weapon.
SHOTGUN_FIRE_INTERVAL = 0.85
# Reload is not a state machine and not a montage: it pushes NextFireTime out by
# this much, which is exactly what "cannot shoot for 1.6 s" means, and it costs
# three nodes instead of a timer, an interrupt rule and an is-reloading flag.
SHOTGUN_RELOAD_SECONDS = 1.6
# The pistol is the fallback weapon and keeps infinite ammo; it still gets an
# interval, because without one it fires once per frame.
PISTOL_FIRE_INTERVAL = 0.18
RELOAD_KEY = "R"

# The seven rebindable actions, in the order the settings screen lists them and
# -- more importantly -- in the order BP_Settings.Binds stores them. That array
# is indexed, not keyed, so this tuple IS the contract between the two builders:
# build_graphics_menu.py imports it and writes Binds[i] for the same i the HUD
# pushes back into the variable named here. Reorder it and every existing save
# on disk silently rebinds itself to the wrong actions.
BIND_VARS = (("KeyFire", FIRE_KEY),
             ("KeyAim", AIM_KEY),
             ("KeySprint", SPRINT_KEY),
             ("KeySwitch", SWITCH_KEY),
             ("KeyDrop", DROP_KEY),
             ("KeyPickup", PICKUP_KEY),
             ("KeyReload", RELOAD_KEY))
# Shells a killed wanderer leaves behind. Two per kill against five spent per
# magazine means the shotgun runs down unless most shots land, which is the
# point of giving it a reserve at all.
AMMO_DROP_SHELLS = 2
AMMO_PICKUP_RADIUS = 200.0   # cm; walked into, not pressed for
AMMO_PICKUP_LIFT = 40.0      # cm above the corpse, so it is not inside the mesh
AMMO_PICKUP_LIFETIME = 120.0 # s before an uncollected drop tidies itself away
AMMO_SPIN_DEG_PER_S = 90.0

# --- the three found weapons -------------------------------------------------
# The shotgun and pistol are the starting loadout and are spawned into the
# player's hands at BeginPlay. These three are not: the only way to get one is
# to kill something that happens to be carrying it, which is what makes the
# 10% a reason to keep fighting rather than a number in a table.
#
# The balance across all five is deliberately one axis: damage per second is
# roughly flat, and what differs is how it is delivered. The SMG spends nine
# rounds to kill a 100 HP wanderer in under a second; the sniper spends one and
# then makes you wait 1.6 s for the next. The shotgun sits between them and
# only at close range, because eight pellets in a 5 degree cone stop all
# landing on one target past about 15 m.
SMG_MAGAZINE, SMG_RESERVE = 30, 90
SMG_FIRE_INTERVAL, SMG_RELOAD_SECONDS = 0.09, 1.9
RIFLE_MAGAZINE, RIFLE_RESERVE = 30, 90
RIFLE_FIRE_INTERVAL, RIFLE_RELOAD_SECONDS = 0.14, 2.1
SNIPER_MAGAZINE, SNIPER_RESERVE = 5, 15
SNIPER_FIRE_INTERVAL, SNIPER_RELOAD_SECONDS = 1.60, 2.6

# Which of the five hold the trigger down. The SMG and the assault rifle do;
# the shotgun, the pistol and the sniper are one shot per click.
#
# This is a property of the weapon and not of the input code, which is the
# whole reason it is expressible at all: the trigger is polled two ways every
# frame -- tapped and held -- and the weapon decides which of the two it
# answers to. Nothing branches on a weapon's name to find out.
#
# Note what automatic fire does NOT need: a timer, a "firing" state, or a
# repeating event. FireInterval and NextFireTime already gate the rate, and
# they were already being consulted on every frame the trigger was down. All
# the automatics change is whether a held button still counts as a pull.
AUTO_DISPLAYS = ("SMG", "Rifle")

# One kill in ten leaves a gun. Rolled once per counted kill, then a second
# uniform draw picks which of the three -- so each individual weapon is a
# 1-in-30 drop and a player who wants a specific one has to keep going.
#
# Rolled on exactly the same arm as the shells, which means DamagedByPlayer
# guards it too: a wanderer the terrain swallowed has not been killed, and the
# safety net must not be a weapon dispenser.
GUN_DROP_CHANCE = 0.10
GUN_DROP_FORWARD = 70.0   # cm; clear of the shells, which land on the corpse

# --- debug mode --------------------------------------------------------------
# One flag on the GameMode, toggled from the graphics menu, that turns the
# developer overlays on and off: the pellet tracers drawn from the muzzle and
# the wanderer's number beside its health bar. Off by default -- they are both
# instrumentation, and instrumentation is not what the game looks like.
DEBUG_MODE_VAR = "DebugMode"

# --- dying: the collapse, and how long a corpse lies there -------------------
# EVERYTHING that dies in this game collapses the same way, and it collapses
# physically rather than by playing a clip. There is no death animation in this
# project and no honest way to make one here:
#
#   * the creatures come from Meshy, whose rigging step generates a walk and a
#     run and nothing else -- there is no clip in assets/cache/meshy that ends
#     on the ground, and none among the 21 retargeted per creature;
#   * Epic's own MM_Death_* set, which the player used to play, is six
#     one-second STAGGERS. Measured off the assets: every one of them ends with
#     the pelvis at 83-88 cm and both feet on the floor, i.e. still standing,
#     having travelled 1.5-2 m backwards. They are hit reactions authored to be
#     blended into a ragdoll, not collapses.
#
# That measurement is the whole diagnosis of "he gets up right away": the
# player staggered for 1.1 s, the dynamic montage blended out, and the
# locomotion state machine underneath it had him standing again well before the
# 2.2 s pause.
#
# A ragdoll needs no asset at all. Every character here already carries a
# physics asset -- PA_Mannequin, SKM_Zombie01_PhysicsAsset,
# SKM_Wendigo01_PhysicsAsset -- and it is not optional: install_hit_zones reads
# the head and limb tables off those bodies, so a rig that could not ragdoll
# could not be shot in the head either. The fall is different every time, it is
# plausible on a slope, and there is nothing to retarget.
#
# SetAllBodiesSimulatePhysics, not SetSimulatePhysics: the latter is not even a
# UFunction on SkeletalMeshComponent (checked -- the node does not exist), and
# on a PrimitiveComponent it would simulate the one root body, which is a
# creature-shaped rigid brick falling over rather than a ragdoll.
RAGDOLL_PROFILE = "Ragdoll"
# How long a corpse lies where it fell. Long enough that a firefight leaves a
# visible history of itself, short enough that a long session does not end up
# rendering a hundred skeletal meshes nobody is looking at.
CORPSE_SECONDS = 60.0
# How long the player's body is left falling before the game pauses and the
# menu opens. The pause stops physics too, so this is also how long the ragdoll
# gets to settle: pausing early freezes the player mid-topple, which reads as a
# hang rather than as a death.
DEATH_PAUSE_SECONDS = 2.2
# The slot the death montage used to play into. Kept, and still spliced into
# ABP_Unarmed by patch_anim_blueprint, because it is the only full-body slot
# either character has and the next thing that needs to override the legs will
# want it -- DefaultSlot is filtered to the upper body so the aim pose leaves
# the legs walking.
FULL_BODY_SLOT = "FullBodySlot"

# --- flinching: the hit reaction ---------------------------------------------
# A survivor reacts; a corpse ragdolls. The two are deliberately different
# mechanisms and they cannot both be wanted at once, which is why the reaction
# hangs off the **False** arm of the death branch in BP_HealthComponent's Tick:
# "Health went down since last frame AND it is still above zero".
#
# WHY A POLL AND NOT A CALL. Damage is written straight onto Health by whoever
# did it -- the weapon component's pellet loop, the wanderers' melee, the world
# floor. Triggering the reaction at each of those sites means each of them can
# forget, and the next damage source that appears starts out silent. Comparing
# Health against PrevHealth once per Tick is one place that cannot be forgotten
# and does not care where the damage came from. It also gets "and survived" for
# free: the frame a target dies, the death branch is taken and the reaction arm
# is never reached, so nothing can flinch and ragdoll in the same frame.
#
# WHY ITS OWN SLOT, UPPER BODY. Three montages want the chest at various times
# and playing two into one slot stops the first:
#
#   DefaultSlot    the aim pose, a 9999-loop dynamic montage the player holds
#                  for as long as a weapon is equipped, and the wanderers'
#                  attack swing. Reacting into it would kill the ready pose and
#                  leave the player holding a rifle in the locomotion pose until
#                  the next equip -- "does not break aiming" ruled it out.
#   FullBodySlot   free, and full body. A one-second full-body stagger stops the
#                  legs: the player loses control of a running character mid
#                  firefight and a charging wanderer freezes in the open.
#   HitSlot        added here, downstream of the aim blend and filtered to the
#                  same spine root, so a reaction overrides the ready pose (and
#                  the swing) for its duration and blends back out of it, while
#                  the legs never stop.
#
# A slot with nothing playing passes its input straight through, and the second
# layered blend's two inputs are then the same pose, so this costs nothing until
# something is actually hit.
#
# WHAT A SEPARATE SLOT DOES NOT BUY, and this is the one surprise in the whole
# feature: montages are stopped per GROUP, not per slot. Every slot belongs to
# the skeleton's default group unless USkeleton::SetSlotGroupName says
# otherwise, and UE 5.8 exposes none of that to Python -- `slot_group_names`,
# `slot_to_group_name_map` and `slot_anim_tracks` all fail as editor properties
# on a USkeleton, and the class has no slot or group methods at all (measured).
# So a flinch in HitSlot DOES stop the ready pose in DefaultSlot. What the
# separate slot buys is the POSE -- the reaction lands on top of the aim pose
# for its second instead of replacing the whole upper body for good -- and
# _author_ready_pose_keepalive buys back the rest by restarting the ready pose
# on the first frame after the stagger.
HIT_SLOT = "HitSlot"
# The six clips, and the ORDER IS THE CONTRACT: the graph picks a direction,
# turns it into a base index into this array, and adds a random offset within
# the run of Fronts. Front first because it is the common case and the one Epic
# authored three of.
#
# They are Epic's MM_Death_* set and they are not deaths -- see the dying block
# above, and HIT_SOURCES in Scripts/asset_pipeline/build_retarget.py, which
# retargets all six onto every creature. Every one is ~1 s long and ends with
# the pelvis at 83-88 cm and both feet on the floor. Rejected for death for
# exactly the reason they are right here.
# Imported, not written out again: the wanderers' AI controllers build their
# own per-creature paths from the same tuple (npc_placement._creature), and two
# copies of an ORDER that three files index by position is the drift this
# project's one-table rule exists to prevent.
HIT_REACTION_CLIPS = NPC_HIT_REACTION_CLIPS
# (base index, count) per direction, derived from the tuple above rather than
# written twice -- the graph bakes these numbers into pin literals, so a
# reordering that only changed the tuple would otherwise play a Left clip for a
# hit in the back and nothing would say so.
HIT_DIR_FRONT = (0, 3)
HIT_DIR_BACK = (3, 1)
HIT_DIR_LEFT = (4, 1)
HIT_DIR_RIGHT = (5, 1)
# Where the six live once retargeted, and the fallback for a checkout with no
# /Game/Sourced. The creature layout mirrors npc_placement._creature and
# build_retarget.anim_dir; it is derived from the mesh's own name at build time
# (see hit_reactions), never written out per creature.
HIT_ANIM_ROOT = "/Game/Sourced/Characters/Anims"
HIT_ANIM_FALLBACK_DIR = "/Game/Characters/Mannequins/Anims/Death"
# The clips this character can play, on the component, filled per character by
# install_hit_reactions from that character's OWN skeleton -- exactly as the
# hit-zone tables are. An AnimSequence belongs to one skeleton, so a shared
# default here could only ever be right for one body.
HIT_REACTIONS_VAR = "HitReactions"
# Unit vector, world space, pointing from the victim TOWARD whatever hit it.
# Written by the pellet loop (off the impact normal, which already points back
# up the shot) and by a wanderer's punch; read once, by the direction pick.
# Zero is a legal value and means "nobody said" -- the pick is written so that
# it falls to Front, which is the reaction that has three clips.
LAST_HIT_FROM_VAR = "LastHitFrom"
# What Health was on the previous Tick. The whole trigger.
PREV_HEALTH_VAR = "PrevHealth"
# When the next reaction may start, in world seconds. Same shape as the
# wanderers' NextVoiceTime and the weapons' NextFireTime: a deadline, not a
# timer, so nothing has to tick it down.
NEXT_REACT_VAR = "NextReactTime"
# The index the direction pick chose, stored rather than wired because it is
# written on four different exec arms and read by one.
REACT_INDEX_VAR = "ReactIndex"
# TEMPORARY INSTRUMENTATION, and it must stay False.
#
# "A gate that never opens looks identical to one that works": a -game run in
# which nothing flinched and a -game run in which the reaction silently never
# fired produce the same log. Flipping this to True adds one PrintWarning to
# the end of the reaction chain, naming the actor and the clip index, so the
# path can be proved to run -- and it was, see the hit-reaction section of
# CLAUDE.md for the numbers. It is then flipped back and the builder re-run,
# which is what removes the node; verify_weapons_and_combat.py asserts BOTH
# that this is False and that no node in the built graph prints the token, so
# a probe left switched on cannot pass.
HIT_REACT_PROBE = False
HIT_REACT_PROBE_PREFIX = "[HIT-REACT] "
# The other half of the same probe: the ready pose putting itself back.
POSE_BACK_PROBE_PREFIX = "[POSE-BACK] "

# Pellet tracers drawn in the world for this many seconds, in debug mode only.
# They are the only way to see *where* a shot went -- sound and blood tell you a
# shot happened and that it connected, but not that it missed high -- which is
# exactly why they are instrumentation and not part of the game.
#
# Drawn with an explicit DrawDebugLine rather than with the trace node's own
# DrawDebugType: that pin is an enum literal, and an enum pin cannot be driven
# by a variable, so "sometimes" is not expressible there at all.
TRACE_DEBUG_SECONDS = 1.5

# NPC respawn: a replacement wanderer appears in the same 75-100 m band the
# level generator spawns the pack in -- but measured from wherever the PLAYER is
# standing at that moment, not from a fixed point. Anchoring it to the dead
# NPC's own spawn point (what this used to do) made the rule decay: the player
# walks 300 m, kills something, and its replacement appears 300 m behind them,
# or worse, right on top of them when they have walked toward the spawn.
#
# The band's far edge can fall outside the navigable island, and the point is
# built from the PLAYER's Z, which is not the ground height at a spot 90 m away.
# So the point is a *request*, never a spawn location: it is projected onto the
# navmesh first, and only the projected result is ever spawned at. See
# _author_respawn_point for what happens when the projection fails.
RESPAWN_BAND = (NPC_SPAWN_MIN_DISTANCE_CM, NPC_SPAWN_MAX_DISTANCE_CM)
RESPAWN_NAV_SNAP = NPC_RESPAWN_NAV_SNAP_CM
# Search box for that projection, half-extents in cm. Deliberately wide in XY:
# a band point that overshoots the navigable island by 20 m snaps back onto its
# edge rather than failing, which is the common case on a map whose usable
# radius (80 m on a 200 m map) is narrower than the band. Deliberately tall in
# Z: the request carries the player's height, and the terrain it has to land on
# ranges from a -2 m hollow to a 40 m edge ramp.
RESPAWN_PROJECT_EXTENT = (3000.0, 3000.0, 10000.0)
# A navmesh point is the ground; a Character's origin is its capsule centre.
RESPAWN_LIFT = NPC_CAPSULE_HALF_HEIGHT_CM
# ...except a navmesh point is NOT reliably the ground. Recast voxelises the
# terrain (cell height, then polygon simplification), so on a slope its polygon
# can sit well below the mesh surface -- measured at up to 86 cm low over 1847
# respawns, with 3% of them landing a capsule less than half-seated and 0.2%
# more than half buried. A capsule that starts inside the terrain depenetrates,
# and a thin one-sided surface is exactly what it pops *through*: that is the
# "some still fall through" case. So the chosen point's XY is kept and its Z is
# re-derived by tracing onto the real collision geometry.
#
# The trace starts only 2 m up on purpose. A trace from far overhead would hit a
# tree canopy and seat the wanderer in the branches; 2 m clears the worst
# measured burial and stays under anything growing above.
RESPAWN_TRACE_UP = 200.0
RESPAWN_TRACE_DOWN = 500.0
# The floor of the world. The terrain bottoms out at about -185 cm and the nav
# volume at -385, so anything under -1000 cm is not standing on anything and
# never will be.
#
# This is now BOTH the NPC safety net and the player's death from walking off
# the map, which are the same measurement and deliberately the same number.
# The navigable island is a disc of radius 85 m inside a 200 m square of
# terrain, and the terrain itself simply ends: walk far enough and there is
# nothing under the capsule. Before this, the player fell for the rest of the
# session -- no floor, no KillZ, no bottom. A Character in freefall never
# stops, and the game has no way to notice, because "still falling" and
# "standing still" look identical to everything that is watching.
#
# Routing it into Health = 0 rather than into a teleport or a Destroy is what
# makes it cost nothing: the death path, the animation, the pause and the
# restart menu all already exist and all already run at 0 HP.
WORLD_FLOOR_Z = -1000.0

# Every wanderer gets a number, handed out in spawn order and shown beside its
# health bar, so a fall-through seen on screen can be matched to the exact
# spawn location in the log. The counter has to live somewhere world-scoped and
# Blueprints have no statics -- the GameMode is the project's existing wiring
# point (it already carries HUDClass), one instance per session, and it outlives
# every wanderer.
SPAWN_COUNT_VAR = "NpcSpawnCount"
NPC_ID_VAR = "NpcId"
# Two more numbers on the same GameMode, for the same reason: they have to
# outlive every wanderer and every one of the player's own components.
# NpcKillCount is what the HUD counts in the corner and what the death menu
# quotes; PlayerDead is the one flag the menu is drawn from.
KILL_COUNT_VAR = "NpcKillCount"
PLAYER_DEAD_VAR = "PlayerDead"
# Set on a health component by whatever hurt it. The HUD shows a wanderer's bar
# only for a few seconds after LastDamageTime, and only a death with
# DamagedByPlayer true counts as a kill -- the safety net writes Health to 0 for
# a wanderer that fell through the world, and that is not something anyone shot.
LAST_DAMAGE_VAR = "LastDamageTime"
DAMAGED_BY_PLAYER_VAR = "DamagedByPlayer"
# Far enough in the past that nothing is "recently damaged" at level start.
NEVER_DAMAGED = -1000.0
SPAWN_LOG_PREFIX = "[NPC-SPAWN] #"
# Flagged ERROR in the text because Blueprint cannot emit an Error-severity log
# line at all: PrintWarning is the highest the Kismet library offers (there is
# no PrintStringWithSeverity / LogError node), and a real UE_LOG(Error) would
# need a C++ module, which this project does not have. Warning severity at
# least colours it in the Output Log and trips the editor's warning filter; the
# token makes it greppable as an error regardless.
FELL_LOG_PREFIX = "[NPC-FELL] ERROR #"
# The player's own death, written once. Without it a headless -game run has no
# way to say whether the death path ran at all: the menu it opens is on a canvas
# nobody is looking at, and a paused game and a quiet game look identical in a
# log. The score goes in the line because it is the one number worth having
# afterwards.
DEAD_LOG_PREFIX = "[PLAYER-DEAD] killed with "
SPAWNED_AT_VAR = "SpawnedAt"
# How many independent bearings to try before giving up on the band. One is
# enough whenever the navmesh has settled -- measured at runtime, 215 of 220
# band points projected, and the five failures were all in the first frame,
# before any tile existed. A second draw exists for exactly that window, and for
# the tile churn that follows a burst of deaths: it costs nothing when the first
# attempt succeeds, and it keeps a respawn in the band instead of dropping it
# next to the player.
RESPAWN_ATTEMPTS = 2

# --- hit boxes ---------------------------------------------------------------
# A zone is a root bone plus everything under it in the skeleton, so the tables
# are derived from each character's own mesh at build time (hit_zones) and
# never typed out here. What a zone is WORTH is combat tuning and lives on
# COMBAT; which bones are in one is a fact about a rig and lives below.
#
# Zone roots by ROLE, with the candidate bone names each rig might use.
#
# Two skeletons reach this code and they share almost no bone names: Epic's
# mannequin (head, upperarm_l, thigh_l) and Meshy's Mixamo-style creature rig
# (Head, LeftArm, LeftUpLeg). A single hardcoded list meant the creatures could
# not be shot at all -- and because the weapons script is not re-run by a level
# rebuild, that only surfaced the next time somebody ran it, a long way from the
# change that caused it.
#
# Resolved against the bodies the physics asset actually has, so a rig only
# needs to match ONE candidate per role, and a third creature family is a few
# more names here rather than a second copy of this function.
HEAD_CANDIDATES = ("head", "Head")
LIMB_CANDIDATES = (
    ("upperarm_l", "LeftArm"),
    ("upperarm_r", "RightArm"),
    ("thigh_l", "LeftUpLeg"),
    ("thigh_r", "RightUpLeg"),
)
HEAD_BONES_VAR = "HeadBones"
LIMB_BONES_VAR = "LimbBones"
HEAD_MULT_VAR = "HeadMultiplier"
LIMB_MULT_VAR = "LimbMultiplier"
# The bone the current pellet struck, on the weapon component. A variable
# because it is written on three different exec arms (struck a body, threaded
# between the limbs, hit something that is not a Character) and read by one.
HIT_BONE_VAR = "HitBone"
# Debug mode's damage readout, drawn at each impact for as long as the tracer.
DAMAGE_TEXT_COLOR = "(R=1.000000,G=0.850000,B=0.100000,A=1.000000)"


# --- the shooting camera -----------------------------------------------------
# A centred third-person camera puts the character's own back where the reticle
# is, so the crosshair sits on the thing you are least interested in shooting.
# The standard fix is to move the boom over the shoulder: shorter, right, and
# up, which frames the player in the lower-left and leaves the centre of the
# screen clear. The boom shortens as well as offsets -- pushing a 400 cm arm
# sideways swings the camera wide enough that the player's own shoulder crosses
# the centre again when they turn.
CAMERA_ARM = 260.0                  # cm, was 400
CAMERA_SHOULDER = (0.0, 55.0, 60.0) # right and up, in the boom's own space

# How far the camera's aiming ray reaches when it finds nothing: the "point
# arbitrarily far away" the shot is then aimed at. 1 km is past anything in a
# 200 m level, so the ray effectively never runs out before the world does.
AIM_TRACE_RANGE = 100000.0

# The reticle turns red when the muzzle's own line to the aim point stops this
# much short of it -- i.e. something is in front of the barrel that the camera
# cannot see past the player's shoulder. Slack, not zero: the muzzle and the
# camera converge on the same surface from different angles, so their hits are
# never at exactly the same millimetre.
BLOCKED_SLACK = 75.0

# The bone the upper body blend starts at. spine_01 is the lowest spine joint,
# so arms + chest follow the aim pose and the hips and legs keep locomotion.
UPPER_BODY_ROOT = "spine_01"
UPPER_BODY_BLEND_DEPTH = 4
AIM_SLOT = "DefaultSlot"

BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
SDL = unreal.SubobjectDataBlueprintFunctionLibrary


def _log(msg):
    unreal.log_warning(f"[GUN] {msg}")


def _assets():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _subobjects():
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)


# ─── Graph helpers ───────────────────────────────────────────────────────────
# Duplicated from build_graphics_menu.py on purpose: every builder in Scripts/
# has to run standalone under -ExecutePythonScript, which imports no package.

def _node(ed, function_path):
    """add_call_function_node, but loud when the path does not resolve.

    An unresolvable path yields a *pinless* node rather than None, and the
    failure then surfaces much later as "pin 'self' not found on ''".
    """
    n = ed.add_call_function_node(function_path)
    if not n or not BEL.list_all_pins(n):
        raise RuntimeError(f"{function_path} is not a Blueprint-callable function")
    return n


def _palette(ed, name, x=0.0, y=0.0):
    n = ed.create_node_from_name(name, unreal.Vector2D(float(x), float(y)), [])
    if not n:
        raise RuntimeError(f"palette node {name!r} could not be created")
    return n


def _pin(node, name, is_input=True):
    p = (BEL.find_input_pin(node, name) if is_input
         else BEL.find_output_pin(node, name))
    if not p or not p.is_valid():
        raise RuntimeError(f"pin {name!r} ({'in' if is_input else 'out'}) not found; "
                           f"node has {_pin_names(node)}")
    return p


def _pin_names(node):
    return ([str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(node)],
            [str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(node)])


def _loose_pin(node, wanted, is_input=True):
    """Find a pin ignoring spaces and case.

    Macro nodes name their pins "First Index" / "Loop Body", and whether the
    space is there is not something to rely on.
    """
    key = wanted.replace(" ", "").lower()
    for p in (BEL.list_input_pins(node) if is_input else BEL.list_output_pins(node)):
        if str(PIN.get_pin_name(p)).replace(" ", "").lower() == key:
            return p
    raise RuntimeError(f"no pin like {wanted!r} on node; has {_pin_names(node)}")


def _connect(a, b):
    if not a.try_create_connection(b):
        raise RuntimeError("could not connect pins")


def _set(node, name, value):
    """Set a pin's literal, and prove it landed.

    set_pin_value's return is not a usable signal: it is False when the set
    genuinely failed *and* when the value already equalled the pin's default.
    Reading the pin back is. A pin that silently stayed empty compiles as zero,
    which is how a 1 km aiming ray quietly became a 0 cm one -- and the shape of
    the graph looked perfect the whole time.
    """
    pin = _pin(node, name)
    pin.set_pin_value(str(value))
    got = str(PIN.get_pin_value(pin))
    if not _literal_matches(got, value):
        raise RuntimeError(f"pin {name!r} would not take {value!r} — it reads "
                           f"back as {got!r} (struct pins reject every format; "
                           "build the constant as a node instead)")


def _literal_matches(got, want):
    want = str(want)
    if got == want:
        return True
    try:
        # An empty numeric pin *is* zero -- the compiler reads a blank literal
        # as 0 -- so setting a pin to zero and reading back "" is a real match,
        # not the silent failure this guard is looking for.
        return abs(float(got or 0.0) - float(want)) < 1e-6
    except ValueError:
        pass
    # Enum literals read back namespaced (EDrawDebugTrace::ForDuration), and
    # bools read back lower-cased.
    return got.lower() == want.lower() or got.endswith(f"::{want}")


def _at(node, x, y):
    BEL.set_node_pos(node, unreal.IntPoint(int(x), int(y)))
    return node


def _create_blueprint(path, parent_class):
    eas = _assets()
    if eas.does_asset_exist(path):
        existing = eas.load_asset(path)
        if existing:
            return existing
    package_path, asset_name = path.rsplit("/", 1)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, package_path, unreal.Blueprint, factory)
    if not bp:
        raise RuntimeError(f"could not create Blueprint {path}")
    return bp


def _float_type():
    """The pin type for a Blueprint float.

    NOT get_basic_type_by_name("float") -- that name is not recognised and the
    library silently falls back to **int**, logging only
    `Primitive type: float not recognized, defaulting to int`. "double" does the
    same. UE 5 calls the Blueprint float type "real", and it is the only spelling
    that produces a float property. Integral defaults like 100.0 or 4000.0 hide
    the bug completely, so it surfaces only once something needs a fraction.
    """
    return BEL.get_basic_type_by_name("real")


def _declare(ed, name, pin_type):
    """Re-declare a member variable so a type change in this file actually lands."""
    ed.remove_member_variable(name)
    if not ed.add_member_variable(name, pin_type):
        raise RuntimeError(f"could not declare {name}")


def _must_load(path):
    """load_asset, but a miss is an error rather than a None.

    _same() compares a read-back default against what was written, and None
    against None is equal -- so a weapon whose FireSound path was misspelt
    would build, apply, verify and ship in silence, and the only symptom would
    be a gun that makes no noise. Every asset reference written as a default
    goes through here.
    """
    asset = _assets().load_asset(path)
    if not asset:
        raise RuntimeError(f"could not load {path}")
    return asset


def _same(a, b):
    """Compare a read-back default with what was written.

    str() on a UE struct embeds its address, so two identical Vectors never
    compare equal that way -- to_tuple() is the field-wise view. Objects compare
    by path, since the read-back is a different wrapper around the same asset.
    An array comes back as unreal.Array, which is not a list and whose repr is
    an address too, so it is compared element-wise by this same function.
    """
    if isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(b, bool):
        return bool(a) == b
    if isinstance(b, float):
        return abs(float(a) - b) < 1e-6
    if isinstance(b, int):
        return int(a) == b
    if hasattr(b, "get_path_name"):
        return a is not None and a.get_path_name() == b.get_path_name()
    if isinstance(b, unreal.Key):
        # BEFORE the to_tuple arm, and that order is the whole point: FKey
        # exposes no struct fields to Python, so to_tuple() is () for every key
        # and comparing two of them that way passes unconditionally. Python's ==
        # on the wrapper is identity, which fails unconditionally. export_text()
        # is the only view that answers the question -- and it is the same bare
        # key name a pin literal uses.
        return a is not None and a.export_text() == b.export_text()
    if hasattr(b, "to_tuple"):
        return (a is not None and hasattr(a, "to_tuple")
                and all(abs(x - y) < 1e-4 for x, y in zip(a.to_tuple(), b.to_tuple())))
    return str(a) == str(b)


def _apply_defaults(bp, defaults):
    """Write variable defaults onto the CDO, because add_member_variable cannot.

    ``add_member_variable(name, type, "100.0")`` returns True, and then the
    compiler logs `Can't parse default value '100.0'` and leaves the property at
    zero -- a default that reads as set everywhere except where it matters. UE
    5.8 exposes no Python API for a *member* variable's default (only
    set_local_variable_default_value, for locals), so the value is written to
    the compiled class's default object and baked in by recompiling.

    The read-back is the point: a weapon that silently does 0 damage, or a
    health component that starts dead, looks exactly like a working one until
    something shoots at it.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        cdo.set_editor_property(name, value)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{bp.get_name()} failed to recompile after defaults")
    _assets().save_loaded_asset(bp)
    fresh = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        got = fresh.get_editor_property(name)
        if not _same(got, value):
            raise RuntimeError(f"default for {name} did not stick: {got!r} != {value!r}")


# ─── Component helpers ───────────────────────────────────────────────────────

def _handles(bp):
    out = []
    for h in _subobjects().k2_gather_subobject_data_for_blueprint(bp):
        data = _subobjects().k2_find_subobject_data_from_handle(h)
        if not data:
            continue
        out.append((h, str(SDL.get_variable_name(data))))
    return out


def _find_handle(bp, name):
    for h, var in _handles(bp):
        if var == name:
            return h
    return None


def _root_handle(bp):
    handles = _subobjects().k2_gather_subobject_data_for_blueprint(bp)
    if not handles:
        raise RuntimeError("blueprint has no subobject root")
    return handles[0]


def _drop_components(bp, names):
    """Delete each named component *and everything hanging off it*.

    Deleting the root alone is not enough. delete_subobject does not cascade,
    and the orphans it leaves behind come back on the next run under generated
    names (StaticMesh7, StaticMesh13, ...) which then hold the names the real
    parts want -- so rename_subobject quietly fails and the actor accumulates a
    second, nameless copy of the weapon on every run.
    """
    sds = _subobjects()
    targets = set(names)
    # One delete per gather: every handle in a batch goes stale as soon as the
    # first of them is removed, and reusing one trips an ensure inside
    # USimpleConstructionScript::RemoveNodeAndPromoteChildren.
    for _ in range(200):
        entries = []
        for h in sds.k2_gather_subobject_data_for_blueprint(bp):
            data = sds.k2_find_subobject_data_from_handle(h)
            if not data:
                continue
            parent = SDL.get_parent_handle(data)
            parent_data = (sds.k2_find_subobject_data_from_handle(parent)
                           if parent else None)
            entries.append((str(SDL.get_variable_name(data)),
                            str(SDL.get_variable_name(parent_data))
                            if parent_data else "",
                            h))
        grew = True
        while grew:
            grew = False
            for var, parent, _h in entries:
                if parent in targets and var not in targets:
                    targets.add(var)
                    grew = True
        doomed = [(var, h) for var, parent, h in entries if var in targets]
        if not doomed:
            return
        claimed = {parent for _v, parent, _h in entries}
        leaves = [h for var, h in doomed if var not in claimed]
        sds.delete_subobject(_root_handle(bp), (leaves or [doomed[0][1]])[0], bp)
    raise RuntimeError(f"could not clear components {sorted(targets)}")


def _add_component(bp, parent_handle, cls, name):
    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", parent_handle)
    params.set_editor_property("new_class", cls)
    params.set_editor_property("blueprint_context", bp)
    handle, failure = _subobjects().add_new_subobject(params)
    if failure and str(failure):
        raise RuntimeError(f"could not add {name}: {failure}")
    _subobjects().rename_subobject(handle, name)
    # Renaming onto a name something else already holds fails silently and
    # leaves the generated one, which is how duplicates went unnoticed before.
    got = str(SDL.get_variable_name(
        _subobjects().k2_find_subobject_data_from_handle(handle)))
    if got != name:
        raise RuntimeError(
            f"component came out named {got!r}, not {name!r} -- something stale "
            "is still holding that name")
    return handle


def _component_object(handle):
    return SDL.get_object(_subobjects().k2_find_subobject_data_from_handle(handle))


# ─── Weapon geometry ─────────────────────────────────────────────────────────

def _rotate_vector(rotator, vector):
    try:
        return rotator.rotate_vector(vector)
    except AttributeError:
        return unreal.MathLibrary.greater_greater_vector_rotator(vector, rotator)


def _barrel_rotation():
    """Rotation that turns a Cylinder's +Z axis into the weapon's +X.

    Derived rather than hard-coded: the sign of the required pitch depends on
    UE's rotator handedness, which is easier to test than to argue about.
    """
    for pitch in (-90.0, 90.0):
        r = unreal.Rotator()
        r.pitch = pitch
        if _rotate_vector(r, unreal.Vector(0.0, 0.0, 1.0)).x > 0.9:
            return r
    raise RuntimeError("no pitch maps a cylinder's +Z onto +X")


def _pure_rotation(rotator):
    """A rotation-only Transform, so ComposeTransforms can be used as rotator algebra."""
    return unreal.Transform(location=unreal.Vector(0.0, 0.0, 0.0),
                            rotation=rotator,
                            scale=unreal.Vector(1.0, 1.0, 1.0))


class _BoneGrip:
    """A socket-shaped stand-in for a rig that has no grip socket.

    Python cannot create a SkeletalMeshSocket -- both SocketName and BoneName
    are read-only on it, so there is no way to say which bone a new socket
    hangs off -- and a Meshy rig arrives with none. Attaching to the BONE works
    instead: AttachToComponent resolves a socket name and a bone name out of
    the same namespace, and everything downstream of here only ever asks a
    socket for its bone and its rotation.

    The rotation is identity, and that is not an approximation. _grip_rotation
    *solves* for the transform that puts the barrel on the player's forward in
    a given pose, so whatever frame the hand bone happens to be authored in is
    taken out by the solve. What identity costs is position, not aim: the
    weapon hangs off the wrist joint rather than the middle of the palm.
    """

    def __init__(self, bone):
        self._bone = bone

    def get_editor_property(self, name):
        if name == "bone_name":
            return unreal.Name(self._bone)
        if name == "relative_rotation":
            return unreal.Rotator()
        if name == "relative_location":
            return unreal.Vector()
        raise AttributeError(name)


def _grip_socket():
    """(mesh yaw inside the actor, the grip socket) off the player's mesh."""
    bp = _assets().load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    grip = player_skin().grip
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            skeletal = obj.get_editor_property("skeletal_mesh_asset")
            socket = skeletal.find_socket(grip)
            if not socket:
                # Not an error unless the name is neither a socket nor a bone:
                # then the weapon would attach to the component root and hang
                # in the middle of the player's chest.
                if unreal.Name(grip) not in _mesh_bone_names(skeletal):
                    raise RuntimeError(
                        f"{skeletal.get_name()} has neither a {grip} socket nor "
                        f"a {grip} bone — a weapon could not be put in its hand")
                socket = _BoneGrip(grip)
            return obj.get_editor_property("relative_rotation").yaw, socket
    raise RuntimeError(f"{CHARACTER_BP_PATH} has no SkeletalMeshComponent")


def _mesh_bone_names(skeletal):
    """Every bone of a skeletal mesh, as Names.

    Off the skeleton's reference pose rather than off a spawned component: this
    runs during a headless build, where spawning an actor to ask it a question
    costs a level that then has to be left undirtied.
    """
    skel = skeletal.get_editor_property("skeleton")
    pose = unreal.AnimPoseExtensions.get_reference_pose(skel)
    return list(unreal.AnimPoseExtensions.get_bone_names(pose))


def socket_in_mesh(aim_pose_path):
    """(mesh yaw, HandGrip_R's rotation in mesh space) during a given pose.

    Sampled from the animation, not from a live mesh: a headless editor world
    only ever shows the *reference* pose, and that is not the pose a weapon is
    held in. With the layered blend in mesh-space rotation mode this sample is
    what the game actually uses -- the blended bones keep the ready pose's own
    component-space orientation rather than inheriting the locomotion hips.
    """
    mesh_yaw, socket = _grip_socket()
    anim = _assets().load_asset(aim_pose_path)
    if not anim:
        raise RuntimeError(f"could not load the pose {aim_pose_path}")
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
        anim, 0.0, unreal.AnimPoseEvaluationOptions())
    # AnimPoseSpaces.WORLD means *component* space here -- a pose has no world
    # to be in -- and the mesh's own yaw is what carries that into the actor.
    bone = unreal.AnimPoseExtensions.get_bone_pose(
        pose, socket.get_editor_property("bone_name"), unreal.AnimPoseSpaces.WORLD)
    return mesh_yaw, unreal.MathLibrary.compose_transforms(
        _pure_rotation(socket.get_editor_property("relative_rotation")),
        bone).rotation.rotator()


def socket_pose_axes(aim_pose_path):
    """HandGrip_R's three axes, in the actor's space, during a given pose."""
    mesh_yaw, in_mesh = socket_in_mesh(aim_pose_path)
    return {name: _rotate_vector(_rot(yaw=mesh_yaw), _rotate_vector(in_mesh, vector))
            for name, vector in (("X", unreal.Vector(1.0, 0.0, 0.0)),
                                 ("Y", unreal.Vector(0.0, 1.0, 0.0)),
                                 ("Z", unreal.Vector(0.0, 0.0, 1.0)))}


def _grip_rotation(aim_pose_path):
    """The fixed rotation that seats a weapon in the hand aiming straight ahead.

    Two things had to be understood before this could be one line of maths.

    First, the axis. The Mannequin's HandGrip_R carries the weapon's forward on
    its **+Y**, not its +X. Measured in the actor's space:

        MM_Idle (arms down)   socket +Y = ( 0.07,  0.07, -0.99)  at the floor
        MF_Rifle_Idle_ADS     socket +Y = ( 0.97,  0.14,  0.21)  down the sights
        MF_Pistol_Idle_ADS    socket +Y = ( 0.99,  0.06,  0.14)  down the sights

    A hand at the side points its weapon axis at the floor and a hand in a ready
    pose points it where the player is looking; +X does neither -- in the rifle
    pose it reads 0.94 to the player's *left*.

    Second, the pose to solve against. It is this sampled one only because the
    layered blend runs in mesh-space rotation mode; in local space the arms
    inherit the locomotion hips and land somewhere else entirely.

    So: rotate the weapon's own +X onto whatever socket-space direction *is* the
    player's forward in this pose, keeping the weapon upright. Solving it this
    way rather than as a fixed 90 degree yaw also takes out the few degrees the
    ready poses are authored off-centre -- the rifle pose aims about 8 degrees
    right of the body -- and gives each weapon its own value for free, because
    the rifle hand and the pistol hand are not held at the same angle.
    """
    mesh_yaw, socket = socket_in_mesh(aim_pose_path)
    into_socket = unreal.MathLibrary.invert_transform(
        _pure_rotation(socket)).rotation.rotator()
    # The player's forward and up, as the socket sees them.
    forward_in_mesh = _rotate_vector(_rot(yaw=-mesh_yaw), unreal.Vector(1.0, 0.0, 0.0))
    grip = unreal.MathLibrary.make_rot_from_xz(
        _rotate_vector(into_socket, forward_in_mesh),
        _rotate_vector(into_socket, unreal.Vector(0.0, 0.0, 1.0)))

    barrel = _rotate_vector(
        _rot(yaw=mesh_yaw),
        _rotate_vector(unreal.MathLibrary.compose_transforms(
            _pure_rotation(grip), _pure_rotation(socket)).rotation.rotator(),
            unreal.Vector(1.0, 0.0, 0.0)))
    if barrel.x < 0.999:
        raise RuntimeError(f"{aim_pose_path}: the barrel would point "
                           f"{barrel.to_tuple()}, not straight ahead")
    _log(f"{aim_pose_path.rsplit('/', 1)[-1]}: grip pitch {grip.pitch:.1f}, "
         f"yaw {grip.yaw:.1f}, roll {grip.roll:.1f}")
    return grip


def _rot(pitch=0.0, yaw=0.0, roll=0.0):
    r = unreal.Rotator()
    r.pitch, r.yaw, r.roll = pitch, yaw, roll
    return r


# Each part: (name, mesh, location, rotation, scale, material).
# Local frame: +X is the muzzle direction, +Z is up, origin sits in the fist.
# A Cube is 100 cm, so scale is the size in metres; a Cylinder is 100 cm tall
# with a 50 cm radius, so scale 0.02 gives a 1 cm radius.

def _shotgun_parts():
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (25.0, 0.0, 0.0),   _rot(),          (0.30, 0.055, 0.075),  MAT_METAL),
        ("Barrel",       CYLINDER, (70.0, 0.0, 2.2),   barrel,          (0.024, 0.024, 0.60),  MAT_METAL),
        ("MagTube",      CYLINDER, (66.0, 0.0, -2.6),  barrel,          (0.020, 0.020, 0.52),  MAT_METAL),
        ("Pump",         CUBE,     (55.0, 0.0, -2.6),  _rot(),          (0.20, 0.050, 0.050),  MAT_WOOD),
        ("Stock",        CUBE,     (-8.0, 0.0, -2.5),  _rot(pitch=6.0), (0.34, 0.048, 0.070),  MAT_WOOD),
        ("Grip",         CUBE,     (8.0, 0.0, -6.0),   _rot(pitch=20.0),(0.055, 0.042, 0.085), MAT_WOOD),
        ("TriggerGuard", CUBE,     (14.0, 0.0, -4.5),  _rot(),          (0.070, 0.030, 0.020), MAT_METAL),
    )


def _pistol_parts():
    """Shorter, all-metal, and with the grip raked back under the receiver.

    The silhouette is what sells which weapon is in hand at a glance, so the
    pistol is deliberately a third the shotgun's length with no wood on it.
    """
    barrel = _barrel_rotation()
    return (
        ("Slide",        CUBE,     (14.0, 0.0, 1.5),   _rot(),           (0.17, 0.035, 0.040), MAT_METAL),
        ("Frame",        CUBE,     (10.0, 0.0, -2.0),  _rot(),           (0.14, 0.032, 0.030), MAT_METAL),
        ("Barrel",       CYLINDER, (24.0, 0.0, 1.5),   barrel,           (0.011, 0.011, 0.10), MAT_METAL),
        ("Grip",         CUBE,     (1.0, 0.0, -7.5),   _rot(pitch=15.0), (0.045, 0.036, 0.095), MAT_WOOD),
        ("TriggerGuard", CUBE,     (7.0, 0.0, -4.5),   _rot(),           (0.050, 0.026, 0.016), MAT_METAL),
    )


def _smg_parts():
    """Compact and all-metal, with the magazine hanging straight down.

    The five weapons have to be told apart in a fist at 3 m with no UI, so each
    silhouette commits to one thing. The SMG's is *short* -- barely longer than
    the pistol -- and the vertical box magazine under the receiver is the one
    feature no other weapon here has.
    """
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (20.0, 0.0, 0.0),   _rot(),           (0.24, 0.050, 0.070), MAT_METAL),
        ("Handguard",    CUBE,     (34.0, 0.0, 1.0),   _rot(),           (0.12, 0.045, 0.045), MAT_METAL),
        ("Barrel",       CYLINDER, (44.0, 0.0, 1.5),   barrel,           (0.014, 0.014, 0.22), MAT_METAL),
        ("Magazine",     CUBE,     (14.0, 0.0, -9.0),  _rot(pitch=8.0),  (0.035, 0.030, 0.110), MAT_METAL),
        ("Grip",         CUBE,     (4.0, 0.0, -7.0),   _rot(pitch=18.0), (0.048, 0.038, 0.088), MAT_METAL),
        ("Stock",        CUBE,     (-6.0, 0.0, 0.0),   _rot(),           (0.18, 0.030, 0.030), MAT_METAL),
        ("TriggerGuard", CUBE,     (10.0, 0.0, -4.5),  _rot(),           (0.060, 0.028, 0.018), MAT_METAL),
    )


def _rifle_parts():
    """Long, straight and flat-topped, with a carry handle above the receiver.

    The handle is doing real work: it is the only part above the bore line on
    any weapon but the sniper, and it is what stops the rifle reading as a
    slightly bigger SMG when both are seen from behind the shoulder.
    """
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (26.0, 0.0, 0.0),    _rot(),            (0.30, 0.052, 0.072), MAT_METAL),
        ("Handguard",    CUBE,     (58.0, 0.0, 1.0),    _rot(),            (0.22, 0.048, 0.050), MAT_METAL),
        ("Barrel",       CYLINDER, (86.0, 0.0, 1.8),    barrel,            (0.016, 0.016, 0.34), MAT_METAL),
        ("CarryHandle",  CUBE,     (30.0, 0.0, 6.5),    _rot(),            (0.14, 0.030, 0.020), MAT_METAL),
        ("Magazine",     CUBE,     (18.0, 0.0, -10.0),  _rot(pitch=-12.0), (0.040, 0.032, 0.130), MAT_METAL),
        ("Grip",         CUBE,     (6.0, 0.0, -7.5),    _rot(pitch=20.0),  (0.050, 0.040, 0.090), MAT_METAL),
        ("Stock",        CUBE,     (-12.0, 0.0, -1.0),  _rot(),            (0.30, 0.045, 0.060), MAT_METAL),
        ("TriggerGuard", CUBE,     (13.0, 0.0, -4.5),   _rot(),            (0.065, 0.028, 0.018), MAT_METAL),
    )


def _sniper_parts():
    """The longest of the five, with wood furniture and a scope on rings.

    Wood is shared with the shotgun on purpose -- these are the two slow, heavy
    weapons -- and the scope plus the bolt handle are what separate them at a
    glance. It is also the only weapon whose barrel reaches past 1.4 m, which
    is visible in third person every time the player turns.
    """
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (28.0, 0.0, 0.0),    _rot(),            (0.32, 0.055, 0.075), MAT_METAL),
        ("Barrel",       CYLINDER, (96.0, 0.0, 2.0),    barrel,            (0.018, 0.018, 0.52), MAT_METAL),
        ("Forestock",    CUBE,     (58.0, 0.0, -1.5),   _rot(),            (0.26, 0.050, 0.050), MAT_WOOD),
        ("Stock",        CUBE,     (-14.0, 0.0, -2.0),  _rot(pitch=4.0),   (0.42, 0.050, 0.078), MAT_WOOD),
        ("Scope",        CYLINDER, (34.0, 0.0, 9.0),    barrel,            (0.030, 0.030, 0.30), MAT_METAL),
        ("ScopeMountF",  CUBE,     (22.0, 0.0, 5.5),    _rot(),            (0.020, 0.020, 0.045), MAT_METAL),
        ("ScopeMountR",  CUBE,     (46.0, 0.0, 5.5),    _rot(),            (0.020, 0.020, 0.045), MAT_METAL),
        # Sticking out to the shooter's left in the weapon's own frame, which
        # reads as the bolt handle from the third-person camera behind them.
        ("Bolt",         CYLINDER, (18.0, -4.5, 2.0),   _rot(roll=90.0),   (0.012, 0.012, 0.090), MAT_METAL),
        ("Grip",         CUBE,     (10.0, 0.0, -6.5),   _rot(pitch=18.0),  (0.052, 0.040, 0.085), MAT_WOOD),
        ("TriggerGuard", CUBE,     (16.0, 0.0, -4.5),   _rot(),            (0.070, 0.030, 0.020), MAT_METAL),
    )


# Muzzle tip in the weapon's own space: where the barrel actually ends, so the
# pellet cone starts at the gun rather than inside the player's chest.
SHOTGUN_MUZZLE = (101.0, 0.0, 2.2)
PISTOL_MUZZLE = (30.0, 0.0, 1.5)
SMG_MUZZLE = (56.0, 0.0, 1.5)
RIFLE_MUZZLE = (122.0, 0.0, 1.8)
SNIPER_MUZZLE = (148.0, 0.0, 2.0)


def _weapon_icon(display):
    """The weapon's HUD silhouette, or None if the UI art is not built yet.

    Soft rather than fatal: a clone that has not run build_ui_art.py should
    still get a working game, with an empty slot where the icon goes.
    """
    path = f"{UI_ART_DIR}/{ICON_NAME_FOR(display)}"
    tex = unreal.EditorAssetLibrary.load_asset(path)
    if not tex:
        _log(f"note: {path} missing -- {display} will have no inventory icon. "
             "Run `python3 Scripts/build_ui_art.py` then "
             "Scripts/asset_pipeline/import_ui_art.py")
    return tex


def _weapon_specs():
    """Everything that differs between the two weapons, in one table.

    Each grip is solved against that weapon's own ready pose, so the two differ
    because the poses differ -- not because a fudge factor was added to one of
    them. GripLocation stays at the socket for both: HandGrip_R sits in the fist
    already, and an invented offset is one more number nobody can later explain.

    The ammunition columns are here too rather than branched on DisplayName
    anywhere in the graphs: the firing code asks the weapon whether it uses
    ammo, so a third weapon needs a row in this table and no new nodes. The
    same is true of `automatic`: the tick polls the fire key both ways every
    frame and asks the weapon which answer counts, so making a sixth weapon
    full-auto is a True in this table and nothing else.

    That claim has now been tested. The SMG, the assault rifle and the sniper
    were added as three rows here plus three part tables, and not one node in
    _author_fire, _author_reload or the fire gate changed to accommodate them:
    pellet count, spread, range, interval, magazine and reload time were
    already the parameters those graphs read off Held. The only code the three
    needed is the code for *finding* one, which is a property of the drop and
    not of the weapon.

    DropClasses below is what marks a weapon as findable rather than issued.

    `recoil` is degrees of muzzle climb per shot, and it is a column here for
    the same reason `spread` is -- how hard a gun kicks is a fact about the
    gun. The ordering is the point of the numbers: the two heavy, slow weapons
    kick hardest (sniper 2.4, shotgun 2.2), the assault rifle next (0.85), the
    SMG noticeably less (0.45) and the pistol least (0.30). Read against
    `interval` it is also a rate: the SMG's 0.45 every 0.09 s is five degrees a
    second of raw climb against the rifle's six, so the rifle is the one that
    walks off target under sustained fire while the SMG stays controllable --
    which is the same "wins the fight it is already in" identity its damage
    gives it. The two singles pay their whole kick in one visible jolt and
    then have a second to recover.
    """
    skin = player_skin()
    AIM_RIFLE, AIM_PISTOL = skin.aim_rifle, skin.aim_pistol
    return (
        dict(path=SHOTGUN_BP_PATH, parts=_shotgun_parts(), muzzle=SHOTGUN_MUZZLE,
             display="Shotgun", automatic=False, damage=18.0, pellets=8, spread=5.0, range=4000.0,
             sound=f"{AUDIO_DIR}/A_ShotgunFire", reload_sound=SND_RELOAD_SHOTGUN, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.85, 0.45, 0.10),
             uses_ammo=True, magazine=SHOTGUN_MAGAZINE, reserve=SHOTGUN_RESERVE,
             interval=SHOTGUN_FIRE_INTERVAL, reload_s=SHOTGUN_RELOAD_SECONDS,
             recoil=2.2),
        dict(path=PISTOL_BP_PATH, parts=_pistol_parts(), muzzle=PISTOL_MUZZLE,
             display="Pistol", automatic=False, damage=26.0, pellets=1, spread=1.0, range=6000.0,
             sound=f"{AUDIO_DIR}/A_PistolFire", reload_sound=SND_RELOAD_PISTOL, aim=AIM_PISTOL,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_PISTOL),
             colour=(0.35, 0.65, 0.95),
             uses_ammo=False, magazine=0, reserve=0,
             interval=PISTOL_FIRE_INTERVAL, reload_s=0.0,
             recoil=0.30),
        # 12 x 9 = 108 damage to kill, delivered in 0.81 s. The lowest damage
        # per round of the five and the highest per second, which is the whole
        # identity: it wins a fight it is already in and empties fast.
        dict(path=SMG_BP_PATH, parts=_smg_parts(), muzzle=SMG_MUZZLE,
             display="SMG", automatic=True, damage=12.0, pellets=1, spread=2.6, range=4500.0,
             sound=f"{AUDIO_DIR}/A_SMGFire", reload_sound=SND_RELOAD_RIFLE, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.45, 0.85, 0.35),
             uses_ammo=True, magazine=SMG_MAGAZINE, reserve=SMG_RESERVE,
             interval=SMG_FIRE_INTERVAL, reload_s=SMG_RELOAD_SECONDS,
             recoil=0.45),
        # Five rounds to a kill at 0.14 s apart, accurate to 90 m. The generalist,
        # and the one a player who finds it will simply keep.
        dict(path=RIFLE_BP_PATH, parts=_rifle_parts(), muzzle=RIFLE_MUZZLE,
             display="Rifle", automatic=True, damage=24.0, pellets=1, spread=1.4, range=9000.0,
             sound=f"{AUDIO_DIR}/A_RifleFire", reload_sound=SND_RELOAD_RIFLE, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.70, 0.45, 0.95),
             uses_ammo=True, magazine=RIFLE_MAGAZINE, reserve=RIFLE_RESERVE,
             interval=RIFLE_FIRE_INTERVAL, reload_s=RIFLE_RELOAD_SECONDS,
             recoil=0.85),
        # One shot, one kill: 120 against 100 HP, at 0.2 degrees of spread and
        # 200 m of range -- further than anything in a 200 m forest is visible.
        # The cost is 1.6 s between shots, which against a pack of five that
        # runs at 600 cm/s is the difference between opening at distance and
        # being caught reloading.
        dict(path=SNIPER_BP_PATH, parts=_sniper_parts(), muzzle=SNIPER_MUZZLE,
             display="Sniper", automatic=False, damage=120.0, pellets=1, spread=0.2, range=20000.0,
             sound=f"{AUDIO_DIR}/A_SniperFire", reload_sound=SND_RELOAD_PISTOL, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.95, 0.30, 0.35), ads_zoom=COMBAT.ads_zoom_scope, scoped=True,
             uses_ammo=True, magazine=SNIPER_MAGAZINE, reserve=SNIPER_RESERVE,
             interval=SNIPER_FIRE_INTERVAL, reload_s=SNIPER_RELOAD_SECONDS,
             recoil=2.4),
    )


# Which of the five a killed wanderer can be carrying. The starting loadout is
# excluded by construction: a drop the player already has in slot 0 is not a
# reward, and this list is the only thing that decides.
DROP_DISPLAYS = ("SMG", "Rifle", "Sniper")


# ─── Materials and sounds ────────────────────────────────────────────────────

# Linear base colours. M_Blood is the one worth stating a number for:
# (0.150, 0.014, 0.012) is sRGB #6C2825, a dark desaturated crimson roughly two
# stops under arterial red. Pure (1, 0, 0) -- or the (0.30, 0.005, 0.005) this
# used to be, which is that hue at lower value -- is the single loudest
# "cartoon" cue there is, because nothing in a forest at night is that
# saturated.
BLOOD_BASE_COLOUR = (0.150, 0.014, 0.012)
# Wet, not painted. The specular highlight off a 0.22-rough droplet is what
# actually makes blood readable at night; emissive was the old answer and it is
# the wrong one -- a glowing droplet cannot sit in the scene's lighting, it only
# sits on top of it.
BLOOD_ROUGHNESS = 0.22


def build_materials():
    """Flat constant materials, so the parts read as a gun and not as white boxes.

    Material *instances* of BasicShapeMaterial would be cheaper, but that engine
    material exposes no parameters, so there is nothing to instance.

    Re-authored in place on every run rather than skipped when the asset is
    already there. The old skip meant a changed recipe never landed: the blood
    colour could be edited here, the builder re-run, and the material on disk
    would still be last month's. delete_all_material_expressions clears the
    graph without deleting the asset, so every reference to it survives.
    """
    eas = _assets()
    mel = unreal.MaterialEditingLibrary
    for path, (colour, metallic, roughness, emissive) in (
            (MAT_METAL, ((0.055, 0.058, 0.065), 1.0, 0.32, None)),
            (MAT_WOOD, ((0.115, 0.062, 0.030), 0.0, 0.62, None)),
            # Deliberately NOT emissive -- see BLOOD_BASE_COLOUR.
            (MAT_BLOOD, (BLOOD_BASE_COLOUR, 0.0, BLOOD_ROUGHNESS, None)),
            # Shells on the forest floor, at night, under trees. Emissive
            # because without it a dropped pickup is a black cylinder on black
            # ground and nobody ever finds it -- a gameplay affordance, which
            # is a reason blood does not get to borrow.
            (MAT_BRASS, ((0.52, 0.36, 0.08), 1.0, 0.28, (0.34, 0.22, 0.03)))):
        package_path, name = path.rsplit("/", 1)
        if eas.does_asset_exist(path):
            mat = _must_load(path)
            mel.delete_all_material_expressions(mat)
        else:
            mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                name, package_path, unreal.Material, unreal.MaterialFactoryNew())
        base = mel.create_material_expression(
            mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
        base.set_editor_property("constant", unreal.LinearColor(*colour, 1.0))
        mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
        for value, prop, offset in ((metallic, unreal.MaterialProperty.MP_METALLIC, 160),
                                    (roughness, unreal.MaterialProperty.MP_ROUGHNESS, 300)):
            c = mel.create_material_expression(
                mat, unreal.MaterialExpressionConstant, -400, offset)
            c.set_editor_property("r", value)
            mel.connect_material_property(c, "", prop)
        if emissive:
            e = mel.create_material_expression(
                mat, unreal.MaterialExpressionConstant3Vector, -400, 440)
            e.set_editor_property("constant", unreal.LinearColor(*emissive, 1.0))
            mel.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        # delete_all_material_expressions above leaves the previous run's
        # now-unreferenced nodes behind in the asset; this is what actually
        # removes them, and without it every rebuild grows the graph.
        mel.delete_unused_expressions(mat)
        mel.recompile_material(mat)
        eas.save_loaded_asset(mat)
        _log(f"built {path}")


def build_sound_attenuations():
    """Build the USoundAttenuation assets, one per AttenuationProfile.

    Re-authored in place every run rather than skipped when present: that is
    the lesson build_materials() had to learn the hard way -- a builder that
    leaves an existing asset alone can never change a recipe, and since nothing
    under Content/ is committed, the asset on disk is only ever as good as the
    last run that actually wrote it.

    Returns {name: asset} for apply_attenuation().
    """
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    eas = _assets()
    built = {}
    for profile in ATTENUATIONS:
        if profile.audible_cm > AUDIBLE_LIMIT_CM:
            raise RuntimeError(
                f"{profile.name} would be audible from "
                f"{profile.audible_cm / 100.0:.0f} m, over the "
                f"{AUDIBLE_LIMIT_CM / 100.0:.0f} m ceiling")
        asset = (eas.load_asset(profile.path)
                 if eas.does_asset_exist(profile.path)
                 else tools.create_asset(profile.name, CREATURE_AUDIO_DIR,
                                         unreal.SoundAttenuation,
                                         unreal.SoundAttenuationFactory()))
        if asset is None:
            raise RuntimeError(f"could not create {profile.path}")
        # The struct read back off the asset is a COPY -- the same trap the
        # LayeredBoneBlend node's inner FAnimNode has -- so it is read,
        # changed, and written back wholesale.
        at = asset.get_editor_property("attenuation")
        at.set_editor_property("attenuate", True)
        at.set_editor_property("spatialize", True)
        at.set_editor_property("distance_algorithm",
                               unreal.AttenuationDistanceModel.NATURAL_SOUND)
        at.set_editor_property("attenuation_shape",
                               unreal.AttenuationShape.SPHERE)
        # Only X is read for a sphere; Y and Z are the box and capsule extents.
        at.set_editor_property("attenuation_shape_extents",
                               unreal.Vector(profile.radius_cm, 0.0, 0.0))
        at.set_editor_property("falloff_distance", profile.falloff_cm)
        # Spelled d_b_ and not db_: the UPROPERTY is dBAttenuationAtMax and
        # the Python name is generated one word boundary at a time.
        at.set_editor_property("d_b_attenuation_at_max", ATT_DB_AT_MAX)
        at.set_editor_property(
            "spatialization_algorithm",
            unreal.SoundSpatializationAlgorithm.SPATIALIZATION_DEFAULT)
        at.set_editor_property("attenuate_with_lpf", profile.air_absorption)
        if profile.air_absorption:
            at.set_editor_property("lpf_radius_min", profile.radius_cm)
            at.set_editor_property("lpf_radius_max", profile.audible_cm)
            at.set_editor_property("lpf_frequency_at_min", ATT_LPF_NEAR_HZ)
            at.set_editor_property("lpf_frequency_at_max", ATT_LPF_FAR_HZ)
        asset.set_editor_property("attenuation", at)
        eas.save_loaded_asset(asset)
        built[profile.name] = asset
        _log(f"built {profile.path} "
             f"(full volume to {profile.radius_cm:.0f} cm, silent past "
             f"{profile.audible_cm / 100.0:.0f} m"
             + (", air absorption on)" if profile.air_absorption else ")"))
    return built


def apply_attenuation(attenuations):
    """Point every SoundWave in the two audio folders at its profile.

    On the ASSET, not on the PlaySoundAtLocation nodes. Both would work -- the
    node carries an AttenuationSettings pin that overrides the asset -- but the
    pin has to be wired at every call site, and there are five of those across
    three Blueprints authored by two different builders, so the pin is five
    chances to miss one and the asset is one write per sound.

    It sweeps the FOLDERS rather than SOUND_NAMES + CREATURE_SOUND_NAMES, and
    raises on a wave it has no profile for. That is the check that makes "no
    world sound was left behind" true rather than merely intended: a sound
    added to either tuple, or dropped into the folder by hand, stops the build
    instead of shipping unattenuated.
    """
    eas = _assets()
    orphans, applied = [], {}
    for folder in (AUDIO_DIR, CREATURE_AUDIO_DIR):
        for ref in eas.list_assets(folder, recursive=False):
            asset = eas.load_asset(ref)
            if not isinstance(asset, unreal.SoundWave):
                continue
            profile = SOUND_ATTENUATION.get(asset.get_name())
            if profile is None:
                orphans.append(asset.get_name())
                continue
            asset.set_editor_property("attenuation_settings",
                                      attenuations[profile.name])
            eas.save_loaded_asset(asset)
            applied.setdefault(profile.name, []).append(asset.get_name())
    if orphans:
        raise RuntimeError(
            f"no attenuation profile for {sorted(orphans)} -- add them to "
            f"SOUND_ATTENUATION, or they ship audible from anywhere")
    for name, names in sorted(applied.items()):
        _log(f"{name} -> {len(names)} sound(s): {', '.join(sorted(names))}")
    return applied


def import_sounds():
    """Import the WAVs as SoundWave assets.

    Two folders and two sources. The gunshots are cut from CC0 recordings by
    Scripts/fetch_weapon_sounds.py, which is run by hand rather than from
    main() -- it reaches the network and unpacks 194 MB, which is not something
    an asset build should do on every invocation. The foley and the monster
    voices are synthesised by Scripts/make_creature_sounds.py, which is cheap
    and offline. Both write into assets/generated/sounds; the cut and
    synthesised files are committed, the downloads are not.

    Nothing in /Engine/Content is a usable gunshot -- or footstep, or growl --
    which is why this project supplies its own at all.
    """
    eas = _assets()
    made = []
    groups = ((AUDIO_DIR, SOUND_NAMES, "Scripts/fetch_weapon_sounds.py"),
              (CREATURE_AUDIO_DIR, CREATURE_SOUND_NAMES,
               "Scripts/make_creature_sounds.py"))
    for folder, names, how in groups:
      for name in names:
        dest = f"{folder}/{name}"
        if eas.does_asset_exist(dest):
            made.append(dest)
            continue
        src = os.path.join(SOUND_SRC_DIR, f"{name}.wav")
        if not os.path.isfile(src):
            raise RuntimeError(f"missing {src} -- run {how}")
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", src)
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        if not eas.does_asset_exist(dest):
            raise RuntimeError(f"import produced no asset at {dest}")
        made.append(dest)
        _log(f"imported {dest}")
    return made


# ─── The AnimGraph patch ─────────────────────────────────────────────────────

def _configure_blend(blend):
    """Branch filter, weight and blend space on a LayeredBoneBlend node.

    Everything here lives on the inner FAnimNode struct rather than on the graph
    node, and the struct that comes back from a read is a *copy* -- so it has to
    be read, changed, and written back wholesale.
    """
    bone = unreal.BranchFilter()
    bone.set_editor_property("bone_name", UPPER_BODY_ROOT)
    bone.set_editor_property("blend_depth", UPPER_BODY_BLEND_DEPTH)
    layer = unreal.InputBlendPose()
    layer.set_editor_property("branch_filters", [bone])
    inner = blend.get_editor_property("node")
    inner.set_editor_property("layer_setup", [layer])
    inner.set_editor_property("blend_weights", [1.0])
    inner.set_editor_property("mesh_space_rotation_blend", True)
    blend.set_editor_property("node", inner)
    back = blend.get_editor_property("node")
    if not back.get_editor_property("mesh_space_rotation_blend"):
        raise RuntimeError("the blend stayed in local space — the aim pose would "
                           "inherit the locomotion hips and aim off to one side")


def _slot_name(node):
    """The slot a Slot node plays, as a plain string."""
    return str(node.get_editor_property("node").get_editor_property("slot_name"))


def _name_slot(node, wanted):
    """Rename a Slot node's inner slot, and prove it took.

    The palette entry for a slot node is spelled with the slot's own name
    (``Slot'DefaultSlot'``) and only *registered* names appear there, so a new
    slot cannot be asked for directly. The way round it is the way the editor
    does it anyway: spawn the DefaultSlot entry, rename the node's inner slot,
    and let the compiler register the new name -- UAnimGraphNode_Slot::
    BakeDataDuringCompilation calls Skeleton->RegisterSlotNode on whatever name
    it finds, so one compile is all the registration takes.
    """
    inner = node.get_editor_property("node")
    inner.set_editor_property("slot_name", wanted)
    node.set_editor_property("node", inner)
    if _slot_name(node) != wanted:
        raise RuntimeError(f"the slot kept the name {_slot_name(node)!r}")
    return node


def _anim_nodes(ed, class_name):
    return [n for n in ed.list_all_nodes()
            if n.get_class().get_name() == class_name]


def _slot_node(ed, name):
    """The Slot node playing ``name``, or None."""
    for n in _anim_nodes(ed, "AnimGraphNode_Slot"):
        if _slot_name(n) == name:
            return n
    return None


def _ensure_hit_slot(ed, aim_blend):
    """Splice Slot(HitSlot) and a second layered blend in after the aim blend.

        aim_blend --+--------------------------> LayeredBoneBlend.BasePose --+
                    |                                                        |--> on
                    +--> Slot(HitSlot) --------> LayeredBoneBlend.Blend -----+

    filtered on the same spine root, so a hit reaction reaches the chest, the
    arms and the head and never the legs.

    It has to be a slot of its own rather than DefaultSlot -- see the block at
    HIT_SLOT. The short version: DefaultSlot is occupied for the whole time a
    weapon is held (the ready pose is a 9999-loop dynamic montage) and playing a
    second montage into one slot stops the first, so reacting there would cost
    the player their aim pose permanently.

    Both of the second blend's inputs are the SAME pose whenever nothing is
    playing -- a slot with no montage passes its source straight through -- so
    the whole insertion is a no-op at rest whatever weight it carries.

    Re-running is safe: an existing HitSlot is left wired where it is and only
    its settings are re-applied, so this never stacks a third blend on the
    chain.
    """
    already = _slot_node(ed, HIT_SLOT)
    if already:
        feeds = PIN.list_connected_pins(_pin(already, "Pose", is_input=False))
        if not feeds:
            raise RuntimeError(f"Slot({HIT_SLOT}) is in the graph but wired to "
                               "nothing — refusing to guess how it was meant to go")
        _configure_blend(PIN.get_owning_node(feeds[0]))
        return already

    out = _pin(aim_blend, "Pose", is_input=False)
    downstream = list(PIN.list_connected_pins(out))
    if not downstream:
        raise RuntimeError("the aim blend feeds nothing; graph is not what we expect")

    slot = _name_slot(_at(_palette(ed, f"Animation|Montage|Slot'{AIM_SLOT}'"),
                          -280, 900), HIT_SLOT)
    blend = _at(_palette(ed, "Animation|Blends|Layeredblendperbone"), -20, 900)

    PIN.break_pin_links(out)
    # One pose output legally drives more than one input, so the aim blend
    # reaches both the new blend's base and the slot's source with no cached
    # pose pair in between.
    _connect(out, _pin(blend, "BasePose"))
    _connect(out, _pin(slot, "Source"))
    _connect(_pin(slot, "Pose", is_input=False), _pin(blend, "BlendPoses_0"))
    for pin in downstream:
        _connect(_pin(blend, "Pose", is_input=False), pin)
    _configure_blend(blend)
    return slot


def _ensure_full_body_slot(ed):
    """Insert Slot(FullBodySlot) between the blend and the ControlRig.

        ... -> LayeredBoneBlend -> Slot(FullBodySlot) -> ControlRig -> Root

    A slot with nothing playing passes its input pose straight through, so this
    is free until something plays into it -- and when the death montage does, it
    lands *after* the upper-body blend and therefore replaces the whole body,
    legs included. Playing a death into DefaultSlot instead folds the chest over
    legs that are still standing in the locomotion pose.

    Nothing plays into it today -- the death is a ragdoll and the hit reaction
    is upper body, in HitSlot -- and a slot with nothing playing costs nothing,
    so it stays as the one full-body override either character has.

    See _name_slot for how a slot that is not in the palette gets made at all.
    """
    rigs = _anim_nodes(ed, "AnimGraphNode_ControlRig")
    if len(rigs) != 1:
        raise RuntimeError(f"expected one ControlRig node, found {len(rigs)}")
    rig = rigs[0]

    feeding = PIN.list_connected_pins(_pin(rig, "Source"))
    if not feeding:
        raise RuntimeError("ControlRig.Source is unconnected; graph is not what "
                           "we expect")
    upstream = PIN.get_owning_node(feeding[0])

    if upstream.get_class().get_name() == "AnimGraphNode_Slot":
        # Already inserted by an earlier run: re-apply the name and leave the
        # wiring alone, so re-running never stacks a second slot on the chain.
        return _name_slot(upstream, FULL_BODY_SLOT)

    slot = _name_slot(_at(_palette(ed, f"Animation|Montage|Slot'{AIM_SLOT}'"),
                          -140, 620), FULL_BODY_SLOT)
    PIN.break_pin_links(_pin(rig, "Source"))
    _connect(_pin(upstream, "Pose", is_input=False), _pin(slot, "Source"))
    _connect(_pin(slot, "Pose", is_input=False), _pin(rig, "Source"))
    return slot


def patch_anim_blueprint():
    """Make DefaultSlot upper-body-only in ABP_Unarmed.

    ABP_Unarmed ships as:

        StateMachine(locomotion) -> Slot(DefaultSlot) -> ControlRig -> Root

    so anything played into DefaultSlot replaces the *whole* body and the
    character slides around frozen in the aim pose. This inserts a layered blend
    so the slot only reaches the upper body:

        StateMachine --+-------------------> LayeredBoneBlend.BasePose ---+
                       |                                                  |--> ControlRig
                       +--> Slot(DefaultSlot) -> LayeredBoneBlend.Blend ---+

    with a spine_01 branch filter. Legs keep walking; arms and chest take the
    ready pose.

    The blend is set to **mesh space rotation blending**, and that is the
    difference between a gun that aims where you look and one that does not.
    In the default (local space) mode the aim pose's arms are hung off whatever
    the locomotion pose's hips are doing, so the ready pose loses its own pelvis
    yaw -- measured at runtime, that put the barrel a constant 21 degrees to the
    player's left (body yaw 44.6, gun yaw 23.3, every frame). In mesh space the
    blended bones keep the ready pose's own component-space orientation, so the
    arms aim where they were authored to aim no matter which way the hips are
    turned.

    There are now THREE slots on the chain, in this order, and the order is the
    design:

        StateMachine -> [aim blend: DefaultSlot]     the ready pose, upper body
                     -> [hit blend: HitSlot]         the flinch, upper body
                     -> Slot(FullBodySlot)           nothing, kept for the legs
                     -> ControlRig -> Root

    HitSlot sits downstream of DefaultSlot so a reaction overrides the ready
    pose for its second and blends back into it, rather than replacing it -- see
    _ensure_hit_slot, and the HIT_SLOT block, for why it could not just share
    DefaultSlot.

    Re-running is safe, and re-running after an edit to *this* function is too:
    an existing blend is left wired as it is but its settings are re-applied.
    """
    bp = _assets().load_asset(ABP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {ABP_PATH}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    if not ed:
        raise RuntimeError("ABP_Unarmed has no AnimGraph")

    aim_slot = _slot_node(ed, AIM_SLOT)
    if aim_slot is None:
        raise RuntimeError(f"ABP_Unarmed has no Slot({AIM_SLOT}); graph is not "
                           "what we expect")

    # The aim blend is the one DefaultSlot feeds, found by following the wire
    # rather than by taking the first LayeredBoneBlend in the list: there are
    # two of them now and list order is not graph order.
    fed = PIN.list_connected_pins(_pin(aim_slot, "Pose", is_input=False))
    aim_blend = PIN.get_owning_node(fed[0]) if fed else None
    fresh = aim_blend is None or \
        aim_blend.get_class().get_name() != "AnimGraphNode_LayeredBoneBlend"

    if fresh:
        # First run on a stock ABP_Unarmed: StateMachine -> Slot -> ControlRig.
        rigs = _anim_nodes(ed, "AnimGraphNode_ControlRig")
        if len(rigs) != 1:
            raise RuntimeError(f"expected one ControlRig in ABP_Unarmed's "
                               f"AnimGraph, found {len(rigs)}")
        rig = rigs[0]
        feeding = PIN.list_connected_pins(_pin(aim_slot, "Source"))
        if not feeding:
            raise RuntimeError("Slot.Source is unconnected; graph is not what "
                               "we expect")
        loco = PIN.get_owning_node(feeding[0])

        aim_blend = _at(_palette(ed, "Animation|Blends|Layeredblendperbone"),
                        -420, 620)
        # A pose output legally drives more than one input here, so the
        # locomotion pose reaches both the blend's base and the slot's source
        # without needing a cached-pose pair.
        _connect(_pin(loco, "Pose", is_input=False), _pin(aim_blend, "BasePose"))
        PIN.break_pin_links(_pin(rig, "Source"))
        _connect(_pin(aim_slot, "Pose", is_input=False),
                 _pin(aim_blend, "BlendPoses_0"))
        _connect(_pin(aim_blend, "Pose", is_input=False), _pin(rig, "Source"))

    _configure_blend(aim_blend)
    _ensure_hit_slot(ed, aim_blend)
    _ensure_full_body_slot(ed)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("ABP_Unarmed failed to compile after the blend patch")
    _assets().save_loaded_asset(bp)

    # Both blends, not just the aim one: an unresolvable branch filter
    # contributes no bones, so a hit blend that lost its filter would play every
    # reaction at zero weight -- invisible, and indistinguishable in the log
    # from a reaction that never fired.
    blends = _anim_nodes(ed, "AnimGraphNode_LayeredBoneBlend")
    filters = [str(f.get_editor_property("bone_name"))
               for b in blends
               for l in b.get_editor_property("node").get_editor_property("layer_setup")
               for f in l.get_editor_property("branch_filters")]
    if len(blends) != 2 or filters != [UPPER_BODY_ROOT] * 2:
        raise RuntimeError(f"expected two {UPPER_BODY_ROOT} blends, got "
                           f"{len(blends)} with filters {filters}")
    slots = sorted(_slot_name(n) for n in _anim_nodes(ed, "AnimGraphNode_Slot"))
    if slots != sorted((AIM_SLOT, HIT_SLOT, FULL_BODY_SLOT)):
        raise RuntimeError(f"ABP_Unarmed's slots are {slots}")
    _log(f"ABP_Unarmed: {AIM_SLOT} and {HIT_SLOT} are upper-body only (from "
         f"{UPPER_BODY_ROOT}), {FULL_BODY_SLOT} is full body")
    return bp


# ─── BP_WeaponItem and its two children ──────────────────────────────────────

def _struct_type(struct):
    return BEL.get_struct_type(struct)


def _key(name):
    """An FKey value for a CDO default.

    unreal.Key takes no constructor argument and exposes no fields, so the only
    two ways in are set_editor_property("key_name", ...) and import_text(). The
    property form is used here because it fails loudly on a misspelling, where
    import_text returns True for anything.
    """
    k = unreal.Key()
    k.set_editor_property("key_name", name)
    return k


def build_settings_savegame(rebuild=True):
    """The settings the player keeps between runs: BP_Settings, a USaveGame.

    A SaveGame and not a GameInstance, and built HERE and not in
    build_graphics_menu.py, for the same reason: both of its consumers have to
    be able to name the class. The HUD loads it, edits it and saves it; the
    weapon component is handed the values every frame and never touches the
    disk. Putting it in the HUD's builder would mean the HUD's builder had to
    run first, and putting it on a GameInstance would mean the menu could not
    write to it without the game already being in progress.

    No graph: this is a record, not behaviour.
    """
    bp = _create_blueprint(SETTINGS_BP_PATH, unreal.SaveGame)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    _declare(ed, "MouseSensitivity", _float_type())
    # Indexed, not a struct per bind and not seven separate variables: the
    # settings screen walks the rows with one ForEachLoop and one Array_Set, and
    # BIND_VARS is what says which index means which action.
    _declare(ed, "Binds", BEL.get_array_type(_struct_type(unreal.Key.static_struct())))
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_Settings failed to compile")
    _apply_defaults(bp, {
        "MouseSensitivity": COMBAT.mouse_sensitivity_default,
        "Binds": [_key(k) for _name, k in BIND_VARS],
    })
    _log(f"built {SETTINGS_BP_PATH} (slot {SETTINGS_SLOT!r})")
    return bp


def build_weapon_item():
    """The base weapon Actor: no geometry, no graph, just the data a gun has.

    Every property the weapon component reads is declared here so that Inventory
    can be a plain array of BP_WeaponItem and the firing code needs exactly one
    cast. The muzzle is a *variable*, not a component: a component would have to
    live either on this class (and then be un-overridable per child) or on each
    child (and then be ambiguous to look up), whereas an offset transformed by
    the actor's transform costs one node and is settable per child.
    """
    bp = _create_blueprint(ITEM_BP_PATH, unreal.Actor)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")

    _drop_components(bp, {"Body"})
    _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Body")

    for name in ("Damage", "SpreadDegrees", "WeaponRange",
                 # When this weapon may next be fired, as a world time in
                 # seconds. One number does both jobs the shotgun needs: the
                 # interval between shots, and the pause a reload costs. A
                 # "reloading" bool plus a timer would need an interrupt rule
                 # and could disagree with itself; a deadline cannot.
                 "FireInterval", "NextFireTime", "ReloadSeconds"):
        _declare(ed, name, _float_type())
    for name, kind in (("DisplayName", "string"),
                       ("PelletCount", "int"),
                       ("Dropped", "bool"),
                       # Ammunition. UsesAmmo false means the other three are
                       # never read -- the pistol is deliberately unlimited, and
                       # the fire gate short-circuits on this rather than on a
                       # magazine that would have to be topped up forever.
                       ("UsesAmmo", "bool"),
                       ("MagazineSize", "int"),
                       ("Loaded", "int"),
                       ("Reserve", "int"),
                       # Held trigger or tapped trigger. Read only behind the
                       # fire gate, where Held is known valid -- a pure Get off
                       # a null self is an Accessed None every frame, and the
                       # outer gate's condition is pulled on frames where
                       # nothing is equipped at all.
                       ("Automatic", "bool")):
        _declare(ed, name, BEL.get_basic_type_by_name(kind))
    _declare(ed, "MuzzleOffset", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "GripLocation", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "GripRotation", _struct_type(unreal.Rotator.static_struct()))
    _declare(ed, "SlotColor", _struct_type(unreal.LinearColor.static_struct()))
    # The weapon's own silhouette for the inventory strip, drawn by
    # build_graphics_menu.py. On the item rather than in a table in the HUD for
    # the same reason SlotColor and DisplayName are: adding a weapon stays a
    # row in _weapon_specs() and the HUD never learns any weapon's name.
    _declare(ed, "Icon",
             BEL.get_object_reference_type(unreal.Texture2D.static_class()))
    # Three sounds, not one, and all three live on the weapon for the same
    # reason FireSound does: the graphs read them off Held, so a new weapon is
    # a row in _weapon_specs() and nothing else. The dry-fire and reload
    # assets happen to be shared by every weapon today -- that is a fact about
    # the defaults, not about the shape of the data.
    for name in ("FireSound", "DryFireSound", "ReloadSound"):
        _declare(ed, name,
                 BEL.get_object_reference_type(unreal.SoundBase.static_class()))
    _declare(ed, "AimPose",
             BEL.get_object_reference_type(unreal.AnimSequence.static_class()))
    # How far this weapon zooms when the right button is held. On the item for
    # the same reason SpreadDegrees is -- the component reads it off Held and
    # knows nothing about which weapon it is holding.
    _declare(ed, "AdsZoom", _float_type())
    # Whether aiming this weapon puts a scope over the screen. A flag rather
    # than "AdsZoom >= COMBAT.ads_zoom_scope": the zoom is how far the camera moves
    # and the scope is what the sight looks like, and a future weapon is free
    # to be a 4x with irons or a 2x with glass without either answer moving.
    _declare(ed, "Scoped", BEL.get_basic_type_by_name("bool"))
    # Degrees of upward kick this weapon puts on the view per shot. On the item
    # for the same reason AdsZoom and SpreadDegrees are: the component reads it
    # off Held and knows nothing about which weapon it is holding. The
    # horizontal half is not a second column -- it is a fraction of this one,
    # drawn per shot, and the fraction is the same for every gun (see
    # COMBAT.recoil_horizontal_ratio).
    _declare(ed, "RecoilPitch", _float_type())

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponItem failed to compile")
    _assets().save_loaded_asset(bp)
    _log(f"built {ITEM_BP_PATH}")
    return bp


def build_weapon(spec, item_bp):
    """One concrete weapon: the parts, plus the defaults for the base's variables."""
    eas = _assets()
    bp = _create_blueprint(spec["path"], BEL.generated_class(item_bp))

    body = _find_handle(bp, "Body")
    if not body:
        raise RuntimeError(f"{spec['path']} has no inherited Body component")

    _drop_components(bp, {p[0] for p in spec["parts"]})
    for name, mesh_path, location, rotation, scale, material in spec["parts"]:
        handle = _add_component(bp, body, unreal.StaticMeshComponent, name)
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(mesh_path))
        obj.set_editor_property("relative_location", unreal.Vector(*location))
        obj.set_editor_property("relative_rotation", rotation)
        obj.set_editor_property("relative_scale3d", unreal.Vector(*scale))
        obj.set_editor_property("override_materials", [eas.load_asset(material)])
        # A held weapon must never block anything -- a collider on the barrel
        # would shove the player's capsule around -- and a dropped one is picked
        # up by distance, not by overlap, so it needs no collision either.
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on {name}: {exc}")

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{spec['path']} failed to compile")

    # The HUD fades the scope on (BaseFOV/CurrentFOV - 1) / (AdsZoom - 1), so a
    # scoped weapon that does not zoom is a divide by zero once per frame while
    # it is aimed. Caught here rather than guarded there: it is a nonsense row
    # in the table, not a state the game can reach.
    if spec.get("scoped") and float(spec.get("ads_zoom", COMBAT.ads_zoom_irons)) <= 1.0:
        raise RuntimeError(f"{spec['display']} is scoped but does not zoom")

    _apply_defaults(bp, {
        "DisplayName": spec["display"],
        "Damage": float(spec["damage"]),
        "PelletCount": int(spec["pellets"]),
        "SpreadDegrees": float(spec["spread"]),
        "WeaponRange": float(spec["range"]),
        "Dropped": False,
        "UsesAmmo": bool(spec["uses_ammo"]),
        "Automatic": bool(spec["automatic"]),
        "MagazineSize": int(spec["magazine"]),
        # Starts loaded. A weapon that had to be reloaded before its first shot
        # would be a puzzle, not a mechanic.
        "Loaded": int(spec["magazine"]),
        "Reserve": int(spec["reserve"]),
        "FireInterval": float(spec["interval"]),
        "ReloadSeconds": float(spec["reload_s"]),
        # World time 0 is "now" at level start, so the first shot is free.
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(*spec["muzzle"]),
        "GripLocation": unreal.Vector(*spec["grip_loc"]),
        "GripRotation": spec["grip_rot"],
        "SlotColor": unreal.LinearColor(*spec["colour"], 1.0),
        "AdsZoom": float(spec.get("ads_zoom", COMBAT.ads_zoom_irons)),
        "Scoped": bool(spec.get("scoped", False)),
        "RecoilPitch": float(spec["recoil"]),
        "Icon": _weapon_icon(spec["display"]),
        "FireSound": _must_load(spec["sound"]),
        "DryFireSound": _must_load(SND_DRY_FIRE),
        "ReloadSound": _must_load(spec["reload_sound"]),
        "AimPose": _must_load(spec["aim"]),
    })
    _log(f"built {spec['path']} ({len(spec['parts'])} parts, "
         f"{spec['pellets']}x{spec['damage']:.0f} dmg, "
         f"{spec['recoil']:.2f} deg kick, "
         + (f"{spec['magazine']}+{spec['reserve']} rounds, "
            f"{spec['interval']:.2f}s between shots"
            if spec["uses_ammo"] else "unlimited ammo")
         + (", automatic)" if spec["automatic"] else ")"))
    return bp


# ─── Graph node paths ────────────────────────────────────────────────────────

FN_GET_OWNER = "/Script/Engine.ActorComponent.GetOwner"
FN_GET_PC = "/Script/Engine.GameplayStatics.GetPlayerController"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
# Held, not tapped: sprint is a state for as long as the key is down, so it is
# the one polled key in this file that cannot use WasInputKeyJustPressed.
FN_IS_KEY_DOWN = "/Script/Engine.PlayerController.IsInputKeyDown"
FN_GET_CAM = "/Script/Engine.GameplayStatics.GetPlayerCameraManager"
FN_CAM_LOC = "/Script/Engine.PlayerCameraManager.GetCameraLocation"
FN_CAM_ROT = "/Script/Engine.PlayerCameraManager.GetCameraRotation"
FN_FORWARD = "/Script/Engine.KismetMathLibrary.GetForwardVector"
FN_RAND_CONE = "/Script/Engine.KismetMathLibrary.RandomUnitVectorInConeInRadians"
FN_TRACE = "/Script/Engine.KismetSystemLibrary.LineTraceSingle"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
# A class reference is a different pin category from an object reference, so
# IsValid refuses to connect to one; IsValidClass is the class-pin twin.
FN_IS_VALID_CLASS = "/Script/Engine.KismetSystemLibrary.IsValidClass"
FN_TRANSFORM_LOC = "/Script/Engine.KismetMathLibrary.TransformLocation"
FN_GET_TRANSFORM = "/Script/Engine.Actor.GetTransform"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_MAKE_TRANSFORM = "/Script/Engine.KismetMathLibrary.MakeTransform"
FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
FN_BREAK_VECTOR = "/Script/Engine.KismetMathLibrary.BreakVector"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_PRINT = "/Script/Engine.KismetSystemLibrary.PrintString"
FN_WARN = "/Script/Engine.KismetSystemLibrary.PrintWarning"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_VEC_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_VectorToString"
FN_NORMAL = "/Script/Engine.KismetMathLibrary.Normal"
FN_DEG2RAD = "/Script/Engine.KismetMathLibrary.DegreesToRadians"
FN_PLAY_SOUND = "/Script/Engine.GameplayStatics.PlaySoundAtLocation"
FN_OBJECT_CLASS = "/Script/Engine.GameplayStatics.GetObjectClass"
FN_ATTACH = "/Script/Engine.Actor.K2_AttachToComponent"
FN_DETACH = "/Script/Engine.Actor.K2_DetachFromActor"
FN_SET_HIDDEN = "/Script/Engine.Actor.SetActorHiddenInGame"
FN_SET_ACTOR_LOC = "/Script/Engine.Actor.K2_SetActorLocation"
FN_SET_REL_LOC = "/Script/Engine.Actor.K2_SetActorRelativeLocation"
FN_SET_REL_ROT = "/Script/Engine.Actor.K2_SetActorRelativeRotation"
FN_SET_SCALE = "/Script/Engine.Actor.SetActorScale3D"
FN_DESTROY = "/Script/Engine.Actor.K2_DestroyActor"
FN_LIFESPAN = "/Script/Engine.Actor.SetLifeSpan"
FN_ALL_ACTORS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"
FN_ANIM_INSTANCE = "/Script/Engine.SkeletalMeshComponent.GetAnimInstance"
FN_PLAY_SLOT = "/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage"
FN_STOP_SLOT = "/Script/Engine.AnimInstance.StopSlotAnimation"
FN_RANDOM_NAV = ("/Script/NavigationSystem.NavigationSystemV1"
                 ".K2_GetRandomLocationInNavigableRadius")
FN_PROJECT_NAV = ("/Script/NavigationSystem.NavigationSystemV1"
                  ".K2_ProjectPointToNavigation")

FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_ARR_REMOVE = "/Script/Engine.KismetArrayLibrary.Array_Remove"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"

FN_ADD_VV = "/Script/Engine.KismetMathLibrary.Add_VectorVector"
FN_SUB_VV = "/Script/Engine.KismetMathLibrary.Subtract_VectorVector"
FN_MUL_VF = "/Script/Engine.KismetMathLibrary.Multiply_VectorFloat"
FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_MOD_II = "/Script/Engine.KismetMathLibrary.Percent_IntInt"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_LESS_II = "/Script/Engine.KismetMathLibrary.Less_IntInt"
FN_GREATER_II = "/Script/Engine.KismetMathLibrary.Greater_IntInt"
FN_MIN_II = "/Script/Engine.KismetMathLibrary.Min"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_ADD_FF = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_SUB_FF = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_LE_FF = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_LESS_FF = "/Script/Engine.KismetMathLibrary.Less_DoubleDouble"
FN_GREATER_FF = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_GE_FF = "/Script/Engine.KismetMathLibrary.GreaterEqual_DoubleDouble"
# The ground test. UCharacterMovementComponent::IsMovingOnGround and ::IsFalling
# are both virtual C++ and neither is BlueprintCallable -- measured, all three
# spellings return a pinless node. Character::CanJump is, and it is a real
# feet-on-the-ground query rather than a coincidence: CanJumpInternal requires
# the movement mode to be walking. It is a PROXY, and the way it could be wrong
# is if something ever disables jumping on an owner, which would silence that
# owner's footsteps. Nothing does.
FN_ON_GROUND = "/Script/Engine.Character.CanJump"
FN_GET_VELOCITY = "/Script/Engine.Actor.GetVelocity"
FN_VSIZE_XY = "/Script/Engine.KismetMathLibrary.VSizeXY"
FN_CLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_DISTANCE = "/Script/Engine.KismetMathLibrary.Vector_Distance"
FN_RANDOM_FLOAT = "/Script/Engine.KismetMathLibrary.RandomFloatInRange"
FN_RAND_INT = "/Script/Engine.KismetMathLibrary.RandomIntegerInRange"
FN_NEQ_BB = "/Script/Engine.KismetMathLibrary.NotEqual_BoolBool"
FN_MAKE_ROT = "/Script/Engine.KismetMathLibrary.MakeRotator"
FN_MUL_FF = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_SELECT_FF = "/Script/Engine.KismetMathLibrary.SelectFloat"
FN_DIV_FF = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_INTERP_FF = "/Script/Engine.KismetMathLibrary.FInterpTo"
FN_NOT_B = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_SET_FOV = "/Script/Engine.CameraComponent.SetFieldOfView"
FN_GET_YAW_SCALE = "/Script/Engine.PlayerController.GetDeprecatedInputYawScale"
FN_GET_PITCH_SCALE = "/Script/Engine.PlayerController.GetDeprecatedInputPitchScale"
FN_SET_YAW_SCALE = "/Script/Engine.PlayerController.SetDeprecatedInputYawScale"
FN_SET_PITCH_SCALE = "/Script/Engine.PlayerController.SetDeprecatedInputPitchScale"
FN_LERP = "/Script/Engine.KismetMathLibrary.Lerp"
# Recoil moves the view through the CONTROLLER's rotation, not through
# AddPitchInput: see COMBAT's recoil block for why routing it through
# RotationInput would make the kick scale with the sensitivity slider.
FN_GET_CONTROL_ROT = "/Script/Engine.Controller.GetControlRotation"
FN_SET_CONTROL_ROT = "/Script/Engine.Controller.SetControlRotation"
FN_BREAK_ROT = "/Script/Engine.KismetMathLibrary.BreakRotator"
FN_ABS = "/Script/Engine.KismetMathLibrary.Abs"
# "Is anything playing in this slot right now?" -- pure, one Name in, one bool
# out. It is what lets the ready pose notice that a hit reaction took the
# montage group off it, and put itself back the frame the flinch ends.
FN_IS_SLOT_ACTIVE = "/Script/Engine.AnimInstance.IsSlotActive"
# The hit-direction pick. Dot_VectorVector against the owner's own forward and
# right is what turns "where the round came from" into one of four clips
# without a single angle or a single trigonometric function.
FN_DOT_VV = "/Script/Engine.KismetMathLibrary.Dot_VectorVector"
FN_ACTOR_RIGHT = "/Script/Engine.Actor.GetActorRightVector"
# Integer clamp, not FClamp: the reaction index is an array index, and an array
# shorter than HIT_REACTION_CLIPS (a checkout whose retarget has not run) must
# clip to the last entry rather than read off the end.
FN_CLAMP_II = "/Script/Engine.KismetMathLibrary.Clamp"
CAMERA_CLASS_PATH = "/Script/Engine.CameraComponent"
MOVEMENT_CLASS_PATH = "/Script/Engine.CharacterMovementComponent"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"
FN_DISABLE_MOVEMENT = "/Script/Engine.CharacterMovementComponent.DisableMovement"
FN_SET_COLLISION = "/Script/Engine.PrimitiveComponent.SetCollisionEnabled"
FN_GET_CONTROLLER = "/Script/Engine.Pawn.GetController"
FN_SET_PROFILE = "/Script/Engine.PrimitiveComponent.SetCollisionProfileName"
# Every body in the physics asset, not the component's one root body --
# see RAGDOLL_PROFILE. SkeletalMeshComponent has no SetSimulatePhysics
# UFunction at all, so there is no node to reach for by mistake.
FN_SIMULATE_ALL = ("/Script/Engine.SkeletalMeshComponent"
                   ".SetAllBodiesSimulatePhysics")
FN_SIN = "/Script/Engine.KismetMathLibrary.Sin"
FN_ROT_FROM_X = "/Script/Engine.KismetMathLibrary.MakeRotFromX"
FN_EXP = "/Script/Engine.KismetMathLibrary.Exp"
FN_INV_XFORM_DIR = "/Script/Engine.KismetMathLibrary.InverseTransformDirection"
FN_BREAK_TRANSFORM = "/Script/Engine.KismetMathLibrary.BreakTransform"
FN_GET_COMPONENTS = "/Script/Engine.Actor.K2_GetComponentsByClass"
# Component-space, not the Actor.* pair above it: the droplets move relative to
# the burst, and the actor itself never moves after the frame it spawns.
FN_COMP_REL_XFORM = "/Script/Engine.SceneComponent.GetRelativeTransform"
FN_COMP_SET_REL_LOC = "/Script/Engine.SceneComponent.K2_SetRelativeLocation"
FN_COMP_SET_SCALE = "/Script/Engine.SceneComponent.SetRelativeScale3D"
FN_SET_ACTOR_ROT = "/Script/Engine.Actor.K2_SetActorRotation"
FN_ACTOR_FORWARD = "/Script/Engine.Actor.GetActorForwardVector"
FN_DRAW_LINE = "/Script/Engine.KismetSystemLibrary.DrawDebugLine"
FN_ADD_LOCAL_ROT = "/Script/Engine.Actor.K2_AddActorLocalRotation"
FN_DRAW_STRING = "/Script/Engine.KismetSystemLibrary.DrawDebugString"
FN_FLOAT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_DoubleToString"
# Only the temporary hit-reaction probe uses this; see HIT_REACT_PROBE.
FN_DISPLAY_NAME = "/Script/Engine.KismetSystemLibrary.GetDisplayName"
FN_TRACE_COMPONENT = "/Script/Engine.PrimitiveComponent.K2_LineTraceComponent"
FN_ARR_CONTAINS = "/Script/Engine.KismetArrayLibrary.Array_Contains"

NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
NODE_BREAK_HIT = "Collision|BreakHitResult"
NODE_SPAWN = "Game|SpawnActorfromClass"
NODE_CAST_CHAR = "Utilities|Casting|CastToBP_ThirdPersonCharacter"
NODE_CAST_CHARACTER = "Utilities|Casting|CastToCharacter"
NODE_CAST_PAWN = "Utilities|Casting|CastToPawn"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"
NODE_CAST_ITEM = "Utilities|Casting|CastToBP_WeaponItem"
MACRO_FOR_LOOP = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForLoop"
MACRO_FOR_EACH = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop"

INF = 1.0e9


def _vec(ed, x, y, z, px, py):
    """A constant vector, as a MakeVector node rather than as a pin default.

    A struct pin refuses set_pin_value outright -- every format returns False
    and the pin keeps an empty default, which the compiler then reads as the
    zero vector. A zero scale on a spawn transform makes the actor invisible,
    so these have to be real nodes.
    """
    n = _at(_node(ed, FN_MAKE_VECTOR), px, py)
    for axis, value in (("X", x), ("Y", y), ("Z", z)):
        _set(n, axis, float(value))
    return _pin(n, "ReturnValue", is_input=False)


def _events(ed, rebuild):
    """Return (tick, begin_play), wiping the graph first when rebuilding.

    A builder whose "already authored, reusing" guard has no escape hatch means
    no edit to the builder ever reaches the asset, so rebuild is the default
    everywhere in this file.
    """
    if rebuild:
        nodes = ed.list_all_nodes()
        if nodes:
            ed.remove_nodes(nodes)
    tick = ed.find_event_node("ReceiveTick")
    if not tick:
        tick = _palette(ed, NODE_TICK, 0, 0)
    begin = ed.find_event_node("ReceiveBeginPlay")
    if not begin:
        begin = _palette(ed, NODE_BEGIN_PLAY, 0, -900)
    return tick, begin


def _post_physics_tick(bp):
    """Tick after the player controller has processed input this frame.

    WasInputKeyJustPressed reads EventCounts, which UPlayerInput::
    ProcessInputStack swaps out once per frame during the controller's
    TG_PrePhysics tick. A component defaults to TG_PrePhysics too, with no
    defined order against the controller, so a trigger polled there fires or
    does not fire depending on registration order.

    Nothing here enables ticking, and nothing needs to: bCanEverTick is not a
    UPROPERTY, but FKismetCompilerContext::SetCanEverTick turns it on at compile
    time for any Blueprint whose first native parent is UActorComponent and
    whose Tick event has its exec pin connected. Leave Tick wired.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    tick_fn = cdo.get_editor_property("primary_component_tick")
    tick_fn.set_editor_property("tick_group", unreal.TickingGroup.TG_POST_PHYSICS)
    cdo.set_editor_property("primary_component_tick", tick_fn)


# ─── BP_BloodSplash ──────────────────────────────────────────────────────────

BLOOD_SEED = 7             # laid out once, at build time, so it is reproducible
BLOOD_DROPLETS = 14        # the fast spray
BLOOD_MIST = 5             # fine, slow, near the wound: what is left hanging
BLOOD_CONE_DEG = 34.0      # spray half-angle around the surface normal
BLOOD_MIST_CONE_DEG = 72.0 # the haze is not directional in the way the spray is
BLOOD_LIFETIME = 0.45      # punctuation, not a fountain
BLOOD_FADE_TAIL = 0.14     # the last of the lifetime, spent shrinking to nothing
BLOOD_SPEED_MIN = 140.0    # cm/s -- the laggards
BLOOD_SPEED_MAX = 900.0    # cm/s -- the leading edge of the spray
BLOOD_MIST_SPEED_MIN = 25.0
BLOOD_MIST_SPEED_MAX = 90.0
BLOOD_DRAG = 3.6           # 1/s. Air drag on a 2 mm droplet, near enough
BLOOD_GRAVITY = 980.0      # cm/s^2, real gravity and not a stylised fraction
BLOOD_DROP_SCALE = (0.010, 0.030)   # 1-3 cm droplets off a 100 cm sphere
BLOOD_MIST_SCALE = (0.005, 0.011)   # 0.5-1.1 cm
# The velocity of each droplet is baked into its relative *location*, divided by
# this. Two things fall out of that and both matter:
#
#   * there is no parallel table to keep in step with the components -- the
#     droplet carries its own velocity, so no ordering assumption about what
#     GetComponentsByClass hands back can ever be wrong;
#   * the frame the actor spawns, before BeginPlay has run, the components are
#     still sitting where the builder left them. At 100 that is a 1-9 cm clump
#     around the wound, which is a wound. Store the velocity directly and the
#     first frame of every hit is a nine-metre sphere of blood.
#
# 100 rather than any other number because cm/s over 100 is m/s, so the baked
# location reads as the droplet's launch speed in metres per second and there
# is nothing to decode by hand. The graph converts it back where it scales the
# drag term, not per droplet.
BLOOD_VELOCITY_ENCODE = 100.0
# Damage the spray is sized against. Shotgun pellets are 18 each and there are
# eight of them; the sniper is one large number. Clamped either side so no
# weapon can produce either a mist or a fire hose.
BLOOD_REFERENCE_DAMAGE = 24.0
BLOOD_SCALE_MIN = 0.65
BLOOD_SCALE_MAX = 1.60


def _blood_blobs():
    """A seeded spray of droplet velocities, thrown back along +X.

    +X is the actor's forward, and _author_impact spawns the splash rotated so
    that forward *is* the surface normal of whatever the pellet hit. So the
    spray comes out of the wound rather than out of an arbitrary world axis,
    and a shot to the chest and a shot to the back throw blood opposite ways.

    Each tuple is (x, y, z, scale) where x/y/z is the droplet's launch velocity
    over BLOOD_VELOCITY_ENCODE -- see that constant for why the velocity lives
    in the location.

    Seeded rather than authored by hand: the shape wanted here is "irregular",
    which a person writing tuples produces badly and a seed produces for free --
    and a fixed seed keeps it reproducible, so the verifier can recompute the
    same layout and compare it against the saved components.
    """
    rng = random.Random(BLOOD_SEED)
    blobs = []

    def shoot(cone_deg, speed_lo, speed_hi, scale_lo, scale_hi, bias):
        # sqrt() on the polar draw is what spreads samples evenly over the cap
        # instead of piling them on the axis -- a uniform draw in theta gives a
        # needle with a halo, which is not what a spray looks like.
        theta = math.radians(cone_deg) * math.sqrt(rng.random())
        phi = rng.uniform(0.0, math.tau)
        # Biased toward the top of the range: most of the spray is fast and a
        # few droplets lag badly behind it. Drawn uniformly, every droplet ends
        # the frame at much the same radius and the burst reads as one
        # expanding shell -- the "everything moves at one speed" tell.
        speed = speed_lo + (speed_hi - speed_lo) * (rng.random() ** bias)
        direction = (math.cos(theta),
                     math.sin(theta) * math.cos(phi),
                     math.sin(theta) * math.sin(phi))
        return tuple(round(d * speed / BLOOD_VELOCITY_ENCODE, 5)
                     for d in direction) + (round(rng.uniform(scale_lo, scale_hi), 5),)

    for _ in range(BLOOD_DROPLETS):
        blobs.append(shoot(BLOOD_CONE_DEG, BLOOD_SPEED_MIN, BLOOD_SPEED_MAX,
                           *BLOOD_DROP_SCALE, bias=0.5))
    for _ in range(BLOOD_MIST):
        blobs.append(shoot(BLOOD_MIST_CONE_DEG, BLOOD_MIST_SPEED_MIN,
                           BLOOD_MIST_SPEED_MAX, *BLOOD_MIST_SCALE, bias=1.0))
    return tuple(blobs)


BLOOD_BLOBS = _blood_blobs()


def build_blood_splash(rebuild=True):
    """Small dark droplets thrown out of the wound under drag and real gravity.

    **Not Niagara, and the reason is not preference.** UE 5.8 exposes
    NiagaraSystem to Python with no emitter handles, no exposed parameters and
    no renderer access -- `get_editor_property("emitter_handles")` does not
    resolve -- and the one API that *can* build an emitter stack,
    UNiagaraExternalSystemEditorUtilities (AddEmitter / AddModule /
    SetStackInputData, the thing the editor's own external-edit tooling drives),
    is plain C++ statics with no UFUNCTION on them, so none of it reaches
    Python. Duplicating an engine template such as
    /Niagara/DefaultAssets/Templates/Systems/DirectionalBurst gets an asset that
    cannot then be retuned. Cascade is worse: the runtime classes survive in 5.8
    but the editor module and every ParticleModule* reflection type are gone.
    A system nobody can rebuild from a script is not allowed here, so the
    droplets are components and the solver is in the graph.

    What each droplet does is the closed-form solution of dv/dt = g - k*v,
    which is a falling drop with linear air drag:

        A(t)  = (1 - e^(-k t)) / k
        B(t)  = (t - A) / k
        local = Velocity * A + Fall * B

    -- one pair of scalars computed once per frame for the whole burst, and one
    multiply-add per droplet. Every droplet has its own launch velocity, so they
    separate as they fly: that separation is most of what the old version was
    missing. It threw ten spheres as one rigid cone at a single speed and swelled
    them on a sine to 35 cm across, which is a cartoon for three separate
    reasons -- one speed, one shape, and blood does not inflate.

    Scale is held flat and then cut to nothing over the last BLOOD_FADE_TAIL of
    the life, so the burst is a punctuation mark rather than something that
    grows.
    """
    eas = _assets()
    bp = _create_blueprint(BLOOD_BP_PATH, unreal.Actor)
    names = {f"Blob{i}" for i in range(max(len(BLOOD_BLOBS), 24))}
    _drop_components(bp, {"Burst"} | names)
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Burst")
    for i, (x, y, z, scale) in enumerate(BLOOD_BLOBS):
        handle = _add_component(bp, root, unreal.StaticMeshComponent, f"Blob{i}")
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(SPHERE))
        obj.set_editor_property("relative_location", unreal.Vector(x, y, z))
        obj.set_editor_property("relative_scale3d", unreal.Vector(scale, scale, scale))
        obj.set_editor_property("override_materials", [eas.load_asset(MAT_BLOOD)])
        # A droplet is 1-3 cm and gone in under half a second; it has no
        # business in the shadow pass, and 19 of them per pellet times eight
        # pellets is 152 shadow casters for a single shotgun blast.
        obj.set_editor_property("cast_shadow", False)
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on Blob{i}: {exc}")

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    _declare(ed, "Age", _float_type())
    _declare(ed, "Blobs", BEL.get_array_type(
        BEL.get_object_reference_type(unreal.StaticMeshComponent.static_class())))
    # Launch velocity and untouched size, one entry per component, filled in the
    # same loop that fills Blobs -- so the three arrays are in step by
    # construction and not by an assumption about component ordering.
    _declare(ed, "Velocity", BEL.get_array_type(
        _struct_type(unreal.Vector.static_struct())))
    _declare(ed, "Size", BEL.get_array_type(_float_type()))
    # Gravity, rotated into the actor's own frame once. The actor is spawned
    # facing the hit normal and never turns, so this cannot go stale, and doing
    # it here keeps a transform inverse out of the per-frame path.
    _declare(ed, "Fall", _struct_type(unreal.Vector.static_struct()))

    # --- BeginPlay: read each droplet's velocity back off the component ------
    # Pure, not impure: UHT promotes a const BlueprintCallable to BlueprintPure,
    # so this node has no exec pin to thread and the loop hangs off BeginPlay
    # directly. The same is true of GetRelativeTransform below.
    found = _at(_node(ed, FN_GET_COMPONENTS), 320, -900)
    _pin(found, "ComponentClass").set_pin_value("/Script/Engine.StaticMeshComponent")

    gather = ed.add_macro_node(MACRO_FOR_EACH)
    if not gather:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(gather, 620, -900)
    _connect(_pin(found, "ReturnValue", is_input=False), _loose_pin(gather, "Array"))
    _connect(BEL.find_then_pin(begin), _loose_pin(gather, "Exec"))
    blob = _loose_pin(gather, "ArrayElement", is_input=False)

    rel = _at(_node(ed, FN_COMP_REL_XFORM), 920, -900)
    _connect(blob, _pin(rel, "self"))
    parts = _at(_node(ed, FN_BREAK_TRANSFORM), 1180, -640)
    _connect(_pin(rel, "ReturnValue", is_input=False), _pin(parts, "InTransform"))

    keep_blob = _at(_node(ed, FN_ARR_ADD), 1180, -900)
    _connect(_pin(_at(ed.add_get_member_variable_node("Blobs"), 1180, -760),
                  "Blobs", is_input=False),
             _pin(keep_blob, "TargetArray"))
    _connect(blob, _pin(keep_blob, "NewItem"))
    _connect(_loose_pin(gather, "LoopBody", is_input=False), _pin(keep_blob, "execute"))

    keep_vel = _at(_node(ed, FN_ARR_ADD), 1700, -900)
    _connect(_pin(_at(ed.add_get_member_variable_node("Velocity"), 1440, -760),
                  "Velocity", is_input=False),
             _pin(keep_vel, "TargetArray"))
    _connect(_loose_pin(parts, "Location", is_input=False), _pin(keep_vel, "NewItem"))
    _connect(BEL.find_then_pin(keep_blob), _pin(keep_vel, "execute"))

    # Uniform by construction, so X is the whole story.
    axes = _at(_node(ed, FN_BREAK_VECTOR), 1700, -560)
    _connect(_loose_pin(parts, "Scale", is_input=False), _pin(axes, "InVec"))
    keep_size = _at(_node(ed, FN_ARR_ADD), 1960, -900)
    _connect(_pin(_at(ed.add_get_member_variable_node("Size"), 1960, -760),
                  "Size", is_input=False),
             _pin(keep_size, "TargetArray"))
    _connect(_pin(axes, "X", is_input=False), _pin(keep_size, "NewItem"))
    _connect(BEL.find_then_pin(keep_vel), _pin(keep_size, "execute"))

    here = _at(_node(ed, FN_GET_TRANSFORM), 620, -1220)
    local_g = _at(_node(ed, FN_INV_XFORM_DIR), 920, -1220)
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(local_g, "T"))
    _connect(_vec(ed, 0.0, 0.0, -BLOOD_GRAVITY, 620, -1080), _pin(local_g, "Direction"))
    pin_fall = _at(ed.add_set_member_variable_node("Fall"), 1180, -1220)
    _connect(_pin(local_g, "ReturnValue", is_input=False), _pin(pin_fall, "Fall"))
    _connect(_loose_pin(gather, "Completed", is_input=False), _pin(pin_fall, "execute"))

    life = _at(_node(ed, FN_LIFESPAN), 1440, -1220)
    _set(life, "InLifespan", BLOOD_LIFETIME)
    _connect(BEL.find_then_pin(pin_fall), _pin(life, "execute"))

    # --- Tick: two scalars for the whole burst, then one pass over it --------
    age_get = _at(ed.add_get_member_variable_node("Age"), 260, 200)
    add = _at(_node(ed, FN_ADD_FF), 470, 200)
    _connect(_pin(age_get, "Age", is_input=False), _pin(add, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(add, "B"))
    age_set = _at(ed.add_set_member_variable_node("Age"), 700, 0)
    _connect(_pin(add, "ReturnValue", is_input=False), _pin(age_set, "Age"))
    _connect(BEL.find_then_pin(tick), _pin(age_set, "execute"))
    # Read the *stored* age from here on. The add is pure, so every re-read of
    # its output would recompute it -- harmless while the inputs hold still, but
    # the stored value is the one the next frame accumulates from, and the two
    # should not be allowed to drift apart.
    age = _at(ed.add_get_member_variable_node("Age"), 700, 240)
    age_out = _pin(age, "Age", is_input=False)

    # A = (1 - e^(-k t)) / k, written as (e^(-k t) - 1) / -k. Algebraically the
    # same; the difference is that every constant then lands on a B pin, and
    # the A pin of these math nodes will not hold a literal -- set_pin_value
    # reports success and the pin reads back empty, which compiles as a zero.
    decay = _at(_node(ed, FN_MUL_FF), 940, 400)
    _connect(age_out, _pin(decay, "A"))
    _set(decay, "B", -BLOOD_DRAG)
    gone_frac = _at(_node(ed, FN_EXP), 1160, 400)
    _connect(_pin(decay, "ReturnValue", is_input=False), _pin(gone_frac, "A"))
    spent = _at(_node(ed, FN_SUB_FF), 1380, 400)
    _connect(_pin(gone_frac, "ReturnValue", is_input=False), _pin(spent, "A"))
    _set(spent, "B", 1.0)
    a_term = _at(_node(ed, FN_DIV_FF), 1600, 400)
    _connect(_pin(spent, "ReturnValue", is_input=False), _pin(a_term, "A"))
    _set(a_term, "B", -BLOOD_DRAG)
    a_out = _pin(a_term, "ReturnValue", is_input=False)
    # A in centimetres, for the velocities stored in metres per second. Done
    # once here rather than per droplet, and not on the Multiply_VectorFloat
    # itself -- that node's float pin rejects a literal default, reading back
    # empty whatever is written to it.
    a_cm = _at(_node(ed, FN_MUL_FF), 1820, 400)
    _connect(a_out, _pin(a_cm, "A"))
    _set(a_cm, "B", BLOOD_VELOCITY_ENCODE)
    a_cm_out = _pin(a_cm, "ReturnValue", is_input=False)

    # B = (t - A) / k
    lag = _at(_node(ed, FN_SUB_FF), 1820, 560)
    _connect(age_out, _pin(lag, "A"))
    _connect(a_out, _pin(lag, "B"))
    b_term = _at(_node(ed, FN_DIV_FF), 2040, 560)
    _connect(_pin(lag, "ReturnValue", is_input=False), _pin(b_term, "A"))
    _set(b_term, "B", BLOOD_DRAG)
    b_out = _pin(b_term, "ReturnValue", is_input=False)

    # fade = clamp((lifetime - age) / tail, 0, 1): flat, then a hard cut. Both
    # signs flipped for the same B-pin reason as the A term above.
    left = _at(_node(ed, FN_SUB_FF), 940, 760)
    _connect(age_out, _pin(left, "A"))
    _set(left, "B", BLOOD_LIFETIME)
    tail = _at(_node(ed, FN_DIV_FF), 1160, 760)
    _connect(_pin(left, "ReturnValue", is_input=False), _pin(tail, "A"))
    _set(tail, "B", -BLOOD_FADE_TAIL)
    fade = _at(_node(ed, FN_CLAMP), 1380, 760)
    _connect(_pin(tail, "ReturnValue", is_input=False), _pin(fade, "Value"))
    _set(fade, "Min", 0.0)
    _set(fade, "Max", 1.0)
    fade_out = _pin(fade, "ReturnValue", is_input=False)

    blobs_get = _at(ed.add_get_member_variable_node("Blobs"), 2300, 240)
    fly = ed.add_macro_node(MACRO_FOR_EACH)
    if not fly:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(fly, 2560, 0)
    _connect(_pin(blobs_get, "Blobs", is_input=False), _loose_pin(fly, "Array"))
    _connect(BEL.find_then_pin(age_set), _loose_pin(fly, "Exec"))
    each = _loose_pin(fly, "ArrayElement", is_input=False)
    index = _loose_pin(fly, "ArrayIndex", is_input=False)

    vel_arr = _at(ed.add_get_member_variable_node("Velocity"), 2860, 420)
    vel = _at(_node(ed, FN_ARR_GET), 3080, 420)
    _connect(_pin(vel_arr, "Velocity", is_input=False), _pin(vel, "TargetArray"))
    _connect(index, _pin(vel, "Index"))
    thrown = _at(_node(ed, FN_MUL_VF), 3320, 420)
    _connect(_pin(vel, "Item", is_input=False), _pin(thrown, "A"))
    _connect(a_cm_out, _pin(thrown, "B"))

    fall_get = _at(ed.add_get_member_variable_node("Fall"), 2860, 640)
    dropped = _at(_node(ed, FN_MUL_VF), 3320, 640)
    _connect(_pin(fall_get, "Fall", is_input=False), _pin(dropped, "A"))
    _connect(b_out, _pin(dropped, "B"))

    offset = _at(_node(ed, FN_ADD_VV), 3560, 420)
    _connect(_pin(thrown, "ReturnValue", is_input=False), _pin(offset, "A"))
    _connect(_pin(dropped, "ReturnValue", is_input=False), _pin(offset, "B"))

    put = _at(_node(ed, FN_COMP_SET_REL_LOC), 3820, 0)
    _connect(each, _pin(put, "self"))
    _connect(_pin(offset, "ReturnValue", is_input=False), _pin(put, "NewLocation"))
    # No sweep: the droplets have no collision and the spray is meant to pass
    # through the surface it came off, not to be stopped by it.
    _set(put, "bSweep", "false")
    _set(put, "bTeleport", "true")
    _connect(_loose_pin(fly, "LoopBody", is_input=False), _pin(put, "execute"))

    size_arr = _at(ed.add_get_member_variable_node("Size"), 2860, 900)
    born = _at(_node(ed, FN_ARR_GET), 3080, 900)
    _connect(_pin(size_arr, "Size", is_input=False), _pin(born, "TargetArray"))
    _connect(index, _pin(born, "Index"))
    now_size = _at(_node(ed, FN_MUL_FF), 3320, 900)
    _connect(_pin(born, "Item", is_input=False), _pin(now_size, "A"))
    _connect(fade_out, _pin(now_size, "B"))
    size_v = _at(_node(ed, FN_MUL_VF), 3560, 900)
    _connect(_vec(ed, 1.0, 1.0, 1.0, 3320, 1040), _pin(size_v, "A"))
    _connect(_pin(now_size, "ReturnValue", is_input=False), _pin(size_v, "B"))
    shrink = _at(_node(ed, FN_COMP_SET_SCALE), 4080, 0)
    _connect(each, _pin(shrink, "self"))
    _connect(_pin(size_v, "ReturnValue", is_input=False), _pin(shrink, "NewScale3D"))
    _connect(BEL.find_then_pin(put), _pin(shrink, "execute"))

    ed.add_comment_to_nodes(
        f"{len(BLOOD_BLOBS)} droplets -- {BLOOD_DROPLETS} of spray in a "
        f"{BLOOD_CONE_DEG:.0f} deg cone around the actor's +X, which "
        f"_author_impact points down the surface normal of the hit, plus "
        f"{BLOOD_MIST} slow fine ones that hang at the wound. Each carries its "
        f"own launch velocity ({BLOOD_SPEED_MIN:.0f}-{BLOOD_SPEED_MAX:.0f} cm/s) "
        f"in its build-time relative location over {BLOOD_VELOCITY_ENCODE:.0f}, "
        f"and flies the exact solution of dv/dt = g - {BLOOD_DRAG} v under "
        f"{BLOOD_GRAVITY:.0f} cm/s^2 -- two scalars for the burst, one "
        f"multiply-add each. Flat scale until the last {BLOOD_FADE_TAIL}s of "
        f"{BLOOD_LIFETIME}s, then cut. SetLifeSpan removes the actor.",
        [found, gather, rel, parts, keep_blob, keep_vel, axes, keep_size,
         here, local_g, pin_fall, life, age_get, add, age_set, age, decay,
         gone_frac, spent, a_term, a_cm, lag, b_term, left, tail, fade,
         blobs_get, fly,
         vel_arr, vel, thrown, fall_get, dropped, offset, put, size_arr, born,
         now_size, size_v, shrink])

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_BloodSplash failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {BLOOD_BP_PATH} ({len(BLOOD_BLOBS)} droplets, {BLOOD_LIFETIME}s, "
         f"drag {BLOOD_DRAG}, gravity {BLOOD_GRAVITY:.0f}, sprayed along the hit "
         f"normal)")
    return bp


# ─── BP_AmmoPickup ───────────────────────────────────────────────────────────

def build_ammo_pickup(rebuild=True):
    """The two shells a killed wanderer leaves behind, and how they are taken.

    Walked into rather than pressed for. E already picks weapons up, and making
    the player press it again for ammunition they obviously want is friction
    with no decision in it -- whereas a *weapon* on the ground is a real choice,
    because the five slots are finite.

    The proximity test runs on the pickup, not on the player, and that is the
    whole reason this is an actor with a graph instead of another
    GetAllActorsOfClass sweep in the weapon component's Tick. There are at most
    a handful of these on the ground; there is exactly one player. One actor
    measuring its own distance costs one Tick each. The alternative re-walks
    every pickup in the level every frame whether any exist or not.

    Credit goes to the weapon in the player's hands, if that weapon takes
    ammunition, and otherwise to the first carried weapon that does. The
    preference is not decoration: with four of the five weapons using
    ammunition, "first in the inventory" means the shells always land in the
    shotgun in slot 0, so a player clearing the forest with the sniper would
    watch their reserve stay at 15 while a gun they are not holding fills up.

    Credited is what stops the fallback loop handing the same two shells to a
    second shotgun -- ForEachLoop has no break pin, so the guard has to be a
    flag the body sets -- and it is also what the destroy is gated on.
    """
    eas = _assets()
    bp = _create_blueprint(AMMO_BP_PATH, unreal.Actor)

    _drop_components(bp, {"Pack", "ShellA", "ShellB"})
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Pack")
    # Two of them, because two is what a kill drops and the pickup should look
    # like what it gives you.
    for name, y in (("ShellA", -5.0), ("ShellB", 5.0)):
        handle = _add_component(bp, root, unreal.StaticMeshComponent, name)
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(CYLINDER))
        obj.set_editor_property("relative_location", unreal.Vector(0.0, y, 0.0))
        obj.set_editor_property("relative_scale3d", unreal.Vector(0.08, 0.08, 0.14))
        obj.set_editor_property("override_materials", [eas.load_asset(MAT_BRASS)])
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on {name}: {exc}")

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    _declare(ed, "Shells", BEL.get_basic_type_by_name("int"))
    _declare(ed, "Credited", BEL.get_basic_type_by_name("bool"))

    # --- BeginPlay: tidy yourself away eventually ---------------------------
    life = _at(_node(ed, FN_LIFESPAN), 320, -500)
    _set(life, "InLifespan", AMMO_PICKUP_LIFETIME)
    _connect(BEL.find_then_pin(begin), _pin(life, "execute"))

    # --- Tick: spin, then check the distance --------------------------------
    # The spin is what makes a 10 cm object findable on a forest floor at night;
    # the emissive brass does the rest.
    turn = _at(_node(ed, FN_MUL_FF), 320, 300)
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(turn, "A"))
    _set(turn, "B", AMMO_SPIN_DEG_PER_S)
    delta = _at(_node(ed, FN_MAKE_ROT), 560, 300)
    _connect(_pin(turn, "ReturnValue", is_input=False), _pin(delta, "Yaw"))
    spin = _at(_node(ed, FN_ADD_LOCAL_ROT), 800, 0)
    _connect(_pin(delta, "ReturnValue", is_input=False), _pin(spin, "DeltaRotation"))
    _set(spin, "bSweep", "false")
    _set(spin, "bTeleport", "true")
    _connect(BEL.find_then_pin(tick), _pin(spin, "execute"))

    pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), 800, 300)
    _set(pawn, "PlayerIndex", 0)
    pawn_out = _pin(pawn, "ReturnValue", is_input=False)
    there = _at(_node(ed, FN_ACTOR_LOC), 1040, 300)
    _connect(pawn_out, _pin(there, "self"))
    here = _at(_node(ed, FN_ACTOR_LOC), 1040, 420)
    gap = _at(_node(ed, FN_DISTANCE), 1280, 300)
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(gap, "V1"))
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(gap, "V2"))
    near = _at(_node(ed, FN_LESS_FF), 1520, 300)
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(near, "A"))
    _set(near, "B", AMMO_PICKUP_RADIUS)

    reached = _at(ed.add_branch_node(), 1760, 0)
    _connect(_pin(near, "ReturnValue", is_input=False), _pin(reached, "Condition"))
    _connect(BEL.find_then_pin(spin), _pin(reached, "execute"))

    # --- who gets the shells ------------------------------------------------
    comp = _at(_node(ed, FN_GET_COMP), 2000, 300)
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    as_weapon_n = _at(_palette(ed, "Utilities|Casting|CastToBP_WeaponComponent"),
                      2280, 0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(as_weapon_n, "Object"))
    _connect(BEL.find_then_pin(reached), _pin(as_weapon_n, "execute"))
    as_weapon = _loose_pin(as_weapon_n, "AsBPWeaponComponent", is_input=False)

    # --- first choice: whatever is in the player's hands ---------------------
    # Two nested branches rather than one AND, and for the reason this file has
    # now hit four times: UsesAmmo is a pure read off Held, and pulling it while
    # Held is None is an Accessed None. The validity test has to be a gate the
    # second read sits behind, not a term beside it.
    held_get = _at(ed.add_get_member_variable_node("Held", WEAPON_COMP_CLASS_PATH),
                   2560, 300)
    _connect(as_weapon, _pin(held_get, "self"))
    held = _pin(held_get, "Held", is_input=False)
    armed = _at(_node(ed, FN_IS_VALID), 2800, 300)
    _connect(held, _pin(armed, "Object"))
    has_gun = _at(ed.add_branch_node(), 3040, -700)
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(has_gun, "Condition"))
    _connect(BEL.find_then_pin(as_weapon_n), _pin(has_gun, "execute"))

    held_uses, held_uses_n = _prop(ed, "UsesAmmo", held, 3300, -400)
    takes_ammo = _at(ed.add_branch_node(), 3560, -700)
    _connect(held_uses, _pin(takes_ammo, "Condition"))
    _connect(BEL.find_then_pin(has_gun), _pin(takes_ammo, "execute"))

    held_res, held_res_n = _prop(ed, "Reserve", held, 3820, -400)
    held_shells = _at(ed.add_get_member_variable_node("Shells"), 3820, -280)
    held_richer = _at(_node(ed, FN_ADD_II), 4080, -400)
    _connect(held_res, _pin(held_richer, "A"))
    _connect(_pin(held_shells, "Shells", is_input=False), _pin(held_richer, "B"))
    held_store = _at(ed.add_set_member_variable_node("Reserve", ITEM_CLASS_PATH),
                     4340, -700)
    _connect(held, _pin(held_store, "self"))
    _connect(_pin(held_richer, "ReturnValue", is_input=False),
             _pin(held_store, "Reserve"))
    _connect(BEL.find_then_pin(takes_ammo), _pin(held_store, "execute"))
    held_mark = _at(ed.add_set_member_variable_node("Credited"), 4600, -700)
    _set(held_mark, "Credited", "true")
    _connect(BEL.find_then_pin(held_store), _pin(held_mark, "execute"))

    # --- fallback: the first carried weapon that takes ammunition ------------
    # Reached when nothing is held, or when what is held is the pistol. Walking
    # over shells with the pistol out still has to pay into something, or the
    # drop is lost for the sake of a rule about which gun is out.
    inv = _at(ed.add_get_member_variable_node("Inventory", WEAPON_COMP_CLASS_PATH),
              2560, 420)
    _connect(as_weapon, _pin(inv, "self"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(loop, 2840, 0)
    _connect(_pin(inv, "Inventory", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_else_pin(has_gun), _loose_pin(loop, "Exec"))
    _connect(BEL.find_else_pin(takes_ammo), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    uses, uses_n = _prop(ed, "UsesAmmo", item, 3140, 300)
    done_get = _at(ed.add_get_member_variable_node("Credited"), 3140, 440)
    fresh = _at(_node(ed, FN_NOT), 3380, 440)
    _connect(_pin(done_get, "Credited", is_input=False), _pin(fresh, "A"))
    wants = _at(_node(ed, FN_AND), 3620, 360)
    _connect(uses, _pin(wants, "A"))
    _connect(_pin(fresh, "ReturnValue", is_input=False), _pin(wants, "B"))

    give = _at(ed.add_branch_node(), 3880, 0)
    _connect(_pin(wants, "ReturnValue", is_input=False), _pin(give, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(give, "execute"))

    item_res, item_res_n = _prop(ed, "Reserve", item, 4140, 300)
    shells = _at(ed.add_get_member_variable_node("Shells"), 4140, 440)
    richer = _at(_node(ed, FN_ADD_II), 4400, 300)
    _connect(item_res, _pin(richer, "A"))
    _connect(_pin(shells, "Shells", is_input=False), _pin(richer, "B"))
    store = _at(ed.add_set_member_variable_node("Reserve", ITEM_CLASS_PATH), 4660, 0)
    _connect(item, _pin(store, "self"))
    _connect(_pin(richer, "ReturnValue", is_input=False), _pin(store, "Reserve"))
    _connect(BEL.find_then_pin(give), _pin(store, "execute"))

    mark = _at(ed.add_set_member_variable_node("Credited"), 4920, 0)
    _set(mark, "Credited", "true")
    _connect(BEL.find_then_pin(store), _pin(mark, "execute"))

    # --- and only then vanish -----------------------------------------------
    # Gated on Credited rather than destroyed unconditionally at the Completed
    # pin: a player with no shotgun who walks over the shells has not picked
    # anything up, and the drop has to still be there when they find one.
    took_get = _at(ed.add_get_member_variable_node("Credited"), 5180, 300)
    took = _at(ed.add_branch_node(), 5440, 0)
    _connect(_pin(took_get, "Credited", is_input=False), _pin(took, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(took, "execute"))
    _connect(BEL.find_then_pin(held_mark), _pin(took, "execute"))
    gone = _at(_node(ed, FN_DESTROY), 5700, 0)
    _connect(BEL.find_then_pin(took), _pin(gone, "execute"))

    ed.add_comment_to_nodes(
        f"{AMMO_DROP_SHELLS} shells, taken by walking within "
        f"{AMMO_PICKUP_RADIUS:.0f} cm of them. The distance is measured HERE "
        "rather than in the weapon component's Tick, so the cost is one Tick "
        "per dropped pickup instead of a GetAllActorsOfClass sweep every frame "
        "whether anything has been dropped or not. The shells go to the weapon "
        "in hand when that weapon takes ammunition, and otherwise to the first "
        "carried one that does -- with four of five weapons using ammunition, "
        "\"first in the inventory\" would mean the shotgun in slot 0, always. "
        "Credited is the break ForEachLoop does not have.",
        [life, turn, delta, spin, pawn, there, here, gap, near, reached, comp,
         as_weapon_n, held_get, armed, has_gun, held_uses_n, takes_ammo,
         held_res_n, held_shells, held_richer, held_store, held_mark,
         inv, loop, uses_n, done_get, fresh, wants, give,
         item_res_n, shells, richer, store, mark, took_get, took, gone])

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_AmmoPickup failed to compile")
    _apply_defaults(bp, {"Shells": AMMO_DROP_SHELLS, "Credited": False})
    _log(f"built {AMMO_BP_PATH} ({AMMO_DROP_SHELLS} shells, "
         f"{AMMO_PICKUP_RADIUS:.0f} cm, {AMMO_PICKUP_LIFETIME:.0f}s)")
    return bp


# ─── BP_HealthComponent ──────────────────────────────────────────────────────

def ensure_game_mode_vars():
    """Put the world-scoped counters and the death flag on the GameMode.

    Variables only -- no graph. The GameMode is chosen because Blueprints have
    no statics and each of these has to be one value per session, shared by
    every wanderer's health component and read by the HUD:

        NpcSpawnCount  the next number to hand a wanderer, so the log and the
                       floating bars agree on who is who;
        NpcKillCount   what the corner of the HUD shows and what the death menu
                       quotes as the final score;
        PlayerDead     the one flag the death menu is drawn from;
        DebugMode      whether the developer overlays are on. Here rather than
                       on the HUD that toggles it because the *weapon
                       component* is the other thing that reads it, and a HUD
                       variable is not reachable from a component.

    All three outlive every actor that touches them -- the player's own health
    component is destroyed with the player, so the score cannot live there.

    Declared here rather than in build_graphics_menu.py (which owns the other
    edit to this asset, HUDClass) because they are part of the NPC and player
    life cycle, and this file is what writes them.
    """
    eas = _assets()
    bp = eas.load_asset(GAME_MODE_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {GAME_MODE_BP_PATH}")
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{GAME_MODE_BP_PATH} has no EventGraph")
    for name in (SPAWN_COUNT_VAR, KILL_COUNT_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("int"))
    for name in (PLAYER_DEAD_VAR, DEBUG_MODE_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonGameMode failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"{GAME_MODE_BP_PATH}: {SPAWN_COUNT_VAR}, {KILL_COUNT_VAR}, "
         f"{PLAYER_DEAD_VAR}, {DEBUG_MODE_VAR} ready")
    return bp


def _author_kill_count(ed, exec_in, x0, y0):
    """Count this death on the GameMode, if a pellet is what caused it.

    Spliced between "this one despawns" and the respawn, so it sees exactly the
    deaths that are a wanderer's. The guard is the point: the safety net writes
    Health to 0 for anything that falls under the world, and the same death path
    runs for it -- counting that as a kill would inflate the score every time
    the terrain lost someone. Only a pellet sets DamagedByPlayer.

    Returns the exec pins to carry on from -- both of them, because a wanderer
    that died unshot still has to be replaced.
    """
    earned = _at(ed.add_get_member_variable_node(DAMAGED_BY_PLAYER_VAR), x0, y0 + 240)
    shot = _at(ed.add_branch_node(), x0 + 240, y0)
    _connect(_pin(earned, DAMAGED_BY_PLAYER_VAR, is_input=False), _pin(shot, "Condition"))
    _connect(exec_in, _pin(shot, "execute"))

    mode = _at(_node(ed, FN_GET_GAME_MODE), x0 + 480, y0 + 240)
    as_mode = _at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 720, y0)
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(BEL.find_then_pin(shot), _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    tally = _at(ed.add_get_member_variable_node(KILL_COUNT_VAR, GAME_MODE_CLASS_PATH),
                x0 + 960, y0 + 240)
    _connect(mode_out, _pin(tally, "self"))
    one_more = _at(_node(ed, FN_ADD_II), x0 + 1200, y0 + 240)
    _connect(_pin(tally, KILL_COUNT_VAR, is_input=False), _pin(one_more, "A"))
    _set(one_more, "B", 1)
    write = _at(ed.add_set_member_variable_node(KILL_COUNT_VAR, GAME_MODE_CLASS_PATH),
                x0 + 1440, y0)
    _connect(mode_out, _pin(write, "self"))
    _connect(_pin(one_more, "ReturnValue", is_input=False), _pin(write, KILL_COUNT_VAR))
    _connect(BEL.find_then_pin(as_mode), _pin(write, "execute"))

    # --- and the shells it drops --------------------------------------------
    # On the same arm as the count, and for the same reason: a wanderer the
    # terrain swallowed was not killed, and paying the player for it would turn
    # the safety net into an ammunition supply.
    #
    # Spawned before the owner is destroyed, at the owner's feet plus a lift --
    # the corpse's origin is at the capsule centre, so a drop placed exactly
    # there is inside the body on the frame it appears.
    corpse = _at(_node(ed, FN_GET_OWNER), x0 + 1680, y0 + 380)
    fell_at = _at(_node(ed, FN_ACTOR_LOC), x0 + 1920, y0 + 380)
    _connect(_pin(corpse, "ReturnValue", is_input=False), _pin(fell_at, "self"))
    lifted = _at(_node(ed, FN_ADD_VV), x0 + 2160, y0 + 380)
    _connect(_pin(fell_at, "ReturnValue", is_input=False), _pin(lifted, "A"))
    _connect(_vec(ed, 0.0, 0.0, AMMO_PICKUP_LIFT, x0 + 1920, y0 + 520),
             _pin(lifted, "B"))
    where = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 2400, y0 + 380)
    _connect(_pin(lifted, "ReturnValue", is_input=False), _pin(where, "Location"))
    # A struct pin cannot be given a literal, and an unset Scale pin compiles to
    # the zero vector -- which spawns the pickup at zero size, invisible.
    _connect(_vec(ed, 1.0, 1.0, 1.0, x0 + 2160, y0 + 560), _pin(where, "Scale"))

    ammo_cls = _at(ed.add_get_member_variable_node("AmmoClass"), x0 + 2400, y0 + 240)
    drop = _at(_palette(ed, NODE_SPAWN), x0 + 2660, y0)
    _connect(_pin(ammo_cls, "AmmoClass", is_input=False), _pin(drop, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(drop, "SpawnTransform"))
    _set(drop, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(write), _pin(drop, "execute"))

    ed.add_comment_to_nodes(
        f"One kill, counted on the GameMode where it outlives the wanderer that "
        f"earned it, and {AMMO_DROP_SHELLS} shells left where it fell. "
        "DamagedByPlayer is the guard on both: the safety net kills anything "
        "that falls under the world through this same path, and nobody shot it.",
        [earned, shot, mode, as_mode, tally, one_more, write, corpse, fell_at,
         lifted, where, ammo_cls, drop])

    gun_exits = _author_gun_drop(ed, _pin(lifted, "ReturnValue", is_input=False),
                                 BEL.find_then_pin(drop), x0, y0 + 1000)
    return gun_exits + (_pin(as_mode, "CastFailed", is_input=False),
                        BEL.find_else_pin(shot))


def _author_gun_drop(ed, at, exec_in, x0, y0):
    """One kill in ten also leaves a weapon: which one is a second uniform draw.

    Two decisions, deliberately separate. Whether anything drops is one roll
    against GUN_DROP_CHANCE; *what* drops is an index into DropClasses. Keeping
    them apart means the rate and the table are tuned independently -- adding a
    fourth findable weapon changes what a drop is worth and not how often one
    happens, which is not true of the obvious alternative (one roll into a
    weighted table).

    DropClasses is an array rather than three variables and a Switch for the
    same reason: a Switch on an integer would have to grow a pin per weapon,
    and the length of the array is already the only number the draw needs.

    Two guards on the roll, folded into one condition because both are plain
    reads with nothing behind them:

        lucky    the 10%.
        stocked  the array is not empty. Without it RandomIntegerInRange(0, -1)
                 feeds Array_Get an index into nothing, which is an access-none
                 per kill on any build where main() has not filled the table.

    The spawned actor is cast to BP_WeaponItem so Dropped can be set on it, and
    Dropped is the entire interface: from that moment it is an ordinary weapon
    lying in the forest, and the E key that picks up a gun the player threw
    away is the same code that picks this one up. Nothing in _author_pickup
    knows these exist.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    roll = keep(_at(_node(ed, FN_RANDOM_FLOAT), x0 + 2400, y0 + 300))
    _set(roll, "Min", 0.0)
    _set(roll, "Max", 1.0)
    lucky = keep(_at(_node(ed, FN_LESS_FF), x0 + 2640, y0 + 300))
    _connect(_pin(roll, "ReturnValue", is_input=False), _pin(lucky, "A"))
    _set(lucky, "B", GUN_DROP_CHANCE)

    table = keep(_at(ed.add_get_member_variable_node("DropClasses"),
                     x0 + 2400, y0 + 440))
    table_out = _pin(table, "DropClasses", is_input=False)
    how_many = keep(_at(_node(ed, FN_ARR_LEN), x0 + 2640, y0 + 440))
    _connect(table_out, _pin(how_many, "TargetArray"))
    stocked = keep(_at(_node(ed, FN_GREATER_II), x0 + 2880, y0 + 440))
    _connect(_pin(how_many, "ReturnValue", is_input=False), _pin(stocked, "A"))
    _set(stocked, "B", 0)

    worth = keep(_at(_node(ed, FN_AND), x0 + 3120, y0 + 360))
    _connect(_pin(lucky, "ReturnValue", is_input=False), _pin(worth, "A"))
    _connect(_pin(stocked, "ReturnValue", is_input=False), _pin(worth, "B"))
    rare = keep(_at(ed.add_branch_node(), x0 + 3360, y0))
    _connect(_pin(worth, "ReturnValue", is_input=False), _pin(rare, "Condition"))
    _connect(exec_in, _pin(rare, "execute"))

    # RandomIntegerInRange is inclusive at both ends, so the top is length - 1.
    top = keep(_at(_node(ed, FN_SUB_II), x0 + 2880, y0 + 580))
    _connect(_pin(how_many, "ReturnValue", is_input=False), _pin(top, "A"))
    _set(top, "B", 1)
    which = keep(_at(_node(ed, FN_RAND_INT), x0 + 3120, y0 + 580))
    _set(which, "Min", 0)
    _connect(_pin(top, "ReturnValue", is_input=False), _pin(which, "Max"))
    pick = keep(_at(_node(ed, FN_ARR_GET), x0 + 3360, y0 + 580))
    _connect(table_out, _pin(pick, "TargetArray"))
    _connect(_pin(which, "ReturnValue", is_input=False), _pin(pick, "Index"))

    # Clear of the shells, which are already sitting on the corpse: two pickups
    # at the same point read as one object and the player collects the ammo
    # without ever seeing the gun.
    beside = keep(_at(_node(ed, FN_ADD_VV), x0 + 3620, y0 + 300))
    _connect(at, _pin(beside, "A"))
    _connect(_vec(ed, GUN_DROP_FORWARD, 0.0, 0.0, x0 + 3360, y0 + 440),
             _pin(beside, "B"))
    where = keep(_at(_node(ed, FN_MAKE_TRANSFORM), x0 + 3880, y0 + 300))
    _connect(_pin(beside, "ReturnValue", is_input=False), _pin(where, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0, x0 + 3620, y0 + 480), _pin(where, "Scale"))

    spawn = keep(_at(_palette(ed, NODE_SPAWN), x0 + 4140, y0))
    _connect(_pin(pick, "Item", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(rare), _pin(spawn, "execute"))

    # DropClasses is typed as class-of-Actor, for the same reason AmmoClass is:
    # this component has to compile in a pass where BP_WeaponItem's generated
    # class is not available to type a pin against. The cost is this cast.
    as_item = keep(_at(_palette(ed, NODE_CAST_ITEM), x0 + 4400, y0))
    _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(as_item, "Object"))
    _connect(BEL.find_then_pin(spawn), _pin(as_item, "execute"))
    loose = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
                     x0 + 4680, y0))
    _connect(_loose_pin(as_item, "AsBPWeaponItem", is_input=False),
             _pin(loose, "self"))
    _set(loose, "Dropped", "true")
    _connect(BEL.find_then_pin(as_item), _pin(loose, "execute"))

    ed.add_comment_to_nodes(
        f"{GUN_DROP_CHANCE * 100:.0f}% of counted kills leave a weapon, drawn "
        f"uniformly from DropClasses -- so each of the three is about a "
        f"1-in-{int(round(1.0 / GUN_DROP_CHANCE)) * len(DROP_DISPLAYS)} drop. "
        "Dropped=true is the whole handover: from here it is an ordinary "
        "weapon on the ground and E picks it up with no new code.",
        made)
    return (BEL.find_then_pin(loose),
            _pin(as_item, "CastFailed", is_input=False),
            BEL.find_else_pin(rare))


def _author_death_collapse(ed, exec_ins, x0, y0):
    """The body goes down, physically, and stops being in the way.

    Shared by the player and by every wanderer, which is the point: there is
    one answer in this project to "what does dying look like", and both arms of
    the death branch walk into it. See the RAGDOLL_PROFILE comment for why it
    is a ragdoll and not a clip -- in short, there is no clip, here or in Epic's
    content, that ends with a body on the ground.

    Four calls, in this order and for these reasons:

      1. DisableMovement. CharacterMovement is still driving the capsule, and a
         corpse whose capsule is walking gets dragged along by the mesh's
         attachment. Movement, not input: the HUD polls the restart key off the
         same PlayerController and turning input off risks it.
      2. the capsule stops colliding. It is the capsule -- not the mesh -- that
         blocks the player and that blocks the pellets (see make_shootable), so
         switching it off is both halves of "a corpse is not in the way": you
         can walk through it and you cannot waste ammunition on it.
      3. the mesh takes the Ragdoll profile, which is what makes the bodies
         collide with the terrain and ignore Pawn. Without it the mesh keeps
         CharacterMesh, which collides with nothing, and the ragdoll falls
         through the world.
      4. only then simulate. Set the profile after simulation starts and the
         first frame is resolved against the old responses.

    Returns the exec to carry on with.
    """
    owner = _at(_node(ed, FN_GET_OWNER), x0, y0 + 240)
    as_char = _at(_palette(ed, NODE_CAST_CHARACTER), x0 + 240, y0)
    _connect(_pin(owner, "ReturnValue", is_input=False), _pin(as_char, "Object"))
    for tail in exec_ins:
        _connect(tail, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    movement = _at(ed.add_get_member_variable_node("CharacterMovement",
                                                   "/Script/Engine.Character"),
                   x0 + 480, y0 + 240)
    _connect(char_out, _pin(movement, "self"))
    stop = _at(_node(ed, FN_DISABLE_MOVEMENT), x0 + 720, y0)
    _connect(_pin(movement, "CharacterMovement", is_input=False), _pin(stop, "self"))
    _connect(BEL.find_then_pin(as_char), _pin(stop, "execute"))

    capsule = _at(ed.add_get_member_variable_node("CapsuleComponent",
                                                  "/Script/Engine.Character"),
                  x0 + 960, y0 + 240)
    _connect(char_out, _pin(capsule, "self"))
    intangible = _at(_node(ed, FN_SET_COLLISION), x0 + 1200, y0)
    _connect(_pin(capsule, "CapsuleComponent", is_input=False),
             _pin(intangible, "self"))
    _set(intangible, "NewType", "NoCollision")
    _connect(BEL.find_then_pin(stop), _pin(intangible, "execute"))

    mesh = _at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
               x0 + 1440, y0 + 240)
    _connect(char_out, _pin(mesh, "self"))
    mesh_out = _pin(mesh, "Mesh", is_input=False)

    loosen = _at(_node(ed, FN_SET_PROFILE), x0 + 1680, y0)
    _connect(mesh_out, _pin(loosen, "self"))
    _set(loosen, "InCollisionProfileName", RAGDOLL_PROFILE)
    _connect(BEL.find_then_pin(intangible), _pin(loosen, "execute"))

    limp = _at(_node(ed, FN_SIMULATE_ALL), x0 + 1920, y0)
    _connect(mesh_out, _pin(limp, "self"))
    _set(limp, "bNewSimulate", "true")
    _connect(BEL.find_then_pin(loosen), _pin(limp, "execute"))

    ed.add_comment_to_nodes(
        f"Dying, for the player and for every wanderer alike: stop the "
        f"movement, switch the capsule off so the body is neither an obstacle "
        f"nor a target, put the mesh on the {RAGDOLL_PROFILE} profile and "
        f"simulate every body in the physics asset. There is no death clip in "
        f"this project to play instead -- Meshy generates a walk and a run, and "
        f"Epic's six MM_Death_* clips are staggers that end on their feet.",
        [owner, as_char, movement, stop, capsule, intangible, mesh, loosen, limp])

    # The cast failure is carried, not dropped: a thing with no Character under
    # it cannot be ragdolled, but the player still has to get a menu and a
    # wanderer still has to be cleaned up.
    return (BEL.find_then_pin(limp),
            _pin(as_char, "CastFailed", is_input=False))


def _author_corpse(ed, exec_ins, x0, y0):
    """Everything a dead wanderer has to stop doing, and when it goes away.

    The collapse is shared (see _author_death_collapse); this is the half that
    is only true of an NPC.

    The AI controller is DESTROYED rather than told to stop. A wanderer's whole
    behaviour -- the chase, the melee, the growls -- is one self-re-entering
    loop on its controller, and none of it consults the pawn's health: a corpse
    whose controller survived would keep hitting the player from the floor.
    Destroying an AController unpossesses it on the way out, which is what
    stops the movement request as well, and it leaves nothing behind to leak
    one controller per kill over a session. UnPossess alone would close the
    loop's possession gate too, but it would leave that controller running its
    Delay for the rest of the game.

    This used to be a K2_DestroyActor on the owner, on the same frame. The
    corpse now lies there for CORPSE_SECONDS, and SetLifeSpan is the engine's
    own timer for exactly that -- a Delay here would be a latent action on a
    component belonging to the actor it is waiting to destroy.
    """
    owner = _at(_node(ed, FN_GET_OWNER), x0, y0 + 240)
    owner_out = _pin(owner, "ReturnValue", is_input=False)
    as_pawn = _at(_palette(ed, NODE_CAST_PAWN), x0 + 240, y0)
    _connect(owner_out, _pin(as_pawn, "Object"))
    for tail in exec_ins:
        _connect(tail, _pin(as_pawn, "execute"))

    # GetController, not the Controller member: APawn::Controller is not marked
    # BlueprintReadOnly, and a get-variable node for it compiles as a warning
    # today and an error in a future release.
    brain = _at(_node(ed, FN_GET_CONTROLLER), x0 + 480, y0 + 240)
    _connect(_loose_pin(as_pawn, "AsPawn", is_input=False), _pin(brain, "self"))
    brain_out = _pin(brain, "ReturnValue", is_input=False)
    possessed = _at(_node(ed, FN_IS_VALID), x0 + 720, y0 + 240)
    _connect(brain_out, _pin(possessed, "Object"))
    has_brain = _at(ed.add_branch_node(), x0 + 960, y0)
    _connect(_pin(possessed, "ReturnValue", is_input=False), _pin(has_brain, "Condition"))
    _connect(BEL.find_then_pin(as_pawn), _pin(has_brain, "execute"))

    lobotomy = _at(_node(ed, FN_DESTROY), x0 + 1200, y0)
    _connect(brain_out, _pin(lobotomy, "self"))
    _connect(BEL.find_then_pin(has_brain), _pin(lobotomy, "execute"))

    rot = _at(_node(ed, FN_LIFESPAN), x0 + 1440, y0)
    _connect(owner_out, _pin(rot, "self"))
    _set(rot, "InLifespan", CORPSE_SECONDS)
    for tail in (BEL.find_then_pin(lobotomy),
                 BEL.find_else_pin(has_brain),
                 _pin(as_pawn, "CastFailed", is_input=False)):
        _connect(tail, _pin(rot, "execute"))

    ed.add_comment_to_nodes(
        f"A dead wanderer: destroy the AI controller -- the chase, the melee "
        f"and the growls are one loop on it, and none of them ask whether the "
        f"pawn is alive -- and give the body {CORPSE_SECONDS:.0f} s of lifespan. "
        f"The kill has already been counted and the replacement already spawned "
        f"by the time this runs, so the pack is back to strength while the "
        f"corpse is still falling.",
        [owner, as_pawn, brain, possessed, has_brain, lobotomy, rot])
    return BEL.find_then_pin(rot)


def _author_player_death(ed, exec_ins, x0, y0):
    """The player is down: wait for the fall, then pause and open the menu.

    This is the DespawnOnDeath-false arm, and it now starts from a body that is
    already a ragdoll -- so there is nothing here that has to keep it down. The
    bug this used to have was the opposite one: a dynamic montage of
    MM_Death_Front_01 blended OUT after 1.1 s, the locomotion state machine
    underneath took the pose back, and the player was on his feet a whole
    second before the pause arrived to freeze him there.

    The Delay is still here and still comes before the pause, for the reason it
    always did -- pausing stops physics as well as everything else, so pausing
    early freezes the body mid-topple.

    PlayerDead is set on the GameMode rather than here because the HUD is what
    draws the menu and the HUD has no route to this component -- it would have
    to find the player's pawn, find this component and cast to it, every frame,
    to read one bool that the GameMode already exists to hold.
    """
    wait = _at(_node(ed, FN_DELAY), x0, y0)
    _set(wait, "Duration", DEATH_PAUSE_SECONDS)
    for tail in exec_ins:
        _connect(tail, _pin(wait, "execute"))

    mode = _at(_node(ed, FN_GET_GAME_MODE), x0 + 240, y0 + 240)
    as_mode = _at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 480, y0)
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(BEL.find_then_pin(wait), _pin(as_mode, "execute"))
    tell = _at(ed.add_set_member_variable_node(PLAYER_DEAD_VAR, GAME_MODE_CLASS_PATH),
               x0 + 720, y0)
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(tell, "self"))
    _set(tell, PLAYER_DEAD_VAR, "true")
    _connect(BEL.find_then_pin(as_mode), _pin(tell, "execute"))

    # Say so in the log, with the score. A paused game and a game where the
    # death path silently did nothing look exactly the same from outside, and
    # the menu that would tell them apart is drawn on a canvas that a headless
    # run has nobody looking at.
    score = _at(ed.add_get_member_variable_node(KILL_COUNT_VAR,
                                                GAME_MODE_CLASS_PATH),
                x0 + 720, y0 + 400)
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(score, "self"))
    score_str = _at(_node(ed, FN_INT_TO_STR), x0 + 960, y0 + 400)
    _connect(_pin(score, KILL_COUNT_VAR, is_input=False), _pin(score_str, "InInt"))
    dead_line = _at(_node(ed, FN_CONCAT), x0 + 1200, y0 + 400)
    _set(dead_line, "A", DEAD_LOG_PREFIX)
    _connect(_pin(score_str, "ReturnValue", is_input=False), _pin(dead_line, "B"))
    say_dead = _at(_node(ed, FN_PRINT), x0 + 1200, y0)
    _connect(_pin(dead_line, "ReturnValue", is_input=False), _pin(say_dead, "InString"))
    # Log only: the menu is what says it on screen, and it says it better.
    _set(say_dead, "bPrintToScreen", "false")
    _set(say_dead, "bPrintToLog", "true")
    _set(say_dead, "Duration", 0.0)
    _connect(BEL.find_then_pin(tell), _pin(say_dead, "execute"))

    # Pause last, and on every arm: with the flag set the HUD draws the menu,
    # and with the game paused nothing moves behind it. The HUD polls its
    # restart key from the PlayerController, which ticks through a pause.
    freeze = _at(_node(ed, FN_SET_PAUSED), x0 + 1460, y0)
    _set(freeze, "bPaused", "true")
    for tail in (BEL.find_then_pin(say_dead),
                 _pin(as_mode, "CastFailed", is_input=False)):
        _connect(tail, _pin(freeze, "execute"))

    ed.add_comment_to_nodes(
        f"The player's death, from a body that is already on the floor: wait "
        f"{DEATH_PAUSE_SECONDS}s for the ragdoll to settle, tell the GameMode "
        f"and pause. The pause stops physics too, so the body stays exactly as "
        f"it fell until the level reopens -- which is the fix for the player "
        f"standing back up. BP_GraphicsMenuHUD draws the menu off "
        f"{PLAYER_DEAD_VAR} and restarts the level from it.",
        [wait, mode, as_mode, tell, score, score_str, dead_line, say_dead, freeze])


def _author_random_sound(ed, var_name, at_pin, exec_in, x0, y0):
    """Play a random element of the ``var_name`` sound array at ``at_pin``.

    Returns ``(nodes, then_pin)``. Guarded on the array's own length, because
    RandomIntegerInRange(0, -1) into Array_Get is an access-none rather than
    silence -- and an empty array is the normal state of a checkout that has
    not run Scripts/make_creature_sounds.py yet.

    The same shape exists in build_npc_blueprints.py. Two copies rather than a
    shared module because the two files each carry their own _pin/_connect/_set
    authoring helpers, and hoisting one function would mean hoisting those.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    table = keep(_at(ed.add_get_member_variable_node(var_name), x0, y0 + 240))
    table_out = _pin(table, var_name, is_input=False)
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 240, y0 + 240))
    _connect(table_out, _pin(count, "TargetArray"))
    stocked = keep(_at(_node(ed, FN_GREATER_II), x0 + 480, y0 + 240))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(stocked, "A"))
    _set(stocked, "B", 0)

    have = keep(_at(ed.add_branch_node(), x0 + 720, y0))
    _connect(_pin(stocked, "ReturnValue", is_input=False), _pin(have, "Condition"))
    _connect(exec_in, _pin(have, "execute"))

    top = keep(_at(_node(ed, FN_SUB_II), x0 + 720, y0 + 240))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(top, "A"))
    _set(top, "B", 1)
    which = keep(_at(_node(ed, FN_RAND_INT), x0 + 960, y0 + 240))
    _set(which, "Min", 0)
    _connect(_pin(top, "ReturnValue", is_input=False), _pin(which, "Max"))
    pick = keep(_at(_node(ed, FN_ARR_GET), x0 + 1200, y0 + 240))
    _connect(table_out, _pin(pick, "TargetArray"))
    _connect(_pin(which, "ReturnValue", is_input=False), _pin(pick, "Index"))

    play = keep(_at(_node(ed, FN_PLAY_SOUND), x0 + 1440, y0))
    _connect(_pin(pick, "Item", is_input=False), _pin(play, "Sound"))
    _connect(at_pin, _pin(play, "Location"))
    _connect(BEL.find_then_pin(have), _pin(play, "execute"))

    join = keep(_at(ed.add_branch_node(), x0 + 1700, y0))
    _set(join, "Condition", "true")
    _connect(BEL.find_then_pin(play), _pin(join, "execute"))
    _connect(BEL.find_else_pin(have), _pin(join, "execute"))
    return made, BEL.find_then_pin(join)


def _author_hit_reaction(ed, exec_in, x0, y0):
    """Took a hit and lived: flinch. Returns ``(nodes, then_pin)``.

    Wired onto the **False** arm of the death branch, which is what makes
    "survived" free: the frame a target's Health reaches zero the other arm is
    taken, so nothing can ragdoll and stagger at the same time.

        Health < PrevHealth?                      something hurt us this frame
          -> world time past NextReactTime?       not still mid-flinch
            -> HitReactions is not empty?         this body has clips
              -> which way did it come from?      -> ReactIndex
              -> play it into HitSlot, upper body
              -> NextReactTime = now + cooldown
        (every no, and a non-Character owner) ---> PrevHealth = Health

    WHICH CLIP. The six are Epic's directional set (three Fronts, one each of
    Back/Left/Right -- see HIT_REACTION_CLIPS) and the pick is two dot products,
    no angles:

        f = LastHitFrom . owner forward     f >= |r|        -> Front, one of 3
        r = LastHitFrom . owner right       -f > |r|        -> Back
                                            |f| < r         -> Right
                                            |f| < -r        -> Left

    LastHitFrom is written by whoever did the damage and points from the victim
    toward the source. Nobody is obliged to write it: an unattributed hit leaves
    it at the zero vector, both dots come out 0, and `>=` on the forward test is
    what makes that land on Front -- the direction with three clips and the one
    a player is most likely to be facing anyway.

    THE INDEX IS CLAMPED against the array's real length rather than trusted.
    The base indices are positions in HIT_REACTION_CLIPS, and a body whose
    retarget has not run carries fewer than six clips (or none -- hence the
    length guard above it); an unclamped Back on a three-clip array is an
    Array_Get off the end.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # --- did Health go down this frame? --------------------------------------
    now_h = keep(_at(ed.add_get_member_variable_node("Health"), x0, y0 + 240))
    was_h = keep(_at(ed.add_get_member_variable_node(PREV_HEALTH_VAR), x0, y0 + 360))
    dropped = keep(_at(_node(ed, FN_LESS_FF), x0 + 240, y0 + 240))
    _connect(_pin(now_h, "Health", is_input=False), _pin(dropped, "A"))
    _connect(_pin(was_h, PREV_HEALTH_VAR, is_input=False), _pin(dropped, "B"))
    took = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(dropped, "ReturnValue", is_input=False), _pin(took, "Condition"))
    _connect(exec_in, _pin(took, "execute"))

    # --- is the last one finished? -------------------------------------------
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 480, y0 + 380))
    now_out = _pin(now, "ReturnValue", is_input=False)
    due = keep(_at(ed.add_get_member_variable_node(NEXT_REACT_VAR), x0 + 480, y0 + 500))
    ready = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0 + 380))
    _connect(now_out, _pin(ready, "A"))
    _connect(_pin(due, NEXT_REACT_VAR, is_input=False), _pin(ready, "B"))
    cooled = keep(_at(ed.add_branch_node(), x0 + 960, y0))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(cooled, "Condition"))
    _connect(BEL.find_then_pin(took), _pin(cooled, "execute"))

    # --- does this body have any reactions at all? ---------------------------
    clips = keep(_at(ed.add_get_member_variable_node(HIT_REACTIONS_VAR),
                     x0 + 960, y0 + 620))
    clips_out = _pin(clips, HIT_REACTIONS_VAR, is_input=False)
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 1200, y0 + 620))
    _connect(clips_out, _pin(count, "TargetArray"))
    count_out = _pin(count, "ReturnValue", is_input=False)
    stocked = keep(_at(_node(ed, FN_GREATER_II), x0 + 1440, y0 + 620))
    _connect(count_out, _pin(stocked, "A"))
    _set(stocked, "B", 0)
    have = keep(_at(ed.add_branch_node(), x0 + 1680, y0))
    _connect(_pin(stocked, "ReturnValue", is_input=False), _pin(have, "Condition"))
    _connect(BEL.find_then_pin(cooled), _pin(have, "execute"))

    # --- which way did it come from? -----------------------------------------
    owner = keep(_at(_node(ed, FN_GET_OWNER), x0 + 1680, y0 + 760))
    owner_out = _pin(owner, "ReturnValue", is_input=False)
    fwd = keep(_at(_node(ed, FN_ACTOR_FORWARD), x0 + 1920, y0 + 760))
    _connect(owner_out, _pin(fwd, "self"))
    rgt = keep(_at(_node(ed, FN_ACTOR_RIGHT), x0 + 1920, y0 + 880))
    _connect(owner_out, _pin(rgt, "self"))
    came = keep(_at(ed.add_get_member_variable_node(LAST_HIT_FROM_VAR),
                    x0 + 1920, y0 + 1000))
    came_out = _pin(came, LAST_HIT_FROM_VAR, is_input=False)

    ahead = keep(_at(_node(ed, FN_DOT_VV), x0 + 2160, y0 + 760))
    _connect(came_out, _pin(ahead, "A"))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(ahead, "B"))
    ahead_out = _pin(ahead, "ReturnValue", is_input=False)
    beside = keep(_at(_node(ed, FN_DOT_VV), x0 + 2160, y0 + 900))
    _connect(came_out, _pin(beside, "A"))
    _connect(_pin(rgt, "ReturnValue", is_input=False), _pin(beside, "B"))
    beside_out = _pin(beside, "ReturnValue", is_input=False)

    fore_aft = keep(_at(_node(ed, FN_ABS), x0 + 2400, y0 + 760))
    _connect(ahead_out, _pin(fore_aft, "A"))
    lateral = keep(_at(_node(ed, FN_ABS), x0 + 2400, y0 + 900))
    _connect(beside_out, _pin(lateral, "A"))
    axis = keep(_at(_node(ed, FN_GE_FF), x0 + 2640, y0 + 760))
    _connect(_pin(fore_aft, "ReturnValue", is_input=False), _pin(axis, "A"))
    _connect(_pin(lateral, "ReturnValue", is_input=False), _pin(axis, "B"))
    front_back = keep(_at(ed.add_branch_node(), x0 + 2880, y0))
    _connect(_pin(axis, "ReturnValue", is_input=False), _pin(front_back, "Condition"))
    _connect(BEL.find_then_pin(have), _pin(front_back, "execute"))

    # Front, and one of the three Epic authored. The random draw is the only
    # thing that keeps a firefight from looking like one animation on a loop,
    # and Front is where it is worth spending because it is the common case.
    facing = keep(_at(_node(ed, FN_GE_FF), x0 + 2880, y0 + 380))
    _connect(ahead_out, _pin(facing, "A"))
    _set(facing, "B", 0.0)
    from_front = keep(_at(ed.add_branch_node(), x0 + 3120, y0 - 260))
    _connect(_pin(facing, "ReturnValue", is_input=False), _pin(from_front, "Condition"))
    _connect(BEL.find_then_pin(front_back), _pin(from_front, "execute"))

    spread = keep(_at(_node(ed, FN_RAND_INT), x0 + 3120, y0 + 380))
    _set(spread, "Min", 0)
    _set(spread, "Max", HIT_DIR_FRONT[1] - 1)
    front_idx = keep(_at(_node(ed, FN_ADD_II), x0 + 3360, y0 + 380))
    _connect(_pin(spread, "ReturnValue", is_input=False), _pin(front_idx, "A"))
    _set(front_idx, "B", HIT_DIR_FRONT[0])

    arms = []
    pick_front = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                          x0 + 3600, y0 - 400))
    _connect(_pin(front_idx, "ReturnValue", is_input=False),
             _pin(pick_front, REACT_INDEX_VAR))
    _connect(BEL.find_then_pin(from_front), _pin(pick_front, "execute"))
    arms.append(BEL.find_then_pin(pick_front))

    pick_back = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                         x0 + 3600, y0 - 180))
    _set(pick_back, REACT_INDEX_VAR, HIT_DIR_BACK[0])
    _connect(BEL.find_else_pin(from_front), _pin(pick_back, "execute"))
    arms.append(BEL.find_then_pin(pick_back))

    to_right = keep(_at(_node(ed, FN_GE_FF), x0 + 2880, y0 + 500))
    _connect(beside_out, _pin(to_right, "A"))
    _set(to_right, "B", 0.0)
    from_side = keep(_at(ed.add_branch_node(), x0 + 3120, y0 + 40))
    _connect(_pin(to_right, "ReturnValue", is_input=False), _pin(from_side, "Condition"))
    _connect(BEL.find_else_pin(front_back), _pin(from_side, "execute"))

    pick_right = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                          x0 + 3600, y0 + 40))
    _set(pick_right, REACT_INDEX_VAR, HIT_DIR_RIGHT[0])
    _connect(BEL.find_then_pin(from_side), _pin(pick_right, "execute"))
    arms.append(BEL.find_then_pin(pick_right))

    pick_left = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                         x0 + 3600, y0 + 260))
    _set(pick_left, REACT_INDEX_VAR, HIT_DIR_LEFT[0])
    _connect(BEL.find_else_pin(from_side), _pin(pick_left, "execute"))
    arms.append(BEL.find_then_pin(pick_left))

    # --- play it, into HitSlot, on whatever body this is ---------------------
    chosen = keep(_at(ed.add_get_member_variable_node(REACT_INDEX_VAR),
                      x0 + 3840, y0 + 620))
    last = keep(_at(_node(ed, FN_SUB_II), x0 + 3840, y0 + 760))
    _connect(count_out, _pin(last, "A"))
    _set(last, "B", 1)
    safe = keep(_at(_node(ed, FN_CLAMP_II), x0 + 4080, y0 + 620))
    _connect(_pin(chosen, REACT_INDEX_VAR, is_input=False), _pin(safe, "Value"))
    _set(safe, "Min", 0)
    _connect(_pin(last, "ReturnValue", is_input=False), _pin(safe, "Max"))
    clip = keep(_at(_node(ed, FN_ARR_GET), x0 + 4320, y0 + 620))
    _connect(clips_out, _pin(clip, "TargetArray"))
    _connect(_pin(safe, "ReturnValue", is_input=False), _pin(clip, "Index"))

    # Through the owner's own AnimInstance, so this works on the player, on a
    # zombie and on a wendigo without knowing which it is holding.
    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 3840, y0))
    _connect(owner_out, _pin(as_char, "Object"))
    for tail in arms:
        _connect(tail, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)
    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    x0 + 4080, y0 + 340))
    _connect(char_out, _pin(mesh, "self"))
    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 4320, y0 + 340))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(anim, "self"))

    play = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 4560, y0))
    _connect(_pin(anim, "ReturnValue", is_input=False), _pin(play, "self"))
    _connect(_pin(clip, "Item", is_input=False), _pin(play, "Asset"))
    _set(play, "SlotNodeName", HIT_SLOT)
    _set(play, "BlendInTime", COMBAT.hit_react_blend_s)
    _set(play, "BlendOutTime", COMBAT.hit_react_blend_s)
    _set(play, "InPlayRate", COMBAT.hit_react_rate)
    _set(play, "LoopCount", 1)
    _connect(BEL.find_then_pin(as_char), _pin(play, "execute"))

    # A deadline, not a countdown: nothing has to tick it.
    when = keep(_at(_node(ed, FN_ADD_FF), x0 + 4560, y0 + 480))
    _connect(now_out, _pin(when, "A"))
    _set(when, "B", COMBAT.hit_react_cooldown_s)
    rearm = keep(_at(ed.add_set_member_variable_node(NEXT_REACT_VAR),
                     x0 + 4820, y0))
    _connect(_pin(when, "ReturnValue", is_input=False), _pin(rearm, NEXT_REACT_VAR))
    _connect(BEL.find_then_pin(play), _pin(rearm, "execute"))

    after_play = BEL.find_then_pin(rearm)
    if HIT_REACT_PROBE:
        who = keep(_at(_node(ed, FN_GET_OWNER), x0 + 4820, y0 + 700))
        who_name = keep(_at(_node(ed, FN_DISPLAY_NAME), x0 + 5060, y0 + 700))
        _connect(_pin(who, "ReturnValue", is_input=False), _pin(who_name, "Object"))
        head = keep(_at(_node(ed, FN_CONCAT), x0 + 5300, y0 + 700))
        _set(head, "A", HIT_REACT_PROBE_PREFIX)
        _connect(_pin(who_name, "ReturnValue", is_input=False), _pin(head, "B"))
        idx_str = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 5060, y0 + 840))
        _connect(_pin(safe, "ReturnValue", is_input=False), _pin(idx_str, "InInt"))
        tail_str = keep(_at(_node(ed, FN_CONCAT), x0 + 5300, y0 + 840))
        _set(tail_str, "A", " clip ")
        _connect(_pin(idx_str, "ReturnValue", is_input=False), _pin(tail_str, "B"))
        line = keep(_at(_node(ed, FN_CONCAT), x0 + 5540, y0 + 700))
        _connect(_pin(head, "ReturnValue", is_input=False), _pin(line, "A"))
        _connect(_pin(tail_str, "ReturnValue", is_input=False), _pin(line, "B"))
        say = keep(_at(_node(ed, FN_WARN), x0 + 5540, y0 + 480))
        _connect(_pin(line, "ReturnValue", is_input=False), _pin(say, "InString"))
        _connect(after_play, _pin(say, "execute"))
        after_play = BEL.find_then_pin(say)

    # --- and remember this frame's health, on every path ---------------------
    # Including the ones that did not react. Skipping it on the cooldown arm
    # would make the NEXT hit compare against a health from before this one and
    # fire the moment the cooldown lapses, with nothing new having happened.
    remember = keep(_at(ed.add_set_member_variable_node(PREV_HEALTH_VAR),
                        x0 + 5080, y0))
    _connect(_pin(now_h, "Health", is_input=False), _pin(remember, PREV_HEALTH_VAR))
    for tail in (after_play,
                 _pin(as_char, "CastFailed", is_input=False),
                 BEL.find_else_pin(have),
                 BEL.find_else_pin(cooled),
                 BEL.find_else_pin(took)):
        _connect(tail, _pin(remember, "execute"))

    ed.add_comment_to_nodes(
        f"FLINCH. Health dropped since last frame and is still above zero, so "
        f"whatever it was, this one lived: play one of {len(HIT_REACTION_CLIPS)} "
        f"one-second staggers into {HIT_SLOT} at {COMBAT.hit_react_rate}x, "
        f"chosen by which side LastHitFrom points at, and refuse another for "
        f"{COMBAT.hit_react_cooldown_s} s. {HIT_SLOT} is blended from "
        f"{UPPER_BODY_ROOT} down, so the chest and arms take the hit and the "
        f"legs never stop -- the player keeps running and a wanderer keeps "
        f"closing. Triggered by POLLING Health rather than called by the "
        f"shooter, so every source of damage reacts, including ones that do not "
        f"know this exists.",
        made)
    return made, BEL.find_then_pin(remember)


def build_footstep_component(rebuild=True):
    """A footfall every FOOTSTEP_STRIDE_CM of ground covered.

        [Tick] -> cast owner to Character -> [on the ground?]
                    no  -> Travelled = 0          (a jump restarts the stride)
                    yes -> Travelled += speed * dt
                        -> [Travelled >= stride AND moving?]
                             yes -> Travelled -= stride
                                 -> play one of Sounds at the owner
                             no  -> done

    Distance rather than time: see FOOTSTEP_STRIDE_CM. Nothing here knows about
    sprint, about the gait variance the level generator applies per wanderer,
    or about the wendigo being 15% faster -- all three change how far the owner
    moves per second, and all three therefore change the step rate for free.

    Subtracting the stride rather than zeroing Travelled is what keeps the rate
    independent of framerate: zeroing throws away the overshoot, so the real
    stride becomes 160 cm plus whatever one frame added.
    """
    bp = _create_blueprint(FOOTSTEP_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, _begin = _events(ed, rebuild)

    _declare(ed, "Travelled", _float_type())
    _declare(ed, "StrideCm", _float_type())
    _declare(ed, "Sounds", BEL.get_array_type(
        BEL.get_object_reference_type(unreal.SoundBase.static_class())))

    owner = _at(_node(ed, FN_GET_OWNER), 0, 300)
    owner_out = _pin(owner, "ReturnValue", is_input=False)
    as_char = _at(_palette(ed, NODE_CAST_CHARACTER), 260, 0)
    _connect(owner_out, _pin(as_char, "Object"))
    _connect(BEL.find_then_pin(tick), _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    grounded = _at(_node(ed, FN_ON_GROUND), 780, 300)
    _connect(char_out, _pin(grounded, "self"))

    walking = _at(ed.add_branch_node(), 1040, 0)
    _connect(_pin(grounded, "ReturnValue", is_input=False), _pin(walking, "Condition"))
    _connect(BEL.find_then_pin(as_char), _pin(walking, "execute"))

    # Airborne: forget the part-stride, so landing does not immediately fire a
    # step that was 90% accumulated before the jump.
    reset = _at(ed.add_set_member_variable_node("Travelled"), 1300, 400)
    _set(reset, "Travelled", 0.0)
    _connect(BEL.find_else_pin(walking), _pin(reset, "execute"))

    speed_v = _at(_node(ed, FN_GET_VELOCITY), 1040, 560)
    _connect(owner_out, _pin(speed_v, "self"))
    # Horizontal speed only: falling at terminal velocity is not walking, and
    # VSize would count it.
    speed = _at(_node(ed, FN_VSIZE_XY), 1300, 560)
    _connect(_pin(speed_v, "ReturnValue", is_input=False), _pin(speed, "A"))
    speed_out = _pin(speed, "ReturnValue", is_input=False)

    step = _at(_node(ed, FN_MUL_FF), 1560, 560)
    _connect(speed_out, _pin(step, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "B"))
    sofar = _at(ed.add_get_member_variable_node("Travelled"), 1560, 700)
    total = _at(_node(ed, FN_ADD_FF), 1820, 560)
    _connect(_pin(sofar, "Travelled", is_input=False), _pin(total, "A"))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(total, "B"))
    advance = _at(ed.add_set_member_variable_node("Travelled"), 2080, 0)
    _connect(_pin(total, "ReturnValue", is_input=False), _pin(advance, "Travelled"))
    _connect(BEL.find_then_pin(walking), _pin(advance, "execute"))
    # Read the STORED total from here on. The add is pure and would be
    # re-evaluated against the new Travelled on a second read -- the same trap
    # the NPC id and the reload arithmetic ran into.
    have = _at(ed.add_get_member_variable_node("Travelled"), 2080, 300)
    have_out = _pin(have, "Travelled", is_input=False)

    stride = _at(ed.add_get_member_variable_node("StrideCm"), 2080, 420)
    stride_out = _pin(stride, "StrideCm", is_input=False)
    far_enough = _at(_node(ed, FN_GE_FF), 2340, 300)
    _connect(have_out, _pin(far_enough, "A"))
    _connect(stride_out, _pin(far_enough, "B"))
    quick_enough = _at(_node(ed, FN_GREATER_FF), 2340, 560)
    _connect(speed_out, _pin(quick_enough, "A"))
    _set(quick_enough, "B", FOOTSTEP_MIN_SPEED_CMS)
    both = _at(_node(ed, FN_AND), 2600, 420)
    _connect(_pin(far_enough, "ReturnValue", is_input=False), _pin(both, "A"))
    _connect(_pin(quick_enough, "ReturnValue", is_input=False), _pin(both, "B"))

    lands = _at(ed.add_branch_node(), 2860, 0)
    _connect(_pin(both, "ReturnValue", is_input=False), _pin(lands, "Condition"))
    _connect(BEL.find_then_pin(advance), _pin(lands, "execute"))

    left = _at(_node(ed, FN_SUB_FF), 3120, 300)
    _connect(have_out, _pin(left, "A"))
    _connect(stride_out, _pin(left, "B"))
    charge = _at(ed.add_set_member_variable_node("Travelled"), 3380, 0)
    _connect(_pin(left, "ReturnValue", is_input=False), _pin(charge, "Travelled"))
    _connect(BEL.find_then_pin(lands), _pin(charge, "execute"))

    at = _at(_node(ed, FN_ACTOR_LOC), 3380, 300)
    _connect(owner_out, _pin(at, "self"))
    _author_random_sound(ed, "Sounds", _pin(at, "ReturnValue", is_input=False),
                         BEL.find_then_pin(charge), 3640, 0)

    ed.add_comment_to_nodes(
        f"A footfall every {FOOTSTEP_STRIDE_CM:.0f} cm of ground covered, "
        f"which is about {600.0 / FOOTSTEP_STRIDE_CM:.1f} a second at a "
        f"600 cm/s run. Distance, not a timer: sprint, the per-wanderer gait "
        f"variance and the wendigo's 1.15x all change how fast their owner "
        f"moves, and an accumulator over distance tracks every one of them "
        f"without being told. The remainder is carried, not zeroed, so the "
        f"rate does not depend on framerate.",
        ed.list_all_nodes())

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_FootstepComponent failed to compile")

    eas = _assets()
    found = [eas.load_asset(f"{CREATURE_AUDIO_DIR}/{n}") for n in FOOTSTEP_NAMES
             if eas.does_asset_exist(f"{CREATURE_AUDIO_DIR}/{n}")]
    _apply_defaults(bp, {"StrideCm": FOOTSTEP_STRIDE_CM,
                         "Travelled": 0.0,
                         "Sounds": found})
    _log(f"built {FOOTSTEP_BP_PATH} "
         f"({len(found)} steps, one every {FOOTSTEP_STRIDE_CM:.0f} cm)")
    return bp


def build_health_component(rebuild=True):
    """Health, plus what happens when it runs out.

    Health is a component rather than a variable on each character so that the
    shooter and the HUD share one lookup -- GetComponentByClass -> Cast ->
    Health -- that works on the player, on the NPC, and on anything given the
    component later.

    Death lives here too, and is driven by three defaults rather than by
    subclassing:

        DespawnOnDeath   this is a wanderer: at 0 HP count the kill, spawn a
                         replacement, kill the AI and let the body rot for
                         CORPSE_SECONDS. False on the player, whose body stays
                         where it fell until the level reopens.
        RespawnClass     what to spawn in the dead actor's place. Left empty on
                         the player; on a wanderer it is overwritten at
                         BeginPlay with the owner's OWN class, so each creature
                         respawns as itself rather than as whatever the shared
                         component template happened to name.

    Where the replacement appears is the RESPAWN_BAND: a random bearing and a
    random distance in the same 75-100 m annulus the level generator uses,
    measured from the player's current location and then snapped onto the
    navmesh. So killing one wanderer keeps the population at five and keeps
    every one of them at a distance the player can see coming.

    Because the replacement carries the same component with the same defaults,
    one death begets one respawn indefinitely with nothing tracking it.

    Damage is applied by the weapon writing Health directly rather than through
    ApplyDamage / Event AnyDamage. AnyDamage is an *Actor* event, so routing
    through it would mean authoring a graph on both characters -- and
    BP_ThirdPersonCharacter's graph is the Enhanced Input template, which the
    graph API cannot partially rebuild.
    """
    # The weapon-drop path casts the spawned actor to BP_WeaponItem, and a cast
    # node only appears in the palette for a class that is already loaded.
    if not _assets().load_asset(ITEM_BP_PATH):
        raise RuntimeError(f"could not load {ITEM_BP_PATH} for its cast node")

    bp = _create_blueprint(HEALTH_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    for name in ("Health", "MaxHealth", LAST_DAMAGE_VAR):
        _declare(ed, name, _float_type())
    for name in ("Dead", "DespawnOnDeath", DAMAGED_BY_PLAYER_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    _declare(ed, "RespawnClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))
    # What a killed wanderer leaves on the ground. Typed as a class rather than
    # hard-coded in the graph so this component still compiles when
    # BP_AmmoPickup does not exist yet -- which is the case every time this
    # builder runs from scratch, because the pickup casts to BP_WeaponComponent
    # and so has to be built after it. main() fills the default in afterwards.
    _declare(ed, "AmmoClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))
    # The weapons a kill can leave behind, class-of-Actor for the same reason
    # AmmoClass is, and filled by main() once every weapon blueprint exists.
    # Empty is a legal state and means "no weapon ever drops" -- the graph
    # checks the length before it draws an index.
    _declare(ed, "DropClasses", BEL.get_array_type(
        BEL.get_class_reference_type(unreal.Actor.static_class())))
    # Where the replacement will appear. Written three times on the way to the
    # spawn -- the request, then whichever navmesh point it resolved to -- so
    # that the random draw and the nav query are each evaluated exactly once.
    _declare(ed, "RespawnPoint", _struct_type(unreal.Vector.static_struct()))
    # The number this wanderer was given at spawn. The HUD draws it beside the
    # health bar; the log line below records where that number appeared.
    _declare(ed, NPC_ID_VAR, BEL.get_basic_type_by_name("int"))
    # Where this wanderer was put. Recorded for diagnosis, not for gameplay --
    # the respawn point is computed from the player, not from here (the old
    # SpawnOrigin, which anchored respawns to it, is gone on purpose). It is
    # what lets the safety net report the spawn that produced a faller.
    _declare(ed, SPAWNED_AT_VAR, _struct_type(unreal.Vector.static_struct()))
    # Hit boxes: which physics-asset bodies are head and which are limbs, and
    # what each is worth. On the target rather than on the weapon, because the
    # tables are a fact about the target's skeleton -- install_on_character
    # and install_on_npc fill them from each one's own mesh. Empty here, which
    # makes a target nobody has zoned take every hit at 1.0x.
    for name in (HEAD_BONES_VAR, LIMB_BONES_VAR):
        _declare(ed, name, BEL.get_array_type(BEL.get_basic_type_by_name("name")))
    for name in (HEAD_MULT_VAR, LIMB_MULT_VAR):
        _declare(ed, name, _float_type())

    # Flinching. Four variables and a clip table, all on the component rather
    # than on either character, because both of them react the same way and
    # neither of their Blueprints has a graph this could be written into.
    _declare(ed, HIT_REACTIONS_VAR, BEL.get_array_type(
        BEL.get_object_reference_type(unreal.AnimSequenceBase.static_class())))
    _declare(ed, LAST_HIT_FROM_VAR, _struct_type(unreal.Vector.static_struct()))
    for name in (PREV_HEALTH_VAR, NEXT_REACT_VAR):
        _declare(ed, name, _float_type())
    _declare(ed, REACT_INDEX_VAR, BEL.get_basic_type_by_name("int"))

    # SpawnOrigin used to hold where this actor started, back when a replacement
    # appeared near the dead one's own spawn point. It has to be removed
    # explicitly: this builder updates blueprints in place, so a variable it
    # simply stops declaring stays on the asset forever.
    ed.remove_member_variable("SpawnOrigin")

    # --- BeginPlay: take the next number and say where this one appeared -----
    # Numbered in spawn order, wanderers only (the player carries the same
    # component and must not consume a number). Both the initially placed five
    # and every replacement come through here, so the log is a complete record
    # of every wanderer that has ever existed this session -- which is what
    # makes a fall-through reportable: read the number off the health bar, find
    # that number in the log, and its spawn location is right there.
    mine = _at(ed.add_get_member_variable_node("DespawnOnDeath"), -1200, -640)
    is_wanderer = _at(ed.add_branch_node(), -960, -900)
    _connect(_pin(mine, "DespawnOnDeath", is_input=False), _pin(is_wanderer, "Condition"))
    _connect(BEL.find_then_pin(begin), _pin(is_wanderer, "execute"))

    # --- what this one respawns as: itself -----------------------------------
    # RespawnClass used to be a default written onto BP_ForestWanderer's own
    # component template, and every variant inherited it. So a wendigo's
    # replacement was a BP_ForestWanderer -- which wears the PARENT's mesh,
    # i.e. a zombie. Kill the two wendigos the level places and there are never
    # any more, which is exactly what it looked like. (The zombies had the same
    # bug and it was invisible: the thing they respawned as looked identical.)
    #
    # Asking the owner what class it is fixes it for every variant at once,
    # including ones that do not exist yet, and needs nothing per creature.
    # The template default stays as the fallback for a wanderer that somehow
    # has no owner class, and DespawnOnDeath -- already the "am I a wanderer"
    # test above -- stays the thing that decides whether any of this runs.
    me = _at(_node(ed, FN_GET_OWNER), -1200, -500)
    my_class = _at(_node(ed, FN_OBJECT_CLASS), -960, -500)
    _connect(_pin(me, "ReturnValue", is_input=False), _pin(my_class, "Object"))
    same_again = _at(ed.add_set_member_variable_node("RespawnClass"), -720, -1100)
    _connect(_pin(my_class, "ReturnValue", is_input=False),
             _pin(same_again, "RespawnClass"))
    _connect(BEL.find_then_pin(is_wanderer), _pin(same_again, "execute"))

    mode = _at(_node(ed, FN_GET_GAME_MODE), -720, -900)
    as_mode = _at(_palette(ed, NODE_CAST_GAME_MODE), -480, -900)
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(BEL.find_then_pin(same_again), _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    seen = _at(ed.add_get_member_variable_node(SPAWN_COUNT_VAR, GAME_MODE_CLASS_PATH),
               -480, -700)
    _connect(mode_out, _pin(seen, "self"))
    next_id = _at(_node(ed, FN_ADD_II), -240, -700)
    _connect(_pin(seen, SPAWN_COUNT_VAR, is_input=False), _pin(next_id, "A"))
    _set(next_id, "B", 1)
    # Take the number FIRST, then write the counter back from the stored value,
    # and read the stored value everywhere after that. The obvious order -- bump
    # the counter, then set NpcId from the same "+1" node -- numbers the first
    # wanderer 2: the add is pure, so reading it again after the counter has
    # moved re-evaluates it against the new count. Same trap as the navmesh
    # queries in the respawn path; a stored value is what makes it go away.
    take = _at(ed.add_set_member_variable_node(NPC_ID_VAR), 0, -900)
    _connect(_pin(next_id, "ReturnValue", is_input=False), _pin(take, NPC_ID_VAR))
    _connect(BEL.find_then_pin(as_mode), _pin(take, "execute"))

    my_id = _at(ed.add_get_member_variable_node(NPC_ID_VAR), 240, -700)
    my_id_out = _pin(my_id, NPC_ID_VAR, is_input=False)

    bump = _at(ed.add_set_member_variable_node(SPAWN_COUNT_VAR, GAME_MODE_CLASS_PATH),
               240, -900)
    _connect(mode_out, _pin(bump, "self"))
    _connect(my_id_out, _pin(bump, SPAWN_COUNT_VAR))
    _connect(BEL.find_then_pin(take), _pin(bump, "execute"))

    # "[NPC-SPAWN] #7 at X=... Y=... Z=..."
    id_str = _at(_node(ed, FN_INT_TO_STR), 480, -700)
    _connect(my_id_out, _pin(id_str, "InInt"))
    head = _at(_node(ed, FN_CONCAT), 720, -700)
    _set(head, "A", SPAWN_LOG_PREFIX)
    _connect(_pin(id_str, "ReturnValue", is_input=False), _pin(head, "B"))
    here_owner = _at(_node(ed, FN_GET_OWNER), 240, -520)
    here = _at(_node(ed, FN_ACTOR_LOC), 480, -520)
    _connect(_pin(here_owner, "ReturnValue", is_input=False), _pin(here, "self"))
    record = _at(ed.add_set_member_variable_node(SPAWNED_AT_VAR), 480, -900)
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(record, SPAWNED_AT_VAR))
    _connect(BEL.find_then_pin(bump), _pin(record, "execute"))
    # The log line reads the stored value rather than the actor again, so the
    # line and the variable the safety net quotes can never disagree.
    spawned_at = _at(ed.add_get_member_variable_node(SPAWNED_AT_VAR), 720, -520)
    where_str = _at(_node(ed, FN_VEC_TO_STR), 960, -520)
    _connect(_pin(spawned_at, SPAWNED_AT_VAR, is_input=False), _pin(where_str, "InVec"))
    at_str = _at(_node(ed, FN_CONCAT), 1200, -520)
    _set(at_str, "A", " at ")
    _connect(_pin(where_str, "ReturnValue", is_input=False), _pin(at_str, "B"))
    line = _at(_node(ed, FN_CONCAT), 1440, -700)
    _connect(_pin(head, "ReturnValue", is_input=False), _pin(line, "A"))
    _connect(_pin(at_str, "ReturnValue", is_input=False), _pin(line, "B"))

    say = _at(_node(ed, FN_PRINT), 1440, -900)
    _connect(_pin(line, "ReturnValue", is_input=False), _pin(say, "InString"))
    # Log only. On screen it would be five lines at level start and another
    # every time something dies, over the top of the HUD it is meant to explain.
    _set(say, "bPrintToScreen", "false")
    _set(say, "bPrintToLog", "true")
    _set(say, "Duration", 0.0)
    _connect(BEL.find_then_pin(record), _pin(say, "execute"))

    ed.add_comment_to_nodes(
        "Every wanderer takes the next number from the GameMode as it spawns "
        "and writes one log line saying where it appeared. The HUD draws the "
        "same number beside its health bar, so anything seen on screen can be "
        "looked up in the log. The player's copy of this component skips it -- "
        "DespawnOnDeath is what tells the two apart.",
        [mine, is_wanderer, mode, as_mode, seen, next_id, take, my_id, bump,
         record, spawned_at, id_str, head, here_owner, here, where_str, at_str,
         line, say])


    # --- Tick: the safety net -----------------------------------------------
    # Anything below the world is counted as dead. For a wanderer that routes
    # into the despawn-and-replace path, so one that ends up under the terrain
    # is gone within a frame and a correctly seated replacement takes its
    # place. For the player it routes into _author_player_death, and that is
    # the answer to walking off the edge of the map.
    #
    # IT USED TO BE GATED ON DespawnOnDeath, i.e. NPCs only, on the reasoning
    # that the player "has no replacement to be given". That was true when it
    # was written and stopped being true the day the player got a death path:
    # the player does not need a replacement, they need the restart menu, and
    # the menu is what 0 HP already opens. So the gate moved inward. It now
    # guards only the log line, which is the part that really is
    # wanderer-specific -- it quotes an NpcId and a spawn location, and the
    # player has neither.
    #
    # For the NPCs this is a net, not the fix: the fix is tracing the respawn
    # onto real ground (see below). A net is worth having anyway, because "the
    # capsule ended up inside geometry" has more causes than the one that was
    # measured. For the player it is not a net at all -- it is the only thing
    # standing between "walked too far" and a fall with no bottom.
    net_owner = _at(_node(ed, FN_GET_OWNER), -1200, 240)
    net_loc = _at(_node(ed, FN_ACTOR_LOC), -960, 240)
    _connect(_pin(net_owner, "ReturnValue", is_input=False), _pin(net_loc, "self"))
    net_brk = _at(_node(ed, FN_BREAK_VECTOR), -720, 240)
    _connect(_pin(net_loc, "ReturnValue", is_input=False), _pin(net_brk, "InVec"))
    under = _at(_node(ed, FN_LESS_FF), -480, 240)
    _connect(_pin(net_brk, "Z", is_input=False), _pin(under, "A"))
    _set(under, "B", WORLD_FLOOR_Z)
    lost = _at(ed.add_branch_node(), -240, 0)
    _connect(_pin(under, "ReturnValue", is_input=False), _pin(lost, "Condition"))
    tick_out = BEL.find_then_pin(tick)

    if HIT_REACT_PROBE:
        # TEMPORARY, and removed by re-running with HIT_REACT_PROBE False.
        #
        # Nothing shoots a wanderer in a headless run, so the NPC half of the
        # reaction is a gate the -game session never opens -- and an unopened
        # gate and a broken one leave the same (empty) log. This shoots one for
        # it: at t > 6 s, any wanderer still at full health takes 20 damage from
        # a direction along its OWN FORWARD, which is the Front bucket and
        # therefore the random-of-three arm the player's own punches never
        # reach. It needs no extra variable to fire once -- after the hit,
        # Health < MaxHealth is false forever.
        probe_npc = _at(ed.add_get_member_variable_node("DespawnOnDeath"), -1900, 1000)
        probe_now = _at(_node(ed, FN_TIME_SECONDS), -1900, 1120)
        probe_late = _at(_node(ed, FN_GREATER_FF), -1660, 1120)
        _connect(_pin(probe_now, "ReturnValue", is_input=False), _pin(probe_late, "A"))
        _set(probe_late, "B", 6.0)
        probe_hp = _at(ed.add_get_member_variable_node("Health"), -1900, 1240)
        probe_max = _at(ed.add_get_member_variable_node("MaxHealth"), -1900, 1360)
        probe_full = _at(_node(ed, FN_GE_FF), -1660, 1240)
        _connect(_pin(probe_hp, "Health", is_input=False), _pin(probe_full, "A"))
        _connect(_pin(probe_max, "MaxHealth", is_input=False), _pin(probe_full, "B"))
        probe_and = _at(_node(ed, FN_AND), -1420, 1120)
        _connect(_pin(probe_npc, "DespawnOnDeath", is_input=False), _pin(probe_and, "A"))
        _connect(_pin(probe_late, "ReturnValue", is_input=False), _pin(probe_and, "B"))
        probe_and2 = _at(_node(ed, FN_AND), -1180, 1120)
        _connect(_pin(probe_and, "ReturnValue", is_input=False), _pin(probe_and2, "A"))
        _connect(_pin(probe_full, "ReturnValue", is_input=False), _pin(probe_and2, "B"))
        probe_br = _at(ed.add_branch_node(), -940, 1000)
        _connect(_pin(probe_and2, "ReturnValue", is_input=False), _pin(probe_br, "Condition"))
        _connect(tick_out, _pin(probe_br, "execute"))

        probe_owner = _at(_node(ed, FN_GET_OWNER), -940, 1240)
        probe_fwd = _at(_node(ed, FN_ACTOR_FORWARD), -700, 1240)
        _connect(_pin(probe_owner, "ReturnValue", is_input=False), _pin(probe_fwd, "self"))
        probe_dir = _at(ed.add_set_member_variable_node(LAST_HIT_FROM_VAR), -700, 1000)
        _connect(_pin(probe_fwd, "ReturnValue", is_input=False),
                 _pin(probe_dir, LAST_HIT_FROM_VAR))
        _connect(BEL.find_then_pin(probe_br), _pin(probe_dir, "execute"))
        probe_hurt = _at(_node(ed, FN_SUB_FF), -460, 1240)
        _connect(_pin(probe_hp, "Health", is_input=False), _pin(probe_hurt, "A"))
        _set(probe_hurt, "B", 20.0)
        probe_set = _at(ed.add_set_member_variable_node("Health"), -460, 1000)
        _connect(_pin(probe_hurt, "ReturnValue", is_input=False), _pin(probe_set, "Health"))
        _connect(BEL.find_then_pin(probe_dir), _pin(probe_set, "execute"))

        probe_join = _at(ed.add_branch_node(), -220, 1000)
        _set(probe_join, "Condition", "true")
        _connect(BEL.find_then_pin(probe_set), _pin(probe_join, "execute"))
        _connect(BEL.find_else_pin(probe_br), _pin(probe_join, "execute"))
        tick_out = BEL.find_then_pin(probe_join)

    _connect(tick_out, _pin(lost, "execute"))
    # ...and only then, is this one worth a log line? A wanderer under the map
    # is a bug worth reporting with its number and its spawn point. A player
    # under the map walked there.
    net_is_npc = _at(ed.add_get_member_variable_node("DespawnOnDeath"), -240, 240)
    reportable = _at(ed.add_branch_node(), 0, 0)
    _connect(_pin(net_is_npc, "DespawnOnDeath", is_input=False),
             _pin(reportable, "Condition"))
    _connect(BEL.find_then_pin(lost), _pin(reportable, "execute"))
    # Say which one, by its number, before removing it: the net recovers the
    # game within a frame, which would otherwise erase the evidence of the very
    # thing worth diagnosing. Grep [NPC-FELL] for the number, then [NPC-SPAWN]
    # for the same number to see exactly where it was put.
    net_id = _at(ed.add_get_member_variable_node(NPC_ID_VAR), -240, 400)
    net_id_str = _at(_node(ed, FN_INT_TO_STR), 0, 400)
    _connect(_pin(net_id, NPC_ID_VAR, is_input=False), _pin(net_id_str, "InInt"))
    net_head = _at(_node(ed, FN_CONCAT), 240, 400)
    _set(net_head, "A", FELL_LOG_PREFIX)
    _connect(_pin(net_id_str, "ReturnValue", is_input=False), _pin(net_head, "B"))
    net_where = _at(_node(ed, FN_VEC_TO_STR), 240, 560)
    _connect(_pin(net_loc, "ReturnValue", is_input=False), _pin(net_where, "InVec"))
    net_at = _at(_node(ed, FN_CONCAT), 480, 560)
    _set(net_at, "A", " fell to ")
    _connect(_pin(net_where, "ReturnValue", is_input=False), _pin(net_at, "B"))
    net_line = _at(_node(ed, FN_CONCAT), 720, 400)
    _connect(_pin(net_head, "ReturnValue", is_input=False), _pin(net_line, "A"))
    _connect(_pin(net_at, "ReturnValue", is_input=False), _pin(net_line, "B"))

    # ...and where it was spawned, which is the half worth having: the fall
    # position is always "somewhere under the map", while the spawn position is
    # the thing that has to be explained. Quoting the stored SpawnedAt means the
    # two lines for one wanderer agree by construction.
    net_origin = _at(ed.add_get_member_variable_node(SPAWNED_AT_VAR), 480, 720)
    net_origin_str = _at(_node(ed, FN_VEC_TO_STR), 720, 720)
    _connect(_pin(net_origin, SPAWNED_AT_VAR, is_input=False),
             _pin(net_origin_str, "InVec"))
    net_from = _at(_node(ed, FN_CONCAT), 960, 720)
    _set(net_from, "A", " — spawned at ")
    _connect(_pin(net_origin_str, "ReturnValue", is_input=False), _pin(net_from, "B"))
    net_full = _at(_node(ed, FN_CONCAT), 1200, 400)
    _connect(_pin(net_line, "ReturnValue", is_input=False), _pin(net_full, "A"))
    _connect(_pin(net_from, "ReturnValue", is_input=False), _pin(net_full, "B"))

    # PrintWarning, not PrintString: Warning is the highest severity Blueprint
    # can emit, so this is as close to an error as the graph can get, and it is
    # what makes the line stand out in the Output Log.
    net_say = _at(_node(ed, FN_WARN), 1200, 0)
    _connect(_pin(net_full, "ReturnValue", is_input=False), _pin(net_say, "InString"))
    _connect(BEL.find_then_pin(reportable), _pin(net_say, "execute"))

    # Both arms write the zero -- the reported wanderer after its line, the
    # player straight away. Missing the second connection would be the exact
    # bug this block exists to fix, silently: the player would fall past the
    # threshold, take the unreported branch, and carry on falling.
    write_off = _at(ed.add_set_member_variable_node("Health"), 1440, 0)
    _set(write_off, "Health", 0.0)
    for tail in (BEL.find_then_pin(net_say), BEL.find_else_pin(reportable)):
        _connect(tail, _pin(write_off, "execute"))

    ed.add_comment_to_nodes(
        f"Below {WORLD_FLOOR_Z / 100:.0f} m there is nothing under the capsule "
        "and never will be, so whatever is down there is written off as dead "
        "and takes the death path it already has: a wanderer is replaced, and "
        "the player -- who walked off the edge of a 200 m square of terrain -- "
        "gets the restart menu instead of falling for the rest of the session. "
        "Only the log line is wanderer-specific; it quotes a number and a spawn "
        "point, and the player has neither.",
        [net_owner, net_loc, net_brk, under, net_is_npc, lost, reportable,
         net_id, net_id_str, net_head, net_where, net_at, net_line, net_origin,
         net_origin_str, net_from, net_full, net_say, write_off])

    # --- Tick: has it died this frame? ---------------------------------------
    health = _at(ed.add_get_member_variable_node("Health"), 240, 240)
    dying = _at(_node(ed, FN_LE_FF), 460, 240)
    _connect(_pin(health, "Health", is_input=False), _pin(dying, "A"))
    _set(dying, "B", 0.0)

    at_zero = _at(ed.add_branch_node(), 700, 0)
    _connect(_pin(dying, "ReturnValue", is_input=False), _pin(at_zero, "Condition"))
    # Both arms of the net fall through to here. The Health getter above is
    # pure, so it is read at *this* branch -- after the net's write -- and a
    # wanderer written off this frame dies this frame.
    _connect(BEL.find_then_pin(write_off), _pin(at_zero, "execute"))
    _connect(BEL.find_else_pin(lost), _pin(at_zero, "execute"))

    # --- Tick: took a hit and lived --------------------------------------
    # The other arm of the same branch, and that is the whole "and survived":
    # this exec pin is reached only on frames the owner is still above zero.
    _author_hit_reaction(ed, BEL.find_else_pin(at_zero), 700, 1600)

    # Branch on Dead and use its *False* pin -- one node cheaper than a NOT, and
    # it is what stops the death path running again every frame after the first.
    dead_get = _at(ed.add_get_member_variable_node("Dead"), 700, 240)
    already = _at(ed.add_branch_node(), 940, 0)
    _connect(_pin(dead_get, "Dead", is_input=False), _pin(already, "Condition"))
    _connect(BEL.find_then_pin(at_zero), _pin(already, "execute"))

    mark = _at(ed.add_set_member_variable_node("Dead"), 1180, 0)
    _set(mark, "Dead", "true")
    _connect(BEL.find_else_pin(already), _pin(mark, "execute"))

    despawn_get = _at(ed.add_get_member_variable_node("DespawnOnDeath"), 1180, 240)
    should = _at(ed.add_branch_node(), 1420, 0)
    _connect(_pin(despawn_get, "DespawnOnDeath", is_input=False), _pin(should, "Condition"))
    _connect(BEL.find_then_pin(mark), _pin(should, "execute"))

    # --- count it, then respawn, then leave a corpse -------------------------
    counted = _author_kill_count(ed, BEL.find_then_pin(should), 1420, -1600)

    cls_get = _at(ed.add_get_member_variable_node("RespawnClass"), 1660, 300)
    can_respawn = _at(_node(ed, FN_IS_VALID_CLASS), 1900, 300)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(can_respawn, "Class"))
    respawns = _at(ed.add_branch_node(), 2120, 0)
    _connect(_pin(can_respawn, "ReturnValue", is_input=False), _pin(respawns, "Condition"))
    for tail in counted:
        _connect(tail, _pin(respawns, "execute"))

    # --- where the replacement goes -----------------------------------------
    # Three steps, and the order matters:
    #
    #   1. build the REQUEST -- a random bearing and distance in the band,
    #      around the player -- and store it, so the random draw happens once;
    #   2. project it onto the navmesh, which is what supplies a real ground
    #      height (the request carries the *player's* Z, which is meaningless
    #      90 m away) and pulls a point that overshot the navigable island back
    #      onto it;
    #   3. only then spawn, lifted by the capsule's half height.
    #
    # Step 1 has to be a variable rather than wires straight into step 2.
    # K2_ProjectPointToNavigation is **pure** (a const BlueprintCallable, which
    # UHT promotes), so it is re-evaluated once per output pin read -- and if
    # its Point pin were driven by the RandomFloatInRange chain, the branch on
    # ReturnValue and the read of ProjectedLocation would each roll fresh
    # numbers and project two different points. Storing the request first makes
    # every re-evaluation deterministic.
    #
    # THIS IS THE BUG THIS SHAPE EXISTS TO FIX: the previous version read the
    # nav query's location output and never looked at its bool, so a failed
    # query -- routine here, because the band's far edge lies outside the
    # navigable island on a 200 m map -- spawned the replacement at the raw
    # request point, at the player's own Z. On any ground higher than the player
    # that is *inside* the terrain, and the capsule falls through the world.
    hero = _at(_node(ed, FN_GET_PLAYER_PAWN), 1660, 560)
    _set(hero, "PlayerIndex", 0)
    hero_loc = _at(_node(ed, FN_ACTOR_LOC), 1900, 560)
    _connect(_pin(hero, "ReturnValue", is_input=False), _pin(hero_loc, "self"))
    hero_out = _pin(hero_loc, "ReturnValue", is_input=False)

    made = [hero, hero_loc]
    flow = BEL.find_then_pin(respawns)
    ready = []          # exec pins that have a good point and may spawn

    for attempt in range(RESPAWN_ATTEMPTS):
        x0 = 2360 + attempt * 1400
        y0 = attempt * 900

        bearing = _at(_node(ed, FN_RANDOM_FLOAT), x0 - 700, y0 + 300)
        _set(bearing, "Min", 0.0)
        _set(bearing, "Max", 360.0)
        facing = _at(_node(ed, FN_MAKE_ROT), x0 - 460, y0 + 300)
        _connect(_pin(bearing, "ReturnValue", is_input=False), _pin(facing, "Yaw"))
        _set(facing, "Pitch", 0.0)
        _set(facing, "Roll", 0.0)
        heading = _at(_node(ed, FN_FORWARD), x0 - 220, y0 + 300)
        _connect(_pin(facing, "ReturnValue", is_input=False), _pin(heading, "InRot"))

        reach = _at(_node(ed, FN_RANDOM_FLOAT), x0 - 460, y0 + 460)
        _set(reach, "Min", RESPAWN_BAND[0])
        _set(reach, "Max", RESPAWN_BAND[1])
        # Multiply_VectorFloat is a wildcard operator whose B pin defaults to a
        # *vector*, so a float literal on it silently does nothing -- but a
        # connected float is fine, and that is what this is.
        offset = _at(_node(ed, FN_MUL_VF), x0, y0 + 300)
        _connect(_pin(heading, "ReturnValue", is_input=False), _pin(offset, "A"))
        _connect(_pin(reach, "ReturnValue", is_input=False), _pin(offset, "B"))

        request = _at(_node(ed, FN_ADD_VV), x0 + 240, y0 + 160)
        _connect(hero_out, _pin(request, "A"))
        _connect(_pin(offset, "ReturnValue", is_input=False), _pin(request, "B"))

        ask = _at(ed.add_set_member_variable_node("RespawnPoint"), x0 + 480, y0)
        _connect(_pin(request, "ReturnValue", is_input=False), _pin(ask, "RespawnPoint"))
        _connect(flow, _pin(ask, "execute"))
        asked = _at(ed.add_get_member_variable_node("RespawnPoint"), x0 + 480, y0 + 200)

        proj = _at(_node(ed, FN_PROJECT_NAV), x0 + 720, y0 + 200)
        _connect(_pin(asked, "RespawnPoint", is_input=False), _pin(proj, "Point"))
        # QueryExtent is a struct pin, and struct pins reject set_pin_value
        # outright -- an empty one compiles as the ZERO vector, i.e. a search box
        # with no volume, which finds nothing and fails every projection.
        _connect(_vec(ed, *RESPAWN_PROJECT_EXTENT, x0 + 480, y0 + 420),
                 _pin(proj, "QueryExtent"))

        landed = _at(ed.add_branch_node(), x0 + 960, y0)
        _connect(_pin(proj, "ReturnValue", is_input=False), _pin(landed, "Condition"))
        _connect(BEL.find_then_pin(ask), _pin(landed, "execute"))

        use_proj = _at(ed.add_set_member_variable_node("RespawnPoint"), x0 + 1200, y0)
        _connect(_pin(proj, "ProjectedLocation", is_input=False),
                 _pin(use_proj, "RespawnPoint"))
        _connect(BEL.find_then_pin(landed), _pin(use_proj, "execute"))

        ready.append(BEL.find_then_pin(use_proj))
        # A failed projection falls through to the next bearing; the draws are
        # independent, so a second one is a real second chance and not a repeat.
        flow = BEL.find_else_pin(landed)
        made += [bearing, facing, heading, reach, offset, request, ask, asked,
                 proj, landed, use_proj]

    # Last resort: no band point anywhere in the search box projected, which in
    # practice means the navmesh has not been generated yet (the first frame of
    # a level, or the tile churn after a burst of deaths). Take any navigable
    # point near the player rather than none -- a replacement standing too close
    # is a gameplay annoyance, one under the terrain is a bug. This call is the
    # *impure* nav function on purpose: it is random, so it must be evaluated
    # exactly once, and only a node with an exec pin can promise that.
    anywhere = _at(_node(ed, FN_RANDOM_NAV), 5400, 1500)
    _connect(hero_out, _pin(anywhere, "Origin"))
    _set(anywhere, "Radius", RESPAWN_BAND[1])
    _connect(flow, _pin(anywhere, "execute"))

    salvaged = _at(ed.add_branch_node(), 5660, 1500)
    _connect(_pin(anywhere, "ReturnValue", is_input=False), _pin(salvaged, "Condition"))
    _connect(BEL.find_then_pin(anywhere), _pin(salvaged, "execute"))

    use_any = _at(ed.add_set_member_variable_node("RespawnPoint"), 5920, 1500)
    _connect(_pin(anywhere, "RandomLocation", is_input=False),
             _pin(use_any, "RespawnPoint"))
    _connect(BEL.find_then_pin(salvaged), _pin(use_any, "execute"))
    ready.append(BEL.find_then_pin(use_any))

    # 3. seat it on the real ground. The point is on the navmesh by now, but the
    # navmesh is a voxelised approximation of the terrain and its Z can be most
    # of a capsule too low -- so keep the XY, throw the Z away, and trace onto
    # the collision geometry the character will actually stand on.
    seat = _at(ed.add_get_member_variable_node("RespawnPoint"), 6180, 600)
    seat_out = _pin(seat, "RespawnPoint", is_input=False)
    above = _at(_node(ed, FN_ADD_VV), 6420, 600)
    _connect(seat_out, _pin(above, "A"))
    _connect(_vec(ed, 0.0, 0.0, RESPAWN_TRACE_UP, 6180, 800), _pin(above, "B"))
    below = _at(_node(ed, FN_ADD_VV), 6420, 780)
    _connect(seat_out, _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -RESPAWN_TRACE_DOWN, 6180, 960), _pin(below, "B"))

    drop = _at(_node(ed, FN_TRACE), 6680, 300)
    _connect(_pin(above, "ReturnValue", is_input=False), _pin(drop, "Start"))
    _connect(_pin(below, "ReturnValue", is_input=False), _pin(drop, "End"))
    _trace_defaults(drop)
    # The terrain is imported with complex collision, and its simple collision
    # is a box around the whole 200 m mesh -- tracing against that would seat
    # every respawn on an invisible lid.
    _set(drop, "bTraceComplex", "true")
    for tail in ready:
        _connect(tail, _pin(drop, "execute"))

    found = _at(ed.add_branch_node(), 6940, 300)
    _connect(_pin(drop, "ReturnValue", is_input=False), _pin(found, "Condition"))
    _connect(BEL.find_then_pin(drop), _pin(found, "execute"))

    lift = _vec(ed, 0.0, 0.0, RESPAWN_LIFT, 6940, 900)
    brk = _at(_palette(ed, NODE_BREAK_HIT), 7200, 700)
    _connect(_pin(drop, "OutHit", is_input=False), _pin(brk, "Hit"))
    ground = _at(_node(ed, FN_ADD_VV), 7460, 700)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(ground, "A"))
    _connect(lift, _pin(ground, "B"))
    stand = _at(ed.add_set_member_variable_node("RespawnPoint"), 7460, 500)
    _connect(_pin(ground, "ReturnValue", is_input=False), _pin(stand, "RespawnPoint"))
    _connect(BEL.find_then_pin(found), _pin(stand, "execute"))

    # Nothing under the point at all (it hangs over a hole in the world). Keep
    # the navmesh height and lift off that instead -- worse, but still above
    # whatever the navmesh thinks the floor is.
    airborne = _at(_node(ed, FN_ADD_VV), 7460, 1100)
    _connect(seat_out, _pin(airborne, "A"))
    _connect(lift, _pin(airborne, "B"))
    hover = _at(ed.add_set_member_variable_node("RespawnPoint"), 7460, 950)
    _connect(_pin(airborne, "ReturnValue", is_input=False), _pin(hover, "RespawnPoint"))
    _connect(BEL.find_else_pin(found), _pin(hover, "execute"))

    made += [seat, above, below, drop, found, brk, ground, stand, airborne, hover]

    # 4. spawn, on ground the character can actually stand on.
    chosen = _at(ed.add_get_member_variable_node("RespawnPoint"), 7720, 300)
    xform = _at(_node(ed, FN_MAKE_TRANSFORM), 7960, 300)
    _connect(_pin(chosen, "RespawnPoint", is_input=False), _pin(xform, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0, 7720, 500), _pin(xform, "Scale"))

    spawn = _at(_palette(ed, NODE_SPAWN), 8220, 0)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    # AlwaysSpawn: the nav point is inset from obstacles by the agent radius but
    # may still clip a trunk's collision, and a respawn that silently returns
    # null would empty the forest one death at a time.
    # AdjustIfPossibleButAlwaysSpawn, not AlwaysSpawn: the nav point is inset
    # from obstacles by the agent radius but can still clip a trunk, and a
    # capsule left interpenetrating gets depenetrated -- sometimes downwards,
    # through the terrain. Adjusting nudges it clear first; it still always
    # spawns, so a respawn cannot silently return null and empty the forest.
    _set(spawn, "CollisionHandlingOverride", "AdjustIfPossibleButAlwaysSpawn")
    for tail in (BEL.find_then_pin(stand), BEL.find_then_pin(hover)):
        _connect(tail, _pin(spawn, "execute"))

    # Every path ends at the same corpse; an exec *input* takes more than one
    # link, so no Sequence node is needed. Note the last one: with no navmesh to
    # be found at all, the dead wanderer is NOT replaced -- it still leaves a
    # body. Losing one of ten is recoverable and visible; dropping a replacement
    # through the floor is neither.
    corpsed = _author_corpse(ed, (BEL.find_then_pin(spawn),
                                  BEL.find_else_pin(respawns),
                                  BEL.find_else_pin(salvaged)), 8220, 0)

    # Both arms of the death branch collapse the same way and through the same
    # nodes: the player straight off the branch, the wanderer once its
    # replacement is out and its brain is gone.
    fell, no_body = _author_death_collapse(
        ed, (corpsed, BEL.find_else_pin(should)), 9900, 0)
    # ...and only the player gets a menu out of it. A second read of
    # DespawnOnDeath rather than routing the two arms separately, so there is
    # exactly one place that says what dying looks like.
    mine_again = _at(ed.add_get_member_variable_node("DespawnOnDeath"), 12060, 240)
    is_player = _at(ed.add_branch_node(), 12300, 0)
    _connect(_pin(mine_again, "DespawnOnDeath", is_input=False),
             _pin(is_player, "Condition"))
    for tail in (fell, no_body):
        _connect(tail, _pin(is_player, "execute"))
    _author_player_death(ed, (BEL.find_else_pin(is_player),), 12540, 0)

    ed.add_comment_to_nodes(
        f"At 0 HP: mark Dead once, then (if DespawnOnDeath) ask for a point "
        f"{RESPAWN_BAND[0] / 100:.0f}-{RESPAWN_BAND[1] / 100:.0f} m from the "
        f"player on a random bearing, PROJECT it onto the navmesh (the request "
        f"carries the player's Z, which is not the ground height out there), "
        f"spawn the replacement on that ground and leave this one on the "
        f"ground for {CORPSE_SECONDS:.0f} s "
        f"({RESPAWN_ATTEMPTS} bearings are tried before falling back to any "
        f"navigable point near the player). The replacement carries the same component, so the cycle sustains "
        "itself with nothing tracking it -- the pack stays five strong and every "
        "member still has to cross the forest. The player's copy has "
        "DespawnOnDeath false and no RespawnClass, so none of this runs on them.",
        [health, dying, at_zero, dead_get, already, mark, despawn_get, should,
         cls_get, can_respawn, respawns] + made +
        [anywhere, salvaged, use_any, chosen, xform, spawn, mine_again,
         is_player])

    _post_physics_tick(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_HealthComponent failed to compile")
    _apply_defaults(bp, {
        "Health": COMBAT.start_health,
        "MaxHealth": COMBAT.start_health,
        "Dead": False,
        "DespawnOnDeath": False,
        # Far enough in the past that nothing counts as recently hurt at level
        # start -- a zero here would float every wanderer's bar for the first
        # five seconds of the game.
        LAST_DAMAGE_VAR: NEVER_DAMAGED,
        DAMAGED_BY_PLAYER_VAR: False,
        HEAD_MULT_VAR: COMBAT.head_multiplier,
        LIMB_MULT_VAR: COMBAT.limb_multiplier,
        # Seeded at full health, so the very first Tick compares like with like
        # and nobody flinches on the frame they spawn. (A wanderer's real
        # maximum is written over this at possession -- see
        # _author_stats_and_voice in build_npc_blueprints.py -- and the poll
        # only ever looks for a DECREASE, so the correction cannot fire one.)
        PREV_HEALTH_VAR: COMBAT.start_health,
        # Zero, not NEVER_DAMAGED: world time starts at zero and this is a
        # deadline, so anything at or before it means "ready now".
        NEXT_REACT_VAR: 0.0,
    })
    _log(f"built {HEALTH_BP_PATH} (Health = MaxHealth = {COMBAT.start_health})")
    return bp


# ─── BP_WeaponComponent ──────────────────────────────────────────────────────

AIM_LOOPS = 9999          # PlaySlotAnimation has no "loop forever"; 9999 x 8 s
                          # is about a day, which outlasts any play session.
AIM_BLEND = 0.25


def _prop(ed, name, self_pin, x, y, class_path=ITEM_CLASS_PATH):
    """Read a variable off another object: Get <name> with its self pin driven.

    A data output pin takes any number of links, so one Held getter can feed
    every one of these.
    """
    n = _at(ed.add_get_member_variable_node(name, class_path), x, y)
    _connect(self_pin, _pin(n, "self"))
    return _pin(n, name, is_input=False), n


def _trace_defaults(node):
    """The settings every trace in this file shares.

    No trace draws itself any more. DrawDebugType is an enum *literal* on the
    pin, and an enum pin cannot be driven by a variable, so a trace that draws
    only in debug mode is not expressible here at all -- the pellet tracer is a
    separate DrawDebugLine behind a Branch instead (see _author_fire).
    """
    _set(node, "TraceChannel", "TraceTypeQuery1")   # Visibility
    _set(node, "bTraceComplex", "false")
    # Ignores the pawn this component hangs off. The weapon actor is separate
    # and *not* ignored, but every one of its parts is NoCollision, so a pellet
    # cannot hit the gun it came out of.
    _set(node, "bIgnoreSelf", "true")
    _set(node, "DrawDebugType", "None")


def _muzzle_location(ed, held, x, y):
    """World position of the held weapon's barrel tip, as a pure sub-graph.

    Pure, so it can be shared: the aim resolve and the pellet loop must agree on
    where the gun is, and the cheapest way to guarantee that is for them to read
    the same nodes rather than each build their own copy.
    """
    xform = _at(_node(ed, FN_GET_TRANSFORM), x, y)
    _connect(held, _pin(xform, "self"))
    off_pin, _off = _prop(ed, "MuzzleOffset", held, x, y + 140)
    at = _at(_node(ed, FN_TRANSFORM_LOC), x + 260, y)
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(at, "T"))
    _connect(off_pin, _pin(at, "Location"))
    return _pin(at, "ReturnValue", is_input=False)


def _author_resolve_aim(ed, held, exec_ins, x0, y0):
    """Work out where this frame's shot lands. The hybrid of the two obvious wrongs.

    Aiming purely from the muzzle is honest and unplayable: the barrel sits below
    and to the side of the camera, so the shot lands a little off wherever the
    crosshair is, and a player standing beside a wall shoots the wall while their
    crosshair is on an enemy in the open. Aiming purely from the camera is
    playable and looks broken: the camera is on a boom behind the shoulder, so
    the pellets visibly fan out from behind the player -- which is exactly what
    was reported here.

    So: the camera decides *what* is being aimed at, and the muzzle decides
    whether the gun can actually reach it.

      1. Trace from the camera along its forward vector. Whatever it hits is the
         aim point; if it hits nothing, the aim point is a point a kilometre out,
         which is the standard stand-in for "the sky".
      2. Trace from the muzzle to that aim point. If something stops that second
         line well short, *that* is where the shot lands -- the wall in front of
         the barrel -- and AimBlocked says so, which is what turns the reticle
         red.

    Step 2 is not a separate safety check bolted on: it is the same line the
    pellets themselves fly down, so the reticle cannot promise a hit the shot
    will not make. The pellet loop then only has to spread a cone around
    (AimPoint - muzzle).

    Runs before the fire gate and unconditionally, because the reticle has to be
    right on frames where the trigger is not pulled -- which is most of them.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cam = keep(_at(_node(ed, FN_GET_CAM), x0, y0 + 260))
    _set(cam, "PlayerIndex", 0)
    cam_out = _pin(cam, "ReturnValue", is_input=False)
    cam_loc = keep(_at(_node(ed, FN_CAM_LOC), x0 + 240, y0 + 260))
    _connect(cam_out, _pin(cam_loc, "self"))
    cam_loc_out = _pin(cam_loc, "ReturnValue", is_input=False)
    cam_rot = keep(_at(_node(ed, FN_CAM_ROT), x0 + 240, y0 + 400))
    _connect(cam_out, _pin(cam_rot, "self"))
    fwd = keep(_at(_node(ed, FN_FORWARD), x0 + 480, y0 + 400))
    _connect(_pin(cam_rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))
    reach = keep(_at(_node(ed, FN_MUL_VF), x0 + 720, y0 + 400))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(reach, "A"))
    # The length goes in as a *vector* literal, not a float one. UE 5 promotes
    # Multiply_VectorFloat to a wildcard operator, and with nothing connected
    # its B pin is a vector -- which is a struct pin, which rejects every
    # literal format there is. Multiplying component-wise by (R, R, R) is the
    # same arithmetic and actually survives the save.
    _connect(_vec(ed, AIM_TRACE_RANGE, AIM_TRACE_RANGE, AIM_TRACE_RANGE,
                  x0 + 480, y0 + 560),
             _pin(reach, "B"))
    sky = keep(_at(_node(ed, FN_ADD_VV), x0 + 960, y0 + 320))
    _connect(cam_loc_out, _pin(sky, "A"))
    _connect(_pin(reach, "ReturnValue", is_input=False), _pin(sky, "B"))
    sky_out = _pin(sky, "ReturnValue", is_input=False)

    look = keep(_at(_node(ed, FN_TRACE), x0 + 1200, y0))
    _connect(cam_loc_out, _pin(look, "Start"))
    _connect(sky_out, _pin(look, "End"))
    # Never drawn: this line runs from the camera through the player's own head
    # every frame, so drawing it would fill the screen. Only the pellets are
    # drawn, and only when they are actually fired.
    _trace_defaults(look)
    for e in exec_ins:
        _connect(e, _pin(look, "execute"))

    look_brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 1200, y0 + 560))
    _connect(_pin(look, "OutHit", is_input=False), _loose_pin(look_brk, "Hit"))
    saw = keep(_at(ed.add_branch_node(), x0 + 1480, y0))
    _connect(_pin(look, "ReturnValue", is_input=False), _pin(saw, "Condition"))
    _connect(BEL.find_then_pin(look), _pin(saw, "execute"))

    on_surface = keep(_at(ed.add_set_member_variable_node("AimPoint"), x0 + 1740, y0 - 160))
    _connect(_loose_pin(look_brk, "Location", is_input=False), _pin(on_surface, "AimPoint"))
    _connect(BEL.find_then_pin(saw), _pin(on_surface, "execute"))
    at_sky = keep(_at(ed.add_set_member_variable_node("AimPoint"), x0 + 1740, y0 + 220))
    _connect(sky_out, _pin(at_sky, "AimPoint"))
    _connect(BEL.find_else_pin(saw), _pin(at_sky, "execute"))

    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 2000, y0 + 320))
    _connect(held, _pin(armed, "Object"))
    holding = keep(_at(ed.add_branch_node(), x0 + 2240, y0))
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(holding, "Condition"))
    _connect(BEL.find_then_pin(on_surface), _pin(holding, "execute"))
    _connect(BEL.find_then_pin(at_sky), _pin(holding, "execute"))

    # Empty-handed: there is nothing to draw a reticle for, and no muzzle to
    # trace from -- reading one off a null weapon is how Accessed None happens.
    unarmed = keep(_at(ed.add_set_member_variable_node("AimValid"), x0 + 2500, y0 + 700))
    _set(unarmed, "AimValid", "false")
    _connect(BEL.find_else_pin(holding), _pin(unarmed, "execute"))

    aim_get = keep(_at(ed.add_get_member_variable_node("AimPoint"), x0 + 2500, y0 + 460))
    aim_out = _pin(aim_get, "AimPoint", is_input=False)

    muzzle = _muzzle_location(ed, held, x0 + 2500, y0 + 1000)

    clear = keep(_at(_node(ed, FN_TRACE), x0 + 3260, y0))
    _connect(muzzle, _pin(clear, "Start"))
    _connect(aim_out, _pin(clear, "End"))
    _trace_defaults(clear)
    _connect(BEL.find_then_pin(holding), _pin(clear, "execute"))

    clear_brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 2760, y0 + 560))
    _connect(_pin(clear, "OutHit", is_input=False), _loose_pin(clear_brk, "Hit"))
    stopped = keep(_at(ed.add_branch_node(), x0 + 3040, y0))
    _connect(_pin(clear, "ReturnValue", is_input=False), _pin(stopped, "Condition"))
    _connect(BEL.find_then_pin(clear), _pin(stopped, "execute"))

    short_by = keep(_at(_node(ed, FN_DISTANCE), x0 + 3040, y0 + 700))
    _connect(_loose_pin(clear_brk, "Location", is_input=False), _pin(short_by, "V1"))
    _connect(aim_out, _pin(short_by, "V2"))
    far_short = keep(_at(_node(ed, FN_GREATER_FF), x0 + 3280, y0 + 700))
    _connect(_pin(short_by, "ReturnValue", is_input=False), _pin(far_short, "A"))
    _set(far_short, "B", BLOCKED_SLACK)

    mark = keep(_at(ed.add_set_member_variable_node("AimBlocked"), x0 + 3300, y0 - 160))
    _connect(_pin(far_short, "ReturnValue", is_input=False), _pin(mark, "AimBlocked"))
    _connect(BEL.find_then_pin(stopped), _pin(mark, "execute"))
    # The aim point moves to where the barrel's own line actually ends, so the
    # reticle sits on the near wall rather than on the enemy behind it.
    reality = keep(_at(ed.add_set_member_variable_node("AimPoint"), x0 + 3560, y0 - 160))
    _connect(_loose_pin(clear_brk, "Location", is_input=False), _pin(reality, "AimPoint"))
    _connect(BEL.find_then_pin(mark), _pin(reality, "execute"))

    open_shot = keep(_at(ed.add_set_member_variable_node("AimBlocked"), x0 + 3300, y0 + 260))
    _set(open_shot, "AimBlocked", "false")
    _connect(BEL.find_else_pin(stopped), _pin(open_shot, "execute"))

    ready = keep(_at(ed.add_set_member_variable_node("AimValid"), x0 + 3840, y0))
    _set(ready, "AimValid", "true")
    _connect(BEL.find_then_pin(reality), _pin(ready, "execute"))
    _connect(BEL.find_then_pin(open_shot), _pin(ready, "execute"))

    ed.add_comment_to_nodes(
        "Resolve aim: the camera picks the target, the muzzle decides whether "
        "the gun can reach it. AimPoint ends up at the first surface on the "
        "line the pellets will actually fly down, which is what makes the "
        "reticle honest -- including when the barrel is against a tree and the "
        "camera can see straight past it.",
        made)
    return [BEL.find_then_pin(ready), BEL.find_then_pin(unarmed)], muzzle


def _author_fire(ed, held, muzzle, exec_in, x0, y0):
    """One trigger pull: the fire sound, then one trace per pellet from the muzzle.

    All the aiming was done in _author_resolve_aim; what is left here is the
    spread. Each pellet takes the muzzle-to-AimPoint direction, jitters it inside
    the weapon's own cone, and traces the weapon's own range. A single-pellet
    weapon with a 1 degree cone is the same code path as an eight-pellet
    shotgun, which is why the pistol needed no second implementation.

    Ammunition is spent here rather than in the gate that allowed the shot: the
    gate decides, this does. Both the round and the cooldown are written before
    a single pellet is traced, so nothing downstream can leave the weapon
    having fired for free.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # --- what the shot costs -------------------------------------------------
    # Unconditional, including on the pistol. Loaded is only ever *read* behind
    # UsesAmmo, so letting an unlimited weapon count into the negatives costs
    # nothing and saves a branch on the one path that runs eight traces.
    was = keep(_at(ed.add_get_member_variable_node("Loaded", ITEM_CLASS_PATH),
                   x0 - 760, y0 + 300))
    _connect(held, _pin(was, "self"))
    spent = keep(_at(_node(ed, FN_SUB_II), x0 - 520, y0 + 300))
    _connect(_pin(was, "Loaded", is_input=False), _pin(spent, "A"))
    _set(spent, "B", 1)
    burn = keep(_at(ed.add_set_member_variable_node("Loaded", ITEM_CLASS_PATH),
                    x0 - 280, y0))
    _connect(held, _pin(burn, "self"))
    _connect(_pin(spent, "ReturnValue", is_input=False), _pin(burn, "Loaded"))
    _connect(exec_in, _pin(burn, "execute"))

    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 - 760, y0 + 440))
    every, every_n = _prop(ed, "FireInterval", held, x0 - 760, y0 + 560)
    keep(every_n)
    again = keep(_at(_node(ed, FN_ADD_FF), x0 - 520, y0 + 440))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(again, "A"))
    _connect(every, _pin(again, "B"))
    cool = keep(_at(ed.add_set_member_variable_node("NextFireTime", ITEM_CLASS_PATH),
                    x0 - 40, y0))
    _connect(held, _pin(cool, "self"))
    _connect(_pin(again, "ReturnValue", is_input=False), _pin(cool, "NextFireTime"))
    _connect(BEL.find_then_pin(burn), _pin(cool, "execute"))

    # --- is anyone watching the tracers? -------------------------------------
    # Read once per shot and cached on this component, rather than read per
    # pellet: the pellet loop needs a plain bool it can branch on, and a
    # GetGameMode plus a cast eight times over for one flag is eight times the
    # work for the same answer.
    mode = keep(_at(_node(ed, FN_GET_GAME_MODE), x0 + 200, y0 + 300))
    as_mode = keep(_at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 200, y0))
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(BEL.find_then_pin(cool), _pin(as_mode, "execute"))
    flag = keep(_at(ed.add_get_member_variable_node(DEBUG_MODE_VAR,
                                                    GAME_MODE_CLASS_PATH),
                    x0 + 200, y0 + 440))
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(flag, "self"))
    note = keep(_at(ed.add_set_member_variable_node(DEBUG_MODE_VAR), x0 + 460, y0))
    _connect(_pin(flag, DEBUG_MODE_VAR, is_input=False), _pin(note, DEBUG_MODE_VAR))
    _connect(BEL.find_then_pin(as_mode), _pin(note, "execute"))
    # A GameMode of the wrong class cannot say; not drawing is the safe answer,
    # and the component's own default is already false.
    after_cost = [BEL.find_then_pin(note),
                  _pin(as_mode, "CastFailed", is_input=False)]

    aim_get = keep(_at(ed.add_get_member_variable_node("AimPoint"), x0, y0 + 560))
    delta = keep(_at(_node(ed, FN_SUB_VV), x0 + 260, y0 + 560))
    _connect(_pin(aim_get, "AimPoint", is_input=False), _pin(delta, "A"))
    _connect(muzzle, _pin(delta, "B"))
    direction_n = keep(_at(_node(ed, FN_NORMAL), x0 + 500, y0 + 560))
    _connect(_pin(delta, "ReturnValue", is_input=False), _pin(direction_n, "A"))
    direction = _pin(direction_n, "ReturnValue", is_input=False)

    snd_pin, snd_n = _prop(ed, "FireSound", held, x0 + 240, y0 + 140)
    keep(snd_n)
    play = keep(_at(_node(ed, FN_PLAY_SOUND), x0 + 520, y0))
    _connect(snd_pin, _pin(play, "Sound"))
    _connect(muzzle, _pin(play, "Location"))
    for tail in after_cost:
        _connect(tail, _pin(play, "execute"))

    pel_pin, pel_n = _prop(ed, "PelletCount", held, x0 + 760, y0 + 180)
    keep(pel_n)
    last = keep(_at(_node(ed, FN_SUB_II), x0 + 980, y0 + 180))
    _connect(pel_pin, _pin(last, "A"))
    _set(last, "B", 1)

    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    keep(_at(loop, x0 + 1240, y0))
    _loose_pin(loop, "FirstIndex").set_pin_value("0")
    _connect(_pin(last, "ReturnValue", is_input=False), _loose_pin(loop, "LastIndex"))
    _connect(BEL.find_then_pin(play), _loose_pin(loop, "execute"))

    spread_pin, spread_n = _prop(ed, "SpreadDegrees", held, x0 + 1420, y0 + 840)
    keep(spread_n)
    # Aiming down the sights is worth something, not just a zoom: the cone
    # shrinks to COMBAT.ads_spread_scale of the weapon's own figure. SelectFloat
    # rather than a branch, so there is exactly one cone and the two cases
    # cannot drift -- the same shape _author_sprint uses to pick a speed.
    aiming_now = keep(_at(ed.add_get_member_variable_node("Aiming"),
                          x0 + 1420, y0 + 1080))
    steadied = keep(_at(_node(ed, FN_SELECT_FF), x0 + 1660, y0 + 1080))
    _set(steadied, "A", COMBAT.ads_spread_scale)
    _set(steadied, "B", 1.0)
    _connect(_pin(aiming_now, "Aiming", is_input=False), _pin(steadied, "bPickA"))
    tightened = keep(_at(_node(ed, FN_MUL_FF), x0 + 1660, y0 + 940))
    _connect(spread_pin, _pin(tightened, "A"))
    _connect(_pin(steadied, "ReturnValue", is_input=False), _pin(tightened, "B"))

    rad = keep(_at(_node(ed, FN_DEG2RAD), x0 + 1900, y0 + 940))
    _connect(_pin(tightened, "ReturnValue", is_input=False), _pin(rad, "A"))

    cone = keep(_at(_node(ed, FN_RAND_CONE), x0 + 1900, y0 + 620))
    _connect(direction, _pin(cone, "ConeDir"))
    _connect(_pin(rad, "ReturnValue", is_input=False),
             _pin(cone, "ConeHalfAngleInRadians"))
    rng_pin, rng_n = _prop(ed, "WeaponRange", held, x0 + 1900, y0 + 840)
    keep(rng_n)
    reach = keep(_at(_node(ed, FN_MUL_VF), x0 + 2140, y0 + 620))
    _connect(_pin(cone, "ReturnValue", is_input=False), _pin(reach, "A"))
    _connect(rng_pin, _pin(reach, "B"))
    end = keep(_at(_node(ed, FN_ADD_VV), x0 + 2380, y0 + 560))
    _connect(muzzle, _pin(end, "A"))
    _connect(_pin(reach, "ReturnValue", is_input=False), _pin(end, "B"))

    trace = keep(_at(_node(ed, FN_TRACE), x0 + 2620, y0))
    _connect(muzzle, _pin(trace, "Start"))
    _connect(_pin(end, "ReturnValue", is_input=False), _pin(trace, "End"))
    _trace_defaults(trace)
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(trace, "execute"))

    # The tracer, in debug mode only. It starts at the barrel, so what you see
    # is the line the pellet took and not a line from the camera -- which is
    # what makes it worth having while tuning the aim solve, and what makes it
    # wrong to leave switched on in the game.
    seen = keep(_at(ed.add_get_member_variable_node(DEBUG_MODE_VAR),
                    x0 + 2620, y0 + 300))
    showing = keep(_at(ed.add_branch_node(), x0 + 2860, y0))
    _connect(_pin(seen, DEBUG_MODE_VAR, is_input=False), _pin(showing, "Condition"))
    _connect(BEL.find_then_pin(trace), _pin(showing, "execute"))
    tracer = keep(_at(_node(ed, FN_DRAW_LINE), x0 + 3100, y0 - 320))
    _connect(muzzle, _pin(tracer, "LineStart"))
    _connect(_pin(end, "ReturnValue", is_input=False), _pin(tracer, "LineEnd"))
    _set(tracer, "Duration", TRACE_DEBUG_SECONDS)
    _set(tracer, "Thickness", 1.0)
    _connect(BEL.find_then_pin(showing), _pin(tracer, "execute"))

    hit = keep(_at(ed.add_branch_node(), x0 + 3360, y0))
    _connect(_pin(trace, "ReturnValue", is_input=False), _pin(hit, "Condition"))
    # Both arms of the tracer branch carry on: whether a line was drawn has
    # nothing to do with whether the pellet connected.
    _connect(BEL.find_then_pin(tracer), _pin(hit, "execute"))
    _connect(BEL.find_else_pin(showing), _pin(hit, "execute"))
    brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 3360, y0 + 300))
    _connect(_pin(trace, "OutHit", is_input=False), _loose_pin(brk, "Hit"))

    ed.add_comment_to_nodes(
        "Fire: one round and one cooldown stamp first, then origin at the "
        "muzzle, direction muzzle -> AimPoint, spread the weapon's own cone. "
        "The tracer leaves the barrel and ends where the reticle said it would "
        "-- when DebugMode is on, which is the only time it is drawn at all.",
        made)

    _author_impact(ed, brk, held, BEL.find_then_pin(hit), x0 + 3640, y0)
    return _loose_pin(loop, "Completed", is_input=False)


def _author_impact(ed, brk, held, exec_in, x0, y0):
    """A pellet that hit something: blood, then subtract the damage.

    Both are behind the health cast, so trees and terrain cost nothing and
    produce no blood -- only things carrying BP_HealthComponent bleed. The
    damage is the weapon's, scaled by where on the body it landed (see
    _author_hit_zone), using the target's own hit-box tables.
    """
    comp = _at(_node(ed, FN_GET_COMP), x0, y0 + 260)
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 260, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    blood_cls = _at(ed.add_get_member_variable_node("BloodClass"), x0 + 520, y0 + 520)
    where = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 520, y0 + 380)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(where, "Location"))
    # How big the spray is, as a clamped ratio of the round's damage to a
    # reference one. Spawn *scale* rather than a parameter on the splash,
    # because the droplet solver works in the actor's own space: scaling the
    # actor scales launch distance and droplet size together, which is the
    # single number that separates a 9 mm from a slug at contact range. A
    # shotgun pays eight of these at once, which is why one pellet is under 1x.
    spray_dmg_pin, spray_dmg = _prop(ed, "Damage", held, x0 - 40, y0 + 760)
    ratio = _at(_node(ed, FN_DIV_FF), x0 + 200, y0 + 760)
    _connect(spray_dmg_pin, _pin(ratio, "A"))
    _set(ratio, "B", BLOOD_REFERENCE_DAMAGE)
    spray = _at(_node(ed, FN_CLAMP), x0 + 440, y0 + 760)
    _connect(_pin(ratio, "ReturnValue", is_input=False), _pin(spray, "Value"))
    _set(spray, "Min", BLOOD_SCALE_MIN)
    _set(spray, "Max", BLOOD_SCALE_MAX)
    spray_v = _at(_node(ed, FN_MUL_VF), x0 + 680, y0 + 900)
    _connect(_vec(ed, 1.0, 1.0, 1.0, x0 + 440, y0 + 1040), _pin(spray_v, "A"))
    _connect(_pin(spray, "ReturnValue", is_input=False), _pin(spray_v, "B"))
    _connect(_pin(spray_v, "ReturnValue", is_input=False), _pin(where, "Scale"))
    # Point the splash's +X down the surface normal: BP_BloodSplash throws its
    # cone along its own forward, so this is what makes the spray come *out of*
    # the wound instead of along an arbitrary world axis.
    facing = _at(_node(ed, FN_ROT_FROM_X), x0 + 520, y0 + 660)
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False), _pin(facing, "X"))
    _connect(_pin(facing, "ReturnValue", is_input=False), _pin(where, "Rotation"))
    splash = _at(_palette(ed, NODE_SPAWN), x0 + 800, y0)
    _connect(_pin(blood_cls, "BloodClass", is_input=False), _pin(splash, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(splash, "SpawnTransform"))
    _set(splash, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(cast), _pin(splash, "execute"))

    zoned, zone_nodes, x_zone = _author_hit_zone(
        ed, brk, BEL.find_then_pin(splash), x0 + 1080, y0)

    get_h = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                x_zone, y0 + 300)
    _connect(as_health, _pin(get_h, "self"))
    dmg_pin, dmg_n = _prop(ed, "Damage", held, x_zone - 480, y0 + 1300)
    worth, worth_nodes = _zone_multiplier(ed, as_health, x_zone - 480, y0 + 1440)
    scaled = _at(_node(ed, FN_MUL_FF), x_zone, y0 + 1300)
    _connect(dmg_pin, _pin(scaled, "A"))
    _connect(worth, _pin(scaled, "B"))
    sub = _at(_node(ed, FN_SUB_FF), x_zone + 240, y0 + 300)
    _connect(_pin(get_h, "Health", is_input=False), _pin(sub, "A"))
    _connect(_pin(scaled, "ReturnValue", is_input=False), _pin(sub, "B"))
    clamp = _at(_node(ed, FN_CLAMP), x_zone + 480, y0 + 300)
    _connect(_pin(sub, "ReturnValue", is_input=False), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = _at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                x_zone + 740, y0)
    _connect(as_health, _pin(set_h, "self"))
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(set_h, "Health"))
    for tail in zoned:
        _connect(tail, _pin(set_h, "execute"))
    # Everything after this sits right of the zone block, as it sat right of
    # the splash before there was one.
    x0 += x_zone - (x0 + 1080)

    # Stamp the hit. Two things read this and nothing else writes it:
    #
    #   LastDamageTime  the HUD floats a wanderer's health bar for a few seconds
    #                   after it, and hides it the rest of the time;
    #   DamagedByPlayer what separates a kill from a wanderer that fell through
    #                   the world -- the safety net writes Health to 0 too, and
    #                   the kill counter must not count that.
    #
    # Written on every pellet rather than only on the killing one: a wanderer
    # that takes a hit and lives has to show its bar as well.
    now = _at(_node(ed, FN_TIME_SECONDS), x0 + 1820, y0 + 300)
    stamp = _at(ed.add_set_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH),
                x0 + 2080, y0)
    _connect(as_health, _pin(stamp, "self"))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(stamp, LAST_DAMAGE_VAR))
    _connect(BEL.find_then_pin(set_h), _pin(stamp, "execute"))

    blame = _at(ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR,
                                                HEALTH_CLASS_PATH),
                x0 + 2340, y0)
    _connect(as_health, _pin(blame, "self"))
    _set(blame, DAMAGED_BY_PLAYER_VAR, "true")
    _connect(BEL.find_then_pin(stamp), _pin(blame, "execute"))

    # ...and which way it came from, for the flinch. The IMPACT NORMAL, not the
    # shot's own direction reversed: it is already in the hit result, it already
    # points back out of the surface toward the muzzle, and it is the one that
    # is right for a pellet that grazed a shoulder at an angle. A target shot in
    # the back therefore plays the Back reaction with nothing having measured an
    # angle. See _author_hit_reaction for what reads it.
    from_where = _at(ed.add_set_member_variable_node(LAST_HIT_FROM_VAR,
                                                     HEALTH_CLASS_PATH),
                     x0 + 2600, y0)
    _connect(as_health, _pin(from_where, "self"))
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False),
             _pin(from_where, LAST_HIT_FROM_VAR))
    _connect(BEL.find_then_pin(blame), _pin(from_where, "execute"))

    shown = _author_damage_readout(ed, brk, _pin(scaled, "ReturnValue", is_input=False),
                                   worth, BEL.find_then_pin(from_where), x0 + 2860, y0)

    ed.add_comment_to_nodes(
        "Clamped at zero so an overkill shot cannot drive Health negative -- "
        "the HUD bar divides by MaxHealth and the death check is Health <= 0, "
        "and both want a floor.",
        [comp, cast, blood_cls, where, facing, splash, spray_dmg, ratio, spray,
         spray_v, get_h, sub, clamp, set_h, now, stamp, blame,
         from_where])
    ed.add_comment_to_nodes(
        f"Hit boxes: the pellet's own line is traced again against the target's "
        f"physics-asset bodies alone, and the bone it strikes picks the "
        f"multiplier off the TARGET's health component -- head "
        f"{COMBAT.head_multiplier}x, arms and legs {COMBAT.limb_multiplier}x, anything else "
        f"1x. A pellet that clipped the capsule but threaded between the limbs "
        f"strikes no body and counts as a body hit, which is what every hit "
        f"was before.",
        zone_nodes + worth_nodes + [dmg_n, scaled])
    ed.add_comment_to_nodes(
        "Debug mode only: the damage this pellet actually did, and the zone "
        "multiplier behind it, drawn where it landed for as long as the tracer.",
        shown)


def _author_damage_readout(ed, brk, damage, worth, exec_in, x0, y0):
    """In debug mode, write "<damage> (x<multiplier>)" at the impact point.

    Behind the same cached DebugMode the tracer branches on, and for the same
    TRACE_DEBUG_SECONDS, so the number appears at the end of the line that
    explains it. DrawDebugString rather than anything on the HUD: it is world
    space, needs no projection, and is compiled out of shipping builds like
    DrawDebugLine is.

    Re-reading `damage` and `worth` here is safe, though both are pure: their
    inputs (Damage, HitBone, the target's tables) are not written between the
    health update and this node.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    seen = keep(_at(ed.add_get_member_variable_node(DEBUG_MODE_VAR), x0, y0 + 300))
    showing = keep(_at(ed.add_branch_node(), x0 + 240, y0))
    _connect(_pin(seen, DEBUG_MODE_VAR, is_input=False), _pin(showing, "Condition"))
    _connect(exec_in, _pin(showing, "execute"))

    dmg_str = keep(_at(_node(ed, FN_FLOAT_TO_STR), x0, y0 + 440))
    _connect(damage, _pin(dmg_str, "InDouble"))
    mult_str = keep(_at(_node(ed, FN_FLOAT_TO_STR), x0, y0 + 580))
    _connect(worth, _pin(mult_str, "InDouble"))
    lead = keep(_at(_node(ed, FN_CONCAT), x0 + 240, y0 + 440))
    _connect(_pin(dmg_str, "ReturnValue", is_input=False), _pin(lead, "A"))
    _set(lead, "B", " (x")
    body = keep(_at(_node(ed, FN_CONCAT), x0 + 480, y0 + 440))
    _connect(_pin(lead, "ReturnValue", is_input=False), _pin(body, "A"))
    _connect(_pin(mult_str, "ReturnValue", is_input=False), _pin(body, "B"))
    text = keep(_at(_node(ed, FN_CONCAT), x0 + 720, y0 + 440))
    _connect(_pin(body, "ReturnValue", is_input=False), _pin(text, "A"))
    _set(text, "B", ")")

    draw = keep(_at(_node(ed, FN_DRAW_STRING), x0 + 960, y0))
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(draw, "TextLocation"))
    _connect(_pin(text, "ReturnValue", is_input=False), _pin(draw, "Text"))
    _set(draw, "TextColor", DAMAGE_TEXT_COLOR)
    _set(draw, "Duration", TRACE_DEBUG_SECONDS)
    _connect(BEL.find_then_pin(showing), _pin(draw, "execute"))
    return made


def _author_hit_zone(ed, brk, exec_in, x0, y0):
    """Which bone did this pellet strike? Written into HitBone, None for none.

    The pellet trace stops at the capsule -- make_shootable makes the capsule,
    not the mesh, block Visibility, and that is what keeps the aim trace and
    the reticle predictable. So the capsule answers *whether* a character was
    hit, and a second trace along the very same line (the hit result carries
    its TraceStart/TraceEnd) answers *where*: K2_LineTraceComponent tests one
    component only, and on a skeletal mesh that means its physics bodies, each
    of which reports its bone. It ignores collision channels altogether, so the
    mesh's own profile (CharacterMesh, which ignores Visibility) is irrelevant;
    what matters is that the mesh has query collision at all, or it has no
    bodies at runtime -- install_hit_zones asserts that.

    HitBone is cleared first, then written only by a trace that struck, which
    covers both misses with one node: an actor that is not a Character (no
    mesh to trace), and a pellet that clipped the capsule's edge and threaded
    between the arms and the body.

    Returns (exec outs that continue to the damage, nodes made, next free x).
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    clear = keep(_at(ed.add_set_member_variable_node(HIT_BONE_VAR), x0, y0))
    _set(clear, HIT_BONE_VAR, "None")
    _connect(exec_in, _pin(clear, "execute"))

    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 260, y0))
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(as_char, "Object"))
    _connect(BEL.find_then_pin(clear), _pin(as_char, "execute"))
    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    x0 + 260, y0 + 300))
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))

    probe = keep(_at(_node(ed, FN_TRACE_COMPONENT), x0 + 560, y0))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(probe, "self"))
    _connect(_loose_pin(brk, "TraceStart", is_input=False), _pin(probe, "TraceStart"))
    _connect(_loose_pin(brk, "TraceEnd", is_input=False), _pin(probe, "TraceEnd"))
    # Simple collision is the physics asset's capsules and spheres, which is
    # the point: complex would be the render mesh, which has no bone to report.
    _set(probe, "bTraceComplex", "false")
    _set(probe, "bShowTrace", "false")
    _set(probe, "bPersistentShowTrace", "false")
    _connect(BEL.find_then_pin(as_char), _pin(probe, "execute"))

    struck = keep(_at(ed.add_branch_node(), x0 + 880, y0))
    _connect(_pin(probe, "ReturnValue", is_input=False), _pin(struck, "Condition"))
    _connect(BEL.find_then_pin(probe), _pin(struck, "execute"))
    note = keep(_at(ed.add_set_member_variable_node(HIT_BONE_VAR), x0 + 1120, y0))
    _connect(_pin(probe, "BoneName", is_input=False), _pin(note, HIT_BONE_VAR))
    _connect(BEL.find_then_pin(struck), _pin(note, "execute"))

    outs = [BEL.find_then_pin(note), BEL.find_else_pin(struck),
            _pin(as_char, "CastFailed", is_input=False)]
    return outs, made, x0 + 1400


def _zone_multiplier(ed, as_health, x0, y0):
    """What HitBone is worth on this target: a pure float, 1.0 unless zoned.

    Head is tested last so it wins, though the two tables never overlap -- a
    bone cannot be under both the head and a thigh.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    bone = keep(_at(ed.add_get_member_variable_node(HIT_BONE_VAR), x0, y0 + 280))
    bone_out = _pin(bone, HIT_BONE_VAR, is_input=False)

    def member(table, x, y):
        pin, n = _prop(ed, table, as_health, x, y, HEALTH_CLASS_PATH)
        keep(n)
        test = keep(_at(_node(ed, FN_ARR_CONTAINS), x + 240, y))
        _connect(pin, _loose_pin(test, "TargetArray"))
        _connect(bone_out, _loose_pin(test, "ItemToFind"))
        return _pin(test, "ReturnValue", is_input=False)

    def worth(var, x, y):
        pin, n = _prop(ed, var, as_health, x, y, HEALTH_CLASS_PATH)
        keep(n)
        return pin

    is_limb = member(LIMB_BONES_VAR, x0, y0)
    limb_or_body = keep(_at(_node(ed, FN_SELECT_FF), x0 + 480, y0))
    _connect(worth(LIMB_MULT_VAR, x0 + 240, y0 + 140), _pin(limb_or_body, "A"))
    _set(limb_or_body, "B", 1.0)
    _connect(is_limb, _pin(limb_or_body, "bPickA"))

    is_head = member(HEAD_BONES_VAR, x0, y0 + 420)
    pick = keep(_at(_node(ed, FN_SELECT_FF), x0 + 720, y0 + 420))
    _connect(worth(HEAD_MULT_VAR, x0 + 480, y0 + 560), _pin(pick, "A"))
    _connect(_pin(limb_or_body, "ReturnValue", is_input=False), _pin(pick, "B"))
    _connect(is_head, _pin(pick, "bPickA"))
    return _pin(pick, "ReturnValue", is_input=False), made


def _detach_rules(node):
    # KeepWorld everywhere: a dropped weapon should stay exactly where it was in
    # world space and then be moved deliberately, not snap back to the origin.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(node, rule, "KeepWorld")


def _author_drop(ed, held, owner, exec_in, x0, y0):
    """Detach the held weapon, drop it on the ground in front of the player."""
    made = []

    def keep(n):
        made.append(n)
        return n

    flag = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH), x0, y0))
    _connect(held, _pin(flag, "self"))
    _set(flag, "Dropped", "true")
    _connect(exec_in, _pin(flag, "execute"))

    off = keep(_at(_node(ed, FN_DETACH), x0 + 280, y0))
    _connect(held, _pin(off, "self"))
    _detach_rules(off)
    _connect(BEL.find_then_pin(flag), _pin(off, "execute"))

    loc = keep(_at(_node(ed, FN_ACTOR_LOC), x0, y0 + 300))
    _connect(owner, _pin(loc, "self"))
    rot = keep(_at(_node(ed, "/Script/Engine.Actor.K2_GetActorRotation"), x0, y0 + 420))
    _connect(owner, _pin(rot, "self"))
    fwd = keep(_at(_node(ed, FN_FORWARD), x0 + 240, y0 + 420))
    _connect(_pin(rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))
    ahead = keep(_at(_node(ed, FN_MUL_VF), x0 + 480, y0 + 420))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(ahead, "A"))
    # A vector literal, for the same reason as the aim ray: with nothing
    # connected, this operator's B pin is a struct pin and will not take a
    # number. Until _set started reading pins back, this silently stayed empty
    # and dropped weapons landed on the player's own feet.
    _connect(_vec(ed, DROP_FORWARD, DROP_FORWARD, DROP_FORWARD, x0 + 240, y0 + 560),
             _pin(ahead, "B"))
    start = keep(_at(_node(ed, FN_ADD_VV), x0 + 720, y0 + 340))
    _connect(_pin(loc, "ReturnValue", is_input=False), _pin(start, "A"))
    _connect(_pin(ahead, "ReturnValue", is_input=False), _pin(start, "B"))

    down = keep(_at(_node(ed, FN_ADD_VV), x0 + 960, y0 + 460))
    _connect(_pin(start, "ReturnValue", is_input=False), _pin(down, "A"))
    _connect(_vec(ed, 0.0, 0.0, -400.0, x0 + 720, y0 + 580), _pin(down, "B"))

    # Trace down so the weapon lands on the terrain instead of hanging at hip
    # height. The forest floor is a mesh, not a plane, so a fixed Z would float
    # or bury it depending on where the player is standing.
    ground = keep(_at(_node(ed, FN_TRACE), x0 + 1220, y0))
    _connect(_pin(start, "ReturnValue", is_input=False), _pin(ground, "Start"))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(ground, "End"))
    _set(ground, "TraceChannel", "TraceTypeQuery1")
    _set(ground, "bTraceComplex", "false")
    _set(ground, "bIgnoreSelf", "true")
    _set(ground, "DrawDebugType", "None")
    _connect(BEL.find_then_pin(off), _pin(ground, "execute"))

    landed = keep(_at(ed.add_branch_node(), x0 + 1500, y0))
    _connect(_pin(ground, "ReturnValue", is_input=False), _pin(landed, "Condition"))
    _connect(BEL.find_then_pin(ground), _pin(landed, "execute"))
    brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 1500, y0 + 300))
    _connect(_pin(ground, "OutHit", is_input=False), _loose_pin(brk, "Hit"))

    lift = keep(_at(_node(ed, FN_ADD_VV), x0 + 1760, y0 + 300))
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(lift, "A"))
    _connect(_vec(ed, 0.0, 0.0, 12.0, x0 + 1520, y0 + 440), _pin(lift, "B"))

    on_ground = keep(_at(_node(ed, FN_SET_ACTOR_LOC), x0 + 2020, y0 - 120))
    _connect(held, _pin(on_ground, "self"))
    _connect(_pin(lift, "ReturnValue", is_input=False), _pin(on_ground, "NewLocation"))
    _connect(BEL.find_then_pin(landed), _pin(on_ground, "execute"))

    in_air = keep(_at(_node(ed, FN_SET_ACTOR_LOC), x0 + 2020, y0 + 120))
    _connect(held, _pin(in_air, "self"))
    _connect(_pin(start, "ReturnValue", is_input=False), _pin(in_air, "NewLocation"))
    _connect(BEL.find_else_pin(landed), _pin(in_air, "execute"))

    # Both placements rejoin here; an exec input takes more than one link.
    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 2300, y0 + 240))
    idx = keep(_at(ed.add_get_member_variable_node("EquippedIndex"), x0 + 2300, y0 + 360))
    remove = keep(_at(_node(ed, FN_ARR_REMOVE), x0 + 2540, y0))
    _connect(_pin(inv, "Inventory", is_input=False), _pin(remove, "TargetArray"))
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(remove, "IndexToRemove"))
    _connect(BEL.find_then_pin(on_ground), _pin(remove, "execute"))
    _connect(BEL.find_then_pin(in_air), _pin(remove, "execute"))

    # Held is set with its input pin left unconnected, which is how a Blueprint
    # object variable is cleared to None.
    clear = keep(_at(ed.add_set_member_variable_node("Held"), x0 + 2800, y0))
    _connect(BEL.find_then_pin(remove), _pin(clear, "execute"))
    reset = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 3060, y0))
    _set(reset, "EquippedIndex", 0)
    _connect(BEL.find_then_pin(clear), _pin(reset, "execute"))

    ed.add_comment_to_nodes(
        f"{DROP_KEY} drops the equipped weapon {DROP_FORWARD:.0f} cm ahead, "
        "traced down onto the terrain, and takes it out of Inventory. It stays "
        "in the world as an ordinary actor with Dropped set, which is the only "
        "thing pick-up looks for.",
        made)
    return BEL.find_then_pin(reset)


def _author_pickup(ed, owner, exec_in, x0, y0):
    """E: take the nearest dropped weapon, if there is room for it."""
    made = []

    def keep(n):
        made.append(n)
        return n

    cls = keep(_at(ed.add_get_member_variable_node("ItemClass"), x0, y0 + 240))
    every = keep(_at(_node(ed, FN_ALL_ACTORS), x0 + 240, y0))
    _connect(_pin(cls, "ItemClass", is_input=False), _pin(every, "ActorClass"))
    _connect(exec_in, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 520, y0))
    _connect(_pin(every, "OutActors", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(every), _loose_pin(loop, "Exec"))
    element = _loose_pin(loop, "ArrayElement", is_input=False)

    cast = keep(_at(_palette(ed, "Utilities|Casting|CastToBP_WeaponItem"), x0 + 820, y0))
    _connect(element, _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    dropped_pin, dropped_n = _prop(ed, "Dropped", item, x0 + 1100, y0 + 260)
    keep(dropped_n)

    there = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1100, y0 + 400))
    _connect(item, _pin(there, "self"))
    here = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1100, y0 + 520))
    _connect(owner, _pin(here, "self"))
    gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 1360, y0 + 440))
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(gap, "V1"))
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(gap, "V2"))
    near = keep(_at(_node(ed, FN_LESS_FF), x0 + 1600, y0 + 440))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(near, "A"))
    _set(near, "B", PICKUP_RADIUS)

    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 1100, y0 + 660))
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 1360, y0 + 660))
    _connect(_pin(inv, "Inventory", is_input=False), _pin(count, "TargetArray"))
    room = keep(_at(_node(ed, FN_LESS_II), x0 + 1600, y0 + 660))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(room, "A"))
    _set(room, "B", INVENTORY_SIZE)

    # The room check is inside the loop, not before it: without it a player
    # standing on a pile would pick up every weapon at once and overflow the
    # five slots the HUD draws.
    and1 = keep(_at(_node(ed, FN_AND), x0 + 1840, y0 + 340))
    _connect(dropped_pin, _pin(and1, "A"))
    _connect(_pin(near, "ReturnValue", is_input=False), _pin(and1, "B"))
    and2 = keep(_at(_node(ed, FN_AND), x0 + 2080, y0 + 420))
    _connect(_pin(and1, "ReturnValue", is_input=False), _pin(and2, "A"))
    _connect(_pin(room, "ReturnValue", is_input=False), _pin(and2, "B"))

    take = keep(_at(ed.add_branch_node(), x0 + 2320, y0))
    _connect(_pin(and2, "ReturnValue", is_input=False), _pin(take, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(take, "execute"))

    clear = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
                     x0 + 2580, y0))
    _connect(item, _pin(clear, "self"))
    _set(clear, "Dropped", "false")
    _connect(BEL.find_then_pin(take), _pin(clear, "execute"))

    inv2 = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 2580, y0 + 300))
    add = keep(_at(_node(ed, FN_ARR_ADD), x0 + 2840, y0))
    _connect(_pin(inv2, "Inventory", is_input=False), _pin(add, "TargetArray"))
    _connect(item, _pin(add, "NewItem"))
    _connect(BEL.find_then_pin(clear), _pin(add, "execute"))

    # Equip what was just picked up: its index is the new last one.
    at = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 3100, y0))
    _connect(_pin(add, "ReturnValue", is_input=False), _pin(at, "EquippedIndex"))
    _connect(BEL.find_then_pin(add), _pin(at, "execute"))

    ed.add_comment_to_nodes(
        f"{PICKUP_KEY} picks up any weapon within {PICKUP_RADIUS:.0f} cm that is "
        f"flagged Dropped, while fewer than {INVENTORY_SIZE} are carried, and "
        "equips it. Array_Add returns the new item's index, which is exactly "
        "the slot to switch to.",
        made)
    return _loose_pin(loop, "Completed", is_input=False)


def _author_equip(ed, exec_in, x0, y0):
    """Show exactly one weapon in the hand, hide the rest, play its ready pose.

    Weapons are spawned once and kept: equipping hides and shows actors rather
    than destroying and respawning them, so a weapon keeps its identity (and
    could keep its ammo, condition, anything) across switches, and so dropping
    can hand the very same actor to the world.

    It is also where sprinting stops looking absurd. The ready pose is a
    montage in an upper-body slot; a sprinting player with it still playing
    runs with the barrel levelled at the horizon and the arms locked, which is
    the one animation complaint this project has had. The fix is not a new
    animation -- it is *not playing* this one: stop the slot, and the layered
    blend has nothing left to override the locomotion state machine with, so
    the character runs with its own run cycle and the weapon goes along in the
    hand socket where it is attached. Sprint's own block in Tick raises
    NeedsRefresh on the frame the state flips, which is what routes back here.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0, y0 + 240))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 260, y0))
    _connect(_pin(inv, "Inventory", is_input=False), _loose_pin(loop, "Array"))
    _connect(exec_in, _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    idx = keep(_at(ed.add_get_member_variable_node("EquippedIndex"), x0 + 560, y0 + 320))
    same = keep(_at(_node(ed, FN_EQ_II), x0 + 800, y0 + 260))
    _connect(_loose_pin(loop, "ArrayIndex", is_input=False), _pin(same, "A"))
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(same, "B"))

    chosen = keep(_at(ed.add_branch_node(), x0 + 1040, y0))
    _connect(_pin(same, "ReturnValue", is_input=False), _pin(chosen, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(chosen, "execute"))

    show = keep(_at(_node(ed, FN_SET_HIDDEN), x0 + 1300, y0 - 160))
    _connect(item, _pin(show, "self"))
    _set(show, "bNewHidden", "false")
    _connect(BEL.find_then_pin(chosen), _pin(show, "execute"))

    hide = keep(_at(_node(ed, FN_SET_HIDDEN), x0 + 1300, y0 + 420))
    _connect(item, _pin(hide, "self"))
    _set(hide, "bNewHidden", "true")
    _connect(BEL.find_else_pin(chosen), _pin(hide, "execute"))

    mesh = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0 + 1300, y0 + 40))
    attach = keep(_at(_node(ed, FN_ATTACH), x0 + 1580, y0 - 160))
    _connect(item, _pin(attach, "self"))
    _connect(_pin(mesh, "OwnerMesh", is_input=False), _pin(attach, "Parent"))
    _set(attach, "SocketName", player_skin().grip)
    # Snap first, then apply the weapon's own grip offset explicitly. Snapping
    # gives a known starting transform; KeepRelative would carry over whatever
    # the actor happened to be at, which after a drop is a world position.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(attach, rule, "SnapToTarget")
    _connect(BEL.find_then_pin(show), _pin(attach, "execute"))

    gl_pin, gl_n = _prop(ed, "GripLocation", item, x0 + 1580, y0 + 120)
    keep(gl_n)
    put = keep(_at(_node(ed, FN_SET_REL_LOC), x0 + 1860, y0 - 160))
    _connect(item, _pin(put, "self"))
    _connect(gl_pin, _pin(put, "NewRelativeLocation"))
    _connect(BEL.find_then_pin(attach), _pin(put, "execute"))

    # The resting orientation only. From the next frame on, Tick points the
    # held weapon at the aim point; this just stops it being visibly wrong for
    # the one frame in between.
    gr_pin, gr_n = _prop(ed, "GripRotation", item, x0 + 1860, y0 + 120)
    keep(gr_n)
    turn = keep(_at(_node(ed, FN_SET_REL_ROT), x0 + 2140, y0 - 160))
    _connect(item, _pin(turn, "self"))
    _connect(gr_pin, _pin(turn, "NewRelativeRotation"))
    _connect(BEL.find_then_pin(put), _pin(turn, "execute"))

    hold = keep(_at(ed.add_set_member_variable_node("Held"), x0 + 2420, y0 - 160))
    _connect(item, _pin(hold, "Held"))
    _connect(BEL.find_then_pin(turn), _pin(hold, "execute"))

    # --- once the loop is done, drive the ready pose -------------------------
    held_get = keep(_at(ed.add_get_member_variable_node("Held"), x0 + 2700, y0 + 300))
    held = _pin(held_get, "Held", is_input=False)
    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 2940, y0 + 300))
    _connect(held, _pin(armed, "Object"))
    # Safe to fold into one condition, unlike the fire gate's ammunition tests:
    # IsValid takes a null object as an answer rather than as an error, and
    # Sprinting is this component's own bool. Neither read can touch Held.
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"),
                       x0 + 2700, y0 + 480))
    still = keep(_at(_node(ed, FN_NOT), x0 + 2940, y0 + 480))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))
    shown = keep(_at(_node(ed, FN_AND), x0 + 3180, y0 + 400))
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(shown, "A"))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(shown, "B"))
    posing = keep(_at(ed.add_branch_node(), x0 + 3420, y0))
    _connect(_pin(shown, "ReturnValue", is_input=False), _pin(posing, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(posing, "execute"))

    mesh2 = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0 + 3180, y0 + 440))
    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 3420, y0 + 440))
    _connect(_pin(mesh2, "OwnerMesh", is_input=False), _pin(anim, "self"))
    anim_out = _pin(anim, "ReturnValue", is_input=False)

    pose_pin, pose_n = _prop(ed, "AimPose", held, x0 + 3420, y0 + 200)
    keep(pose_n)
    play = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 3700, y0 - 100))
    _connect(anim_out, _pin(play, "self"))
    _connect(pose_pin, _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", AIM_BLEND)
    _set(play, "BlendOutTime", AIM_BLEND)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", AIM_LOOPS)
    _connect(BEL.find_then_pin(posing), _pin(play, "execute"))

    stop = keep(_at(_node(ed, FN_STOP_SLOT), x0 + 3700, y0 + 200))
    _connect(anim_out, _pin(stop, "self"))
    _set(stop, "InBlendOutTime", AIM_BLEND)
    _set(stop, "SlotNodeName", AIM_SLOT)
    _connect(BEL.find_else_pin(posing), _pin(stop, "execute"))

    ed.add_comment_to_nodes(
        f"The ready pose is the weapon's own AimPose played into {AIM_SLOT}, "
        f"looping {AIM_LOOPS} times because PlaySlotAnimationAsDynamicMontage "
        "has no infinite option. It reads as a pose rather than a full-body "
        "animation only because patch_anim_blueprint() put a spine_01 layered "
        "blend around that slot in ABP_Unarmed -- without it the legs would "
        "freeze mid-stride. Empty hands stop the slot and locomotion returns, "
        "and so does sprinting: you cannot fire while running, so there is "
        "nothing for a ready pose to be ready for.",
        made)


def _author_wc_begin_play(ed, begin):
    """Cache the character's mesh, spawn the starting loadout, equip slot 0."""
    made = []

    def keep(n):
        made.append(n)
        return n

    owner = keep(_at(_node(ed, FN_GET_OWNER), 240, -1060))
    cast = keep(_at(_palette(ed, NODE_CAST_CHAR), 500, -1200))
    _connect(_pin(owner, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(begin), _pin(cast, "execute"))
    as_char = _loose_pin(cast, "AsBPThirdPersonCharacter", is_input=False)

    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    780, -1020))
    _connect(as_char, _pin(mesh, "self"))
    remember = keep(_at(ed.add_set_member_variable_node("OwnerMesh"), 1040, -1200))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(remember, "OwnerMesh"))
    _connect(BEL.find_then_pin(cast), _pin(remember, "execute"))

    # Whatever the character's own walking speed is, before sprint ever touches
    # it. Cached rather than written down here: a literal would silently fight
    # any later change to BP_ThirdPersonCharacter's movement defaults, and the
    # symptom -- "the player walks at the wrong speed, but only after
    # sprinting once" -- would point at the sprint code instead of at the copy.
    movement = keep(_at(ed.add_get_member_variable_node(
        "CharacterMovement", "/Script/Engine.Character"), 1040, -1560))
    _connect(as_char, _pin(movement, "self"))
    walk = keep(_at(ed.add_get_member_variable_node(
        "MaxWalkSpeed", MOVEMENT_CLASS_PATH), 1300, -1560))
    _connect(_pin(movement, "CharacterMovement", is_input=False), _pin(walk, "self"))
    cache = keep(_at(ed.add_set_member_variable_node("BaseSpeed"), 1300, -1420))
    _connect(_pin(walk, "MaxWalkSpeed", is_input=False), _pin(cache, "BaseSpeed"))
    _connect(BEL.find_then_pin(remember), _pin(cache, "execute"))

    # And whatever the camera's own field of view is, for the same reason and
    # with the same failure mode: a literal 90 here would silently fight the
    # camera asset, and the symptom -- "the view is subtly wrong, but only
    # after aiming once" -- would point at the ADS code rather than at the copy.
    cam = keep(_at(_node(ed, FN_GET_COMP), 1040, -1700))
    _connect(as_char, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    fov = keep(_at(ed.add_get_member_variable_node("FieldOfView", CAMERA_CLASS_PATH),
                   1300, -1700))
    _connect(_pin(cam, "ReturnValue", is_input=False), _pin(fov, "self"))
    fov_out = _pin(fov, "FieldOfView", is_input=False)
    base_fov = keep(_at(ed.add_set_member_variable_node("BaseFOV"), 1560, -1700))
    _connect(fov_out, _pin(base_fov, "BaseFOV"))
    _connect(BEL.find_then_pin(cache), _pin(base_fov, "execute"))
    # Start the interpolation where the camera already is, or the first frame
    # lerps from zero and the view snaps open.
    now_fov = keep(_at(ed.add_set_member_variable_node("CurrentFOV"), 1820, -1700))
    _connect(fov_out, _pin(now_fov, "CurrentFOV"))
    _connect(BEL.find_then_pin(base_fov), _pin(now_fov, "execute"))

    # And whatever the controller's own look scales already are, for the third
    # time in this function and for the third identical reason. The pitch one
    # is the reason this is a cache and not a constant: the engine ships it
    # NEGATIVE (-2.5), so any literal written here would have a one-in-two
    # chance of inverting the player's vertical look, and the symptom -- "the
    # mouse is upside down, but only after aiming once" -- would send whoever
    # chased it into the ADS code rather than into this line.
    pc = keep(_at(_node(ed, FN_GET_PC), 1040, -1840))
    _set(pc, "PlayerIndex", 0)
    pc_out = _pin(pc, "ReturnValue", is_input=False)
    yaw_now = keep(_at(_node(ed, FN_GET_YAW_SCALE), 1300, -1840))
    _connect(pc_out, _pin(yaw_now, "self"))
    keep_yaw = keep(_at(ed.add_set_member_variable_node("BaseYawScale"), 2080, -1700))
    _connect(_pin(yaw_now, "ReturnValue", is_input=False), _pin(keep_yaw, "BaseYawScale"))
    _connect(BEL.find_then_pin(now_fov), _pin(keep_yaw, "execute"))
    pitch_now = keep(_at(_node(ed, FN_GET_PITCH_SCALE), 1300, -1960))
    _connect(pc_out, _pin(pitch_now, "self"))
    keep_pitch = keep(_at(ed.add_set_member_variable_node("BasePitchScale"),
                          2340, -1700))
    _connect(_pin(pitch_now, "ReturnValue", is_input=False),
             _pin(keep_pitch, "BasePitchScale"))
    _connect(BEL.find_then_pin(keep_yaw), _pin(keep_pitch, "execute"))

    where = keep(_at(_node(ed, FN_GET_TRANSFORM), 1040, -1000))
    _connect(as_char, _pin(where, "self"))
    spawn_at = _pin(where, "ReturnValue", is_input=False)

    prev = BEL.find_then_pin(keep_pitch)
    for i, var in enumerate(("ShotgunClass", "PistolClass")):
        cls = keep(_at(ed.add_get_member_variable_node(var), 1300, -1020 + i * 460))
        spawn = keep(_at(_palette(ed, NODE_SPAWN), 1560, -1200 + i * 460))
        _connect(_pin(cls, var, is_input=False), _pin(spawn, "Class"))
        _connect(spawn_at, _pin(spawn, "SpawnTransform"))
        _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
        _connect(prev, _pin(spawn, "execute"))

        inv = keep(_at(ed.add_get_member_variable_node("Inventory"),
                       1840, -1000 + i * 460))
        add = keep(_at(_node(ed, FN_ARR_ADD), 2100, -1200 + i * 460))
        _connect(_pin(inv, "Inventory", is_input=False), _pin(add, "TargetArray"))
        _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(add, "NewItem"))
        _connect(BEL.find_then_pin(spawn), _pin(add, "execute"))
        prev = BEL.find_then_pin(add)

    first = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), 2400, -1200))
    _set(first, "EquippedIndex", 0)
    _connect(prev, _pin(first, "execute"))
    dirty = keep(_at(ed.add_set_member_variable_node("NeedsRefresh"), 2660, -1200))
    _set(dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(first), _pin(dirty, "execute"))

    ed.add_comment_to_nodes(
        "The player starts carrying both weapons. They are spawned here rather "
        "than placed in the level so that a generated map needs no weapon "
        "actors in it -- nothing in Scripts/generated_levels knows weapons "
        "exist. NeedsRefresh makes Tick do the actual equipping, so the attach "
        "logic is authored exactly once.",
        made)


def _author_sprint(ed, tick, pc_out, owner_out, key_pin, exec_ins, x0, y0):
    """Hold Shift to run, while there is stamina left to spend.

    Written without a single Branch, which is not cleverness for its own sake:
    the two arms would otherwise be the same two writes with different numbers,
    and the pair could drift. SelectFloat picks the number, one write applies it:

        Sprinting = ShiftDown AND Stamina > 0
        MaxWalkSpeed = Sprinting ? SPRINT_SPEED : BaseSpeed
        Stamina += (Sprinting ? -drain : +regen) * DeltaSeconds,  clamped

    BaseSpeed is whatever the character's own MaxWalkSpeed was at BeginPlay, so
    sprinting can never leave the player permanently faster or slower than the
    character asset says they are -- which is exactly what a hardcoded "walk
    speed" here would do the first time someone retuned the character.

    Stamina lives on the *weapon* component rather than on the health one
    because the HUD already casts to this component every frame for the
    inventory strip and the reticle, and because the thing sprinting interacts
    with is firing: the fire gate below reads Sprinting.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # A cast, because MaxWalkSpeed lives on the CharacterMovementComponent and
    # GetOwner only promises an Actor. Its failure pin is a continuation: a
    # weapon component on something that is not a Character still has to fire.
    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0, y0))
    _connect(owner_out, _pin(as_char, "Object"))
    for e in exec_ins:
        _connect(e, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    movement = keep(_at(ed.add_get_member_variable_node(
        "CharacterMovement", "/Script/Engine.Character"), x0 + 240, y0 + 240))
    _connect(char_out, _pin(movement, "self"))
    movement_out = _pin(movement, "CharacterMovement", is_input=False)

    down = keep(_at(_node(ed, FN_IS_KEY_DOWN), x0 + 240, y0 + 420))
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))

    stamina = keep(_at(ed.add_get_member_variable_node("Stamina"), x0 + 240, y0 + 560))
    stamina_out = _pin(stamina, "Stamina", is_input=False)
    left = keep(_at(_node(ed, FN_GREATER_FF), x0 + 480, y0 + 560))
    _connect(stamina_out, _pin(left, "A"))
    _set(left, "B", 0.0)

    running = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 460))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(running, "A"))
    _connect(_pin(left, "ReturnValue", is_input=False), _pin(running, "B"))
    mark = keep(_at(ed.add_set_member_variable_node("Sprinting"), x0 + 960, y0))
    _connect(_pin(running, "ReturnValue", is_input=False), _pin(mark, "Sprinting"))
    _connect(BEL.find_then_pin(as_char), _pin(mark, "execute"))
    # Read the stored flag from here on, for the same reason the NPC id is read
    # back from its variable: the AND is pure and would be re-evaluated per read.
    is_running = keep(_at(ed.add_get_member_variable_node("Sprinting"),
                          x0 + 960, y0 + 460))
    running_out = _pin(is_running, "Sprinting", is_input=False)

    base = keep(_at(ed.add_get_member_variable_node("BaseSpeed"), x0 + 1200, y0 + 300))
    pick_speed = keep(_at(_node(ed, FN_SELECT_FF), x0 + 1440, y0 + 300))
    _set(pick_speed, "A", COMBAT.sprint_speed_cms)
    _connect(_pin(base, "BaseSpeed", is_input=False), _pin(pick_speed, "B"))
    _connect(running_out, _pin(pick_speed, "bPickA"))
    apply_speed = keep(_at(ed.add_set_member_variable_node(
        "MaxWalkSpeed", MOVEMENT_CLASS_PATH), x0 + 1700, y0))
    _connect(movement_out, _pin(apply_speed, "self"))
    _connect(_pin(pick_speed, "ReturnValue", is_input=False),
             _pin(apply_speed, "MaxWalkSpeed"))
    _connect(BEL.find_then_pin(mark), _pin(apply_speed, "execute"))

    rate = keep(_at(_node(ed, FN_SELECT_FF), x0 + 1440, y0 + 620))
    _set(rate, "A", -COMBAT.stamina_drain_per_s)
    _set(rate, "B", COMBAT.stamina_regen_per_s)
    _connect(running_out, _pin(rate, "bPickA"))
    step = keep(_at(_node(ed, FN_MUL_FF), x0 + 1700, y0 + 620))
    _connect(_pin(rate, "ReturnValue", is_input=False), _pin(step, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "B"))
    moved = keep(_at(_node(ed, FN_ADD_FF), x0 + 1940, y0 + 620))
    _connect(stamina_out, _pin(moved, "A"))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(moved, "B"))
    held_in = keep(_at(_node(ed, FN_CLAMP), x0 + 2180, y0 + 620))
    _connect(_pin(moved, "ReturnValue", is_input=False), _pin(held_in, "Value"))
    _set(held_in, "Min", 0.0)
    _set(held_in, "Max", COMBAT.max_stamina)
    spend = keep(_at(ed.add_set_member_variable_node("Stamina"), x0 + 2420, y0))
    _connect(_pin(held_in, "ReturnValue", is_input=False), _pin(spend, "Stamina"))
    _connect(BEL.find_then_pin(apply_speed), _pin(spend, "execute"))

    ed.add_comment_to_nodes(
        f"{SPRINT_KEY}: {COMBAT.sprint_speed_cms:.0f} cm/s while Stamina lasts "
        f"({COMBAT.max_stamina / COMBAT.stamina_drain_per_s:.0f} s from full), refilling at "
        f"{COMBAT.stamina_regen_per_s:.0f}/s the moment it is let go. No Branch: "
        f"SelectFloat picks the speed and the sign of the drain, so there is one "
        f"write of each and the two arms cannot drift apart. The fire gate below "
        f"reads Sprinting -- you cannot shoot while running.",
        made)
    return (BEL.find_then_pin(spend),
            _pin(as_char, "CastFailed", is_input=False))


def _author_ads(ed, tick, pc_out, owner_out, held, armed_out, key_pin,
                exec_ins, x0, y0):
    """Right mouse held: narrow the camera to this weapon's AdsZoom.

        Aiming   = RightMouseButton down AND something is equipped
                                          AND not sprinting
        TargetFOV = Aiming ? BaseFOV / Held.AdsZoom : BaseFOV
        CurrentFOV = FInterpTo(CurrentFOV, TargetFOV, dt, COMBAT.ads_interp_speed)
        Camera.SetFieldOfView(CurrentFOV)

    ...and then slow the mouse and the legs by how far that zoom has actually
    travelled, rather than by the key state. The legs are the second write of
    MaxWalkSpeed in this Tick; see the block itself for why that is the cheap
    way round.

    Three things are load-bearing here.

    Not while sprinting, because the fire gate already refuses to shoot while
    sprinting: a zoom that stayed on through a sprint would be aiming a weapon
    that cannot fire, and the view would be narrow exactly when the player is
    running away and needs it wide.

    Not with empty hands, because AdsZoom is read off Held and a pure Get off a
    null self is an Accessed None every frame. The read therefore sits inside
    the true arm of the branch, where Held is known valid -- pure nodes are
    pulled by whoever reads them, so the getter simply never runs on the frames
    nothing is equipped. That is the same trap ``Automatic`` is commented for
    above, and it has bitten this file before.

    Interpolated rather than snapped, and CurrentFOV is a stored variable
    because FInterpTo's input is its own previous output. Recomputing the
    target every frame and lerping toward it also means letting go of the
    button unzooms by the same curve with no second code path.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    down = keep(_at(_node(ed, FN_IS_KEY_DOWN), x0, y0 + 300))
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))

    # Sprinting has already been written this frame -- _author_sprint runs
    # before this block -- so this reads the flag rather than the key.
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"), x0, y0 + 420))
    still = keep(_at(_node(ed, FN_NOT_B), x0 + 240, y0 + 420))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))

    can = keep(_at(_node(ed, FN_AND), x0 + 480, y0 + 360))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(can, "A"))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(can, "B"))
    wants = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 300))
    _connect(_pin(can, "ReturnValue", is_input=False), _pin(wants, "A"))
    _connect(armed_out, _pin(wants, "B"))

    mark = keep(_at(ed.add_set_member_variable_node("Aiming"), x0 + 980, y0))
    _connect(_pin(wants, "ReturnValue", is_input=False), _pin(mark, "Aiming"))
    for e in exec_ins:
        _connect(e, _pin(mark, "execute"))

    base = keep(_at(ed.add_get_member_variable_node("BaseFOV"), x0 + 980, y0 + 420))
    base_out = _pin(base, "BaseFOV", is_input=False)

    aiming = keep(_at(ed.add_get_member_variable_node("Aiming"), x0 + 980, y0 + 300))
    zoomed = keep(_at(ed.add_branch_node(), x0 + 1240, y0))
    _connect(_pin(aiming, "Aiming", is_input=False), _pin(zoomed, "Condition"))
    _connect(BEL.find_then_pin(mark), _pin(zoomed, "execute"))

    # True arm: BaseFOV / this weapon's zoom. The AdsZoom getter lives here so
    # it is never pulled on a frame with nothing equipped.
    zoom_pin, zoom_n = _prop(ed, "AdsZoom", held, x0 + 1240, y0 + 420)
    keep(zoom_n)
    narrow = keep(_at(_node(ed, FN_DIV_FF), x0 + 1500, y0 + 420))
    _connect(base_out, _pin(narrow, "A"))
    _connect(zoom_pin, _pin(narrow, "B"))
    want_in = keep(_at(ed.add_set_member_variable_node("TargetFOV"), x0 + 1760, y0))
    _connect(_pin(narrow, "ReturnValue", is_input=False), _pin(want_in, "TargetFOV"))
    _connect(BEL.find_then_pin(zoomed), _pin(want_in, "execute"))

    want_out = keep(_at(ed.add_set_member_variable_node("TargetFOV"), x0 + 1760, y0 + 220))
    _connect(base_out, _pin(want_out, "TargetFOV"))
    _connect(BEL.find_else_pin(zoomed), _pin(want_out, "execute"))

    # --- move the camera toward it ------------------------------------------
    have = keep(_at(ed.add_get_member_variable_node("CurrentFOV"), x0 + 2020, y0 + 420))
    want = keep(_at(ed.add_get_member_variable_node("TargetFOV"), x0 + 2020, y0 + 540))
    step = keep(_at(_node(ed, FN_INTERP_FF), x0 + 2280, y0 + 420))
    _connect(_pin(have, "CurrentFOV", is_input=False), _pin(step, "Current"))
    _connect(_pin(want, "TargetFOV", is_input=False), _pin(step, "Target"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "DeltaTime"))
    _set(step, "InterpSpeed", COMBAT.ads_interp_speed)
    moved = keep(_at(ed.add_set_member_variable_node("CurrentFOV"), x0 + 2540, y0))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(moved, "CurrentFOV"))
    for tail in (BEL.find_then_pin(want_in), BEL.find_then_pin(want_out)):
        _connect(tail, _pin(moved, "execute"))

    cam = keep(_at(_node(ed, FN_GET_COMP), x0 + 2540, y0 + 420))
    _connect(owner_out, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    apply_fov = keep(_at(_node(ed, FN_SET_FOV), x0 + 2800, y0))
    _connect(_pin(cam, "ReturnValue", is_input=False), _pin(apply_fov, "self"))
    # Driven from the SET node's own pass-through output, not from a fresh
    # getter: the setter passes the value it wrote straight out, so this cannot
    # read a stale CurrentFOV the way a second Get would if anything were ever
    # spliced in between. That pin is called "Output_Get", NOT the variable's
    # own name -- a Set node's data output is named for what it does, not for
    # what it writes.
    _connect(_loose_pin(moved, "Output_Get", is_input=False),
             _pin(apply_fov, "InFieldOfView"))
    _connect(BEL.find_then_pin(moved), _pin(apply_fov, "execute"))

    # --- and slow the mouse by the same curve --------------------------------
    # Not "if aiming, use the slow number": the factor is read straight off how
    # far the zoom has actually travelled this frame, so it eases in and out
    # along the FInterpTo above, is automatically stronger on the 4x scope than
    # on 1.5x irons, and has no second code path for letting the button go.
    #
    #     eased = Lerp(1, CurrentFOV / BaseFOV, COMBAT.ads_sens_compensation)
    #     yaw   scale = BaseYawScale   * MouseSensitivity * eased
    #     pitch scale = BasePitchScale * MouseSensitivity * eased
    #
    # Both base scales are signed as the engine shipped them, so multiplying
    # by a positive sensitivity cannot flip the pitch axis.
    base_again = keep(_at(ed.add_get_member_variable_node("BaseFOV"),
                          x0 + 2800, y0 + 560))
    ratio = keep(_at(_node(ed, FN_DIV_FF), x0 + 3060, y0 + 480))
    _connect(_loose_pin(moved, "Output_Get", is_input=False), _pin(ratio, "A"))
    _connect(_pin(base_again, "BaseFOV", is_input=False), _pin(ratio, "B"))
    eased = keep(_at(_node(ed, FN_LERP), x0 + 3320, y0 + 480))
    _set(eased, "A", 1.0)
    _connect(_pin(ratio, "ReturnValue", is_input=False), _pin(eased, "B"))
    _set(eased, "Alpha", COMBAT.ads_sens_compensation)

    sens = keep(_at(ed.add_get_member_variable_node("MouseSensitivity"),
                    x0 + 3320, y0 + 620))
    factor = keep(_at(_node(ed, FN_MUL_FF), x0 + 3580, y0 + 480))
    _connect(_pin(eased, "ReturnValue", is_input=False), _pin(factor, "A"))
    _connect(_pin(sens, "MouseSensitivity", is_input=False), _pin(factor, "B"))
    factor_out = _pin(factor, "ReturnValue", is_input=False)

    flow = BEL.find_then_pin(apply_fov)
    for i, (var, setter, arg) in enumerate(
            (("BaseYawScale", FN_SET_YAW_SCALE, "NewValue"),
             ("BasePitchScale", FN_SET_PITCH_SCALE, "NewValue"))):
        base_scale = keep(_at(ed.add_get_member_variable_node(var),
                              x0 + 3840, y0 + 480 + i * 140))
        scaled = keep(_at(_node(ed, FN_MUL_FF), x0 + 4100, y0 + 480 + i * 140))
        _connect(_pin(base_scale, var, is_input=False), _pin(scaled, "A"))
        _connect(factor_out, _pin(scaled, "B"))
        put = keep(_at(_node(ed, setter), x0 + 4360, y0 + i * 220))
        _connect(pc_out, _pin(put, "self"))
        _connect(_pin(scaled, "ReturnValue", is_input=False),
                 _loose_pin(put, arg))
        _connect(flow, _pin(put, "execute"))
        flow = BEL.find_then_pin(put)

    # --- and slow the legs by the same curve ---------------------------------
    # A SECOND write of MaxWalkSpeed, after the one _author_sprint made earlier
    # in this same Tick, and that ordering is the whole design. Sprint writes
    # the speed unconditionally every frame -- Sprinting ? sprint_speed :
    # BaseSpeed -- so this write does not need an "undo" path at all: the frame
    # this branch stops running, sprint's write has already put the player back
    # at BaseSpeed. Moving the decision into _author_sprint instead was the
    # alternative, and it is worse: the aim state is resolved after the sprint
    # block (it reads Sprinting), and sprint's CastFailed pin is a live
    # continuation that would then need the same arithmetic on it.
    #
    # Gated on "not sprinting", the same pin the zoom is gated on, so the two
    # MaxWalkSpeed writes can never disagree about a frame: while Sprinting is
    # set this block does nothing and sprint's 900 stands, and letting go of
    # Shift hands the frame straight back here. Gated on armed as well,
    # because the AdsZoom read below needs a valid Held.
    #
    #     progress = FClamp((BaseFOV / CurrentFOV - 1) / (AdsZoom - 1), 0, 1)
    #     MaxWalkSpeed = BaseSpeed * Lerp(1, COMBAT.ads_move_speed_scale, progress)
    #
    # progress is the scope overlay's fade alpha, node for node -- how far the
    # camera has actually travelled toward this weapon's zoom, 0 at rest and 1
    # at full ADS. So the slowdown eases in and out on the FInterpTo above
    # instead of snapping on a key, it has no second code path for release, and
    # because it is NORMALISED by the weapon's own AdsZoom it lands on exactly
    # ads_move_speed_scale at full ADS for every weapon. The un-normalised
    # CurrentFOV/BaseFOV the sensitivity uses would have made the sniper slower
    # on its legs than the pistol, which is a zoom factor leaking into a
    # mechanic that has nothing to do with zoom.
    steady = keep(_at(_node(ed, FN_AND), x0 + 4620, y0 + 900))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(steady, "A"))
    _connect(armed_out, _pin(steady, "B"))
    slow_gate = keep(_at(ed.add_branch_node(), x0 + 4880, y0 + 760))
    _connect(_pin(steady, "ReturnValue", is_input=False), _pin(slow_gate, "Condition"))
    _connect(flow, _pin(slow_gate, "execute"))

    base_third = keep(_at(ed.add_get_member_variable_node("BaseFOV"),
                          x0 + 4880, y0 + 1040))
    zoom_ratio = keep(_at(_node(ed, FN_DIV_FF), x0 + 5140, y0 + 1040))
    _connect(_pin(base_third, "BaseFOV", is_input=False), _pin(zoom_ratio, "A"))
    _connect(_loose_pin(moved, "Output_Get", is_input=False), _pin(zoom_ratio, "B"))
    so_far = keep(_at(_node(ed, FN_SUB_FF), x0 + 5400, y0 + 1040))
    _connect(_pin(zoom_ratio, "ReturnValue", is_input=False), _pin(so_far, "A"))
    _set(so_far, "B", 1.0)

    # The denominator is this weapon's own zoom, not the config's, for the same
    # reason the scope's fade uses it: 4x has four times as far to travel.
    zoom_again, zoom_again_n = _prop(ed, "AdsZoom", held, x0 + 5140, y0 + 1180)
    keep(zoom_again_n)
    span = keep(_at(_node(ed, FN_SUB_FF), x0 + 5400, y0 + 1180))
    _connect(zoom_again, _pin(span, "A"))
    _set(span, "B", 1.0)

    frac = keep(_at(_node(ed, FN_DIV_FF), x0 + 5660, y0 + 1040))
    _connect(_pin(so_far, "ReturnValue", is_input=False), _pin(frac, "A"))
    _connect(_pin(span, "ReturnValue", is_input=False), _pin(frac, "B"))
    # Clamped because the FInterpTo can overshoot its target by a fraction on a
    # long frame, and an unclamped progress of 1.02 is a walk speed below the
    # configured floor -- small, but it would be a number nobody chose.
    progress = keep(_at(_node(ed, FN_CLAMP), x0 + 5920, y0 + 1040))
    _connect(_pin(frac, "ReturnValue", is_input=False), _pin(progress, "Value"))
    _set(progress, "Min", 0.0)
    _set(progress, "Max", 1.0)

    slowed = keep(_at(_node(ed, FN_LERP), x0 + 6180, y0 + 1040))
    _set(slowed, "A", 1.0)
    _set(slowed, "B", COMBAT.ads_move_speed_scale)
    _connect(_pin(progress, "ReturnValue", is_input=False), _pin(slowed, "Alpha"))
    # Off BaseSpeed, not off the speed that is currently set: this runs every
    # frame, so a factor applied to the live value would compound.
    walked = keep(_at(ed.add_get_member_variable_node("BaseSpeed"),
                      x0 + 6180, y0 + 1180))
    speed = keep(_at(_node(ed, FN_MUL_FF), x0 + 6440, y0 + 1040))
    _connect(_pin(walked, "BaseSpeed", is_input=False), _pin(speed, "A"))
    _connect(_pin(slowed, "ReturnValue", is_input=False), _pin(speed, "B"))

    # No cast: GetComponentByClass reshapes its return pin to the class chosen
    # on ComponentClass, so this wires straight into the movement component's
    # own setter. _author_sprint casts to Character instead only because it
    # needs the CastFailed pin as a continuation; here the branch above is
    # already the guard.
    legs = keep(_at(_node(ed, FN_GET_COMP), x0 + 5140, y0 + 900))
    _connect(owner_out, _pin(legs, "self"))
    _pin(legs, "ComponentClass").set_pin_value(MOVEMENT_CLASS_PATH)
    apply_speed = keep(_at(ed.add_set_member_variable_node(
        "MaxWalkSpeed", MOVEMENT_CLASS_PATH), x0 + 6700, y0 + 760))
    _connect(_pin(legs, "ReturnValue", is_input=False), _pin(apply_speed, "self"))
    _connect(_pin(speed, "ReturnValue", is_input=False),
             _pin(apply_speed, "MaxWalkSpeed"))
    _connect(BEL.find_then_pin(slow_gate), _pin(apply_speed, "execute"))

    ed.add_comment_to_nodes(
        f"{AIM_KEY}: zoom to BaseFOV / the weapon's own AdsZoom "
        f"({COMBAT.ads_zoom_irons:g}x irons, {COMBAT.ads_zoom_scope:g}x on the sniper's "
        f"scope), interpolated at {COMBAT.ads_interp_speed:g} so it arrives in about "
        f"a fifth of a second. Refused while sprinting -- the fire gate already "
        f"is -- and with empty hands, which is also what keeps the AdsZoom "
        f"getter off a null Held. The cone shrinks to "
        f"{COMBAT.ads_spread_scale:g}x while Aiming; see _author_fire. The mouse "
        f"slows with the zoom rather than with the button: "
        f"Lerp(1, CurrentFOV/BaseFOV, {COMBAT.ads_sens_compensation:g}) scaling both "
        f"of the controller's cached look scales, so a 4x scope is slower than "
        f"1.5x irons for free and the slowdown eases in on the same curve. "
        f"The legs slow too, to {COMBAT.ads_move_speed_scale:g}x BaseSpeed at full "
        f"ADS, on the scope overlay's own fade curve -- a second MaxWalkSpeed "
        f"write after the sprint block's, which is what makes releasing the "
        f"button need no code: sprint restores BaseSpeed unconditionally on "
        f"the next frame.",
        made)
    return (BEL.find_then_pin(apply_speed), BEL.find_else_pin(slow_gate))


def _author_reload(ed, held, exec_in, x0, y0):
    """R: top the magazine up from the reserve, and stand still for a moment.

    How many rounds move is worked out ONCE and stored in ReloadTake before
    anything is written. The arithmetic is pure, so a second read of
    ``Min(MagazineSize - Loaded, Reserve)`` after Loaded has been raised would
    quietly return a different (smaller) number, and the reserve would be
    charged less than the magazine gained -- the pure-node trap this file keeps
    running into, in its most expensive form yet: free ammunition.

    There is no reloading *state*. The cost is a deadline pushed out on the
    weapon's own NextFireTime, which is the same field the interval between
    shots uses, so "cannot fire yet" has exactly one meaning in the whole
    system and nothing has to decide which of two rules is in force.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    mag, mag_n = _prop(ed, "MagazineSize", held, x0, y0 + 300)
    have, have_n = _prop(ed, "Loaded", held, x0, y0 + 420)
    keep(mag_n), keep(have_n)
    gap = keep(_at(_node(ed, FN_SUB_II), x0 + 260, y0 + 300))
    _connect(mag, _pin(gap, "A"))
    _connect(have, _pin(gap, "B"))
    spare, spare_n = _prop(ed, "Reserve", held, x0, y0 + 560)
    keep(spare_n)
    # Min, so a reserve of one tops a magazine that is four short up by one and
    # not by four -- and so the reserve can never be driven negative.
    moving = keep(_at(_node(ed, FN_MIN_II), x0 + 520, y0 + 300))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(moving, "A"))
    _connect(spare, _pin(moving, "B"))
    pin_take = keep(_at(ed.add_set_member_variable_node("ReloadTake"), x0 + 780, y0))
    _connect(_pin(moving, "ReturnValue", is_input=False), _pin(pin_take, "ReloadTake"))
    _connect(exec_in, _pin(pin_take, "execute"))

    uses, uses_n = _prop(ed, "UsesAmmo", held, x0 + 780, y0 + 420)
    keep(uses_n)
    take_get = keep(_at(ed.add_get_member_variable_node("ReloadTake"),
                        x0 + 780, y0 + 540))
    any_left = keep(_at(_node(ed, FN_GREATER_II), x0 + 1020, y0 + 540))
    _connect(_pin(take_get, "ReloadTake", is_input=False), _pin(any_left, "A"))
    _set(any_left, "B", 0)
    worth = keep(_at(_node(ed, FN_AND), x0 + 1260, y0 + 460))
    _connect(uses, _pin(worth, "A"))
    _connect(_pin(any_left, "ReturnValue", is_input=False), _pin(worth, "B"))

    # An unlimited weapon and a full magazine both take the False arm, and both
    # skip the pause -- a reload that cost 1.6 s and moved nothing would be a
    # way to punish the player for pressing a key that did not apply.
    does = keep(_at(ed.add_branch_node(), x0 + 1520, y0))
    _connect(_pin(worth, "ReturnValue", is_input=False), _pin(does, "Condition"))
    _connect(BEL.find_then_pin(pin_take), _pin(does, "execute"))

    # The clack, on the True arm only. On the False arm nothing moves, so a
    # sound there would be the game telling the player it had done something it
    # had not -- which is worse than silence, because the pause that normally
    # follows a reload would not happen either.
    #
    # Placed at the weapon rather than at the player: the gun is in the
    # player's hands, so the two are the same position to within a few
    # centimetres, and reading the weapon's transform needs no owner cast.
    at = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1520, y0 + 300))
    _connect(held, _pin(at, "self"))
    clack_pin, clack_n = _prop(ed, "ReloadSound", held, x0 + 1520, y0 + 180)
    keep(clack_n)
    clack = keep(_at(_node(ed, FN_PLAY_SOUND), x0 + 1780, y0))
    _connect(clack_pin, _pin(clack, "Sound"))
    _connect(_pin(at, "ReturnValue", is_input=False), _pin(clack, "Location"))
    _connect(BEL.find_then_pin(does), _pin(clack, "execute"))

    take_a = keep(_at(ed.add_get_member_variable_node("ReloadTake"),
                      x0 + 1780, y0 + 420))
    was, was_n = _prop(ed, "Loaded", held, x0 + 1780, y0 + 300)
    keep(was_n)
    filled = keep(_at(_node(ed, FN_ADD_II), x0 + 2020, y0 + 300))
    _connect(was, _pin(filled, "A"))
    _connect(_pin(take_a, "ReloadTake", is_input=False), _pin(filled, "B"))
    load = keep(_at(ed.add_set_member_variable_node("Loaded", ITEM_CLASS_PATH),
                    x0 + 2280, y0))
    _connect(held, _pin(load, "self"))
    _connect(_pin(filled, "ReturnValue", is_input=False), _pin(load, "Loaded"))
    _connect(BEL.find_then_pin(clack), _pin(load, "execute"))

    take_b = keep(_at(ed.add_get_member_variable_node("ReloadTake"),
                      x0 + 2280, y0 + 420))
    kept, kept_n = _prop(ed, "Reserve", held, x0 + 2280, y0 + 300)
    keep(kept_n)
    fewer = keep(_at(_node(ed, FN_SUB_II), x0 + 2540, y0 + 300))
    _connect(kept, _pin(fewer, "A"))
    _connect(_pin(take_b, "ReloadTake", is_input=False), _pin(fewer, "B"))
    charge = keep(_at(ed.add_set_member_variable_node("Reserve", ITEM_CLASS_PATH),
                      x0 + 2800, y0))
    _connect(held, _pin(charge, "self"))
    _connect(_pin(fewer, "ReturnValue", is_input=False), _pin(charge, "Reserve"))
    _connect(BEL.find_then_pin(load), _pin(charge, "execute"))

    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 2800, y0 + 300))
    takes, takes_n = _prop(ed, "ReloadSeconds", held, x0 + 2800, y0 + 420)
    keep(takes_n)
    ready = keep(_at(_node(ed, FN_ADD_FF), x0 + 3060, y0 + 300))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(ready, "A"))
    _connect(takes, _pin(ready, "B"))
    pause = keep(_at(ed.add_set_member_variable_node("NextFireTime", ITEM_CLASS_PATH),
                     x0 + 3320, y0))
    _connect(held, _pin(pause, "self"))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(pause, "NextFireTime"))
    _connect(BEL.find_then_pin(charge), _pin(pause, "execute"))

    ed.add_comment_to_nodes(
        f"{RELOAD_KEY} reloads. ReloadTake is computed once and stored because "
        "the arithmetic behind it is pure: read it again after Loaded has gone "
        "up and the reserve is charged less than the magazine gained. The cost "
        "is the weapon's own ReloadSeconds pushed onto NextFireTime -- the same "
        "field the interval between shots uses, so there is only ever one rule "
        "saying when the weapon may fire. The clack plays on the True arm only, "
        "because a reload that moved nothing has nothing to announce.",
        made)
    return (BEL.find_then_pin(pause), BEL.find_else_pin(does))


def _author_dry_fire(ed, held, muzzle, has_ammo, cooled, tapped, exec_in, x0, y0):
    """The trigger was pulled on an empty chamber: click, and nothing else.

    Hangs off the False arm of the ready gate, which is the one place in the
    graph that knows the trigger was pulled and the shot did not happen. Three
    reasons now lead here and only one of them is worth a sound:

        no ammunition   the player has to *do* something (reload, or switch)
                        and nothing on screen says so -- the ammo readout is
                        four digits in the corner of a slot. This is the cue.
        still cooling   the weapon is working exactly as designed. Clicking
                        here would mean clicking on every frame a held trigger
                        outruns the interval, which on the SMG is most of them.
        held, not tapped  a semi-automatic with the button still down. Nothing
                        has gone wrong; the player has simply not let go.

    So the condition is "empty AND cooled AND tapped". The third term arrived
    with automatic fire and is not optional: the outer gate now opens on a HELD
    button, so without it, holding the mouse on an empty shotgun would click
    sixty times a second. Tapped also gives the automatics the right behaviour
    for free -- an empty SMG clicks once per pull rather than at its own fire
    rate, because it is out of ammunition, not out of cooldown.

    All three inputs are the same pure pins the ready gate itself used:
    re-reading them costs three re-evaluations of plain reads, and nothing has
    written to Held between the gate and here -- precisely because nothing
    fired.

    No cooldown is stamped, and with the tap requirement none is needed: one
    click of the mouse is one click of the hammer however long it is held.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    empty = keep(_at(_node(ed, FN_NOT), x0, y0 + 300))
    _connect(has_ammo, _pin(empty, "A"))
    settled = keep(_at(_node(ed, FN_AND), x0 + 260, y0 + 300))
    _connect(_pin(empty, "ReturnValue", is_input=False), _pin(settled, "A"))
    _connect(cooled, _pin(settled, "B"))
    worth = keep(_at(_node(ed, FN_AND), x0 + 260, y0 + 460))
    _connect(_pin(settled, "ReturnValue", is_input=False), _pin(worth, "A"))
    _connect(tapped, _pin(worth, "B"))

    click = keep(_at(ed.add_branch_node(), x0 + 520, y0))
    _connect(_pin(worth, "ReturnValue", is_input=False), _pin(click, "Condition"))
    _connect(exec_in, _pin(click, "execute"))

    dry_pin, dry_n = _prop(ed, "DryFireSound", held, x0 + 520, y0 + 180)
    keep(dry_n)
    play = keep(_at(_node(ed, FN_PLAY_SOUND), x0 + 780, y0))
    _connect(dry_pin, _pin(play, "Sound"))
    # At the muzzle, like the shot it is standing in for, so the click comes
    # from the same place in the mix as the bang the player expected.
    _connect(muzzle, _pin(play, "Location"))
    _connect(BEL.find_then_pin(click), _pin(play, "execute"))

    ed.add_comment_to_nodes(
        "Empty chamber: the click. Gated on \"out of ammunition\" AND \"off "
        "cooldown\" AND \"pressed this frame\", so the weapon clicks when the "
        "player needs to be told to reload, stays silent while it is merely "
        f"between shots (every {SMG_FIRE_INTERVAL:.2f}s on the SMG), and clicks "
        "once per pull rather than once per frame now that a HELD button opens "
        "the gate above.",
        made)
    return (BEL.find_then_pin(play), BEL.find_else_pin(click))


def _author_turn_view(ed, pc_out, pitch_delta, yaw_delta, exec_in, x0, y0):
    """Add a pitch and a yaw to the player's own control rotation.

    SetControlRotation, never AddPitchInput / AddControllerPitchInput. Those
    accumulate into RotationInput, which APlayerController then multiplies by
    its deprecated InputPitchScale -- and that is precisely the handle the
    mouse-sensitivity setting drives every frame (see _author_ads). Recoil fed
    through it would be a fifth of its size for a player on 0.2 and three times
    its size for a player on 3.0, which is a weapon whose kick depends on a
    menu slider.

    Nothing clamps the result here and nothing needs to: the controller's own
    UpdateRotation runs LimitViewPitch against ViewPitchMin/Max on the very
    next frame, so a kick taken while already looking near-vertical is pulled
    back under the limit rather than tipping the camera over the top.

    Roll is carried through from the rotation that was read rather than written
    as zero. Nothing rolls the view in this project today, and a literal 0 here
    would be this function deciding that for whatever does later.

    Returns (the exec pin to carry on from, the nodes it made).
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    now = keep(_at(_node(ed, FN_GET_CONTROL_ROT), x0, y0 + 240))
    _connect(pc_out, _pin(now, "self"))
    brk = keep(_at(_node(ed, FN_BREAK_ROT), x0 + 240, y0 + 240))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(brk, "InRot"))

    lifted = keep(_at(_node(ed, FN_ADD_FF), x0 + 500, y0 + 240))
    _connect(_pin(brk, "Pitch", is_input=False), _pin(lifted, "A"))
    _connect(pitch_delta, _pin(lifted, "B"))
    swung = keep(_at(_node(ed, FN_ADD_FF), x0 + 500, y0 + 400))
    _connect(_pin(brk, "Yaw", is_input=False), _pin(swung, "A"))
    _connect(yaw_delta, _pin(swung, "B"))

    aimed = keep(_at(_node(ed, FN_MAKE_ROT), x0 + 760, y0 + 240))
    _connect(_pin(brk, "Roll", is_input=False), _pin(aimed, "Roll"))
    _connect(_pin(lifted, "ReturnValue", is_input=False), _pin(aimed, "Pitch"))
    _connect(_pin(swung, "ReturnValue", is_input=False), _pin(aimed, "Yaw"))

    turn = keep(_at(_node(ed, FN_SET_CONTROL_ROT), x0 + 1020, y0))
    _connect(pc_out, _pin(turn, "self"))
    _connect(_pin(aimed, "ReturnValue", is_input=False), _pin(turn, "NewRotation"))
    _connect(exec_in, _pin(turn, "execute"))
    return BEL.find_then_pin(turn), made


def _author_recoil_kick(ed, held, pc_out, exec_in, x0, y0):
    """One shot's jolt: up by the weapon's own RecoilPitch, and a little sideways.

        kick     = Held.RecoilPitch * (Aiming ? recoil_ads_scale : 1)
        sideways = random in +/- kick * recoil_horizontal_ratio
        RecoilDebt    += kick
        RecoilYawDebt += sideways
        control rotation += (kick, sideways)

    Both halves are charged to the accumulators *and* applied to the view. The
    debts are what _author_recoil_recovery then pays back down; without them a
    kick would be permanent, and with them and no view write it would be
    invisible.

    RandomFloatInRange is a PURE node, so every pin that reads it draws its own
    number. The draw is therefore made once, into RecoilYawKick, and read from
    there twice -- inline it in both places and the view would swing one way
    while the accumulator was charged another, so the recovery would never
    cancel the kick it was paying for. That is the same "a pure node is pulled
    by whoever reads it" trap ReloadTake exists for.

    Reading RecoilPitch off Held is safe here and only here: this runs behind
    both fire gates, where Held has already been checked valid.

    Returns the exec pin to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    per_shot, per_shot_n = _prop(ed, "RecoilPitch", held, x0, y0 + 320)
    keep(per_shot_n)
    # Down the sights the weapon is shouldered and kicks less. SelectFloat and
    # not a Branch, the same shape _author_fire picks the cone width with, so
    # the aimed and unaimed cases are one expression that cannot drift.
    aiming = keep(_at(ed.add_get_member_variable_node("Aiming"), x0, y0 + 460))
    steadied = keep(_at(_node(ed, FN_SELECT_FF), x0 + 260, y0 + 460))
    _set(steadied, "A", COMBAT.recoil_ads_scale)
    _set(steadied, "B", 1.0)
    _connect(_pin(aiming, "Aiming", is_input=False), _pin(steadied, "bPickA"))
    up = keep(_at(_node(ed, FN_MUL_FF), x0 + 520, y0 + 320))
    _connect(per_shot, _pin(up, "A"))
    _connect(_pin(steadied, "ReturnValue", is_input=False), _pin(up, "B"))
    up_out = _pin(up, "ReturnValue", is_input=False)

    span = keep(_at(_node(ed, FN_MUL_FF), x0 + 780, y0 + 620))
    _connect(up_out, _pin(span, "A"))
    _set(span, "B", COMBAT.recoil_horizontal_ratio)
    span_out = _pin(span, "ReturnValue", is_input=False)
    mirrored = keep(_at(_node(ed, FN_MUL_FF), x0 + 1040, y0 + 760))
    _connect(span_out, _pin(mirrored, "A"))
    _set(mirrored, "B", -1.0)
    draw = keep(_at(_node(ed, FN_RANDOM_FLOAT), x0 + 1300, y0 + 620))
    _connect(_pin(mirrored, "ReturnValue", is_input=False), _pin(draw, "Min"))
    _connect(span_out, _pin(draw, "Max"))
    hold = keep(_at(ed.add_set_member_variable_node("RecoilYawKick"), x0 + 1560, y0))
    _connect(_pin(draw, "ReturnValue", is_input=False), _pin(hold, "RecoilYawKick"))
    _connect(exec_in, _pin(hold, "execute"))

    owed = keep(_at(ed.add_get_member_variable_node("RecoilDebt"), x0 + 1820, y0 + 320))
    charge = keep(_at(_node(ed, FN_ADD_FF), x0 + 2080, y0 + 320))
    _connect(_pin(owed, "RecoilDebt", is_input=False), _pin(charge, "A"))
    _connect(up_out, _pin(charge, "B"))
    bill = keep(_at(ed.add_set_member_variable_node("RecoilDebt"), x0 + 2340, y0))
    _connect(_pin(charge, "ReturnValue", is_input=False), _pin(bill, "RecoilDebt"))
    _connect(BEL.find_then_pin(hold), _pin(bill, "execute"))

    drawn = keep(_at(ed.add_get_member_variable_node("RecoilYawKick"),
                     x0 + 1820, y0 + 620))
    drawn_out = _pin(drawn, "RecoilYawKick", is_input=False)
    owed_yaw = keep(_at(ed.add_get_member_variable_node("RecoilYawDebt"),
                        x0 + 1820, y0 + 480))
    charge_yaw = keep(_at(_node(ed, FN_ADD_FF), x0 + 2080, y0 + 480))
    _connect(_pin(owed_yaw, "RecoilYawDebt", is_input=False), _pin(charge_yaw, "A"))
    _connect(drawn_out, _pin(charge_yaw, "B"))
    bill_yaw = keep(_at(ed.add_set_member_variable_node("RecoilYawDebt"),
                        x0 + 2600, y0))
    _connect(_pin(charge_yaw, "ReturnValue", is_input=False),
             _pin(bill_yaw, "RecoilYawDebt"))
    _connect(BEL.find_then_pin(bill), _pin(bill_yaw, "execute"))

    turned, turn_nodes = _author_turn_view(
        ed, pc_out, up_out, drawn_out, BEL.find_then_pin(bill_yaw),
        x0 + 2860, y0)
    made.extend(turn_nodes)

    ed.add_comment_to_nodes(
        f"Recoil, on the shot the gate just allowed: this weapon's own "
        f"RecoilPitch up ({COMBAT.recoil_ads_scale:g}x of it while aiming) and "
        f"a random +/-{COMBAT.recoil_horizontal_ratio:g} of that sideways, "
        f"charged to RecoilDebt and applied to the control rotation. The "
        f"pellets below fly down the AimPoint resolved at the top of this "
        f"frame, so a shot never bends itself -- it is the next one that pays.",
        made)
    return turned


def _author_recoil_recovery(ed, tick, pc_out, exec_in, x0, y0):
    """Give most of the kick back, every frame, until the debt is settled.

        RecoilDebt    -> FInterpTo(debt, 0, dt, recoil_recovery_speed)
        the view moves by (that step - the debt) * recoil_recovery_fraction

    Two things about that shape are the whole feel of it.

    The debt always reaches zero, so nothing accumulates across a magazine --
    but only recoil_recovery_fraction of each step is handed back to the view,
    so a fraction of every kick stays in the player's aim. A burst therefore
    walks up its target and has to be pulled back down by hand, which is what
    separates a gun from a screen shake.

    And the view is turned BEFORE the debts are written, not after. Every
    number here is pure and is pulled by whoever reads it, so a give-back
    computed from Get RecoilDebt after the Set would read the value it had just
    been reduced to and come out as zero -- the graph would look right and the
    view would never move.

    Skipped entirely while both debts are settled, so this does not write the
    player's control rotation sixty times a second to no effect.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    owed = keep(_at(ed.add_get_member_variable_node("RecoilDebt"), x0, y0 + 300))
    owed_out = _pin(owed, "RecoilDebt", is_input=False)
    owed_yaw = keep(_at(ed.add_get_member_variable_node("RecoilYawDebt"),
                        x0, y0 + 440))
    owed_yaw_out = _pin(owed_yaw, "RecoilYawDebt", is_input=False)

    size = keep(_at(_node(ed, FN_ABS), x0 + 260, y0 + 300))
    _connect(owed_out, _pin(size, "A"))
    size_yaw = keep(_at(_node(ed, FN_ABS), x0 + 260, y0 + 440))
    _connect(owed_yaw_out, _pin(size_yaw, "A"))
    total = keep(_at(_node(ed, FN_ADD_FF), x0 + 520, y0 + 360))
    _connect(_pin(size, "ReturnValue", is_input=False), _pin(total, "A"))
    _connect(_pin(size_yaw, "ReturnValue", is_input=False), _pin(total, "B"))
    # FInterpTo snaps to its target once the remaining distance is negligible,
    # so the debt reaches exactly zero and this gate really does close.
    owing = keep(_at(_node(ed, FN_GREATER_FF), x0 + 780, y0 + 360))
    _connect(_pin(total, "ReturnValue", is_input=False), _pin(owing, "A"))
    _set(owing, "B", 0.001)
    gate = keep(_at(ed.add_branch_node(), x0 + 1040, y0))
    _connect(_pin(owing, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    deltas = []
    for i, (var, current) in enumerate((("RecoilDebt", owed_out),
                                        ("RecoilYawDebt", owed_yaw_out))):
        step = keep(_at(_node(ed, FN_INTERP_FF), x0 + 1300, y0 + 300 + i * 300))
        _connect(current, _pin(step, "Current"))
        _set(step, "Target", 0.0)
        _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "DeltaTime"))
        _set(step, "InterpSpeed", COMBAT.recoil_recovery_speed)
        paid = keep(_at(_node(ed, FN_SUB_FF), x0 + 1560, y0 + 300 + i * 300))
        _connect(_pin(step, "ReturnValue", is_input=False), _pin(paid, "A"))
        _connect(current, _pin(paid, "B"))
        given = keep(_at(_node(ed, FN_MUL_FF), x0 + 1820, y0 + 300 + i * 300))
        _connect(_pin(paid, "ReturnValue", is_input=False), _pin(given, "A"))
        _set(given, "B", COMBAT.recoil_recovery_fraction)
        deltas.append((step, _pin(given, "ReturnValue", is_input=False)))

    turned, turn_nodes = _author_turn_view(
        ed, pc_out, deltas[0][1], deltas[1][1], BEL.find_then_pin(gate),
        x0 + 2080, y0)
    made.extend(turn_nodes)

    flow = turned
    for i, ((step, _delta), var) in enumerate(zip(deltas,
                                                  ("RecoilDebt", "RecoilYawDebt"))):
        settle = keep(_at(ed.add_set_member_variable_node(var),
                          x0 + 3400 + i * 260, y0))
        _connect(_pin(step, "ReturnValue", is_input=False), _pin(settle, var))
        _connect(flow, _pin(settle, "execute"))
        flow = BEL.find_then_pin(settle)

    ed.add_comment_to_nodes(
        f"Recoil recovery: both debts FInterpTo zero at "
        f"{COMBAT.recoil_recovery_speed:g}, and "
        f"{COMBAT.recoil_recovery_fraction * 100:.0f}% of each frame's step is "
        f"handed back to the view -- so the accumulator always settles but "
        f"{(1.0 - COMBAT.recoil_recovery_fraction) * 100:.0f}% of every kick "
        f"stays in the player's aim, which is what makes a burst climb. The "
        f"view is turned before the debts are written, because both give-backs "
        f"are pure and would read the already-reduced value otherwise.",
        made)
    return (flow, BEL.find_else_pin(gate))


def _author_ready_pose_keepalive(ed, held, exec_ins, x0, y0):
    """Put the ready pose back after a hit reaction has taken it away.

    THIS IS NOT BELT AND BRACES, it is the price of the second slot.
    UAnimInstance plays montages per GROUP, and every slot on a skeleton
    belongs to the default group unless the SKELETON maps it elsewhere --
    USkeleton::SetSlotGroupName, which UE 5.8 does not expose to Python at all
    (measured: `slot_group_names`, `slot_to_group_name_map` and
    `slot_anim_tracks` all fail as editor properties on a USkeleton, and the
    class has no slot or group methods). So starting the flinch in HitSlot
    stops the ready pose in DefaultSlot even though the two slots are different
    nodes in different blends.

    Measured before this existed, in a -game run: DefaultSlot sat at weight
    1.000 until the first punch landed, and read active=False, weight 0.000 for
    the rest of the session -- the player fought on with the gun in the
    locomotion pose. The flinch itself was fine; what it cost was the aim.

    Re-asserting it from Tick is the fix, and it is a better fix than never
    interrupting would have been: the arms ARE meant to be yanked off the
    sights for the length of the stagger, and this puts them back on the first
    frame after it, with the montage's own blend.

        Held is valid AND not sprinting
          AND DefaultSlot is quiet      (nothing is holding the pose)
          AND HitSlot is quiet          (we are not mid-flinch)
            -> play AimPose into DefaultSlot again

    The HitSlot term is the one that stops it oscillating: without it, the
    frame the flinch starts DefaultSlot goes quiet, this restarts the ready
    pose, and the restart stops the flinch -- in the same group, for the same
    reason -- and the reaction is a single frame of twitch.

    Nothing inside the condition reads a property off Held: only IsValid does,
    and the AimPose getter sits behind the gate on the play node's own pin, so
    a player with empty hands does not cost an Accessed None per frame.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    mesh = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0, y0 + 500))
    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 240, y0 + 500))
    _connect(_pin(mesh, "OwnerMesh", is_input=False), _pin(anim, "self"))
    anim_out = _pin(anim, "ReturnValue", is_input=False)

    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 160))
    _connect(held, _pin(armed, "Object"))
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"), x0, y0 + 280))
    still = keep(_at(_node(ed, FN_NOT), x0 + 240, y0 + 280))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))

    aiming = keep(_at(_node(ed, FN_IS_SLOT_ACTIVE), x0 + 480, y0 + 620))
    _connect(anim_out, _pin(aiming, "self"))
    _set(aiming, "SlotNodeName", AIM_SLOT)
    no_pose = keep(_at(_node(ed, FN_NOT), x0 + 720, y0 + 620))
    _connect(_pin(aiming, "ReturnValue", is_input=False), _pin(no_pose, "A"))

    flinching = keep(_at(_node(ed, FN_IS_SLOT_ACTIVE), x0 + 480, y0 + 760))
    _connect(anim_out, _pin(flinching, "self"))
    _set(flinching, "SlotNodeName", HIT_SLOT)
    settled = keep(_at(_node(ed, FN_NOT), x0 + 720, y0 + 760))
    _connect(_pin(flinching, "ReturnValue", is_input=False), _pin(settled, "A"))

    ready = keep(_at(_node(ed, FN_AND), x0 + 480, y0 + 220))
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(ready, "A"))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(ready, "B"))
    quiet = keep(_at(_node(ed, FN_AND), x0 + 960, y0 + 680))
    _connect(_pin(no_pose, "ReturnValue", is_input=False), _pin(quiet, "A"))
    _connect(_pin(settled, "ReturnValue", is_input=False), _pin(quiet, "B"))
    needed = keep(_at(_node(ed, FN_AND), x0 + 1200, y0 + 400))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(needed, "A"))
    _connect(_pin(quiet, "ReturnValue", is_input=False), _pin(needed, "B"))

    gate = keep(_at(ed.add_branch_node(), x0 + 1440, y0))
    _connect(_pin(needed, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    for tail in exec_ins:
        _connect(tail, _pin(gate, "execute"))

    pose_pin, pose_n = _prop(ed, "AimPose", held, x0 + 1440, y0 + 300)
    keep(pose_n)
    replay = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 1720, y0))
    _connect(anim_out, _pin(replay, "self"))
    _connect(pose_pin, _pin(replay, "Asset"))
    _set(replay, "SlotNodeName", AIM_SLOT)
    _set(replay, "BlendInTime", AIM_BLEND)
    _set(replay, "BlendOutTime", AIM_BLEND)
    _set(replay, "InPlayRate", 1.0)
    _set(replay, "LoopCount", AIM_LOOPS)
    _connect(BEL.find_then_pin(gate), _pin(replay, "execute"))

    after_replay = BEL.find_then_pin(replay)
    if HIT_REACT_PROBE:
        # Same temporary instrumentation as the reaction's own, and removed the
        # same way. Without it "the pose came back" is unobservable in a log:
        # the restart is silent and the only other evidence is a slot weight
        # sampled from outside, which cannot be caught in the 0.05 s gap
        # between two flinches when ten wanderers are hitting the player.
        say = keep(_at(_node(ed, FN_WARN), x0 + 1980, y0 + 300))
        _set(say, "InString", POSE_BACK_PROBE_PREFIX + "ready pose restarted")
        _connect(after_replay, _pin(say, "execute"))
        after_replay = BEL.find_then_pin(say)

    join = keep(_at(ed.add_branch_node(), x0 + 2240, y0))
    _set(join, "Condition", "true")
    _connect(after_replay, _pin(join, "execute"))
    _connect(BEL.find_else_pin(gate), _pin(join, "execute"))

    ed.add_comment_to_nodes(
        f"The ready pose puts itself back. A montage started in {HIT_SLOT} "
        f"stops the one in {AIM_SLOT}, because both slots are in the skeleton's "
        f"default montage GROUP and UE 5.8 gives Python no way to move one out "
        f"of it -- so the flinch costs the aim pose, and this is what buys it "
        f"back, on the first frame after the stagger has finished. The "
        f"{HIT_SLOT} term is what stops the two restarting each other forever.",
        made)
    return (BEL.find_then_pin(join),)


def _author_wc_tick(ed, tick):
    """Five polled keys and a refresh, chained so each block rejoins the next.

    There is no Sequence node here: an exec *input* accepts any number of links,
    so every block's exit and its guard branch's False pin both run into the
    next guard. That keeps the chain flat and means a block can be inserted or
    removed without re-fanning a Sequence's pins.

    Refresh runs last so a switch, drop or pick-up earlier in the same frame is
    already applied when it does.
    """
    pc = _at(_node(ed, FN_GET_PC), 240, 260)
    _set(pc, "PlayerIndex", 0)
    pc_out = _pin(pc, "ReturnValue", is_input=False)

    owner = _at(_node(ed, FN_GET_OWNER), 240, 400)
    owner_out = _pin(owner, "ReturnValue", is_input=False)

    held_get = _at(ed.add_get_member_variable_node("Held"), 240, 520)
    held = _pin(held_get, "Held", is_input=False)
    armed = _at(_node(ed, FN_IS_VALID), 480, 520)
    _connect(held, _pin(armed, "Object"))
    armed_out = _pin(armed, "ReturnValue", is_input=False)

    # One Get per bind, reused by every poll below -- an output pin takes any
    # number of links. The Key pins are DRIVEN rather than set to a literal,
    # which is the whole of rebinding: the HUD writes these variables each
    # frame from the player's save, and a literal cannot be written to.
    key_pins = {}
    for i, (name, _default) in enumerate(BIND_VARS):
        getter = _at(ed.add_get_member_variable_node(name), -40, 260 + i * 120)
        key_pins[name] = _pin(getter, name, is_input=False)

    def pressed(var, y):
        n = _at(_node(ed, FN_WAS_PRESSED), 480, y)
        _connect(pc_out, _pin(n, "self"))
        _connect(key_pins[var], _pin(n, "Key"))
        return _pin(n, "ReturnValue", is_input=False)

    def both(a, b, y):
        n = _at(_node(ed, FN_AND), 760, y)
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return _pin(n, "ReturnValue", is_input=False)

    # --- aim -----------------------------------------------------------------
    # First, and unconditionally: the reticle has to be right on the frames
    # where nothing is fired, which is nearly all of them. It also leaves
    # AimPoint and the muzzle position sitting there for the fire block to use.
    # --- recoil recovery -----------------------------------------------------
    # First of all, because it moves the view: the aim trace below has to be
    # taken after this frame's give-back rather than one frame behind it.
    recoil_exits = _author_recoil_recovery(ed, tick, pc_out,
                                           BEL.find_then_pin(tick), 1040, -3600)

    aim_exits, muzzle = _author_resolve_aim(ed, held, recoil_exits,
                                            1040, -2400)

    # --- sprint --------------------------------------------------------------
    # Before the trigger, because the trigger reads Sprinting: polled in the
    # other order, a shot would be allowed on the frame the sprint started.
    sprint_exits = _author_sprint(ed, tick, pc_out, owner_out,
                                  key_pins["KeySprint"], aim_exits,
                                  1040, -1400)

    # --- aim down the sights -------------------------------------------------
    # After the sprint block, which writes Sprinting, and before the trigger,
    # which the cone width now depends on: polled in any other order the zoom
    # and the spread would disagree by a frame.
    ads_exits = _author_ads(ed, tick, pc_out, owner_out, held, armed_out,
                            key_pins["KeyAim"], sprint_exits, 1040, -700)

    # --- the pose follows the sprint -----------------------------------------
    # Edge-triggered, not level-triggered, and that distinction is the whole
    # block. Re-equipping costs a detach, an attach and a montage restart; done
    # every frame the player holds Shift it would restart the run's ready pose
    # sixty times a second, which is a weapon that flickers. PoseSprinting is
    # what the pose currently reflects, Sprinting is what it should reflect,
    # and only the frames where those disagree do any work.
    now_sprint = _at(ed.add_get_member_variable_node("Sprinting"), 240, 1020)
    now_sprint_out = _pin(now_sprint, "Sprinting", is_input=False)
    posed = _at(ed.add_get_member_variable_node("PoseSprinting"), 240, 1140)
    changed = _at(_node(ed, FN_NEQ_BB), 520, 1060)
    _connect(now_sprint_out, _pin(changed, "A"))
    _connect(_pin(posed, "PoseSprinting", is_input=False), _pin(changed, "B"))
    pose_gate = _at(ed.add_branch_node(), 780, 940)
    _connect(_pin(changed, "ReturnValue", is_input=False), _pin(pose_gate, "Condition"))
    for exit_pin in ads_exits:
        _connect(exit_pin, _pin(pose_gate, "execute"))
    remember = _at(ed.add_set_member_variable_node("PoseSprinting"), 1040, 940)
    _connect(now_sprint_out, _pin(remember, "PoseSprinting"))
    _connect(BEL.find_then_pin(pose_gate), _pin(remember, "execute"))
    pose_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 1300, 940)
    _set(pose_dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(remember), _pin(pose_dirty, "execute"))
    pose_exits = (BEL.find_then_pin(pose_dirty), BEL.find_else_pin(pose_gate))

    # --- and the pose survives being shot ------------------------------------
    # After the sprint edge, because that block is what starts and stops the
    # pose deliberately, and this one only restores what something else took
    # away. See _author_ready_pose_keepalive: a hit reaction stops the ready
    # pose as a side effect of the montage group, and without this the player
    # fights the rest of the session with the gun in the locomotion pose.
    pose_exits = _author_ready_pose_keepalive(ed, held, pose_exits, 240, 1400)

    ed.add_comment_to_nodes(
        "Started or stopped sprinting this frame -- re-equip, which is what "
        "starts or stops the ready pose. Edge-triggered on PoseSprinting: the "
        "level-triggered version restarts the montage every frame Shift is "
        "held, and the weapon strobes.",
        [now_sprint, posed, changed, pose_gate, remember, pose_dirty])

    # --- fire ----------------------------------------------------------------
    # Three conditions, and "not sprinting" is the new one: the weapon is being
    # used to run with, not to aim with. Note this AND is safe to fold together
    # -- every input is a plain bool read, with no chain behind it that could be
    # pulled by the half that should not have run (unlike the NPC melee gate).
    #
    # The trigger is polled BOTH ways, and the two are OR'd here rather than
    # chosen between. Which one a given weapon honours is settled further in,
    # behind this gate, because the answer is a property of Held -- and this
    # condition is evaluated on every frame, including the frames where nothing
    # is equipped. Reading Automatic here would be an Accessed None per frame
    # for as long as the player's hands are empty.
    #
    # So the outer gate asks the question that is answerable without a weapon:
    # is the player touching the trigger at all? A tap is also a hold on the
    # frame it happens, so the OR is not strictly necessary for the automatics
    # -- it is there so that a semi-automatic still opens the gate on the tap
    # frame even if IsInputKeyDown were ever to disagree, and so that the two
    # reads that actually decide are the same two pins the weapon is asked
    # about below.
    steady = _at(_node(ed, FN_NOT), 760, 760)
    _connect(_pin(_at(ed.add_get_member_variable_node("Sprinting"), 480, 760),
                  "Sprinting", is_input=False), _pin(steady, "A"))

    tap = pressed("KeyFire", 600)
    holding = _at(_node(ed, FN_IS_KEY_DOWN), 480, 860)
    _connect(pc_out, _pin(holding, "self"))
    _connect(key_pins["KeyFire"], _pin(holding, "Key"))
    holding_out = _pin(holding, "ReturnValue", is_input=False)
    touching = _at(_node(ed, FN_OR), 760, 580)
    _connect(tap, _pin(touching, "A"))
    _connect(holding_out, _pin(touching, "B"))

    fire_gate = _at(ed.add_branch_node(), 1040, 0)
    _connect(both(both(_pin(touching, "ReturnValue", is_input=False),
                       armed_out, 640),
                  _pin(steady, "ReturnValue", is_input=False), 700),
             _pin(fire_gate, "Condition"))
    for exit_pin in pose_exits:
        _connect(exit_pin, _pin(fire_gate, "execute"))

    # Ammunition and the cooldown are a SECOND branch inside the first, not two
    # more terms folded into its condition, and that nesting is the whole
    # reason this reads the way it does. Both tests have to read properties off
    # Held, and the condition of the outer gate is pulled on every frame --
    # including the frames where nothing is equipped at all. A pure Get with a
    # null self is an "Accessed None" per frame forever. Behind the gate, Held
    # has already been checked valid.
    loaded, loaded_n = _prop(ed, "Loaded", held, 1240, 300)
    rounds = _at(_node(ed, FN_GREATER_II), 1480, 300)
    _connect(loaded, _pin(rounds, "A"))
    _set(rounds, "B", 0)
    limited, limited_n = _prop(ed, "UsesAmmo", held, 1240, 420)
    unlimited = _at(_node(ed, FN_NOT), 1480, 420)
    _connect(limited, _pin(unlimited, "A"))
    # OR, so the pistol never consults a magazine it does not have.
    has_ammo = _at(_node(ed, FN_OR), 1720, 360)
    _connect(_pin(unlimited, "ReturnValue", is_input=False), _pin(has_ammo, "A"))
    _connect(_pin(rounds, "ReturnValue", is_input=False), _pin(has_ammo, "B"))

    when, when_n = _prop(ed, "NextFireTime", held, 1240, 560)
    right_now = _at(_node(ed, FN_TIME_SECONDS), 1240, 680)
    cooled = _at(_node(ed, FN_GE_FF), 1480, 560)
    _connect(_pin(right_now, "ReturnValue", is_input=False), _pin(cooled, "A"))
    _connect(when, _pin(cooled, "B"))

    # Held trigger, or tapped trigger? Now that Held is known valid, the
    # weapon can be asked. An automatic accepts either; everything else
    # accepts only the tap, which is what makes one click one shot on the
    # shotgun even though the button is still down on the following frame.
    auto_pin, auto_n = _prop(ed, "Automatic", held, 1240, 820)
    spraying = _at(_node(ed, FN_AND), 1480, 820)
    _connect(holding_out, _pin(spraying, "A"))
    _connect(auto_pin, _pin(spraying, "B"))
    trigger = _at(_node(ed, FN_OR), 1720, 760)
    _connect(tap, _pin(trigger, "A"))
    _connect(_pin(spraying, "ReturnValue", is_input=False), _pin(trigger, "B"))
    trigger_out = _pin(trigger, "ReturnValue", is_input=False)

    ready = _at(_node(ed, FN_AND), 1960, 420)
    _connect(_pin(has_ammo, "ReturnValue", is_input=False), _pin(ready, "A"))
    _connect(_pin(cooled, "ReturnValue", is_input=False), _pin(ready, "B"))
    allowed = _at(_node(ed, FN_AND), 1960, 600)
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(allowed, "A"))
    _connect(trigger_out, _pin(allowed, "B"))
    ready_gate = _at(ed.add_branch_node(), 2200, 0)
    _connect(_pin(allowed, "ReturnValue", is_input=False),
             _pin(ready_gate, "Condition"))
    _connect(BEL.find_then_pin(fire_gate), _pin(ready_gate, "execute"))

    ed.add_comment_to_nodes(
        "The trigger is being touched, the weapon is out and the player is not "
        "sprinting -- now, can it actually fire? A weapon with no ammunition "
        "rule passes on the first half; every weapon waits out its own "
        "FireInterval on the second; and an automatic is the only kind that "
        "counts a held button as a pull. Nested inside the first gate rather "
        "than folded into it, because every one of these reads a property off "
        "Held.",
        [loaded_n, rounds, limited_n, unlimited, has_ammo, when_n, right_now,
         cooled, auto_n, spraying, trigger, ready, allowed, ready_gate])

    # The kick lands before the round is spent, which costs nothing and reads
    # in the right order. It cannot bend the shot that caused it: the pellets
    # fly down the AimPoint resolved at the top of this frame.
    kicked = _author_recoil_kick(ed, held, pc_out,
                                 BEL.find_then_pin(ready_gate), 6800, -1400)
    after_fire = _author_fire(ed, held, muzzle, kicked, 2700, 0)

    # --- the click, when the gate said no ------------------------------------
    dry_exits = _author_dry_fire(
        ed, held, muzzle,
        _pin(has_ammo, "ReturnValue", is_input=False),
        _pin(cooled, "ReturnValue", is_input=False), tap,
        BEL.find_else_pin(ready_gate), 2200, 1100)

    # --- reload --------------------------------------------------------------
    # Shares its key with the death menu's "try again", and that is safe rather
    # than lucky: Event Tick does not run while the game is paused, so this
    # graph is not listening on any frame the menu is on screen. (The HUD's
    # DrawHUD is; it is renderer-driven, which is why the menu can poll a key at
    # all.)
    reload_gate = _at(ed.add_branch_node(), 1040, 7200)
    _connect(both(pressed("KeyReload", 7360), armed_out, 7300),
             _pin(reload_gate, "Condition"))
    for exit_pin in (after_fire, BEL.find_else_pin(fire_gate)) + dry_exits:
        _connect(exit_pin, _pin(reload_gate, "execute"))
    reload_exits = _author_reload(ed, held, BEL.find_then_pin(reload_gate),
                                  1400, 7200)

    # --- switch --------------------------------------------------------------
    switch_gate = _at(ed.add_branch_node(), 1040, 1400)
    inv = _at(ed.add_get_member_variable_node("Inventory"), 240, 1560)
    count = _at(_node(ed, FN_ARR_LEN), 480, 1560)
    _connect(_pin(inv, "Inventory", is_input=False), _pin(count, "TargetArray"))
    count_out = _pin(count, "ReturnValue", is_input=False)
    any_held = _at(_node(ed, FN_LESS_II), 760, 1680)
    _set(any_held, "A", 0)
    _connect(count_out, _pin(any_held, "B"))
    _connect(both(pressed("KeySwitch", 1560), _pin(any_held, "ReturnValue", is_input=False),
                  1620), _pin(switch_gate, "Condition"))
    for exit_pin in reload_exits + (BEL.find_else_pin(reload_gate),):
        _connect(exit_pin, _pin(switch_gate, "execute"))

    idx = _at(ed.add_get_member_variable_node("EquippedIndex"), 1300, 1600)
    step = _at(_node(ed, FN_ADD_II), 1540, 1600)
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(step, "A"))
    _set(step, "B", 1)
    wrap = _at(_node(ed, FN_MOD_II), 1780, 1600)
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(wrap, "A"))
    _connect(count_out, _pin(wrap, "B"))
    to = _at(ed.add_set_member_variable_node("EquippedIndex"), 2020, 1400)
    _connect(_pin(wrap, "ReturnValue", is_input=False), _pin(to, "EquippedIndex"))
    _connect(BEL.find_then_pin(switch_gate), _pin(to, "execute"))
    switch_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 2280, 1400)
    _set(switch_dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(to), _pin(switch_dirty, "execute"))

    ed.add_comment_to_nodes(
        f"{SWITCH_KEY} cycles: (index + 1) mod count, so it wraps and works for "
        "any number of carried weapons. 1/2/3 and M would have been the obvious "
        "keys but they already belong to the graphics menu.",
        [inv, count, any_held, idx, step, wrap, to, switch_dirty, switch_gate])

    # --- drop ----------------------------------------------------------------
    drop_gate = _at(ed.add_branch_node(), 1040, 2200)
    _connect(both(pressed("KeyDrop", 2360), armed_out, 2300), _pin(drop_gate, "Condition"))
    _connect(BEL.find_then_pin(switch_dirty), _pin(drop_gate, "execute"))
    _connect(BEL.find_else_pin(switch_gate), _pin(drop_gate, "execute"))
    after_drop = _author_drop(ed, held, owner_out, BEL.find_then_pin(drop_gate),
                              1400, 2200)
    drop_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4700, 2200)
    _set(drop_dirty, "NeedsRefresh", "true")
    _connect(after_drop, _pin(drop_dirty, "execute"))

    # --- pick up -------------------------------------------------------------
    pick_gate = _at(ed.add_branch_node(), 1040, 3400)
    _connect(pressed("KeyPickup", 3560), _pin(pick_gate, "Condition"))
    _connect(BEL.find_then_pin(drop_dirty), _pin(pick_gate, "execute"))
    _connect(BEL.find_else_pin(drop_gate), _pin(pick_gate, "execute"))
    after_pick = _author_pickup(ed, owner_out, BEL.find_then_pin(pick_gate),
                                1400, 3400)
    pick_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4900, 3400)
    _set(pick_dirty, "NeedsRefresh", "true")
    _connect(after_pick, _pin(pick_dirty, "execute"))

    # --- refresh -------------------------------------------------------------
    dirty_get = _at(ed.add_get_member_variable_node("NeedsRefresh"), 1040, 4760)
    refresh_gate = _at(ed.add_branch_node(), 1300, 4600)
    _connect(_pin(dirty_get, "NeedsRefresh", is_input=False),
             _pin(refresh_gate, "Condition"))
    _connect(BEL.find_then_pin(pick_dirty), _pin(refresh_gate, "execute"))
    _connect(BEL.find_else_pin(pick_gate), _pin(refresh_gate, "execute"))
    settle = _at(ed.add_set_member_variable_node("NeedsRefresh"), 1560, 4600)
    _set(settle, "NeedsRefresh", "false")
    _connect(BEL.find_then_pin(refresh_gate), _pin(settle, "execute"))
    _author_equip(ed, BEL.find_then_pin(settle), 1900, 4600)


def build_weapon_component(item_bp, shotgun_bp, pistol_bp, blood_bp, rebuild=True):
    # Cast nodes only appear in the palette for classes that are already loaded,
    # and this graph casts to all three. Without these loads
    # create_node_from_name returns None and the failure reads as a typo in the
    # node name rather than as a missing asset.
    for path in (CHARACTER_BP_PATH, ITEM_BP_PATH, HEALTH_BP_PATH):
        if not _assets().load_asset(path):
            raise RuntimeError(f"could not load {path} for its cast node")

    bp = _create_blueprint(WEAPON_COMP_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    item_class = BEL.generated_class(item_bp)
    _declare(ed, "Inventory",
             BEL.get_array_type(BEL.get_object_reference_type(item_class)))
    _declare(ed, "Held", BEL.get_object_reference_type(item_class))
    _declare(ed, "EquippedIndex", BEL.get_basic_type_by_name("int"))
    _declare(ed, "NeedsRefresh", BEL.get_basic_type_by_name("bool"))
    _declare(ed, "OwnerMesh", BEL.get_object_reference_type(
        unreal.SkeletalMeshComponent.static_class()))
    # Where this frame's shot lands, and whether there is anything to draw a
    # reticle on. The HUD reads all three; nothing else writes them.
    _declare(ed, "AimPoint", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "AimValid", BEL.get_basic_type_by_name("bool"))
    _declare(ed, "AimBlocked", BEL.get_basic_type_by_name("bool"))
    # Sprint. The HUD reads Stamina/MaxStamina for the bar under the player's
    # HP bar; BaseSpeed is cached off the character at BeginPlay, never a
    # literal. Sprinting is what the fire gate refuses on.
    for name in ("Stamina", "MaxStamina", "BaseSpeed"):
        _declare(ed, name, _float_type())
    _declare(ed, "Sprinting", BEL.get_basic_type_by_name("bool"))
    # Aiming down the sights. BaseFOV is cached off the camera at BeginPlay for
    # the same reason BaseSpeed is cached off the movement component; CurrentFOV
    # is stored because FInterpTo's input is its own previous output, and
    # TargetFOV because the two arms of the zoom branch must write one value
    # that one interpolation then reads.
    for name in ("BaseFOV", "CurrentFOV", "TargetFOV"):
        _declare(ed, name, _float_type())
    _declare(ed, "Aiming", BEL.get_basic_type_by_name("bool"))
    # The seven polled keys, as variables rather than as pin literals. Nothing
    # in this component loads them: the HUD pushes the player's binds in every
    # DrawHUD frame (see build_graphics_menu._author_push_settings), which is
    # what keeps the component free of any cast to the HUD and of any knowledge
    # that a save file exists. The CDO defaults below are therefore also the
    # standalone fallback -- a weapon component on an actor with no HUD in front
    # of it still plays with the keys this file documents.
    for name, _default in BIND_VARS:
        _declare(ed, name, _struct_type(unreal.Key.static_struct()))
    # Mouse sensitivity, and the two controller scales it multiplies. Both
    # bases are cached off the PlayerController at BeginPlay -- BasePitchScale
    # especially, because the engine ships it negative and a literal would
    # invert the look. See the ADS block for what the zoom does to them.
    for name in ("MouseSensitivity", "BaseYawScale", "BasePitchScale"):
        _declare(ed, name, _float_type())
    # What the ready pose currently reflects, as opposed to what it should.
    # The pair is what makes the sprint pose edge-triggered; see _author_wc_tick.
    _declare(ed, "PoseSprinting", BEL.get_basic_type_by_name("bool"))
    # Recoil. RecoilDebt/RecoilYawDebt are what has been kicked and not yet
    # given back, recovered toward zero every frame; RecoilYawKick holds the
    # one draw of the sideways component for the frame it is fired on, because
    # RandomFloatInRange is pure and a second read would be a second number.
    for name in ("RecoilDebt", "RecoilYawDebt", "RecoilYawKick"):
        _declare(ed, name, _float_type())
    # How many rounds this reload moves, computed once and read back three
    # times. See _author_reload for why it cannot just be recomputed.
    _declare(ed, "ReloadTake", BEL.get_basic_type_by_name("int"))
    # The GameMode's DebugMode, cached at the moment of firing so the pellet
    # loop can branch on a plain bool instead of casting eight times.
    _declare(ed, DEBUG_MODE_VAR, BEL.get_basic_type_by_name("bool"))
    _declare(ed, HIT_BONE_VAR, BEL.get_basic_type_by_name("name"))
    # Typed as "class of BP_WeaponItem", not "class of Actor": SpawnActor's
    # return pin takes its type from its Class pin, and an Actor-typed return
    # cannot be added to an array of BP_WeaponItem.
    for name in ("ShotgunClass", "PistolClass", "ItemClass"):
        _declare(ed, name, BEL.get_class_reference_type(item_class))
    _declare(ed, "BloodClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))

    _author_wc_begin_play(ed, begin)
    _author_wc_tick(ed, tick)

    _post_physics_tick(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponComponent failed to compile")
    _apply_defaults(bp, {
        "EquippedIndex": 0,
        "NeedsRefresh": True,
        "Stamina": COMBAT.max_stamina,
        "MaxStamina": COMBAT.max_stamina,
        # Overwritten on the first frame of BeginPlay; this is only what the
        # bar would divide by if that somehow never ran.
        "BaseSpeed": 500.0,
        "Sprinting": False,
        # 1.0 is "exactly what the controller already does", because the two
        # base scales this multiplies are the controller's own. A player who
        # never opens the settings screen therefore gets the stock feel.
        "MouseSensitivity": COMBAT.mouse_sensitivity_default,
        **{name: _key(k) for name, k in BIND_VARS},
        # Both overwritten on the first frame of BeginPlay. Seeded with the
        # engine's own defaults, signs included, so that a BeginPlay that
        # somehow never ran leaves the look working rather than dead.
        "BaseYawScale": 2.5,
        "BasePitchScale": -2.5,
        # Matches Sprinting, so the first frame sees no edge and does not
        # re-equip for nothing.
        "PoseSprinting": False,
        "ReloadTake": 0,
        "RecoilDebt": 0.0,
        "RecoilYawDebt": 0.0,
        "RecoilYawKick": 0.0,
        DEBUG_MODE_VAR: False,
        "ShotgunClass": BEL.generated_class(shotgun_bp),
        "PistolClass": BEL.generated_class(pistol_bp),
        "ItemClass": item_class,
        "BloodClass": BEL.generated_class(blood_bp),
    })
    _log(f"built {WEAPON_COMP_BP_PATH}")
    return bp


# ─── Installing on the characters ────────────────────────────────────────────

OLD_SHOTGUN_PARTS = {"Shotgun", "Receiver", "Barrel", "MagTube", "Pump", "Stock",
                     "Grip", "TriggerGuard", "ShotgunComponent"}
OLD_SHOTGUN_BP = "/Game/Weapons/BP_ShotgunComponent"


def _uninstall_old_shotgun(bp):
    """Strip what build_shotgun_and_health.py welded onto the character.

    The old design hung the weapon's seven primitives off the character's mesh
    directly. Those have to go, or the player carries a second shotgun that no
    longer responds to anything.
    """
    present = {var for _h, var in _handles(bp)} & OLD_SHOTGUN_PARTS
    if present:
        _drop_components(bp, present)
        _log(f"removed the old welded shotgun: {sorted(present)}")


def make_shootable(bp):
    """Let a Visibility trace hit this character's capsule.

    This is the bug that made the NPC unkillable. UE's stock `Pawn` profile sets
    Visibility to **Ignore** (and `CharacterMesh` does too), while the pellets
    trace on TraceTypeQuery1, which *is* Visibility -- so every shot passed
    straight through the NPC and no hit was ever registered. Nothing logs this:
    the trace simply reports no hit, exactly as it would for a genuine miss.

    The capsule alone is made to block, not the skeletal mesh: the capsule is
    guaranteed present and correctly sized, whereas hitting the mesh depends on
    the physics asset's shapes being well fitted. Capsule-only hit detection is
    coarse but predictable.

    Setting a single channel response switches the profile off its preset and
    onto "Custom", which is expected.
    """
    capsule = _find_handle(bp, "CapsuleComponent")
    if not capsule:
        _log(f"note: {bp.get_name()} has no CapsuleComponent — not made shootable")
        return
    obj = _component_object(capsule)
    obj.set_collision_response_to_channel(
        unreal.CollisionChannel.ECC_VISIBILITY, unreal.CollisionResponseType.ECR_BLOCK)
    got = obj.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)
    if got != unreal.CollisionResponseType.ECR_BLOCK:
        raise RuntimeError(
            f"{bp.get_name()}'s capsule still ignores Visibility ({got}) — "
            "shots would pass through it")
    _log(f"{bp.get_name()}: capsule now blocks Visibility (shootable)")


def hit_zones(mesh_asset):
    """(head, limbs, body): the physics-asset bodies of a mesh, by zone.

    Only bones with a body can ever come back from a trace, so the tables list
    exactly those. The physics asset's SkeletalBodySetups are protected from
    Python, but every body is one end of a constraint, and the constraints are
    readable. The zone test walks the real skeleton (BoneIsChildOf on a
    transient component), so a renamed or re-parented bone moves with it rather
    than falling out of a hand-written list.
    """
    pa = mesh_asset.get_editor_property("physics_asset")
    if not pa:
        raise RuntimeError(f"{mesh_asset.get_name()} has no physics asset — "
                           "there are no bodies for a hit to land on")
    bodies = set()
    for constraint in pa.get_constraints(False):
        ends = unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names(constraint)
        bodies.update(str(n) for n in ends if isinstance(n, unreal.Name))
    bodies.discard("None")

    probe = unreal.SkeletalMeshComponent()
    probe.set_skeletal_mesh_asset(mesh_asset)

    def under(bone, roots):
        return any(bone == root or probe.bone_is_child_of(bone, root) for root in roots)

    # FName comparison is case-insensitive, so "head" already finds "Head";
    # the pairs that actually differ are the limbs.
    lower = {b.lower(): b for b in bodies}

    def resolve(candidates, role):
        for c in candidates:
            if c.lower() in lower:
                return lower[c.lower()]
        raise RuntimeError(
            f"{pa.get_name()} has no body for {role} (tried {list(candidates)}) "
            "— that zone could never be hit. Add this rig's bone name to "
            "HEAD_CANDIDATES / LIMB_CANDIDATES.")

    head_roots = (resolve(HEAD_CANDIDATES, "the head"),)
    limb_roots = tuple(resolve(c, f"limb {i + 1}")
                       for i, c in enumerate(LIMB_CANDIDATES))
    head = sorted(b for b in bodies if under(b, head_roots))
    limbs = sorted(b for b in bodies if under(b, limb_roots))
    return head, limbs, sorted(bodies - set(head) - set(limbs))


def install_hit_zones(bp, health_handle):
    """Write this character's own hit-box tables onto its HealthComponent.

    Per character, on the component template -- the same place DespawnOnDeath
    goes -- because the tables describe *this* skeleton; a character with a
    different rig gets different bones with no change to the graph.
    """
    mesh = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            mesh = obj
            break
    if mesh is None:
        raise RuntimeError(f"{bp.get_name()} has no SkeletalMeshComponent to zone")
    # K2_LineTraceComponent walks the mesh's physics bodies, and a mesh with
    # collision off never creates them: every hit would be a body hit and
    # nothing would say so.
    if mesh.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION:
        raise RuntimeError(f"{bp.get_name()}'s mesh has no collision — "
                           "it has no physics bodies to tell head from leg")
    head, limbs, body = hit_zones(mesh.get_editor_property("skeletal_mesh_asset"))
    comp = _component_object(health_handle)
    comp.set_editor_property(HEAD_BONES_VAR, [unreal.Name(b) for b in head])
    comp.set_editor_property(LIMB_BONES_VAR, [unreal.Name(b) for b in limbs])
    got = ([str(b) for b in comp.get_editor_property(HEAD_BONES_VAR)],
           [str(b) for b in comp.get_editor_property(LIMB_BONES_VAR)])
    if got != (head, limbs):
        raise RuntimeError(f"{bp.get_name()}'s hit-box tables did not stick: {got}")
    _log(f"{bp.get_name()}: hit boxes — head {head} x{COMBAT.head_multiplier}, "
         f"limbs {len(limbs)} bodies x{COMBAT.limb_multiplier}, body {body} x1.0")


def hit_reactions(mesh_asset):
    """The six flinches on THIS mesh's own skeleton, in HIT_REACTION_CLIPS order.

    An AnimSequence belongs to exactly one skeleton, so there is no shared
    default that could be right for the adventurer, the zombie and the wendigo
    at once -- which is why this is resolved per character at build time,
    exactly as the hit-zone tables are.

    Where they live is derived from the mesh's own name (SKM_Zombie01 ->
    Anims/Zombie01/A_Zombie01_*), the layout build_retarget.py writes and
    npc_placement._creature reads. A mannequin-skinned checkout, which has no
    /Game/Sourced at all, falls back to Epic's originals -- they are on
    SK_Mannequin, so the skeleton test below passes for exactly the bodies they
    can drive and fails for the rest.

    ALL SIX OR NONE. The directional pick indexes this array by position, so a
    partial set is not a smaller set, it is the wrong clip for three of the four
    directions -- and unlike a missing asset, that failure is silent. Every
    candidate's skeleton is checked for the same reason: a clip on the wrong
    skeleton does not error, it simply never plays.
    """
    skeleton = mesh_asset.get_editor_property("skeleton") if mesh_asset else None
    if not skeleton:
        return []
    name = mesh_asset.get_name()
    family = name[4:] if name.startswith("SKM_") else name
    eas = _assets()
    for folder, prefix in ((f"{HIT_ANIM_ROOT}/{family}", f"A_{family}_"),
                           (HIT_ANIM_FALLBACK_DIR, "")):
        found = []
        for clip in HIT_REACTION_CLIPS:
            path = f"{folder}/{prefix}{clip}"
            asset = eas.load_asset(path) if eas.does_asset_exist(path) else None
            if (isinstance(asset, unreal.AnimSequence)
                    and asset.get_editor_property("skeleton") == skeleton):
                found.append(asset)
        if len(found) == len(HIT_REACTION_CLIPS):
            return found
    return []


def install_hit_reactions(bp, health_handle):
    """Write this character's own six reaction clips onto its HealthComponent.

    Per character and on the component template, for the reason
    install_hit_zones is: the clips describe *this* skeleton.

    Empty is a legal, logged outcome rather than an error. On a from-nothing
    build this runs before build_retarget.py has ever produced a creature's
    clips -- the weapons builder runs twice, see the build-order note in the
    player's-body section of CLAUDE.md -- and the graph guards an empty array:
    the character simply does not flinch, which is what it did before.
    """
    mesh = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            mesh = obj
            break
    if mesh is None:
        raise RuntimeError(f"{bp.get_name()} has no SkeletalMeshComponent")
    clips = hit_reactions(mesh.get_editor_property("skeletal_mesh_asset"))
    comp = _component_object(health_handle)
    comp.set_editor_property(HIT_REACTIONS_VAR, clips)
    got = [a.get_name() for a in comp.get_editor_property(HIT_REACTIONS_VAR)]
    if got != [a.get_name() for a in clips]:
        raise RuntimeError(f"{bp.get_name()}'s hit reactions did not stick: {got}")
    if clips:
        _log(f"{bp.get_name()}: {len(clips)} hit reactions into {HIT_SLOT} "
             f"({got[0]} ... {got[-1]})")
    else:
        _log(f"note: {bp.get_name()} has no hit reactions on its skeleton -- it "
             f"will not flinch. Run Scripts/asset_pipeline/build_retarget.py, "
             f"then this builder again.")
    return clips


def face_the_camera(bp):
    """Turn the body with the camera instead of with the movement input.

    This is what aims the gun, and it is the standard arrangement for a
    third-person shooter: the character always faces where the camera looks and
    strafes around that, so the ready pose -- and therefore the barrel -- stays
    lined up with the crosshair no matter which way the player is running.

    The template ships the opposite (`orient_rotation_to_movement`), which turns
    the whole body to face the movement input. With a weapon in hand that means
    running left points the gun left while the crosshair stays dead ahead.

    The honest cost: the legs still play the *unarmed* forward gait, because a
    strafe set needs blend spaces and those cannot be authored from Python, so
    sideways movement reads as running forward while sliding. That is the same
    limitation the ready pose already documents, not a new one.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    cdo.set_editor_property("use_controller_rotation_yaw", True)
    movement = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.CharacterMovementComponent):
            movement = obj
            break
    if movement is None:
        raise RuntimeError(f"{bp.get_name()} has no CharacterMovementComponent")
    movement.set_editor_property("orient_rotation_to_movement", False)
    if movement.get_editor_property("orient_rotation_to_movement"):
        raise RuntimeError("the character still turns to face its movement — "
                           "the body would fight the camera for where to aim")
    _log("player: body follows the camera's yaw (gun stays on the crosshair)")


def aim_camera(bp):
    """Move the camera boom over the player's right shoulder.

    Belongs with the weapons rather than with the level or the HUD: it exists
    because there is now a reticle in the middle of the screen, and a centred
    boom points that reticle straight at the player's own back.
    """
    arm = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SpringArmComponent):
            arm = obj
            break
    if arm is None:
        _log(f"note: {bp.get_name()} has no SpringArmComponent — camera left alone")
        return
    arm.set_editor_property("target_arm_length", CAMERA_ARM)
    arm.set_editor_property("socket_offset", unreal.Vector(*CAMERA_SHOULDER))
    got = arm.get_editor_property("socket_offset")
    if abs(got.y - CAMERA_SHOULDER[1]) > 1e-3:
        raise RuntimeError(f"the camera boom kept its old offset ({got})")
    _log(f"camera: boom {CAMERA_ARM:.0f} cm, over the shoulder by "
         f"{CAMERA_SHOULDER[1]:.0f} cm right / {CAMERA_SHOULDER[2]:.0f} cm up")


def wear_skin(skin=None):
    """Put the player in a body, and run that body's animation.

    Separate from install_on_character, and called before it, because the
    weapon specs are built in between: _grip_rotation() samples the ready pose
    through whatever mesh the player is wearing at the time, so a skin applied
    afterwards would leave five weapons oriented for the previous rig.

    Idempotent, and quiet when there is nothing to do -- the template already
    ships wearing SKM_Quinn_Simple, so a checkout without the asset pipeline
    passes through here writing the values that are already there.
    """
    skin = skin or player_skin()
    eas = _assets()
    bp = eas.load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    mesh_asset = eas.load_asset(skin.mesh)
    if not mesh_asset:
        raise RuntimeError(f"{skin.mesh} is missing — the player would have no body")
    # An anim BP is bound to one skeleton, so a mismatch here is not a cosmetic
    # error: the component silently falls back to the reference pose and the
    # player slides around the map in a T-pose with nothing in the log.
    anim_class = unreal.load_class(None, f"{skin.anim_bp}.{skin.anim_bp.rsplit('/', 1)[1]}_C")
    if not anim_class:
        raise RuntimeError(f"{skin.anim_bp} has no generated class — it did not compile")

    comp = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            comp = obj
            break
    if comp is None:
        raise RuntimeError(f"{CHARACTER_BP_PATH} has no SkeletalMeshComponent")

    comp.set_editor_property("skeletal_mesh_asset", mesh_asset)
    comp.set_editor_property("anim_class", anim_class)
    comp.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, skin.mesh_z))
    comp.set_editor_property("relative_rotation", _rot(yaw=skin.mesh_yaw))
    got = comp.get_editor_property("skeletal_mesh_asset")
    if got != mesh_asset or comp.get_editor_property("anim_class") != anim_class:
        raise RuntimeError(f"the skin did not stick: mesh={got}, "
                           f"anim={comp.get_editor_property('anim_class')}")
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile after the skin")
    eas.save_loaded_asset(bp)
    _log(f"player: wearing {mesh_asset.get_name()} animated by "
         f"{anim_class.get_name()}, weapon on {skin.grip}")
    return skin


def install_on_character(health_bp, weapon_bp, footstep_bp):
    eas = _assets()
    bp = eas.load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    _uninstall_old_shotgun(bp)
    _drop_components(bp, {"HealthComponent", "WeaponComponent", "FootstepComponent"})
    handles = {}
    for name, source in (("HealthComponent", health_bp),
                         ("WeaponComponent", weapon_bp),
                         ("FootstepComponent", footstep_bp)):
        handles[name] = _add_component(bp, _root_handle(bp),
                                       BEL.generated_class(source), name)
    # Symmetry, and forward planning: the player carries health too, so anything
    # that shoots back later needs to be able to hit them -- and hit them in
    # the head. (The wanderers' punch is not a trace and stays a body hit.)
    make_shootable(bp)
    install_hit_zones(bp, handles["HealthComponent"])
    install_hit_reactions(bp, handles["HealthComponent"])
    aim_camera(bp)
    face_the_camera(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile")
    eas.save_loaded_asset(bp)
    _log("player: HealthComponent + WeaponComponent + FootstepComponent installed")


def install_on_npc(health_bp, footstep_bp):
    """The NPC gets health that despawns and respawns it.

    DespawnOnDeath and RespawnClass are set on *this* Blueprint's component
    template rather than on BP_HealthComponent's defaults, which is what keeps
    the same component class usable on the player without the player vanishing
    at 0 HP.
    """
    eas = _assets()
    bp = eas.load_asset(NPC_BP_PATH)
    if not bp:
        _log(f"note: {NPC_BP_PATH} not found — skipping the NPC")
        return None
    _drop_components(bp, {"HealthComponent", "FootstepComponent"})
    handle = _add_component(bp, _root_handle(bp),
                            BEL.generated_class(health_bp), "HealthComponent")
    # The same component the player carries. A wanderer at 600 cm/s covers a
    # stride more than three times a second, and ten of them arriving through
    # the trees is most of what the approach sounds like.
    _add_component(bp, _root_handle(bp),
                   BEL.generated_class(footstep_bp), "FootstepComponent")
    comp = _component_object(handle)
    comp.set_editor_property("DespawnOnDeath", True)
    comp.set_editor_property("RespawnClass", unreal.load_class(None, NPC_CLASS_PATH))

    # A respawned wanderer is spawned, not placed, so the default
    # "Placed in World" would leave it with no AI controller and no movement.
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    try:
        cdo.set_editor_property(
            "auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
    except Exception as exc:                                      # noqa: BLE001
        _log(f"note: could not set auto_possess_ai: {exc}")

    make_shootable(bp)
    install_hit_zones(bp, handle)
    # The PARENT's clips, i.e. whichever creature BP_ForestWanderer wears. Each
    # variant child is a different skeleton and cannot override an inherited
    # component's defaults from Python (see _author_stats_and_voice in
    # build_npc_blueprints.py), so its own six are copied onto the component at
    # possession by its own AI controller -- the same route its health takes.
    install_hit_reactions(bp, handle)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    eas.save_loaded_asset(bp)
    _log("NPC: HealthComponent + FootstepComponent installed "
         "(despawns and respawns at 0 HP)")
    return bp


def retire_old_assets():
    """Delete assets this build has superseded, once nothing references them.

    Both cases are the same shape: an asset that an earlier version of this
    builder created and that nothing now points at. Neither disappears on its
    own -- this builder updates in place, so a reference it simply stops
    emitting leaves the old asset sitting in the content tree, where the next
    person to read the audio folder will reasonably assume it is still in use.
    """
    eas = _assets()
    for path in (OLD_SHOTGUN_BP,) + RETIRED_SOUNDS:
        if not eas.does_asset_exist(path):
            continue
        try:
            if eas.delete_asset(path):
                _log(f"deleted the superseded {path}")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"note: {path} still referenced, left in place: {exc}")


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    build_materials()
    import_sounds()
    # Both halves have to exist before either can name the other, so the link
    # is a third step rather than something import_sounds() does on the way
    # past -- and it is a step that refuses to finish with a sound it has no
    # profile for.
    apply_attenuation(build_sound_attenuations())
    patch_anim_blueprint()

    # First of the Blueprints, and before anything that names its class: both
    # consumers -- this file's weapon component defaults and the HUD's settings
    # screen -- have to be able to load /Game/Weapons/BP_Settings, and the HUD
    # builder runs after this whole script.
    build_settings_savegame()

    # Before the weapons: every weapon's GripRotation is solved against the
    # ready pose as seen through the player's own rig, so the body has to be
    # the final one before the first spec is built.
    skin = wear_skin()

    item_bp = build_weapon_item()
    weapons = {}
    for spec in _weapon_specs():
        weapons[spec["display"]] = build_weapon(spec, item_bp)

    blood_bp = build_blood_splash()
    # Before the health component: its BeginPlay casts to the GameMode, and a
    # cast node only appears in the palette for a class that is already loaded.
    ensure_game_mode_vars()
    health_bp = build_health_component()
    footstep_bp = build_footstep_component()
    weapon_bp = build_weapon_component(item_bp, weapons["Shotgun"],
                                       weapons["Pistol"], blood_bp)

    # After the weapon component, because the pickup's graph casts to it -- and
    # therefore after the health component that spawns it, which is why the
    # link between the two is a default written here rather than a parameter.
    ammo_bp = build_ammo_pickup()
    _apply_defaults(health_bp, {
        "AmmoClass": BEL.generated_class(ammo_bp),
        # The three findable weapons, in the order _weapon_specs() lists them
        # rather than in an order written out here -- so a weapon added to
        # DROP_DISPLAYS is in the table with no second edit.
        "DropClasses": [BEL.generated_class(weapons[name])
                        for name in DROP_DISPLAYS],
    })
    _log(f"{HEALTH_BP_PATH}.AmmoClass -> {AMMO_BP_PATH}")
    _log(f"{HEALTH_BP_PATH}.DropClasses -> {', '.join(DROP_DISPLAYS)} "
         f"({GUN_DROP_CHANCE * 100:.0f}% per kill)")

    install_on_character(health_bp, weapon_bp, footstep_bp)
    install_on_npc(health_bp, footstep_bp)
    retire_old_assets()

    _log(f"done — five weapons, ammunition, inventory, aiming down the sights, "
         f"footsteps, blood, death, drops and respawn, worn by "
         f"{skin.mesh.rsplit('/', 1)[1]}")


if __name__ == "__main__":
    main()
