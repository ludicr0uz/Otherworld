"""BP_SurvivalComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import FLOAT, Var, cls
from survival.tuning import SURVIVAL

HungerDecay = Var("HungerDecay", FLOAT, SURVIVAL.hunger_decay_per_s)
ThirstDecay = Var("ThirstDecay", FLOAT, SURVIVAL.thirst_decay_per_s)
ConsumeAbility = Var("ConsumeAbility", cls("/Script/GameplayAbilities.GameplayAbility"))
Hunger = Var("Hunger")
MaxHunger = Var("MaxHunger")
MaxTemperature = Var("MaxTemperature")
MaxThirst = Var("MaxThirst")
Temperature = Var("Temperature")
Thirst = Var("Thirst")

TABLE = (HungerDecay, ThirstDecay, ConsumeAbility)
