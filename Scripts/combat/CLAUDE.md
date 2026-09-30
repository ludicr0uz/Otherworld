# Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds `/Game/Weapons` and installs it on the characters.
`Scripts/verify_weapons_and_combat.py` reads the saved assets back. Both are thin entry points:
the code is this package (`__init__.py` is the map) and the verifier's sections are `verify/`.

## Controls, and where they live

The defaults are all rebindable on the settings screen:

- Left click fires. It **auto-fires while held** on the SMG and the assault rifle, a tap
  **eats or drinks** a held consumable, and with **empty hands it punches**
  (`weapon_component/punch.py`, see `docs/firing_gate.md`).
- Right click aims **over the shoulder**, middle click aims **down the sights** (both held),
  **Q** cycles, **G** drops, **E** picks up, **Shift** sprints, **F** blocks (held),
  **C** toggles crouch, **Z** toggles prone.
- **R** reloads, and restarts from the death menu.
- 1/2/3/4, M and D belong to the graphics menu.

The keys are CDO defaults on `BP_WeaponComponent`. The HUD pushes them from `BP_Settings`
every frame. Sprint and every other key live on the component, not on the character, because
`BP_ThirdPersonCharacter`'s graph is the Enhanced Input template, which the API cannot
partially rebuild.

R is shared safely between reload and restart: Tick does not run while paused, and the death
menu polls its own copy from `DrawHUD`, which does.

## The shape of it

- **Weapons are Actors, not components.** You can't leave a component behind in the world, so:
  - equipping is an attach, and dropping is a detach;
  - `Inventory` is one typed array of `BP_WeaponItem`;
  - firing reads every stat off `Held`, with one cast and no per-weapon branching.
- **A new weapon is a row plus a part table.** Add a row in `weapon_specs._weapon_specs()` and a
  part table. Adding the SMG, the rifle and the sniper changed **no** node in the fire, reload or
  gate graphs.
- **The rifle and the sniper are Fab models** (`weapon_models.py`): the FPS Weapon Bundle's AK 47
  (`SK_KA47_X`) and AS Val (`SK_KA_Val_X`) with its 25x56 scope, under `/Game/FPS_Weapon_Bundle`.
  - A row with a `model` builds the model instead of its `parts`. Its `parts` are then the
    model's **measured outline**: boxes that are never built, which the grip solve and the sight
    checks read exactly as they read a primitive gun's parts. Re-measure them if the mesh changes.
  - The pack's `_X`/`_Y` are **axis** variants, not textures: `_X` points down +X, which is the
    weapon's frame, so the model sits unrotated at real size. Muzzles are the meshes'
    `b_gun_muzzleflash` sockets.
  - The pack isn't committed. Without it the build stops at `_must_load`.
    `Scripts/asset_pipeline/fab_library.json` is the restore recipe.
  - The shotgun, pistol and SMG are still primitives. The pack has no shotgun or pistol, and
    its SMG11 and KA74U were not asked for.
- **Equipping is authored once.** BeginPlay, switch, drop and pick-up only set `NeedsRefresh`.
  Tick's last block consumes it and runs the single equip sequence. Weapons are spawned once at
  BeginPlay and then hidden or shown, never destroyed, so a dropped weapon is the same actor.
- **A pick-up goes into the inventory without switching.** The held item stays held. Only empty
  hands (`Held` is None, after a drop or eating the last item) take the new item up.
- **Ammunition lives on the weapon** (`MagazineSize`/`Loaded`/`Reserve` on `BP_WeaponItem`).
  Drop a half-empty gun and it is still half-empty when picked up. The pistol is the fallback: an
  8-round magazine over an endless reserve (`InfiniteReserve`), so it reloads every 8 shots but
  never runs dry. The reload fills its whole gap and never charges its reserve; shell pickups skip
  it; the HUD shows `5 / ∞`.
- **There is no reloading state.** `NextFireTime` is one world-time deadline. Both the fire
  interval and the reload push it out.
- **The shotgun and pistol are issued; the SMG, rifle and sniper are found.**
  - The gun drop (`gun_drop.py`) is **two seeded rolls** on two `FRandomStream`s on the
    GameMode: `GunDropRollStream < GUN_DROP_CHANCE` (10%) decides whether anything drops, then
    `RandomIntegerFromStream(GunDropPickStream, Length)` decides which.
  - **The loot table is `GUN_LOOT_TABLE`** (`tuning.py`), as weights: SMG 5, rifle 3, sniper 2.
    `DropClasses` holds one entry per ticket, so the uniform pick is the weighted draw.
  - The pick stream advances only on kills that drop, so re-weighting never moves which kills
    drop.
  - **The streams are seeded on the first counted kill,** behind `GunDropSeeded`. This happens
    in the health component because `combat_trace.py` owns the GameMode's graph.
    `GUN_DROP_SEED = 0` means a fresh seed each session. Any other value replays the same
    sequence every run: it is for probes.
  - A stream draw is pure and advances the stream, so each draw has exactly one reader. The
    verifier asserts it.
  - `verify/drops.simulate_gun_drops()` replays `FRandomStream` bit for bit. With a fixed seed,
    a PIE run dropped exactly the predicted guns.
  - Setting `Dropped = true` on the spawned actor is the entire handover.
  - Keep the `Length(DropClasses) > 0` guard, or an unfilled table indexes into nothing.
