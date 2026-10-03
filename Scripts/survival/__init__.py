"""survival -- hunger, thirst and temperature; food and water; debuffs.

Entry point: Scripts/build_survival.py (main() calls the build_* functions in
dependency order), run AFTER build_weapons_and_combat.py: the consumables are
children of combat's BP_WeaponItem. Checks: Scripts/verify_survival.py, which
runs the survival.verify package. Forage is placed into the levels by
Scripts/place_forage.py; the icons are rendered from the models by
Scripts/build_item_icons.py (the item_icons package).

THE STANDARD PIECES (Gameplay Ability System, plugin GameplayAbilities)
  An AbilitySystemComponent on the player and on every wanderer.
  A debuff is an infinite GameplayEffect (GE_Starving, GE_Dehydrated) whose
  gameplay tags (Debuff.*) are what everything else asks about. One that
  wears off is a GameplayEffect with a duration (GE_Bleeding), put on by a
  hit: the on-hit effects.
  Eating/drinking is a GameplayAbility (GA_ConsumeItem) triggered by the
  gameplay event Event.Item.Consume, which the weapon component sends when the
  fire key is pressed with a Consumable in hand.
  The one non-GAS piece is the stats themselves: an AttributeSet can only be
  declared in C++, so Hunger/Thirst/Temperature are Blueprint variables on
  BP_SurvivalComponent. Tags live in Config/DefaultGameplayTags.ini.

DATA (no Blueprint authoring)
  paths             /Game/Survival asset and class paths, component names
  component_vars    BP_SurvivalComponent's member variables, named once
  tuning            SurvivalConfig / SURVIVAL, restores (and the EASY heal),
                    debuff tags, forage
  consumable_specs  the mushroom and the canteen: parts, grip part, colours, restores
  forage_placement  where forage goes in a level (pure Python, seeded)
  on_hit            the on-hit effects: which attack can leave which effect on
                    its target, and how likely (a wendigo's swing: bleeding, 33%)

BUILDERS
  effects           GE_Starving, GE_Dehydrated (and why their tags are on the
                    spec); GE_Bleeding, which lasts 3 minutes
  on_hit_graph      _author_on_hit: the roll, per effect, and the apply. A
                    fragment for any graph that lands a hit (npc/melee.py)
  consumables       materials, BP_ConsumableItem, BP_Mushroom, BP_WaterCanteen
  debuffs           _author_debuff_sync: apply/remove a debuff GE at zero
  survival_component  BP_SurvivalComponent: decay, grant the ability, debuffs
  consume_ability   GA_ConsumeItem
  easy_heal         GA_ConsumeItem's heal: HealthRestoreEasy onto Health, EASY only
  campfire          BP_Campfire: what the matches light; its Tick warms a player
                    within its radius. Also writes it onto the weapon
                    component's CampfireClass
  install           the ability system + survival component onto the characters
  forage_level      putting the forage into a level, in the editor

Elsewhere, because they belong to what they extend: the use event is sent by
combat/weapon_component/consume.py, the matches and their strike are
combat/matches.py and combat/weapon_component/light.py, the HP drain is combat/debuff_drain.py,
and the bars are graphics_menu/survival_bars.py.

Dependency direction: survival imports combat, never the reverse (combat only
knows the tag names and the bleed's numbers, in combat.tuning). npc imports
survival's on_hit and on_hit_graph; survival never imports npc.
"""
