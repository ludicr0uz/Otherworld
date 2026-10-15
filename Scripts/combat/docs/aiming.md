# Combat: aiming, and how a weapon sits in the hand

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Aiming

- **Hybrid aim, resolved every frame before the trigger is checked:**
  1. A camera trace gives `AimPoint`.
  2. A muzzle trace towards `AimPoint` sets `AimBlocked` if it stops short.

  Each shot draws **one** direction inside the accuracy cloud around `Normal(AimPoint - muzzle)`
  into `ShotDirection`; pellets fly the gun's `PelletSpreadDegrees` pattern around it. Hitscan.
- **The reticle is nailed to the viewport centre.** Drawing it at the projected `AimPoint` was
  tried and reverted: it slid under parallax. It is always white (it turned red when
  `AimBlocked`; the HUD no longer reads that). A headshot draws an X round it for 0.35 s:
  a pellet or a thrown blade in one of the target's `HeadBones` stamps the weapon component's
  `HeadshotTime` (`weapon_component/headshot.py`, `headshot_tuning.py`,
  `probes/probe_headshot.py`).
  - **Down a gun's sights it is drawn only in debug mode.** The front sight's tip is the
    middle of the view there (below), so the crosshair only covered it. The HUD leaves it out
    past `SightLook` 0.9 (`RETICLE_HIDE_LOOK`: the camera turned onto the sight line, which
    is only once the gun is up) unless `DebugOn`; the hip, the shoulder aim and the gun on
    its way up keep it, since the crosshair is the mark the gun rises to
    (`graphics_menu/reticle.py`).
- **Two ways to aim** (`weapon_component/ads.py`):
  - `KeyAim` (right) is the shoulder aim: the camera stays on the boom and zooms
    `COMBAT.shoulder_zoom` (1.5x) on every weapon.
  - `KeySights` (middle) is down the sights: zoom is the weapon's `AdsZoom` (irons 1.5x, scope
    4x), and `sights.py` eases the camera from the boom's `SpringEndpoint` to the held weapon's
    `SightOffset` by `SightSeat`, and **turns it onto the weapon's sight line** by `SightLook`
    (below).
  - `Aiming` is either key (cloud, recoil, slowdown). `SightAiming` is the sights key alone,
    and only with a gun in hand: an item whose `HasSights` is set, which the guns' rows alone
    do (`weapon_items.py`). The knife, the axe, the matches, wood, food and the stick have no
    sights: with one in hand the sights key is the use key (`weapon_component/use.py` writes
    `Using`, which this block reads) and does not aim at all; only the shoulder key aims
    them (`probes/probe_item_no_sights.py`). `AimZoom` stores the zoom being aimed at. It isn't written on
    release, so the walk slowdown's ease-out divides by the zoom being let go of.
  - The camera is written every frame, both ways. The template camera has no offset or turn
    on the boom and does not take the control rotation itself (asserted in `aim_camera`), so
    SightSeat 0 is exactly home.
  - The weapon component ticks **after the boom** (`AddTickPrerequisiteComponent`). Otherwise
    the camera is placed against last frame's boom and shimmers while strafing.
  - How far back the eye sits was tuned in PIE. At 14 cm behind the receiver, its back face
    filled a third of the screen. At 34 cm, the camera was inside the head.
  - **The pistol's eye is 25 cm behind the grip** (`PISTOL_SIGHT`), so both hands stand
    partly in the view, round the gun. At 14 cm the slide's back and two blurred thumbs were
    all of the lower view; at 30 cm the hands took too much of it.
