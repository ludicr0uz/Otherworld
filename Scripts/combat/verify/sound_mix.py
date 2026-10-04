"""verify.sound_mix -- each sound's SoundClass on its waves, and the game's
sound mix (Sound/mix.py). The volumes themselves are the HUD's table:
verify_graphics_menu (graphics_menu/sound_tune_checks.py).
"""

from Sound.catalog import BED_NAMES, SOUND_ATTENUATION, SOUND_STATS
from Sound.mix import SOUND_CLASS_PROP, SOUND_MIX_PATH, class_path, wave_path
from Sound.tuning import FOOTSTEPS, table
from combat.verify.common import check, load
from combat.verify.fixtures import _eas


def check_sound_classes():
    rows = [name for s in SOUND_STATS for name in s[2]]
    check("every sound of the game is in exactly one row of the sound tuning table",
          sorted(rows) == sorted(tuple(SOUND_ATTENUATION) + BED_NAMES),
          str(sorted(set(rows) ^ (set(SOUND_ATTENUATION) | set(BED_NAMES)))))
    wrong = []
    for sound, _label, waves, _default in SOUND_STATS:
        path = class_path(sound)
        if not _eas.does_asset_exist(path):
            wrong.append(f"no {path}")
            continue
        cls = load(path)
        # An override multiplies the class's own volume: it must stay 1.
        if abs(cls.get_editor_property("properties").volume - 1.0) > 1e-6:
            wrong.append(f"{sound} class volume")
        for name in waves:
            got = load(wave_path(name)).get_editor_property(SOUND_CLASS_PROP)
            if got != cls:
                wrong.append(f"{name} -> {got.get_name() if got else None}")
    check(f"each of the {len(SOUND_STATS)} sounds has a SoundClass of its own, at "
          f"volume 1, and every wave of it plays in that class", not wrong, str(wrong))


def check_sound_mix():
    mix = load(SOUND_MIX_PATH) if _eas.does_asset_exist(SOUND_MIX_PATH) else None
    check("the game's sound mix exists and adjusts nothing itself (the HUD "
          "overrides each class's volume in it)",
          mix is not None and len(mix.get_editor_property("sound_class_effects")) == 0,
          str(mix))
    volumes = table()
    check("the sound tuning table holds every volume between 0 and 2, the "
          "footsteps' under 1",
          all(0.0 <= v <= 2.0 for v in volumes.values()) and volumes[FOOTSTEPS] < 1.0,
          str(volumes))


def run():
    check_sound_classes()
    check_sound_mix()
