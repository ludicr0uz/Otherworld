"""GE_Starving / GE_Dehydrated, and BP_SurvivalComponent's decay and sync."""

import unreal

from combat.verify.common import by_pins, cdo, check, graph, load, pin_value
from survival.effects import DEBUFF_EFFECT_PATHS
from survival.paths import CONSUME_ABILITY_PATH, SURVIVAL_BP_PATH
from survival.tuning import DEBUFFS, SURVIVAL


def run():
    for var, path in DEBUFF_EFFECT_PATHS.items():
        ge = load(path)
        check(f"{path} exists", ge is not None)
        if ge:
            check(f"{path} is infinite: on until removed",
                  cdo(ge).get_editor_property("duration_policy")
                  == unreal.GameplayEffectDurationType.INFINITE)

    bp = load(SURVIVAL_BP_PATH)
    check("BP_SurvivalComponent exists", bp is not None)
    if not bp:
        return
    d = cdo(bp)
    for var, want in (("Hunger", SURVIVAL.max_hunger), ("MaxHunger", SURVIVAL.max_hunger),
                      ("Thirst", SURVIVAL.max_thirst), ("MaxThirst", SURVIVAL.max_thirst),
                      ("Temperature", SURVIVAL.start_temperature),
                      ("MaxTemperature", SURVIVAL.max_temperature),
                      ("HungerDecay", SURVIVAL.hunger_decay_per_s),
                      ("ThirstDecay", SURVIVAL.thirst_decay_per_s)):
        got = d.get_editor_property(var)
        # isinstance: a "float" declared the wrong way compiles as an int, and
        # a decay of 0.111 per second would then be zero.
        check(f"{var} is the float {want:.4f}",
              isinstance(got, float) and abs(got - want) < 1e-6, repr(got))
    check("hunger and thirst both fall", SURVIVAL.hunger_decay_per_s > 0
          and SURVIVAL.thirst_decay_per_s > 0)
    for var, path in DEBUFF_EFFECT_PATHS.items():
        cls = d.get_editor_property(var)
        check(f"{var} names {path}",
              cls is not None and cls.get_path_name().startswith(path + "."),
              str(cls))
    ability = d.get_editor_property("ConsumeAbility")
    check("ConsumeAbility names GA_ConsumeItem", ability is not None and
          ability.get_path_name().startswith(CONSUME_ABILITY_PATH + "."), str(ability))

    nodes = graph(bp).list_all_nodes()
    grants = by_pins(nodes, "SpecHandle", "NewGameplayTag")
    granted = sorted(pin_value(n, "NewGameplayTag") for n in grants)
    want = sorted(f'(TagName="{t}")' for _s, _e, tags in DEBUFFS for t in tags)
    check("each debuff's spec is given its tags before it is applied",
          granted == want, f"{granted} vs {want}")
    applies = by_pins(nodes, "SpecHandle")
    applies = [n for n in applies if "NewGameplayTag" not in {
        str(unreal.BlueprintGraphPinLibrary.get_pin_name(p))
        for p in unreal.BlueprintEditorLibrary.list_input_pins(n)}]
    check(f"{len(DEBUFFS)} debuffs are applied to self", len(applies) == len(DEBUFFS),
          str(len(applies)))
    removes = by_pins(nodes, "GameplayEffect", "StacksToRemove")
    check(f"{len(DEBUFFS)} debuffs are removed, every stack",
          len(removes) == len(DEBUFFS)
          and all(pin_value(n, "StacksToRemove") == "-1" for n in removes))
    counts = by_pins(nodes, "SourceGameplayEffect")
    check("whether a debuff is on is asked of the ability system, per debuff",
          len(counts) == len(DEBUFFS), str(len(counts)))
    gives = by_pins(nodes, "AbilityClass", "InputID")
    check("BeginPlay grants the consume ability once", len(gives) == 1)
    clamps = by_pins(nodes, "Value", "Min", "Max")
    check("hunger and thirst are clamped as they fall", len(clamps) == 2, str(len(clamps)))
