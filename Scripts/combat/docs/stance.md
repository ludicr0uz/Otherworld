# Combat: sprint, blocking, crouch, prone and the body poses

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Sprint

- 900 cm/s while stamina lasts: 4 s from full, refilling at 12/s. The pack runs at 600.
- The fire gate refuses while sprinting.
- Authored **without a Branch**. `SelectFloat` picks the speed and the stamina rate, and one
  write applies each.
- **Sprinting drops the ready pose** by stopping the slot, so `ABP_Unarmed`'s run comes through.
  It is edge-triggered: `Sprinting != PoseSprinting` sets `NeedsRefresh`. Level-triggering it
  restarts the montage every frame and the weapon strobes.
- `BaseSpeed` is cached from the character at BeginPlay (600). Never hardcode it.

## Blocking

- **Hold F to guard, armed or not** (`weapon_component/block.py`):
  `Blocking = KeyBlock down AND Stamina > 0 AND NOT Sprinting`, stored once a frame after the
  sprint block. It never reads `Held`, so empty hands block too. The fire gate refuses while
  it is set.
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
  after the sprint block.
- **Both low stances are UE's own crouch.** `allow_crouch()` turns on
  `NavAgentProps.bCanCrouch` (the template ships it off) and walking off ledges while crouched.
  The movement component shrinks the capsule (half-height 60 crouched, 40 prone, from 90) and
  keeps the feet where they were. The camera boom hangs off the capsule, so the view drops with it.
  - **The engine sizes the capsule only when a crouch starts.** Changing between crouch and prone
    therefore uncrouches for a frame when the crouched capsule is at the other height, then
    crouches again. Probed in PIE: 90 → 60 → (90) → 40 → (90) → 60 → 90.
  - **The prone height can't be below the capsule radius (35).** The engine clamps a crouch to
    the radius, so the height would never match and the stance would re-crouch every frame. The
    verifier asserts it.
  - **Speed:** crouched, the engine reads `MaxWalkSpeedCrouched` instead of `MaxWalkSpeed`. The
    stance writes it as `BaseSpeed ×` 0.45 or 0.2, so sprint's and aiming's writes don't apply
    while low.
- **Footsteps:** `BP_FootstepComponent` has `StepVolume` (the `PlaySoundAtLocation` volume) and
  `StepNoise` (multiplies the noise reach, which is already proportional to speed). The stance
  writes them onto the player's component every frame: 1/1 standing, 0.5/0.5 crouched, 0.3/0.35
  prone. The wanderers keep 1.0. A crouched step carries 12 m × 0.45 × 0.5 = 2.7 m; a crawl
  under a metre.
- **The footstep ground test is `NavMovementComponent.IsMovingOnGround`.** It used to be
  `Character.CanJump`, which is false while crouched, so every low step would have been silent.
  (`CharacterMovementComponent.IsMovingOnGround` isn't callable; the one a class up is.)
- **The body crouches and lies down** (see Body poses), so the down-the-sights camera follows
  the gun down too.
- **Known gaps:**
  - Space does nothing while low: UE refuses a crouched jump.
  - The camera drops in one frame (no boom lag).

## Body poses (`body_pose.py`, `weapon_component/pose_weights.py`)

- **Procedural, because no clip exists.** The only crouch clips are `MM_Unarmed_Crouch_*` in the
  experimental MoverExamples plugin (not enabled, another skeleton); there is no prone or guard
  clip anywhere. Each pose is a set of Transform (Modify) Bone nodes in the player's anim BP,
  every one with its **Alpha wired to a weight**: `PoseCrouch`, `PoseProne`, `GuardArms`,
  `GuardGun`. A weight of 0 skips its nodes.
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