- **A glimpse of the zoom, then a cut; only the turn waits for the gun**
  (`weapon_component/ads.py`, `seat.py`, numbers in `seat_tuning.py` and the gun's row of
  `gun_tuning.csv`). A gun is carried lowered, and the sights key raises it over the ready
  pose's blend (the gun's `AdsRaiseSeconds`, 0.25 s on every gun; `HandRaise`, taken with
  `HandPose` in `look.py`, is the equip's `BlendInTime`), from 70–95° off the view. The
  sequence is:
  1. **The zoom-in.** On the key `TargetFOV` is the weapon's own, and the zoom eases toward
     it (`FInterpTo` at the gun's `AdsZoomSpeed`, 12 on every gun) while the camera stays on
     the boom and the gun stays lowered (`SightPending`, read by the carry). `SightHeld`
     counts the seconds the key has been down.
  2. **The cut.** On the first frame `SightHeld` is past the gun's `AdsZoomInSeconds` (0.1 s
     on every gun; 0 is a cut on the key's own frame) `SightSnapped` is set: `CurrentFOV` is
     `TargetFOV`, `SightSeat` is 1 and the gun's raise begins, all on that frame.
  3. **The raise.** The gun rises into the view from below and to the right onto the
     crosshair, the camera standing still; the turn onto its line waits for it (below).
  - **The cut keeps the point aimed at** (`weapon_component/sight_cut.py`). The boom's
    camera is behind and beside the shoulder; cut to the head with the boom's rotation
    kept, the middle of the view moved by that offset and the target jumped aside (5.8°
    at 5.4 m, probed). On the cut's frame alone (`SightCut`, written by `ads.py` just
    before `SightSnapped`) the control rotation turns from the anchor onto `ViewPoint`,
    the camera trace's point kept by `aim.py` before the muzzle's trace can move
    `AimPoint`, and the camera takes that rotation on the same frame (the boom ticked
    with the old one). The mouse, the body and the gun follow the control rotation, so
    the gun rises onto the same target. From the hip the body's own turn to the new yaw
    carries the camera about 0.5° on that one frame; the next frame's trace lands on the
    point. Letting go is not turned back: the point drifts the offset back over the
    ease home. `probes/probe_sight_cut_aim.py` (from the hip and from the shoulder aim),
    `verify/sight_cut.py`.
  Letting go eases everything out at the same `AdsZoomSpeed`, the zoom-in's inverse. The
  three numbers are rows of the GUN SETTINGS tab (`sights zoom speed`, `sights zoom-in (s)`,
  `sights raise (s)`), the same default on every gun. `AdsSpeed` on the component is the
  gun's speed, taken while aiming and kept on letting go (as `AimZoom` is), so the ease out
  with empty hands is the aimed gun's; every ease here reads it.
  The sights are three values:
  - `SightBlend` is the **body's**: the upper body's pitch, the sway, the steady hand. It
    eases toward the cut at the gun's speed, and starts with the cut, as the raise does.
  - `SightSeat` is the **camera's place**: on the sights or on the boom, and with it when a
    scoped gun and the head go. It is **1 on the frame of the cut**, and the weapon's own
    zoom (`ads.py`) lands on the camera the same frame: the player is in the sights' view at
    once, and the gun is what moves. While the gun is still down the camera stands at the
    **anchor** (`SightAnchor`: the head bone, `OwnerMesh`'s, the one `head_hide.py` hides, in
    the owner's frame, taken every frame the view is off the sights and **held from the
    cut**), looking where the player looks; the gun rises into that view from below and to
    the right onto the crosshair. Letting go, `SightSeat` eases home at the gun's speed.
  - **Why the anchor is held and not the live bone:** the ready pose leans the head in to the
    sights, and the head bone moves up to 1 cm a frame while the gun rises (probed, looking
    down); a camera on the live bone was carried with it, a bob under the raise. Held, the
    camera moves 0 cm a frame in the owner's frame from the cut to the latch.
  - `SightLook` is the **camera's turn** onto the gun's sight line. It eases toward
    `SightSeated`, a latch that sets once the sight line is within `SIGHT_SEAT_DEG` (10°) of
    the control rotation and clears when the key is let go. Until then the camera looks where
    the player looks, and the gun rises into the view. As it turns, the camera also settles
    from the head bone onto the gun's own eye point (`VLerp(anchor, eye, SightLook)`), the
    last few centimetres. From a gun already up (the shoulder aim, just after a shot) it
    latches at once.
  - **Why the camera does not travel:** it used to ease from the boom to the eye point over
    a fifth of a second, zooming as it went, and before that it waited on the boom until the
    gun was up. Either way the view glided, and the raise was half hidden behind the travel.
    Now the view cuts to the sights and the raise is the whole animation. The zoom-in before
    the cut is on the boom only, a tenth of a second of the zoom starting (what the glide
    had that the bare cut lost), and the cut lands the rest.
  - **Why the raise waits for the cut:** raised on the key, the gun was part-way up by the
    cut and the raise into the view was the tail of it. `SightPending` keeps the carry's
    gun lowered through the zoom-in, unless the shoulder key already holds it up: a gun on
    the shoulder key is up, and lowering it for a tenth of a second would twitch.
  - **Why the anchor and not the eye point from the key:** the eye point rides the gun, and
    the gun starts at the hip. A camera put there at once would have ridden up with it: the
    world swinging, the gun still in the view.
  - **Why the turn still waits:** a camera turned onto the gun's line from the key looked
    down at the hand, then swung onto the target with the arms. What the turn takes from the
    gun is the last few degrees only (under 1.5°, probed).
  - **A latch, not the angle alone:** a reload with the sights up throws the gun off the view,
    and the camera stays on the gun through it, as it always has.
  - **Why `SightBlend` does not wait:** the body's pitch is part of what brings the gun onto
    the view. A blend that waited for the gun would wait for itself.
  - **Letting go, everything holds until the camera is home:** the carry keeps the gun up and
    `SightBlend` keeps its target while `SightSeat > SEAT_HOLD` (0.02). Otherwise the view,
    still easing off the gun, dips with it as it lowers and as the body's pitch comes off
    (5.8° at a view pitch of -25, probed). The way home is eased, not cut: a cut back to the
    boom out of a scope would be a jolt, and the carry reads the seat on its way down.
  - An item with no sight line is seated at once.
  - `SightsForced` is the probes' stand-in for the sights key. `probes/probe_sight_raise.py`
    runs the whole raise: on the frame of the key the camera is on the boom, the zoom has
    started and the gun is lowered; the cut comes on the first frame past the item's own
    `AdsZoomInSeconds` (the pistol's is written to 0.3 s on its live item for the case),
    and on it `SightSeat` is 1, the zoom is the weapon's own, the camera is at the head bone,
    the gun's front sight is below and right of the middle of the view and the gun is no
    longer lowered; from the cut to the latch the camera moves under 0.01 cm a frame in the
    owner's frame; the gun latches about 0.2 s after the cut with its line within 10°; the
    camera stays within 1.1° of the control rotation all the way in and out. With
    `--windowed` and `OW_RAISE_SHOTS=1` it saves the view with and without the crosshair.
  - A probe that holds the sights by writing variables writes `SightSeat` and `SightLook`
    (and `SightBlend`, which the seat then holds).
- **Down the sights the view IS the gun's sight line** (`weapon_models.py`, `sights.py`):
  - Each gun has a rear sight point and a front sight tip, measured off the mesh's vertices
    (`*_SIGHT_REAR`, `*_SIGHT_FRONT`): the AK's notch and post, the pistol's blades and post,
    the SMG11's peep and post, the scope's eyepiece and objective. The shotgun has no rear
    sight, so its line skims the receiver's hump and ends on the bead.
  - `SightOffset` is the point of that line at the eye's distance (`_eye_behind`), and
    `SightAim` is the front tip. The camera looks from the one at the other
    (`MakeRotFromX`, so no roll), eased from the boom's rotation by `SightLook`. The tip is
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
  - It is not per-view: a mannequin skin's shadow is headless meanwhile.
  - **The MetaHuman's Face and its six grooms go out of their owner's view instead**
    (`OwnerNoSee`, on the same two arms; `body_parts.author_head_parts_no_see`). A groom is
    not skinned: a hidden bone does not reach its strands, and the hair stood by itself in
    front of the sight camera. `metahuman_body.py` tags the seven `HeadPart`
    (`seat_tuning.HEAD_PART_TAG`) and sets `bCastHiddenShadow` on them; the loops over the
    parts under the mannequin Branch on the tag (`ComponentHasTag`), so the body, the arms
    and the garments are never touched, and the hidden bone skips the tagged seven (a face
    with its bone hidden would cast no shadow, whatever its flag). Per view: other players
    see the whole character. Strand hair honours `OwnerNoSee` (seen in a windowed run: the
    hair is drawn carried and gone on the sights).
  - **A new component that draws the head alone** (a hat or glasses drawn on the body, which
    none is today: only the jacket, the pants and the boots have a worn mesh) takes the tag
    and `bCastHiddenShadow` where it is made, and needs nothing else.
  - The dead gate needs no line for them: its `SetOwnerNoSee(false)` is on every part.
  - **0.8, not sooner:** the camera comes from behind, and a head hidden early is a headless
    body seen from the boom. Probed: the nearest the camera comes to a head still drawn is
    30 cm (the pistol, passing beside it), 37–52 cm on the long guns.
  - The dead gate shows it (`dead.py`), since the Tick that would no longer runs: a player
    killed down the sights leaves a corpse with a head.
  - `probes/probe_head_hide.py` raises the sights on every item in the bag that has a sight
    line, so a gun added later is covered unnamed, then kills the player down them. It holds
    the Face and the grooms to the same rule frame by frame, and to being visible to
    everyone else meanwhile.
- **The camera's near plane is 2 cm, so the hands are not cut open** (`NEAR_CLIP_CM` in
  `seat_tuning.py`; `Config/DefaultEngine.ini`, `[/Script/Engine.Engine] NearClipPlane`):
  - **Why:** the eye is on the gun, and the shotgun's right thumb is 6 cm from it, in the
    view. The engine's default plane is 10 cm: it went through the thumb, and the player saw
    into the hand and out the other side. (The pistol's thumbs were cut the same way while
    its eye was 14 cm behind the grip; at 25 cm its nearest skin is 9.5 cm off.)
  - **It is the engine's plane, for every view,** read at startup. A camera component has no
    near plane of its own (`FMinimalViewInfo.PerspectiveNearClipPlane` is not set by it), and
    `r.SetNearClipPlane` is the same global. Depth is reversed-Z, so nothing far is lost.
  - At 2 cm the piece of the plane in view is 2.3 x 1.3 cm; the nearest skin in view is
    6 cm from the eye (the shotgun's right thumb).
  - `verify/near_clip.py` reads the ini line; `verify/sights.py` holds each gun's parts
    clear of the same plane. `probes/probe_sight_near_clip.py` reads the plane off the
    game's projection matrix (an ini key in the wrong section is ignored silently) and, for
    every gun with a sight line, standing, crouched and prone, finds no hand or forearm
    crossing the plane's piece in view; at 10 cm it finds the shotgun's thumb. With
    `--windowed` and `OW_SIGHT_SHOTS=1` it saves each gun's sight picture.
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
  - **Its speed is the gun's** (`SwayRate`, the `sway_rate` column of `gun_tuning.csv`, 0.5
    on every gun: the periods run at 11.2 s and 7 s). The clock advances by `dt x SwayRate`,
    so a change of rate never jumps the sway. The component's `SwayRate` is copied off
    `Held` behind an `IsValid` Branch each frame (`weapon_component/breath.py`).
