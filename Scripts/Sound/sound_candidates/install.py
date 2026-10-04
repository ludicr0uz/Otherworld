"""Install the selection: write each sound the game plays to
`assets/generated/sounds/`, under the name the builders import it by.

This is the step between listening and building. `selection.py` says which
takes were chosen; this cuts them to what the game is given (mono unless the
row is a bed, 16-bit, the project's sample rate) and puts a reload together
from its parts. The weapons build then imports what it finds
(`Sound.waves.import_sounds`), replacing a SoundWave whose WAV is newer.

It takes over from `fetch_weapon_sounds.py` and `make_creature_sounds.py` for
every name in the selection: run after either of them, it has the last word.
"""

import os

import numpy as np

from sound_candidates import dsp
from sound_candidates.selection import GAME, USES, asset_names

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
GENERATED_DIR = os.path.join(_PROJECT_DIR, "assets", "generated")
CANDIDATE_DIR = os.path.join(GENERATED_DIR, "sound_candidates")
SOUND_DIR = os.path.join(GENERATED_DIR, "sounds")
SOURCES_PATH = os.path.join(SOUND_DIR, "SELECTED.md")


def candidate_path(take):
    return os.path.join(CANDIDATE_DIR, take + ".wav")


def _load(take, channels):
    path = candidate_path(take)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path} -- run Scripts/Sound/prepare_sound_candidates.py")
    return dsp.decode(path, channels)


def _assemble(recipe, channels):
    """A reload out of its parts, each at its own start."""
    parts = [(_load(take, channels), int(dsp.RATE * start)) for take, start in recipe]
    out = np.zeros((max(at + len(s) for s, at in parts), channels), dtype=np.float32)
    for samples, at in parts:
        out[at:at + len(samples)] += samples
    return out


def _render(use):
    """`[samples]`, one per asset name of the row."""
    channels = 2 if use.stereo else 1
    sounds = ([_assemble(use.recipe, channels)] if use.recipe
              else [_load(take, channels) for take in use.takes])
    out = []
    for samples in sounds:
        if use.seconds:
            samples = dsp.fade(samples[:int(dsp.RATE * use.seconds)], 0.0, 300.0)
        if use.peak:
            samples = dsp.normalise(samples, use.peak)
        out.append(samples)
    return out


def install():
    """Write every GAME row's sounds. Returns `[(asset, seconds, from)]`."""
    written = []
    for use in USES:
        if use.status != GAME:
            continue
        sources = ([" + ".join(take for take, _at in use.recipe)] if use.recipe else use.takes)
        for name, samples, source in zip(asset_names(use.key), _render(use), sources):
            dsp.write(os.path.join(SOUND_DIR, name + ".wav"), samples)
            written.append((name, len(samples) / dsp.RATE, source))
    lines = ["# The sounds the game plays: where each was cut from", "",
             "Written by `Scripts/Sound/install_selected_sounds.py` from",
             "`Scripts/Sound/sound_candidates/selection.py`. Do not edit by hand.",
             "Each take's own source and licence are in `../sound_candidates/SOURCES.md`.", "",
             "| sound | s | take |", "|---|---|---|"]
    lines += [f"| `{name}` | {seconds:.2f} | `{source}` |" for name, seconds, source in written]
    with open(SOURCES_PATH, "w") as out:
        out.write("\n".join(lines) + "\n")
    return written
