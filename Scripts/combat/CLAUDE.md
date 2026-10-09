# Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds `/Game/Weapons` and installs it on the characters.
`Scripts/verify_weapons_and_combat.py` reads the saved assets back. Both are thin entry points:
the code is this package (`__init__.py` is the map) and the verifier's sections are `verify/`.

Graphs are authored with `Scripts/uebp` (root `CLAUDE.md`): no coordinates, `out`/`then`
for pins, node paths from `uebp.nodes`, and a variable by its row (`WV.Held` from
`weapon_component/vars.py`, `HV.Health` from `health_vars.py`, `IV.Loaded` from
`item_vars.py`) or its `*_VAR` constant. `_log` is `combat/log.py`.

What each feature built, measured and proved is in `docs/history/combat.md`, moved there word
for word. A bullet here that is only its bold line and a link, or a heading with only a
link under it, names its part there.

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
  **1-4** bring the primary, secondary, pistol or melee slot's item to hand (the same key
  again puts it back: empty hands), **5-9** the bag's first five slots, **Q** the next filled
  bag slot, round the bag (not the weapon slots: `NextRequest`, `probes/probe_slots.py`) (all fixed keys, not settings binds: see "The slots" below), **G** drops, **E** interacts (an item in reach is picked up; a campfire heats the knife or axe in hand), **Shift** sprints, **F** blocks (held),
  **C** toggles crouch (in a sprint it slides: G5, "Crouch, slide and traversal from the sample"), **Z** toggles prone, **Left Alt** held down the sights holds the breath (`docs/aiming.md`), **V** held cocks the arm and shows the throw's arc, which ends on the reticle's point, and a click throws (see below).
- **R** reloads, and restarts from the death menu.
- M belongs to the graphics menu; **I** (the inventory: the backpack and the worn
  garments, with drag and drop) and Tab (the loot window) to the HUD.

The keys are CDO defaults on `BP_WeaponComponent`. The HUD pushes them from `BP_Settings`
every frame. Sprint and every other key live on the component, not on the character, because
`BP_ThirdPersonCharacter`'s graph is the Enhanced Input template, which the API cannot
partially rebuild.

**The keys are read only where the owner is locally controlled**
(`weapon_component/local.py`; `Scripts/net/CLAUDE.md`, "Input"). The component ticks on the
server and on other players' clients too; there the Tick skips the view, the keys and the
actions and runs only the pose, the slots and the equip. Every poll's self is `LocalPC`
(`local.local_pc`), never a controller by index, and a new key is polled in a fragment on
the local arm (`tick._author_wc_tick`'s first half or `_author_actions`).

R is shared safely between reload and restart: Tick does not run while paused, and the death
menu polls its own copy from `DrawHUD`, which does.

Death's pause is single player's (`death.py`, authored by `net.pause.author_pause`): a Branch
on IsStandalone stands in front of it, so on a server the world runs on past a dead player
(`verify/health.py`; `probes/probe_death_pause.py` is the standalone arm). What a dead
player gets there instead: their gear onto the body (`weapon_component/shed.py`) and a new
body 10 s later (`player_respawn.py`); `docs/health.md`, "Dying", and
`Scripts/net/CLAUDE.md`, "Death".

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
  its guard from the rifle's ready pose (`docs/aiming.md`). The shotgun is held in the
  rifle's ready pose, a shipped clip, and down the sights its left hand is held on a point
  of its own, on the pump with the thumb under the barrel's top (`shotgun_hold.py`,
  `pump_seat.py`; "The gun poses" below).
- **The SMG, the rifle and the sniper are Fab models**: `docs/history/combat.md#the-smg-the-rifle-and-the`
- **Equipping is authored once.** BeginPlay, a slot key, drop and pick-up only change an
  item's `Slot` or `Inventory`; the slot sync raises `NeedsRefresh` when the hand slot's item
  is not `Held`. Tick's last block consumes it and runs the single equip sequence (which
  empties `Held` first, so a hand slot with nothing in it is empty hands). Weapons are spawned once at
  BeginPlay and then hidden or shown, never destroyed, so a dropped weapon is the same actor.
