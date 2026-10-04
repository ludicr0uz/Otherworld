"""What a sound is, as data: the folders, the attenuation profiles the areas
share, a row of the sound table (Sound) and where a sound is played from
(Binding). Constants only -- no `unreal` import, no authoring.

Each area module (sound_weapons, sound_monsters, sound_items, sound_world)
is a table of Sound rows and a table of Bindings; catalog.py puts the four
together, and build_sound.py writes them onto the assets and the Blueprints.
"""

import dataclasses

from combat.paths import AUDIO_DIR
# Which takes were chosen for each sound, and so how many of each there are
# (Scripts/Sound/sound_candidates/selection.py; pure Python).
from Sound.sound_candidates.selection import asset_names

# Two folders, and a third below the second. The guns' own sounds (shots,
# reloads, the dry click) are in /Game/Weapons/Audio; everything else is not a
# weapon sound -- footsteps belong to anything with legs and the growls to the
# monsters -- and is in /Game/Audio. The beds are in a folder of their own,
# below the one apply_attenuation() sweeps (see sound_world.py).
WEAPON_AUDIO_DIR = AUDIO_DIR
CREATURE_AUDIO_DIR = "/Game/Audio"
BED_DIR = f"{CREATURE_AUDIO_DIR}/Beds"

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


def takes(key):
    """The selection's takes for a use: the SoundWave names, in order."""
    return asset_names(key)


@dataclasses.dataclass(frozen=True)
class Sound:
    """One row of the sound table: what the player hears as one thing.

    ``key`` is its row of sound_tuning.csv and its SoundClass, ``label`` its
    row on the SOUND SETTINGS tab, ``names`` its SoundWaves (the takes, one
    drawn per play), ``attenuation`` how far it carries (None: a bed, which is
    not at a place), ``volume`` its volume with no CSV row, and ``looping``
    whether a take goes round (a fire does not end).
    """

    key: str
    label: str
    names: tuple
    attenuation: object
    folder: str = CREATURE_AUDIO_DIR
    volume: float = 1.0
    looping: bool = False

    @property
    def paths(self):
        return tuple(f"{self.folder}/{n}" for n in self.names)


@dataclasses.dataclass(frozen=True)
class Binding:
    """Where a sound is played from: a variable of a Blueprint, holding the
    sound's takes as an array (or, ``single``, its first take). With
    ``component`` the variable is a property of that component of the
    Blueprint (an AudioComponent's ``sound``) rather than of the class.

    The graphs read the variable; which takes it holds is this row, written
    by the Blueprint's builder and again by build_sound.py (bind.py).
    """

    blueprint: str
    variable: str
    sound: Sound
    single: bool = False
    component: str = ""
