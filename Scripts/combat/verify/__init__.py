"""combat.verify -- reads the saved combat assets back and checks them.

Run through Scripts/verify_weapons_and_combat.py, which calls each module's
run() in SECTIONS order and prints the PASS/FAIL summary.

One module per area, mirroring the builder: a change to combat/<x>.py is
usually checked in verify/<x>.py or the module named for the same feature.
Each check_* function is one section and is self-contained: what it reads it
either loads itself or imports from fixtures (assets several sections share),
and it never relies on a variable another section left behind.

  common      check(), the PASS/FAIL ledger, pin/graph/component readers
  fixtures    shared loaded assets (health, weapon component, characters, ...)
  anim_blueprint  weapons  grip_fit  audio  health  weapon_inputs  install
  player_body  blood  hit_reactions  ragdoll  aiming  settings_and_tuning
  firing  consume  drops  noise  combat_trace
  bullet_impact  BP_BulletImpact: the chips and dust, the seeded layout, and
              the fire graph spawning it off the health cast's failed arm
  hit_bodies  the physics bodies fitted to each model, measured ray by ray
              against the mesh; a pellet that strikes no body does nothing
  tracer      debug mode's pellet tracer: drawn off the trace's own hit result
  loot        the corpse loot roll on a counted kill (loot/roll.py)
  sights      the two aim keys, each weapon's eye point and sight line, the
              sight camera: where it goes and the line it is turned onto
  near_clip   the camera's near plane: Config/DefaultEngine.ini sets it to
              NEAR_CLIP_CM, once, in the engine's own section
  head_hide   down the sights the player's own head is hidden: the Branch on
              SightSeat, the hide and the show, and the dead arm's show
  carry       a gun rides lowered: Lowered's formula, the pose edge on it, and
              both ready-pose plays gated by it
  sway        the sight sway: its numbers, and the graph that turns the view
              by the sway's change before storing it
  steady      down the sights a hit plays no flinch: the health component's
              Steady gate, and the weapon component's write of it
  aim_pitch   down the sights the anim BP pitches two spine bones by AimPitch,
              which the component writes from the view pitch x SightBlend
  support_hand  down the sights the left hand holds the gun: the anim BP's
              Two Bone IK onto a point in the right hand's space, its weight
              and pose written by the component from SightBlend and
              HeldTwoHanded
  body_pose   the crouch, prone and guard poses: the anim BP's weighted
              ModifyBones match body_pose.pose_plan, the plan replayed on the
              skeleton lands where each pose says, the component's weights
  stance_clips  the crouch, crawl and kneel clips: the stance blends in the
              AnimGraph, the crouch down with the feet planted, the crawl on
              the ground, the kneel down for the stretch it is held over
  dead        the dead gate at the head of the weapon component's Tick, and
              what the dead arm lets go of (fixtures keeps that arm out of wg)
  block       the guard: its key, the Blocking stance, the fire gate refusing
              (and FireWard, fire held out, which only starts false)
  sprint      the sprint's latch: spent at zero Stamina until the key is let go
  stance      crouch/prone: keys, the character may crouch, the Stance toggle,
              the crouch it drives, the footsteps' volume and reach per stance
  accuracy    the per-gun cloud and recoil factors: the table, the weapons'
              variables, AimSpread/RecoilScale/ReticleSpread, the shot's draw
  punch       empty hands: the press gate, the clip, the sweep and the blow
  knife       the knife: the item, the slash clip, the loadout, the press
              behind the fire gate, the swing and the blow; is_melee_*
  axe         the axe: the item, its model in the fist, the loadout
  chop        chopping a tree: BP_Wood, who Chops, the stage off the knife's
              blow (the tree test, the count, the stored landing point, the
              spawn); is_chop_node
  light       the matches and lighting a campfire: BP_Matches, who Lights,
              the loadout, the branch off the fire gate, the wood spent, the
              ground trace and the spawn; is_light_trace
  torch       the stick and the use key: BP_Stick's two models and its own
              burn-out, the torch poses, the loadout, Using/UsePressed off the
              sights key (which then does not aim), the light at a campfire,
              FireWard, the raised pose's swap
  hold_pose   every hold pose's arms; A_HoldItem / A_HoldKnife: hands, fist,
              who holds them
  shotgun_pose  A_AimShotgun: the rifle pose but for the thumbs, where they
              point and sit on the shotgun, the grip unchanged
  interact    the interact key: its idle state, the probe's press, the reach,
              the ranking by AimPoint, a walk that only remembers
  pickup      interact's item kind: the take runs once, after the search, on
              the kept target cast to an item, with room in the bag, and
              detaches it from what it was left in
  heat        the heated blade: who Heats, M_HotMetal and each item's
              instance, the glow and the cooling on the item's own Tick, the
              interact key's campfire kind, the use key's cauterising, the
              doubled blow on a body tagged FearsFire
  throw       the throw: its key, BP_ThrowArc, the predicted arc, the click,
              the clip's wind-up, the tumbling flight on the same curve;
              is_throw_trace, is_throw_play, launch_nodes
  throw_aim   where a throw is sent: at the reticle's point, a melee weapon
              pitched to pass through it; the ready pose held while the key
              is down, and the clip playing on from it; is_ready_node
  throw_melee a melee weapon's throw: the knife's and the axe's flat, fast
              arc and forward spin, and the release squaring them up to it
  throw_strike  what a thrown blade strikes: who has a ThrowDamage, where it
              went into the body (the two body traces), the wound (the head's
              multiplier) and its blood, the body it stays in (the attach
              to the bone), the tree it lodges in and how high, the pose it
              is left in, the fall it skips; is_strike_node
"""

SECTIONS = (
    "anim_blueprint", "weapons", "grip_fit", "audio", "health", "weapon_inputs", "install",
    "player_body", "blood", "bullet_impact", "hit_reactions", "ragdoll", "hit_bodies", "dead", "aiming", "carry", "sights", "near_clip", "head_hide", "sway", "steady", "aim_pitch", "support_hand", "body_pose", "stance_clips", "block", "sprint", "stance", "accuracy", "punch", "knife", "axe", "chop", "light", "torch",
    "hold_pose", "shotgun_pose", "throw", "throw_aim", "throw_melee", "throw_strike", "interact", "pickup", "heat",
    "settings_and_tuning", "firing", "tracer", "consume", "drops", "loot", "noise", "combat_trace",
)
