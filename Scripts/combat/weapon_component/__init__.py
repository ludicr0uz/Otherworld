"""weapon_component -- BP_WeaponComponent: inventory, aim, fire, reload, recoil, sprint,
block, stance, body pose weights.

build.build_weapon_component() is the entry; it declares the variables and
authors BeginPlay (inventory.py) and Tick (tick.py). Tick calls one
_author_* fragment per concern, each in its own module:

  common      _prop, trace defaults, muzzle location (shared fragments)
  vars        BP_WeaponComponent's member variables that had no constant, named
              once: name, pin type, default (uebp/vars.py)
  dead        the dead gate at the head of Tick: an owner who is Dead or at
              0 HP gets none of it; the aim, zoom and camera are let go
  local       the local gate, after the dead gate: LocalPC (this machine's
              controller of the owner, every poll's self) and LocalInput; the
              keys and the view run only where the owner is locally controlled
              (net/CLAUDE.md, "Input"); the first local frame caches the look
              scales and pins the listener
  aim         resolve the aim point every frame (camera trace, muzzle trace)
  use         the use key: the sights key on an item with no sights -> Using /
              UsePressed (and the one poll of that key, which ads aims a gun
              on). KINDS lists what a use does (today: the stick, and a
              hot blade)
  torch       use's stick kind: a press at a campfire lights a stick that
              Burns; a Lit one is held out while Using (FireWard, written on
              every arm), its AimPose swapped for its UsePose
  cauterize   use's hot-blade kind: a press with a Hot item in hand takes
              the bleed off the player, by the tag its spec grants
  ads         the two aim keys (shoulder, sights) -> Aiming/SightAiming/AimZoom
              (the sights key aims only while it is not Using); the zoom, the
              scope's look slowdown, and the aim-walk flag handed to the
              movement component
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
  breath      SwayRate copied off Held (behind IsValid); the hold breath key
              down the sights: Breath, BreathHeld, Winded and BreathScale
  sway        down the sights: the view drifts on two slow sines (the control
              rotation is turned by the change), at SwayRate, steadied by the
              stance and BreathScale
  steady      down the sights: write the owner's health component's Steady
              (SightBlend > 0.01), which refuses the flinch, so a hit leaves
              the view on the target; re-equip over a flinch already playing
  sight_pitch down the sights: write the anim BP's AimPitch (the view's pitch
              x SightBlend), which tips the upper body and the gun onto the aim
  support_hand  down the sights: write the anim BP's SupportHand (SightBlend)
              and SupportPoint (HeldSupportPoint), which hold the left hand on
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
  headshot    the headshot stamp: HeadshotTime, when a round or a thrown
              blade last struck a head (the HUD's X round the reticle)
  surface_impact  a pellet that hit something with no health: BP_BulletImpact,
              off the health cast's failed arm, at the blood's transform
  inventory   equip, drop, BeginPlay loadout (each issued item into its slot)
  slot_nodes  the slot fragments' shared shapes: loops, SlotItems[c], fits()
  slot_moves  1-9 ask for a slot (SlotRequest), Q for the bag's next item; the request (the hand's
              item home, the asked one up) and the HUD's drag (MoveFrom/To)
  slot_sync   last before the refresh: SlotItems rebuilt from each item's
              Slot, UNPLACED items placed (a weapon in its weapon slot
              before the bag), EquippedIndex, HasRoom, refresh
  interact    the interact key acts on ONE thing in reach: the candidate
              nearest AimPoint, the point the reticle rests on. KINDS lists
              what can be interacted with (today: an item, which is picked
              up, and a campfire, which heats the blade in hand)
  pickup      interact's item kind: the Dropped items it offers, and the take
              of the one kept into the bag, detached from what it was left in
              (a body a thrown blade struck); a Lodged blade taken with empty
              hands goes to the hand
  heat        interact's campfire kind: the fires it offers while the held
              item Heats (the knife, the axe), and what makes that item Hot
              for HEAT_S (the item's own Tick cools it: combat/heat.py)
  ammo        reload and dry fire
  (sounds)    Sound/sound_weapons.py and sound_items.py: the component's own
              sounds, and an item's as a slot move handles it (HandledItem)
              or it is used up; Sound/sound_world.py: the listener at the
              character, the breath of a spent sprint
  punch       empty hands: the fire key throws a punch (MM_Attack_01 into the
              upper-body slot); the blow is a short sphere sweep a moment later.
              The swing and the blow are written once, for a Strike
  knife       a Melee item held: the fire key slashes (behind the fire gate,
              beside the Consumable branch); punch.py's swing and blow on the
              KNIFE Strike, playing A_KnifeSlash
  hot_blow    what the knife stage's blow takes (BlowDamage): the strike's
              damage, doubled with a Hot item in hand off a body tagged
              FearsFire (the wendigo)
  chop        the knife stage's blow on something with no health: with an item
              that Chops in hand (the axe) and a tree under it, chips, a count
              on that tree, and every third blow a BP_Wood beside the trunk
  light       an item that Lights held (the matches): the fire key burns one
              piece of wood from Inventory into CampfireClass on the ground
              in front of the player (behind the fire gate, after Melee)
  throw       the throw key held: the predicted arc on BP_ThrowArc; clicked:
              the wind-up, then the release: the item leaves hand and
              inventory
  throw_launch  where a throw leaves from and how fast, as pure pins: at
              AimPoint, pitched so its curve passes through the point the
              reticle rests on; out of the item's reach, tipped over the view
  throw_ready the arm cocked (ThrowReadyAnim held in the slot), and an item
              with ThrowGrip (the knife) moved into it, by the blade, while the arc
              is drawn, and the re-equip that brings it down, called off
  throw_windup  the click plays the skin's throw clip on from the ready
              pose's moment and holds the release until its hand lets go
              (ThrowWinding, ThrowDueTime)
  throw_flight  the item in the air flies the arc's curve, tumbling end over
              end, and lands as a Dropped item; a melee weapon leaves the hand
              squared up to the throw, so it spins forward, edge first
  throw_strike  what the flight struck, for an item with a ThrowDamage (the
              knife, the axe): a body is wounded (more in the head) and
              bleeds, and keeps the item, set on the model and attached to
              the bone it struck (a trace on along the blade's line); a
              tree within reach keeps it, lodged point or bit first; a pick-up
              either way
  consume     the fire key on a Consumable: send the GAS use event, spend it,
              and spend the press so it cannot fire what is equipped next
  wear        clothing: the fire key on a garment (a Consumable with a
              ClothingSlot) wears it, into Worn[slot], swapping out what was
              there; TakeOffSlot (the I panel's ask) takes one off into the bag,
              or into the hand or bag slot a drag dropped it on (TakeOffTo)
  wear_drag   WearRequest (the I panel's drag onto the worn grid): a slot's
              garment is worn from wherever it is carried
  drop_request  DropRequest (the I panel's drag released outside the
              inventory): a slot's item or a worn garment is set down on the
              ground ahead, as the drop key sets the held one down
  asks        what a screen asks, one custom event each (combat/ask_consts.py):
              AskSlot, AskMove, AskTakeOff, AskWear, AskDrop raise the request
              the Tick serves, in place of the HUD writing it
  loot_take   AskLootTake(Body, Index): the loot window's take, with its
              refusals (dead, no body, no room, no such row)
  save_exit   AskSaveExit and the countdown it starts (ExitPending, ExitAt,
              ExitDue): the owner stands still, a hit calls it off; first in
              the upkeep, on every copy
  recoil      view turn, kick, recovery
  shot_noise  the shot's noise for the wanderers (ShotVolume + a cone)
  sprint      the sprint key handed to the movement component (C++, which
              sprints, latches and spends the stamina), and its answers
              copied into Sprinting, SprintSpent, SprintAhead and Stamina
  block       the guard: Blocking = block key AND stamina AND not sprinting
              (what a block does to a swing is npc/block.py)
  stance      crouch/prone toggles -> Stance, handed to the movement
              component (UE's crouch at two heights, and its speed), and
              the footsteps' StepVolume/StepNoise
  carry       Lowered, once a frame: sprinting, or a gun that no aim key,
              guard, shot or reload is holding up (the ready pose is off)
  ready_pose  restart the ready pose after it is interrupted; re-equip on the
              frames Lowered changes (the pose's edge)
  tick        the Tick that calls all of the above

BP_WeaponComponent event graph:

  [BeginPlay] --> cache Character + Mesh
              --> attenuation listener on the capsule
              --> spawn BP_Shotgun, BP_Pistol, BP_Knife, BP_Axe, BP_Matches and
                  BP_Stick into Inventory
              --> Equip(0)

  [Tick] --> Branch owner Dead or at 0 HP                    --> nothing below runs
         --> Branch WasInputKeyJustPressed(LeftMouseButton) --> Fire
                                        (or, if Held.Consumable, use it:
                                         a garment is worn, food eaten;
                                         if Held.Melee, slash with it;
                                         if Held.Lights, light a campfire;
                                         or, with empty hands, punch)
         --> Branch IsInputKeyDown(MiddleMouse), no sights   --> use the held item
                                        (a stick at a campfire: light it;
                                         a burning stick: hold it out)
         --> Branch WasInputKeyJustPressed(Q)               --> the bag's next item
         --> Branch WasInputKeyJustPressed(G)               --> drop held
         --> Branch WasInputKeyJustPressed(E)               --> interact with the one
                                                                thing nearest the
                                                                reticle (an item:
                                                                pick it up)
         --> Branch IsInputKeyDown(V)                       --> cock the arm and draw
                                                                the throw arc, which
                                                                ends on AimPoint;
                                                                on a click, wind up
                                                                (V shuts the Fire gate)
         --> Branch IsValid(ThrowWinding) AND due           --> let go: throw held
         --> Branch IsValid(Thrown)                         --> carry it along the arc;
                                                                where it strikes, a
                                                                blade wounds a body or
                                                                lodges in a tree
         --> Branch TakeOffSlot >= 0                        --> that garment off,
                                                                into the bag

  Tick also resolves the aim every frame, before the trigger is even looked at,
  because the reticle depends on it:

    camera -> LineTrace -> AimPoint      what the crosshair is resting on
    muzzle -> LineTrace -> AimPoint      can the gun actually reach it?
                                         if not, AimPoint moves to the wall and
                                         AimBlocked goes true (the reticle stays
                                         white: the HUD no longer reads it)

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