- **The slots**: `docs/history/combat.md#the-slots`
- **E is Interact, and picking up is one kind of it**: `docs/history/combat.md#e-is-interact-and-picking-up`
- **An item on the ground glimmers**: `docs/history/combat.md#an-item-on-the-ground-glimmers`
- **Ammunition lives on the weapon** (`MagazineSize`/`Loaded`/`Reserve` on `BP_WeaponItem`).
  Drop a half-empty gun and it is still half-empty when picked up. The pistol is the fallback: an
  8-round magazine over an endless reserve (`InfiniteReserve`), so it reloads every 8 shots but
  never runs dry. The reload fills its whole gap and never charges its reserve; shell pickups skip
  it; the HUD shows `5 / ∞`.
- **There is no reloading state.** `NextFireTime` is one world-time deadline. Both the fire
  interval and the reload push it out.
- **The shot and the reload are server requests**: `docs/history/combat.md#the-shot-and-the-reload-are`
- **The pellet is judged where the shooter saw the target** (M22; `lag_tuning.py`,
  `uebp/nodes/shot.py`; the C++ is `Source/Otherworld`'s `OtherworldHitHistory` and
  `OtherworldShotLibrary`; `Scripts/net/CLAUDE.md`, "Lag compensation"). firing.py's
  pellet trace is one C++ node, `ShotTrace`: the Visibility trace and, for a struck
  character, its bodies along the same line (`bBodyHit`, `BodyBone`, `BodyPoint`, which
  impact.py's hit zone reads in place of its own `K2_LineTraceComponent`). On a server a
  remote shooter's pellets are traced against where every character stood its round
  trip ago (plus `EXTRA_REWIND_S`, at most `MAX_REWIND_S`); a local shooter's, so single
  player's, against the present, the same two engine traces as before.
  `probes/probe_net_lag_hits.py` is the proof, with and without `--lag 150`.
- **Melee, the guard, the throw and the take are server requests too**: `docs/history/combat.md#melee-the-guard-the-throw-and`
- **Everyone sees and hears the fight**: `docs/history/combat.md#everyone-sees-and-hears-the-fight`
- **The knife is a melee item, not a gun** (`knife.py`): a `BP_WeaponItem` child flagged `Melee`,
  drawn by the pack's `SK_M9_Knife_X` (blade up, tipped 30° forward, the pistol's grip), and
  not a row of `_weapon_specs()`, whose every column and check is about a gun. Its swing's clip
  `/Game/Weapons/Anims/A_KnifeSlash` is Mixamo's stab (`melee_clips.py`, "The melee clips"
  below; the asset keeps the name it had as a slash keyed from Python).
- **The axe is the other melee item** (`axe.py`): Quaternius's Survival Pack `SM_Axe` (CC0,
  `/Game/Sourced/Quaternius/Survival`) at 0.2, a 65 cm camp axe, head up and tipped 30° forward
  with the bit leading, held in `A_HoldAxe` by the stretch of haft above its knob. It has
  **no strike of its own**: `Melee` sends the fire key to the knife's stage, so it swings
  for `COMBAT.knife_damage`, in a clip of its own (`A_AxeSwing`). An axe that hits harder needs its
  own `Strike` in `weapon_component/` (`punch.py` has the two stages).
- **The axe cuts wood from a tree**: `docs/history/combat.md#the-axe-cuts-wood-from-a`
- **Wood is an item with nothing to fire** (`wood.py`): `BP_Wood`, a `BP_WeaponItem` child,
  Quaternius's `SM_WoodLog` scaled apart (0.08 long, 0.055 across) to a 30 cm split, `Dropped`
  by default like food, so a spawned piece is already a pick-up. It is neither `Melee` nor
  `Consumable`, so the fire key runs the guns' path over no pellets, sound, kick or noise, and
  the carry treats it as a gun (it rides in the lowered hand). It stands on end in its own
  frame, held like a club, because the one fist pose closes on a handle running up through it;
  the chop's spawn tips it flat, but one dropped with G stands on its end.
