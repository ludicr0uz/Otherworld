"""Build the weapon audio from free recordings of real firearms.

This replaces Scripts/make_weapon_sounds.py, which synthesised every sound from
noise bursts and damped sines. That was enough to prove the wiring -- a shot
made a noise, and the noise came from the muzzle -- but it never sounded like a
gun, because the thing that makes a gunshot recognisable is the part a
three-oscillator model has no way to produce: the slap of the report off
whatever is around you. A forest full of trunks is exactly that, and it is the
half the synthesiser could not invent.

So the sounds are now cut from recordings, and every source is **CC0** (public
domain dedication) -- not CC-BY, not CC-BY-SA. That is a deliberate filter and
the reason several better-known packs were passed over: this project has no
credits screen to put an attribution in, and a licence whose terms cannot be
honoured is worse than a licence that was never taken.

    Prepared SFX Library          22 real firearms, outdoors, 96 kHz/24-bit.
    (The Free Firearm Sound       Still North Media / freefirearmsfx.com.
    Library, CC0)                 https://opengameart.org/content/the-free-firearm-sound-library
    Gun reload sounds (CC0)       https://opengameart.org/content/gun-reload-sounds
    Gun reload, lock or click     https://opengameart.org/content/gun-reload-lock-or-click-sound
    sound (CC0)

Everything here is the macOS toolchain that is always present -- ``curl`` for
the fetch, ``bsdtar`` for the 7-Zip archive (libarchive reads it; the ``7z``
binary is not installed on a stock Mac), ``afconvert`` for the format
conversion -- plus the standard library's ``wave`` module for the cut itself.
No pip install, no Homebrew, nothing to import that the synthesiser did not
already manage without.

    python3 Scripts/Sound/fetch_weapon_sounds.py

Downloads are cached in assets/cache/sounds/ (gitignored, ~200 MB) so a
re-run only re-cuts. Output is nine 44.1 kHz 16-bit mono WAVs in
assets/generated/sounds/, which is exactly where
combat.audio.import_sounds() looks for them.

MONO IS NOT A SIZE OPTIMISATION. PlaySoundAtLocation spatialises a sound by
panning and attenuating it around the listener, and it can only do that to a
source that has one channel: hand it the stereo original and UE plays it flat,
at full volume, with no sense of where the muzzle was. The downmix is what
makes a shot come from the gun.
"""

import os
import re
import shutil
import subprocess
import sys
import urllib.request
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(HERE))   # this file is Scripts/Sound/
CACHE_DIR = os.path.join(PROJECT_DIR, "assets", "cache", "sounds")
OUT_DIR = os.path.join(PROJECT_DIR, "assets", "generated", "sounds")

RATE = 44100
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

# ─── Sources ─────────────────────────────────────────────────────────────────

OGA = "https://opengameart.org/sites/default/files"

# (cache name, url, page it came from, what it is)
DOWNLOADS = (
    ("firearm_library.7z", f"{OGA}/Prepared%20SFX%20Library.7z",
     "https://opengameart.org/content/the-free-firearm-sound-library",
     "The Free Firearm Sound Library, prepared edition — 22 firearms"),
    ("shotguncock.wav", f"{OGA}/shotguncock_0.wav",
     "https://opengameart.org/content/gun-reload-sounds",
     "pump shotgun being cocked"),
    ("riflereload.wav", f"{OGA}/assaultriflereload1_0.wav",
     "https://opengameart.org/content/gun-reload-sounds",
     "magazine out, magazine in, bolt released"),
    ("pistolreload.wav", f"{OGA}/gunreload1.wav",
     "https://opengameart.org/content/gun-reload-sounds",
     "slower handling reload"),
    ("lockclick.mp3", f"{OGA}/gun_reload_lock_or_click_sound.mp3",
     "https://opengameart.org/content/gun-reload-lock-or-click-sound",
     "a single metallic lock/click"),
)

# The 7-Zip archive holds 104 takes across 22 firearms, several takes per file
# with seconds of silence between them. Only these five are unpacked.
ARCHIVE_ROOT = "Prepared SFX Library"
ARCHIVE_WANTED = ("1911", "Mossberg", "Carl Gustav M45", "AK-47", "Mosin Nagant")

