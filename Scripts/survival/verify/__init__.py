"""survival.verify -- reads the saved survival assets back and checks them.

Run through Scripts/verify_survival.py, which calls each module's run() in
SECTIONS order. Uses combat.verify.common's check() ledger and graph readers,
so the two suites read the same way.

  tags          the config declares every tag; the engine knows them
  items         BP_ConsumableItem, the mushroom and the canteen
  debuffs       the two GameplayEffects, and the survival component's sync
  bleeding      GE_Bleeding: its duration, its cost, and the on-hit table's assets
  ability       GA_ConsumeItem: trigger, instancing, graph
  hooks         the combat side: the use event, the HP drain, the inventory size
  install       ability systems and the survival component on the characters
  forage        what place_forage.py put in each generated level
  loot          the corpse loot table written onto BP_HealthComponent
  campfire      BP_Campfire: the model, the burn time, the warmth; and
                BP_WeaponComponent.CampfireClass pointing at it
  server        M26: the stats replicate to their owner, the components
                replicate on the player, every write is behind authority,
                and GA_ConsumeItem is server only
  var_tables    each Blueprint's variables against its table (uebp/verify_vars.py)
"""

SECTIONS = ("tags", "items", "debuffs", "bleeding", "ability", "hooks", "install", "forage", "loot",
            "campfire", "server", "var_tables")
