# Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds `/Game/Weapons` and installs it on the characters.
`Scripts/verify_weapons_and_combat.py` reads the saved assets back. Both are thin entry points:
the code is this package (`__init__.py` is the map) and the verifier's sections are `verify/`.

## Controls, and where they live

The defaults are all rebindable on the settings screen:

- Left click fires. It **auto-fires while held** on the SMG and the assault rifle, a tap
  **eats or drinks** a held consumable, with the **knife** in hand it **slashes**
  (`weapon_component/knife.py`), with the **matches** it **lights a campfire**
  (`weapon_component/light.py`), and with **empty hands it punches**
  (`weapon_component/punch.py`; all in `docs/firing_gate.md`).
- A gun is **carried lowered** (the jog's own arms, the gun in the hand) and comes up into its
  ready pose while an aim key or the guard is held, and for a shot or a reload
  (`weapon_component/carry.py`, `docs/aiming.md`).
- Right click aims **over the shoulder**, middle click aims **down the sights** (both held;
  only a gun has sights, `HasSights`, so with the knife, the axe, the matches, wood or food
  in hand the middle click aims over the shoulder too: `probes/probe_item_no_sights.py`),
  **Q** cycles, **G** drops, **E** picks up, **Shift** sprints, **F** blocks (held),
  **C** toggles crouch, **Z** toggles prone, **V** held shows the throw's arc and a click throws (see below).
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
- **A new weapon is a row plus a model and its outline.** Add a row in
  `weapon_specs._weapon_specs()`. Adding the SMG, the rifle and the sniper changed **no** node
  in the fire, reload or gate graphs.
- **The shotgun and the pistol are Quaternius models** (`weapon_models.py`): the Ultimate Gun
  Pack's `SM_Shotgun_3` (a pump gun with a straight wooden stock) and `SM_Pistol_1`, CC0,
  imported by `asset_pipeline/import_quaternius.py` into `/Game/Sourced/Quaternius/Guns`
  (zips in `assets/cache/quaternius/`). The pack is at no one size, so each row's model
  carries its scale to real size (0.18 and 0.11: 104 cm and 20 cm). Static meshes have no
  muzzle socket: the muzzles are the barrels' ends, measured. The shotgun's index can't reach
  its guard from the rifle's ready pose (`docs/aiming.md`). The shotgun is held in a pose of
  its own, `A_AimShotgun` (`shotgun_pose.py`): the rifle's, with the right thumb over the
  stock's wrist and the left along the pump, out of its low sight line.
- **The SMG, the rifle and the sniper are Fab models** (`weapon_models.py`): the FPS Weapon
  Bundle's SMG11 (`SK_SMG11_X`, a MAC-11 with its wire stock folded), AK 47 (`SK_KA47_X`) and
  AS Val (`SK_KA_Val_X`) with its 25x56 scope, under `/Game/FPS_Weapon_Bundle`.
  - **The SMG is held like the pistol:** its row's `aim` is the pistol's ready pose, so the grip
    is solved against it and it is one-handed (`TwoHanded` follows `aim`:
    `weapon_specs.two_handed_poses()`), guarding with fists.
  - A row with a `model` builds the model instead of its `parts`. Its `parts` are then the
    model's **measured outline**: boxes that are never built, which the grip solve and the sight
    checks read exactly as they read a primitive gun's parts. Re-measure them if the mesh changes.
  - The pack's `_X`/`_Y` are **axis** variants, not textures: `_X` points down +X, which is the
    weapon's frame, so the model sits unrotated at real size. Muzzles are the meshes'
    `b_gun_muzzleflash` sockets.
  - The pack isn't committed. Without it the build stops at `_must_load`.
    `Scripts/asset_pipeline/fab_library.json` is the restore recipe.
  - The pack has no shotgun or pistol (those are Quaternius's, above), and its KA74U was not
    asked for.
- **Equipping is authored once.** BeginPlay, switch, drop and pick-up only set `NeedsRefresh`.
  Tick's last block consumes it and runs the single equip sequence. Weapons are spawned once at
  BeginPlay and then hidden or shown, never destroyed, so a dropped weapon is the same actor.
- **A pick-up goes into the inventory without switching.** The held item stays held. Only empty
  hands (`Held` is None, after a drop or eating the last item) take the new item up.
- **A press picks up one item** (`weapon_component/pickup.py`): of the `Dropped` items within
  `PICKUP_RADIUS` of the player, the one nearest `AimPoint`, the point the reticle rests on (the
  aim resolve sets it every frame, armed or not). The loop only remembers the best candidate
  (`PickBest`, `PickBestGap`); the take runs once, off the loop's `Completed`. A take inside the
  loop is how one press used to empty a pile. `PickupForced` is the probe's key press
  (`probes/probe_pickup.py`).
- **Ammunition lives on the weapon** (`MagazineSize`/`Loaded`/`Reserve` on `BP_WeaponItem`).
  Drop a half-empty gun and it is still half-empty when picked up. The pistol is the fallback: an
  8-round magazine over an endless reserve (`InfiniteReserve`), so it reloads every 8 shots but
  never runs dry. The reload fills its whole gap and never charges its reserve; shell pickups skip
  it; the HUD shows `5 / ∞`.
- **There is no reloading state.** `NextFireTime` is one world-time deadline. Both the fire
  interval and the reload push it out.
- **The knife is a melee item, not a gun** (`knife.py`): a `BP_WeaponItem` child flagged `Melee`,
  drawn by the pack's `SK_M9_Knife_X` (blade up, tipped 30° forward, the pistol's grip), and
  not a row of `_weapon_specs()`, whose every column and check is about a gun. Its slash clip
  `/Game/Weapons/Anims/A_KnifeSlash` is keyed from Python (`knife_anim.py`): the pack has no
  animation and no stock clip is a knife attack.
- **The axe is the other melee item** (`axe.py`): Quaternius's Survival Pack `SM_Axe` (CC0,
  `/Game/Sourced/Quaternius/Survival`) at 0.2, a 65 cm camp axe, head up and tipped 30° forward
  with the bit leading, held in `A_HoldKnife` by the stretch of haft above its knob. It has
  **no strike of its own**: `Melee` sends the fire key to the knife's stage, so it swings
  `A_KnifeSlash` for `COMBAT.knife_damage`. An axe that hits harder needs its
  own `Strike` in `weapon_component/` (`punch.py` has the two stages).
