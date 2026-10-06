"""Checks for what a landed swing can leave on the player (the on-hit effects:
survival/on_hit.py, rolled by survival/on_hit_graph.py at the end of
npc/melee.py), read back off the saved controllers. Run through
Scripts/verify_npc_blueprints.py.

What it proves, of each creature's BT_Swing: every effect its attack names is
rolled once, against its own chance plus OnHitChanceBonus; only a roll that
lands removes what the player already has of it, tags a fresh spec and
applies it; and a creature whose attack names none has none of that. That a
wendigo's hit makes the player bleed in the game, and what the bleed costs,
is probes/probe_bleeding.py's.
"""

import unreal

from forest_generator.npc_placement import NPC_VARIANTS
from npc.paths import AI_BP_PATH, STEP_SWING
from npc.verify import (
    BEL, _close, _drivers, _exec_reach, _feeders, _ins, _lit, _num, _title,
    check, step_nodes,
)
from survival.on_hit import ON_HIT, ON_HIT_BONUS_VAR, melee_attack, on_hit_effects


def check_settings():
    creatures = {melee_attack(v.key) for v in NPC_VARIANTS}
    melee = {a for a in ON_HIT if a.startswith("melee.")}
    check("on-hit effects: every melee row names a creature", melee <= creatures,
          f"{sorted(melee - creatures)}")
    check("on-hit effects: every chance is a real chance, above 0 and at most 1",
          all(0.0 < e.chance <= 1.0 for row in ON_HIT.values() for e in row))
    wendigo = on_hit_effects(melee_attack("Wendigo"))
    check("on-hit effects: a wendigo's swing makes the player bleed 33% of the time",
          [(e.name, e.chance) for e in wendigo] == [("bleeding", 0.33)], f"{wendigo}")


def check_on_hit(path, key):
    tag = path.rsplit("/", 1)[-1]
    effects = on_hit_effects(melee_attack(key))
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag} exists, for its on-hit effects", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    everything = ed.list_all_nodes()
    own = step_nodes(everything, STEP_SWING)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    bonus = cdo.get_editor_property(ON_HIT_BONUS_VAR)
    check(f"{tag}: {ON_HIT_BONUS_VAR} is the real 0: the chances are as written",
          isinstance(bonus, float) and bonus == 0.0, repr(bonus))

    def of(nodes, *pins, without=()):
        return [n for n in nodes if set(pins) <= _ins(n) and not set(without) & _ins(n)]

    applies = of(everything, "SpecHandle", without=("NewGameplayTag",))
    removes = of(everything, "GameplayEffect", "StacksToRemove")
    if not effects:
        check(f"{tag}: its swing leaves nothing on the player: no effect is "
              f"applied or removed anywhere in the graph",
              not applies and not removes and not of(everything, "GameplayEffectClass"),
              f"{len(applies)} applies, {len(removes)} removes")
        return

    check(f"{tag}: the swing applies {len(effects)} on-hit effect(s), and nothing "
          f"else in the graph applies one",
          len(of(own, "SpecHandle", without=("NewGameplayTag",))) == len(effects)
          and len(applies) == len(effects), f"{len(applies)} applies")
    for e in effects:
        specs = [n for n in of(own, "GameplayEffectClass")
                 if _lit(n, "GameplayEffectClass") == e.effect_class]
        check(f"{tag}: {e.name}: one spec is made of {e.effect_class.rsplit('.', 1)[-1]}",
              len(specs) == 1, f"{len(specs)}")
        if len(specs) != 1:
            continue
        # The chain the spec's handle runs down: each tag, then the apply.
        chain, at = [], specs[0]
        while True:
            nxt = [n for n in of(own, "SpecHandle") if at in _feeders(n, "SpecHandle")]
            if len(nxt) != 1:
                break
            chain.append(nxt[0])
            at = nxt[0]
        granted = [_lit(n, "NewGameplayTag") for n in chain if "NewGameplayTag" in _ins(n)]
        ends = bool(chain) and "NewGameplayTag" not in _ins(chain[-1])
        check(f"{tag}: {e.name}: the spec is given {', '.join(e.tags)} and then "
              f"applied to the player's ability system",
              granted == [f'(TagName="{t}")' for t in e.tags] and ends, f"{granted}")
        if not ends:
            continue
        mine = [n for n in removes if _lit(n, "GameplayEffect") == e.effect_class]
        check(f"{tag}: {e.name}: what the player already has of it is removed "
              f"first, every stack, so a second wound restarts it and never doubles it",
              len(mine) == 1 and _lit(mine[0], "StacksToRemove") == "-1"
              and chain[-1] in _exec_reach(mine[0]), f"{len(mine)} removes")
        if len(mine) != 1:
            continue
        rolls = [n for n in _drivers(mine[0]) if "Condition" in _ins(n)]
        check(f"{tag}: {e.name}: only a roll that lands does any of it",
              len(rolls) == 1 and len(_drivers(mine[0])) == 1, f"{len(rolls)} branches")
        if len(rolls) != 1:
            continue
        gates = _drivers(rolls[0])
        asked = [f for g in gates if "Condition" in _ins(g)
                 for f in _feeders(g, "Condition")]
        # The first effect's roll hangs off the gate; a later one off the first.
        if e is effects[0]:
            check(f"{tag}: the rolls are the server's: they run only off a Branch "
                  f"on HasAuthority of the target, and a client rolls nothing",
                  len(gates) == 1 and len(asked) == 1
                  and "".join(_title(asked[0]).split()) == "HasAuthority",
                  f"{[_title(f) for f in asked]}")
        under = _feeders(rolls[0], "Condition")
        draws = [d for u in under for d in _feeders(u, "A")]
        odds = [d for u in under for d in _feeders(u, "B")]
        check(f"{tag}: {e.name}: the roll is a random 0..1 under "
              f"{e.chance:g} + {ON_HIT_BONUS_VAR}",
              len(under) == 1 and _title(under[0]) == "float < float"
              and len(draws) == 1 and {"Min", "Max"} <= _ins(draws[0])
              and _close(_num(draws[0], "Min") or 0.0, 0.0)
              and _close(_num(draws[0], "Max"), 1.0)
              and len(odds) == 1 and _close(_num(odds[0], "B"), e.chance)
              and [_title(f) for f in _feeders(odds[0], "A")]
              == [f"Get {ON_HIT_BONUS_VAR}"],
              f"{[_title(u) for u in under]}, {[_title(d) for d in draws]}, "
              f"{[_num(o, 'B') for o in odds]}")


def run():
    check_settings()
    check_on_hit(AI_BP_PATH, NPC_VARIANTS[0].key)
    for variant in NPC_VARIANTS:
        check_on_hit(variant.ai_blueprint, variant.key)
