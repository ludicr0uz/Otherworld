"""The sound build's steps (Scripts/build_sound.py calls them in order).

    build_sound_assets()   the waves, their attenuation, their classes and
                           the mix: everything that is an asset of its own
    apply_sound_bindings() each sound's takes onto the Blueprint variable or
                           component that plays them, as the Blueprints stand
    apply_sound_volumes()  sound_tuning.csv onto the HUD's table

The weapons build runs the first, because its Blueprints hold the waves; the
other two re-write what the Blueprints' own builders wrote, so a changed
mapping or volume needs this build and no other.
"""

from combat.log import _log
from graphics_menu.sound_tune_tick import sound_tune_defaults
from graphics_menu.umg_consts import HUD_BP_PATH
from Sound.attenuation import apply_attenuation, build_sound_attenuations
from Sound.bind import apply_bindings
from Sound.catalog import BINDINGS
from Sound.mix import build_sound_mix
from Sound.waves import import_sounds
from uebp.graph import _apply_defaults, _assets, _must_load


def build_sound_assets():
    import_sounds()
    # Both halves have to exist before either can name the other, so the link
    # is a third step rather than something import_sounds() does on the way
    # past -- and it is a step that refuses to finish with a sound it has no
    # profile for.
    apply_attenuation(build_sound_attenuations())
    # A sound class per sound, so each has a volume (the SOUND SETTINGS tab).
    build_sound_mix()


def apply_sound_bindings():
    return apply_bindings(BINDINGS)


def apply_sound_volumes():
    """The CSV's volumes into the HUD's table, as build_graphics_menu.py bakes
    them. The HUD's graph is not touched: a new ROW of the table needs that
    build."""
    if not _assets().does_asset_exist(HUD_BP_PATH):
        _log(f"note: {HUD_BP_PATH} is not built yet -- its builder bakes the volumes")
        return False
    _apply_defaults(_must_load(HUD_BP_PATH), sound_tune_defaults())
    _log(f"{HUD_BP_PATH}: the sound tuning table is sound_tuning.csv's")
    return True