- **The matches light a campfire**: `docs/history/combat.md#the-matches-light-a-campfire`
- **Food and the stick have their own hold poses, not the pistol's aim**
  (`hold_pose.py`): `A_HoldItem` (the item carried at the waist, left arm hanging), `A_HoldTorch` (the stick
  up beside the head) and `A_WardTorch` (it held out at arm's length), keyed off the idle by
  arm directions like the guard's. The right hand keeps the pistol pose's orientation and fingers, so the grip solve
  gives the pistol's answer and every item stays upright in the fist. The knife's and the
  axe's ready poses are clips ("The melee clips"). `probes/probe_hold_poses.py` measures the hand heights in game.
- **The shotgun, pistol, knife, axe, matches and a stick are issued; the SMG, rifle and sniper are found.**: `docs/history/combat.md#the-shotgun-pistol-knife-axe-matches`
- **Anything in hand can be thrown**: `docs/history/combat.md#anything-in-hand-can-be-thrown`
- **A thrown blade wounds a body and stays in it, and lodges in a tree**: `docs/history/combat.md#a-thrown-blade-wounds-a-body`
- **The use key is the sights key on an item with no sights**: `docs/history/combat.md#the-use-key-is-the-sights`
- **The stick burns**: `docs/history/combat.md#the-stick-burns`
- **`FireWard` is fire held out in front of the player**: `docs/history/combat.md#fireward-is-fire-held-out-in`
- **A blade is heated at a campfire**: `docs/history/combat.md#a-blade-is-heated-at-a`
- **Kill rewards happen only on the `DamagedByPlayer` arm.** That covers the kill count, the two
  shells and the gun roll. The world-floor net writes `Health = 0` down the same death path, and
  it must not pay out.
- **`BP_AmmoPickup` is walked into.** It measures its own distance on its own Tick. `Credited`
  stops a player with two shotguns being paid twice. It destroys itself only once something has
  taken it.
- **Balance:** sustained DPS across the five weapons spans 75–171 (asserted). The shotgun does
  8 × 18 = 144, so one connected shot kills a 100 HP wanderer. The weapons differ in how damage
  is delivered, not in how much.

## The motion-matching base (G3, 2026-10-08)

The player's base movement is Epic's Game Animation Sample ("GAS": its motion matching,
not the ability system): the sample's `SandboxCharacter_CMC_ABP` and its
`CHT_PoseSearchDatabases` chooser, on the hidden UEFN mannequin the MetaHuman follows
(`Scripts/asset_pipeline/CLAUDE.md`, "The skeleton bridge"). `gas_locomotion.py` authors
it, `gas_locomotion_consts.py` holds its names, `verify/gas_locomotion.py` checks the
graph and `probes/probe_gas_locomotion.py` what it plays (`probe_net_gas_locomotion.py`:
another player's copy and the server's).

- **One switch: `GAS_LOCOMOTION`** (`gas_locomotion_consts.py`). Off, the player is the
  mannequin on the patched `ABP_Unarmed` again after a weapons build, with nothing else to
  change. A checkout without the sample (or without `build_gas_bridge.py`'s assets) wears
  the mannequin too, and says so.
- **One skin** (`skin.py`): `player_skin()` is `SKIN_GAS`, the UEFN mannequin. Its
  `anim_bp` is the graph the layers, the slots and the pose variables are in
  (`ABP_WeaponLayers`, below); `base_anim_bp` (`worn_anim_bp`) is what the Mesh component
  runs, the sample's. A probe finds the row with `skin_of_mesh`.
- **The anim Blueprint is patched where it lies, not copied.** The sample's choosers take
  an object of `SandboxCharacter_CMC_ABP_C` and of no other class: a duplicate ran, read
  the character correctly and was handed no database (`LogChooser: Error: ... ContextData
  entry 0 expects an object of type SandboxCharacter_CMC_ABP_C`). So it is a row of
  `gas_paths.PATCHED`, `import_gas.py` leaves it alone once it is here, and the weapons
  build patches it every run (each part is taken out or rebuilt first). To get the
  sample's own back, delete the file and run `import_gas.py`.
- **What it reads of the character is re-authored**: `docs/history/combat.md#what-it-reads-of-the-character`
- **The databases' search indices are built as a game starts** when it runs from the
  editor binary (out of the derived-data cache after the first time): until they are
  there the motion matching picks nothing and the body stands in its reference pose,
  with `LogPoseSearch: ... databases AsyncBuildIndex are in still in progress` in the
  log. `probe_gas_locomotion` waits for the first pick. A packaged game has them cooked.
- **The server branch is its own** (`gas_locomotion._author_server_branch`; A4's rule,
  `server_anim_consts.py`): one Blend Poses by bool on `ServerPose`, before the pose
  history. A server skips Foot Placement and Leg IK (the ground traces under the feet,
  as the old graph's Control Rig was); the search, the lean, the aim offset, the root's
  offset and the pose history are on both arms. `verify/server_anim.py` still checks
  `ABP_Unarmed`'s branch (the keyed rig's, and each wanderer's); the worn graph's is
  `verify/gas_locomotion.py`'s. The sample's graph has a blend by bool of its own (the
  aim offset's), so the server's is found by its flag, not by its class.
- **The sample's foley component rides on the player, silent** (`install.install_foley`,
  `GasFoley`). The sample's clips carry foot, jump and land notifies that look for
  `AC_FoleyEvents` on the owner and play the sample's own sound in 2D when there is
  none. The player's has a bank with nothing in it (`DA_SilentFoleyBank`): with no bank
  at all it logs an `Accessed None` at every footfall. The game's footsteps are still
  `BP_FootstepComponent`'s, by ground covered.
- **Memory:** a server or a `-nullrhi` client peaks at 4.2–4.3 GB with the sample's
  databases loaded (1.9 GB before). The chooser brings in the dense, sparse and
  extreme-sparse sets alike; dropping the ones the game never selects is not done.
  At 32 bots the server's world tick was 26.4 ms mean, 111.5 p99 (one client, a 45 s
  window, an editor open: A4's own figure was 25.3 / 87.0 with the editor closed), so
  the search itself did not show in the mean.

## The weapon layers (G4, 2026-10-08)

Everything a weapon, a stance or a hit does to the player's body is a second anim
Blueprint on the sample's skeleton, `ABP_WeaponLayers` (`/Game/Sourced/MetaHuman`), linked
into the motion-matching one by a Linked Anim Graph node after Remap Curves.
`weapon_layers.py` authors its start (an Input Pose, the three slots), `gas_locomotion.py`
the link, `weapon_layers_consts.py` holds the picture and the names,
`verify/weapon_layers.py` and `verify/gas_locomotion.py` check them.

- **No pose in it is linked to two inputs**: `docs/history/combat.md#no-pose-in-it-is-linked`
- **Its graph has `ABP_Unarmed`'s shape, with an Input Pose where the state machine was**,
  so `aim_pitch.py`, `body_pose.py`, `support_hand.py`, `stance_clips.py` and
  `server_anim.py` run on it as written, each on `skin.anim_bp`, and so do their
  verifiers. The sample's graph was not patched for them: it has component-space
  conversions, blends and a root of its own that those builders would have taken for
  theirs. The upper body is a layered blend per bone from `spine_01`, as it was: the
  sample's graph has no AnimationLayering slot (its one montage slot is full body, and is
  out of the pose line but while a traversal plays: G5, below).
- **The link is after the root's offset.** The aim's blend is in mesh space, so an aimed
  chest faces where the capsule does; before Offset Root Bone it would face where the
  lagging root does (the sample turns in place). It is before the feet and the pose
  history, and on both arms of the base's server branch: the layers move the hit bodies
  and the muzzle, and the layer graph has A4's branch of its own (a server skips
  FullBodySlot), which is the one `verify/server_anim.py` checks for the player.
- **The pose variables are on the linked instance, not the mesh's own.** A graph gets it
  with `GetLinkedAnimGraphInstanceByTag(LAYERS_TAG)` on the mesh
  (`weapon_component/sight_pitch._anim_instance`: the four writers, `sight_pitch`,
  `pose_weights`, `support_hand`, `look`), a probe with `p.pose_instance(mesh)`. Montages
  and slot questions (`PlaySlotAnimationAsDynamicMontage`, `IsSlotActive`,
  `IsPlayingSlotAnimation`) stay on the mesh's own instance: the layer class has
  `bUseMainInstanceMontageEvaluationData`, so its slots play the main instance's montages.
- **A linked graph's tag is the graph node's `tag`**, not the inner struct's (`Tag` there
  is a deprecated field Python calls protected).
