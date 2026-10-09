"""BP_SurvivalComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
STATS, TABLE and LINKS, in that order (the order they have always been
declared in).
"""

from uebp.vars import FLOAT, REPLICATED, Var, cls, obj
from survival.paths import ASC_COMPONENT
from survival.tuning import DEBUFFS, SURVIVAL

# The three needs, each with its ceiling. Replicated to their owner alone
# (survival_component.REPLICATED).
Hunger = Var("Hunger", FLOAT, SURVIVAL.max_hunger, rep=REPLICATED)
MaxHunger = Var("MaxHunger", FLOAT, SURVIVAL.max_hunger)
Thirst = Var("Thirst", FLOAT, SURVIVAL.max_thirst, rep=REPLICATED)
MaxThirst = Var("MaxThirst", FLOAT, SURVIVAL.max_thirst)
Temperature = Var("Temperature", FLOAT, SURVIVAL.start_temperature, rep=REPLICATED)
MaxTemperature = Var("MaxTemperature", FLOAT, SURVIVAL.max_temperature)
STATS = (Hunger, MaxHunger, Thirst, MaxThirst, Temperature, MaxTemperature)

HungerDecay = Var("HungerDecay", FLOAT, SURVIVAL.hunger_decay_per_s)
ThirstDecay = Var("ThirstDecay", FLOAT, SURVIVAL.thirst_decay_per_s)
ConsumeAbility = Var("ConsumeAbility", cls("/Script/GameplayAbilities.GameplayAbility"))
TABLE = (HungerDecay, ThirstDecay, ConsumeAbility)

# The owner's ability system, found at BeginPlay, and one GameplayEffect class
# per DEBUFFS row. ConsumeAbility and the effects are written by
# build_survival.py, once those assets exist.
AbilitySystem = Var(ASC_COMPONENT, obj("/Script/GameplayAbilities.AbilitySystemComponent"))
EFFECTS = tuple(Var(effect_var, cls("/Script/GameplayAbilities.GameplayEffect"))
                for _stat, effect_var, _tags in DEBUFFS)
LINKS = (AbilitySystem, *EFFECTS)
