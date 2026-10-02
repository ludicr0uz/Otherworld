# Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds `/Game/Weapons` and installs it on the characters.
`Scripts/verify_weapons_and_combat.py` reads the saved assets back. Both are thin entry points:
the code is this package (`__init__.py` is the map) and the verifier's sections are `verify/`.

## Controls, and where they live

The defaults are all rebindable on the settings screen:

- Left click fires. It **auto-fires while held** on the SMG and the assault rifle, a tap
  **eats or drinks** a held consumable, **wears** a held garment (`weapon_component/wear.py`,
  `Scripts/clothing/CLAUDE.md`), with the **knife** in hand it **slashes**
  (`weapon_component/knife.py`), with the **matches** it **lights a campfire**
  (`weapon_component/light.py`), and with **empty hands it punches**
  (`weapon_component/punch.py`; all in `docs/firing_gate.md`).
- A gun is **carried lowered** (the jog's own arms, the gun in the hand) and comes up into its
  ready pose while an aim key or the guard is held, and for a shot or a reload
  (`weapon_component/carry.py`, `docs/aiming.md`).
- Right click aims **over the shoulder**, middle click aims **down the sights** (both held).
  Only a gun has sights (`HasSights`): with anything else in hand the middle click is the
  **use key** (`weapon_component/use.py`) and does not aim at all
  (`probes/probe_item_no_sights.py`). It lights a stick at a campfire and holds a burning one
  out, and with a hot knife or axe it cauterises a bleed (both below); on a cold blade, the
  matches, wood and food it does nothing yet.
  **Q** cycles, **G** drops, **E** interacts (an item in reach is picked up; a campfire heats the knife or axe in hand), **Shift** sprints, **F** blocks (held),
  **C** toggles crouch, **Z** toggles prone, **Left Alt** held down the sights holds the breath (`docs/aiming.md`), **V** held cocks the arm and shows the throw's arc, which ends on the reticle's point, and a click throws (see below).
- **R** reloads, and restarts from the death menu.
- 1/2/3/4, M and D belong to the graphics menu; **I** (the clothing panel) and Tab (the loot
  window) to the HUD.

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
  stock's wrist and the left along the pump, out of its low sight line, and the left hand
  turned under the pump with its fingers closed on the wood (the rifle pose cups a deep
  handguard: its knuckles stood inside the pump and its fingers out to the right).
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
- **E is Interact, and picking up is one kind of it** (`weapon_component/interact.py`). The key
  (`KeyInteract`, `INTERACT_KEY`) knows nothing about items. Each kind of thing is a
  `(candidates, act)` pair in `interact.KINDS`: `candidates` walks its things and offers some,
  `act` casts the kept target to its kind and does its thing. Of the candidates offered within
  `INTERACT_RADIUS` of the player, the one nearest `AimPoint`, the point the reticle rests on
  (the aim resolve sets it every frame, armed or not), is kept (`InteractTarget`, an Actor, and
  `InteractGap`). A walk only remembers; the act runs once, after the last walk's `Completed`,
  by the first kind whose cast takes the target. `InteractForced` is the probe's key press
  (`probes/probe_pickup.py`).
  - **To add something to interact with,** write its pair in a module of its own and add it to
    `KINDS`. Don't poll the key anywhere else.
  - **One kind is an item** (`weapon_component/pickup.py`): it offers the `Dropped`
    items and takes the target into the bag. A take inside the walk is how one press used to
    empty a pile.
  - **The other is a campfire** (`weapon_component/heat.py`), offered only while the held
    item `Heats`. It has no cast: a kind's `act` may test the target any way it likes (here
    `ClassIsChildOf` against `CampfireClass`) as long as it hands on the exec pin a target
    that is not its own leaves by.
  - `verify/interact.py` counts one reach test, one ranking and one keep **per kind**
    (`len(KINDS)`).
  - Searching a body is Tab, not this key (`Scripts/loot/CLAUDE.md`).
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
- **Knife, food and the stick have their own hold poses, not the pistol's aim**
  (`hold_pose.py`): `A_HoldKnife` (knife up at the chest, left fist raised as a guard),
  `A_HoldItem` (the item carried at the waist, left arm hanging), `A_HoldTorch` (the stick
  up beside the head) and `A_WardTorch` (it held out at arm's length), keyed off the idle by
  arm directions like the guard's. The right hand keeps the pistol pose's orientation and fingers, so the grip solve
  gives the pistol's answer and every item stays upright in the fist. The slash starts and ends
  in `A_HoldKnife`. `probes/probe_hold_poses.py` measures the hand heights in game.
- **The shotgun, pistol, knife, axe, matches and a stick are issued; the SMG, rifle and sniper are found.**
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
  arc: `PredictProjectilePath` from a point in front of the chest, at the point the reticle
  rests on (below), as world-space instances on `BP_ThrowArc`'s one ISM
  (spawned on first aim; `throw_arc.py`), with a disc where it lands. A click of the fire key
  over the arc plays the skin's throw clip (`throw_windup.py`: Quaternius UAL2's
  `OverhandThrow`, upper body only) and, where the clip's hand lets go (`THROW_RELEASE_S`,
  0.35 s into it), stores the launch, detaches the item and takes it out of the inventory as a
  drop does; letting V up instead calls it off.
  - **A throw goes where the reticle is** (`weapon_component/throw_launch.py`, the launch
    as pure pins). Its yaw is the bearing from the launch point to `AimPoint`, and its
    pitch the one whose curve passes through `AimPoint` at the item's `ThrowSpeed`, the
    flatter of the two (`DegAtan2` over a root: the docstring has the formula). So the arc
    lies in the upright plane through the reticle's point, stands under the reticle on
    screen and ends on it. The launch point is 55 cm to one side of the camera's line:
    along the view's own yaw the arc ran beside the reticle and never met it.
    - **Out of reach, or at the sky, it is a lob:** the root's inside goes negative past
      what the speed reaches (about 12 m at the default 1100 cm/s, 33 m for a blade), and
      the pitch is then the view's tipped up by the item's `ThrowArcDegrees`, as every
      throw was before. The two meet with a step at the edge of the reach.
    - **A point under `THROW_AIM_MIN_AHEAD` (100 cm) ahead of the launch point is not
      aimed at** (a wall at the shoulder, a trunk between the camera and the player):
      the throw goes out along the view's yaw, tipped.
    - `AimPoint` is where the reticle rests, which with something in hand is the first
      surface on the line from the shot's origin (`aim.py`), not always the camera's.
    - **A probe that faces a thing has not aimed at it:** the camera's line runs beside
      the player's. `probes/probe_throw_strike._reticle_on` turns the view until the
      reticle is on a target; `probes/probe_throw_reticle.py` checks the arc against
      `AimPoint` near, far and at the sky.
  - **While V is held the arm is cocked** (`weapon_component/throw_ready.py`):
    `A_ThrowReady` (`throw_pose.py`) is the throw clip stopped at `THROW_READY_S` (frame
    7, the hand furthest back), held looping in the upper-body slot for as long as the
    arc is drawn. It is asked for every frame by what the slot is playing
    (`IsPlayingSlotAnimation`), not on the key's edge, so it comes back after a flinch or
    a re-equip, and never starts under a flinch (the ready pose's own rule,
    `ready_pose.py`). The click plays the clip on from that moment
    (`InTimeToStartMontageAt`), so the hand lets go `THROW_WINDUP_S` (0.12 s) after it.
    Letting V up sets `NeedsRefresh`: the equip puts the item's own pose back, or stops
    the slot under a lowered gun. A skin with no throw clip has no ready pose.
    - `verify/throw_aim.is_ready_node` sets its two nodes aside in the older count of
      the slot's plays.
  - **The wind-up is a state, `ThrowWinding`: the item being thrown.** While it is valid no
    arc is drawn and the fire gate is shut. The release runs only if the hand still holds
    that item (a switch or a drop in the wind-up throws nothing), and reads the launch on
    its own frame, so the item goes where the view looks then.
  - **A skin with no clip** (`PlayerSkin.throw` is None: the mannequin) stamps no delay, and
    the item leaves on the frame of the click, from no ready pose.
  - **The release re-equips the hand** (`NeedsRefresh`), and the equip plays the next item's
    ready pose or stops the slot, so the clip's follow-through blends out over the equip's
    blend rather than playing to its end.
  - **With V down the fire gate is shut** (`_author_throw_key`'s NOT), so the click does not
    also fire, eat or slash, and the click that threw sets `TriggerSpent`, so it cannot fire
    the automatic equipped in the thrown item's place.
  - **The click needs last frame's `ThrowAiming`:** the Branch sits before the arc is drawn,
    so a click on the frame V goes down throws nothing.
  - **The lob's arc is per item.** `ThrowArcDegrees` defaults to `THROW_PITCH_UP_DEG` (30) on
    `BP_WeaponItem`, so food and water use it; a gun's is its `throw_arc` cell in
    `gun_tuning.csv`, the GUN TUNING tab's last row. It is the tip over the view of a
    throw at nothing in reach. Per item too are the speed (`ThrowSpeed`, 1100
    cm/s) and the tumble (`ThrowSpinDegS`, 540°/s): the launch reads the one off `Held`, the
    flight the other off `Thrown`.
  - **A melee weapon is thrown, not lobbed** (`throw_tuning.MELEE_THROW`, spread into the
    knife's and the axe's defaults; a sword's builder would do the same): 1800 cm/s, so its
    curve to a point 10 m off is nearly flat and it reaches 33 m; 8° up at nothing in
    reach, which rises 30 cm over the hand and carries 15 m, against the lob's 1.5 m over
    13 m; and 1080°/s of spin. Its `ThrowEdgeOn` makes the release square it up
    (`throw_flight._author_square`): `MakeRotFromX(ThrowVelocity)` on the detached item, so
    its X runs along the throw and its Y level across it. Every melee model is built blade
    up, edge towards +X, so the blade's plane is then the plane it flies in and the tumble,
    which turns about the across axis, is a throwing axe's forward spin, edge first. A new
    melee model must be built the same way round, or it spins flat-on.
    - The flag is its own bool, not `Melee`: the verifier counts the Branches that ask
      `Held.Melee` (one: the fire gate's).
    - That SetActorRotation is the only one in the graph, and `verify/weapon_inputs.py`
      requires it to come after a detach: nothing turns a weapon still in the hand.

  The flight (`throw_flight.py`) is **kinematic**, not
  physics (items are NoCollision): start + v t + g t²/2 under `THROW_GRAVITY_Z`, the arc's own
  gravity, traced frame to frame on Visibility; on a hit it backs off the surface, traces down
  to the ground and becomes an ordinary `Dropped` item. In the air it tumbles end over end,
  top first, its own `ThrowSpinDegS` (`THROW_SPIN_DEG_S`, 540°/s, by default) about the level
  axis across the throw, added frame by frame (`_author_spin`); it rests as it came down. One item flies at a time.
  What it strikes is the next point's. `ThrowKeyForced` and `ThrowClickForced` are the probe's stand-ins for
  the key and the click
  (`probes/probe_throw.py`, and `probe_throw_melee.py` for the knife and the axe); the throw
  numbers are in `throw_tuning.py`.
- **A thrown blade wounds a body and stays in it, and lodges in a tree** (`weapon_component/throw_strike.py`,
  called by the flight on the frame its segment trace hits something, before the item is set
  down). The whole stage is behind one Branch, `Thrown.ThrowDamage > 0`: the base item's is 0,
  so a thrown gun, mushroom or canteen does neither. The knife's is 50 and the axe's 75
  (the defaults in `throw_tuning.py`; each is its `throw_damage` cell in `gun_tuning.csv`,
  the GUN TUNING tab's last row: see Tuning), against the slash's 35: the throw costs the
  weapon until it is picked up again.
  - **A body** (the struck actor has a `BP_HealthComponent`) loses `ThrowDamage`, with the
    three stamps a pellet leaves (`LastDamageTime`, `DamagedByPlayer`, `LastHitFrom`: so a
    thrown blade counts the kill and enrages a wendigo), and `BloodClass` is spawned at the
    wound. No hot blade's double.
  - **A blade in the head does more** (`_head_worth`): the damage is times the struck
    body's own `HeadMultiplier` (1.5, the pellet's: `hit_zones.py`) where the bone the
    blade went in at is one of its `HeadBones`. Only the head: a limb takes it whole.
    That bone is the one the blade is then left in, so a blade seen in the head was a
    head shot. So where it went in (`_author_skin`, below) is found **before** the wound,
    and two variables on the component carry it across: `ThrowBone` (a Name, None for a
    body the blade could not be set into) and `ThrowSkin` (the point on that bone's body).
    `probes/probe_throw_head.py` throws both blades at a zombie's head and at its middle.
    - A probe that aims at the head must aim at the middle of the head's **body**
      (`_head_middle`): the `Head` bone itself is the base of the skull, and the reticle
      there is on the neck, which the `Spine` body covers.
  - **The blade stays in the body** (`_author_stick`): set on the model as it is into a
    trunk (the same `_author_lodge`, the pose below) and attached to the mesh at the bone
    it struck, KeepWorld, then straight to the landing's `Dropped = true`. So it goes
    where the body goes, alive or a ragdoll, and E takes it back from within
    `INTERACT_RADIUS` of the blade itself. Nothing else knows it is there: it is an
    ordinary pick-up whose actor moves.
    - **Where on the body is a trace of the mesh's physics bodies alone**
      (`K2_LineTraceComponent`, as the pellet's hit zone), since the flight's hit is on
      the capsule, far wider than the model. First **on along the blade's own line**:
      from that hit the way the segment flew and `STICK_LINE_REACH_CM` (120) far (not the
      segment itself, which is a frame long and can end short of the model). What that
      strikes is what the blade struck. A blade can also cross the capsule beside the
      model, having wounded it all the same: then, and only then, a second trace runs
      from the hit towards the bone nearest it (`FindClosestBone_K2`, bodies only) and
      `STICK_TRACE_PAST` (1.5) times as far. The one that strikes writes its `BoneName`
      to `ThrowBone` and its `HitLocation` to `ThrowSkin`, which the set and the attach
      read after the wound.
    - **The take detaches** (`pickup._author_take_item`'s `DetachFromActor`, KeepWorld):
      an item taken into the bag with something else in hand is only hidden, and would
      ride on with the body.
    - **A corpse's lifespan ends with the blade still in it**: the engine detaches
      attached actors as it destroys an actor, so the blade is left where the corpse lay,
      a pick-up still. Nothing here does that.
    - A dead body cannot be struck at all: its capsule is NoCollision and the Ragdoll
      profile ignores Visibility, so a throw passes through a corpse as a pellet does.
  - **`ThrowPast` is what the fall's ground trace ignores** (an Actor array on the
    component): emptied every strike, and given a body the blade could not be set into
    (no Character, or neither body trace found anything: `ThrowBone` is None), which drops it at its foot. The
    trace down then cannot land the item on the body's own arm or knee. A wall, a tree or
    the ground must never go in it: the same trace finds the ground through them.
  - **A tree** (no health, and the struck component is an `InstancedStaticMeshComponent`:
    chop's test) struck within `LODGE_MAX_HEIGHT_CM` (250) of its foot chips
    (`ImpactClass`) and keeps the item: one `SetActorLocationAndRotation`, then straight to
    the landing's `Dropped = true`, skipping the fall. Lodged, it is an ordinary pick-up
    hanging in the tree, and E takes it back. The foot is the tree instance's own origin
    (`GetInstanceTransform`, world space), not a trace, which a branch would stop. Higher
    than the pick-up could reach (`INTERACT_RADIUS` from the player's middle), it falls to
    the foot of the tree like any item.
  - **The pose is the item's own** (`combat/lodge.py`; `knife.knife_lodge`,
    `axe.axe_lodge`): `LodgeTurn`, a pitch that takes what goes into the wood (the knife's
    blade, the axe's bit) onto the item's +X, composed before `MakeRotFromX` of the
    segment it just flew; and `LodgePoint`, the point of its frame set on the hit, a
    `LODGE_*_DEPTH_CM` behind the tip or the bit. Both come out of the model's measured
    constants; a new blade's builder calls `lodge_pose` with its own.
  - `LodgeTurn` is a rotator variable, not a pitch into a Make Rotator: `verify/firing.py`
    counts the Make Rotators in the graph. The move is `SetActorLocationAndRotation`, not
    the release's `SetActorRotation`, which `verify/weapon_inputs.py` allows once.
  - `verify/throw_strike.is_strike_node` sets the stage's nodes aside in the older
    whole-graph counts (blood and impact spawns, `LastHitFrom` writes, the chop's tree
    cast, the pellet's body trace). `probes/probe_throw_strike.py` throws both blades and
    a gun at a trunk, and `probes/probe_throw_stick.py` at a body: alive, killed by the
    throw, and gone. With `--windowed` and `OW_THROW_SHOTS=1` each saves a picture of
    every lodged blade. A body the throw kills drops its gun beside it, and E takes the
    item nearest the reticle: the probe presses past it.
- **The use key is the sights key on an item with no sights** (`weapon_component/use.py`,
  names in `use_tuning.py`). `Using` is the key held (or `SightsForced`, the probes'
  stand-in), not sprinting, with a valid `Held` whose `HasSights` is false; `UsePressed` is
  its first frame. The stage runs before the aim, which reads `Using` so the key does not
  also aim, and hands the aim the one poll of the key.
  - **A use is a fragment in `use.KINDS`,** run every frame after those two are written,
    which asks its own flag of `Held` behind a Branch on `Using` or `UsePressed` (false with
    empty hands, so `Held` is valid there). To add one, write it in a module of its own and
    add it to `KINDS`. Don't poll the key anywhere else.
  - `HasSights` is read on the true arm of an `IsValid(Held)` Branch, never folded into the
    key's condition.
- **The stick burns** (`stick.py`, `weapon_component/torch.py`, numbers in `torch_tuning.py`).
  `BP_Stick` is Quaternius's `SM_WoodenTorch` at 0.18 (48 cm), flagged `Burns`, the sixth
  issued item. A press of the use key within `STICK_LIGHT_RADIUS_CM` (3 m) of a campfire
  (any `CampfireClass` actor) sets it `Lit` until `BurnOutTime`, `STICK_BURN_S` (120 s) on.
  - **It burns on its own Tick,** in the hand, in the bag (hidden) and on the ground, and
    shows `SM_WoodenTorch_Fire` and a point light in place of the bare model while `Lit`.
    Burnt out it is a stick again and can be relit: nothing is spent.
  - **Its graph names its components,** so `build_stick` wipes the graph before it rebuilds
    the model: with last build's nodes still reading the dropped components, the compile
    fails.
  - **The carry does not lower it** (`carry.py`: `Burns` joins `Melee` and `Consumable`):
    it is carried up in `A_HoldTorch`.
- **`FireWard` is fire held out in front of the player** (`paths.FIRE_WARD_VAR`, a bool on
  `BP_WeaponComponent`). `torch.py` writes it on every arm, every frame: true while `Using`
  with a `Lit` item in hand, false otherwise, so the key let go, a sprint, a burn-out, a
  drop, a throw or a switch all lower it with no code of their own; the dead gate lets it
  go too. A wendigo reads it (`Scripts/npc/CLAUDE.md`, "Fire holds the wendigo off").
  **Nothing else may write it**: a probe that set it by hand is overwritten on the next
  frame (`probes/probe_wendigo_ward.py` holds out a real stick).
  - **Held out, the stick's `AimPose` is swapped for its `UsePose`** (`A_WardTorch`) and
    the hand re-equips, so the equip and the keep-alive play it with no branch of their
    own. `WardItem` is the stick that is up and `WardCarryPose` what to put back; the
    lowering is tested before the raising. `probes/probe_lit_stick.py` runs all of it.
- **A blade is heated at a campfire** (`heat.py`, `weapon_component/heat.py`, numbers in
  `heat_tuning.py`). With an item flagged `Heats` in hand (the knife, the axe), E on a
  campfire in reach (`INTERACT_RADIUS`) sets it `Hot` until `CoolTime`, `HEAT_S` (20 s) on;
  a press on a hot one starts the time again. Nothing is spent.
  - **It cools on its own Tick,** in the hand, in the bag and on the ground, as the stick
    burns: `heat.build_heated_model` wipes the item's graph, builds the model and authors
    the Tick, for the stick's reason (its nodes name its components).
  - **The glow is an overlay material, not a second mesh:** `M_HotMetal`, unlit and
    additive, masked along an axis of the model component's own space, so the blade glows
    and the handle does not. Each item has an instance (`MI_HotKnife`, `MI_HotAxe`:
    `Axis`, `Start`, `Fade`, measured off the mesh; a scaled static mesh's are in mesh
    units). `HeatMaterial` on the item is what its Tick puts on `Model` while `Hot`, with a
    dim red point light, `HeatGlow`. The material is flagged `used_with_skeletal_mesh` by
    the builder: the knife is one, and a game cannot set the flag itself.
  - **Emissive above about 1 blooms out to white-yellow.** `HOT_EMISSIVE` is 1.0.
  - **The use key on a hot blade cauterises** (`weapon_component/cauterize.py`, a kind in
    `use.KINDS`): a press calls `RemoveActiveEffectsWithGrantedTags(Debuff.Bleeding)` on
    the player's ability system. The bleed is named by its tag because survival's
    `GE_Bleeding` is built after this graph. The blade stays hot.
  - **A hot blade's blow does double damage to a creature afraid of fire**
    (`weapon_component/hot_blow.py`, the blow's `damage` fragment in `punch._author_blow`).
    The knife stage's blow reads `BlowDamage`, written just before the health is: the
    strike's damage, or `HOT_BLOW_SCALE` (2) times it when `Held` is valid, `Held.Hot`,
    and the body carries the `FearsFire` actor tag (three nested Branches). The tag is the
    creature's (`Scripts/npc/CLAUDE.md`): combat never names a wendigo. A punch has no
    such fragment and takes its literal.
  - `probes/probe_hot_blade.py` runs all of it in a game; with `--windowed` and
    `OW_HOT_SHOTS=1` it saves a picture of each hot blade from in front of the player.
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

**The jog, the sprint and the stamina bar's times are `player_tuning.csv`'s** (`player_tuning.py`),
laid over `COMBAT` and tuned in game by the menu's PLAYER TUNING tab (`docs/stance.md`).

**Per-gun numbers can be tuned in game** (the M panel's **T** tab, `graphics_menu/tune_*.py`):
- `gun_tuning.csv` (tracked) holds each gun's 21 tunable stats (`gun_tuning.TUNE_STATS`: damage,
  pellets, range, interval, reload, magazine, sights zoom, shot volume, the accuracy columns,
  the sway's rate and the throw's arc).
- **The melee weapons have rows too** (`Knife`, `Axe`, under the guns:
  `gun_tuning.MELEE_WEAPONS`), holding their throw alone: `throw_arc` and `throw_damage`
  (`melee_tuning.py`, which `knife.py` and `axe.py` lay over `MELEE_THROW`; the defaults
  are `throw_tuning`'s). `throw_damage` is the table's 22nd column and no gun's: a gun's
  `ThrowDamage` stays 0, which is what keeps a thrown gun from wounding.
  `gun_tuning.columns_of(weapon)` says which columns are a weapon's own; a cell outside
  them is empty in the CSV, a dash on the tab, and never written onto the weapon. The
  slash's damage is not there: it is `COMBAT.knife_damage`, a literal in the blow's graph.
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
- the stick (`stick.py`, `hold_pose.HOLD_TORCH_DIRS`, `WARD_TORCH_DIRS`): how the torch
  reads carried beside the head and held out at arm's length (both keyed, both only looked
  at from behind in one windowed shot), the fist on a 3.8 cm handle, the pack's flat-shaded
  flames and the 7 m point light at night, lighting it with no animation, sound or message
  (and the silent press with no fire in reach), whether 2 minutes of burning and 3 m of
  reach feel right, whether a torch burning down unseen in the bag reads as fair, and the
  middle click no longer aiming a knife or an axe over the shoulder;
- the heated blade (`heat_tuning.py`): heating it with no animation, sound or message
  (and the silent press with a cold fire out of reach, or with the stick in hand), nothing
  on the HUD saying it is hot or how long is left, whether 20 s is long enough to reach a
  wendigo, the flat red of the axe's whole head by day (the overlay adds one colour, and
  the top of the haft inside the head glows with it), the glow and its light at night,
  and cauterising with no animation, sound or cost;
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
  pose's was), whether the left one closes on the pump or hovers (its base is 5 cm off the
  wood), and both on the mannequin fallback, where only the directions were carried over;
- the shotgun's left hand (`shotgun_pose.SUPPORT_PALM`, `SUPPORT_FINGERS`): how the wrist
  reads now the hand is turned 16° down under the pump on the rifle pose's forearm, the
  fingertips leaning forward up the pump's right side, and the right hand, left as the rifle
  pose has it (a pistol grip's fist on a straight stock: its fingers run into the receiver's
  belly and the guard);
- the head leaving the view on the way onto the sights (`HEAD_HIDE_SEAT` 0.8): whether it is
  seen to go, from behind, in the last of the camera's travel, and whether the headless
  shadow is noticed with the sun behind the player;
- the sight sway (`sway_tuning.py`): whether 0.3° reads as a held breath or as drunk,
  above all through the 4x scope, and whether crouch and prone steady it enough; whether
  the halved rate (0.5) is slow enough to time a shot, and holding the breath
  (`breath_tuning.py`): Left Alt with a real keyboard (on a Mac it is Option), whether 5 s
  held and 5 s winded feel right, and that nothing on the HUD shows the breath left;
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
  keyboard and mouse (the probe forces both); the throw's clip: whether the release
  0.12 s after the click feels right, the follow-through cut short by the re-equip, how
  it reads with a two-handed gun in the fist, crouched and prone;
- the throw at the reticle (`weapon_component/throw_launch.py`): whether the arc reads
  as under the reticle (it starts 55 cm to one side and closes on the point); the arc
  jumping as the reticle crosses the edge of a near thing onto far ground, or leaves
  the item's reach (12 m for a lobbed item: just inside it the throw goes up at about
  45°, just outside it is the tipped lob); a gun thrown straight at a point 3 m off at
  11 m/s, which is fast for a lob;
- the ready pose (`throw_pose.py`): how the cocked arm reads from behind with a long gun
  in the fist (seen once, in one windowed shot: the shotgun stands up beside the head),
  the 0.15 s it takes going up and coming down, holding it while walking, crouched and
  prone, and with the left hand of a two-handed gun left where the pose puts it; and whether 540°/s of tumble suits
  every item; a melee weapon's throw: whether 18 m/s at 8° up reads as thrown hard rather
  than shot, whether three turns a second reads as a spin or a blur, and the snap as the
  knife or the axe squares up to the throw on leaving the hand;
- a thrown blade's strike (`throw_tuning.py`): whether 50 and 75 HP are worth giving the
  weapon up for, and 75 and 112 in the head (a thrown axe in the head kills a full-health
  wanderer); how often a throw at a moving wanderer's head is in the head, the blade
  leaving the hand to the left of and below the camera; a hit with no sound, on a body or in the wood; the blade always going in
  point or bit first whatever its spin was at the moment it struck, and only into a tree
  (off a rock or the ground it still falls flat); how the lodged knife and axe read
  from the front and from the far side of a thin trunk (7 cm and 5 cm are in the wood);
  one that struck above 2.5 m dropping to the foot of the tree; and a blade thrown into a
  wendigo's capsule beside its body still wounding it (the flight has no hit zones);
- a blade left in a body (`weapon_component/throw_strike.py`): where it sits on a walking,
  swinging wanderer, since it goes in at the body part nearest where it met the capsule
  (thrown at a zombie's side it is in the arm) and not always where it was aimed; whether
  it clips through the limb as the bone turns; taking it back off a wendigo that is
  attacking (E within 2.5 m of the blade, nearest the reticle); a blade in a corpse lying
  under the gun the corpse dropped, where E takes whichever is nearer the reticle; and
  the blade left hanging a little off the ground when the corpse under it goes after 60 s;
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