- **A clip belongs to one skeleton**, so the layers' clips are copies on
  `SK_UEFN_Mannequin` (`asset_pipeline/retarget_to_uefn.py`: the two ready poses and
  the six flinches off the mannequin, the crouch, crawl, kneel and throw off
  Quaternius's own rig; `asset_pipeline/import_lyra.py`: the punch, Lyra's
  `MM_Pistol_Melee`, since C1; `SKIN_GAS` names them), and the poses the build keys (the hold
  poses, the shotgun's, the throw's) are keyed on that skeleton from them and
  from the sample's idle.
- **No clip played into a slot may have root motion** (`hold_pose.in_place`,
  `verify/weapon_layers.py`). A montage of a clip with the flag on takes the character's
  movement over. The sample's clips have it on, the hold poses are copies of its idle,
  and a hold pose is a looping montage: with the knife or the axe out the player could
  not walk. The mannequin's punch has it on too (150 cm forward), so until G3 a punch
  carried the player forward; its copy here is in place, flag off.
- **The punch is Lyra's pistol melee** (C1; `asset_pipeline/lyra_paths.PUNCH`, a straight
  right: Lyra has no unarmed attack). Nothing about the strike changed: the blow is still
  timed, `COMBAT.punch_impact_s` (0.3 s) after the swing, not notified, with the same
  sweep and damage. The clip's fist is out 0.45-0.5 s in, so the swing plays it from
  `COMBAT.punch_clip_start_s` (0.15 s; `Strike.clip_start_s`, the slot play's
  `InTimeToStartMontageAt`), and `verify/punch.py` measures the fist's reach at the
  blow's time off the clip (at least 80% of the swing's travel). Under the mannequin's
  clip the blow landed 0.1 s before the fist was out. A checkout without Lyra punches
  with the mannequin's clip (`skin._gas_skin`).
