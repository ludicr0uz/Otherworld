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
  sound_mix   each sound's SoundClass on its waves, and the game's sound mix
  sound_states  the sounds of a state or an item: the heartbeat at low
              health, the breath of a spent sprint, a footfall's rustle in a
              bush, a thrown axe's kill by the head, an item's own takes
              handled and used up
  wear        clothing: the wear behind the Consumable tap (Server_Wear), the
              take-off the I panel asks for (TakeOffSlot), served with
              authority, Worn and ClothingSlot's defaults
  asks        what a screen asks of the weapon component: an event per action
              (none an RPC yet), the loot take's refusals and what it moves,
              save and exit's countdown, freeze and call-off
  bullet_impact  BP_BulletImpact: the chips and dust, the seeded layout, and
              the fire graph spawning it off the health cast's failed arm
  body_setting  the one setting that names the player's body
              (asset_pipeline/player_body.py), and everything that follows it
  skins       every generated character's material: an instance of the
              Meshy master wearing its own maps (not the grey default)
  hit_bodies  the physics bodies fitted to each model, measured ray by ray
              against the mesh; a pellet that strikes no body does nothing
  tracer      debug mode's pellet tracer: drawn off the trace's own hit result
  loot        the corpse loot roll on a counted kill (loot/roll.py)
  player_death  a player's death on a server: the gear shed onto the body, the
              respawn at a random PlayerStart, neither in standalone
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
  breath      the sway's per-gun rate (SwayRate, copied off Held behind
              IsValid) and the held breath: numbers, bind, variables, graph
  damage      health is the server's: TakeHit and what it writes, what
              replicates, OnRep_Health, the Tick's server-only parts and its
              death latch, the kill's credit, no blow writing health itself
  look        what another machine's copy poses by: the three replicated
              variables and no more, Server_SetLook, the component
              replicating, the report on a change, the mirror, HandPose
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
  movement    the player's C++ movement component: the reparented character,
              its numbers, and the aim-walk flag the graph hands it
  sprint      the sprint's two ends in the graph: the key handed to the
              movement component, its answers copied back; the rates
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
  record      the inventory's record (M18): what replicates and to whom, the
              server alone issuing, serving and writing, a client's picture
              of it (ViewRow, ViewTrim)
  shot        the shot and the reload as server requests (M19): the Server
              events, the pellets traced only in Server_Fire, the owning
              client's prediction off authority, the counters and the view
  strike      melee, the guard, the fire held out, the throw and the take as
              server requests (M20): the five Server events, what each asks
              first, a blow pending and an item let go only in its event, the
              client's predicted swing, what an item in the world replicates
  fire        fire and heat as server requests (M25): the four Server events,
              and how Lit and Hot reach a client (the record's columns, the
              hand's flags, the picture's row)
  slots       the inventory's slots: each item's Slot and WeaponKind, the
              component's slot variables and number keys, the issued items'
              slots, the sync before the refresh, the keys' requests
  pickup      interact's item kind: the take runs once, after the search, on
              the kept target cast to an item, with room in the bag, and
              detaches it from what it was left in
  world_items an item in the world is the server's: the drop key asks, the
              server sets it down, and an item lying Dropped replicates
  relevancy   what the server sends and how often (A2): the rows on the
              class defaults, the item's dormancy and its wakes
  glimmer     the glimmer over an item on the ground: MPC_ItemGlimmer and
              M_ItemGlimmer, the sprite on the item and the ammo pickup, the
              Tick step on the base and on each child with its own Tick;
              is_glimmer_node
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
  headshot    the headshot stamp: HeadshotTime's default, and its two writes
              (a pellet's wound, a thrown blade's), each the game's time for
              a bone of the head and nothing otherwise
  fx          the fight as everyone sees and hears it (M21): each cosmetic's
              Fx_/Multicast_ pair, its gate, the counter, the client's
              predictions, the headshot stamp's RepNotify; nodes_of, in_fx,
              calls, predicts for the sections whose nodes moved into a pair
  shot_hits   a shot's impacts told once (A4): the notes, FlushShotHits,
              Multicast_ShotHits and its loop over Fx_PelletHit
  server_anim the one IsDedicatedServer branch of the player's and each
              wanderer's anim graph (A4), and what its server arm may hold
"""

SECTIONS = (
    "anim_blueprint", "weapons", "grip_fit", "audio", "sound_mix", "sound_states", "health", "weapon_inputs", "install",
    "player_body", "body_setting", "blood", "bullet_impact", "hit_reactions", "damage", "ragdoll", "skins", "hit_bodies", "dead", "aiming", "carry", "look", "sights", "near_clip", "head_hide", "sway", "breath", "steady", "aim_pitch", "support_hand", "body_pose", "stance_clips", "block", "movement", "sprint", "stance", "accuracy", "punch", "knife", "axe", "chop", "light", "torch",
    "hold_pose", "shotgun_pose", "throw", "throw_aim", "throw_melee", "throw_strike", "headshot", "fx", "shot_hits", "server_anim", "interact", "slots", "record", "shot", "strike", "fire", "pickup", "world_items", "relevancy", "glimmer", "heat",
    "settings_and_tuning", "firing", "tracer", "consume", "wear", "asks", "drops", "loot", "player_death", "noise", "combat_trace",
)
