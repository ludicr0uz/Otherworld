"""Decode, cut and write audio: the signal half of the candidate cutter.

Everything here is a float32 numpy array of shape (frames, channels) at RATE.
ffmpeg does the decoding and the resampling (the sources are WAV at 44.1 to
192 kHz, OGG and MP3); numpy does the cutting. Nothing here knows which sound
is which: that is `manifest.py`.
"""

import os
import subprocess
import wave

import numpy as np

# The project's AudioSampleRate (Config/DefaultEngine.ini). The first set was
# cut at 44.1 kHz and resampled by the engine on every play.
RATE = 48000

ENV_BLOCK_MS = 10.0     # the envelope's resolution
FADE_IN_MS = 2.0        # kills the click of an abrupt start, no more
FADE_OUT_MS = 20.0


def decode(path, channels):
    """`path` as float32 (frames, channels) at RATE. A stereo file asked for
    as mono is the mean of its sides, which is ffmpeg's downmix."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le",
         "-ac", str(channels), "-ar", str(RATE), "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).copy()


def envelope(samples):
    """Peak per ENV_BLOCK_MS block, across channels."""
    block = int(RATE * ENV_BLOCK_MS / 1000.0)
    mono = np.abs(samples).max(axis=1)
    count = len(mono) // block
    if count == 0:
        return np.array([mono.max() if len(mono) else 0.0])
    return mono[:count * block].reshape(count, block).max(axis=1)


def _blocks(ms):
    return max(1, int(round(ms / ENV_BLOCK_MS)))


def _frames(ms):
    return int(RATE * ms / 1000.0)


def fade(samples, in_ms=FADE_IN_MS, out_ms=FADE_OUT_MS):
    out = samples.copy()
    n_in = min(_frames(in_ms), len(out) // 2)
    n_out = min(_frames(out_ms), len(out) // 2)
    if n_in:
        out[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)[:, None]
    if n_out:
        out[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype=np.float32)[:, None]
    return out


def normalise(samples, peak):
    top = float(np.abs(samples).max()) if len(samples) else 0.0
    return samples if top <= 0.0 else samples * (peak / top)


def trim(samples, floor=0.02, lead_ms=5.0, tail_ms=60.0):
    """Drop the silence either side of the sound. `floor` is a fraction of the
    file's own peak, so a quiet recording is not trimmed to nothing."""
    env = envelope(samples)
    loud = np.nonzero(env > env.max() * floor)[0]
    if not len(loud):
        return samples
    block = _frames(ENV_BLOCK_MS)
    start = max(0, loud[0] * block - _frames(lead_ms))
    end = min(len(samples), (loud[-1] + 1) * block + _frames(tail_ms))
    return samples[start:end]


def split_events(samples, floor=0.06, gap_ms=180.0, min_ms=40.0,
                 lead_ms=5.0, tail_ms=80.0):
    """The separate takes of a file that holds several, in order.

    A take is a run of the envelope above `floor` (a fraction of the file's
    peak). Runs closer than `gap_ms` are one take: a punch and its own flesh
    slap 60 ms later are not two punches.
    """
    env = envelope(samples)
    loud = env > env.max() * floor
    runs, start = [], None
    for i, on in enumerate(loud):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append([start, i])
            start = None
    if start is not None:
        runs.append([start, len(loud)])

    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < _blocks(gap_ms):
            merged[-1][1] = run[1]
        else:
            merged.append(run)

    block = _frames(ENV_BLOCK_MS)
    takes = []
    for first, last in merged:
        if last - first < _blocks(min_ms):
            continue
        a = max(0, first * block - _frames(lead_ms))
        b = min(len(samples), last * block + _frames(tail_ms))
        takes.append(samples[a:b])
    return takes


def count_transients(samples, level=0.75, gap_ms=30.0):
    """How many separate events reach `level` of the cut's peak. One for a
    single shot; an echo is quieter than that, a second round is not."""
    env = envelope(samples)
    hits = np.nonzero(env >= env.max() * level)[0]
    count, last = 0, None
    for i in hits:
        if last is None or i - last > _blocks(gap_ms):
            count += 1
        last = i
    return count


