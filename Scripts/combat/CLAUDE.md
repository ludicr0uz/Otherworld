# Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds `/Game/Weapons` and installs it on the characters.
`Scripts/verify_weapons_and_combat.py` reads the saved assets back. Both are thin entry points:
the code is this package (`__init__.py` is the map) and the verifier's sections are `verify/`.

## Controls, and where they live

The eight defaults are all rebindable on the settings screen:

- Left click fires. It **auto-fires while held** on the SMG and the assault rifle, and a tap
  **eats or drinks** a held consumable.
- Right click aims **over the shoulder**, middle click aims **down the sights** (both held),
  **Q** cycles, **G** drops, **E** picks up, **Shift** sprints.
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
- **Equipping is authored once.** BeginPlay, switch, drop and pick-up only set `NeedsRefresh`.
  Tick's last block consumes it and runs the single equip sequence. Weapons are spawned once at
  BeginPlay and then hidden or shown, never destroyed, so a dropped weapon is the same actor.
- **Ammunition lives on the weapon** (`MagazineSize`/`Loaded`/`Reserve` on `BP_WeaponItem`).
  Drop a half-empty gun and it is still half-empty when picked up. The pistol is the fallback and
  has unlimited ammo.
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

## Aiming

- **Hybrid aim, resolved every frame before the trigger is checked:**
  1. A camera trace gives `AimPoint`.
  2. A muzzle trace towards `AimPoint` sets `AimBlocked` if it stops short.

  Pellets fly a cone around `Normal(AimPoint - muzzle)`. It is hitscan.
- **The reticle is nailed to the viewport centre**, and turns red when `AimBlocked`. Drawing it at
  the projected `AimPoint` was tried and reverted: it slid under parallax.
- **Two ways to aim** (`weapon_component/ads.py`):
  - `KeyAim` (right) is the shoulder aim: the camera stays on the boom and zooms
    `COMBAT.shoulder_zoom` (1.5x) on every weapon.
  - `KeySights` (middle) is down the sights: zoom is the weapon's `AdsZoom` (irons 1.5x, scope
    4x), and `sights.py` eases the camera from the boom's `SpringEndpoint` to the held weapon's
    `SightOffset` by `SightBlend`, by **location only**. The rotation stays the boom's.
  - `Aiming` is either key (cone, recoil, slowdown). `SightAiming` is the sights key alone,
    never with a consumable. `AimZoom` stores the zoom being aimed at. It isn't written on
    release, so the walk slowdown's ease-out divides by the zoom being let go of.
  - The camera is written every frame, both ways. The template camera has no offset on the
    boom (asserted in `aim_camera`), so SightBlend 0 is exactly home.
  - The weapon component ticks **after the boom** (`AddTickPrerequisiteComponent`). Otherwise
    the camera is placed against last frame's boom and shimmers while strafing.
  - `SightOffset` values (`weapon_specs.py`) were tuned in PIE. At 14 cm behind the receiver,
    its back face filled a third of the screen. At 34 cm, the camera was inside the head.
- **`Scoped` (sniper only) draws a scope overlay instead of the reticle, down the sights only.**
  `T_UI_Scope` is drawn as a square of the viewport height, with black side strips (in
  `graphics_menu/scope.py`).
  - It fades on `clamp((BaseFOV/CurrentFOV - shoulder) / (AdsZoom - shoulder), 0, 1)`, so the
    glass and the zoom are one animation.
  - It replaces the crosshair only past `shoulder_zoom + 0.02`: the hip and shoulder keep the
    crosshair. The slack is there because FInterpTo settles within rounding of 1.5x.
  - The sniper is **hidden past SightBlend 0.9**. The eye is behind the solid scope tube,
    which would fill the glass's hole. A dropped weapon is always unhidden.
  - `Scoped` and `AdsZoom` are independent.
- **Known limit of the sights:** the gun doesn't pitch (no aim offset), so looking steeply up
  or down leaves it below the view. At level aim the eye is on the sight line.
- **The camera boom sits over the right shoulder** (`camera.aim_camera()`: arm 260, socket
  offset `(0, 55, 60)`). Only pellet traces are drawn, never the two aim traces.
