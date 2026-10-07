"""combat -- weapons, inventory, aiming, damage and death, as Unreal Python.

Entry point: Scripts/build_weapons_and_combat.py (main() calls the build_*
functions below in dependency order). Checks: Scripts/verify_weapons_and_combat.py,
which runs the combat.verify package.

One module per responsibility. Find the owner here before opening anything;
each module's docstring says what it owns and why it is shaped that way.

DATA (constants and pure tables -- no Blueprint authoring)
  paths             /Game asset paths and generated-class paths
  health_vars, item_vars, settings_vars, burst_vars, ammo_vars, footstep_vars
                    one Blueprint's member variables each, named once: name,
                    pin type, default (uebp/vars.py). The weapon component's
                    is weapon_component/vars.py
  nodes             engine class paths the graphs name (the node paths, FN_*
                    and NODE_*, are the shared catalog: uebp/nodes/)
  tuning            keys, inventory size, CombatConfig / COMBAT, ammo, drops
                    (GUN_LOOT_TABLE, GUN_DROP_CHANCE, GUN_DROP_SEED),
                    auto fire, the consume event and health-drain tags,
                    the throw (THROW_*),
                    noise, SHOT_VOLUME_CM (how loud each gun is)
  sway_tuning       the sight sway's numbers (SWAY_*): angles, periods, the
                    default rate (SWAY_RATE, a gun_tuning column), the stance's
                    steadying, the component's variables, sway_at()
  breath_tuning     holding the breath down the sights: the key, how long, the
                    sway's scale held and winded, the variables, breath_step()
  headshot_tuning   the headshot mark: its variable's name, how long the X
                    stays up
  seat_tuning       the sight camera's seat: how near the view the gun must
                    be before the camera turns onto its line (SIGHT_SEAT_DEG),
                    SightSeated / SightSeat / SightLook / SightsForced,
                    HasSights (the
                    item flag only a gun sets), where the HUD's
                    crosshair gives way to the sights (RETICLE_HIDE_SEAT),
                    the player's own head leaves the view (HEAD_HIDE_SEAT),
                    and the camera's near plane (NEAR_CLIP_CM, set in
                    Config/DefaultEngine.ini), near enough not to cut the
                    hands open down the pistol's sights
  sprint_tuning     the sprint's direction rule: the 60 degree cone ahead a
                    sprint is allowed in, and the SprintAhead variable's name;
                    the names of the speed and stamina rates the sprint reads
  player_tuning     player_tuning.csv: jog and sprint speed (m/s), how long a
                    full bar sprints and an empty one refills (s); what the
                    menu's PLAYER SETTINGS tab saves and COMBAT is built from
  player_pace       the jog: the character's own MaxWalkSpeed, set at install
  player_move       the player's native parent and its C++ movement component (the
                    reparent), and the numbers sprint, prone and the aim-walk move by
  player_gait       the jog plays the jog clip: GroundSpeed scaled in the
                    body's anim Blueprint so the jog's speed is the blend
                    space's jog row
  carry_tuning      the carry's numbers and names: how long a shot keeps the
                    gun up (CARRY_RAISE_HOLD_S), Lowered / PoseLowered
  chop_tuning       chopping a tree: blows per piece of wood, where it lands
                    (WOOD_*), Chops and the component's Chop* variables
  throw_tuning      the throw's numbers (THROW_*): speed, the lob's angle,
                    launch point, how near a point the reticle rests on is
                    still aimed at, the arc's and the flight's gravity, dots,
                    landing, the tumble, a melee weapon's own flat fast
                    spinning throw (MELEE_THROW), a thrown blade's damage and
                    how deep and how high it lodges in a tree
                    (THROW_*_DAMAGE, LODGE_*), when the clip's hand lets go
                    and where in the clip the ready pose is taken
  difficulty        EASY / MEDIUM / SURVIVOR: labels, default, the variable
  game_state        world-scoped + health-component variable names (which live
                    on the GameMode, which moved: net/state_consts.py), debug mode,
                    the noise record, ensure_game_mode_vars()
  gun_tuning        gun_tuning.csv: the tunable stats (TUNE_STATS: column,
                    variable, label, step, minimum), which are whose
                    (columns_of: a gun's, a melee weapon's), reading and writing it
  melee_tuning      the knife's and the axe's rows of that table: their
                    throw's arc and damage, defaults under the CSV's cells
  weapon_specs      the five weapons: muzzles, icons, _weapon_specs()
  weapon_models     every gun's model: the SMG's, the rifle's and the sniper's Fab
                    ones (SMG11, AK 47, AS Val + scope), the shotgun's and the pistol's
                    Quaternius ones (Shotgun_3, Pistol_1), their muzzles and sights,
                    and the measured outline the grip and sight checks read
  camera            boom and aim-trace numbers, face/aim-the-camera patches
  knife             BP_Knife: the Fab M9 knife as a Melee item, its model
                    placement and measured outline, its blade grip for the
                    throw (knife_throw_grip), build_knife()
  axe               BP_Axe: Quaternius's Survival Pack axe as a Melee item,
                    swung through the knife's stage, and the one item that
                    Chops; build_axe()
  wood              BP_Wood: Quaternius's Survival Pack log, what a tree gives
                    the axe; an item that lies Dropped, with nothing to fire
  light_tuning      lighting a campfire: where it goes (CAMPFIRE_*), Lights and
                    the component's MatchesClass/CampfireClass/LightWood
  matches           BP_Matches: Quaternius's Survival Pack matchbox, the one
                    item that Lights; build_matches()
  use_tuning        the use key's names: Using / UsePressed / UseWas
  slot_tuning       the inventory's slots: the codes (the hand, primary,
                    secondary, pistol, melee, the bag's ten), WeaponKind, the
                    number keys, the issued items' slots, fits()
  record_vars       the inventory's record (M18): the four plain arrays the server
                    writes and the owning client is sent, HandClass for everyone
                    else, the view's events, a probe's forced asks
  shot_vars         the shot and the reload as server requests (M19): the events'
                    names, AsksSent / AsksServed (which reconcile a client's
                    predicted rounds), the server's grace on the cooldown
  lag_tuning        lag compensation for shots (M22): the cap on the rewind and
                    the allowance over the round trip; the C++ history and trace
                    are Source/Otherworld
  strike_vars       melee, the guard, the use key, the throw and the take as
                    server requests (M20): the five events' names, what the
                    owning machine reports and the server keeps, the limits
  fx_vars           the fight as everyone sees and hears it (M21): each cosmetic's
                    Fx_/Multicast_ pair by name, its parameters and its gate, the
                    five the owning client predicts, FxPlayed (a probe's count)
  item_world        an item loose in the world is a replicated actor (M20):
                    InWorld, the release's SetReplicates, a client's copy
                    hidden while the item is carried
  wear_tuning       clothing: the eight slots (WEAR_SLOTS), ClothingSlot on the
                    item, Worn / TakeOffSlot / WearItem on the component
  ask_consts        what a screen asks of the weapon component: the Ask
                    events' names and parameters, and save and exit's
                    countdown (its variables, EXIT_SECONDS)
  torch_tuning      the stick that burns: Burns / Lit / BurnOutTime / UsePose on
                    the item, how long it burns and how near a campfire lights
                    it (STICK_*), the component's StickClass/NearFire/WardItem/
                    WardCarryPose
  heat_tuning       the heated blade: Heats / Hot / CoolTime / HeatMaterial on
                    the item, how long it stays hot (HEAT_S), what its blow
                    does to a creature afraid of fire (HOT_BLOW_SCALE,
                    FIRE_FEAR_TAG), the component's BlowDamage, the glow's
                    colour, light and material parameters
  stick             BP_Stick: Quaternius's Survival Pack torch, bare and
                    burning, and its glow; its own Tick puts it out and shows
                    the one or the other; build_stick()
  knife_anim        A_KnifeSlash: the slash keyed bone by bone onto the
                    knife's hold pose (AnimationDataController)
  hold_pose         A_HoldItem / A_HoldKnife / A_HoldTorch / A_WardTorch: food
                    carried at the waist, the knife up in a fighting stance, the
                    stick carried as a torch and held out, keyed off the idle
  throw_pose        A_ThrowReady: the arm cocked while a throw is aimed, the
                    skin's throw clip stopped where its hand is furthest back
  shotgun_pose      A_AimShotgun: the shotgun's ready pose, the rifle's with
                    the right thumb over the stock's wrist, the left along
                    the pump (SHOTGUN_THUMBS), and the left hand under the
                    pump with its fingers closed on it (SUPPORT_PALM,
                    SUPPORT_FINGERS), keyed off the rifle pose

SHARED AUTHORING HELPERS
  (uebp)            node/pin/connect/set, out/then, variables, components,
                    events: Scripts/uebp/graph.py, shared by every package
  log               _log: the [GUN] log line
  noise             _author_make_noise: write the GameMode's noise record
                    (the shot and the player's footsteps call it)

ASSETS AND PATCHES
  materials         flat materials (gunmetal, wood, blood, brass, impact chip
                    and dust)
  (sound)           the Sound package: Scripts/Sound/__init__.py. The weapons
                    build runs its asset step (Sound.build.build_sound_assets)
  anim_blueprint    ABP_Unarmed: layered blends and the three slots
  aim_pitch         the player's anim BP: AimPitch tips the upper body (two
                    spine ModifyBones) so the gun follows the sights' pitch
  support_hand      the player's anim BP: down the sights a Two Bone IK holds
                    the left hand on the gun (a point in the right hand's
                    space), weighted by SupportHand; support_at()
  body_pose         the player's anim BP: guard poses, and crouch and prone where
                    the rig has no clips, as weighted ModifyBones, pose_plan()
  stance_clips      the player's anim BP: the Quaternius crouch, crawl and kneel
                    clips blended over the locomotion by PoseCrouch/PoseProne
                    and (searching a body) PoseKneel
  skin              the player's body (PlayerSkin, wear_skin)
  grip              hand-grip socket maths for holding a weapon: GripRotation
                    and GripLocation (the handle seated in the fist)
  lodge             how a thrown blade sits in the tree it lodged in, out of
                    its model: lodge_pose -> LodgeTurn, LodgePoint
  settings_savegame BP_Settings
  weapon_items      BP_WeaponItem and one child per weapon
  heat              the item's side of a heated blade: M_HotMetal (an additive
                    overlay masked along the model's own axis) and an
                    instance per item, the HeatGlow light, and the Tick that
                    cools it and shows the glow; build_heated_model()
  burst             build_burst: the actor of small pieces thrown off a hit
                    under drag and gravity (the graph both bursts below fly)
  blood             BP_BloodSplash: the droplet layout, what a body throws
  bullet_impact     BP_BulletImpact: the chips and dust layout, what the
                    scenery throws where a bullet hits it
  ammo_pickup       BP_AmmoPickup
  glimmer_tuning    the glimmer over an item on the ground: names, paths, look
  glimmer           MPC_ItemGlimmer + M_ItemGlimmer, the Glimmer sprite on an
                    item, and the Tick step that shows it while Dropped
  throw_arc         BP_ThrowArc + M_ThrowArc: the dotted arc a throw is aimed
                    with (one instanced mesh of emissive spheres)
  footsteps         BP_FootstepComponent (StepVolume/StepNoise, set by the stance)
  combat_trace      the combat trace switch: GameMode's CombatTraceOn/Off
                    console events and CombatTrace's default

BP_HealthComponent (health_component wires the fragments together)
  health_component  variables, defaults, the Tick's death branch
  damage            health is the server's: the TakeHit event every blow calls
                    (hit, owner_instigator), what replicates, OnRep_Health
  server_pose       a dedicated server refreshes the bones of every body with
                    health: its hit bodies and muzzles are where clients see them
  respawn           spawn numbering, world-floor net, respawn band and delay
  replacement       the dead wanderer's replacement: the wait, the point, the spawn
  death             kill count, shells, ragdoll collapse, corpse, player death
  player_kill       a player killed by another player: the credit, PlayerKillCount
                    on the killer's PlayerState (the damage itself is damage.py's,
                    the same for a player as for a wanderer)
  player_respawn    a dead player on a server: the wait, a new pawn at a random
                    PlayerStart, the body left as a corpse
  gun_drop          the gun drop: seeded roll + pick streams, loot-table draw
  debuff_drain      HP lost per stack of each drained GAS tag (tuning.HEALTH_DRAINS)
  hit_reaction      flinch clips and direction pick; the Steady gate (a body
                    looking down its sights takes the hit and plays no flinch)
  hit_zones         head/limb bone tables and multipliers
  hit_bodies        the physics bodies fitted to each model (fit_hit_bodies),
                    and body_coverage(): bodies against the mesh, ray by ray
  pump_seat         pure: the move that closes the left hand's fingers on the
                    shotgun's pump, for whatever hand is worn (shotgun_pose)
  capsule_fit       pure geometry for hit_bodies: a cloud of vertices to its
                    long axis and one to four capsules along it
  ragdoll           joint limits and tune_ragdolls()

BP_WeaponComponent -> the weapon_component subpackage (see its __init__)

INSTALLING
  install           components onto the player and the wanderer; retire old

Dependency direction: data modules import nothing from this package except
each other; everything else may import data and uebp. No module imports
the entry point. Keep it acyclic -- a module that
needs a name from a sibling that already imports it means the name is in the
wrong module.
"""
