# Future refactor: the camera leads, the gun follows

Status: planned, not started. Written 2026-10-14.

## Why

Down the sights, the camera is currently placed **on the gun**. Each frame, `weapon_component/sights.py`
puts it at the held gun's eye point (`SightOffset`) and turns it down the gun's sight line (towards
`SightAim`). The sights are on the reticle by construction, but the view has no source of its own. It
inherits everything the skeleton does: motion matching, Foot Placement and Leg IK, the spine tip,
the idle's breathing. It also depends on update order.

That order broke on `Lvl_Horde_Survival`. On about one frame in seven, the hand was posed **after**
the weapon component had placed the camera. Walking with the sights up, the gun left the crosshair
by up to 2.5° (the camera was 3.4 cm off the eye point). On `Lvl_Forest_1000m` the same code missed by
0 on every frame. Frame rate was the same on both maps. Evidence: `probes/probe_sight_lag.py`.

**The stopgap is in place.** The weapon component ticks after the owner's mesh as well as after the
camera boom (`sights._author_tick_order`). The weapon verifier checks the rule. `probe_sight_lag.py`
(run `--windowed`) reads 0 on both maps. This document is the long-term fix: the view must not
depend on the pose at all.

## The design

### 1. One native component owns the aim view

Add `UOtherworldAimView`, a C++ component on the player that computes this frame's ADS view once:

- **Rotation:** control rotation plus sway plus recoil, as offsets.
- **Eye position:** in the actor's own space. It is a fixed per-gun ADS eye point relative to the head
  anchor (the same anchor `sights.py` already uses), not relative to the gun.
- **Seat blend:** how far the camera has travelled from the shoulder.

It runs in `TG_PrePhysics` with explicit tick prerequisites: after character movement (so the actor
has moved), and the character mesh ticks after it. That makes the order
**input → movement → aim view → animation → camera** fixed and declared, not left to the level.

The sway and recoil math moves into it from `sway.py`, `breath.py` and `recoil.py`. Those currently
write the control rotation from the weapon component's late tick, which would leave the gun a frame
behind every recoil kick. The numbers stay in `sway_tuning.py`, `breath_tuning.py` and the gun table,
so only where the math runs changes.

### 2. A native camera manager draws the view

Add `AOtherworldCameraManager` (C++, set on the player controller). It runs after every tick group
and reads the aim view:

- It blends the shoulder camera into the ADS eye by the seat value.
- It sets the rotation and applies the zoom.

The camera then depends on nothing that animation produces.

- This deletes the camera placement in `sights.py`, the boom tick rule and the ordering bug together.
- The zoom glimpse and the cut timing from `seat.py` and `ads.py` stay as inputs.

### 3. The animation graph puts the gun on the view

Keep the gun attached to the right hand at `HandGrip_R` as now, so the grip system, the fingers and
the support hand are unchanged.

- **Target:** in the anim update, work out where the gun must be so that its sight line
  (`SightOffset` → `SightAim`) lies exactly on the view's centre line. Convert that into a right-hand
  target using the gun's known grip offset.
- **IK:** add a Two Bone IK on the right arm that takes both position and rotation from that target.
  Place it before the existing left-hand IK (`support_hand.py`). The left hand still follows the gun,
  so both hands stay on it.
- **Posture:** `sight_pitch.py`'s spine tip stays as coarse posture, so the IK only corrects a few
  centimetres and the arm never over-stretches.

The anim update reads the same aim view the camera will use, through one shared function. Both are
expressed in actor space, so anything that moves the actor later in the frame carries the camera and
the gun together.

## Entering the sights: off the reticle, then onto it

The raise becomes one curve, `GunOnSight`, from 0 to 1.

- **Key down:**
  - The camera goes to the ADS view on its own schedule: the existing zoom glimpse, then the cut.
  - The gun starts from wherever the carry or ready animation has it: low, to the right and off the
    reticle.
  - `GunOnSight` rises over the player's `SightRaise` (0.25 s built) with an ease-out. The IK blends
    the hand from the animated pose to the target. At 1 the gun is exactly on the reticle.
- **While held:** at 1, the gun is pinned to the view exactly, whatever the legs or the breathing do.
- **Key up:** it eases back to 0 while the camera returns to the shoulder.

Because the camera no longer waits for the gun, the raise is purely visual: the view is ready at
once, and the gun arrives into it. For extra feel, the curve could be a critically damped spring, so
the gun settles instead of stopping dead. That is a tuning detail on the same curve.

**Recoil.** The visual kick is a short additive offset on the gun target in view space: back and up,
then back to 0. The sights leave the reticle only for the length of the kick, by design.

## Multiplayer

Other machines run the same anim graph from the replicated look (`look.py` already mirrors it), so
remote players see the gun come up onto their aim. The camera manager only matters locally.

## Order of work

1. **Native aim view and camera manager.** Move the camera placement and the sway and recoil into
   C++, still with the gun-led look. Check on both maps with `probe_sight_lag.py`, now measuring that
   the camera is unaffected by the pose, and that sway and recoil match `probe_sight_align.py`'s
   numbers.
2. **Right-hand IK and `GunOnSight`.** Author them with Python in the weapon layers graph, the way
   `support_hand.py` already does. Then delete the camera-on-gun code from `sights.py`.
3. **Probes:**
   - At `GunOnSight` 1, walking at real speed on the horde map: the front sight is on the reticle
     within 0.02° on every frame.
   - During the raise: it starts off the reticle and closes in steadily, landing within
     `SightRaise`.
   - The IK can reach for every gun in every stance: the hand target is within arm length, checked
     for all five guns.
4. **Docs:** update `docs/aiming.md` to describe the new model.

## Main risk

A gun whose ADS eye point is far from where the arms naturally hold it, so the arm cannot reach. The
reach probe catches that. The fix is per-gun tuning of the eye point, not code.

## Notes for whoever picks this up

- `probe_sight_lag.py` must run `--windowed`. Headless (about 700 fps) the race is rare and small. With
  the mesh rule removed, a headless run missed on only 1 frame in 2110.
- `probe_sight_align.py` once failed "AssaultRifle, looking +25: AimPoint" by 0.28° against its 0.1°
  limit. It passed on reruns, with and without the mesh rule. `AimPoint` is traced from last frame's
  camera, so it is likely the same kind of ordering issue. Step 1 should remove it; confirm that it
  does.
- `probe_sight_align.py` measures with the game slowed to a ten-thousandth of real time, so it cannot
  see anything that happens within one frame. Keep a real-time probe alongside it.