- **Kill rewards happen only on the `DamagedByPlayer` arm.** That covers the kill count, the two
  shells and the gun roll. The world-floor net writes `Health = 0` down the same death path, and
  it must not pay out.
- **`BP_AmmoPickup` is walked into.** It measures its own distance on its own Tick. `Credited`
  stops a player with two shotguns being paid twice. It destroys itself only once something has
  taken it.
- **Balance:** sustained DPS across the five weapons spans 75–171 (asserted). The shotgun does
  8 × 18 = 144, so one connected shot kills a 100 HP wanderer. The weapons differ in how damage
  is delivered, not in how much.

## Tuning

`COMBAT`, a frozen `CombatConfig` in `tuning.py`, is the **one** place global combat numbers
live: lethality, sprint and stamina, ADS, mouse sensitivity, recoil and the hit reactions.
Per-weapon numbers live in `_weapon_specs()`.

There is no DataAsset on purpose. Every number is a pin literal baked into a compiled graph,
and `Content/` is not committed, so an edit in the editor would be erased by the next build.
The verifier asserts the old loose constants are gone.

## Topic notes: read the one you are changing

The design rules and traps for each area are in `docs/`, one file per area. Read the file
before you change anything it covers. It is not loaded until then, so a session that only
touches the fire graph doesn't pay for the notes on blood.

| file | covers |
|---|---|
| `docs/aiming.md` | shoulder and down-the-sights aim, the accuracy cloud and recoil, the reticle and scope, sight pitch (`weapon_component/ads.py`, `accuracy.py`, `sight_pitch.py`, `sights.py`), how a weapon sits in the hand (`grip.py`, `verify/grip_fit.py`) |
| `docs/stance.md` | sprint, blocking (the guard's quarter damage and stamina cost), crouch and prone (`weapon_component/stance.py`), the procedural body poses (`body_pose.py`, `weapon_component/pose_weights.py`) |
| `docs/health.md` | health, respawn and the pack's numbering (`health_component.py`, `respawn.py`), dying (the ragdoll collapse), hit boxes and hit reactions (`hit_zones.py`, `hit_reaction.py`), blood (`blood.py`) |
| `docs/skin.md` | the player's body: the Meshy mesh and its retarget (`skin.py`) |
| `docs/audio.md` | gun and creature sounds (`audio.py`, `Scripts/fetch_weapon_sounds.py`) |
| `docs/firing_gate.md` | what may fire and when, eating through the fire button (`weapon_component/consume.py`), debug mode |
| `docs/anim_blueprint.md` | authoring Animation Blueprints from Python: AnimGraphs, pose pins, anim node settings |

## Collision

- **The collision enum is `unreal.CollisionResponseType.ECR_BLOCK`** (`CollisionResponse` is a
  struct). Use `get_/set_collision_response_to_channel`.
- **To test a collision change without playing,** spawn the actor into the editor world and run
  `SystemLibrary.line_trace_single` through it. A/B it by reverting the change.

## Still needs a play session

These are feel checks a headless run can't do:

- the punch's feel: whether the blow at `COMBAT.punch_impact_s` lines up with the fist in
  `MM_Attack_01`, and whether a flinch cutting the swing short (same montage group) reads;
- a real trigger pull through the hit zones (a pistol head shot should take a wanderer from 100
  to 61);
- the pistol emptying after 8 shots, clicking, and R refilling it to 8 (no key can be injected
  into a headless game, so only the verifier covers this);
- the rifle-arm pose on flinching creatures;
- whether a sustained SMG burst reads as a burst;
- the `GUN_ACCURACY` numbers: how wide each cloud feels at the hip, and whether the reticle's
  gap (and its 240 px cap) reads well on a real window;
- how the death camera looks under the terrain;
- how the sights' pitch looks at steep angles (the eye swings on an arc round the spine);
- the body poses in motion: the walk cycle plays on top of the crouch and the prone legs, and a
  prone body is longer than its capsule, so it can clip into slopes and walls.
