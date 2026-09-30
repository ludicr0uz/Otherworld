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
                    noise, SHOT_VOLUME_CM (how loud each gun is)
  difficulty        EASY / MEDIUM / SURVIVOR: labels, default, the variable
  game_state        GameMode + health-component variable names, debug mode,
                    the noise record, ensure_game_mode_vars()
  weapon_specs      the five weapons: parts, muzzles, icons, _weapon_specs()
  weapon_models     the rifle's and the sniper's Fab models (AK 47, AS Val +
                    scope), their muzzles and sights, and the measured outline
                    the grip and sight checks read in place of parts
  camera            boom and aim-trace numbers, face/aim-the-camera patches

SHARED AUTHORING HELPERS
  graph             node/pin/connect/set, variables, components, events
  noise             _author_make_noise: write the GameMode's noise record
                    (the shot and the player's footsteps call it)

ASSETS AND PATCHES
  materials         flat materials (gunmetal, wood, blood, brass)
  audio             sound names, attenuation profiles, import + link
  anim_blueprint    ABP_Unarmed: layered blends and the three slots
  aim_pitch         the player's anim BP: AimPitch tips the upper body (two
                    spine ModifyBones) so the gun follows the sights' pitch
  body_pose         the player's anim BP: crouch, prone and guard poses as
                    weighted ModifyBones (no clip exists), pose_plan()
  skin              the player's body (PlayerSkin, wear_skin)
  grip              hand-grip socket maths for holding a weapon: GripRotation
                    and GripLocation (the handle seated in the fist)
  settings_savegame BP_Settings
  weapon_items      BP_WeaponItem and one child per weapon
  blood             BP_BloodSplash
  ammo_pickup       BP_AmmoPickup
  footsteps         BP_FootstepComponent (StepVolume/StepNoise, set by the stance)
  combat_trace      the combat trace switch: GameMode's CombatTraceOn/Off
                    console events and CombatTrace's default

BP_HealthComponent (health_component wires the fragments together)
  health_component  variables, defaults, the Tick's death branch
  respawn           spawn numbering, world-floor net, respawn band
  death             kill count, shells, ragdoll collapse, corpse, player death
  gun_drop          the gun drop: seeded roll + pick streams, loot-table draw
  debuff_drain      HP lost per stack of the GAS Debuff.HealthDrain tag
  hit_reaction      flinch clips and direction pick
  hit_zones         head/limb bone tables and multipliers
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
