"""The sprint's latch, in the running game: a sprint that runs Stamina out
stays off until the key is let go (the movement component's rule, C++:
Source/Otherworld, combat/player_move.py).

    key up      zero stamina alone does not latch, Sprinting stays down and
                the bar refills.
    key held    (SprintForced, a probe's hand on it, steering forward) the
                player sprints at the sprint's speed, the bar runs out, the
                latch sets and Sprinting stays down every frame after, bar
                refilling, for as long as the key is held: no flicker.
    key let go  the latch clears.
"""

import math

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.sprint_tuning import SPRINT_FORCED_VAR
from combat.tuning import COMBAT
from combat.weapon_component.sprint import SPRINT_SPENT_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, SPRINT_FORCED_VAR)]
MOVE = unreal.OtherworldMovementLibrary
# What the held sprint starts with: a third of a second's worth.
SHORT_BAR = COMBAT.stamina_drain_per_s / 3.0
HELD_S = 1.2

FRAMES = 20


def _forward(pawn):
    yaw = math.radians(pawn.get_actor_rotation().yaw)
    pawn.add_movement_input(unreal.Vector(math.cos(yaw), math.sin(yaw), 0.0), 1.0, False)


def _speed(pawn):
    v = pawn.get_velocity()
    return math.hypot(v.x, v.y)


def probe(p):
    yield 0.2
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    p.check("the latch starts clear and the player is not sprinting",
            not p.get(wc, SPRINT_SPENT_VAR) and not p.get(wc, "Sprinting"))

    # Frame by frame from empty: the old flicker was one frame on, one off.
    MOVE.set_stamina(pawn, 0.0)
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

    # The key held through the bar's end.
    MOVE.set_stamina(pawn, SHORT_BAR)
    p.set(wc, SPRINT_FORCED_VAR, True)
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    t0, held = now(), []
    while now() - t0 < HELD_S:
        _forward(pawn)
        yield 0.0
        held.append((bool(p.get(wc, "Sprinting")), bool(p.get(wc, SPRINT_SPENT_VAR)),
                     float(p.get(wc, "Stamina")), _speed(pawn)))
    ran = [h for h in held if h[0]]
    first_spent = next((i for i, h in enumerate(held) if h[1]), None)
    p.check("the key held, steering forward, the player sprints: faster than the jog",
            bool(ran) and max(h[3] for h in ran) > COMBAT.jog_speed_cms + 20.0,
            f"{len(ran)} sprinting frames of {len(held)}, top speed "
            f"{max((h[3] for h in held), default=0):.0f} cm/s")
    p.check("...until the bar runs out, which latches the sprint spent",
            first_spent is not None and min(h[2] for h in held) < 0.5,
            f"spent from frame {first_spent}, lowest bar {min(h[2] for h in held):.2f}")
    after = held[first_spent:] if first_spent is not None else []
    p.check("...and it stays off every frame the key is still held: no flicker",
            len(after) > 3 and all(spent and not running for running, spent, _, _ in after),
            f"{len(after)} frames, {sum(1 for h in after if h[0])} of them sprinting")
    p.check("...while the bar refills under the held key",
            len(after) > 3 and after[-1][2] > after[1][2],
            f"{after[1][2]:.2f} -> {after[-1][2]:.2f}" if len(after) > 3 else "")

    p.set(wc, SPRINT_FORCED_VAR, False)
    yield lambda: not p.get(wc, SPRINT_SPENT_VAR)
    p.check("letting the key go clears the latch", not p.get(wc, SPRINT_SPENT_VAR))
