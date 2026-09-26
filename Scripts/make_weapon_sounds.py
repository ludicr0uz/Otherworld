"""
make_weapon_sounds.py -- synthesise the gunshot WAVs.

Pure Python (no `unreal` import), so it runs standalone:

    python3 Scripts/make_weapon_sounds.py

The project ships no audio assets at all, and a gunshot is not something that
can be conjured from engine content -- /Engine/Content has no weapon SFX. Rather
than take a dependency on a download, the two shots are synthesised here from
noise and a pitch-swept sine, which is how a real gunshot is usually faked:

    crack   bright noise, very fast decay   -- the supersonic snap
    body    low-passed noise, slower decay  -- the powder charge
    thump   sine swept downward             -- the chest punch

The shotgun gets a longer body and a deeper thump than the pistol; that contrast
is the whole point, since the two weapons otherwise sound alike and the player
has no other cue for which one is equipped.

Output lands in Scripts/generated_assets/sounds/ and is imported into
/Game/Weapons/Audio by build_weapons_and_combat.py.
"""

import math
import os
import random
import struct
import wave

RATE = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "generated_assets", "sounds")


def _lowpass(samples, cutoff_hz):
    """One-pole low-pass. Crude, but it is the difference between 'hiss' and 'boom'."""
    dt = 1.0 / RATE
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = dt / (rc + dt)
    out, prev = [], 0.0
    for s in samples:
        prev += alpha * (s - prev)
        out.append(prev)
    return out


def _noise(n, rng):
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def _shot(duration, crack_decay, body_decay, body_cutoff,
          thump_from, thump_to, thump_decay, seed):
    """One gunshot = crack + body + thump, summed and soft-clipped."""
    rng = random.Random(seed)
    n = int(RATE * duration)
    crack = _noise(n, rng)
    body = _lowpass(_noise(n, rng), body_cutoff)

    out = []
    for i in range(n):
        t = i / RATE
        # Sine swept downward in frequency; phase is the integral of frequency,
        # so sweeping f linearly means the phase term is quadratic in t.
        f = thump_from + (thump_to - thump_from) * min(1.0, t / thump_decay)
        phase = 2.0 * math.pi * (thump_from * t +
                                 0.5 * (f - thump_from) * t)
        s = (0.55 * crack[i] * math.exp(-t / crack_decay) +
             0.85 * body[i] * math.exp(-t / body_decay) +
             0.70 * math.sin(phase) * math.exp(-t / thump_decay))
        # A gunshot is a clipped sound in real life too; tanh keeps it loud
        # without the buzz that hard clipping adds.
        out.append(math.tanh(s * 1.6))

    # 4 ms fade-in kills the click a hard start would make, and a fade-out at the
    # tail stops the loop point from popping.
    fade = int(RATE * 0.004)
    for i in range(fade):
        out[i] *= i / fade
        out[-1 - i] *= i / fade
    return out


def _write(path, samples):
    peak = max(abs(s) for s in samples) or 1.0
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s / peak)) * 32000))
                      for s in samples)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    return len(samples) / RATE


SHOTS = {
    # Deep, long, loud -- 12-gauge.
    "A_ShotgunFire": dict(duration=0.90, crack_decay=0.035, body_decay=0.26,
                          body_cutoff=1600.0, thump_from=140.0, thump_to=45.0,
                          thump_decay=0.22, seed=12),
    # Tighter and brighter, roughly half the tail.
    "A_PistolFire": dict(duration=0.45, crack_decay=0.018, body_decay=0.085,
                         body_cutoff=3200.0, thump_from=210.0, thump_to=80.0,
                         thump_decay=0.10, seed=7),
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, kw in SHOTS.items():
        path = os.path.join(OUT_DIR, f"{name}.wav")
        secs = _write(path, _shot(**kw))
        print(f"[SND] {name}.wav  {secs:.2f}s  {os.path.getsize(path)/1024:.0f} KB")
    print(f"[SND] wrote {len(SHOTS)} files to {OUT_DIR}")


if __name__ == "__main__":
    main()
