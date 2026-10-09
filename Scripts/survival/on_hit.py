"""What a landed hit can leave on its target, and how likely: the on-hit
effects, as a table. Data only, no ``unreal`` -- the graph that rolls them is
survival/on_hit_graph.py.

An ATTACK is a name its author picks ("melee.Wendigo"); ON_HIT maps it to the
effects a hit of it rolls, each on its own. To give another attack an effect,
add a row here and have the graph that lands that attack call
``_author_on_hit`` with ``on_hit_effects(<its name>)``: the wanderers' swing
already does (npc/melee.py), for every creature, so a zombie that poisons is
one row.
"""

import dataclasses

from combat.tuning import BLEEDING_TAG
from uebp.vars import FLOAT, Var
from survival.paths import BLEEDING_GE_CLASS_PATH, BLEEDING_GE_PATH


@dataclasses.dataclass(frozen=True)
class OnHitEffect:
    name: str           # as the comments and the checks word it
    effect_path: str    # the GameplayEffect Blueprint...
    effect_class: str   # ...and its class, which is what the spec is made of
    tags: tuple         # granted on the spec (survival/effects.py says why)
    chance: float       # 0..1, rolled once per landed hit


# 50 HP over 3 minutes (combat.tuning.BLEED_*), on one hit in three. A hit
# that rolls it on a target already bleeding starts the 3 minutes again: one
# wound, not two.
BLEEDING = OnHitEffect("bleeding", BLEEDING_GE_PATH, BLEEDING_GE_CLASS_PATH,
                       (BLEEDING_TAG,), 0.33)

ON_HIT = {
    "melee.Wendigo": (BLEEDING,),
}

# A real on the graph that rolls, added to every chance in it. 0 as built; a
# probe writes +1 for "every hit" and -1 for "never" (probes/probe_bleeding.py),
# since a one-in-three roll proves nothing in a short run.
ON_HIT_BONUS_VAR = Var("OnHitChanceBonus", FLOAT)
ON_HIT_TABLE = (ON_HIT_BONUS_VAR,)       # on_hit_graph.declare_on_hit_vars


def melee_attack(creature):
    """The attack name of creature ``creature``'s swing."""
    return f"melee.{creature}"


def on_hit_effects(attack):
    return ON_HIT.get(attack, ())