- **The breath can be held down the sights** (`breath_tuning.py`, `weapon_component/breath.py`):
  the hold breath key (Left Alt, not Shift, which sprints) multiplies the sway's width by
  0.15 for up to 5 s. Run out, the player is `Winded` (the sway at 1.5x and no hold) until
  the breath has refilled, 5 s from empty; let go early, what is left can be held again at
  once. The width eases between the three (`BreathScale`, FInterpTo at 4), since a jump in
  the width is a jump in the view. `BreathForced` is the probes' key
  (`probes/probe_hold_breath.py`).
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
- **Down the sights the left hand is held on the gun** (`support_hand.py`,
  `weapon_component/support_hand.py`):
  - The gun is rigid to the right hand only. The ready pose is layered over the locomotion
    in mesh space, so the arms keep the pose's turn but hang off a spine the legs' clip
    twists, and the shoulders move apart. In the gun's own space the left hand slid 0.4 cm
    standing and 1 cm walking (probed), and down the sights the camera rides the gun, so the
    gun stood still in the view and the hand moved under it.
  - A Two Bone IK on the left arm, last in the player's anim BP's chain (after the pitch's
    ModifyBones), puts the hand at a point in the **right hand's bone space**: where the
    ready clip holds it at its start (`support_at`, sampled at build time), moved onto
    the gun's own model ("Both hands are fitted to each gun's model" below). The point is
    each gun's own, `SupportPoint` on `BP_WeaponItem`: one clip is the ready pose of three
    guns, and each has its handguard somewhere else. The joint target is the
    forearm bone itself, so the elbow stays on the side the pose has it.
  - The component writes `SupportHand = SightBlend` (the IK's weight) and
    `SupportPoint = HeldSupportPoint` (its copy of `Held.SupportPoint`, made beside
    `HeldTwoHanded`). **Only down the sights:** at the hip and on the shoulder
    the upper-body slot also plays things the left hand must be free for (a throw, a
    search), and the camera is not on the gun.
  - It eases in with `SightBlend`.
  - `aim_pitch._remove_previous` takes the IK out with its own nodes, so the build order is
    the pitch, the body poses, then `patch_support_hand`.
  - `probes/probe_sight_hands.py`: rifle and pistol, standing and walking, both hands within
    0.05 cm of still in the gun's space over 3 s; the hold off at the hip and let go after.
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
  `gun_rows.py`, copied onto each weapon; `weapon_component/accuracy.py`):
  - **The cloud** decides where a shot lands. Once a frame, behind an `IsValid(Held)` Branch:
    `AimSpread = SpreadDegrees × (sights ? 0 : shoulder ? SpreadShoulderScale : 1) ×
    (prone ? SpreadProneScale : crouched ? SpreadCrouchScale : 1) × (1 + Bloom)`. Down the sights it is
    exactly zero, and `VRandCone` returns the direction itself for a zero cone.
  - **The bloom: a burst from the hip shakes the hands** (`combat/bloom_tuning.py` has the
    numbers and the rule in Python, `weapon_component/bloom.py` the graph). Each round of an
    automatic (`Held.Automatic`: the SMG and the rifle) fired while not `SightAiming` adds
    `BLOOM_PER_SHOT` (0.12) to `Bloom`, up to `BLOOM_MAX` (1.5: the cloud 2.5 times the gun's
    own; the SMG is there after 13 rounds), and stamps `BloomShotTime`. `BLOOM_HOLD_S` (0.2 s,
    longer than either automatic's interval) after the last round it eases to zero once a
    frame (`FInterpTo`, speed 5: ~8% left half a second later), at the head of the accuracy
    block, on every machine. A round adds in `ShotFired` (the server, and single player) and
    in the owning client's prediction of the ask, so its reticle and the server's draw bloom
    alike. Down the sights a round adds nothing (and the cloud is zero there anyway). Checked
    by `verify/bloom.py`, `Scripts/dev/tests/test_bloom_tuning.py` and
    `probes/probe_hip_bloom.py` (the SMG: 2.6 -> 6.5 degrees over a burst, under 0.01 a second
    after the hold; the pistol and the sights add none).
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
  in the right hand, as it always has while sprinting. A one-handed gun still rides so; a
  long gun has a carry of its own (below).
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
- **A long gun is carried in both hands** (`carry_pose.py`, `carry_pose_consts.py`,
  `weapon_component/carry_weights.py`, `verify/carry_pose.py`): with the rifle, the sniper or
  the shotgun lowered, standing or crouched, the upper body is the Animation Starter Pack's
  rifle carry (`Scripts/asset_pipeline/CLAUDE.md`), the gun at the hip some 15 degrees under
  the horizon standing, walking, jogging and crouched, across the body at a sprint.
  - It is not a montage. In `ABP_WeaponLayers` a blend by `CarryPose` sits on the aim slot's
    **source alone** (the layered blend's base stays the stance blends' pose): a slot with no
    montage hands its source on, so the carry reaches the body from `spine_01` up through
    the blend that was already there, and the ready pose, a throw or a pick-up plays over it
    and blends back to it. No second layered blend, and the legs are the motion matching's.
  - `CarryPose -> Lowered AND HandPose == CarryFor AND NOT Stance == PRONE AND NOT Searching AND NOT
    sliding AND NOT in a traversal`; `CarrySprint -> the movement's IsSprinting`, both eased
    by `pose_weights.py` on every machine. `CarryFor` is the rifle's ready pose, which the
    three long guns share (`weapon_specs`): the pistol, the SMG, the knife and empty hands
    never carry. `Lowered` and `HandPose` already reach the other machines, so nothing new
    replicates.
  - The clip under it is the standing one or the jog's by `GroundSpeed`
    (`CARRY_JOG_FULL_CM_S`), then the sprint's by `CarrySprint`. Measured retargeted: the
    grip hand 29 cm under the ready pose's (40 at the sprint), the left hand within 3 cm of
    where the ready pose has it against the right, so no IK holds it.
  - **Crouched it is the pack's crouched pair** (`Crouch_Idle_Rifle_Hip`,
    `Crouch_Walk_Fwd_Rifle_Hip` by `GroundSpeed`, all of the walk's from
    `CARRY_CROUCH_WALK_FULL_CM_S`), blended over the standing carry by `PoseCrouch`: the
    body poses' own weight, already eased to `Stance == CROUCH` on every machine, so the
    carry changes with the body and nothing new is declared or replicated. The layered
    blend lays the slot's pose on in mesh space, so the chest leans as the crouched clip
    has it over the sample's crouched legs. Measured in game (`probe_carry.py`): the
    shotgun's barrel 14 degrees down at rest and creeping, the hands 35 cm apart against
    33 raised.
  - Prone the gun is up (`Lowered` is false). The stand-in shot origin (below) is
    unchanged.
  - A checkout without the pack has no carry: the skin's three fields are None
    (`skin._gas_skin` says so in the build's log), the variables exist and nothing weights
    them.
  - In game: `probes/probe_carry.py` (the weights, the barrel, the hands, the sprint, the
    crouch at rest, creeping and aimed) and, for another player's copy,
    `probes/probe_net_look.py`.
- **The carry runs where the keys are.** On another machine's copy of the player `Lowered`
  is the mirror's, off the replicated `LookLowered`, and the pose the equip and the
  keep-alive play is `HandPose`: `Held.AimPose` locally, the replicated `LookPose` on a
  remote copy (`weapon_component/look.py`; `Scripts/net/CLAUDE.md`, "Other players'
  characters").
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
- **Mid-flinch the shot snaps the gun up first** (`shot_snap.py`, `docs/health.md`): the
  flinch is not `Lowered`, so it is not the stand-in above. The ready pose is snapped back and
  the real muzzle read.
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
- **The game seats an item by its `Grip` component** (`grip_handle.py`), not by the two
  variables. Every held item's Blueprint (the guns, the axe, the knife, the stick, the wood,
  the matches, the consumables, the garments) has a SceneComponent named and tagged `Grip`
  under its root. It marks where the hand's grip socket is in the item's own frame: the equip
  attaches the item to the socket and sets its relative transform to the inverse of `Grip`'s
  (`weapon_component/inventory.py`, found by the tag).
  - **`GripLocation` and `GripRotation` are the seed:** what the solve below says, written by
    every build as before. Nothing in the game reads them.
  - **A build makes `Grip` from the seed when it is missing.** One that exists and still sits
    on the last build's seed was moved by nobody, so it follows the solve (a ready pose that
    changes moves the fist). One that sits anywhere else was placed by a person, and no build
    touches it again: the build logs `Grip was placed by hand (… off the solve), left alone`.
  - **`verify/grip_fit.py` measures the `Grip`, and leaves a placed one to its placer:** it
    prints that grip's measurements and holds it only to 8 cm of the fist (`PLACED_MISS_CM`).
  - **What a placed grip does not move:** the shotgun's left hand (`shotgun_hold.py` bakes
    it against the solved grip), and the knife's blade grip for the throw
    (`ThrowGripLocation`, still solved and baked).

