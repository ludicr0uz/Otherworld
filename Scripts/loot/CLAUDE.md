# Corpse loot

A wanderer killed by the player may carry things; the player searches the body with **Tab**,
kneeling over it. **Every body can be searched**, whether it carries anything or not: the
player finds out by looking.
The code is this package (`__init__.py` is the map) plus the HUD's `graphics_menu/loot_*.py`.

## The data

- **A loot table is a row list in `tables.py`:** `LootEntry(item_bp, chance)`. Each entry is
  rolled on its own, once per counted kill, so a body can carry several things or nothing.
  Today: `WANDERER_LOOT` = the canteen (water) at 50%.
- **It lives on `BP_HealthComponent`'s defaults** as parallel arrays (`LootTable`,
  `LootChances`, `LootTableNames`, `LootTableIcons`, `LootTableTints`), because Python can't
  author a Blueprint struct. The name, icon and tint are the item's own `DisplayName`, `Icon`
  and `SlotColor`, copied at install: a body holds classes, and a class of Actor has no `Icon`
  to read in a graph. `consts.LOOT_ARRAYS` pairs each table array with the body's.
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
- `RandomFloat < LootChances[i]` → `Loot += LootTable[i]`, and the same for `LootNames`,
  `LootIcons` and `LootTints`. `RandomFloat` is pure, so the Branch is its one reader.
- **A body holds classes, not actors.** The item is spawned only when taken, so nothing hidden
  is left over when the corpse's 60 s lifespan ends. The loot goes with the corpse.

## The window (`graphics_menu/loot_tick.py`, `loot_find.py`, `loot_take.py`, `loot_draw.py`)

- **Every HUD Tick** finds `LootTarget`: the nearest dead Character other than the player,
  within `LOOT_RADIUS` (250 cm) of the player, **measured to the mesh**: the capsule stays
  where the wanderer died, the ragdoll is what the player walks to. A dead player is the
  nearest body to itself, hence the pawn test.
- **Keys** (fixed, not binds): **Tab** opens and closes, **Up/Down** pick, **Enter** takes.
  The mouse cursor shows with the window: the row under it is picked, and a click takes
  (`graphics_menu/cursor.py`; DrawHUD raises the same `LootSel` / `LootTakeRequested`).
  E stays the pick-up: a dropped gun lies beside the body, and E on it must not also empty it.
  The keys only raise `LootOpen` / `LootTakeRequested`; Tick serves them, which is what lets
  a probe drive the window.
- **Taking** spawns the class at the pawn, `Dropped = false`, `Inventory += it`,
  `NeedsRefresh` (as the dev-all-guns cheat does), then removes the row from every body array.
  Only while the bag has room (`LootBagFull`, which the window shows as BAG FULL) and the body
  has something (`Loot[LootSel]` of an empty array is never read).
- **Out of reach, or the body gone,** loses the target, which shuts the window. An emptied
  body stays the target: the window stays open and says NOTHING (`LootEmpty`).
- **The view:** `WBP_HUD`'s `LootPrompt` (under the reticle) and `LootPanel` (right edge,
  `LOOT_ROWS` = 6 `WBP_MenuRow`s), written by DrawHUD from those variables. **A row is the
  item's icon, not its name:** `WBP_MenuRow.Icon` (collapsed in every other menu) gets
  `LootIcons[i]` as its brush and `LootTints[i]` as its tint, exactly as an inventory slot
  draws the item.

## The kneel (`graphics_menu/loot_kneel.py`, `combat/stance_clips.py`)

- **While the window is open the player kneels** and cannot walk. The HUD writes the weapon
  component's `Searching = LootOpen` every Tick and, on `LootOpen`'s edges only,
  `SetIgnoreMoveInput` (it counts its calls; `LootKneeling` is the edge's memory).
- **The pose is a clip blended in the AnimGraph, not a montage.** Montages stop each other per
  group, and every slot here is in one group (`combat/hit_reaction.py`): a kneel montage and
  the gun's ready pose would stop each other every frame. `pose_weights.py` eases the anim
  BP's `PoseKneel` from `Searching`, and `stance_clips.py` blends in the UAL's
  `Fixing_Kneeling`, under the aim layer: empty hands rummage, a held gun stays held.
- **The clip kneels, works and stands again,** so it is evaluated, not played: `KneelTime`
  runs up and back down its working stretch (1.0–3.9 s). `PoseKneel`'s ease is what kneels
  and stands.
- **A prone player searches lying down** (the crawl's hip lift would lift a kneel too). On the
  mannequin fallback there is no clip and the search is made standing.

## Checks

- `verify_weapons_and_combat.py`: `combat/verify/loot.py` (the roll's graph and guard),
  `verify/stance_clips.py` (the kneel blend and clip), `verify/body_pose.py` (`PoseKneel`,
  `KneelTime`).
- `verify_survival.py` (`survival/verify/loot.py`): the table as written, icons and tints too.
- `verify_graphics_menu.py` (`graphics_menu/loot_checks.py`): the window's graph and widgets,
  the icon row, `Searching` and the move-input edge.
  `dev_guns_checks._looting` keeps the take's nodes out of the cheat's counts.
- `uepy.py --game --probe Scripts/probes/probe_corpse_loot.py`: forced unlucky, lucky and
  unearned kills, each body found, the drawn window (NOTHING, or the icon), a take, and the
  kneel (the hips down, move input ignored, standing again). It steps the player up to where
  each ragdoll came to rest: one can slide out of reach down a slope.

## Still needs a play session

- the Tab / Up / Down / Enter keys themselves (a probe has no keyboard);
- how the prompt and the panel read on a real window, and whether 250 cm to a ragdoll feels right;
- the kneel in motion: half a second down and up, the hands working over 2.9 s and back; with
  a gun in hand only the legs and hips kneel. The kneeling knee's joint sits 4 cm under the
  ground on the adventurer. Jump, crouch and prone keys are not held back while kneeling.
