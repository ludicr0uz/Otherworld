# Survival: hunger, thirst, food, water and debuffs

`Scripts/build_survival.py` builds `/Game/Survival` and installs it. `Scripts/verify_survival.py`
reads it back. The code is this package (`__init__.py` is the map).

## Build order

Run it after `build_weapons_and_combat.py` and `build_clothing.py` (the corpse loot table
it installs names three garments) and before `build_graphics_menu.py`:

```bash
python3 Scripts/dev/uepy.py Scripts/build_weapons_and_combat.py Scripts/build_clothing.py \
    Scripts/build_survival.py Scripts/build_graphics_menu.py Scripts/place_forage.py
python3 Scripts/dev/uepy.py Scripts/verify_survival.py
```

The mushroom's and the canteen's inventory icons are renders of their models
(`python3 Scripts/build_item_icons.py`, `Scripts/item_icons/CLAUDE.md`).

## It is the Gameplay Ability System

The plugin is enabled in the `.uproject` and the tags are in `Config/DefaultGameplayTags.ini`.
Both are read at editor **startup**, so changing either needs a restart.

| piece | what it is |
|---|---|
| `AbilitySystem` component | A stock ASC on the player **and** the wanderer. It initialises itself, and `GetAbilitySystemComponent(Actor)` finds it without the C++ interface. It replicates (the stock default), so a client is sent the effects the server applies. |
| `GE_Starving`, `GE_Dehydrated` | **Infinite** GameplayEffects. |
| `GE_Bleeding` | A GameplayEffect with a **duration** (180 s): the ability system takes it off. A hit puts it on (below). |
| `Debuff.Starving` / `.Dehydrated` / `.Bleeding` / `.HealthDrain` | The HUD names a debuff from the first three tags. `combat/debuff_drain.py` drains by the rows of `combat.tuning.HEALTH_DRAINS`: 0.5 HP/s per stack of `HealthDrain` (so starving and dehydrated together drain twice as fast) and 50/180 HP/s per stack of `Bleeding`; the rates add up. |
| `GA_ConsumeItem` | Triggered by the gameplay event `Event.Item.Consume`. The payload's `OptionalObject` is the item. Instanced per actor, and run on the server only. |
| `BP_Campfire` | Not GAS: a replicated Actor the matches light (`campfire.py`). Its Tick warms a player near it, on the server. |
| `BP_SurvivalComponent` | Hunger/Thirst/Temperature as Blueprint floats, because an AttributeSet needs C++; replicated to the owning client alone. Also their decay, the ability grant at BeginPlay, and the debuff sync, all three with authority only. |

## The flow

1. The player presses fire while holding a `Consumable`. Their machine plays the item's
   sound, asks `Server_Consume` (a reliable Server event on the weapon component; a plain
   call in single player) and spends the press.
2. `Server_Consume` (`combat/weapon_component/consume.py`), refused unless the server's own
   `Held` is a Consumable that is not a garment, sends the event, **then** removes and
   destroys the item. The ability runs synchronously and reads the item first.
3. `GA_ConsumeItem` adds the restore value, clamped. On the **EASY** difficulty it also adds the
   item's `HealthRestoreEasy` to Health (`easy_heal.py`; a mushroom heals 10). It reads the
   GameState's `Difficulty` (`combat/difficulty.py`, `net/state_consts.py`), which the HUD copies from the settings save.
4. On the next Tick, the survival component sees that the bar and the effect disagree, and
   removes the effect.

The debuff sync is the only place that decides a debuff is on, and it asks the ASC
(`GetGameplayEffectCount`). combat never names a survival asset, only the two tags in
`combat/tuning.py`.

## On a server (M26)

Survival values drive health and death, so the server owns all of them. A client's copy
writes nothing; in single player the one machine has authority and nothing differs.

| what | whose | how a client learns of it |
|---|---|---|
| `Hunger`, `Thirst`, `Temperature` | the server's `BP_SurvivalComponent`; the decay, the night's cold (`world/night_cold.py`) and a campfire's warmth all write behind an authority switch | the component replicates and the three replicate `COND_OWNER_ONLY`: a player's bars are their own, and nobody else's copy of that character is told them |
| the debuffs, the bleed | effects on the server's ability system: the debuff sync, the on-hit fragment and the cauterise are all behind authority | the ability system component replicates its active effects, with the tags granted on their specs, so the HUD's `GetGameplayTagCount` on its own pawn answers as it does in single player. The stock replication mode (Full) is meant to send them to every client the character is relevant to (not measured); nothing reads them off another player yet |
| eating and drinking | `Server_Consume`, then `GA_ConsumeItem` with `NetExecutionPolicy` ServerOnly | the bag is the inventory's record, the bars the stats above; nothing is predicted, so a meal shows a round trip late |
| stamina | the C++ movement component's since M12 (`Source/CLAUDE.md`) | predicted by the owner |
| health | the health component's since M14; the EASY heal is the server's because the ability is | `Health` replicates |

