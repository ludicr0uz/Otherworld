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
# Which takes were chosen for each sound, and so how many of each there are
# (Scripts/Sound/sound_candidates/selection.py; pure Python).
from Sound.sound_candidates.selection import asset_names


# The mechanical sounds. All of these, and the five gunshots, are cut from
# recordings of real firearms. Which take each one is was chosen by ear on the
# audition page, and Scripts/Sound/install_selected_sounds.py writes the WAVs
# (assets/generated/sounds/SELECTED.md says what each was cut from).
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
# The .wav files are recordings now, as the gunshots are: the selection names
# the takes and how many there are of each, so a take added there is a take
# here. (Scripts/Sound/make_creature_sounds.py synthesised the first set.)
CREATURE_AUDIO_DIR = "/Game/Audio"
FOOTSTEP_NAMES = asset_names("footsteps")
MELEE_HIT_NAMES = asset_names("melee_hit")
WENDIGO_ROAR_NAMES = asset_names("wendigo_roar")
ZOMBIE_GROWL_NAMES = asset_names("zombie_growl")
CREATURE_VOICE_NAMES = ZOMBIE_GROWL_NAMES + WENDIGO_ROAR_NAMES
# What the first set had no sound for at all. The player's own voice, a swing
# through the air, the axe on a trunk, a match, and a campfire, which loops.
PLAYER_HIT_NAMES = asset_names("player_hit")
PLAYER_DEATH_NAMES = asset_names("player_death")
MELEE_SWING_NAMES = asset_names("melee_swing")
AXE_CHOP_NAMES = asset_names("axe_chop")
MATCH_NAMES = asset_names("match")
# A blade on a body, in the hand and thrown, and anything leaving the hand.
BLADE_HIT_NAMES = asset_names("blade_hit")
BLADE_LODGE_NAMES = asset_names("blade_lodge")
THROW_NAMES = asset_names("throw")
THROW_SHARP_NAMES = asset_names("throw_sharp")
CAMPFIRE_NAMES = asset_names("campfire")
LOOPING_NAMES = CAMPFIRE_NAMES

# ── The beds ─────────────────────────────────────────────────────────────────
#
# The one kind of sound that is NOT something in the level making a noise at a
# place: the forest itself, by day and by night, and the wind. A bed is
# stereo, loops, and has no attenuation profile on purpose -- it is all round
# the player wherever they stand. They live in a folder of their own, below
# the one apply_attenuation() sweeps, so that sweep still means what it says:
# every wave in the two audio folders is placed, and a flat one there is a
# mistake. BP_DayNightCycle plays them (world/ambience.py).
BED_DIR = f"{CREATURE_AUDIO_DIR}/Beds"
BED_DAY, BED_NIGHT, BED_WIND = (asset_names(key)[0] for key in
                                ("ambience_day", "ambience_night", "ambience_wind"))