- **Aiming halves walking speed** (`ads_move_speed_scale`) with a *second* `MaxWalkSpeed`
  write in `_author_aim_slowdown`, after sprint's write.
  - It is gated on `NOT Sprinting AND IsValid(Held)`. Letting go needs no code, because sprint
    rewrites the speed every frame.
  - It eases on the zoom's progress, normalised by `AimZoom - 1`, so full zoom is half speed
    on any zoom and either aim. The mouse slowdown is deliberately *not* normalised.
  - **Trap:** always scale `BaseSpeed`, never the live `MaxWalkSpeed`, which compounds to a
    standstill. The verifier walks the inputs to check.
- **Recoil:**
  - The view kicks up by `RecoilPitch` and sideways by ±`recoil_horizontal_ratio` of it. Both are
    charged to `RecoilDebt`/`RecoilYawDebt` and repaid with `FInterpTo`.
  - Only `recoil_recovery_fraction` (0.7) of the recovery reaches the view, so bursts climb.
  - ADS multiplies the kick by `recoil_ads_scale`.
  - **Never use `AddPitchInput`/`AddControllerPitchInput`.** They are scaled by `InputPitchScale`,
    which the mouse-sensitivity setting writes. `_author_turn_view` does Get/Set
    `ControlRotation` instead.
  - Draw the sideways kick **once** into `RecoilYawKick`, because `RandomFloatInRange` is pure.
  - Turn the view **before** writing the reduced debts.

## How a weapon sits in the hand

- **The layered blend runs in mesh space** (`mesh_space_rotation_blend = True`). In local space
  the ready pose loses its pelvis yaw, and the barrel sat 21° left.
- **`GripRotation` is solved per weapon** against that weapon's sampled ready pose, putting the
  weapon's +X on the player's forward.
  - On the mannequin, `HandGrip_R` carries forward on its **+Y** axis.
  - On the adventurer, the hand bone's +Y runs down the aim too, since the retarget's palm
    calibration turns the whole hand onto the mannequin's. Nothing depends on that.