- **The body is 10 cm shorter than the mannequin** and the ready poses are retargeted
  chain to chain, so the fist of a ready pose is 11-14 cm nearer and 14-19 cm lower in the
  capsule's frame (`carry_tuning.CARRY_GRIP`, re-measured) and the sights' view with it.
- **A body on another skeleton re-creates the hold poses** (`A_HoldItem` and the rest
  are deleted and keyed again: `hold_pose._copy_of`), and every item Blueprint outside
  this package that names one is left holding nothing: run `build_survival.py` and
  `build_clothing.py` after the weapons build (their verifiers say so: "is carried in
  A_HoldItem").
- **Probes that share a game disturb each other** more than they did (the dev-all-guns
  request, `RaiseForced`, a thrown item): `probe_carry`, `probe_knife`, `probe_punch`,
  `probe_net_fire` and `probe_net_melee` pass alone and failed behind another probe.
- **A headless frame is about 10 ms now**, so a probe that writes an eased value every
  frame and reads what the Tick made of it (`probe_scope_hide` did) sees one ease step of
  that size; hold the key's stand-in (`SightsForced`) and wait instead.
- **`probe_sight_align` fails one check of 186** (the rifle, looking up 25°: the shot's
  point 0.37° off the sight line). The view is still and the point is a hit 7.7 m away,
  5 cm off the line: the aim trace grazing a branch from the lower eye point, not the pose.

## The gun poses (C3, 2026-10-08)

Every gun's ready pose (what it is held in for an aim, down the sights, a shot, a reload
and the guard) is a shipped clip: Lyra's ADS idles, retargeted onto the UEFN skeleton by
`asset_pipeline/import_lyra.py` (`lyra_paths.AIM_RIFLE`, `AIM_PISTOL`; `SKIN_GAS.aim_rifle`,
`aim_pistol`). The rifle's is the sniper's and the shotgun's, the pistol's the SMG's.
Nothing is keyed: `shotgun_pose.py` and `A_AimShotgun` are gone (the weapons build deletes
the asset from a checkout that has it).

