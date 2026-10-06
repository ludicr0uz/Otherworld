# Combat: sprint, blocking, crouch, prone and the body poses

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Sprint

- **The sprint is the movement component's, in C++** (`UOtherworldCharacterMovement`,
  `Source/CLAUDE.md` "Predicted movement"; `combat/player_move.py` reparents the player
  onto the class that has it and writes its numbers). The weapon component's graph
  (`weapon_component/sprint.py`) hands it the key (`SetSprintHeld`) and the tab's numbers
  (`SetPace`), and copies its answers into `Sprinting`, `SprintSpent`, `SprintAhead` and
  `Stamina`, which every other graph reads as before. The copies are the owning machine's:
  on the server, and for another player's character, ask the movement component
  (`uebp.nodes.move`). Stamina is changed only on the server (`SetStamina`,
  `SpendStamina`), and reaches the client as a correction.
- **No graph writes `MaxWalkSpeed`.** The jog is the character's `MaxWalkSpeed`; the
  component's `GetMaxSpeed` answers the sprint's speed, the aim's or a low stance's from
  the state. A write from a graph exists on one machine and is corrected by the server.
- The jog is 400 cm/s, the sprint 600 while stamina lasts: 8 s from full, refilling in 8.33 s.
- **The jog plays the jog clip** (`player_gait.py`). The body's blend space has its walk
  clips at 300 cm/s and its jog clips at 600, so at the 400 cm/s jog the player moved in a
  blend that was two thirds walk. The body's anim Blueprint now sets
  `GroundSpeed = VectorLengthXY(Velocity) x 600 / jog speed`: the jog is on the jog row, the
  aim's half speed on the walk row, and a sprint, past the last row, keeps the jog clip.
  `GroundSpeed` is therefore in the blend space's units, not cm/s. The scale is baked from
  `player_tuning.csv` by the weapons build. `probes/probe_player_gait.py` measures the foot's
  lift against each clip's.
  - **A blend space's rows cannot be moved from Python.** The game looks samples up in data
    baked by `UBlendSpace::ResampleData`, which only the blend space editor's widget calls:
    samples moved, added or reordered through `sample_data` save, but the game reads the old
    layout by index (tried: standing still played the jog clips).
  The pack runs at 600, so a sprint keeps a zombie's distance and no more.
- **The numbers are `player_tuning.csv`'s** (`player_tuning.py`: m/s and seconds), laid over
  `COMBAT` and tuned in game by the menu's PLAYER SETTINGS tab
  (`graphics_menu/player_tune_*.py`). The graph reads variables, not literals: `BaseSpeed`
  (the jog, cached at BeginPlay off the character's `MaxWalkSpeed`, which
  `player_pace.set_jog_speed` sets), `SprintSpeed`, `StaminaDrainPerSecond`,
  `StaminaRegenPerSecond` (`sprint_tuning.SPRINT_RATE_VARS`).
  `probes/probe_player_tuning.py` reads them on the live player and times the refill.
  The graph hands the four to the movement component each frame (`SetPace`), which takes
  them only with authority: as a client of a server the pace is the server's.
- **Footstep noise is per gait, as before:** its reference speed followed the jog down to 400,
  so a jog still carries 12 m and a sprint 18 m.
