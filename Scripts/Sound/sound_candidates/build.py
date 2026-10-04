"""Run the manifest: cut every row and write the candidates and their sources.

Output goes to `assets/generated/sound_candidates/`, which nothing imports.
`Sound.waves.import_sounds()` reads `assets/generated/sounds/`, so a candidate
is in the game only once someone has listened to it and moved it there.
"""

import glob
import os
import shutil
import tempfile
import wave

from sound_candidates import dsp
from sound_candidates import manifest, manifest_archive, manifest_guns
from sound_candidates.manifest import PREVIEWS

ROWS = manifest.ROWS + manifest_archive.ROWS + manifest_guns.ROWS
LICENCES = {**manifest.LICENCES, **manifest_archive.LICENCES}

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
CACHE_DIR = os.path.join(_PROJECT_DIR, "assets", "cache", "sounds")
OUT_DIR = os.path.join(_PROJECT_DIR, "assets", "generated", "sound_candidates")


def _find(pattern, optional=False):
    found = sorted(glob.glob(os.path.join(CACHE_DIR, pattern), recursive=True))
    if not found and optional:
        return []
    if not found:
        raise FileNotFoundError(f"no source for {pattern!r} under {CACHE_DIR}")
    return found


def _rel(path):
    return os.path.relpath(path, CACHE_DIR)


def _legacy(path, opts):
    """A sound of the first set, cut exactly as it was: by
    fetch_weapon_sounds.py's own functions, at its own rate, then brought to
    this one. The first gunshots were liked better than the second ones, and
    "the same take, cut the same way" is the only honest way to have them back."""
    import fetch_weapon_sounds as first
    cut = first._cut(first._to_mono(path), opts.get("seconds", 0.0), opts["peak"],
                     opts.get("lead_ms", 0.0), seek_onset="seconds" in opts)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        name = tmp.name
    try:
        with wave.open(name, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(first.RATE)
            out.writeframes(b"".join(int(s).to_bytes(2, "little", signed=True) for s in cut))
        return dsp.decode(name, 1)
    finally:
        os.remove(name)


def _takes(op, source, opts, channels):
    """`[(samples, source_path)]` for one row, cut but not yet levelled."""
    if op == "design":
        layers, used = [], []
        for pattern, semitones, gain in opts["layers"]:
            path = _find(pattern)[0]
            used.append(path)
            layers.append((dsp.repitch(dsp.trim(dsp.decode(path, channels)), semitones), gain))
        return [(dsp.fade(dsp.mix(layers)), " + ".join(_rel(p) for p in used))]

    paths = _find(source, opts.get("optional", False))
    if not paths:
        return []
    if op == "each":
        paths = paths[:opts.get("limit")]
        return [(dsp.fade(dsp.trim(dsp.decode(p, channels))), _rel(p)) for p in paths]
    if op == "split":
        samples = dsp.decode(paths[0], channels)
        cuts = dsp.split_events(samples, gap_ms=opts.get("gap_ms", 180.0))
        return [(dsp.fade(c), _rel(paths[0])) for c in cuts[:opts.get("limit")]]
    if op == "shot":
        cut = dsp.cut_shot(dsp.decode(paths[0], channels), opts["seconds"])
        shots = dsp.count_transients(cut)
        if shots != 1:
            raise ValueError(f"{_rel(paths[0])}: {shots} shots in the cut, wanted 1")
        return [(cut, _rel(paths[0]))]
    if op == "shots":
        cuts = dsp.single_shots(dsp.decode(paths[0], channels), opts["seconds"],
                                opts.get("limit", 2))
        return [(c, _rel(paths[0])) for c in cuts]
    if op == "loop":
        return [(dsp.decode(paths[0], channels), _rel(paths[0]))]
    if op == "legacy":
        return [(_legacy(paths[0], opts), _rel(paths[0]))]
    if op == "mkloop":
        samples = dsp.trim(dsp.decode(paths[0], channels), tail_ms=0.0)
        return [(dsp.loopify(samples, opts.get("seconds")), _rel(paths[0]))]
    raise ValueError(f"unknown op {op!r}")


def build_rows():
    """Cut every row. Returns `[(out_name, seconds, channels, source)]`."""
    written = []
    for op, out, source, opts in ROWS:
        channels = 2 if opts.get("stereo") else 1
        takes = _takes(op, source, opts, channels)
        numbered = len(takes) > 1 or op in ("each", "split", "shots")
        for i, (samples, src) in enumerate(takes, 1):
            if opts.get("named"):
                name = f"{out}/{os.path.splitext(os.path.basename(src))[0]}"
            else:
                name = f"{out}_{i:02d}" if numbered else out
            if opts.get("peak"):   # none: the file's own level, untouched
                samples = dsp.normalise(samples, opts["peak"])
            dsp.write(os.path.join(OUT_DIR, name + ".wav"), samples)
            written.append((name, len(samples) / dsp.RATE, channels, src))
    return written


def build_previews():
    written = []
    for out, seconds, layers in PREVIEWS:
        parts = []
        for loop, gain in layers:
            samples = dsp.decode(os.path.join(OUT_DIR, loop + ".wav"), 2)
            parts.append((dsp.tile(samples, seconds), gain))
        mixed = dsp.normalise(dsp.fade(dsp.mix(parts), 500.0, 2000.0), 0.6)
        dsp.write(os.path.join(OUT_DIR, out + ".wav"), mixed)
        written.append((out, seconds, 2, " + ".join(l for l, _ in layers)))
    return written


def write_sources(written):
    lines = [
        "# Sound candidates: sources",
        "",
        "Produced by `Scripts/Sound/prepare_sound_candidates.py`. Do not edit by hand:",
        "re-run the script. Nothing here is in the game: these are for listening.",
        "",
        "## Licences",
        "",
        "| pack | licence | from |",
        "|---|---|---|",
    ]
    for folder in sorted(LICENCES):
        name, licence, url = LICENCES[folder]
        lines.append(f"| {name} (`{folder}/`) | {licence} | <{url}> |")
    lines += ["", "## Files", "", "| candidate | s | ch | cut from |", "|---|---|---|---|"]
    for name, seconds, channels, src in written:
        lines.append(f"| `{name}` | {seconds:.2f} | {channels} | `{src}` |")
    with open(os.path.join(OUT_DIR, "SOURCES.md"), "w") as out:
        out.write("\n".join(lines) + "\n")


def build():
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)   # a dropped row must not leave its file behind
    written = build_rows()
    written += build_previews()
    write_sources(written)
    return written
