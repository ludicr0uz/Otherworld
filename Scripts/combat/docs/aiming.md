# Combat: aiming, and how a weapon sits in the hand

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Aiming

- **Hybrid aim, resolved every frame before the trigger is checked:**
  1. A camera trace gives `AimPoint`.
  2. A muzzle trace towards `AimPoint` sets `AimBlocked` if it stops short.

  Each shot draws **one** direction inside the accuracy cloud around `Normal(AimPoint - muzzle)`
  into `ShotDirection`; pellets fly the gun's `PelletSpreadDegrees` pattern around it. Hitscan.
- **The reticle is nailed to the viewport centre**, and turns red when `AimBlocked`. Drawing it at
  the projected `AimPoint` was tried and reverted: it slid under parallax.
  - **Down a gun's sights it is drawn only in debug mode.** The front sight's tip is the
    middle of the view there (below), so the crosshair only covered it. The HUD leaves it out
    past `SightSeat` 0.9 (`RETICLE_HIDE_SEAT`) unless `DebugOn`; the hip and the shoulder aim
    keep it (`graphics_menu/reticle.py`).
- **Two ways to aim** (`weapon_component/ads.py`):
  - `KeyAim` (right) is the shoulder aim: the camera stays on the boom and zooms
    `COMBAT.shoulder_zoom` (1.5x) on every weapon.
  - `KeySights` (middle) is down the sights: zoom is the weapon's `AdsZoom` (irons 1.5x, scope
    4x), and `sights.py` eases the camera from the boom's `SpringEndpoint` to the held weapon's
    `SightOffset` by `SightSeat`, and **turns it onto the weapon's sight line** (below).
  - `Aiming` is either key (cloud, recoil, slowdown). `SightAiming` is the sights key alone,
    never with a consumable. `AimZoom` stores the zoom being aimed at. It isn't written on
    release, so the walk slowdown's ease-out divides by the zoom being let go of.
  - The camera is written every frame, both ways. The template camera has no offset or turn
    on the boom and does not take the control rotation itself (asserted in `aim_camera`), so
    SightSeat 0 is exactly home.
  - The weapon component ticks **after the boom** (`AddTickPrerequisiteComponent`). Otherwise
    the camera is placed against last frame's boom and shimmers while strafing.
  - How far back the eye sits was tuned in PIE. At 14 cm behind the receiver, its back face
    filled a third of the screen. At 34 cm, the camera was inside the head.
- **The camera waits for the gun** (`weapon_component/seat.py`, numbers in `seat_tuning.py`).
  A gun is carried lowered, and the sights key raises it over the ready pose's 0.25 s blend. A
  camera that went to the gun on the key rode it up from the hip: the view dropped to the hand,
  then swung onto the target. So the sights are two blends:
  - `SightBlend` is the **body's**: the upper body's pitch, the sway, the steady hand. It
    starts on the key.
  - `SightSeat` is the **camera's**: where it is, which way it looks, when a scoped gun hides.
    It eases toward `SightSeated`, a latch that sets once the gun's sight line is within
    `SIGHT_SEAT_DEG` (10°) of the control rotation and clears when the key is let go. Until
    then the camera stays on the boom, looking where the player looks, and the gun rises into
    the view. From a gun already up (the shoulder aim, just after a shot) it latches at once.
  - **A latch, not the angle alone:** a reload with the sights up throws the gun off the view,
    and the camera stays on the gun through it, as it always has.
  - **Why `SightBlend` does not wait too:** the body's pitch is part of what brings the gun onto
    the view. A blend that waited for the gun would wait for itself.
  - **Letting go, everything holds until the camera is home:** the carry keeps the gun up and
    `SightBlend` keeps its target while `SightSeat > SEAT_HOLD` (0.02). Otherwise the view,
    still easing off the gun, dips with it as it lowers and as the body's pitch comes off
    (5.8° at a view pitch of -25, probed).
  - **The weapon's own zoom waits for `SightSeated`** (`ads.py`): until then the sights key
    zooms as the shoulder does. Only the scope shows it: its 4x and its glass arrive with the
    camera, not over the shoulder.
  - An item with no sight line (the knife) is seated at once.
  - `SightsForced` is the probes' stand-in for the sights key. `probes/probe_sight_raise.py`
    runs the whole raise: from a gun 70–90° off the view, the camera stays within 1.5° of the
    control rotation all the way in and out (it latches about 0.19 s after the key). With
    `--windowed` and `OW_RAISE_SHOTS=1` it saves the view with and without the crosshair.
  - A probe that holds the sights by writing variables writes `SightSeat` (and `SightBlend`,
    which the seat then holds).