### Placing a grip by eye

For a handle that sits a couple of centimetres off in the hand. No build, no script.

1. In the Content Browser open the item's Blueprint (`/Game/Weapons/BP_Pistol`,
   `BP_Axe`, …; the consumables are under `/Game/Survival`, the garments under
   `/Game/Clothing`) and go to its **Viewport** tab.
2. In the **Components** panel select **Grip**. The move gizmo appears where the hand's
   grip socket will be: on the player that is the right wrist, some 8 to 14 cm from the
   handle, not the palm.
3. Drag `Grip` (or type into Location and Rotation in Details). **The item moves the
   opposite way in the hand:** `Grip` 2 cm towards the muzzle puts the gun 2 cm further
   back in the fist; `Grip` 1 cm up sinks the item 1 cm into the hand. Leave its Scale at 1.
4. **Compile** and **Save**, then press Play: the next item of that kind that is equipped
   sits by the new grip.
5. Commit the `.uasset`. A rebuild keeps it.

To give a grip back to the solve, delete the `Grip` component, Compile, Save, and run the
item's build step (`UEPY_BUILD_ONLY=weapons` for a gun, `knife`, `axe`, `wood`, `matches`,
`stick`; `build_survival.py`; `build_clothing.py`): it is seeded again. Until that build,
an item with no `Grip` hangs from the wrist and logs an `Accessed None` at each equip.

