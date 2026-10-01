"""loot -- corpse loot: what a killed wanderer carries, and the tables that decide it.

A counted kill (DamagedByPlayer) rolls every entry of the body's loot table
once; what hits goes into the body's Loot. Any body can be searched: the HUD's
loot window shows what it carries as icons and takes an item into the bag,
the player kneeling meanwhile (graphics_menu/loot_*.py). The gun drop, which
lands on the ground instead, is combat/gun_drop.py. Rules: loot/CLAUDE.md.

  consts   the health component's loot variable names (table and body arrays:
           class, name, icon, tint) and the search radius --
           constants only, naming no item, so combat can import it
  tables   the loot tables (LootEntry: item Blueprint, chance) -- constants only
  roll     BP_HealthComponent: declaring the loot variables, and the roll
           spliced after the gun drop (called from combat/death.py)
  install  writing the tables onto BP_HealthComponent's defaults; run by
           build_survival.py, once every item a table names exists

Checks: combat/verify/loot.py (the roll), survival/verify/loot.py (the filled
table), graphics_menu/loot_checks.py (the window), probes/probe_corpse_loot.py
(all of it, in a running game).
"""