- **Down the sights the view IS the gun's sight line** (`weapon_models.py`, `sights.py`):
  - Each gun has a rear sight point and a front sight tip, measured off the mesh's vertices
    (`*_SIGHT_REAR`, `*_SIGHT_FRONT`): the AK's notch and post, the pistol's blades and post,
    the SMG11's peep and post, the scope's eyepiece and objective. The shotgun has no rear
    sight, so its line skims the receiver's hump and ends on the bead.
  - `SightOffset` is the point of that line at the eye's distance (`_eye_behind`), and
    `SightAim` is the front tip. The camera looks from the one at the other
    (`MakeRotFromX`, so no roll), eased from the boom's rotation by `SightSeat`. The tip is
    therefore the middle of the view in any pose, and the shot goes to the middle of the view
    (the aim trace starts at the camera).
  - **Why not the control rotation:** the gun rides the arms. Against the control rotation it
    sat 0.4° off in the rifle pose and up to 2.3° off in the pistol's while walking, so the
    sights pointed beside the shot. The mouse still aims: it turns the control rotation, the
    body takes its yaw and (`sight_pitch.py`) its pitch, and the camera rides the gun.
  - The sight lines are not parallel to the barrel (the AK's falls 0.7° to the muzzle), so
    the view sits that far off the control rotation. Nothing reads the difference.
  - An item with no sight line (the knife: both points at its origin) keeps the boom's
    rotation (`SIGHT_LINE_MIN_CM`).
  - **The player's mesh always refreshes its bones** (`skin.wear_skin`). An unrendered mesh
    keeps its last pose, and behind the scope the body is `OwnerNoSee`: the gun would freeze
    and the view could not pitch.
  - `probes/probe_sight_align.py` measures it per gun, standing, pitched, walking, crouched
    and prone: eye, rear and front on the middle of the view within 0.02°. It holds
    `SightSeat` at exactly 1 by slowing the game (time dilation 0.0001) while it measures.
    With `--windowed` and `OW_SIGHT_SHOTS=1` it saves each gun's sight picture.
- **Down the sights the player's own head is hidden** (`weapon_component/head_hide.py`,
  `HEAD_HIDE_SEAT` in `seat_tuning.py`):
  - The eye point of a gun at the shoulder is inside or beside the head: pieces of the head
    stood in the AK's sight picture. Where the eye lands differs by gun, pose and stance, so
    it is not fixed per weapon: past `SightSeat` 0.8 the skin's head bone (`PlayerSkin.head`)
    is hidden with `HideBoneByName`, whatever is held, and shown again below it. **A new gun
    needs nothing.** A new skin names its head bone, and the build refuses one its mesh lacks.
  - Not `OwnerNoSee` (the scope's way, below): the arms and the gun are the sight picture.
  - A hidden bone is drawn at zero scale, with its children. The pose, the sockets and the
    physics bodies are untouched (`PBO_None`), so the head can still be hit.
  - It is not per-view: the body's shadow is headless meanwhile.
  - **0.8, not sooner:** the camera comes from behind, and a head hidden early is a headless
    body seen from the boom. Probed: the nearest the camera comes to a head still drawn is
    30 cm (the pistol, passing beside it), 37–52 cm on the long guns.
  - The dead gate shows it (`dead.py`), since the Tick that would no longer runs: a player
    killed down the sights leaves a corpse with a head.
  - `probes/probe_head_hide.py` raises the sights on every item in the bag that has a sight
    line, so a gun added later is covered unnamed, then kills the player down them.
- **Down the sights the aim sways** (`sway_tuning.py`, `weapon_component/sway.py`):
  - Two slow sines, 0.3° sideways and 0.2° up and down, times `SightBlend` and the stance
    (crouched 0.6, prone 0.3). It is the **control rotation** that sways, so the gun, its
    sights and the shot go together; a gun swaying under a still camera would point its
    sights where the shot does not go.
  - Each frame turns the view by the change and stores what it applied (`SwayYaw`,
    `SwayPitch`), so the mouse and the recoil work on top and letting go gives it back.
  - **Trap: `SetControlRotation` drops a change under 0.001°.** A frame's sway step is
    smaller than that at a high frame rate, so the offsets counted turns that never happened
    and the view drifted 0.13° in one probe run. A step waits until it is 0.002°
    (`SWAY_MIN_STEP_DEG`) and is then taken whole.
- **`Scoped` (sniper only) draws a scope overlay instead of the reticle, down the sights only.**
  `T_UI_Scope` is drawn as a square of the viewport height, with black side strips (in
  `graphics_menu/scope.py`).
  - It fades on `clamp((BaseFOV/CurrentFOV - shoulder) / (AdsZoom - shoulder), 0, 1)`, so the
    glass and the zoom are one animation.
  - It replaces the crosshair only past `shoulder_zoom + 0.02`: the hip and shoulder keep the
    crosshair. The slack is there because FInterpTo settles within rounding of 1.5x.
  - The sniper is **hidden past SightSeat 0.9**. The eye is behind the solid scope tube,
    which would fill the glass's hole. A dropped weapon is always unhidden.
  - The player's own body goes with it: `OwnerMesh` is `OwnerNoSee` on the same condition, so
    the arms' hold and recoil animation don't swing through the glass. OwnerNoSee rather than
    hidden, so it still casts its shadow. It is shown again whenever the camera goes home.
    Probed by `probes/probe_scope_hide.py` (the shotgun's irons hide nothing).
  - `Scoped` and `AdsZoom` are independent.
- **Down the sights, the upper body pitches with the view** (`aim_pitch.py`,
  `weapon_component/sight_pitch.py`):
  - The player's anim BP (`PlayerSkin.anim_bp`, not `ABP_Unarmed`) has `AimPitch`. Two
    ModifyBones on `PlayerSkin.aim_bones` (`Spine01`, `Spine`) each **add** half of it as a
    component-space roll, last in the chain before the output. The chest, arms, head and gun
    turn rigidly, and the camera turns with the gun (above).
  - The axis: the mesh is yawed 270, so the body faces component +Y, and `Roll(+a)` tips +Y
    **down**. Looking up by P is `Roll(-P)`.
  - The component writes `AimPitch = NormalizeAxis(ControlRotation.Pitch) × SightBlend`, cast
    to the player's anim BP class. The hip and shoulder aims stay level.
  - Probed in PIE: at view pitch 0 / +30 / −40 / −80, the view direction in weapon space was
    (1, 0, 0) within 0.1°. With the pitch not scaled by SightBlend, the gun matched the view to
    0.1°. At the hip with the view at +30, `AimPitch` read 0.
  - The anim updates before the component ticks, so the gun trails a fast vertical flick by one
    frame.
- **Down the sights a hit plays no flinch** (`weapon_component/steady.py`, `docs/health.md`):
  the view rides the gun, so anything that takes the arms takes the aim. A reload still does.
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
- **Accuracy: two separate mechanics, every number per gun** (`GUN_ACCURACY` in
  `weapon_specs.py`, copied onto each weapon; `weapon_component/accuracy.py`):
  - **The cloud** decides where a shot lands. Once a frame, behind an `IsValid(Held)` Branch:
    `AimSpread = SpreadDegrees × (sights ? 0 : shoulder ? SpreadShoulderScale : 1) ×
    (prone ? SpreadProneScale : crouched ? SpreadCrouchScale : 1)`. Down the sights it is
    exactly zero, and `VRandCone` returns the direction itself for a zero cone.
  - The shot's draw is **stored** in `ShotDirection` before the pellet loop: the cone is pure, and
    read per pellet it would give the shotgun's pattern a new centre per pellet.
  - **The reticle is the cloud.** `ReticleSpread = DegTan(AimSpread) / DegTan(CurrentFOV/2)`, a
    fraction of half the viewport width (UE's FOV is horizontal). The HUD pushes the four ticks
    out by `ReticleSpread × W/2`, capped at `RETICLE_SPREAD_MAX` (`graphics_menu/reticle.py`).
  - **Recoil** moves the view, never the shot: `RecoilScale` = the same shape with
    `RecoilShoulderScale`/`RecoilSightsScale` and `RecoilCrouchScale`/`RecoilProneScale`.
  - Probed in `-game` with the shotgun: standing hip `AimSpread` 3.0, `RecoilScale` 1,
    `ReticleSpread` 0.0524 (FOV 90); with the CDO's `Stance` written to 2, 1.65 / 0.5 / 0.0288.
- **Recoil:**
  - The view kicks up by `RecoilPitch × RecoilScale` and sideways by ±`RecoilYaw × RecoilScale`.
    `RecoilYaw` is a quarter of `RecoilPitch` on every gun (asserted). Both are charged to
    `RecoilDebt`/`RecoilYawDebt` and repaid with `FInterpTo`.
  - Only `recoil_recovery_fraction` (0.7) of the recovery reaches the view, so bursts climb.
  - **Never use `AddPitchInput`/`AddControllerPitchInput`.** They are scaled by `InputPitchScale`,
    which the mouse-sensitivity setting writes. `_author_turn_view` does Get/Set
    `ControlRotation` instead.
  - Draw the sideways kick **once** into `RecoilYawKick`, because `RandomFloatInRange` is pure.
  - Turn the view **before** writing the reduced debts.

## The carry: a gun rides lowered

`weapon_component/carry.py`, numbers in `carry_tuning.py`, checks in `verify/carry.py`,
in game `probes/probe_carry.py`.

- **A gun's ready pose plays only while something holds the gun up.** Otherwise the slot is
  stopped and the locomotion (idle, walk, jog) comes through the upper-body blend with the gun
  in the right hand, as it always has while sprinting. No new clip: the packs have no
  armed-carry jog.
  `Lowered = Sprinting OR (gun AND NOT prone AND NOT (Aiming OR Blocking OR RaiseForced OR
  SightSeat > SEAT_HOLD OR now < Held.NextFireTime + CARRY_RAISE_HOLD_S))`, written once a
  frame behind `IsValid(Held)`.
  - Prone keeps the gun up: the crawl's arms pull along the ground, and the stand-in shot
    origin below is measured standing (crouched it is about 20 cm high).
  - `Aiming` is either aim key, so over the shoulder and down the sights both raise it.
  - A shot and a reload both write `NextFireTime`, so both raise it, and it stays up 1.5 s
    after it could fire again.
  - A gun is an item that is neither `Melee` nor `Consumable`: the knife and the food keep
    their hold poses.
  - `RaiseForced` is the probes' stand-in for an aim key.
  - The sight camera holds it up too (`SightSeat > SEAT_HOLD`), until it has left the gun.
- **The pose follows `Lowered` on its edge** (`ready_pose.py`): `Lowered != PoseLowered` sets
  `NeedsRefresh`, and the equip plays or stops the slot. The keepalive after a flinch asks
  `Lowered` too.
- **The shot is not delayed.** It leaves on the frame of the click, before the gun is up. So
  while `Lowered`, the wall check and the pellets start not at the muzzle (at the knee,
  pointing at the ground) but where the muzzle is about to be: `CARRY_GRIP` in the body's
  frame plus `Held.MuzzleOffset` (`carry._author_shot_origin`, one `SelectVector` both traces
  read).
  - **Trap:** `CARRY_GRIP` is the nearer of the two ready poses' fists (the shotgun's). A
    start past the real muzzle can be inside a target at arm's length, and a trace that starts
    inside its target does not stop on it.
  - The first frames after the click the gun is on its way up and the real muzzle is used
    again: an automatic's second round starts from a muzzle part-raised.
- Jogging, the barrel swings with the arm: about 90° below the horizon to 20° above it,
  median 56° below (probe).

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
  - **A model gun is seated by its measured outline** (`weapon_models.py`): the AK's and the
    Val's `Grip` and `TriggerGuard` boxes are their real pistol grips, measured off the meshes'
    vertices. Those grips are 2.6–2.8 cm thick, thinner than the primitive guns' 4 cm, so the
    fist is looser on them: the furthest wrapping joint is 3.4–3.5 cm off, just inside the
    3.5 cm limit. A thinner grip than these needs the limit or the ready pose revisited, not
    a fatter box. The SMG11's grip is 3.2 cm thick but 6.8 cm front to back (its magazine runs
    up it); its furthest joint is 3.2 cm off.
  - **The Quaternius shotgun has a straight stock** (`Shotgun_3`): no pistol grip, and its
    guard hangs under the wrist. The ready pose is a pistol grip's, with the index 4.5 cm
    above the fist's centre, so no fist on the wood reaches the guard: the `Grip` box is the
    wrist and the receiver's back belly (furthest joint 3.4 cm off), and the index lies along
    the receiver 4.1 cm above the guard. Its row carries `trigger_reach` 4.5 for that check
    (`SHOTGUN_TRIGGER_REACH_CM`); the others keep 2.5. The pistol (`Pistol_1`) fits like the
    rest: 2.9 cm, index 1.7 cm off.
- **The weapon is rigidly attached and never rotated on its own.** Aiming it per frame was tried
  and reverted. `face_the_camera()` makes the body follow the camera's yaw instead.
- **Known limits:**
  - There is no aim offset. Only down the sights does the gun pitch (the spine turns, see
    Aiming), so at the hip and on the shoulder it stays level.
  - The legs play the unarmed gait, because strafe blend spaces can't be authored from Python.
- **Lesson:** three static "fixes" in a row agreed with themselves and shipped a sideways gun.
  When reasoning disagrees with the screen, instrument a `-game` run.