### The grip nudges: the last centimetre, from inside the game

`Content/Tuning/grip_nudges.csv` has a row per held item, named by its Blueprint
(`BP_Knife`): `x, y, z` in centimetres and `pitch, yaw, roll` in degrees, in the grip
socket's frame, all zero until somebody tunes one. The row is laid over whatever the
`Grip` component gives:

    seat under the socket = inverse(Grip) * row

so the item turns about the socket (the hand) by the row's rotation and then moves by its
position. A row of zeros, or no row, is skipped: the seat is the `Grip`'s alone.

- **The running game reads it, not the build.** `UOtherworldGripLibrary` (C++,
  `Source/Otherworld/Public/OtherworldGripLibrary.h`) reads the file the first time an item
  is seated, on a server, a client and the title alike; the equip's one node is its
  `GripSeat(Item)` (`weapon_component/inventory.py`). So a number edited in the CSV is a
  relaunch and no build, and a rebuild, a re-seeded `Grip` or a new ready pose keeps it.
- **In play: the GUN SETTINGS tab's last six rows** (`grip x (cm)` … `grip roll (deg)`,
  `graphics_menu/grip_tune.py`). They are the **held** item's row, whichever weapon the tab
  shows, so hold the item, open the tab, go down to the grip rows and press Left/Right:
  0.1 cm or 1 degree a step. The item moves that frame and the CSV is written that frame;
  there is no Enter for them. Empty hands show zeros and move nothing.
- **Which way:** `x`, `y` and `z` are the socket's axes, the same frame as `GripLocation`.
  Nudge one and watch; the step is small enough to walk it.
- **A packaged build carries the file loose** (`DefaultGame.ini`,
  `DirectoriesToAlwaysStageAsNonUFS`, `Tuning`), so it ships the tuned rows.
