#!/usr/bin/env python3
"""make_creature_sounds.py -- synthesise the foley and the monster voices.

    python3 Scripts/Sound/make_creature_sounds.py

Writes 44.1 kHz 16-bit mono WAVs into assets/generated/sounds/, alongside the
gunshots -- which is where Sound.waves.import_sounds() looks.

── Why these are synthesised when the gunshots are not ─────────────────────

Scripts/Sound/fetch_weapon_sounds.py cut the five gunshots from CC0 recordings of
real firearms, and its own docstring explains why a synthesiser could not do
that job: what makes a gunshot recognisable is the report slapping back off
whatever is around you, and a three-oscillator model has no way to invent a
treeline.  That argument is specific to gunfire and it does not carry over:

  footsteps   leaf litter under a boot IS filtered noise with a soft low
              thump under it.  There is no room signature to miss.
  melee hits  a body blow is a low transient plus a short broadband slap,
              over in a tenth of a second -- too short to carry a room.
  growls,     there is no recording of a wendigo.  Every monster voice in
  roars       every game is a processed source, so starting from a
              synthesised one skips a step rather than cutting a corner.

So this file takes the honest half of the synthesis approach and leaves the
gunshots where they belong.

── How the voices are made ─────────────────────────────────────────────────

A growl is a *voiced* sound, which is a different generator from anything in
the weapon set: a buzzing source at some fundamental, shaped by a few
resonances.  Three parts, and all three matter:

  source     a sawtooth at f0 plus noise.  Aliasing is not corrected for --
             a naive sawtooth's aliasing is inharmonic grit, which on a
             monster is an asset.
  formants   three 2-pole resonators.  These are what make it read as a
             THROAT rather than as a synthesiser: the zombie's sit low and
             close together (a chest), the wendigo's high and wide (a scream).
  roughness  f0 jitter plus a noisy tremolo.  A steady pitch sounds like a
             tone generator; the irregularity is most of what sells it as
             an animal.

Several takes per category rather than one, because a footstep played every
0.4 s from the same buffer stops being a footstep after about four steps.
The Blueprints hold an array and draw from it at random -- see
build_npc_blueprints.py.
"""

import math
import os
import random
import struct
import wave

RATE = 44100
# This file is Scripts/Sound/make_creature_sounds.py: the project is three up.
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "assets", "generated", "sounds")


# ─── Building blocks ────────────────────────────────────────────────────────

def _lowpass(samples, cutoff_hz):
    """One-pole low-pass."""
    dt = 1.0 / RATE
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    a = dt / (rc + dt)
    out, prev = [], 0.0
    for s in samples:
        prev += a * (s - prev)
        out.append(prev)
    return out


def _highpass(samples, cutoff_hz):
    """One-pole high-pass, as the difference between the signal and its own
    low-passed self. Used to keep the mud out of the bright half of a step."""
    lo = _lowpass(samples, cutoff_hz)
    return [s - l for s, l in zip(samples, lo)]


def _resonate(samples, freq_hz, bandwidth_hz, gain=1.0):
    """A 2-pole resonator -- one formant.

    y[n] = x[n] + 2 r cos(theta) y[n-1] - r^2 y[n-2], with the pole radius set
    from the bandwidth.  Normalised by (1 - r) so that widening a formant does
    not also make it quieter, which would otherwise make the three impossible
    to balance against each other.
    """
    theta = 2.0 * math.pi * freq_hz / RATE
    r = math.exp(-math.pi * bandwidth_hz / RATE)
    a1 = 2.0 * r * math.cos(theta)
    a2 = -(r * r)
    norm = (1.0 - r) * gain
    out = []
    y1 = y2 = 0.0
    for x in samples:
        y = x * norm + a1 * y1 + a2 * y2
        out.append(y)
        y2, y1 = y1, y
    return out


