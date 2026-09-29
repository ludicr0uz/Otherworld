# Survival: hunger, thirst, food, water and debuffs

`Scripts/build_survival.py` builds `/Game/Survival` and installs it. `Scripts/verify_survival.py`
reads it back. The code is this package (`__init__.py` is the map).

## Build order

Run it after `build_weapons_and_combat.py` and before `build_graphics_menu.py`:

```bash
python3 Scripts/build_survival_icons.py      # Pillow, outside the editor
python3 Scripts/dev/uepy.py Scripts/asset_pipeline/import_ui_art.py Scripts/build_weapons_and_combat.py \
    Scripts/build_survival.py Scripts/build_graphics_menu.py Scripts/place_forage.py
python3 Scripts/dev/uepy.py Scripts/verify_survival.py
```

## It is the Gameplay Ability System

The plugin is enabled in the `.uproject` and the tags are in `Config/DefaultGameplayTags.ini`.
Both are read at editor **startup**, so changing either needs a restart.

| piece | what it is |
|---|---|
| `AbilitySystem` component | A stock ASC on the player **and** the wanderer. It initialises itself, and `GetAbilitySystemComponent(Actor)` finds it without the C++ interface. |
| `GE_Starving`, `GE_Dehydrated` | **Infinite** GameplayEffects. |
| `Debuff.Starving` / `.Dehydrated` / `.HealthDrain` | The HUD names a debuff from the first two tags. `combat/debuff_drain.py` drains 0.5 HP/s per stack of the third, so both debuffs together drain twice as fast. |
| `GA_ConsumeItem` | Triggered by the gameplay event `Event.Item.Consume`. The payload's `OptionalObject` is the item. Instanced per actor. |
| `BP_SurvivalComponent` | Hunger/Thirst/Temperature as Blueprint floats, because an AttributeSet needs C++. Also their decay, the ability grant at BeginPlay, and the debuff sync. |

## The flow

1. The player presses fire while holding a `Consumable`.
2. `combat/weapon_component/consume.py` sends the event, **then** removes and destroys the item.
   The ability runs synchronously and reads the item first.
3. `GA_ConsumeItem` adds the restore value, clamped.
4. On the next Tick, the survival component sees that the bar and the effect disagree, and
   removes the effect.

The debuff sync is the only place that decides a debuff is on, and it asks the ASC
(`GetGameplayEffectCount`). combat never names a survival asset, only the two tags in
`combat/tuning.py`.

## Items

- **Consumables are weapons:** `BP_ConsumableItem` is a child of `BP_WeaponItem`, with
  `Consumable = True` on the base. E, G, Q and the strip therefore work unchanged.
- **They default to `Dropped = True`.** They use the pistol's pose, and there is no eating
  animation.

## Numbers and placement (`tuning.py`)

- **Rates:**
  - Hunger empties in 15 min and thirst in 10.
  - A mushroom restores +25 hunger and a canteen +40 thirst.
  - Temperature is a 0–100 bar that nothing moves yet.
- **Where forage goes:** `scatter_forage` puts mushrooms 0.7–2.2 m from a trunk and canteens
  anywhere.
- **How much:** 6 and 1.5 per hectare, capped at 300 and 80. That is 24 + 6 on the 200 m map and
  300 + 80 on the 1 km map.
- **How it gets into the levels:** `place_forage.py` (tag `OW_Forage`, idempotent). The level
  generator doesn't do it, so re-run `place_forage.py` after any `import_<Level>.py`.

## Gotchas

- **A GameplayEffect's granted tags can't be set from Python.**
  - `TargetTagsGameplayEffectComponent`'s container is private, and the deprecated field is
    upgraded only for pre-5.3 assets.
  - Grant the tags **on the spec** instead:
    `MakeOutgoingSpec` → `AddGrantedTag` ×N → `ApplyGameplayEffectSpecToSelf`.
  - `MakeOutgoingSpec` is pure, so chain each `AddGrantedTag` off the previous return.
- **`AbilityTriggerData` exposes no fields** (`to_tuple()` is `()`), so read it back with
  `export_text()`.
- **Structs like `InheritedTagContainer` refuse `set_editor_property`** but take `import_text`.
- **A level loaded within the same Python call has no terrain collision yet,** because complex
  collision cooks asynchronously and all traces miss.
  - Read heights from the mesh instead (`terrain_heights.py`, via
    `ProceduralMeshLibrary.get_section_from_static_mesh`).
- **`GameplayCueNotifyPaths` in `Config/DefaultGame.ini` points at `/Game/Survival`.** Without it
  the ability system warns and scans all of `/Game`.

## Still needs a play session

These can't be proved headlessly:

- pressing fire with food in hand;
- how the bars and the two-row strip look.
