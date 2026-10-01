"""combat -- weapons, inventory, aiming, damage and death, as Unreal Python.

Entry point: Scripts/build_weapons_and_combat.py (main() calls the build_*
functions below in dependency order). Checks: Scripts/verify_weapons_and_combat.py,
which runs the combat.verify package.

One module per responsibility. Find the owner here before opening anything;
each module's docstring says what it owns and why it is shaped that way.

DATA (constants and pure tables -- no Blueprint authoring)
  paths             /Game asset paths and generated-class paths
  nodes             FN_* function paths, NODE_* palette names, macros
  tuning            keys, inventory size, CombatConfig / COMBAT, ammo, drops
                    (GUN_LOOT_TABLE, GUN_DROP_CHANCE, GUN_DROP_SEED),
                    auto fire, the consume event and health-drain tags,
                    the throw (THROW_*),
                    noise, SHOT_VOLUME_CM (how loud each gun is)
  sway_tuning       the sight sway's numbers (SWAY_*): angles, periods, the
                    stance's steadying, the component's variables, sway_at()
  seat_tuning       the sight camera's seat: how near the view the gun must
                    be before the camera goes onto it (SIGHT_SEAT_DEG),
                    SightSeated / SightSeat / SightsForced, HasSights (the
                    item flag only a gun sets), where the HUD's
                    crosshair gives way to the sights (RETICLE_HIDE_SEAT) and
                    the player's own head leaves the view (HEAD_HIDE_SEAT)
  carry_tuning      the carry's numbers and names: how long a shot keeps the
                    gun up (CARRY_RAISE_HOLD_S), Lowered / PoseLowered
  chop_tuning       chopping a tree: blows per piece of wood, where it lands
                    (WOOD_*), Chops and the component's Chop* variables
  throw_tuning      the throw's numbers (THROW_*): speed, angle, launch point,
                    the arc's and the flight's gravity, dots, landing, the
                    tumble, when the clip's hand lets go
  difficulty        EASY / MEDIUM / SURVIVOR: labels, default, the variable
  game_state        GameMode + health-component variable names, debug mode,
                    the noise record, ensure_game_mode_vars()
  gun_tuning        gun_tuning.csv: the tunable stats (TUNE_STATS: column,
                    variable, label, step, minimum), reading and writing it
  weapon_specs      the five weapons: muzzles, icons, _weapon_specs()
  weapon_models     every gun's model: the SMG's, the rifle's and the sniper's Fab
                    ones (SMG11, AK 47, AS Val + scope), the shotgun's and the pistol's
                    Quaternius ones (Shotgun_3, Pistol_1), their muzzles and sights,
                    and the measured outline the grip and sight checks read
  camera            boom and aim-trace numbers, face/aim-the-camera patches
  knife             BP_Knife: the Fab M9 knife as a Melee item, its model
                    placement and measured outline, build_knife()
  axe               BP_Axe: Quaternius's Survival Pack axe as a Melee item,
                    swung through the knife's stage, and the one item that
                    Chops; build_axe()
  wood              BP_Wood: Quaternius's Survival Pack log, what a tree gives
                    the axe; an item that lies Dropped, with nothing to fire
  light_tuning      lighting a campfire: where it goes (CAMPFIRE_*), Lights and
                    the component's MatchesClass/CampfireClass/LightWood
  matches           BP_Matches: Quaternius's Survival Pack matchbox, the one
                    item that Lights; build_matches()
  knife_anim        A_KnifeSlash: the slash keyed bone by bone onto the
                    knife's hold pose (AnimationDataController)
  hold_pose         A_HoldItem / A_HoldKnife: food carried at the waist, the
                    knife up in a fighting stance, keyed off the idle

SHARED AUTHORING HELPERS
  graph             node/pin/connect/set, variables, components, events
  noise             _author_make_noise: write the GameMode's noise record
                    (the shot and the player's footsteps call it)

ASSETS AND PATCHES
  materials         flat materials (gunmetal, wood, blood, brass, impact chip
                    and dust)
  audio             sound names, attenuation profiles, import + link
  anim_blueprint    ABP_Unarmed: layered blends and the three slots
  aim_pitch         the player's anim BP: AimPitch tips the upper body (two
                    spine ModifyBones) so the gun follows the sights' pitch
  body_pose         the player's anim BP: guard poses, and crouch and prone where
                    the rig has no clips, as weighted ModifyBones, pose_plan()
  stance_clips      the player's anim BP: the Quaternius crouch, crawl and kneel
                    clips blended over the locomotion by PoseCrouch/PoseProne
                    and (searching a body) PoseKneel
  skin              the player's body (PlayerSkin, wear_skin)
  grip              hand-grip socket maths for holding a weapon: GripRotation
                    and GripLocation (the handle seated in the fist)
  settings_savegame BP_Settings
  weapon_items      BP_WeaponItem and one child per weapon
  burst             build_burst: the actor of small pieces thrown off a hit
                    under drag and gravity (the graph both bursts below fly)
  blood             BP_BloodSplash: the droplet layout, what a body throws
  bullet_impact     BP_BulletImpact: the chips and dust layout, what the
                    scenery throws where a bullet hits it
  ammo_pickup       BP_AmmoPickup
  throw_arc         BP_ThrowArc + M_ThrowArc: the dotted arc a throw is aimed
                    with (one instanced mesh of emissive spheres)
  footsteps         BP_FootstepComponent (StepVolume/StepNoise, set by the stance)
  combat_trace      the combat trace switch: GameMode's CombatTraceOn/Off
                    console events and CombatTrace's default

BP_HealthComponent (health_component wires the fragments together)
  health_component  variables, defaults, the Tick's death branch
  respawn           spawn numbering, world-floor net, respawn band and delay
  replacement       the dead wanderer's replacement: the wait, the point, the spawn
  death             kill count, shells, ragdoll collapse, corpse, player death
  gun_drop          the gun drop: seeded roll + pick streams, loot-table draw
  debuff_drain      HP lost per stack of the GAS Debuff.HealthDrain tag
  hit_reaction      flinch clips and direction pick; the Steady gate (a body
                    looking down its sights takes the hit and plays no flinch)
  hit_zones         head/limb bone tables and multipliers
  hit_bodies        the physics bodies fitted to each model (fit_hit_bodies),
                    and body_coverage(): bodies against the mesh, ray by ray
  ragdoll           joint limits and tune_ragdolls()

BP_WeaponComponent -> the weapon_component subpackage (see its __init__)

INSTALLING
  install           components onto the player and the wanderer; retire old

Dependency direction: data modules import nothing from this package except
each other; graph imports only nodes; everything else may import data and
graph. No module imports the entry point. Keep it acyclic -- a module that
needs a name from a sibling that already imports it means the name is in the
wrong module.
"""