**Where it lives: on the character, not the PlayerState.** Both the ability system and the
survival component are components of `BP_ThirdPersonCharacter`. Why:

- **M16's respawn hands the player a new character,** and wants it fresh: full bars, no
  bleed, no starving. On the pawn that is what a new pawn is, with no reset code; on the
  PlayerState every effect and stat would have to be cleared by hand at each respawn, and
  a missed one (a bleed carried across a death) drains the new body.
- **The body left behind keeps its own state** for the 60 s it lies there, and the health
  component beside it drains by *its owner's* ability system (`combat/debuff_drain.py`).
  Health, the drain and the debuffs staying on one actor is what keeps that a one-line read.
- **A wanderer has no PlayerState** and carries the same ability system for the same
  drain and the same on-hit fragment. One place for both kinds of character.
- **Nothing in Blueprint finds an ability system on a PlayerState from a pawn:**
  `GetAbilitySystemComponent(Actor)` searches the actor's own components unless the
  actor implements `IAbilitySystemInterface`, which is C++, and the avatar/owner split
  (`InitAbilityActorInfo` at every possession) is C++ too.
- **The save does not need it there.** What persists is the numbers, and a save reads
  them off the living character as the single-player profile does
  (`graphics_menu/player_parts.py`); a server-side save (phase 7) can do the same on the
  server's copy and write them back onto the character it spawns at login.

What this costs: a logout or a respawn loses anything not written down first. That is the
intended rule for a respawn; for a logout it is the save's job.