BED_NAMES = (BED_DAY, BED_NIGHT, BED_WIND)
CREATURE_SOUND_NAMES = (FOOTSTEP_NAMES + MELEE_HIT_NAMES + CREATURE_VOICE_NAMES
                        + PLAYER_HIT_NAMES + PLAYER_DEATH_NAMES + MELEE_SWING_NAMES
                        + AXE_CHOP_NAMES + MATCH_NAMES + CAMPFIRE_NAMES
                        + BLADE_HIT_NAMES + BLADE_LODGE_NAMES + THROW_NAMES
                        + THROW_SHARP_NAMES)

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

    ``linear`` swaps the natural curve for a straight line from full volume to
    silence. Only the roar: see ATT_ROAR.
    """

    name: str
    radius_cm: float
    falloff_cm: float
    air_absorption: bool = False
    linear: bool = False

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


# THE ROAR IS HEARD FAR OFF, so it has a curve of its own. On the natural (dB)
# curve every other sound uses, a wendigo that saw the player from 35 m roared
# at about -34 dB: the loudest thing in the forest, and barely there. The
# curve is steep by design -- it reaches -60 dB at the edge, and is half way
# there in dB at half the distance -- which suits a noise heard close and is
# wrong for one whose whole purpose is to arrive from far away.
#
# So the roar is at full volume out to ROAR_FULL_CM and falls in a straight
# line from there to silence at its reach: at 35 m that is about half, -6 dB.
# Close up it is no louder than the recording (a multiplier never passes 1),
# so a wendigo that turns on the player at arm's length does not deafen them.
ROAR_FULL_CM = 1000.0
ATT_ROAR = AttenuationProfile("A_Att_WendigoRoar", ROAR_FULL_CM,
                              roar_reach_cm() - ROAR_FULL_CM, linear=True)
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
# The axe on a trunk carries as a creature's voice does: it is the loudest
# thing a player does without a gun, and the wanderers' hearing of it is the
# chop's own noise event, not this.
SOUND_ATTENUATION = dict(
    [(n, ATT_GUNFIRE) for n in GUNSHOT_NAMES]
    + [(n, ATT_FOLEY) for n in HANDLING_NAMES + FOOTSTEP_NAMES + PLAYER_HIT_NAMES
       + PLAYER_DEATH_NAMES + MELEE_SWING_NAMES + MATCH_NAMES + CAMPFIRE_NAMES + THROW_NAMES
       + THROW_SHARP_NAMES]
    + [(n, ATT_CREATURE) for n in MELEE_HIT_NAMES + CREATURE_VOICE_NAMES + AXE_CHOP_NAMES
       + BLADE_HIT_NAMES + BLADE_LODGE_NAMES]
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
        at.set_editor_property(
            "distance_algorithm",
            unreal.AttenuationDistanceModel.LINEAR if profile.linear
            else unreal.AttenuationDistanceModel.NATURAL_SOUND)
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


def _wav_is_newer(src, dest):
    """True if the WAV was written after the SoundWave it was imported as.
    A take chosen again is a new WAV under an old name, and an import that
    skipped every asset that exists would never hear of it."""
    package = unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()) + dest[len("/Game/"):] + ".uasset"
    return not os.path.isfile(package) or os.path.getmtime(src) > os.path.getmtime(package)


def import_sounds():
    """Import the WAVs as SoundWave assets, each one whose WAV is new or newer
    than its asset.

    Two folders, one source: assets/generated/sounds, written by
    Scripts/Sound/install_selected_sounds.py from the takes chosen on the
    audition page. It is run by hand rather than from main(): what it cuts
    from is gigabytes of downloaded packs, which an asset build should not
    need on every invocation.

    Nothing in /Engine/Content is a usable gunshot -- or footstep, or growl --
    which is why this project supplies its own at all.
    """
    eas = _assets()
    made = []
    how = "Scripts/Sound/install_selected_sounds.py"
    groups = ((AUDIO_DIR, SOUND_NAMES), (CREATURE_AUDIO_DIR, CREATURE_SOUND_NAMES),
              (BED_DIR, BED_NAMES))
    # A take dropped from the selection leaves its wave behind, under a name
    # nothing knows: the attenuation sweep would stop the build on it. Gone
    # first, so a row can lose a take as easily as it gains one.
    for folder, names in groups:
        for ref in eas.list_assets(folder, recursive=False):
            name = ref.rsplit("/", 1)[-1].split(".")[0]
            if name not in names and isinstance(eas.load_asset(ref), unreal.SoundWave):
                eas.delete_asset(f"{folder}/{name}")
                _log(f"removed {folder}/{name}: no longer a sound of the game")
    for folder, names in groups:
      for name in names:
        dest = f"{folder}/{name}"
        src = os.path.join(SOUND_SRC_DIR, f"{name}.wav")
        if not os.path.isfile(src):
            raise RuntimeError(f"missing {src} -- run {how}")
        if eas.does_asset_exist(dest) and not _wav_is_newer(src, dest):
            made.append(dest)
            continue
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
    # A fire does not end. Set every run, not only on import: it is a
    # property of the asset, and an import leaves it off.
    for name in LOOPING_NAMES:
        wave = eas.load_asset(f"{CREATURE_AUDIO_DIR}/{name}")
        wave.set_editor_property("looping", True)
        eas.save_loaded_asset(wave)
    # A bed loops, and goes on playing at volume zero: the day's birds fade
    # out at dusk and back in at dawn, and a wave the mixer dropped at zero
    # would start again from its first second each time.
    for name in BED_NAMES:
        wave = eas.load_asset(f"{BED_DIR}/{name}")
        wave.set_editor_property("looping", True)
        wave.set_editor_property("virtualization_mode",
                                 unreal.VirtualizationMode.PLAY_WHEN_SILENT)
        eas.save_loaded_asset(wave)
    return made
