"""The sound classes and the game's sound mix: what makes each sound's volume
one number, tunable in a game.

    /Game/Audio/A_Class_<Sound>   a SoundClass per row of sound_tuning.SOUND_STATS,
                                  given to that sound's waves
    /Game/Audio/A_Mix_Game        an empty SoundMix: the HUD makes it the base
                                  mix and overrides each class's volume in it
                                  with its row's (graphics_menu/sound_tune_tick.py)

The volume is not baked into the class or the wave: an override multiplies
what the asset holds, so a baked 0.4 under a tuned 0.4 would be 0.16. The
assets all stay at 1 and the HUD's table (sound_tuning.csv, baked into the
HUD) is the one place a volume is.

On the asset, as the attenuation is (audio.apply_attenuation): the play
sites are in three Blueprints by two builders, and the class is one write
per wave.
"""

import unreal

from combat.audio import BED_DIR, BED_NAMES, CREATURE_AUDIO_DIR, SOUND_ATTENUATION
from combat.log import _log
from combat.paths import AUDIO_DIR
from combat.sound_tuning import SOUND_STATS, class_name
from uebp.graph import _assets

SOUND_CLASS_DIR = CREATURE_AUDIO_DIR
SOUND_MIX_NAME = "A_Mix_Game"
SOUND_MIX_PATH = f"{SOUND_CLASS_DIR}/{SOUND_MIX_NAME}"
SOUND_CLASS_PROP = "sound_class_object"


def class_path(sound):
    return f"{SOUND_CLASS_DIR}/{class_name(sound)}"


def wave_path(name):
    """A wave's asset, in whichever of the audio folders holds it."""
    for folder in (AUDIO_DIR, CREATURE_AUDIO_DIR, BED_DIR):
        if _assets().does_asset_exist(f"{folder}/{name}"):
            return f"{folder}/{name}"
    raise RuntimeError(f"no SoundWave named {name} in {AUDIO_DIR} or {CREATURE_AUDIO_DIR}")


def _made(name, cls, factory):
    eas = _assets()
    path = f"{SOUND_CLASS_DIR}/{name}"
    asset = (eas.load_asset(path) if eas.does_asset_exist(path)
             else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                 name, SOUND_CLASS_DIR, cls, factory))
    if asset is None:
        raise RuntimeError(f"could not create {path}")
    return asset


def build_sound_mix():
    """The classes, the mix, and each wave's class. After import_sounds().
    Raises on a wave with no row, or in two: it would play at no one's volume."""
    eas = _assets()
    rows = [name for s in SOUND_STATS for name in s[2]]
    stray = sorted((set(SOUND_ATTENUATION) | set(BED_NAMES)) ^ set(rows))
    if stray or len(rows) != len(set(rows)):
        raise RuntimeError(f"sound_tuning.SOUND_STATS and the game's waves differ: "
                           f"{stray or 'a wave is in two rows'}")
    mix = _made(SOUND_MIX_NAME, unreal.SoundMix, unreal.SoundMixFactory())
    mix.set_editor_property("sound_class_effects", [])
    eas.save_loaded_asset(mix)
    for sound, _label, waves, _default in SOUND_STATS:
        cls = _made(class_name(sound), unreal.SoundClass, unreal.SoundClassFactory())
        props = cls.get_editor_property("properties")
        props.set_editor_property("volume", 1.0)
        cls.set_editor_property("properties", props)
        eas.save_loaded_asset(cls)
        for name in waves:
            wave = eas.load_asset(wave_path(name))
            wave.set_editor_property(SOUND_CLASS_PROP, cls)
            eas.save_loaded_asset(wave)
        _log(f"{class_name(sound)} -> {', '.join(waves)}")
    return mix
