"""Importing the WAVs as SoundWave assets: every take of every row of the
sound table, into its row's folder, and the flags an import leaves off.
"""

import os

import unreal

from combat.log import _log
from Sound.catalog import BED_NAMES, CREATURE_SOUND_NAMES, LOOPING_NAMES, SOUND_NAMES
from Sound.sound_def import BED_DIR, CREATURE_AUDIO_DIR, WEAPON_AUDIO_DIR
from uebp.graph import _assets

# <project>/assets/generated/sounds -- this file is Scripts/Sound/waves.py.
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SOUND_SRC_DIR = os.path.join(_PROJECT_DIR, "assets", "generated", "sounds")


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
    groups = ((WEAPON_AUDIO_DIR, SOUND_NAMES), (CREATURE_AUDIO_DIR, CREATURE_SOUND_NAMES),
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
