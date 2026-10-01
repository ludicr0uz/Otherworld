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
- **Two ways to aim** (`weapon_component/ads.py`):
  - `KeyAim` (right) is the shoulder aim: the camera stays on the boom and zooms
    `COMBAT.shoulder_zoom` (1.5x) on every weapon.
  - `KeySights` (middle) is down the sights: zoom is the weapon's `AdsZoom` (irons 1.5x, scope
    4x), and `sights.py` eases the camera from the boom's `SpringEndpoint` to the held weapon's
    `SightOffset` by `SightBlend`, by **location only**. The rotation stays the boom's.
  - `Aiming` is either key (cloud, recoil, slowdown). `SightAiming` is the sights key alone,
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
    turn rigidly, so the eye at `SightOffset` stays on the sight line at any pitch.
  - The axis: the mesh is yawed 270, so the body faces component +Y, and `Roll(+a)` tips +Y
    **down**. Looking up by P is `Roll(-P)`.
  - The component writes `AimPitch = NormalizeAxis(ControlRotation.Pitch) × SightBlend`, cast
    to the player's anim BP class. The hip and shoulder aims stay level.
  - Probed in PIE: at view pitch 0 / +30 / −40 / −80, the view direction in weapon space was
    (1, 0, 0) within 0.1°. With the pitch not scaled by SightBlend, the gun matched the view to
    0.1°. At the hip with the view at +30, `AimPitch` read 0.
  - The anim updates before the component ticks, so the gun trails a fast vertical flick by one
    frame.
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
