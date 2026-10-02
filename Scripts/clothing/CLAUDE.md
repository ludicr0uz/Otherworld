# Clothing

The player wears eight garments, one per slot: **hat, glasses, shirt, jacket, gloves, pants,
boots, backpack** (`combat/wear_tuning.WEAR_SLOTS`, in that order). Only the state exists:
nothing is drawn on the player when a garment is worn, and wearing one changes no number.

```bash
python3 Scripts/dev/uepy.py Scripts/build_clothing.py      # after build_weapons_and_combat.py
python3 Scripts/dev/uepy.py Scripts/verify_clothing.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_clothing.py
```

## Where each piece lives

| piece | owner |
|---|---|
| the garments (`/Game/Clothing/BP_<Garment>`), their stand-in models and materials | this package (`specs.py`, `items.py`) |
| the test garments on `Lvl_Forest_200m` | this package (`placement.py`) |
| the slots, `ClothingSlot` on the item, `Worn`/`TakeOffSlot` on the weapon component | `combat/wear_tuning.py` |
| putting one on, taking one off | `combat/weapon_component/wear.py` (checks: `combat/verify/wear.py`) |
| the **I** panel | `graphics_menu/wear_*.py`, `wbp_wear.py` (checks: `graphics_menu/wear_checks.py`) |
| the icons | `item_icons/items.py` rows, `python3 Scripts/build_item_icons.py Hat ...` |

## The design

- **A garment is a `BP_WeaponItem`**, as food is: the bag is an array of it, so E picks one up,
  G drops it, Q cycles to it, V throws it and the strip draws it, with no new code. It is
  `Dropped` by default, so a placed one is a pick-up.
- **In the bag until worn.** A pick-up only puts it in a slot of the bag. **Using it wears it:**
  the fire key with it in hand. It is `Consumable` (the fire key uses it instead of firing),
  and its `ClothingSlot` (the slot's index; `NOT_CLOTHING`, -1, on every other item) makes that
  use a wear rather than the GAS eat event (`wear._author_wear_gate`, handed to
  `consume._author_use_gate` by `tick.py`, so consume never imports wear).
- **A worn garment is the same actor:** out of `Inventory`, into `Worn[slot]`, hidden. Wearing
  one into a filled slot puts the old one back in the bag (there is room: the new one just
  left it). The press is spent (`TriggerSpent`) as eating spends it.
- **`Worn` starts empty and the first wear into a slot grows it** (`Array_Set`, size to fit).
  Every read of it is behind `IsValidIndex`, then `IsValid`.
- **Taking one off is the I panel's**: Up/Down and Enter (or a click) raise the HUD's
  `WearTakeOffRequested`; its Tick sets the weapon component's `TakeOffSlot`, and the
  component's own Tick serves it (into the bag while there is room, the slot emptied).
  The HUD never touches the bag.
- **The I panel** sits on the left edge, centred: one row per slot, the worn garment's
  `DisplayName` or `-`. It does not pause; the walk is held while it is open (its own
  `SetIgnoreMoveInput` edge, `WearStill`), the cursor shows with it, and with the loot window
  open as well the arrows and Enter are the loot window's. The menu hides it.
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
- The saved profile (`graphics_menu/CLAUDE.md`, "Save and exit") stores the bag, not `Worn`:
  what was worn is lost on save and exit.
- No loot table names a garment yet (`Scripts/loot/tables.py`); a looted one would go into
  the bag like any item.
- **Still needs a play session:** the I key and the panel's look, the cursor on its rows, and
  how the stand-in models read on the ground.
