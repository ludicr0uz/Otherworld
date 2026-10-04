"""Weapon, foley and creature sound assets: the names, the four attenuation
profiles, importing the .wav files and linking every SoundWave to its profile.
"""

import dataclasses
import os

import unreal

from combat.log import _log
from uebp.graph import _assets
from combat.paths import AUDIO_DIR
from npc.monster_tuning import monster_specs


# The mechanical sounds. All of these, and the five gunshots, are now cut from
# CC0 recordings of real firearms by Scripts/Sound/fetch_weapon_sounds.py -- see that
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
# The .wav files come from Scripts/Sound/make_creature_sounds.py, which synthesises
# rather than cutting from recordings; that file's docstring says why that is
# the right call for these and the wrong one for gunfire.
CREATURE_AUDIO_DIR = "/Game/Audio"
FOOTSTEP_NAMES = tuple(f"A_Footstep_{i:02d}" for i in (1, 2, 3, 4))
MELEE_HIT_NAMES = tuple(f"A_MeleeHit_{i:02d}" for i in (1, 2, 3))
WENDIGO_ROAR_NAMES = tuple(f"A_WendigoRoar_{i:02d}" for i in (1, 2, 3))
CREATURE_VOICE_NAMES = (tuple(f"A_ZombieGrowl_{i:02d}" for i in (1, 2, 3))
                        + WENDIGO_ROAR_NAMES)
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
# A profile per kind of noise rather than one, because how far a noise carries is a fact
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
# A wendigo roars as it goes aggro, so the roar has to reach a player it has
# only just seen: it carries this many times the wendigo's aggro range (its
# sight, monster_tuning.csv's vision_range_cm: 35 m, so 61 m), and never past
# the 100 m ceiling. Sized from the tuned range when the build runs, so a range
# saved from the MONSTER SETTINGS tab moves the roar with the next weapons build.
ROAR_REACH_X_AGGRO = 1.75
ROAR_CREATURE = "Wendigo"


def roar_reach_cm():
    """How far the wendigo's roar is heard, in cm."""
    return min(ROAR_REACH_X_AGGRO * monster_specs(ROAR_CREATURE)["vision_range_cm"],
               AUDIBLE_LIMIT_CM)


ATT_ROAR = AttenuationProfile("A_Att_WendigoRoar", ATT_CREATURE.radius_cm,
                              roar_reach_cm() - ATT_CREATURE.radius_cm)
ATTENUATIONS = (ATT_GUNFIRE, ATT_CREATURE, ATT_ROAR, ATT_FOLEY)

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
    + [(n, ATT_CREATURE) for n in MELEE_HIT_NAMES + CREATURE_VOICE_NAMES]
    + [(n, ATT_ROAR) for n in WENDIGO_ROAR_NAMES])

# <project>/assets/generated/sounds -- this file is Scripts/combat/audio.py.
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SOUND_SRC_DIR = os.path.join(_PROJECT_DIR, "assets", "generated", "sounds")


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
    Scripts/Sound/fetch_weapon_sounds.py, which is run by hand rather than from
    main() -- it reaches the network and unpacks 194 MB, which is not something
    an asset build should do on every invocation. The foley and the monster
    voices are synthesised by Scripts/Sound/make_creature_sounds.py, which is cheap
    and offline. Both write into assets/generated/sounds; the cut and
    synthesised files are committed, the downloads are not.

    Nothing in /Engine/Content is a usable gunshot -- or footstep, or growl --
    which is why this project supplies its own at all.
    """
    eas = _assets()
    made = []
    groups = ((AUDIO_DIR, SOUND_NAMES, "Scripts/Sound/fetch_weapon_sounds.py"),
              (CREATURE_AUDIO_DIR, CREATURE_SOUND_NAMES,
               "Scripts/Sound/make_creature_sounds.py"))
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