- **The axe cuts wood from a tree** (`weapon_component/chop.py`, numbers in `chop_tuning.py`).
  The knife stage's blow passes what it struck to `_author_chop` off its failed health cast
  (`punch._author_blow`'s `scenery`). With an item flagged `Chops` in hand (only the axe) and a
  tree under the blow, it throws `BP_BulletImpact` chips and counts; every third blow on the
  one tree spawns `BP_Wood` 80 cm from the cut, turned 40-80° to one side of the player, traced
  down onto the ground and laid flat.
  - **A tree is "an `InstancedStaticMeshComponent` the sweep struck".** The trees are untagged
    instances of per-cell HISMs (`forest_import/trees.py`) and nothing else instanced has
    collision. One tree is the component plus the hit's `Item` (`ChopTree`, `ChopItem`); a blow
    on another tree starts the count over. Trees never run out and never fall: an instance
    can't be marked or removed cheaply.
  - **`Chops` is read behind its own `IsValid(Held)` Branch**: the blow lands after the press,
    when the hands may be empty.
  - **Order and purity:** `ChopCount` is stored before `ChopTree`/`ChopItem` (the pure "same
    tree" test reads them), and the landing point goes into `WoodSpot` before the trace reads
    it twice (it is built from random draws).
  - `verify/chop.is_chop_node` sets the stage's nodes aside in the older whole-graph counts.
    `probes/probe_chop_tree.py` stands the player at a trunk and swings.
- **Wood is an item with nothing to fire** (`wood.py`): `BP_Wood`, a `BP_WeaponItem` child,
  Quaternius's `SM_WoodLog` scaled apart (0.08 long, 0.055 across) to a 30 cm split, `Dropped`
  by default like food, so a spawned piece is already a pick-up. It is neither `Melee` nor
  `Consumable`, so the fire key runs the guns' path over no pellets, sound, kick or noise, and
  the carry treats it as a gun (it rides in the lowered hand). It stands on end in its own
  frame, held like a club, because the one fist pose closes on a handle running up through it;
  the chop's spawn tips it flat, but one dropped with G stands on its end.
- **The matches light a campfire** (`matches.py`, `weapon_component/light.py`, numbers in
  `light_tuning.py`). `BP_Matches` is Quaternius's `SM_Matchbox` at 0.08 (a 9 cm box), flagged
  `Lights`, carried in `A_HoldItem`. A tap of the fire key with it in hand takes one `BP_Wood`
  out of `Inventory`, destroys it, and spawns `CampfireClass` 130 cm in front of the player,
  on the ground a trace finds. The matches are never spent; with no wood nothing happens.
  - **The campfire is survival's** (`survival/campfire.py`): combat only holds a class
    variable. `build_survival.py` writes `CampfireClass`; the weapons build re-declares it
    and puts the old value back (`build._kept_class`), so a weapons-only rebuild keeps the
    fire. Unset, the strike is refused before any wood is spent.
  - **`EquippedIndex` is found again after the removal** (`Array_Find(Inventory, Held)`):
    wood ahead of the matches in the bag moves them down a slot.
  - **The loop only remembers** (`LightWood`); the take runs once off `Completed`, as the
    pick-up's does.
  - The fire goes where the player faces, whatever is there: facing a trunk at arm's length
    puts it in the tree. `probes/probe_campfire.py` runs the whole chain in a game.
- **Knife and food have their own hold poses, not the pistol's aim** (`hold_pose.py`):
  `A_HoldKnife` (knife up at the chest, left fist raised as a guard) and `A_HoldItem` (the
  item carried at the waist, left arm hanging), keyed off the idle by arm directions like the
  guard's. The right hand keeps the pistol pose's orientation and fingers, so the grip solve
  gives the pistol's answer and every item stays upright in the fist. The slash starts and ends
  in `A_HoldKnife`. `probes/probe_hold_poses.py` measures the hand heights in game.
- **The shotgun, pistol, knife, axe and matches are issued; the SMG, rifle and sniper are found.**
  The issued items are `inventory.STARTER_CLASS_VARS`, in bag order: one class variable
  each on the component, spawned at BeginPlay.
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
- **Anything in hand can be thrown** (`weapon_component/throw.py`). Holding **V** draws the
  arc: `PredictProjectilePath` from a point in front of the chest, along the view tipped up
  by the held item's `ThrowArcDegrees`, as world-space instances on `BP_ThrowArc`'s one ISM
  (spawned on first aim; `throw_arc.py`), with a disc where it lands. A click of the fire key
  over the arc plays the skin's throw clip (`throw_windup.py`: Quaternius UAL2's
  `OverhandThrow`, upper body only) and, `THROW_RELEASE_S` (0.35 s) later, where the clip's
  hand lets go, stores the launch, detaches the item and takes it out of the inventory as a
  drop does; letting V up instead calls it off.
  - **The wind-up is a state, `ThrowWinding`: the item being thrown.** While it is valid no
    arc is drawn and the fire gate is shut. The release runs only if the hand still holds
    that item (a switch or a drop in the wind-up throws nothing), and reads the launch on
    its own frame, so the item goes where the view looks then.
  - **A skin with no clip** (`PlayerSkin.throw` is None: the mannequin) stamps no delay, and
    the item leaves on the frame of the click.
  - **The release re-equips the hand** (`NeedsRefresh`), and the equip plays the next item's
    ready pose or stops the slot, so the clip's follow-through blends out over the equip's
    blend rather than playing to its end.
  - **With V down the fire gate is shut** (`_author_throw_key`'s NOT), so the click does not
    also fire, eat or slash, and the click that threw sets `TriggerSpent`, so it cannot fire
    the automatic equipped in the thrown item's place.
  - **The click needs last frame's `ThrowAiming`:** the Branch sits before the arc is drawn,
    so a click on the frame V goes down throws nothing.
  - **The arc is per item.** `ThrowArcDegrees` defaults to `THROW_PITCH_UP_DEG` (30) on
    `BP_WeaponItem`, so the knife, food and water use it; a gun's is its `throw_arc` cell in
    `gun_tuning.csv`, the GUN TUNING tab's last row.

  The flight (`throw_flight.py`) is **kinematic**, not
  physics (items are NoCollision): start + v t + g t²/2 under `THROW_GRAVITY_Z`, the arc's own
  gravity, traced frame to frame on Visibility; on a hit it backs off the surface, traces down
  to the ground and becomes an ordinary `Dropped` item. In the air it tumbles end over end,
  top first, `THROW_SPIN_DEG_S` (540°/s) about the level axis across the throw, added frame
  by frame (`_author_spin`); it rests as it came down. One item flies at a time. A thrown
  item does no damage. `ThrowKeyForced` and `ThrowClickForced` are the probe's stand-ins for
  the key and the click
  (`probes/probe_throw.py`); the throw numbers are in `throw_tuning.py`.
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

**Per-gun numbers can be tuned in game** (the M panel's **T** tab, `graphics_menu/tune_*.py`):
- `gun_tuning.csv` (tracked) holds each gun's 20 tunable stats (`gun_tuning.TUNE_STATS`: damage,
  pellets, range, interval, reload, magazine, sights zoom, shot volume, the accuracy columns
  and the throw's arc).
  `_weapon_specs()` lays it over its literals, so **the CSV wins**; the literals are the
  fallback for a missing cell. Edit the CSV by hand or through the tab, never only the literal.
- The tab writes the carried guns live and Enter saves the CSV; the Blueprints change only when
  `build_weapons_and_combat.py` and then `build_graphics_menu.py` run (the HUD's copy of the
  table is baked too: `tune_checks` fails if it is stale).
- A tuned value can break a design check that pins it (e.g. "the shotgun does 18 per pellet",
  the DPS spread, the recoil 4:1): update the check with the design, or re-tune.

There is no DataAsset on purpose. Every number is a pin literal baked into a compiled graph,
and `Content/` is not committed, so an edit in the editor would be erased by the next build.
The verifier asserts the old loose constants are gone.

## Topic notes: read the one you are changing

The design rules and traps for each area are in `docs/`, one file per area. Read the file
before you change anything it covers. It is not loaded until then, so a session that only
touches the fire graph doesn't pay for the notes on blood.

| file | covers |
|---|---|
| `docs/aiming.md` | the carry (a gun rides lowered until aimed or fired: `weapon_component/carry.py`), shoulder and down-the-sights aim, the accuracy cloud and recoil, the reticle and scope, sight pitch, the player's own head hidden down the sights, the camera's near plane (2 cm, so the pistol's hands are not cut open), the left hand held on the gun there (`weapon_component/ads.py`, `accuracy.py`, `sight_pitch.py`, `sights.py`, `head_hide.py`, `sway.py`, `support_hand.py`), how a weapon sits in the hand (`grip.py`, `verify/grip_fit.py`) |
| `docs/stance.md` | sprint, blocking (the guard's quarter damage and stamina cost), crouch and prone (`weapon_component/stance.py`), the procedural body poses (`body_pose.py`, `weapon_component/pose_weights.py`) |
| `docs/health.md` | health, respawn and the pack's numbering (`health_component.py`, `respawn.py`), dying (the ragdoll collapse), hit boxes and hit reactions (`hit_zones.py`, `hit_bodies.py`, `hit_reaction.py`), blood and bullet impacts on the scenery (`burst.py`, `blood.py`, `bullet_impact.py`) |
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

- sprint held with an aim key until the stamina runs out: no key can be pressed in a headless
  game, so the latch setting (`SprintSpent`, `docs/stance.md`) is checked on the graph only.
  Whether needing to let go of Shift before the next sprint feels right;
- the carry (`carry_tuning.py`): how a rifle reads jogging in one hand with the arm's swing
  (there is no two-handed carry clip), whether the gun coming up in 0.25 s behind the first
  shot reads, and whether 1.5 s is the right time to keep it up after the last one;
- the knife: how the keyed slash reads (`knife_anim.SLASH_KEYS`), whether the blow at
  `COMBAT.knife_impact_s` lines up with the cut, how the knife sits in the fist (the pistol
  grip's solve), and how the two hold poses read (`hold_pose.HOLD_*_DIRS`; the wrist keeps the
  pistol pose's angle on a lower forearm);
- the axe: how it reads in the fist and over the shoulder in the knife's stance (the head
  stands 35 cm above the hand, near the face), and swung on the knife's short slash, which
  was keyed for a blade (`probes/probe_axe.py` only proves it is in the hand and lands);
- chopping (`chop_tuning.py`): whether three blows a piece feels right, whether the chips
  read as a cut (there is no chop sound and no mark on the trunk), where the wood lands on a
  slope or among roots, and how the wood looks in the hand: the fist's joints sit up to 1.6 cm
  inside the 6 cm log (it has no handle), and a log dropped with G stands on its end;
- the matches and the campfire: the box in the fist (it is 1.3 cm thick and the one fist
  pose is closed on a pistol's grip, so the fingers stand up to 4 cm off it), a strike with
  no animation, sound or message (above all the silent one with no wood), a fire that
  appears at once 130 cm ahead, on a slope or inside whatever stands there, and how the
  pack's flat-shaded flames and the point light read at night;
- the punch's feel: whether the blow at `COMBAT.punch_impact_s` lines up with the fist in
  `MM_Attack_01`, and whether a flinch cutting the swing short (same montage group) reads;
- a real trigger pull through the hit zones (a pistol head shot should take a wanderer from 100
  to 61);
- the fitted hit bodies (`hit_bodies.py`): whether a shot that looks on the zombie ever misses
  (the bodies are one capsule a bone; `FIT_ROUNDNESS` and `FIT_END_OVERLAP` trade overhang
  for gaps), and whether a near miss vanishing at the capsule, with no chips behind, shows;
- the pistol emptying after 8 shots, clicking, and R refilling it to 8 (no key can be injected
  into a headless game, so only the verifier covers this);
- the rifle-arm pose on flinching creatures;
- whether a sustained SMG burst reads as a burst;
- bringing the sights up (`weapon_component/seat.py`): from the key the camera travels in
  one motion from the boom onto the sights, zooming as it goes, while the view stays on the
  target and the gun rises into it, about 0.3 s in all from a lowered gun. Whether that
  reads as one move; whether the camera reaching the eye point just before the gun is level
  (0.9 of the way when the gun is 10° off, `SIGHT_SEAT_DEG`) shows the gun still coming up
  from below, and whether its path bowing about 30 cm toward the rising gun is seen; the
  crosshair going out at 0.9 of the way with no fade (`RETICLE_HIDE_SEAT`), now before the
  sights have settled on the middle; the scope's glass closing while the rifle is still
  rising; sprinting out of the sights still lowers the gun under a camera on its way home;
- every gun down its sights, now that the eye is ON the sight line and the view runs down it
  (`docs/aiming.md`): the SMG11's is a 3 mm peep in a plate 15 cm from the eye, so the plate
  hides much of the view below and beside the target; the shotgun's support-hand fingers
  stand just right of the bead (its thumb no longer stands left of it); the adventurer's
  hair shows at the top of the AK's view;
- the hands down the pistol's sights, now that the near plane no longer cuts them open
  (`NEAR_CLIP_CM`, 2 cm): both thumbs stand whole beside the slide, left of the rear
  sight, 4-10 cm from the eye, where the skin's texture is a blur; whether they take too
  much of the view; and anything the nearer plane shows that 10 cm hid (the player's own
  body with the boom pulled in against a wall);
- the shotgun's thumbs (`shotgun_pose.SHOTGUN_THUMBS`): how the right thumb reads over the
  stock's wrist from behind and at the hip (its base joint is inside the wood, as the rifle
  pose's was), whether the left one closes on the pump or hovers (its base is 3 cm off the
  wood), and both on the mannequin fallback, where only the directions were carried over;
- the head leaving the view on the way onto the sights (`HEAD_HIDE_SEAT` 0.8): whether it is
  seen to go, from behind, in the last of the camera's travel, and whether the headless
  shadow is noticed with the sun behind the player;
- the sight sway (`sway_tuning.py`): whether 0.3° reads as a held breath or as drunk,
  above all through the 4x scope, and whether crouch and prone steady it enough;
- the left hand held on the gun down the sights (`support_hand.py`): whether the hand
  now reads as one with the gun while swaying and walking, on the AK above all; whether
  the hand is seen to shift (0.7 cm) as the hold eases in with the sights; a throw wound
  up down the sights keeps the left hand on the gun until the sights come off;
- a reload with the sights up: the view follows the gun, so it is thrown about with the
  arms. A hit no longer does (`weapon_component/steady.py`: no flinch down the sights);
  whether taking hits with no reaction at all reads, and the hit-then-sights blend;
- the `GUN_ACCURACY` numbers: how wide each cloud feels at the hip, and whether the reticle's
  gap (and its 240 px cap) reads well on a real window;
- how the death camera looks under the terrain;
- how the sights' pitch looks at steep angles (the eye swings on an arc round the spine);
- the throw: whether V and its arc read well (dot size and spacing, the landing disc on
  slopes), whether 11 m/s at 30° up feels right, holding V and clicking with a real
  keyboard and mouse (the probe forces both); the throw's clip: whether the 0.35 s
  wind-up feels late, the follow-through cut short by the re-equip, how it reads with a
  two-handed gun in the fist, crouched and prone; and whether 540°/s of tumble suits
  every item;
- the stance clips in motion (`stance_clips.py`): the crouched walk covers about 55 cm/s and
  plays at 2x, so at the crouch's 270 cm/s the feet slide; the crawl is the UAL's face-down
  swim (no crawl clip exists in the packs), a two-armed pull and a frog kick, which may read
  as swimming on dry ground; with a gun in hand, only its legs show under the aim (prone keeps the gun up). A prone body is longer
  than its capsule, so it can clip into slopes and walls. On the mannequin fallback the
  procedural poses still apply, with the walk cycle on top of them;
- the bullet impact on the scenery (`bullet_impact.py`): whether 1-3 cm lit chips and dust
  read at all at range and at night (they are not emissive, as blood is not), and whether
  0.6 s is long enough to see where a round landed. It leaves no mark behind;
- the shotgun's index finger along the receiver, 4 cm above the guard (`docs/aiming.md`).
