"""A spent sprint's latch lets go with the key, and never holds stamina down.

No key can be injected into a headless game, so the sprint key is up for the
whole run and the latch cannot be seen to set here: verify/sprint.py checks
that wiring (key AND (spent OR Stamina <= 0)). What the game can show is the
other half, the one that would strand the player if it were wrong: with the
key up a latch left set clears on the next tick, zero stamina does not set it,
Sprinting stays down every frame, and the stamina refills.
"""

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component.sprint import SPRINT_SPENT_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, SPRINT_SPENT_VAR), (WEAPON_COMP_BP_PATH, "Stamina")]

FRAMES = 20


def probe(p):
    yield 0.2
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    p.check("the latch starts clear and the player is not sprinting",
            not p.get(wc, SPRINT_SPENT_VAR) and not p.get(wc, "Sprinting"))

    p.set(wc, "Stamina", 0.0)
    p.set(wc, SPRINT_SPENT_VAR, True)
    yield lambda: not p.get(wc, SPRINT_SPENT_VAR)
    p.check("a set latch clears once the sprint key is up",
            not p.get(wc, SPRINT_SPENT_VAR))

    # Frame by frame from empty: the old flicker was one frame on, one off.
    p.set(wc, "Stamina", 0.0)
    seen = []
    for _ in range(FRAMES):
        yield 0.0
        seen.append((p.get(wc, SPRINT_SPENT_VAR), p.get(wc, "Sprinting"),
                     p.get(wc, "Stamina")))
    p.check("zero stamina alone does not latch: the key is what holds it",
            not any(spent for spent, _, _ in seen))
    p.check("...and Sprinting stays down every frame",
            not any(running for _, running, _ in seen))
    levels = [s for _, _, s in seen]
    p.check("...while the stamina refills",
            levels[-1] > 0.0 and all(b >= a for a, b in zip(levels, levels[1:])),
            f"{levels[0]:.3f} -> {levels[-1]:.3f} over {FRAMES} yields")