- **`GripLocation` is solved too** (`grip._grip_location`): it puts the weapon's `Grip` part in
  the middle of the fist in the ready pose.
  - Each closing finger's three joints lie on a circle. The centre of that circle is what the
    finger curls round, and the fist centre is the mean of the index-to-pinky centres
    (`PlayerSkin.grip_fingers`).
  - The ready poses hold the index finger on the trigger, 0.5–1.9 cm from `TriggerGuard`.
    Centring on the other three fingers alone moved it 2–3 cm off, and sank the pistol grip
    1.2 cm into the ring finger.
  - Consumables are seated the same way by their `grip_part` (the mushroom's `Stem`, the
    canteen's `Neck`).
  - `verify/grip_fit.py` re-measures the saved values. It checks that the handle is centred,
    that no joint sinks more than 0.5 cm into the part's box, that every wrapping joint is
    within 3.5 cm of it, and that the index is at the trigger guard.
  - **Before the solve,** a hand bone's origin is the wrist, so the grip hung 8–14 cm from the
    fingers, over the back of the hand.
- **The weapon is rigidly attached and never rotated on its own.** Aiming it per frame was tried
  and reverted. `face_the_camera()` makes the body follow the camera's yaw instead.
- **Known limits:**
  - There is no aim offset, so the gun doesn't pitch.
  - The legs play the unarmed gait, because strafe blend spaces can't be authored from Python.
- **Lesson:** three static "fixes" in a row agreed with themselves and shipped a sideways gun.
  When reasoning disagrees with the screen, instrument a `-game` run.

## Sprint

- 900 cm/s while stamina lasts: 4 s from full, refilling at 12/s. The pack runs at 600.
- The fire gate refuses while sprinting.
- Authored **without a Branch**. `SelectFloat` picks the speed and the stamina rate, and one
  write applies each.
- **Sprinting drops the ready pose** by stopping the slot, so `ABP_Unarmed`'s run comes through.
  It is edge-triggered: `Sprinting != PoseSprinting` sets `NeedsRefresh`. Level-triggering it
  restarts the montage every frame and the weapon strobes.
- `BaseSpeed` is cached from the character at BeginPlay (600). Never hardcode it.

## Health, respawn and the pack's numbering (`health_component.py`, `respawn.py`)

- **Respawns land 75–100 m from the player's current location.**
  - The band point is a *request*, stored in `RespawnPoint`, because the projection node is pure.
  - It is projected onto the navmesh (`RESPAWN_PROJECT_EXTENT`, 30 × 30 × 100 m).
  - Z is then **re-traced onto real collision** (`RESPAWN_TRACE_UP`/`_DOWN`; the trace starts only
    2 m up, to miss canopies) and lifted by the 88 cm capsule half-height, because navmesh Z can be
    86 cm low.
  - It spawns with `AdjustIfPossibleButAlwaysSpawn`.
  - `RESPAWN_ATTEMPTS` (2) bearings are tried, then any navigable point near the player. If that
    fails too, the wanderer is not replaced.
- **World-floor net:** anything below `WORLD_FLOOR_Z` (−1000 cm) gets `Health = 0` and dies the
  ordinary way. The player too: walking off the map kills you. `DespawnOnDeath` gates only the
  `[NPC-FELL]` log line.
- **Numbering:**
  - Each wanderer takes `NpcSpawnCount` from the GameMode into its own `NpcId` and logs
    `[NPC-SPAWN] #n at …`.
  - Set `NpcId` **first**, then write the counter back from `NpcId`. The other order numbers the
    first one 2, because the add is pure.
  - `[NPC-FELL] ERROR #n fell to … — spawned at …` quotes the stored `SpawnedAt`, which is for
    diagnosis only.
  - Both lines are `PrintWarning` (Blueprint has no Error severity) and appear in the log only.
- **Debuff drain** (`debuff_drain.py`) sits between the net and the death check.

## Dying

- **Everything collapses into a ragdoll** (`_author_death_collapse`):
  `DisableMovement` → capsule `NoCollision` → mesh profile `Ragdoll` → `SetAllBodiesSimulatePhysics`.
  - Use `DisableMovement`, not `DisableInput`: the HUD polls restart off the controller.
  - Turn off the capsule, not the mesh, because it is the capsule that blocks and is traced.
  - Set the profile **before** simulating.
  - `SetSimulatePhysics` would simulate only the root body.
- **There is no death animation, and none is possible.** Meshy rigs ship only walk and run, and
  the `MM_Death_*` clips are staggers that end standing.
- **The ragdoll joints are tuned** (`ragdoll.tune_ragdolls()`), for every mesh under
  `/Game/Sourced/Characters`.
  - The importer's `create_physics_asset` gives soft 45° cones centred on the bind pose, so limbs
    fold both ways.
  - `RAGDOLL_JOINTS` gives each role a one-sided flex range. `ragdoll_plan()` builds both frames
    from the reference pose:
    - a ball joint has X along the bone and Y as the flex axis;
    - a hinge has X as the flex axis;
    - an off-centre range turns the parent frame (PA_Mannequin's trick);
    - springs are 500/50 for ball joints and 1000/100 for hinges.
  - Write through `unreal.find_object(pa, "PhysicsConstraintTemplate_N")` →
    `set_editor_property("DefaultInstance", …)`. The property-change notification is required,
    or the edit reverts on save.
  - `ConstraintInstanceBlueprintLibrary` has no frames. `AngularRotationOffset` is ignored by
    physics assets.
- **A wanderer's corpse** (`_author_corpse`, on the `DespawnOnDeath` arm):
  `GetController` → `SetLifeSpan(controller, 0.1)` → `Owner.SetLifeSpan(60)`.
  - **`DestroyActor` on a controller is a no-op from Blueprint** (overridden empty in
    `Controller.cpp`). A lifespan calls the real `Destroy()`.
  - Use `GetController`, not the `Controller` member (not BlueprintReadOnly).
  - Use `SetLifeSpan` rather than a `Delay` owned by the actor being destroyed.
  - The corpse state itself is `npc/corpse.py`.
- **The player's death:**
  - collapse → `Delay 2.2` → `GameMode.PlayerDead` → `[PLAYER-DEAD] killed with N` → pause.
  - The delay is also the ragdoll's settle time.
  - The HUD draws YOU DIED, the kill count and `[R] try again`. That unpauses **before**
    `OpenLevel`; a level opened paused stays paused.
  - Restart is polled from `DrawHUD`, which runs while paused.
  - `FullBodySlot` is spliced into `ABP_Unarmed` and asserted, though nothing plays into it yet.
- **Combat trace:**
  - Toggle it in the console with `ke * CombatTraceOn` / `CombatTraceOff`, or set
    `COMBAT_TRACE_DEFAULT`.
  - It logs one `[COMBAT-TRACE]` line per landed swing.
  - The flag is on the GameMode. `combat_trace.py` **owns the GameMode's EventGraph** and wipes it
    every build.
  - The level verifier allows only the `[COMBAT-TRACE]` and `[NPC-CORPSE]` PrintStrings.
  - **Known, unfixed:** a wanderer can land one more swing on a player already at 0 HP.

## Hit boxes and hit reactions

- **The capsule decides whether a character was hit; the physics asset decides where.**
  - `_author_hit_zone` retraces the same line with `K2_LineTraceComponent` against the struck
    `Mesh`. This ignores channels, but the mesh needs query collision
    (`install_hit_zones` raises otherwise).
  - Head is ×1.5 and limbs ×0.75 (`COMBAT.head_multiplier`/`limb_multiplier`). A trace through the
    capsule that finds no body counts ×1.
- **Hit tables are derived per character.** `HeadBones`/`LimbBones` on each character's
  HealthComponent template come from `hit_zones(mesh)`:
  - bodies come from the physics asset's **constraints**, because `SkeletalBodySetups` is protected;
  - each is zoned via `BoneIsChildOf` on a transient component.
- **Characters must be shootable.** `make_shootable()` sets the capsule to block Visibility (see
  the root gotcha about `Pawn` ignoring it).
- **Hit reactions** (`hit_reaction.py`, on the death branch's False arm) poll
  `Health < PrevHealth`. The flow:
  - Check the cooldown `hit_react_cooldown_s`.
  - Pick a direction from `LastHitFrom` (a unit vector towards the source; zero counts as Front).
  - Play the montage into `HitSlot`.
  - Set `PrevHealth = Health` on every arm.
- **The clips are Epic's `MM_HitReact_*`, not `MM_Death_*`**, which carry the head up to 2.2 m.
  - The verifier measures every clip, including the retargeted copies: head under 30 cm, chest
    under 60°.
  - Left and right reuse `Front_Hvy_01` and `Front_Lgt_04`, chosen by head motion.
- **Order contract:** `NPC_HIT_REACTION_CLIPS` in `forest_generator/npc_placement.py` is the one
  definition, and the graph bakes its indices (`HIT_DIR_*`). It is all six clips or none; an empty
  array means no flinch.
- **`HitSlot` is its own slot**, created by `_ensure_hit_slot` behind a second `LayeredBoneBlend`,
  because `DefaultSlot` holds the ready pose.
  - All slots share one montage group, so a flinch stops the ready pose.
  - `_author_ready_pose_keepalive` restarts the ready pose when both slots are quiet. It is
    required.
- **Each wanderer variant's clips travel on its AI controller** and are copied at possession,
  because a child BP's inherited component override is unreachable from Python.
- **Debuff drain:** `debuff_drain.py` lowers `PrevHealth` along with `Health`, so starving is not
  read as a hit.

## Blood (`blood.py`)

- **19 lit droplets:** 14 of spray in a 34° cone plus 5 slow ones.
  - `M_Blood` is linear `(0.150, 0.014, 0.012)`, roughness 0.22, not emissive.
- **Flight uses the closed form of `dv/dt = g − k·v`** (k = 3.6/s, g = 980):
  - `A(t) = (1 − e^(−kt))/k` and `B(t) = (t − A)/k`;
  - `local = Velocity·A + Fall·B`;
  - fade `clamp((0.45 − Age)/0.14, 0, 1)`.
- **Launch velocity is baked into each droplet's build-time relative location** (÷100). The layout
  comes from a fixed seed, so the verifier recomputes it.
- **The impact spawns it rotated to the surface normal** (`MakeRotFromX`), scaled by
  `clamp(Damage/24, 0.65, 1.6)`.
- **Not Niagara:** Python can't build or retune an emitter stack in 5.8.
- **Trap:** a Kismet math node's **A** pin won't hold a literal. Keep constants on B, e.g.
  `(e^(−kt) − 1)/−k`.

## The player's body (`skin.py`)

- **The player wears `SKM_Adventurer01`** (Meshy `catalog.ADVENTURER`) animated by
  `A_Adventurer01_ABP_Unarmed`, which is `ABP_Unarmed` retargeted by
  `asset_pipeline/build_retarget.py`.
- **`PlayerSkin` is one record:** mesh, anim BP, grip, poses and offsets.
  - `player_skin()` picks the adventurer only if **all four** assets exist, and otherwise falls
    back to `SKIN_QUINN`.
  - A partial skin compiles, then stands in its bind pose.
- **The animation moved to the mesh, not the mesh to `SK_Mannequin`:**
  - Meshy returns its own 24-bone Mixamo-named rig, with no fingers and no twist bones.
    `asset_pipeline/finger_rig.py` adds 15 finger bones per hand and skins them (mannequin
    layout and weights carried into the measured hand frame), so the retargeted clips curl the
    fingers.
  - FBX import merges bone trees.
  - 5.8 exposes no skin transfer to Python.
- **Everything else is rig-agnostic:**
  - hit zones and the ragdoll read whatever mesh is worn;
  - `fix_retargeted_abp()` re-points `spine_01` to `Spine02`.
- **The grip is a bone (`RightHand`), not a socket**, because Python can't create a socket.
  `_BoneGrip` stands in for one.
  - The weapon is attached at the wrist, then moved into the fist by `GripLocation`.
  - The fingers close the way the mannequin's do in the retargeted ready pose.
    `finger_verify.py` checks each finger's curl against the mannequin's.
- **The two ready poses and the six hit reactions are retargeted onto every creature**
  (`AIM_SOURCES`, `HIT_SOURCES`), because they are played by path and no dependency walk
  finds them.
- **Build order from nothing:** weapons (mannequin fallback) → `fetch_monsters` →
  `import_characters` → `build_creature_materials` → `build_retarget` → `build_npc_blueprints` →
  weapons again.
  - `build_retarget` deletes and rebuilds `Anims/<Creature>/` every run, so
    `build_npc_blueprints` must follow it. Otherwise four checks fail in the *level* verifier.
- **Looking at a character:** `Scripts/dev/render_character.py` renders every character mesh to
  `Saved/Renders/`.
  - **To see a pose on it,** call `override_animation_data(anim, True, True, 0, 1)` on a
    `SkeletalMeshActor` already set to single-node with `play_animation`, set
    `visibility_based_anim_tick_option` to `ALWAYS_TICK_POSE_AND_REFRESH_BONES`, and capture in
    a **later** `uepy` job. Nothing poses in the job that spawns the actor. A scene capture is
    not "rendered", so the default option never evaluates the pose.
  - The world context is **not** optional on `create_render_target2d`/`export_render_target`.
  - Use `show_only_actor_components()`.

## Audio (`audio.py`, `Scripts/fetch_weapon_sounds.py`)

- **The nine weapon sounds are cut from CC0 recordings.**
  - The five gunshots all come from *The Free Firearm Sound Library*, so they share room and
    distance. The handling sounds come from two OpenGameArt packs.
  - The license is **CC0 only**, because there is no credits screen.
  - The fetcher downloads and caches into `assets/cache/sounds` using curl, bsdtar (for 7z),
    afconvert and `wave`, and cuts into `assets/generated/sounds`.
- **Rules baked into the samples:**
  - mono 44.1 kHz 16-bit, because a stereo sound can't be spatialised;
  - automatics cut quieter (peak < 0.80), with `length ÷ FireInterval ≤ 12` asserted;
  - shots truncated and faded, handling sounds not;
  - `_count_shots()` raises unless a gunshot cut has exactly one onset. One "single shot" take
    was a four-round burst.
- **`ReloadSound` is per weapon:** pump, magazine or hand-fed. `DryFireSound` is shared.
- **Where each sound fires:**
  - The dry click fires on the ready gate's False arm when `empty AND cooled AND tapped`.
  - The reload clack fires only on the reload's True arm.
- **Attenuation:** three `USoundAttenuation` assets in `/Game/Audio`, all `NATURAL_SOUND` and
  spherical:
  - `A_Att_Gunfire`: 2 m → 100 m, with a low-pass;
  - `A_Att_Creature`: 1.5 → 40 m;
  - `A_Att_Foley`: 1 → 15 m.
- **A sound with no attenuation plays at full volume from anywhere.** `apply_attenuation()` sets
  it **on the asset**, sweeps both audio folders, and raises on a wave with no profile.
  - The Python name is `d_b_attenuation_at_max`.
  - Proof it took: the engine-cached `max_distance` reads 10000 / 4000 / 1500.
  - `AreAnyListenersWithinRange` is **impure**. Left without an exec wire, it is pruned and
    reads false.

## Firing gate and debug mode

- **The fire gate:**
  ```
  outer: (tapped OR holding) AND IsValid(Held) AND NOT Sprinting
  inner: (Loaded > 0 AND cooled) AND (tapped OR (holding AND Held.Automatic))
  ```
  - Anything read off `Held` must stay inside the outer gate, per the nested-Branch gotcha in the
    root CLAUDE.md. The verifier pins that exactly one Branch reads `Automatic`, together with
    `Loaded` and `NextFireTime`.
  - Consumables branch off it: `Held.Consumable` plus a tap goes to `weapon_component/consume.py`.
  - **The press that eats is spent.** Eating equips the next item in the same frame, while the
    key is still down. `TriggerSpent` is set by the consume chain, the outer gate requires
    `NOT TriggerSpent`, and `TriggerSpent &= IsInputKeyDown` runs just before the gate. Without
    it, a weapon in the next slot fired once on the same press.
- **Reload stores `Min(MagazineSize − Loaded, Reserve)` into `ReloadTake` once.** Recomputing it
  after `Loaded` rises means free ammo.
- **Debug mode:**
  - `DebugMode` lives on the GameMode, because a component can't reach the HUD. It is on by
    default and persisted as `BP_Settings.DebugMode`. The HUD copies it at BeginPlay, and D writes
    both it and the save.
  - It shows the FPS readout, pellet tracers, per-impact damage (`39.0 (x1.5)`, only on actors
    with a health component) and wanderer numbers.
  - The tracer is a separate `DrawDebugLine` behind a Branch, since the enum pin can't be driven.
    Every trace's `DrawDebugType` is `None`.
  - Readers copy the flag once: the weapon component per shot, the HUD per `DrawHUD`.

## Animation Blueprint authoring

- **AnimGraphs are authorable; blend spaces are not.** Use
  `get_graph_editor_by_name(anim_bp, "AnimGraph")`. A bare `BlueprintGraphEditor(bp)` is the
  EventGraph.
- **A pose output pin may feed two pose inputs.**
- **An anim node's settings live on its inner `node` struct.** The read is a copy: mutate it and
  write the whole struct back. These structs `repr()` as `{}`, so check them field by field.
- **New slot:**
  1. Spawn the palette entry for an *existing* slot (`Animation|Montage|Slot'DefaultSlot'`).
  2. Rename `node.slot_name`.
  3. Compile, which registers it.
- **Sampling a pose:** `AnimPoseExtensions.get_anim_pose_at_time` → `get_bone_pose(…, WORLD)`,
  where WORLD means component space.
  - `get_reference_pose` takes a Skeleton, and its pose is not the mesh's, so compare like with
    like.
  - `compose_transforms(A, B)` is A-then-B.
- **The creatures' physics assets** are `SKM_Zombie01_PhysicsAsset` and
  `SKM_Wendigo01_PhysicsAsset`. `PA_Mannequin` is stock and untouched.

## Collision

- **The collision enum is `unreal.CollisionResponseType.ECR_BLOCK`** (`CollisionResponse` is a
  struct). Use `get_/set_collision_response_to_channel`.
- **To test a collision change without playing,** spawn the actor into the editor world and run
  `SystemLibrary.line_trace_single` through it. A/B it by reverting the change.

## Still needs a play session

These are feel checks a headless run can't do:

- a real trigger pull through the hit zones (a pistol head shot should take a wanderer from 100
  to 61);
- the rifle-arm pose on flinching creatures;
- whether a sustained SMG burst reads as a burst;
- how the death camera looks under the terrain.