def cut_shot(samples, seconds, lead_ms=10.0, onset=0.10, tail_fraction=0.30):
    """`seconds` of a gunshot from its onset, faded over its last part.

    The library's files run 9 to 30 s, most of it the report coming back off
    the treeline, so the cut is truncated and the fade is long: it has to
    sound like a decay, not like an edit.
    """
    env = envelope(samples)
    first = int(np.nonzero(env > env.max() * onset)[0][0])
    start = max(0, first * _frames(ENV_BLOCK_MS) - _frames(lead_ms))
    cut = samples[start:start + int(RATE * seconds)]
    return fade(cut, FADE_IN_MS, seconds * 1000.0 * tail_fraction)


def single_shots(samples, seconds, count, level=0.5, gap_ms=60.0, lead_ms=8.0,
                 tail_fraction=0.30):
    """The cleanest ``count`` single shots of a recording that holds several.

    A file of gunfire is shots at any spacing: singles seconds apart, or a
    burst a tenth of a second apart, where each shot's tail is the next one's
    start. Every transient that reaches ``level`` of the file's peak is a
    shot; the ones kept are those with the most room after them before the
    next, because that room is the shot's own tail. Each is cut from just
    before its transient to ``seconds`` on or to the next shot, whichever
    comes first, and faded as cut_shot fades.
    """
    env = envelope(samples)
    block = _frames(ENV_BLOCK_MS)
    loud = np.nonzero(env >= env.max() * level)[0]
    onsets = [int(i) for n, i in enumerate(loud)
              if n == 0 or i - loud[n - 1] > _blocks(gap_ms)]
    ends = onsets[1:] + [len(env)]
    room = sorted(((end - on, on, end) for on, end in zip(onsets, ends)), reverse=True)
    cuts = []
    for _gap, on, end in sorted(room[:count], key=lambda r: r[1]):
        start = max(0, on * block - _frames(lead_ms))
        stop = min(start + int(RATE * seconds), end * block - _frames(lead_ms), len(samples))
        cut = samples[start:stop]
        cuts.append(fade(cut, FADE_IN_MS, len(cut) / RATE * 1000.0 * tail_fraction))
    return cuts


def loopify(samples, seconds=None, cross_s=2.0):
    """A seamless loop out of a recording that is not one: its head is
    cross-faded (equal power) into its tail, so the end runs into the start."""
    if seconds:
        samples = samples[:int(RATE * seconds)]
    n = min(int(RATE * cross_s), len(samples) // 4)
    t = np.linspace(0.0, np.pi / 2.0, n, dtype=np.float32)[:, None]
    body = samples[n:].copy()
    body[-n:] = body[-n:] * np.cos(t) + samples[:n] * np.sin(t)
    return body


def repitch(samples, semitones):
    """Played slower or faster, as a tape is: pitch and length move together.
    Down is what turns a man's grunt into something bigger than a man."""
    if not semitones:
        return samples
    rate = 2.0 ** (semitones / 12.0)
    at = np.arange(0, len(samples) - 1, rate)
    idx = at.astype(np.int64)
    frac = (at - idx).astype(np.float32)[:, None]
    return samples[idx] * (1.0 - frac) + samples[idx + 1] * frac


def mix(layers):
    """Sum `(samples, gain)` layers, each from its own start."""
    length = max(len(s) for s, _ in layers)
    out = np.zeros((length, layers[0][0].shape[1]), dtype=np.float32)
    for samples, gain in layers:
        out[:len(samples)] += samples * gain
    return out


def tile(samples, seconds):
    """A loop repeated out to `seconds`."""
    need = int(RATE * seconds)
    reps = -(-need // len(samples))
    return np.tile(samples, (reps, 1))[:need]


def write(path, samples):
    """16-bit PCM WAV, the format the engine's importer is given."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).round().astype("<i2")
    with wave.open(path, "wb") as out:
        out.setnchannels(samples.shape[1])
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm.tobytes())
