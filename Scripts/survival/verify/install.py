"""The ability system on both characters, the survival component on the player."""

import unreal

from combat.paths import CHARACTER_BP_PATH, NPC_BP_PATH
from combat.verify.common import BEL, check, component_template, components, load
from survival.paths import ASC_COMPONENT, SURVIVAL_BP_PATH, SURVIVAL_COMPONENT


def run():
    player, npc = load(CHARACTER_BP_PATH), load(NPC_BP_PATH)
    survival_cls = BEL.generated_class(load(SURVIVAL_BP_PATH))
    for name, bp in (("player", player), ("wanderer", npc)):
        comps = components(bp)
        check(f"the {name} has one {ASC_COMPONENT}", comps.count(ASC_COMPONENT) == 1,
              str(comps))
        t = component_template(bp, ASC_COMPONENT)
        check("...and it is an AbilitySystemComponent",
              isinstance(t, unreal.AbilitySystemComponent), str(type(t)))
    check("the player has one SurvivalComponent",
          components(player).count(SURVIVAL_COMPONENT) == 1)
    t = component_template(player, SURVIVAL_COMPONENT)
    check("...of class BP_SurvivalComponent",
          t is not None and t.get_class() == survival_cls)
    check("the wanderer does not get hungry",
          SURVIVAL_COMPONENT not in components(npc))
    # Still there after survival's install: the two installers share a Blueprint.
    check("combat's components survived the survival install",
          {"HealthComponent", "WeaponComponent"} <= set(components(player)))