- The fire gate refuses while sprinting.
- **A spent sprint is latched** (`SprintSpent`, `verify/sprint.py`):
  `SprintSpent = key AND (SprintSpent OR Stamina <= 0)`, `Sprinting = key AND NOT SprintSpent`.
  Running out ends the sprint until the key is let go and pressed again; stamina refills
  meanwhile.
  - **Trap:** `Sprinting = key AND Stamina > 0` alone flips every frame at zero stamina (stop,
    regen a sliver, start, drain it). Everything gated on `NOT Sprinting` flips with it: with an
    aim key held the zoom and the sight camera twitched, and the ready pose re-equipped every
    frame.
  - `probes/probe_sprint_latch.py` shows both halves in game: with the key held
    (`SprintForced`, a probe's hand on it) the player sprints, the bar runs out, the latch
    sets and the sprint stays off, bar refilling, until the key is let go. The rule is C++
    now, so no graph check sees it.
- **Forwards only** (`sprint_tuning.py`, `SprintAhead`): `Sprinting` also needs the player to be
  steering within 60° of the way the character faces (the camera's yaw), so forward and the
  forward diagonals sprint; sideways, backwards and standing still do not, and cost no stamina.
  - It reads the movement **input** (the move's acceleration, which is what a move carries
    to the server), not the velocity, which lags a turn, against the view's yaw. It gates `Sprinting` only, never the latch: turning back with the key held resumes.
  - `probes/probe_sprint_forward.py` steers the pawn at angles and reads `SprintAhead`.
- **Sprinting drops the ready pose** by stopping the slot, so `ABP_Unarmed`'s run comes through.
  Sprinting is one way into `Lowered` (the carry, `docs/aiming.md`), which is what the pose
  follows. It is edge-triggered: `Lowered != PoseLowered` sets `NeedsRefresh`. Level-triggering
  it restarts the montage every frame and the weapon strobes.
- `BaseSpeed` is cached from the character at BeginPlay (600). Never hardcode it.

## Blocking

- **Hold F to guard, armed or not** (`weapon_component/block.py`):
  `Blocking = KeyBlock down AND Stamina > 0 AND NOT Sprinting`, stored once a frame after the
  sprint block. It never reads `Held`, so empty hands block too. The fire gate refuses while
  it is set.
- **That is the owning machine's `Blocking`.** On a server the wanderer reads the
  server's copy of the character, which writes its own (`weapon_component/holds.py`,
  M20): the guard the client reports (`Server_SetHolds`) AND the movement component's
  own stamina AND not sprinting. It replicates to the other players, whose copies pose
  the guard. `BlockForced` is a probe's stand-in for the key.
- **The hit is resolved by the wanderer that swings** (`npc/block.py`), because the melee
  writes `Health` straight onto the player's component and the swing is the only place its
  damage and bearing exist together. The controller casts the player's `BP_WeaponComponent`:
  - `Blocking AND Dot(player forward, bearing) >= cos(block_half_angle_deg)` (60°) →
    `Stamina -= block_stamina_per_hit` (20, floored at 0), `HitDamage = 10 × block_damage_scale`
    (2.5);
  - otherwise, or if the cast fails, `HitDamage = 10`. The Health write reads `HitDamage`.
  - Five blocked hits from full would break the guard, but regen (12/s) refills 24 between swings
    of one wanderer, so only a pack wears it down.
- **Probed in PIE** with `Set Blocking` forced true in memory: a wanderer in front dealt 2.5 per
  swing and took stamina 100 → 80 each time. From behind, it dealt 10 and cost nothing. The
  combat trace quotes the dealt `HitDamage`.
- **The guard has a pose** (see Body poses): fists up with empty hands, a pistol, the SMG or a
  consumable; the gun raised across the body with a two-handed gun (`BP_WeaponItem.TwoHanded`).
- **Known gaps:** no HUD cue beyond the stamina bar, and a blocked hit still flinches.

## Crouch and prone (`weapon_component/stance.py`)

- **`Stance` is one int** (0 stand, 1 crouch, 2 prone), toggled by tapping C or Z, and set to
  standing while `Sprinting`. It is picked with `SelectInt`s, no Branch, and written once a frame
  after the sprint block, then handed to the movement component (`SetStance`): the crouch
  travels with each move as the engine's own flag and prone as one of ours, so the owning
  client predicts the capsule and the speed and the server makes the same ones.
- **Both low stances are UE's own crouch.** `allow_crouch()` turns on
  `NavAgentProps.bCanCrouch` (the template ships it off) and walking off ledges while crouched.
  The movement component shrinks the capsule (half-height 60 crouched, 40 prone, from 90) and
  keeps the feet where they were. The camera boom hangs off the capsule, so the view drops with it.
  - **The engine sizes the capsule only when a crouch starts.** Changing between crouch and prone
    the component therefore uncrouches and crouches again at the other height, within the one
    movement step (it used to take a frame standing: 90 → 60 → (90) → 40).
  - **The prone height can't be below the capsule radius (35).** The engine clamps a crouch to
    the radius, so the height would never match and the stance would re-crouch every frame. The
    verifier asserts it.
  - **Speed:** crouched, the component moves at the jog × 0.45, prone × 0.2
    (`CrouchSpeedScale`, `ProneSpeedScale`), whatever the sprint key or the aim say.
- **Footsteps:** `BP_FootstepComponent` has `StepVolume` (the `PlaySoundAtLocation` volume) and
  `StepNoise` (multiplies the noise reach, which is already proportional to speed). The stance
  writes them onto the player's component every frame: 1/1 standing, 0.5/0.5 crouched, 0.3/0.35
  prone. The wanderers keep 1.0. A crouched step carries 12 m × 0.45 × 0.5 = 2.7 m; a crawl
  under a metre.
- **On another machine's copy of the player** nothing toggles `Stance`: the mirror writes it
  each frame from `GetStance(owner)`, the movement component's answer, and the capsule
  there is sized in C++ from the replicated crouch and `bProne`
  (`weapon_component/look.py`; `Scripts/net/CLAUDE.md`, "Other players' characters").
- **The footstep ground test is `NavMovementComponent.IsMovingOnGround`.** It used to be
  `Character.CanJump`, which is false while crouched, so every low step would have been silent.
  (`CharacterMovementComponent.IsMovingOnGround` isn't callable; the one a class up is.)
- **The body crouches and lies down** (see Body poses), so the down-the-sights camera follows
  the gun down too.
- **Known gaps:**
  - Space does nothing while low: UE refuses a crouched jump.
  - The camera drops in one frame (no boom lag).

## The crouch and crawl clips (`stance_clips.py`)

- **On the adventurer the low stances are clips**, from the Quaternius Universal Animation
  Library (CC0; `asset_pipeline/import_quaternius.py` retargets every UAL clip onto the
  adventurer, into `/Game/Sourced/Quaternius/UAL/Adventurer01`). `PlayerSkin` names four (the fourth is `search_kneel`, below):
  `crouch_idle` (`Crouch_Idle_Loop`), `crouch_walk` (`Crouch_Fwd_Loop`) and `prone_crawl`. The
  packs have no crawl and no prone idle: the crawl is the face-down `Swim_Fwd_Loop` (a two-armed
  pull and a frog kick), and lying still is that clip held at 0.5 s (arms ahead, legs straight).
- **Where:** between the locomotion state machine and both its readers (the aim slot and the
  upper-body layered blend's base): `TwoWayBlend(PoseCrouch)` then `TwoWayBlend(PoseProne)`,
  each B a still/walking `TwoWayBlend` by `Move = clamp(GroundSpeed / 60, 0, 1)`. The aim
  layer, the hit slot and the procedural poses all apply on top.
- **The crawl's hips lie 7.5 cm under the root,** so `body_pose` lifts them: to 16 cm by
  `PoseProne`, and 15 cm more by `ProneMoving` (`PoseProne × Move`), because the kick drops the
  knees 28 cm under the hips. The verifier samples the clip with both lifts.
- **A held gun needs no correction.** The aim layer blends in mesh space over four spine joints,
  so the chest comes out propped between the crawl's face-down chest and the aim's upright one,
  with the arms and head level. The procedural prone's 60° chest tip, carried over, put the
  hands 2 cm off the ground (`probes/probe_stance_clips.py` caught it); without it they hold
  the shotgun 33 cm up, as far apart as standing.
- **Rates:** the crouch walk covers ~55 cm/s and plays at 2× (the most before it reads as a
  scurry; the feet slide at the crouch's 270), the crawl at 1.5×.
- **The kneel over a searched body** is a third blend on top of those two:
  `TwoWayBlend(PoseKneel, B = Evaluate search_kneel at KneelTime)` (`Fixing_Kneeling`). It is
  evaluated because the clip kneels, works and stands again: `pose_weights.py` runs
  `KneelTime` up and back down the working stretch (`KNEEL_FROM_S`..`KNEEL_TO_S`) and eases
  `PoseKneel` from the component's `Searching` (written by the HUD's loot window,
  `Scripts/loot/CLAUDE.md`) at `KNEEL_BLEND_SPEED`, slower than a stance. Not while prone.
  `PoseKneel` is not one of `POSE_WEIGHTS`: no ModifyBone reads it.
- **This module owns every TwoWayBlend and sequence node in the player's AnimGraph,** so a rerun
  removes them all and rejoins the locomotion. The weapons build strips them before anything
  compiles the anim BP (`unpatch_stance_clips`), because rerunning the import regenerates the
  clips and leaves the old players empty, which does not compile.
- **The mannequin fallback** (and an adventurer before the import) has no clips: `PlayerSkin`
  leaves the four fields `None` and the stances stay procedural, below.

## Body poses (`body_pose.py`, `weapon_component/pose_weights.py`)

- **Procedural where no clip exists:** the guard always, and the crouch and prone on a rig
  without the stance clips. The only stock crouch clips are `MM_Unarmed_Crouch_*` in the
  experimental MoverExamples plugin (not enabled, another skeleton). Each pose is a set of
  Transform (Modify) Bone nodes in the player's anim BP, every one with its **Alpha wired to a
  weight**: `PoseCrouch`, `PoseProne`, `GuardArms`, `GuardGun`. A weight of 0 skips its nodes.
- **Where:** between the aim pitch's `LocalToComponent` and its two spine bones. Guard first (so
  the prone hip turn carries the guarded arms), then crouch, then prone, then the aim pitch.
  `patch_body_pose` runs after `patch_aim_pitch`, whose rerun deletes every ModifyBone; a body-pose
  node is told apart by its driven Alpha.
- **Every turn is stated as what it does** (`_between(a, b)`: "swing the thigh's downward line
  forward 90°") in the component frame (forward +Y, left +X, up +Z), then written as a
  `MakeRotator`. Nothing depends on bone axes, so the mannequin fallback gets the same poses
  (`PlayerSkin.pose_bones` names the bones per rig).
  - Crouch: thighs 90° forward, shins 45° back, feet flattened, lower spine 20° forward and the
    chest 20° back so the gun stays level. The hip drop (52 cm) and the half-lead back are the
    two leg turns **replayed on the skeleton's leg**: the textbook `L1(1-cos A)+L2(1-cos S)` left
    the feet 4 cm up.
  - Prone: hips turned face down and lowered to 16 cm, chest propped 30°, then both clavicles
    and the neck turned back up 60° so the gun and the eyes are level again.
  - `GuardArms` **replaces** the upper arms and forearms (component space): elbows before the
    ribs, fists before the chin. `GuardGun` turns the chest 60° left and 15° back, and the neck
    by the inverse.
- **Two turns keep a gun in both hands:** one bone above both arms (the chest), or both
  clavicles about the left-right axis (their pivots lie on that axis). Anything else pulls the
  hands apart. The verifier replays each pose on the reference skeleton and asserts it.
- **The weights live on the anim instance.** The component eases each one with
  `FInterpTo(current, target, dt, 12)`: crouch and prone from `Stance`, the guard from
  `Blocking` and `HeldTwoHanded`. `HeldTwoHanded` is copied from `Held.TwoHanded` behind an
  `IsValid` Branch, because the weights are computed on empty-handed frames too.
- **Probed in PIE:** prone put the hips at 14 cm and the head at 38 cm (capsule 40), crouch the
  head at 101 cm (capsule 60). With `Set Blocking` forced true in memory, the shotgun gave
  `GuardGun` 1; with its `TwoHanded` cleared in memory, `GuardArms` 1.
- **Looking at a pose:** spawn a `SkeletalMeshActor` with the anim BP, write the weight on the
  anim class's CDO, `set_update_animation_in_editor(True)` (the property refuses
  `set_editor_property`), play the ready pose with `play_slot_animation_as_dynamic_montage`, and
  capture in a later job (see Looking at a character).