def _noise(n, rng):
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def _envelope(n, attack, decay, hold=0.0):
    """Attack / hold / exponential release, in seconds."""
    a = max(1, int(attack * RATE))
    h = int(hold * RATE)
    out = []
    for i in range(n):
        t = i / RATE
        if i < a:
            e = i / a
        elif i < a + h:
            e = 1.0
        else:
            e = math.exp(-(t - (a + h) / RATE) / max(decay, 1e-4))
        out.append(e)
    return out


def _declick(samples, fade_ms=4.0):
    fade = max(1, int(fade_ms * RATE / 1000.0))
    fade = min(fade, len(samples) // 2)
    for i in range(fade):
        samples[i] *= i / fade
        samples[-1 - i] *= i / fade
    return samples


def _write(path, samples, level=0.92):
    peak = max(abs(s) for s in samples) or 1.0
    gain = level / peak
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, s * gain)) * 32767))
        for s in samples)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    return len(samples) / RATE


# ─── Foley ──────────────────────────────────────────────────────────────────

# The brightest a footfall gets. Boot on leaf litter has essentially nothing
# above this, and leaving the top open is the difference between a step and a
# burst of static.
CRUNCH_TOP_HZ = 5200.0


def footstep(duration, low_cut, crunch_hz, crunch_decay, body_decay,
             grains, seed):
    """One footfall on forest floor: a soft body thump under a dry crunch.

    The crunch is not plain filtered noise -- ``grains`` short bursts are
    scattered through the first half, which is what leaf litter actually is
    (a handful of separate small snaps, not one hiss).
    """
    rng = random.Random(seed)
    n = int(RATE * duration)

    body = _lowpass(_noise(n, rng), low_cut)
    # Band-LIMITED, not just high-passed. A one-pole high-pass leaves
    # everything above its corner untouched, so the first version of this was
    # a 23 kHz-bright hiss with a thump hiding under it -- measured, not
    # guessed. Capping the top at CRUNCH_TOP_HZ is what turns it back into
    # leaf litter.
    crunch = _lowpass(_highpass(_noise(n, rng), crunch_hz), CRUNCH_TOP_HZ)

    out = []
    for i in range(n):
        t = i / RATE
        out.append(1.00 * body[i] * math.exp(-t / body_decay) +
                   0.42 * crunch[i] * math.exp(-t / crunch_decay))

    # Leaf grains: tiny ticks scattered through the first 60% of the step,
    # built in their own buffer so they can be band-limited with the same
    # ceiling as the crunch rather than putting the hiss straight back.
    grain_buf = [0.0] * n
    for _ in range(grains):
        start = int(rng.uniform(0.0, 0.6) * n)
        span = int(RATE * rng.uniform(0.002, 0.006))
        amp = rng.uniform(0.10, 0.30)
        for i in range(span):
            if start + i >= n:
                break
            grain_buf[start + i] += amp * rng.uniform(-1.0, 1.0) * (1.0 - i / span)
    for i, g in enumerate(_lowpass(grain_buf, CRUNCH_TOP_HZ)):
        out[i] += g

    return _declick([math.tanh(s * 1.3) for s in out], 2.0)


def melee_hit(duration, thump_from, thump_to, thump_decay,
              meat_cut, meat_decay, slap_decay, seed):
    """A body blow: a pitched thump, a dull filtered body, and a short slap.

    The slap is the shortest of the three and is what makes it land -- without
    it the sound reads as something heavy being dropped nearby rather than as
    contact.
    """
    rng = random.Random(seed)
    n = int(RATE * duration)
    meat = _lowpass(_noise(n, rng), meat_cut)
    slap = _highpass(_noise(n, rng), 1800.0)

    out = []
    for i in range(n):
        t = i / RATE
        f = thump_from + (thump_to - thump_from) * min(1.0, t / thump_decay)
        phase = 2.0 * math.pi * (thump_from * t + 0.5 * (f - thump_from) * t)
        out.append(0.80 * math.sin(phase) * math.exp(-t / thump_decay) +
                   0.75 * meat[i] * math.exp(-t / meat_decay) +
                   0.45 * slap[i] * math.exp(-t / slap_decay))
    return _declick([math.tanh(s * 1.5) for s in out], 3.0)


