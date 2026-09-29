"""survival.verify -- reads the saved survival assets back and checks them.

Run through Scripts/verify_survival.py, which calls each module's run() in
SECTIONS order. Uses combat.verify.common's check() ledger and graph readers,
so the two suites read the same way.

  tags          the config declares every tag; the engine knows them
  items         BP_ConsumableItem, the mushroom and the canteen
  debuffs       the two GameplayEffects, and the survival component's sync
  ability       GA_ConsumeItem: trigger, instancing, graph
  hooks         the combat side: the use event, the HP drain, the inventory size
  install       ability systems and the survival component on the characters
  forage        what place_forage.py put in each generated level
"""

SECTIONS = ("tags", "items", "debuffs", "ability", "hooks", "install", "forage")
