# Clothing

The player wears eight garments, one per slot: **hat, glasses, shirt, jacket, gloves, pants,
boots, backpack** (`combat/wear_tuning.WEAR_SLOTS`, in that order). Only the state exists:
nothing is drawn on the player when a garment is worn, and wearing one changes no number.

```bash
python3 Scripts/dev/uepy.py Scripts/build_clothing.py      # after build_weapons_and_combat.py
python3 Scripts/dev/uepy.py Scripts/verify_clothing.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_clothing.py
python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_clothing.py
```

## Where each piece lives

| piece | owner |
|---|---|
| the garments (`/Game/Clothing/BP_<Garment>`), their stand-in models and materials | this package (`specs.py`, `items.py`) |
| the test garments on `Lvl_Forest_200m` | this package (`placement.py`) |
| the mesh a garment is drawn as, worn: `Garment.worn` (the body component it fills, the skeletal mesh, from `metahuman_paths.CLOTHING`), written onto the item as `WornPart` and `WornMesh`. Jacket, Pants and Boots have one; data only, nothing reads it yet | `specs.py`, `items.py`; the variables `combat/item_vars.py` |
| the slots, `ClothingSlot` on the item, `Worn`/`TakeOffSlot` on the weapon component | `combat/wear_tuning.py` |
| putting one on, taking one off (the server's: `Scripts/net/CLAUDE.md`, "Clothing") | `combat/weapon_component/wear.py`, `wear_drag.py` (checks: `combat/verify/wear.py`) |
| what is worn, as the owning client is told it and pictures it | the record's `Worn` (`combat/record_vars.py`; C++, read with `WornRow`: `uebp/nodes/inventory.py`), `view_worn.py` |
| the **I** panel, and the character's portrait in it | `graphics_menu/wear_*.py`, `wbp_wear.py` (checks: `graphics_menu/wear_checks.py`); the picture: `item_icons/portrait.py` |
| the icons | `item_icons/items.py` rows, `python3 Scripts/build_item_icons.py Hat ...` |
| the base body in boxers, what the garments will be drawn on | `asset_pipeline/player_body.py` `CLOTHING_BASE_BODY` (a `catalog.py` spec); names in `specs.py` `BASE_BODY_*` (checks: `verify/base_body.py`) |

## The design

- **A garment is a `BP_WeaponItem`**, as food is: the bag is an array of it, so E picks one up
  (into a bag slot), G drops it, a number key or a click brings its slot to hand, V throws
  it and the slots draw it, with no new code. It is
  `Dropped` by default, so a placed one is a pick-up.
- **In the bag until worn.** A pick-up only puts it in a slot of the bag. **Using it wears it:**
  the fire key with it in hand. It is `Consumable` (the fire key uses it instead of firing),
  and its `ClothingSlot` (the slot's index; `NOT_CLOTHING`, -1, on every other item) makes that
  use a wear rather than the GAS eat event (`wear._author_wear_gate`, handed to
  `consume._author_use_gate` by `tick.py`, so consume never imports wear).
- **It is the server's** (task M24). The fire key asks `Server_Wear`, the I panel
  `AskWear` and `AskTakeOff`, all reliable Server events; the server's Tick serves them
  with authority and writes what is worn down in the inventory's record (its `Worn`),
  which goes to the owning client, whose `Worn` is made from it. In single player each is a plain call.
- **A worn garment is the same actor:** out of `Inventory`, into `Worn[slot]`, hidden, its
  inventory `Slot` UNPLACED (`combat/slot_tuning.py`), so taken off it finds a bag slot. Wearing
  one into a filled slot puts the old one back in the bag (there is room: the new one just
  left it). The press is spent (`TriggerSpent`) as eating spends it.
- **`Worn` starts empty and the first wear into a slot grows it** (`Array_Set`, size to fit).
  Every read of it is behind `IsValidIndex`, then `IsValid`.
- **Taking one off is the I panel's**: Up/Down and Enter (or a click) raise the HUD's
  `WearTakeOffRequested`; its Tick calls the weapon component's `AskTakeOff`
  (`Scripts/net/CLAUDE.md`, "A screen asks"), which raises `TakeOffSlot`, and the
  component's own Tick serves it (into the bag while there is room, `HasRoom`: a bag slot
  or the hand free; the slot emptied).
  The HUD never touches the bag.
- **The mouse does both, in the I panel** (`graphics_menu/inv_drag.py` asks,
  `probes/probe_clothing_drag.py` checks): a worn garment dragged onto the hand or a bag
  slot is taken off into it (`TakeOffTo` with `TakeOffSlot`; a filled slot or a weapon
  slot sends it to the bag's first free one), and a carried garment dragged onto the worn
  grid is worn (`WearRequest`, a slot code: `weapon_component/wear_drag.py`), from the bag
  or the hand, into its own slot whichever cell it lands on; one already worn there takes
  the slot it left. A worn garment dragged out of the inventory is set down on the
  ground, as any item is (`DropRequest`: `weapon_component/drop_request.py`).
- **The worn panel** sits bottom right, over the backpack, and both are always shown (the
  menu hides them): one inventory slot per worn slot, in two rows of four, showing the worn
  garment's icon, or the garment's translucent silhouette while nothing is worn there. No
  text. **I** opens the inventory: the caret (a lit slot) runs over the worn slots and
  then the bag, and the mouse drags. It does not pause; the walk is held while it is open (its own `SetIgnoreMoveInput`
  edge, `WearStill`), the cursor shows with it, and with the loot window open as well the
  arrows and Enter are the loot window's.
- **The test garments**: one of each, in a row across the view 3 m in front of
  `Lvl_Forest_200m`'s PlayerStart, 55 cm apart (tag `OW_TestClothing`; `build_clothing.py`
  places them, idempotently, and saves the level). Regenerating the level drops them, as it
  drops the forage: run `build_clothing.py` again.

## Traps

- **No part may be called `Body`:** it is the inherited root the parts hang off, and
  `build_parts` fails clearing it.
- **The fist-fit check is not run on garments:** the fist pose is closed on a handle, and a
  folded shirt has none, so the fingers stand in the cloth.
- **`FireForced` is a held key**, a press on every frame it is up: a probe that leaves it up
  for 0.1 s wears the garment that slides into the hand next, too.
  `probe_clothing._fire` drops it on the frame the item leaves the bag.

## Not done yet

- Nothing is drawn worn, and a worn garment does nothing (no warmth, no carry space).
- **The base body is worn:** the player is `SKM_Adventurer03`, the man in skin-tight
  shorts, generated to swap in for the dressed `SKM_Adventurer01`
  (`asset_pipeline/player_body.py` `PLAYER_BODY` and `CLOTHING_BASE_BODY`;
  `verify/base_body.py` checks it). Garments are not drawn on it yet. Swapping bodies is
  `python3 Scripts/asset_pipeline/swap_player_body.py <id>`
  (`Scripts/asset_pipeline/CLAUDE.md`). `SKM_Adventurer02`, the first try in loose boxers,
  is kept only as test data.
- The saved profile (`graphics_menu/CLAUDE.md`, "Save and exit") stores the bag, not `Worn`:
  what was worn is lost on save and exit.
- No loot table names a garment yet (`Scripts/loot/tables.py`); a looted one would go into
  the bag like any item.
- **Still needs a play session:** the I key and the panel's look, the cursor on its
  slots, dragging a garment on and off, and how the stand-in models read on the ground.