# ─── Voices ─────────────────────────────────────────────────────────────────

def voice(duration, f0_points, formants, noise_mix, rasp_hz, rasp_depth,
          jitter, attack, decay, hold, drive, seed):
    """A growl or a roar.

    ``f0_points`` is a list of (fraction_through, hz) that the fundamental is
    linearly interpolated between -- a growl barely moves, a roar rises and
    then falls away, and that contour is most of the difference between the
    two.  ``formants`` is a list of (hz, bandwidth, gain).
    """
    rng = random.Random(seed)
    n = int(RATE * duration)

    def f0_at(frac):
        for i in range(len(f0_points) - 1):
            x0, y0 = f0_points[i]
            x1, y1 = f0_points[i + 1]
            if x0 <= frac <= x1:
                k = (frac - x0) / max(x1 - x0, 1e-6)
                return y0 + (y1 - y0) * k
        return f0_points[-1][1]

    # --- source: naive sawtooth at a jittering f0, plus breath -------------
    src = []
    phase = 0.0
    wobble = 0.0
    for i in range(n):
        frac = i / n
        # Jitter is smoothed random walk, not per-sample noise: per-sample
        # jitter is just more hiss, while a wandering pitch is a throat.
        wobble += (rng.uniform(-1.0, 1.0) - wobble) * 0.0009
        f = f0_at(frac) * (1.0 + jitter * wobble)
        phase = (phase + f / RATE) % 1.0
        saw = 2.0 * phase - 1.0
        src.append((1.0 - noise_mix) * saw + noise_mix * rng.uniform(-1.0, 1.0))

    # --- formants: three resonators in parallel ----------------------------
    voiced = [0.0] * n
    for hz, bw, gain in formants:
        for i, v in enumerate(_resonate(src, hz, bw, gain)):
            voiced[i] += v

    # --- roughness and shape -----------------------------------------------
    env = _envelope(n, attack, decay, hold)
    out = []
    rasp_walk = 0.0
    for i in range(n):
        t = i / RATE
        rasp_walk += (rng.uniform(-1.0, 1.0) - rasp_walk) * 0.02
        # Tremolo at rasp_hz, itself made irregular by the walk -- a clean
        # tremolo sounds like an effect pedal.
        trem = 1.0 - rasp_depth * (0.5 + 0.5 * math.sin(
            2.0 * math.pi * rasp_hz * t + 2.0 * rasp_walk))
        out.append(math.tanh(voiced[i] * env[i] * trem * drive))
    return _declick(out, 8.0)


# ─── The set ────────────────────────────────────────────────────────────────
#
# Footsteps: four takes, deliberately not four seeds of one recipe. A step is
# heard hundreds of times a minute, so the variation has to be in the sound and
# not only in the noise -- these differ in how bright and how long they are, so
# the sequence reads as different ground underfoot rather than as one sample
# being retriggered.
FOOTSTEPS = (
    ("A_Footstep_01", dict(duration=0.16, low_cut=260.0, crunch_hz=1400.0,
                           crunch_decay=0.042, body_decay=0.055, grains=5, seed=101)),
    ("A_Footstep_02", dict(duration=0.14, low_cut=300.0, crunch_hz=1900.0,
                           crunch_decay=0.030, body_decay=0.048, grains=8, seed=102)),
    ("A_Footstep_03", dict(duration=0.18, low_cut=220.0, crunch_hz=1150.0,
                           crunch_decay=0.055, body_decay=0.065, grains=3, seed=103)),
    ("A_Footstep_04", dict(duration=0.15, low_cut=280.0, crunch_hz=1650.0,
                           crunch_decay=0.036, body_decay=0.052, grains=6, seed=104)),
)