# ─── What each output is cut from ────────────────────────────────────────────
#
# Which real gun stands in for which of the five is not arbitrary, and neither
# is it about the silhouette the player sees -- it is about the report:
#
#   Shotgun   Mossberg 500        the pump shotgun everything else imitates
#   Pistol    Colt 1911           .45 ACP; a flat heavy crack, not a pop
#   SMG       Carl Gustav M45     9 mm SMG, dry and short -- see LEVELS below
#   Rifle     AK-47               7.62x39, the loudest thing in the set
#   Sniper    Mosin Nagant        bolt-action rifle with the longest tail
#
# WHICH TAKE matters as much as which gun, and picking one by ear is not an
# option here. Most files in this library hold several takes seconds apart, and
# several of the automatic weapons' takes are BURSTS: AK-47/C_29P looks like a
# single shot at 20 ms resolution and is four rounds 90 ms apart -- which, cut
# to 0.9 s and played on every trigger pull, gives an assault rifle that fires
# four bullets per click. Every take below was checked for exactly one
# transient inside its own window before it was chosen.
#
# SECONDS is measured from the onset, and it is a real decision rather than a
# trim: the Prepared library records outdoors, so every take runs 9-30 s and
# most of that is the report coming back off the treeline. Keeping all of it
# would be gorgeous and unusable -- the SMG fires every 0.09 s, so a 9 s sample
# is a hundred overlapping copies. What each weapon keeps is roughly its own
# fire interval plus enough tail to hear where it went.
#
# LEVEL is the peak the cut is normalised to, and it is the whole answer to
# "hold the button down and the automatics clip". Nine SMG shots overlapping
# at 0.95 is distortion; at 0.55 it is a burst. Baking it into the sample
# rather than driving PlaySoundAtLocation's VolumeMultiplier keeps the mix a
# property of the asset and costs the firing graph no nodes at all.
#
# (output, source, seconds after onset, peak level, lead-in ms)
SHOTS = (
    ("A_ShotgunFire", ("Mossberg", "N_26P.wav"),        1.30, 0.95, 12.0),
    ("A_PistolFire",  ("1911", "A_42P.wav"),            0.95, 0.85, 12.0),
    ("A_SMGFire",     ("Carl Gustav M45", "G_20P.wav"), 0.60, 0.55, 8.0),
    ("A_RifleFire",   ("AK-47", "C_31P.wav"),           0.90, 0.68, 8.0),
    ("A_SniperFire",  ("Mosin Nagant", "M_26P.wav"),    1.60, 0.95, 12.0),
)

# The handling sounds. Three reloads rather than one: a pump shotgun, a
# magazine swap and a slower hand-fed reload are three different actions, and
# the weapon table already carries a per-weapon slot for which one to play.
# The click is shared by all five, because a hammer falling on an empty chamber
# really is the same noise in every receiver.
#
# These are cut whole -- no onset search -- because each file already IS the
# event, with nothing before or after it.
HANDLING = (
    ("A_ReloadShotgun", "shotguncock.wav",  None, 0.90),
    ("A_ReloadRifle",   "riflereload.wav",  None, 0.90),
    ("A_ReloadPistol",  "pistolreload.wav", None, 0.90),
    # The click is deliberately the quietest thing in the set. It is a "you
    # have no ammunition" cue, not an event, and at shot level it reads as a
    # malfunction rather than as an empty gun.
    ("A_DryFire",       "lockclick.mp3",    None, 0.45),
)

ONSET_FRACTION = 0.10   # of the file's peak; the first block this loud is the shot
FADE_IN_MS = 2.0        # just enough to kill the click of an abrupt start

# Two different fades, because the two kinds of cut end for two different
# reasons. A shot is TRUNCATED -- the real tail is still ringing at the point
# the window closes -- so it needs a long fade, over the last third, to sound
# like a decay rather than like an edit. A handling sound is WHOLE: it already
# ends in its own silence, and a long fade there would land on the loudest
# event in the file (the bolt release, at 1.28 s of a 1.56 s reload) and duck
# it by 70%. It gets a de-click and nothing more.
FADE_OUT_FRACTION = 0.30
HANDLING_FADE_MS = 20.0


# ─── Fetching ────────────────────────────────────────────────────────────────

