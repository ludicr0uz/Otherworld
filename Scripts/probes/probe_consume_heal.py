"""Eating a mushroom heals 10 HP on EASY and nothing on MEDIUM.

The verifier proves GA_ConsumeItem's graph is wired that way; this proves the
game does it: the ability is granted, the event reaches it, the heal lands (a
tick after the event, not inside it), and hunger refills on both levels.

The GameMode's Difficulty is written directly: in a -nullrhi run the HUD never
draws, so the per-frame copy from BP_Settings onto the GameMode never runs and
cannot overwrite it.
"""

SYSTEMS = ('survival',)

from combat.difficulty import DIFFICULTY_VAR, EASY, MEDIUM
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from net.state_consts import GAME_STATE_BP_PATH
from combat.tuning import CONSUME_EVENT_TAG
from survival.paths import MUSHROOM_CLASS_PATH, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from survival.tuning import MUSHROOM_HEALTH_EASY
from combat import health_vars as HV
from survival import component_vars as UV

WRITABLE = [(HEALTH_BP_PATH, HV.Health), (SURVIVAL_BP_PATH, UV.Hunger),
            (GAME_STATE_BP_PATH, DIFFICULTY_VAR)]

START_HEALTH = 50.0
START_HUNGER = 50.0     # well under the cap, so a refill always shows
SETTLE = 0.3            # game seconds for the ability to activate and apply


def _eat(p, difficulty):
    pawn = p.pawn()
    health = p.component(pawn, HEALTH_CLASS_PATH)
    survival = p.component(pawn, SURVIVAL_CLASS_PATH)
    p.set(p.game_state(), DIFFICULTY_VAR, difficulty)
    p.set(health, "Health", START_HEALTH)
    p.set(survival, "Hunger", START_HUNGER)
    hunger_before = p.get(survival, "Hunger")
    p.send_event(pawn, CONSUME_EVENT_TAG, optional_object=p.actor_of(MUSHROOM_CLASS_PATH))
    yield SETTLE
    return p.get(health, "Health"), hunger_before, p.get(survival, "Hunger")


def probe(p):
    healed, hunger_before, hunger_after = yield from _eat(p, EASY)
    p.check("on EASY a mushroom heals 10",
            healed == START_HEALTH + MUSHROOM_HEALTH_EASY,
            f"health {START_HEALTH} -> {healed}")
    p.check("on EASY eating refills hunger", hunger_after > hunger_before,
            f"hunger {hunger_before:.2f} -> {hunger_after:.2f}")

    healed, hunger_before, hunger_after = yield from _eat(p, MEDIUM)
    p.check("on MEDIUM a mushroom does not heal", healed == START_HEALTH,
            f"health {START_HEALTH} -> {healed}")
    p.check("on MEDIUM eating still refills hunger", hunger_after > hunger_before,
            f"hunger {hunger_before:.2f} -> {hunger_after:.2f}")