# Melee: three, because the wanderers swing every 1.5 s and a pack of ten
# lands hits far faster than that.
MELEE = (
    ("A_MeleeHit_01", dict(duration=0.34, thump_from=125.0, thump_to=52.0,
                           thump_decay=0.085, meat_cut=620.0, meat_decay=0.10,
                           slap_decay=0.013, seed=201)),
    ("A_MeleeHit_02", dict(duration=0.30, thump_from=150.0, thump_to=62.0,
                           thump_decay=0.070, meat_cut=780.0, meat_decay=0.085,
                           slap_decay=0.010, seed=202)),
    ("A_MeleeHit_03", dict(duration=0.38, thump_from=105.0, thump_to=44.0,
                           thump_decay=0.100, meat_cut=520.0, meat_decay=0.12,
                           slap_decay=0.016, seed=203)),
)

# The zombie: LOW, close-packed formants and almost no pitch movement. A chest
# with something wrong in it. Heavy noise mix, because the thing is supposed to
# sound like it cannot breathe properly.
ZOMBIE_VOICE = dict(
    f0_points=[(0.0, 68.0), (0.45, 74.0), (1.0, 62.0)],
    formants=[(430.0, 130.0, 1.00), (1080.0, 200.0, 0.62), (2350.0, 340.0, 0.28)],
    noise_mix=0.30, rasp_hz=23.0, rasp_depth=0.45, jitter=0.16,
    attack=0.13, decay=0.30, drive=1.9,
)
GROWLS = (
    ("A_ZombieGrowl_01", dict(duration=1.25, hold=0.45, seed=301, **ZOMBIE_VOICE)),
    ("A_ZombieGrowl_02", dict(duration=0.95, hold=0.25, seed=302, **ZOMBIE_VOICE)),
    ("A_ZombieGrowl_03", dict(duration=1.55, hold=0.70, seed=303, **ZOMBIE_VOICE)),
)

# The wendigo: higher and much wider apart, so it reads as a scream from
# something with a long throat rather than as a bigger zombie. The pitch
# contour does the rest -- it climbs hard and then falls away, which the
# zombie's deliberately does not.
WENDIGO_VOICE = dict(
    f0_points=[(0.0, 115.0), (0.22, 205.0), (0.60, 188.0), (1.0, 132.0)],
    formants=[(720.0, 150.0, 1.00), (1540.0, 240.0, 0.78), (3150.0, 420.0, 0.42)],
    noise_mix=0.42, rasp_hz=31.0, rasp_depth=0.32, jitter=0.11,
    attack=0.07, decay=0.55, drive=2.4,
)
ROARS = (
    ("A_WendigoRoar_01", dict(duration=1.70, hold=0.55, seed=401, **WENDIGO_VOICE)),
    ("A_WendigoRoar_02", dict(duration=1.35, hold=0.35, seed=402, **WENDIGO_VOICE)),
    ("A_WendigoRoar_03", dict(duration=2.05, hold=0.80, seed=403, **WENDIGO_VOICE)),
)

# Levels. The footstep is the player's own boot and is heard constantly, so it
# sits well under everything else; a roar is meant to carry across the forest.
LEVELS = {"foot": 0.42, "melee": 0.88, "growl": 0.70, "roar": 0.92}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    made = 0
    for name, kw in FOOTSTEPS:
        path = os.path.join(OUT_DIR, f"{name}.wav")
        secs = _write(path, footstep(**kw), LEVELS["foot"])
        print(f"[SND] {name}.wav  {secs:.2f}s")
        made += 1
    for name, kw in MELEE:
        path = os.path.join(OUT_DIR, f"{name}.wav")
        secs = _write(path, melee_hit(**kw), LEVELS["melee"])
        print(f"[SND] {name}.wav  {secs:.2f}s")
        made += 1
    for group, level in ((GROWLS, "growl"), (ROARS, "roar")):
        for name, kw in group:
            path = os.path.join(OUT_DIR, f"{name}.wav")
            secs = _write(path, voice(**kw), LEVELS[level])
            print(f"[SND] {name}.wav  {secs:.2f}s")
            made += 1
    print(f"[SND] wrote {made} files to {OUT_DIR}")


if __name__ == "__main__":
    main()
