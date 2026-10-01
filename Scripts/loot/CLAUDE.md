# Corpse loot

A wanderer killed by the player may carry things; the player searches the body with **Tab**.
The code is this package (`__init__.py` is the map) plus the HUD's `graphics_menu/loot_*.py`.

## The data

- **A loot table is a row list in `tables.py`:** `LootEntry(item_bp, chance)`. Each entry is
  rolled on its own, once per counted kill, so a body can carry several things or nothing.
  Today: `WANDERER_LOOT` = the canteen (water) at 50%.
- **It lives on `BP_HealthComponent`'s defaults** as parallel arrays (`LootTable`,
  `LootChances`, `LootTableNames`), because Python can't author a Blueprint struct. The names
  are the items' own `DisplayName`.
- **`build_survival.py` fills them** (`install.fill_loot_tables`), because it is the last
  builder to make an item. `build_weapons_and_combat.py` re-declares the variables and so
  **empties the table**: re-run `build_survival.py` after it (the documented order). An empty
  table is legal; the roll loops zero times. `verify_survival.py` catches it.
- **One table for every wanderer.** A child Blueprint's override of an inherited component is
  out of Python's reach (`Scripts/npc/CLAUDE.md`); a per-creature table would travel on the AI
  controller, as the hit-reaction clips do.

## The roll (`roll.py`, spliced in `combat/death.py`)

- After the gun drop, on the **`DamagedByPlayer` arm** only, like the shells: the world-floor
  net kills the same way and must not pay out.
- `RandomFloat < LootChances[i]` → `Loot += LootTable[i]`, `LootNames += LootTableNames[i]`.
  `RandomFloat` is pure, so the Branch is its one reader.
- **A body holds classes, not actors.** The item is spawned only when taken, so nothing hidden
  is left over when the corpse's 60 s lifespan ends. The loot goes with the corpse.

## The window (`graphics_menu/loot_tick.py`, `loot_find.py`, `loot_take.py`, `loot_draw.py`)

- **Every HUD Tick** finds `LootTarget`: the nearest dead Character whose health component still
  carries `Loot`, within `LOOT_RADIUS` (250 cm) of the player, **measured to the mesh**: the
  capsule stays where the wanderer died, the ragdoll is what the player walks to.
- **Keys** (fixed, not binds): **Tab** opens and closes, **Up/Down** pick, **Enter** takes.
  The mouse cursor shows with the window: the row under it is picked, and a click takes
  (`graphics_menu/cursor.py`; DrawHUD raises the same `LootSel` / `LootTakeRequested`).
  E stays the pick-up: a dropped gun lies beside the body, and E on it must not also empty it.
  The keys only raise `LootOpen` / `LootTakeRequested`; Tick serves them, which is what lets
  a probe drive the window.
- **Taking** spawns the class at the pawn, `Dropped = false`, `Inventory += it`,
  `NeedsRefresh` (as the dev-all-guns cheat does), then removes the row from the body. Only while
  the bag has room (`LootBagFull`, which the window shows as BAG FULL).
- **Out of reach, or the body emptied or gone,** loses the target, which shuts the window.
- **The view:** `WBP_HUD`'s `LootPrompt` (under the reticle) and `LootPanel` (right edge,
  `LOOT_ROWS` = 6 `WBP_MenuRow`s), written by DrawHUD from those variables.

## Checks

- `verify_weapons_and_combat.py` (`combat/verify/loot.py`): the roll's graph and guard.
- `verify_survival.py` (`survival/verify/loot.py`): the table as written.
- `verify_graphics_menu.py` (`graphics_menu/loot_checks.py`): the window's graph and widgets.
  `dev_guns_checks._looting` keeps the take's nodes out of the cheat's counts.
- `uepy.py --game --probe Scripts/probes/probe_corpse_loot.py`: forced lucky, unlucky and
  unearned kills, the HUD finding the body, the drawn window, and a take.

## Still needs a play session

- the Tab / Up / Down / Enter keys themselves (a probe has no keyboard);
- how the prompt and the panel read on a real window, and whether 250 cm to a ragdoll feels right.