- **Traps:**
  - `GA_ConsumeItem`'s default policy, LocalPredicted, refuses to activate on a server for a
    player who is not local to it (the engine's "Can't activate LocalOnly or LocalPredicted
    ability", read in its source, not reproduced here): the item would be spent and
    nothing restored.
  - A stock `AbilitySystemComponent` replicates by default, the wanderer's too.
    `ReplicationMode` is not a `UPROPERTY`, so Mixed or Minimal cannot be set from Python
    or a class default; it would take a `SetReplicationMode` call in C++.
  - A probe's write of a stat goes on the server. A client's own write stays until the
    server's value next changes, which hunger's and thirst's do every frame and
    `Temperature`'s only at night or by a fire.
- **Checks:** `verify/server.py`; `uepy.py --net --clients 2 --probe
  Scripts/probes/probe_net_survival.py` (client 1 eats and its own hunger rises by 25,
  client 2's does not, and client 2's copy of client 1's character is told none of its
  bars; client 1 is sent the temperature and the dehydrated tag the server gave it), clean
  with `--lag 120`, and its single-player arm with `--game`.
- **Not done here:** the HUD drawing itself was not looked at in a rendered net run (the
  probe reads the same variables and the same tag count the HUD reads); the eating sound
  is heard by the eater alone.

## On-hit effects and bleeding (`on_hit.py`, `on_hit_graph.py`)

- **The table:** `on_hit.ON_HIT` maps an attack's name to the effects a landed hit of it
  rolls, each with its own chance. Today: `"melee.Wendigo"` → bleeding at 33%.
- **The fragment:** `_author_on_hit(ed, exec_in, target, effects)` goes into whatever
  graph lands the hit and takes the target as an actor pin. Per effect: a random 0..1 under
  `chance + OnHitChanceBonus` → remove every stack the target has → spec, tags → apply. It
  returns the exec tails. The wanderers' swing runs it for every creature (`npc/melee.py`), so
  another creature's effect is one `ON_HIT` row and an NPC rebuild; another kind of attack
  calls the fragment with its own name (declare the bonus variable once per graph with
  `declare_on_hit_vars`).
- **Bleeding:** `GE_Bleeding` lasts `BLEED_DURATION_S` (180) and its spec grants
  `Debuff.Bleeding`; the health component drains `BLEED_TOTAL_HP / BLEED_DURATION_S` per
  second while the tag is on (all three in `combat/tuning.py`), which is 50 HP in all. A
  second wound **restarts** the 3 minutes and never stacks. A blocked swing rolls too. It is
  not saved with the profile. One thing stops it early: the use key with a hot knife or axe
  in hand (heated at a campfire) removes it, by the tag
  (`combat/weapon_component/cauterize.py`, `probes/probe_hot_blade.py`).
- **The roll is the server's:** the fragment asks `HasAuthority` of its target before any
  roll (`Scripts/net/CLAUDE.md`, "Random rolls"), so a graph a client also runs can use it.
- **Build order:** the controllers name `GE_Bleeding` on a pin, so `build_npc_blueprints.py`
  runs after `build_survival.py`. Without the asset the swing is built without the roll, and
  the builder says so.
- **`OnHitChanceBonus`** is 0 as built. `probes/probe_bleeding.py` writes -1 and +1 to make
  the roll fail or land, then measures the bleed; `npc/verify_on_hit.py` reads the 33%.
- **A query by tag does not find the effect** (`GetActiveEffectsWithAllTags` returns
  nothing): the tag is granted on the spec. Ask for the tag count or the effect count.
- **A duration is set with `import_text`** on a `GameplayEffectModifierMagnitude`, then
  `set_editor_property("duration_magnitude", …)`; read it back with `export_text()`.

## Items

- **Consumables are weapons:** `BP_ConsumableItem` is a child of `BP_WeaponItem`, with
  `Consumable = True` on the base. E, G, Q and the strip therefore work unchanged.
- **They default to `Dropped = True`.** They are carried in `A_HoldItem`, one hand at the
  waist (`combat/hold_pose.py`), and there is no eating animation.

- **Water is also corpse loot:** `build_survival.py` fills the wanderers' loot table
  (`Scripts/loot/`), a canteen at 50% (and three garments at 10% each, which
  `build_clothing.py` makes first), because it builds the last items the table names.

## The campfire (`campfire.py`)

- **Lit by the matches:** a strike with wood in the bag spawns `BP_Campfire` in front of the
  player (`combat/weapon_component/light.py`). combat holds only a class variable,
  `BP_WeaponComponent.CampfireClass`, which `build_survival.py` writes (`install_campfire`),
  as it fills the loot table.
- **It warms on its own Tick,** as `BP_AmmoPickup` measures its own distance: the player's
  pawn, valid, within `WarmRadius`, then `Temperature = min(Temperature + WarmPerSecond × dt,
  MaxTemperature)` on its survival component. The night's cold writes the same variable
  (`world/night_cold.py`), so the two add up: by a fire the night nets +0.9 a second.
- **It is the server's** (M25, `Scripts/net/CLAUDE.md`, "Fire and heat"): the class
  replicates and only the server spawns one (`Server_Light`), so every client is sent it.
  The warmth and the life span are behind HasAuthority; a client's copy only shows.
- **It burns out:** BeginPlay, with authority, sets a life span of `CAMPFIRE_BURN_S`; the actor is destroyed.
  It is not saved with the profile and blocks nothing (the player walks through it).
- **The model** is Quaternius's `SM_Bonfire_Fire` at 0.4 (87 cm across) with a point light
  that casts no shadows.
- **A stick takes its fire:** the use key with `BP_Stick` in hand, within 3 m of any
  `CampfireClass` actor, lights it (`combat/weapon_component/torch.py`; combat's, and it
  knows the fire only by that class variable).
- **It draws the zombies:** one on patrol within 200 m walks to a burning fire
  (`Scripts/npc/CLAUDE.md`, `npc/drawn.py`; the NPC build names `BP_Campfire`, so it runs
  after this one).
- **It crackles:** `Crackle`, an AudioComponent playing `/Game/Audio/A_Campfire`, a looping
  placed wave (how far and how loud are the wave's: `Scripts/Sound/CLAUDE.md`). On a
  component so that it ends with the fire. The weapons build imports the wave: run it first.
- `probes/probe_campfire.py` cuts wood, strikes, and measures the warmth in and out of the
  radius. It raises the fire's rate for the run and zeroes the night's cold.

## Numbers and placement (`tuning.py`)

- **Rates:**
  - Hunger empties in 15 min and thirst in 10.
  - A mushroom restores +25 hunger and a canteen +40 thirst. On EASY a mushroom also heals 10.
  - Temperature is a 0–100 bar that falls at night: the day/night cycle lowers it
    (`world/night_cold.py`, rate in `world/world_config.py`) and a campfire raises it
    (below). Nothing reads it yet.
  - A campfire warms +1 a second within 4 m and burns 180 s (`CAMPFIRE_*`).
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

- pressing fire with food in hand. The heal itself is covered by a probe that sends
  `Event.Item.Consume` from Python: 50 → 60 HP on EASY, unchanged on MEDIUM, and it lands a
  frame after the send. Run it with
  `uepy.py --game --probe Scripts/probes/probe_consume_heal.py`;
- how the bars and the two-row strip look;
- the campfire: whether +1 a second within 4 m and a 3 minute burn feel right against a
  night that takes 0.1 a second, and how the fire and its light look (see
  `Scripts/combat/CLAUDE.md` for the strike).
