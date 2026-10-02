"""Probe: down the sights the sway runs at the held gun's SwayRate, and holding
the breath stills it until the breath runs out (weapon_component/breath.py).

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_hold_breath.py

SightsForced stands in for the sights key and BreathForced for the hold
breath key. The breath is written short (Breath) rather than held for its
whole 5 s, which a headless game's slow clock may not reach.
"""

from combat.breath_tuning import (
    BREATH_FORCED_VAR, BREATH_HELD_VAR, BREATH_HOLD_S, BREATH_SCALE_VAR,
    BREATH_SWAY_SCALE, BREATH_VAR, BREATH_WINDED_SCALE, WINDED_VAR,
)
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.sway_tuning import (
    SWAY_MIN_STEP_DEG, SWAY_PITCH_DEG, SWAY_PITCH_VAR, SWAY_RATE_VAR, SWAY_TIME_VAR, SWAY_YAW_DEG,
    SWAY_YAW_VAR,
)

import unreal

WRITABLE = [(WEAPON_COMP_BP_PATH, v)
            for v in (SIGHTS_FORCED_VAR, BREATH_FORCED_VAR, BREATH_VAR)]


def probe(p):
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())

    def until(cond, seconds):
        t0 = now()
        yield lambda: cond() or now() - t0 > seconds
        return cond()

    p.set(wc, SIGHTS_FORCED_VAR, True)
    up = yield from until(lambda: p.get(wc, "SightAiming") and p.get(wc, "SightBlend") > 0.99, 5.0)
    p.check("the sights come up (SightsForced)", up, f"{p.get(wc, 'SightBlend'):.3f}")
    held = p.get(wc, "Held")
    rate = p.get(wc, SWAY_RATE_VAR)
    p.check("the component's SwayRate is the held gun's",
            held is not None and abs(rate - held.get_editor_property(SWAY_RATE_VAR)) < 1e-6,
            f"{rate} vs {held.get_editor_property(SWAY_RATE_VAR) if held else None}")

    t0, c0 = now(), p.get(wc, SWAY_TIME_VAR)
    yield 0.5
    ratio = (p.get(wc, SWAY_TIME_VAR) - c0) / max(now() - t0, 1e-6)
    p.check("...and the sway's clock runs at it", abs(ratio - rate) < 0.05 * rate + 0.01,
            f"{ratio:.3f} clock s per game s")
    p.check("not holding the breath: a full breath, the sway at its full width",
            not p.get(wc, BREATH_HELD_VAR) and abs(p.get(wc, BREATH_VAR) - BREATH_HOLD_S) < 1e-3
            and abs(p.get(wc, BREATH_SCALE_VAR) - 1.0) < 1e-3,
            f"breath {p.get(wc, BREATH_VAR):.2f}, scale {p.get(wc, BREATH_SCALE_VAR):.3f}")

    # Held.
    p.set(wc, BREATH_FORCED_VAR, True)
    steady = yield from until(lambda: p.get(wc, BREATH_SCALE_VAR) < BREATH_SWAY_SCALE + 0.02, 5.0)
    p.check("the key held down the sights holds the breath, and the sway's width "
            f"eases to {BREATH_SWAY_SCALE:g}",
            p.get(wc, BREATH_HELD_VAR) and steady, f"{p.get(wc, BREATH_SCALE_VAR):.3f}")
    p.check("...spending it", p.get(wc, BREATH_VAR) < BREATH_HOLD_S - 1e-3,
            f"{p.get(wc, BREATH_VAR):.3f} s left")
    worst = [0.0]

    def watch():
        worst[0] = max(worst[0], abs(p.get(wc, SWAY_YAW_VAR)) / SWAY_YAW_DEG,
                       abs(p.get(wc, SWAY_PITCH_VAR)) / SWAY_PITCH_DEG)
        return False
    t1 = now()
    yield lambda: watch() or now() - t1 > 0.5
    # The sway's own step threshold lets it lag up to SWAY_MIN_STEP_DEG.
    p.check("...and the sway held to a fraction of its width",
            worst[0] <= BREATH_SWAY_SCALE + 0.02 + SWAY_MIN_STEP_DEG / SWAY_PITCH_DEG,
            f"{worst[0]:.3f} of the full width")

    # Run out.
    p.set(wc, BREATH_VAR, 0.05)
    winded = yield from until(lambda: p.get(wc, WINDED_VAR), 3.0)
    yield 0.1
    p.check("spent, the player is winded and lets go though the key is held",
            winded and p.get(wc, BREATH_FORCED_VAR) and not p.get(wc, BREATH_HELD_VAR),
            f"winded {p.get(wc, WINDED_VAR)}, held {p.get(wc, BREATH_HELD_VAR)}")
    shaky = yield from until(lambda: p.get(wc, BREATH_SCALE_VAR) > BREATH_WINDED_SCALE - 0.02, 5.0)
    p.check(f"...the sway widening to {BREATH_WINDED_SCALE:g}", shaky,
            f"{p.get(wc, BREATH_SCALE_VAR):.3f}")
    p.check("...and the breath refilling", 0.0 < p.get(wc, BREATH_VAR) < BREATH_HOLD_S,
            f"{p.get(wc, BREATH_VAR):.3f}")

    # Whole again.
    p.set(wc, BREATH_VAR, BREATH_HOLD_S - 0.01)
    back = yield from until(lambda: p.get(wc, BREATH_HELD_VAR), 3.0)
    p.check("full again, the held key holds it again", back and not p.get(wc, WINDED_VAR),
            f"held {p.get(wc, BREATH_HELD_VAR)}, winded {p.get(wc, WINDED_VAR)}")

    # Off the sights.
    p.set(wc, SIGHTS_FORCED_VAR, False)
    off = yield from until(lambda: not p.get(wc, "SightAiming"), 3.0)
    yield 0.1
    p.check("off the sights the key holds nothing",
            off and not p.get(wc, BREATH_HELD_VAR), f"held {p.get(wc, BREATH_HELD_VAR)}")
    p.set(wc, BREATH_FORCED_VAR, False)