- **Still one ready pose per gun.** Lyra's hipfire idles are not played: the game has no
  hip pose (a gun not held up is carried in the locomotion's hand, `docs/aiming.md`, "The
  carry"), and a second pose would need a second grip solve. The pitch is still the spine's
  (`aim_pitch.py`); no aim offset asset is used.
- **The shotgun is the rifle's clip with one offset** (`shotgun_hold.py`): its
  `SupportPoint`, the point the support hand's IK holds the left wrist on down the sights,
  is the pose's point moved onto the pump (4 cm forward, 5 down on the worn hand), found
  by `pump_seat.seat` with the thumb kept under the barrel's top. Unmoved, the thumb's tip
  is 3.7 cm above the shotgun's sight line. The hand's shape is the clip's, so its joints
  ride up to 3.8 cm off the wood (`verify/shotgun_pose.PUMP_REACH_CM`), and the point
  holds only down the sights: at the hip the hand is where the clip has it. Lyra's own
  `MM_Shotgun_Idle_ADS` is the rifle's with the left hand 2 cm further back, further from
  this pump, so it is not taken.
- **Lyra's pistol pose lays the trigger finger straight along the frame.** Three things
  follow. `grip.fist_in_socket` leaves a finger on a circle wider than
  `CURL_MAX_RADIUS_CM` out of the fist's middle (the index's was 44 cm, which put the
  middle 10 cm out of the hand and every grip with it). The pistol's and the SMG's rows
  carry `trigger_reach` 4.5 (`weapon_models.PISTOL_POSE_TRIGGER_REACH_CM`): the index
  rests 3.5 to 3.9 cm above the guard, not on the trigger. And a carried item's fist
  (`hold_pose.closed_fist`: the hold poses, the knife's and the axe's clips) is the
  pistol pose's with the index taken from the rifle pose (`PlayerSkin.fist_index`),
  where it is closed: a knife held in the pistol's own fist would be pointed at.
  `verify/grip_fit.fist_off` checks that fist joint by joint.
