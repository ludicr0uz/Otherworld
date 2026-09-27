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

Each weapon gets its own body length and thump depth; that contrast is the
whole point, since five weapons otherwise sound alike and the player has no
other cue for which one is equipped. Broadly: the longer and deeper the tail,
the bigger the gun -- SMG is almost all crack, the sniper is almost all boom.

Two of the sounds are not shots at all and are built from a different
generator. A dry fire and a reload are *mechanical* noises: a hammer falling on
an empty chamber and a shell going into a tube are metal hitting metal, with no
powder behind them. _clack() lays one or more damped metallic rings into a
buffer at given offsets, which is what makes a reload a rhythm (clunk ... clunk
... clack) rather than a single event.

Output lands in assets/generated/sounds/ and is imported into
/Game/Weapons/Audio by build_weapons_and_combat.py.
"""

import math
import os
import random
import struct
import wave

RATE = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "generated", "sounds")


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


def _tick(n, decay, ring_hz, ring_decay, bright, rng):
    """One metallic click: a noise transient plus a short damped sine ring.

    The ring is what makes it read as *metal*. Noise alone is a pop; a pitched
    ring decaying over a few tens of milliseconds is a receiver closing.
    """
    out = []
    for i in range(n):
        t = i / RATE
        s = (bright * rng.uniform(-1.0, 1.0) * math.exp(-t / decay) +
             0.50 * math.sin(2.0 * math.pi * ring_hz * t) * math.exp(-t / ring_decay))
        out.append(math.tanh(s * 1.4))
    return out


def _clack(duration, events, seed):
    """Several clicks summed into one buffer at their own offsets.

    Each event is (offset_s, decay, ring_hz, ring_decay, bright, gain). A reload
    is three of them; a dry fire is one. Writing both through the same function
    means the click you hear on an empty chamber is the same *kind* of sound as
    the first half of the reload that fixes it, which is the cue the player
    actually learns.
    """
    rng = random.Random(seed)
    n = int(RATE * duration)
    out = [0.0] * n
    for offset, decay, ring_hz, ring_decay, bright, gain in events:
        start = int(RATE * offset)
        if start >= n:
            raise ValueError(f"event at {offset}s falls outside a {duration}s buffer")
        # Six time constants is silence to within 0.25%, so truncating there
        # costs nothing audible and keeps the inner loop short.
        span = min(n - start, int(RATE * max(decay, ring_decay) * 6.0))
        for i, v in enumerate(_tick(span, decay, ring_hz, ring_decay, bright, rng)):
            out[start + i] += gain * v

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
    # Shortest of the five: at 0.09 s between rounds the tail has to be out of
    # the way before the next shot starts, or the burst turns into mush.
    "A_SMGFire": dict(duration=0.26, crack_decay=0.011, body_decay=0.048,
                      body_cutoff=3800.0, thump_from=240.0, thump_to=115.0,
                      thump_decay=0.055, seed=21),
    # The middle of the range, and deliberately so -- the rifle is the weapon
    # everything else is heard relative to.
    "A_RifleFire": dict(duration=0.52, crack_decay=0.016, body_decay=0.105,
                        body_cutoff=2800.0, thump_from=200.0, thump_to=70.0,
                        thump_decay=0.125, seed=33),
    # Longest and deepest. One shot every 1.6 s can afford a 1.3 s tail, and
    # the tail is most of what sells a single shot as worth 120 damage.
    "A_SniperFire": dict(duration=1.30, crack_decay=0.045, body_decay=0.38,
                         body_cutoff=1200.0, thump_from=120.0, thump_to=35.0,
                         thump_decay=0.32, seed=44),
}

# Mechanical sounds: no powder, so no crack/body/thump -- just metal.
CLACKS = {
    # The hammer falls on nothing. One event, very short, fairly high: the
    # whole job of this sound is to be recognisably NOT a gunshot, because it
    # is the only thing telling the player why the trigger did nothing.
    "A_DryFire": dict(duration=0.14, seed=51, events=(
        (0.000, 0.0055, 2800.0, 0.018, 0.85, 1.00),
    )),
    # Three events: two shells into the tube, then the pump closing. The
    # rhythm is the point -- it lasts about as long as the reload it covers, so
    # the sound finishing is the cue that the weapon is live again.
    "A_Reload": dict(duration=0.90, seed=63, events=(
        (0.000, 0.0100, 430.0, 0.075, 0.55, 0.85),
        (0.230, 0.0100, 470.0, 0.070, 0.55, 0.85),
        (0.480, 0.0130, 880.0, 0.055, 0.90, 1.00),
    )),
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, kw in SHOTS.items():
        path = os.path.join(OUT_DIR, f"{name}.wav")
        secs = _write(path, _shot(**kw))
        print(f"[SND] {name}.wav  {secs:.2f}s  {os.path.getsize(path)/1024:.0f} KB")
    for name, kw in CLACKS.items():
        path = os.path.join(OUT_DIR, f"{name}.wav")
        secs = _write(path, _clack(**kw))
        print(f"[SND] {name}.wav  {secs:.2f}s  {os.path.getsize(path)/1024:.0f} KB")
    print(f"[SND] wrote {len(SHOTS) + len(CLACKS)} files to {OUT_DIR}")


if __name__ == "__main__":
    main()