- **What a nudge does not move:** what a placed grip does not (the shotgun's left hand, the
  knife's blade grip for the throw). And a nudge made in play on a server's client reaches
  that machine's table alone until the others are launched again on the written file.
- **The format in Python** is `combat/grip_nudges.py` (`read_table`, `write_table`), held by
  `Scripts/dev/tests/test_grip_nudges.py`; that a row moves the item by exactly the row, and
  that a step on the tab moves it and writes the file, is `probes/probe_grip_nudge.py`, which
  points the game at a scratch file (`SetGripNudgeFile`) so the tracked one is not written.

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
  - **The shotgun has a wooden stock with a semi-pistol swell** (`SM_Shotgun_02`): no
    pistol grip, and its guard hangs under the receiver ahead of the wrist. The ready pose
    is a pistol grip's, with the index 3.5 to 4 cm above the fist's centre, so no fist on
    the wood reaches the guard: the `Grip` box is the front of the wrist, just behind the
    guard (furthest joint 2.8 cm off), and the index lies along the receiver 3.3 cm above
    the guard. The fist is not down on the swell, 4 cm further back, where a hand would
    also sit: the left arm (49 cm, its IK does not stretch) then has the pump out of reach. Its row carries `trigger_reach` 4.5 for that check
    (`SHOTGUN_TRIGGER_REACH_CM`); the others keep 2.5. The pistol (the 1911) fits like the
    rest: furthest joint 2.9 cm off; its index lies 3.8 cm above the guard's bar, inside
    the pistol pose's 4.5 (`PISTOL_POSE_TRIGGER_REACH_CM`).
- **Both hands are fitted to each gun's model** (`gun_hold.py`, `hand_seat.py`), at the
  build, for every row of `weapon_specs`: no gun's hands are placed by hand.
  - **The right hand** is the one the gun is rigid to: the grip's solve seats the model's
    "Grip" in the fist (`grip.py`, above).
  - **The left hand** is carried by the IK to the gun's `SupportPoint`, and that point is
    where the ready pose has the wrist, moved by `gun_hold.support_move()`: the rigid hand
    (its shape is the clip's; the fingers are bent afterwards, below) is brought to where its own
    finger joints and tips ride `SEAT_OFF_CM` (0.75) off the part the row names, the worst
    of them as near as it can be (`hand_seat.seat`, a descent from where the clip has the
    hand), with no joint deeper than 0.5 cm in it, none in a part of the outline beside
    it (an AK's magazine and receiver), the thumb under the sight line, and the wrist no
    further from the shoulder than the arm is long.
  - **The arm's reach is part of the seat** (`hand_seat.reached`). The IK does not
    stretch: a point further from the shoulder than the arm is long is never reached, and
    the hand stops short along the line from the shoulder. The pump-action's first seat
    was 3.7 cm past the arm and its live wrist read 3.69 cm short of the point. So every
    trial move is cut to what the arm makes before its fit is measured, and the point
    saved is one the hand arrives at (live: 0.07 to 0.15 cm off on the five guns).
  - **What a row says** (`support`, a `<GUN>_SUPPORT` of `weapon_models.py`):
    `dict(part="Handguard")`, a part of the gun's outline; `dict(box=((lo), (hi)))`, a box
    measured off the mesh where the outline has no such part (the Val's handguard is the
    front of its "Receiver"); `under="Barrel"` keeps the thumb under that part's top
    rather than the sight line (the shotgun); `fist=True` grows the part to hold the right
    hand's three wrapping fingers, for a pistol held in both hands (the 1911, the MAC-11).
    A row with no `support` stops the build.
  - **What it did** (the worn body, cm from the part, before and after): the AK's hand hung
    1.9 to 7.5 under its handguard with a knuckle 1.9 inside the magazine, now 0.3 to 4.2
    on it; the Val's 1.5 to 7.1 under, now -0.4 to 1.9; the pistol's and the SMG's left
    fingers lay through the right hand's (-2.8 to 3.2 of the fist), now -0.5 to 2.0; the
    shotgun's is -0.75 to 5.0 (its hand is wider than the pump is deep, and its thumb is
    held under the barrel).
  - **A new gun's hands:** give its row `support=` and its line of
    `weapon_models.GUN_HOLDS` (the outline and the support by the Blueprint's name, which
    is how a running game finds them), build, and read the `[GUN] <name>: the left hand's
    point moved ...` line. `verify/gun_hold.py` holds both hands of every row to its
    model (the left: on its part, within 5.25 cm, in no part beside it, thumb under the
    sight line, the arm long enough; the right: no joint more than 1.5 cm in any part,
    thumb 2 cm under the sight line; `verify/grip_fit.py` has its fingers on the Grip),
    and `probes/probe_gun_hands.py` reads the live hands down each gun's sights, the wrist
    against the point first. A hand that cannot be fitted says so there: move the row's
    box, or the grip (a fist further back takes the handguard out of the arm's reach).
- **Every check above measures the hidden mannequin; the drawn MetaHuman is measured by
  `probes/probe_drawn_grip.py`** (15 Oct 2026). The grip is fitted on the UEFN mannequin
  and the gun hangs off its hand. The drawn Body's wrists are pinned to the mannequin's,
  place and turn, by hand IK goals in its retarget (`asset_pipeline/hand_goals.py`,
  `asset_pipeline/CLAUDE.md`), so the gun sits in the drawn hand; the elbows give the
  difference in arm length. The probe reads both bodies' wrists, elbows and hand turns,
  and every finger and thumb against each gun's real meshes (GeometryScript, signed distance;
  `probes/grip_report.py` makes a finger's riding points into its penetration and gap a
  0.75 cm skin off its axis), for each gun standing, walking, crouched, sprinting
  (lowered) and down the sights at pitch +25/0/-25, with two close pictures each
  (`--windowed`; `Saved/Screenshots/MacEditor/grip_*.png`) and the tables in
  `Saved/grip_report/drawn_grip.md`. Before the pin the drawn wrists were 2.5 to 6.6 cm
  off the mannequin's. With it (15 Oct 2026): wrists 0.00 cm and hands 0.0 degrees off in
  every gun state, elbows 3 to 6 cm off (the left 9 to 11 cm down a long gun's sights).
  Lowered, a pistol's left hand hangs free (50 to 70 cm off), as meant.
- **The drawn fingers are fitted on the MetaHuman's own hand against each gun's real mesh**
  (15 Oct 2026; before it they were the retarget of the mannequin's, up to 2 cm in or off
  the grip). `/Game/Sourced/MetaHuman/A_DrawnGrip` holds three frames a gun at one a
  second (hold, sights, carry; `drawn_grip_consts.GUNS`' order), both hands' fingers, and
  `ABP_MetaHuman_Retarget_UEFN` lays it over the retarget's fingers, each from its root in
  local space: the right by `GripRight`, the left by `GripLeft` over a blend of the gun's
  three frames by the sights' and the carry's weights (`drawn_grip_graph.py`). The weapon
  component writes them, finding the gun by the ready pose in hand
  (`weapon_component/drawn_grip.py`): the right hand is on the gun whenever it is held,
  the left raised, down the sights and in a long gun's carry, never on a lowered pistol,
  through a reload's clip or over a searched body.
  - **The fit** (`drawn_grip.py`, pure; `drawn_grip_bake.py` in the editor, run by
    `Scripts/build_drawn_grip.py`, about 7 minutes, so not a step of the weapons build,
    whose `drawn_grip` step lays the clip over the fingers) reads the
    wrists the probe captured (`drawn_grip_capture.json`; the wrists are pinned, so they
    are the mannequin's) and the gun's meshes as one solid (`drawn_grip_mesh.py`). Each
    finger is closed by `finger_fit.close` with a press weight of 400 (a point in the gun
    costs as much as one 20 cm off it); a finger whose own knuckle is in the gun first
    turns its metacarpal (a cup about the curl axis up to 15 degrees, else a lift away
    from the surface up to 25), the turn chosen by the deepest point, then the knuckle,
    then the fit. The thumb swings onto the gun, and out of it the least either way. The
    right index is drawn to the trigger (a segment per gun, `TRIGGER`), its pad on it.
    A handgun's left fingers are fitted on the gun and the fitted right fingers together.
    **The pistol's right thumb is laid along the frame** (`drawn_thumb.py`, 15 Oct 2026):
    swung onto the gun, the retarget's thumb stood up behind the slide, its tip 1.4 cm
    over the slide's top and in front of the rear sight down the sights. A gun named in
    `THUMB_REST` has its right thumb turned at its root (two swings and a roll past the
    turn that points it at the rest, within 45 and 60 degrees) and its outer joints bent,
    searched on a grid and then in halving steps, so that its tip lies on the rest (a
    segment on the frame's left side under the slide, z 4.2), nothing of it is pressed
    into the gun or the fitted fingers, and no point's skin rises over
    `THUMB_CEILING_CM` (6 cm, 1.5 under the slide's top); the least turn and the least
    bend win a tie, so it lies straight rather than curled. On the 1911 its top fell from
    +8.9 cm to +4.4 (the skin's +5.1), its tip 0.66 cm off the rest's line; the SMG's
    right thumb is beside its receiver, not over its sights, and is still swung.
    One frame holds every hand placement of its state (the carry's four clips), and the
    fingers are kept out of the gun in all of them.
  - **The clip plays retargeted** (Taro's mesh against the skeleton's reference pose:
    root `CLAUDE.md`, "Skeletons and retargeting"), so the bake keys each frame, reads it
    back as played and corrects the keys until the played pose is the fit's (0.13 degrees
    at worst: `drawn_grip_bake.settle`).
  - **Measured** (`probe_drawn_grip`, 345 checks since the pistol's thumb, 15 Oct 2026): no finger more than 0.3 cm
    into a gun raised or down the sights but the left knuckle of the shotgun's little
    finger (0.44) and the SMG's index (0.38), which no turn of the metacarpal clears at
    the pinned wrist (`PRESSED_CM_BY_GUN`); every finger within 1 cm of the surface
    there. Carried, within 1.5 cm in and 2 cm off (crouched, the shotgun's left little
    stands 1.7 off: one frame serves the four carry clips), but the left thumb, which the
    carry's clips hold 6 to 9 cm off along the stock (`CARRY_OFF`). The right index's
    pad is 0.01 cm (the 1911) to 1.14 (the Val) off the trigger's face, the shotgun's
    2.45 (its trigger is 5 cm under the hand: `TRIGGER_NEAR_CM_BY_GUN`).
  - **No fingertip IK at run time**: the wrists are pinned and the right hand is rigid on
    the gun, so the baked fingers do not drift; the carry's spread is the one place they
    move against the gun, and stays inside the bounds above.
  - **Not done:** a frame of its own for the crouched carry; the reload's fingers are
    Lyra's on the left (the left hand lets go for the clip), the fitted grip's on the right.
- **A gun's fingers are bent onto its model** (`finger_pose.py`, `finger_fit.py`), for
  the guns `weapon_models.GUN_FINGERS` names (all five: the AK, the Val, the shotgun,
  and the 1911 and the SMG, "The pistols" below). The hands above are rigid pieces of a clip made for Lyra's rifle:
  on the AK the left fingers hang up to 2.9 cm off the handguard and the right's up to
  2.4 off the grip; the Val's left joints start up to 0.8 cm inside its receiver.
  - **Each such gun is held in a clip of its own**, `/Game/Weapons/Anims/A_Aim<Blueprint>`
    (`A_AimAssaultRifle`, `A_AimSniperRifle`; the `finger_poses` build step, before
    `weapons`): the row's ready pose frame for frame, but the bent fingers' bones hold one
    key on every frame. It is the item's `AimPose`, which the equip already plays and the
    look already replicates, so no graph changed. A row keeps both: `pose` (the shipped
    clip, which the grip, the left hand's seat and `two_handed` are solved in) and `aim`
    (what is played; the same clip for a gun that is not fitted).
  - **What bends:** the left hand's four fingers (the hand where the seat has it), the
    right hand's middle, ring and little, and the left thumb. The right index is the
    clip's (it is at the trigger) and so is the right thumb.
  - **How** (`finger_fit.close`, pure, `dev/tests/test_finger_fit.py`): a finger bends
    about one axis, the normal of the plane its own joints lie in. Its three joints take
    the bend that lays its riding points (the two outer joints, the tip, the middles of
    the two outer bones) nearest `SKIN_CM` (0.75, the seat's number) off the model's
    boxes, a point pressed in counted four times one as far off; a joint opens at most
    20° from the clip and closes 45/60/50°, never back past straight. A finger that still
    has fewer than two points on the model keeps the clip's pose (the AK's left index,
    past the front of its handguard). The left fingers lie on what the hand holds and
    the parts beside it; the right's on every part. The thumb is not curled: one swing at
    its base towards the part, stopped a skin off it or under the seat's ceiling.
  - **Measured:** every bent finger's riding points 0.43 to 1.44 cm off the model (1.98
    to 2.86 before on the AK), the left thumbs 0.8 cm (4.6 and 2.8 before).
  - **Tried first:** closing the knuckle until something touched, then the next joint.
    The tip of an opened finger touches before the finger is round the part, and the
    outer joints ended at their opening limit.
  - **What it does not do:** the fingers are fitted with the left hand at its seat, which
    it has only down the sights; at the hip the hand is the clip's and the fingers are
    those of the seat. The carry's clips are untouched. A fist that closes moves its
    middle, so `verify/grip_fit.py` measures the grip in the row's `pose`.
  - **The carry** asked `HandPose == CarryFor` (the rifle's ready pose); a fitted gun's
    HandPose is its own clip, so the component has `CarryAlso`, every fitted clip that
    is the rifle's pose (`finger_pose.carry_clips`: not a pistol's), and
    the test is `== CarryFor OR CarryAlso contains` (`weapon_component/carry_weights.py`).
  - **A new gun:** its Blueprint's name in `GUN_FINGERS`, build, and read the
    `[GUN] <name>: built ... its fingers bent onto the model` line (each finger's bend,
    and its nearest and furthest point before and after). `verify/finger_pose.py` holds
    the saved clip to the model and to the fit's own arithmetic;
    `probes/probe_gun_hands.py` reads the live fingers and that the gun is still carried.
  - **The shotgun** (`A_AimShotgun`, the name its keyed pose had until C3; nothing
    retires that name any more). Two things it needed that the rifles did not:
    - Its magazine tube and barrel run through its pump, so `gun_hold.beside` (the parts
      that share no volume with what is held) dropped them, and the little finger, 1.4 cm
      behind the wood, had nothing to lie on. Where a row holds a named part of the
      outline (not a measured box cut out of one, as the Val's, nor the fist), the left
      fingers lie on every part (`finger_fit.through`). The AK's handguard shares no
      volume with a part, so its clip did not change.
    - Bounds of its own (`verify/finger_pose.BOUNDS`, `probe_gun_hands.FINGER_BOUNDS`).
      The pump is 4.8 cm deep under a hand shaped for 7.5, and the thumb under the
      barrel's top holds the knuckles 1.6 to 4.6 cm below the wood. Measured: the seven
      fingers' riding points 0.17 to 2.66 cm off the model (-0.75 to 3.84 before; live
      0.13 to 2.60), the left index, middle and little at their 20 degree opening limit,
      the left thumb swung 30 degrees to 0.78 cm off the wood (5.7 before). Opening
      the outer joints 40 degrees was tried by hand: the middle then lies 0.47 to 1.49,
      but the index's best fit has one point on the wood and is refused; the limits are
      the rifles' still.
  - **The pistols** (`A_AimPistol`, `A_AimSMG`: the rows whose `support` says `fist`,
    held in Lyra's pistol pose with the left hand closed over the right). What they
    needed:
    - The left fingers lie on the right fist, not the model. The seat's fist
      (`gun_hold.support_box`) is the grip with the pose's right fingers on it, which
      stand 0.3 to 2 cm off the grip; the fit closes those first, so the left fingers
      are laid on the fist as closed (`finger_pose.fist`: the grip and the right hand's
      three wrapping fingers bent by `finger_fit.wrapped`, skin and all, 0.8 cm
      shallower in front and at the fingertips), and on the parts beside it. It is
      worked out off the row's `pose` whichever clip is measured, so the pose and the
      clip are measured against one thing.
    - Their clips are not the carry's: `CarryAlso` is `finger_pose.carry_clips()`, and
      `probe_gun_hands` holds a lowered pistol to `CarryPose` 0.
    - `verify/finger_pose` no longer asks `two_handed` of a fitted row (that is the
      rifle's pose), only a `support`.
    - Measured, saved clip: the 1911's six fitted fingers 0.63 to 1.15 cm off (0.12 to
      1.96 before), its left index left as the pose has it (0.85 to 2.79: it stands 2 cm
      in front of the closed fist and cannot be laid on it within the 20 degree
      opening); the SMG's seven 0.46 to 1.48 (-0.24 to 2.25 before); the left thumbs
      swung 30 and 26 degrees to 0.76 and 0.79 cm off the fist (5.2 before). Live
      (`probe_gun_hands`): 0.62 to 1.20 and 0.43 to 1.45. The rifles' bounds hold both.
- **The shotgun is held in the rifle's ready pose** (C3; until then a whole pose keyed
  for it; its fingers alone are bent since, above), and its left hand has a point of
  its own (`shotgun_hold.py`).
  - **Why:** the rifle pose stands the left thumb up the handguard, far under the AK's and
    the Val's sight lines (14 cm above the grip). The shotgun's line skims the receiver
    8.5 cm above the fist: as the clip has it the thumb's tip is 4.2 cm ABOVE the line, a
    finger beside the bead, and the hand is at the pump's back end (a bar 4.8 cm deep,
    `weapon_models.SHOTGUN_PUMP`), one joint 1.4 cm inside the wood.
  - **What moves:** the shotgun's `SupportPoint` (the IK's point, in the right hand's
    space) is the pose's moved by `gun_hold.support_move()`, as every gun's: straight down
    until the thumb is under the barrel's top, then `hand_seat.seat`'s descent to where the
    fingers' joints fit the pump best within the arm's reach (2.6 cm forward, 2.2 left
    and 5.4 down). The hand is moved as one piece; its shape is the clip's. The barrel
    lies only 2.2 cm over the pump's wood, so the thumb holds the hand low: its joints
    ride up to 5.0 cm off the wood.
  - **Only down the sights** (`SupportHand` is `SightBlend`): at the hip and on the
    shoulder the hand is the clip's own. `probes/probe_shotgun_hands.py` reads the live
    joints against the pump both ways; with `--windowed` and `OW_GRIP_SHOTS=1` it saves
    pictures of both hands from round the gun (its view target is a spare item from the
    bag: a game cannot spawn a camera from Python, and moving the pawn's own detached
    camera changes nothing).
  - **The right hand is the rifle pose's**, so the grip's solve and the fist are the
    rifle's (`verify/shotgun_pose.py`); its thumb lies forward along the top of the
    stock's wrist, 3.6 cm under the sight line.
  - `probes/probe_shotgun_thumb.py` reads the live thumbs down the sights (and the rifle's,
    left where the clip has them); with `--windowed` and `OW_SIGHT_SHOTS=1` it saves the
    sight picture.
  - **Trap:** a headless editor (the warm one, `UnrealEditor-Cmd`) never ticks its world, so
    a SkeletalMesh or PoseableMesh spawned there stays in the reference pose and a
    SceneCapture of it shows nothing of a clip. Look at a pose in a `--windowed` game.
- **The weapon is rigidly attached and never rotated on its own.** Aiming it per frame was tried
  and reverted. `face_the_camera()` makes the body follow the camera's yaw instead.
- **Known limits:**
  - There is no aim offset. Only down the sights does the gun pitch (the spine turns, see
    Aiming), so at the hip and on the shoulder it stays level.
  - The legs play the unarmed gait, because strafe blend spaces can't be authored from Python.
- **Lesson:** three static "fixes" in a row agreed with themselves and shipped a sideways gun.
  When reasoning disagrees with the screen, instrument a `-game` run.