- **A changed fist leaves the items outside this package seated in the old one**: the
  mushroom's and the canteen's grips are solved against `A_HoldItem` by their own
  builders. Run `build_survival.py` and `build_clothing.py` after a weapons build that
  changed a ready pose (`verify_survival.py` says so: "the Stem is in the middle of the
  fist").
- **The poses lean in to the sights**: the fist is 11 to 13 cm further forward than in
  the mannequin's poses, so `carry_tuning.CARRY_GRIP` was re-measured ((28, 10, 40)).
- **A checkout without Lyra** holds the guns in the mannequin's `MF_*_Idle_ADS`,
  retargeted (`skin.GAS_AIM_WITHOUT_LYRA`, as the punch falls back); the shotgun
  verifier then fails its "is Lyra's" line.
- **`probe_headshot` was unreliable before this** and is not the poses': its wanderer
  swung at the player, who was dead before the last round one run in two, and at 150 cm
  a hip round's line from the muzzle to the reticle's point left through the capsule's
  side. The wanderer's controller is taken off it now and it stands at 300 cm.

## The melee clips (C2, 2026-10-08)

The knife's and the axe's ready pose and swing are Mixamo's clips, not poses keyed from
Python: `Knife Idle` and `Stabbing` (two single downloads), and the Pro Melee Axe Pack's
`standing idle` and `standing melee attack downward`. `asset_pipeline/import_mixamo.py`
(its last step; `import_mixamo_player.py` runs that step alone) imports the four named in
`mixamo_paths.PLAYER_CLIPS` onto `SK_XBot` and retargets them onto the player's skeleton
into `/Game/Sourced/Mixamo/UEFN_Player`; the weapons build's `melee_clips.py` bakes each
into the game's own asset (`A_HoldKnife`, `A_KnifeSlash`, `A_HoldAxe`, `A_AxeSwing`), and
`verify/melee_clips.py` checks each bake against Mixamo's frame for frame.

- **A bake changes two things.** The right hand's fingers are the pistol pose's on every
  frame (Mixamo's hand is posed for a prop the game does not have, and the items are seated
  in the pistol's fist), and a swing starts `COMBAT.knife_impact_s` before the moment its
  clip strikes (`MeleeClip.hit_s`, read off the hand's path: 0.97 s into the stab, 0.85 s
  into the chop), since the blow is timed and not notified. The wind-up before that is not
  played; the recovery is, to the clip's end, unless the next swing cuts it short.
- **The grip rotation is the pistol hand's** (`knife.py`, `axe.py`:
  `_grip_rotation(skin.aim_pistol)`), not one solved against the ready pose: that solve
  turns the item to face ahead, and Mixamo's hand does not face ahead. The location is
  still solved in the ready pose, whose fist is the pistol's.
- **Which clip a swing plays is picked on each machine by the ready pose in hand**
  (`Strike.by_pose`, `punch._author_clip`): `A_AxeSwing` while `HandPose` is `AxePose`,
  else the strike's own. Not by `Held`: another client's copy of a player has `HandPose`
  (`look.py`, off the replicated `LookPose`) and may not have the item.
  `probe_net_fx.py` has client 2 see the axe's clip and the knife's on client 1's copy.
- **A new melee item's clips** are two rows of `PLAYER_CLIPS`, two of `MELEE_CLIPS`, and
  a `by_pose` pair on the `KNIFE` Strike.
- **The stick is not a melee item** (it is not `Melee`; the fire key does nothing with it),
  so it has no swing, and its torch poses are still `hold_pose.py`'s.
- **The clips are on the sample's skeleton alone.** With `GAS_LOCOMOTION` off, or the
  sample missing, the weapons build stops at `melee_clips.py` saying so: the keyed slash
  that any skeleton could be given is gone.
- **Mixamo's knife idle carries the knife at the hip**, where the keyed pose held it up
  before the chest, and its stab ends with the hand 14 cm above where the idle holds it
  (two downloads); the slot's blend takes that up.
- `probe_metahuman_look.py` (windowed) pictures the axe held and as its blow lands, and
  checks that both are moving clips; `probe_axe.py` and `probe_knife.py` swing each at a
  wanderer.

## Crouch, slide and traversal from the sample (G5, 2026-10-08)

The moves the sample ships beyond the walk and the run, on the keys the game already
had, each behind its own switch in `gas_moves_tuning.py` (`GAS_CROUCH`, `GAS_SLIDE`,
`GAS_TRAVERSAL`; a builder or a verifier asks `gas_moves.crouch_on()` and its two
siblings, which are also off on the mannequin fallback). Change one, then run the
weapons build. `verify/gas_moves.py` checks each switch both ways,
`probes/probe_gas_traversal.py` crouches, slides and mantles a 1 m block, and
`probes/probe_net_slide.py` slides as a lagged client.

- **The crouch is the sample's Stance.** `Update_PropertiesFromCharacter` sets
  `Stance = Crouch` while `GetStance(pawn) == 1` (crouched, not prone: the movement's own
  answer, so every machine's copy), and the sample's chooser picks its crouch databases
  (idles, walks, starts, stops, pivots, the stand-to-crouch transition). The weapon
  layers then author **no** crouch blend (`stance_clips.py`): the two Quaternius crouch
  clips are still built and named by the skin, and come back with the switch off.
  `PoseCrouch` is still eased (nothing reads it on this body). Prone, the kneel and the
  crawl are the layers' as before; the capsule, the speed and the key are unchanged.
- **The slide is ours, posed by the sample's clip.**: `docs/history/combat.md#the-slide-is-ours-posed-by`
- **Traversal is the sample's own component**: `docs/history/combat.md#traversal-is-the-sample-s-own`

## Building one step (T9)

`build_weapons_and_combat.py` is an entry point over `combat/build_steps.py`, a table of
`Step(name, function, needs, made)`. `uepy.py --only a,b Scripts/build_weapons_and_combat.py`
(or `UEPY_BUILD_ONLY=a,b`) runs those steps, in table order, and nothing else.

- A step run alone finds what earlier steps hand on (the item Blueprint, the weapons, the
  knife's clip...) on disk, where the last full build left it (`Ctx`).
- A `needs` step that was not selected must have left its `made` assets on disk, or the run
  stops before building anything. A need with no `made` (a patch) cannot be checked.
- An unknown step name is an error too (the message lists them).
- Proof: `graph_fingerprint.py full` after a full build, `--only weapon_component,health,health_defaults`
  on top, `graph_fingerprint.py only`: `graph_fingerprint_diff.py full only` differs only in
  the stock `UI_Thumbstick`'s opaque delegate default (an address, not ours).
- Time: the full build 156 s (with the editor's cold boot inside it; about 105 s warm); those three
  steps 122 s (the weapon component is nearly all of it); `--only blood,knife` 1.9 s.
- A new builder is a new function and a row in `STEPS`, in the order it must run.

## Tuning

`COMBAT`, a frozen `CombatConfig` in `tuning.py`, is the **one** place global combat numbers
live: lethality, sprint and stamina, ADS, mouse sensitivity, recoil and the hit reactions.
Per-weapon numbers live in `_weapon_specs()`.

**The jog, the sprint and the stamina bar's times are `player_tuning.csv`'s** (`player_tuning.py`),
laid over `COMBAT` and tuned in game by the menu's PLAYER SETTINGS tab (`docs/stance.md`).

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
| `Scripts/Sound/CLAUDE.md` | every sound: the areas' tables, the bindings, attenuation, volumes, `build_sound.py` (it was `docs/audio.md`) |
| `docs/firing_gate.md` | what may fire and when, eating through the fire button (`weapon_component/consume.py`), debug mode |
| `docs/anim_blueprint.md` | authoring Animation Blueprints from Python: AnimGraphs, pose pins, anim node settings |

## Collision

- **The collision enum is `unreal.CollisionResponseType.ECR_BLOCK`** (`CollisionResponse` is a
  struct). Use `get_/set_collision_response_to_channel`.
- **To test a collision change without playing,** spawn the actor into the editor world and run
  `SystemLibrary.line_trace_single` through it. A/B it by reverting the change.

## Still needs a play session

Moved word for word: `docs/history/combat.md#still-needs-a-play-session`.

## Hit reactions (C4)

The six `MM_HitReact` clips stay on the motion-matching base: GAS's shove set has only a front shove, Lyra's are the same Epic clips. Record: `docs/health.md`, "Decision (C4)". Proof: `probes/probe_hit_react.py` (front, back, left, right).
