"""weapon_component -- BP_WeaponComponent: inventory, aim, fire, reload, recoil, sprint,
block, stance, body pose weights.

build.build_weapon_component() is the entry; it declares the variables and
authors BeginPlay (inventory.py) and Tick (tick.py). Tick calls one
_author_* fragment per concern, each in its own module:

  common      _prop, trace defaults, muzzle location (shared fragments)
  dead        the dead gate at the head of Tick: an owner who is Dead or at
              0 HP gets none of it; the aim, zoom and camera are let go
  aim         resolve the aim point every frame (camera trace, muzzle trace)
  ads         the two aim keys (shoulder, sights) -> Aiming/SightAiming/AimZoom;
              the zoom, and the look and walk slowdowns it drives
  seat        down the sights: SightSeat (how far the camera has gone onto
              the gun, from the key: one motion), SightSeated (the gun is up)
              and SightLook (how far the camera has turned onto its line,
              from then), so the view stays on the target while the gun rises
  sights      down the sights: ease the camera (by SightSeat) from the boom to
              Held's SightOffset and turn it (by SightLook) onto Held's sight
              line (towards SightAim); hide a scoped weapon behind its glass
  head_hide   down the sights: the player's own head bone is hidden past
              SightSeat HEAD_HIDE_SEAT, whatever gun is held, and shown again
              off them (the eye point is inside or beside the head)
  sway        down the sights: the view drifts on two slow sines (the control
              rotation is turned by the change), steadied by the stance
  steady      down the sights: write the owner's health component's Steady
              (SightBlend > 0.01), which refuses the flinch, so a hit leaves
              the view on the target; re-equip over a flinch already playing
  sight_pitch down the sights: write the anim BP's AimPitch (the view's pitch
              x SightBlend), which tips the upper body and the gun onto the aim
  support_hand  down the sights: write the anim BP's SupportHand (SightBlend)
              and SupportRifle (HeldTwoHanded), which hold the left hand on
              the gun
  pose_weights  ease the anim BP's PoseCrouch/PoseProne/GuardArms/GuardGun
              from Stance, Blocking and Held.TwoHanded (body_pose.py's poses),
              and PoseKneel from Searching (the HUD's loot window), with KneelTime
  accuracy    once a frame: AimSpread (the shot's cloud), RecoilScale and
              ReticleSpread from Held's GUN_ACCURACY factors, stance and aim
  firing      the round and cooldown, the shot's one draw inside AimSpread
              (ShotDirection), the pellet traces around it
  tracer      debug mode: the line each pellet flew, off the trace's own hit
              result (red to an impact, blue out to the range), and a point
  impact      a pellet that connected: blood, damage, hit zones, debug readout
  surface_impact  a pellet that hit something with no health: BP_BulletImpact,
              off the health cast's failed arm, at the blood's transform
  inventory   equip, drop, BeginPlay loadout
  pickup      the pick-up key takes ONE Dropped item in reach: the one nearest
              AimPoint, the point the reticle rests on
  listener    BeginPlay: sounds fade with the distance from the character,
              not the camera (the controller's attenuation listener override)
  ammo        reload and dry fire
  punch       empty hands: the fire key throws a punch (MM_Attack_01 into the
              upper-body slot); the blow is a short sphere sweep a moment later.
              The swing and the blow are written once, for a Strike
  knife       a Melee item held: the fire key slashes (behind the fire gate,
              beside the Consumable branch); punch.py's swing and blow on the
              KNIFE Strike, playing A_KnifeSlash
  chop        the knife stage's blow on something with no health: with an item
              that Chops in hand (the axe) and a tree under it, chips, a count
              on that tree, and every third blow a BP_Wood beside the trunk
  light       an item that Lights held (the matches): the fire key burns one
              piece of wood from Inventory into CampfireClass on the ground
              in front of the player (behind the fire gate, after Melee)
  throw       the throw key held: the predicted arc on BP_ThrowArc; clicked:
              the wind-up, then the release: the item leaves hand and
              inventory
  throw_windup  the click plays the skin's throw clip and holds the release
              until its hand lets go (ThrowWinding, ThrowDueTime)
  throw_flight  the item in the air flies the arc's curve, tumbling end over
              end, and lands as a Dropped item
  consume     the fire key on a Consumable: send the GAS use event, spend it,
              and spend the press so it cannot fire what is equipped next
  recoil      view turn, kick, recovery
  shot_noise  the shot's noise for the wanderers (ShotVolume + a cone)
  sprint      sprint and stamina, and the latch that ends a spent sprint
  block       the guard: Blocking = block key AND stamina AND not sprinting
              (what a block does to a swing is npc/block.py)
  stance      crouch/prone toggles -> Stance; UE's crouch at two heights, the
              crouched speed, and the footsteps' StepVolume/StepNoise
  carry       Lowered, once a frame: sprinting, or a gun that no aim key,
              guard, shot or reload is holding up (the ready pose is off)
  ready_pose  restart the ready pose after it is interrupted; re-equip on the
              frames Lowered changes (the pose's edge)
  tick        the Tick that calls all of the above

BP_WeaponComponent event graph:

  [BeginPlay] --> cache Character + Mesh
              --> attenuation listener on the capsule
              --> spawn BP_Shotgun, BP_Pistol, BP_Knife, BP_Axe and BP_Matches
                  into Inventory
              --> Equip(0)

  [Tick] --> Branch owner Dead or at 0 HP                    --> nothing below runs
         --> Branch WasInputKeyJustPressed(LeftMouseButton) --> Fire
                                        (or, if Held.Consumable, use it;
                                         if Held.Melee, slash with it;
                                         if Held.Lights, light a campfire;
                                         or, with empty hands, punch)
         --> Branch WasInputKeyJustPressed(Q)               --> cycle equipped
         --> Branch WasInputKeyJustPressed(G)               --> drop held
         --> Branch WasInputKeyJustPressed(E)               --> pick up the one item
                                                                nearest the reticle
         --> Branch IsInputKeyDown(V)                       --> draw the throw arc;
                                                                on a click, wind up
                                                                (V shuts the Fire gate)
         --> Branch IsValid(ThrowWinding) AND due           --> let go: throw held
         --> Branch IsValid(Thrown)                         --> carry it along the arc

  Tick also resolves the aim every frame, before the trigger is even looked at,
  because the reticle depends on it:

    camera -> LineTrace -> AimPoint      what the crosshair is resting on
    muzzle -> LineTrace -> AimPoint      can the gun actually reach it?
                                         if not, AimPoint moves to the wall and
                                         AimBlocked goes true (red reticle)

  Fire: muzzle world location  -> Start
        AimPoint - muzzle      -> direction
        one draw in AimSpread  -> ShotDirection
        N pellets in a cone    -> LineTraceSingle each
        hit -> BP_BloodSplash at the impact + Health -= Damage
               (no health component: BP_BulletImpact there instead)

  A melee blow (punch.py) that finds no health goes to chop.py: the axe on a
  tree throws chips and, every third blow, spawns BP_Wood beside the trunk.

THE HYBRID AIM (why there are two traces and not one)
------------------------------------------------------
Aiming from the muzzle alone is geometrically honest and unplayable: the barrel
is below and to the side of the camera, so shots land off the crosshair, and a
player beside a wall shoots the wall while the crosshair is on an enemy in the
open. Aiming from the camera alone is playable and looks broken: the camera is
on a boom behind the shoulder, so the cone fans out from behind the player.

The camera picks *what* is aimed at; the muzzle decides whether the gun can
reach it, and the pellets then fly down that same muzzle line. The wall check is
not an extra safety net -- it is the same trace the pellets use, which is what
lets the reticle promise only hits the shot can actually make.

This is hitscan: the pellets resolve in the frame they are fired. A projectile
version would use the identical aim resolve and fire a velocity along
(AimPoint - muzzle) instead of tracing it.
"""
