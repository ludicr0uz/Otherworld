"""survival -- hunger, thirst and temperature; food and water; debuffs.

Entry point: Scripts/build_survival.py (main() calls the build_* functions in
dependency order), run AFTER build_weapons_and_combat.py: the consumables are
children of combat's BP_WeaponItem. Checks: Scripts/verify_survival.py, which
runs the survival.verify package. Forage is placed into the levels by
Scripts/place_forage.py; the icons are drawn by Scripts/build_survival_icons.py.

THE STANDARD PIECES (Gameplay Ability System, plugin GameplayAbilities)
  An AbilitySystemComponent on the player and on every wanderer.
  A debuff is an infinite GameplayEffect (GE_Starving, GE_Dehydrated) whose
  gameplay tags (Debuff.*) are what everything else asks about.
  Eating/drinking is a GameplayAbility (GA_ConsumeItem) triggered by the
  gameplay event Event.Item.Consume, which the weapon component sends when the
  fire key is pressed with a Consumable in hand.
  The one non-GAS piece is the stats themselves: an AttributeSet can only be
  declared in C++, so Hunger/Thirst/Temperature are Blueprint variables on
  BP_SurvivalComponent. Tags live in Config/DefaultGameplayTags.ini.

DATA (no Blueprint authoring)
  paths             /Game/Survival asset and class paths, component names
  tuning            SurvivalConfig / SURVIVAL, restores, debuff tags, forage
  consumable_specs  the mushroom and the canteen: parts, grip part, colours, restores
  forage_placement  where forage goes in a level (pure Python, seeded)

BUILDERS
  effects           GE_Starving, GE_Dehydrated (and why their tags are on the spec)
  consumables       materials, BP_ConsumableItem, BP_Mushroom, BP_WaterCanteen
  debuffs           _author_debuff_sync: apply/remove a debuff GE at zero
  survival_component  BP_SurvivalComponent: decay, grant the ability, debuffs
  consume_ability   GA_ConsumeItem
  install           the ability system + survival component onto the characters
  forage_level      putting the forage into a level, in the editor
  icon_art          the two inventory icons (Pillow, outside the editor)

Elsewhere, because they belong to what they extend: the use event is sent by
combat/weapon_component/consume.py, the HP drain is combat/debuff_drain.py,
and the bars are graphics_menu/survival_bars.py.

Dependency direction: survival imports combat, never the reverse (combat only
knows the two tag names, in combat.tuning).
"""