def _fetch():
    """Download anything not already cached. Returns nothing; raises on failure."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    for name, url, page, what in DOWNLOADS:
        dest = os.path.join(CACHE_DIR, name)
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            print(f"  cached  {name} ({os.path.getsize(dest) / 1e6:.1f} MB)")
            continue
        print(f"  fetch   {name} <- {url}")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        tmp = dest + ".part"
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out)
        os.replace(tmp, dest)
        print(f"          {os.path.getsize(dest) / 1e6:.1f} MB")


def _unpack():
    """Extract the five wanted firearm folders from the 7-Zip archive.

    bsdtar, not 7z: libarchive reads 7-Zip and ships with macOS, whereas the
    reference 7z binary does not. Extracting only what is used keeps ~90 MB of
    takes for seventeen guns this project does not fire out of the tree.
    """
    root = os.path.join(CACHE_DIR, "firearms")
    archive = os.path.join(CACHE_DIR, "firearm_library.7z")
    missing = [g for g in ARCHIVE_WANTED
               if not os.path.isdir(os.path.join(root, ARCHIVE_ROOT, g))]
    if not missing:
        print(f"  cached  {len(ARCHIVE_WANTED)} firearm folders")
        return os.path.join(root, ARCHIVE_ROOT)
    os.makedirs(root, exist_ok=True)
    patterns = [f"{ARCHIVE_ROOT}/{g}/*" for g in ARCHIVE_WANTED]
    print(f"  unpack  {', '.join(missing)}")
    subprocess.run(["bsdtar", "-xf", archive, "-C", root] + patterns, check=True)
    return os.path.join(root, ARCHIVE_ROOT)


# ─── Reading, cutting, writing ───────────────────────────────────────────────

def _to_mono(src):
    """Any source format -> 44.1 kHz 16-bit mono samples, via afconvert.

    afconvert is in /usr/bin on every Mac, handles the 96 kHz/24-bit originals
    and the one mp3, and does the stereo downmix and the sample-rate conversion
    in one pass. Writing that conversion by hand would mean a resampler, and a
    bad resampler on a transient this sharp is audible.
    """
    tmp = os.path.join(CACHE_DIR, "_convert.wav")
    subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{RATE}", "-c", "1",
                    src, tmp], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with wave.open(tmp, "rb") as w:
        if w.getframerate() != RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise RuntimeError(f"afconvert gave {w.getparams()} for {src}")
        raw = w.readframes(w.getnframes())
    os.remove(tmp)
    return [int.from_bytes(raw[i:i + 2], "little", signed=True)
            for i in range(0, len(raw), 2)]


def _find_onset(samples, block):
    """Index of the first block loud enough to be the shot, not the room.

    A fixed start time would be wrong for every take: the Prepared library's
    files begin with anywhere from 0.2 s to 3.5 s of the recordist standing
    there. The threshold is a fraction of the file's own peak rather than an
    absolute level, so it does not care how hot the take was recorded.
    """
    peak = max(abs(s) for s in samples) or 1
    floor = peak * ONSET_FRACTION
    for i in range(0, len(samples) - block, block):
        if max(abs(s) for s in samples[i:i + block]) >= floor:
            return i
    return 0


def _cut(samples, seconds, level, lead_ms, seek_onset):
    """One normalised, faded window of samples."""
    if seek_onset:
        start = max(0, _find_onset(samples, RATE // 200) - int(lead_ms * RATE / 1000.0))
        end = min(len(samples), start + int(seconds * RATE))
    else:
        start, end = 0, len(samples)
    cut = samples[start:end]
    if not cut:
        raise RuntimeError("empty cut")

    peak = max(abs(s) for s in cut) or 1
    gain = (level * 32767.0) / peak

    fade_in = max(1, int(FADE_IN_MS * RATE / 1000.0))
    fade_out = max(1, int(len(cut) * FADE_OUT_FRACTION) if seek_onset
                   else int(HANDLING_FADE_MS * RATE / 1000.0))
    out = []
    for i, s in enumerate(cut):
        v = s * gain
        if i < fade_in:
            v *= i / fade_in
        tail = len(cut) - i
        if tail < fade_out:
            # Squared, not linear: a linear fade over 30% of a gunshot audibly
            # ducks the tail. Squared leaves the decay alone until the end.
            v *= (tail / fade_out) ** 2
        out.append(max(-32768, min(32767, int(v))))
    return out


SHOT_LEVEL = 0.75      # of the cut's peak; a second SHOT is this loud, an echo is not
SHOT_GAP_MS = 30.0     # closer together than this and it is one event, not two


def _count_shots(samples):
    """How many separate reports are in this cut. Must be 1 for a gunshot.

    This exists because of a bug that was in the first version of this file and
    was not audible from any number it printed: AK-47/C_29P reads as a single
    shot at 20 ms resolution and is actually four rounds 90 ms apart, so the
    assault rifle fired a four-round burst on every trigger pull while the log
    happily reported "0.90s <- AK-47/C_29P.wav".

    Telling a second shot from the report coming back off the treeline is the
    whole difficulty, and it is done on LEVEL rather than on timing: in these
    recordings a repeat shot is within a few percent of the first, while the
    loudest slapback measured (Mosin Nagant/M_26P, 140 ms after the crack) is
    0.61 of it. The 0.75 line sits between those with room on both sides.

    It is not a perfect detector and is not claimed to be one -- a two-round
    burst 40 ms apart reads as one event, because at that spacing nothing
    distinguishes it from a single report with a hard early reflection. What it
    does catch reliably is the failure that actually happened: a burst of four
    or more.
    """
    block = RATE // 200                       # 5 ms
    env = [max((abs(v) for v in samples[i:i + block]), default=0)
           for i in range(0, len(samples), block)]
    peak = max(env) or 1
    gap = int(SHOT_GAP_MS / 5.0)
    count, last = 0, -10 ** 6
    for i, level in enumerate(env):
        if level >= SHOT_LEVEL * peak:
            if i - last > gap:
                count += 1
            last = i
    return count


def _write(name, samples):
    path = os.path.join(OUT_DIR, f"{name}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(int(s).to_bytes(2, "little", signed=True)
                               for s in samples))
    return path


# ─── Provenance ──────────────────────────────────────────────────────────────

def _write_credits(rows):
    """A record of where every sample came from, next to the samples.

    CC0 requires no attribution. This exists anyway, because "where did this
    file come from" is a question that gets asked about audio long after
    everyone has forgotten, and the answer being un-findable is how a project
    ends up unable to prove it may ship what it ships.
    """
    lines = [
        "# Weapon audio — sources",
        "",
        "Produced by `Scripts/Sound/fetch_weapon_sounds.py`. Do not edit by hand:",
        "re-run the script.",
        "",
        "**Every source below is CC0 1.0 (public domain dedication).** No",
        "attribution is legally required; it is recorded because provenance is",
        "worth more than the licence text.",
        "",
        "| asset | cut from | source |",
        "|---|---|---|",
    ]
    lines += rows
    lines += [
        "",
        "## Sources",
        "",
    ]
    for name, url, page, what in DOWNLOADS:
        lines.append(f"- **{what}** — <{page}> (CC0)")
    lines += [
        "",
        "All five gunshots come from the same library, recorded outdoors with",
        "the same rig, which is why they sit together in a mix: five samples",
        "from five places would differ in room and in distance before they",
        "differed in calibre.",
        "",
    ]
    path = os.path.join(OUT_DIR, "SOURCES.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    if sys.platform != "darwin":
        raise SystemExit("needs macOS: afconvert and bsdtar are the toolchain")
    for tool in ("afconvert", "bsdtar"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found — expected in /usr/bin on macOS")

    os.makedirs(OUT_DIR, exist_ok=True)
    print("sources:")
    _fetch()
    firearms = _unpack()

    rows = []
    print("cutting:")
    for name, (gun, take), seconds, level, lead in SHOTS:
        src = os.path.join(firearms, gun, take)
        samples = _to_mono(src)
        cut = _cut(samples, seconds, level, lead, seek_onset=True)
        shots = _count_shots(cut)
        if shots != 1:
            raise RuntimeError(
                f"{name}: {gun}/{take} gives {shots} reports in {seconds}s, not 1 "
                f"-- that take is a burst. Pick another, or shorten the window.")
        path = _write(name, cut)
        print(f"  {name:16s} {len(cut) / RATE:5.2f}s  peak {level:.2f}  "
              f"<- {gun}/{take} ({len(samples) / RATE:.1f}s original)")
        rows.append(f"| `{name}` | {gun} — `{take}` | The Free Firearm "
                    f"Sound Library |")

    for name, cache_name, seconds, level in HANDLING:
        src = os.path.join(CACHE_DIR, cache_name)
        samples = _to_mono(src)
        cut = _cut(samples, seconds, level, 0.0, seek_onset=False)
        path = _write(name, cut)
        print(f"  {name:16s} {len(cut) / RATE:5.2f}s  peak {level:.2f}  "
              f"<- {cache_name}")
        origin = next(d for d in DOWNLOADS if d[0] == cache_name)
        rows.append(f"| `{name}` | `{cache_name}` — {origin[3]} | "
                    f"<{origin[2]}> |")

    credits = _write_credits(rows)
    print(f"wrote {len(SHOTS) + len(HANDLING)} sounds to {OUT_DIR}")
    print(f"wrote {credits}")


if __name__ == "__main__":
    main()
