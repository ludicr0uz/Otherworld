"""Survival numbers: hunger/thirst/temperature, how fast they fall, what
food and water restore, the debuff tags, and how much forage a level gets.
Numbers only -- the graphs that read them live elsewhere.

The same rule as combat/tuning.py applies: every number here is a pin literal
or a CDO default baked in by a builder, so change it here and re-run
build_survival.py. There is no in-editor copy to drift out of step.
"""

import dataclasses

# The drain itself is a health concept, so its tag and rate live with the
# health component in combat.tuning; the debuffs here only have to grant it.
from combat.tuning import HEALTH_DRAIN_TAG


@dataclasses.dataclass(frozen=True)
class SurvivalConfig:
    # All three bars run 0..max. Temperature is on the same 0..100 scale --
    # 100 is comfortably warm. The night lowers it (BP_DayNightCycle writes
    # it: world/night_cold.py, the rate in world/world_config.py) and a
    # campfire raises it (campfire.py, CAMPFIRE_* below); nothing reads it yet.
    max_hunger: float = 100.0
    max_thirst: float = 100.0
    max_temperature: float = 100.0
    start_temperature: float = 100.0
    # Points per second. Full to empty in 15 minutes of hunger and 10 of
    # thirst: water is the more urgent of the two, which is what makes the
    # canteens worth detouring for.
    hunger_decay_per_s: float = 100.0 / (15 * 60)
    thirst_decay_per_s: float = 100.0 / (10 * 60)


SURVIVAL = SurvivalConfig()

# What one of each restores. A mushroom is a snack and a canteen is a proper
# drink: four mushrooms fill an empty stomach, two and a half canteens an
# empty throat.
MUSHROOM_HUNGER = 25.0
MUSHROOM_THIRST = 0.0
CANTEEN_HUNGER = 0.0
CANTEEN_THIRST = 40.0
# Health a use gives back, on the EASY difficulty only (combat.difficulty);
# on MEDIUM and SURVIVOR food is food. GA_ConsumeItem reads the GameMode's
# Difficulty, so this is the item's number and the ability decides whether it
# applies.
MUSHROOM_HEALTH_EASY = 10.0
CANTEEN_HEALTH_EASY = 0.0

# A campfire (campfire.py), lit by the matches with a piece of wood. Standing
# within the radius raises Temperature by the rate, ten times what the night
# takes (world_config.NIGHT_TEMPERATURE_DROP_PER_S), so a cold player is warm
# again well inside one fire. One piece of wood burns this long, then the
# fire is gone.
CAMPFIRE_WARM_RADIUS_CM = 400.0
CAMPFIRE_WARM_PER_S = 1.0
CAMPFIRE_BURN_S = 180.0

# The debuffs, as gameplay tags (declared in Config/DefaultGameplayTags.ini).
# Each debuff grants its own tag, so the HUD can name it, plus the shared
# HEALTH_DRAIN_TAG, whose stack count BP_HealthComponent drains HP by -- so
# starving AND dehydrated drains twice as fast as either alone.
STARVING_TAG = "Debuff.Starving"
DEHYDRATED_TAG = "Debuff.Dehydrated"

# (stat variable, GameplayEffect default variable on the component, tags)
DEBUFFS = (
    ("Hunger", "StarvingEffect", (STARVING_TAG, HEALTH_DRAIN_TAG)),
    ("Thirst", "DehydratedEffect", (DEHYDRATED_TAG, HEALTH_DRAIN_TAG)),
)

# Forage, placed into a level by Scripts/place_forage.py. Per hectare, so a
# 200 m map (4 ha) gets 24 mushrooms and 6 canteens, with a cap so the 1 km
# map (100 ha) does not carry a thousand pickups.
MUSHROOMS_PER_HECTARE = 6.0
CANTEENS_PER_HECTARE = 1.5
MAX_MUSHROOMS = 300
MAX_CANTEENS = 80
# Mushrooms grow at the foot of trees: this far from a trunk's centre.
MUSHROOM_TRUNK_RING_CM = (70.0, 220.0)
# Everything stays this far inside the terrain's edge, clear of the rim.
FORAGE_EDGE_MARGIN_CM = 1500.0
# And this far from the player's start, so the first one is a find.
FORAGE_START_CLEAR_CM = 1200.0
# Nothing within this of anything else placed.
FORAGE_MIN_SPACING_CM = 300.0
FORAGE_SEED = 7
