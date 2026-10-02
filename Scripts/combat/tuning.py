"""Global combat tuning: polled keys, inventory size, the CombatConfig
dataclass (COMBAT), ammunition, drops and automatic fire. Numbers only --
the graphs that read them live elsewhere.
"""

import dataclasses


# ─── Tuning ──────────────────────────────────────────────────────────────────

INVENTORY_SIZE = 10

# The gameplay event the fire key sends when the held item is Consumable
# rather than a gun (see weapon_component/consume.py). The weapon component
# only announces the use; what eating or drinking *does* is GA_ConsumeItem's
# business, triggered by this tag (Scripts/survival/consume_ability.py). The
# tag itself is declared in Config/DefaultGameplayTags.ini.
CONSUME_EVENT_TAG = "Event.Item.Consume"

# A debuff that drains health grants this tag, once per debuff, and
# BP_HealthComponent takes DEBUFF_DRAIN_HP_PER_S per stack of it every second
# (combat/debuff_drain.py). The debuffs themselves are GameplayEffects built by
# Scripts/survival; the health component only counts the tag, so any future
# debuff that should hurt just grants it too.
HEALTH_DRAIN_TAG = "Debuff.HealthDrain"
DEBUFF_DRAIN_HP_PER_S = 0.5    # 100 HP lasts 200 s with one debuff, 100 with two

# Bleeding: a wound that takes BLEED_TOTAL_HP over BLEED_DURATION_S and then
# closes. GE_Bleeding (Scripts/survival) lasts that long and grants this tag;
# the health component drains at the rate the two numbers make. A tag of its
# own, not HEALTH_DRAIN_TAG, because its rate is its own.
BLEEDING_TAG = "Debuff.Bleeding"
BLEED_TOTAL_HP = 50.0
BLEED_DURATION_S = 180.0
# Six places: what a pin literal holds, so the graph and this agree exactly.
BLEED_HP_PER_S = round(BLEED_TOTAL_HP / BLEED_DURATION_S, 6)

# Every tag the health component drains by: (tag, HP per second per stack).
# The rates add up, so a starving, bleeding player loses both.
HEALTH_DRAINS = (
    (HEALTH_DRAIN_TAG, DEBUFF_DRAIN_HP_PER_S),
    (BLEEDING_TAG, BLEED_HP_PER_S),
)

# Polled keys.  1/2/3 and M belong to the graphics menu, so the weapon keys stay
# clear of them.
#
# Every one of them is polled on the weapon component's Tick rather than bound
# as an input action, for the same reason: BP_ThirdPersonCharacter's graph is
# the Enhanced Input template, and adding an IA asset plus an IMC entry is not
# authorable from Python. Sprint lives on the *weapon* component specifically
# because that is the thing that has to refuse to fire while it is held down.
FIRE_KEY = "LeftMouseButton"
# Two ways to aim, two keys. AIM_KEY is the over-the-shoulder aim: the camera
# stays on its boom and zooms. SIGHTS_KEY is aiming down the sights: the camera
# leaves the boom for the weapon's own eye point (SightOffset on the item), so
# the player looks along the gun in first person -- and on the sniper, into
# the scope. Held, not toggled, like the shoulder aim. The middle button
# because the other two are taken and it is on every mouse; it is rebindable.
AIM_KEY = "RightMouseButton"
SIGHTS_KEY = "MiddleMouseButton"
SWITCH_KEY = "Q"
DROP_KEY = "G"
# Pressed to interact with whatever the reticle rests on
# (weapon_component/interact.py). An item lying there is picked up.
INTERACT_KEY = "E"
SPRINT_KEY = "LeftShift"
# Held to guard (weapon_component/block.py). F because it sits under the left
# hand beside the movement keys and nothing else here uses it; rebindable.
BLOCK_KEY = "F"
# Tapped to toggle the stance (weapon_component/stance.py). C and Z are the
# usual pair, and both sit under the left hand; rebindable.
CROUCH_KEY = "C"
PRONE_KEY = "Z"
# Held to aim a throw, released to let go (weapon_component/throw.py). V sits
# beside C under the left hand, and nothing else here uses it; rebindable.
THROW_KEY = "V"

INTERACT_RADIUS = 250.0    # cm; how close you must be to press E
DROP_FORWARD = 120.0       # cm in front of the player a dropped weapon lands

# ─── The combat config ───────────────────────────────────────────────────────
#
# One named structure for the global combat tuning, and it is a Python
# dataclass rather than a UserDefinedStruct or a DataAsset on purpose.
#
# Every number in here is BAKED INTO A GRAPH at build time: the cone scale is a
# SelectFloat pin literal, the recoil recovery speed an FInterpTo pin literal,
# the sensitivity limits FClamp literals in the settings screen. A struct asset
# a designer edited in the editor would have to be *read* at runtime instead --
# an asset load, a null guard and a member read in front of every one of those
# pins, in a project where each of those nodes is placed and wired by hand from
# Python.
#
# And it would not survive being edited. Nothing under Content/ is committed
# (see CLAUDE.md): every asset in this project is derived and is rebuilt from
# these scripts on a fresh clone. An in-editor edit to a generated DataAsset is
# erased the next time the builder runs and was never in the repository to
# begin with -- so "tunable in the editor without re-running Python" is a
# promise this architecture cannot keep, and pretending otherwise would lose
# somebody's tuning pass rather than save them a build.
#
# So tuning combat means editing this object and re-running
# build_weapons_and_combat.py. That is the same workflow as the project's two
# other tuning homes, forest_generator/lighting.py (the time-of-day presets)
# and forest_generator/npc_placement.py (run speed, melee reach) -- and it is
# the one that gets checked, because the verifier reads these fields back out
# of the compiled graphs.
#
# Frozen, so no builder can quietly write a number back into it and leave the
# verifier asserting a value the graph never saw.
#
# PER-WEAPON numbers deliberately do NOT live here. Damage, spread, range, fire
# interval, magazine size and recoil are columns in _weapon_specs(), which is
# what keeps a sixth weapon a row in a table rather than a code change. This is
# the other half: what is true of a fight whatever is being held.
@dataclasses.dataclass(frozen=True)
class CombatConfig:
    """The global, tunable combat parameters -- the one place to change them."""

    # --- what it takes to kill and to die ------------------------------------
    start_health: float = 100.0
    # Where on the body a shot landed. The capsule decides *whether* a pellet
    # hit a character; the physics asset's bodies decide where (see hit_zones).
    # Anything the zones do not name -- neck, clavicles, torso -- is worth 1.0.
    head_multiplier: float = 1.5
    limb_multiplier: float = 0.75

    # --- sprint and stamina --------------------------------------------------
    # The walking speed is NOT here: BeginPlay caches whatever the character's
    # MaxWalkSpeed already is into BaseSpeed and restores that. A literal would
    # silently fight any later change to the character's own default.
    sprint_speed_cms: float = 900.0
    max_stamina: float = 100.0
    # 4 s of sprint from full, a little over 8 s to refill. Deliberately
    # asymmetric: sprint is the escape from a pack that runs at 600 cm/s, so it
    # has to be worth spending and it has to cost something to have spent.
    stamina_drain_per_s: float = 25.0
    stamina_regen_per_s: float = 12.0

    # --- blocking ------------------------------------------------------------
    # Held BLOCK_KEY, armed or not. A wanderer's swing that lands within
    # block_half_angle_deg of where the player faces does block_damage_scale of
    # its damage and costs block_stamina_per_hit; a guard with no stamina left
    # is no guard (Blocking needs Stamina > 0), so five blocked hits from full
    # break it. The hit itself is resolved where it is dealt, in the NPC melee
    # (npc/block.py), because that is the one place the swing's damage and
    # bearing exist together.
    block_damage_scale: float = 0.25
    block_stamina_per_hit: float = 20.0
    block_half_angle_deg: float = 60.0

    # --- the punch: the fire key with empty hands (weapon_component/punch) ---
    # One swing every punch_interval_s; the blow lands punch_impact_s into the
    # clip (MM_Attack_01's fist is out by then), on the first body a sphere of
    # punch_radius_cm meets within punch_reach_cm in front of the chest. Seven
    # punches kill a 100 HP wanderer: a last resort, not a weapon.
    punch_damage: float = 15.0
    punch_interval_s: float = 0.8
    punch_impact_s: float = 0.3
    punch_reach_cm: float = 130.0
    punch_radius_cm: float = 30.0
    punch_chest_cm: float = 30.0

    # --- the knife: the fire key with the knife held (weapon_component/knife) -
    # The same three stages as the punch (press, swing, blow), on their own
    # variables. A slash every knife_interval_s; the blow lands knife_impact_s
    # in, at the bottom of the swing of A_KnifeSlash (knife_anim.py), on the
    # first body a knife_radius_cm sphere meets within knife_reach_cm. Three
    # slashes kill a 100 HP wanderer, against the punch's seven: a real weapon
    # at arm's length, where the guns are at range.
    knife_damage: float = 35.0
    knife_interval_s: float = 0.6
    knife_impact_s: float = 0.24
    knife_reach_cm: float = 150.0
    knife_radius_cm: float = 25.0
    knife_chest_cm: float = 30.0

    # --- crouch and prone ----------------------------------------------------
    # Toggled by CROUCH_KEY / PRONE_KEY; sprinting stands the player up. Both
    # are UE's own crouch (the capsule shrinks, the camera boom rides down with
    # it), prone being a lower crouch -- see weapon_component/stance.py. Speeds
    # are fractions of BaseSpeed, so they follow the character's own walk.
    # The prone capsule cannot be shorter than its radius (the engine clamps
    # to it, and the stance code would then re-crouch forever); the verifier
    # asserts it against the character's capsule.
    crouch_speed_scale: float = 0.45
    prone_speed_scale: float = 0.2
    crouch_half_height_cm: float = 60.0
    prone_half_height_cm: float = 40.0
    # What a footstep sounds like, and how far it carries for the wanderers,
    # per stance: StepVolume is the PlaySoundAtLocation volume, StepNoise
    # multiplies the (already speed-proportional) reach. So a crouched step at
    # 270 cm/s carries 12 m x 0.45 x 0.5 = 2.7 m, and a crawl under a metre.
    crouch_step_volume: float = 0.5
    prone_step_volume: float = 0.3
    crouch_step_noise: float = 0.5
    prone_step_noise: float = 0.35

    # --- aiming down the sights ----------------------------------------------
    # What ADS does is narrow the camera's field of view and tighten the
    # weapon's cone. The zoom factor is per weapon (AdsZoom on BP_WeaponItem)
    # because the sniper's is a scope and everything else's is a set of irons:
    # 4x against 1.5x is the difference the player is buying when they pick the
    # rifle up. These two are the values that table chooses between.
    #
    # BaseFOV is cached at BeginPlay from whatever the camera already has,
    # exactly as BaseSpeed caches MaxWalkSpeed.
    ads_zoom_irons: float = 1.5
    ads_zoom_scope: float = 4.0
    # The over-the-shoulder aim zooms by this on every weapon: it is a way of
    # holding the camera, not a sight, so it is not a column. Equal to the
    # irons, so shouldering a rifle and looking down its irons frame the world
    # the same and only the camera moves. The scope's glass and its extra
    # sensitivity slowdown key off zoom BEYOND this, which is what keeps them
    # off the sniper's shoulder aim.
    shoulder_zoom: float = 1.5
    # The FOV is NOT snapped. FInterpTo at this speed takes about a fifth of a
    # second to arrive, which is short enough to feel instant and long enough
    # that a 4x snap does not read as a teleport. CurrentFOV is stored rather
    # than recomputed because FInterpTo needs its own previous output.
    ads_interp_speed: float = 12.0
    # And what it costs in mobility: at full ADS the player walks at half
    # speed. Aiming is meant to be a commitment -- the cloud is narrower (or
    # gone, down the sights) and the camera is inside a scope, so the price is that you cannot also
    # be going anywhere.
    #
    # Applied as a fraction of BaseSpeed, never of the CURRENT walk speed: the
    # write runs every frame, so scaling what is already there would compound
    # to a standstill in about a second. And it eases in along the zoom's own
    # curve rather than snapping with the button, for the reason
    # ads_sens_compensation below eases -- except that the interpolant here is
    # normalised by the weapon's own AdsZoom, so full ADS is exactly this
    # number on irons and on the scope alike. The sensitivity one deliberately
    # is NOT normalised, because "a 4x scope slows the mouse more" is wanted
    # and "a 4x scope slows the legs more" is not.
    ads_move_speed_scale: float = 0.50

    # --- mouse sensitivity, and what aiming does to it -----------------------
    # The player's look input is the Enhanced Input template's IA_Look, which
    # lands on AddControllerYawInput / AddControllerPitchInput -- and those
    # still multiply by APlayerController's InputYawScale / InputPitchScale on
    # their way into RotationInput. That pair is marked deprecated in UE5, but
    # the setters are BlueprintCallable and they are the ONLY per-frame handle
    # on look speed that does not require editing BP_ThirdPersonCharacter's
    # input graph, which the Blueprint graph API cannot partially rebuild.
    #
    # Their values are CACHED at BeginPlay rather than written down here, for
    # the same reason as BaseSpeed and BaseFOV. It matters more here than
    # anywhere else: the engine's default pitch scale is NEGATIVE (-2.5), so a
    # literal positive number would silently invert the player's vertical look.
    mouse_sensitivity_default: float = 1.0
    mouse_sensitivity_min: float = 0.20
    mouse_sensitivity_max: float = 3.00
    mouse_sensitivity_step: float = 0.05
    # How much of the zoom aiming gives back in slower mouse movement.
    #
    # Driven off CurrentFOV / BaseFOV, not off a flag, which buys three things
    # for one node: the slowdown is per weapon without anything per weapon
    # being written (a 4x scope slows the mouse more than 1.5x irons because
    # its FOV is narrower), it EASES IN along the same FInterpTo curve the zoom
    # does rather than snapping the instant the button goes down, and letting
    # go restores it by the same curve with no second code path.
    #
    # 1.0 would be full compensation: the crosshair would then cross the same
    # number of PIXELS per centimetre of mouse at any zoom, which at 4x reads
    # as the mouse having gone dead. 0.0 would be none at all, which at 4x
    # throws the crosshair off the far side of the scope. 0.75 is the usual
    # compromise, and works out at 0.75x sensitivity down the irons and 0.44x
    # down the scope.
    ads_sens_compensation: float = 0.75
    # ...and on top of that, the sniper's scope halves it again. 0.44x read as
    # still too twitchy at 4x, where a few pixels of mouse cross a whole head.
    # Keyed off zoom BEYOND the irons -- progress from ads_zoom_irons to
    # ads_zoom_scope -- not off Held.Scoped, so it eases in on the same
    # FInterpTo curve, needs no Held read on the frames nothing is equipped, and
    # leaves irons exactly at 0.75x. Works out at 0.22x down the scope.
    #
    # This is only the DEFAULT: the player sets it on the settings screen
    # ("SCOPE SENSITIVITY"), it is saved in BP_Settings.ScopeSensitivity and
    # pushed onto BP_WeaponComponent every frame like MouseSensitivity. 1.0
    # there means "no extra slowdown", i.e. the 0.44x the zoom alone gives.
    ads_scope_sens_scale: float = 0.50
    scope_sensitivity_min: float = 0.10
    scope_sensitivity_max: float = 1.50
    scope_sensitivity_step: float = 0.05

    # --- recoil --------------------------------------------------------------
    # A shot kicks the view up by the weapon's own RecoilPitch (a column in
    # GUN_ACCURACY, because how hard a gun kicks is the gun's business) and
    # sideways by a random draw within its RecoilYaw, and the kick is then paid back over
    # the following fraction of a second.
    #
    # Applied by READING AND WRITING THE CONTROL ROTATION, never with
    # AddPitchInput / AddControllerPitchInput. That route multiplies by
    # APlayerController's deprecated InputPitchScale -- which is exactly the
    # handle the mouse-sensitivity setting above drives -- so a player on 0.2
    # sensitivity would get a fifth of the recoil and a player on 3.0 would be
    # thrown at the sky. Recoil is a property of the weapon and must not move
    # when a settings slider does. SetControlRotation bypasses RotationInput
    # entirely, and the engine's own LimitViewPitch re-clamps the result inside
    # ViewPitchMin/Max on the controller's next UpdateRotation, so a kick taken
    # while already looking near-vertical cannot push the camera over the top.
    #
    # The accumulator is RecoilDebt: what has been kicked and not yet given
    # back. Recovery is an FInterpTo of the debt toward zero, so it is fast at
    # first and settles rather than stopping dead.
    recoil_recovery_speed: float = 7.0
    # ...and only this much of each frame's recovery is handed back to the
    # view. The rest of the debt still decays -- the accumulator always returns
    # to zero, so nothing can build up across a magazine -- but 30% of every
    # kick is left in the player's aim for good. That is the difference between
    # a gun and a screen shake: a burst walks up the target and has to be
    # pulled back down, instead of springing exactly home between rounds.
    recoil_recovery_fraction: float = 0.70
    # How much each stance and aim steadies the kick, and how far it swings
    # sideways, are per gun: GUN_ACCURACY in weapon_specs.py.

    # --- flinching (taking a hit and living) ---------------------------------
    # Anything that takes damage and survives plays a one-second stagger on its
    # upper body, picked by which side the hit came from. See the hit-reaction
    # block below HIT_SLOT for what it is made of and why it is upper body.
    #
    # The cooldown is the load-bearing number of the three. The reaction is
    # triggered by a per-frame "is Health lower than it was last frame" poll, so
    # without one the SMG (one round every 0.09 s) would restart the montage
    # eleven times a second and the target would stand in the first two frames
    # of a flinch forever -- a vibration, not a reaction. 0.45 s is a little
    # over half the clip at the rate below: consecutive hits still re-trigger,
    # visibly, but only after the previous stagger has read.
    hit_react_cooldown_s: float = 0.45
    # Faster than authored. The clips are ~1.0 s of stagger-and-recover, which
    # is a long time to have your chest yanked around in a firefight; 1.4x
    # brings it to ~0.7 s, which still reads and gets the arms back under the
    # player's control sooner.
    hit_react_rate: float = 1.4
    # In and out. Short enough to look like an impact -- a hit that eases in
    # over a quarter of a second reads as a stumble, not a bullet -- and long
    # enough not to pop the chest between two poses in one frame.
    hit_react_blend_s: float = 0.08

    # --- noise: what the wanderers can hear ----------------------------------
    # A noise is one record on the GameMode (combat/noise.py) -- where, how far
    # it carries all round, and for a gunshot how far it carries down the
    # barrel -- and every patrolling wanderer checks it on its heartbeat. How
    # far a noise carries belongs to whatever made it; the listener only
    # scales it (forest_generator/npc_agro.py, hearing_scale).
    #
    # A noise is held this long before anything quieter may replace it. It
    # has to outlast one NPC heartbeat (NPC_REPATH_SECONDS, 0.5 s), or a
    # footstep 0.3 s after a gunshot would overwrite the shot before half the
    # pack had checked for it. The verifier asserts the inequality.
    noise_hold_s: float = 0.6
    # A gunshot is louder in front of the muzzle: inside this half-angle of
    # the aim direction it carries shot_noise_cone_range_scale times the
    # weapon's ShotVolume, all round it carries ShotVolume. So firing TOWARD a
    # pack wakes it from further off than firing away from it.
    shot_noise_cone_half_angle_deg: float = 30.0
    shot_noise_cone_range_scale: float = 1.6
    # The player's footsteps carry this far at this speed, and in proportion
    # to speed either side of it: 12 m at a 600 cm/s run, 18 m at a 900 cm/s
    # sprint, 6 m at the half-speed walk aiming costs. Proportional rather
    # than a walk/sprint pair so that anything else that changes the player's
    # speed changes their noise for free. Only the PLAYER's footsteps are a
    # noise -- the wanderers share the footstep component and must not wake
    # each other up.
    footstep_noise_range_cm: float = 1200.0
    footstep_noise_reference_speed_cms: float = 600.0


COMBAT = CombatConfig()


# --- shotgun ammunition ------------------------------------------------------
# Ammunition lives on BP_WeaponItem, not on the weapon component, because a
# weapon is a droppable actor here: drop a half-empty shotgun, walk away, come
# back and pick it up, and it still has to be half empty. Reserve on the
# component would belong to the player and would survive a gun that did not.
#
# "Starting 20" is read as twenty shells in total, not twenty plus a free
# magazine: five are in the gun and fifteen are spare.
SHOTGUN_MAGAZINE = 5
SHOTGUN_RESERVE = 15
# Enough of a pause that the shotgun is a decision and not a hose -- it now does
# 8 x 18 = 144 damage to a wanderer with 100 HP, so one connected shot is a
# kill and the interval is the whole balance of the weapon.
SHOTGUN_FIRE_INTERVAL = 0.85
# Reload is not a state machine and not a montage: it pushes NextFireTime out by
# this much, which is exactly what "cannot shoot for 1.6 s" means, and it costs
# three nodes instead of a timer, an interrupt rule and an is-reloading flag.
SHOTGUN_RELOAD_SECONDS = 1.6
# The pistol is the fallback weapon: an 8-round magazine over an unlimited
# reserve (BP_WeaponItem.InfiniteReserve), so it reloads every eight shots but
# can never run dry for good. It still gets an interval, because without one it
# fires once per frame.
PISTOL_MAGAZINE = 8
PISTOL_FIRE_INTERVAL, PISTOL_RELOAD_SECONDS = 0.18, 1.2
RELOAD_KEY = "R"

# The seven rebindable actions, in the order the settings screen lists them and
# -- more importantly -- in the order BP_Settings.Binds stores them. That array
# is indexed, not keyed, so this tuple IS the contract between the two builders:
# build_graphics_menu.py imports it and writes Binds[i] for the same i the HUD
# pushes back into the variable named here. Reorder it and every existing save
# on disk silently rebinds itself to the wrong actions.
#
# KeySights sits next to KeyAim, and adding it changed the length: a save
# written before it has seven binds, which the settings loader refills with
# these defaults rather than trusting (build_graphics_menu.py's settings load).
# KeyBlock went on the END, for the same reason: a nine-bind list refills an
# eight-bind save once, and no existing index changes meaning. KeyCrouch and
# KeyProne were appended the same way, and then KeyThrow.
BIND_VARS = (("KeyFire", FIRE_KEY),
             ("KeyAim", AIM_KEY),
             ("KeySights", SIGHTS_KEY),
             ("KeySprint", SPRINT_KEY),
             ("KeySwitch", SWITCH_KEY),
             ("KeyDrop", DROP_KEY),
             ("KeyInteract", INTERACT_KEY),
             ("KeyReload", RELOAD_KEY),
             ("KeyBlock", BLOCK_KEY),
             ("KeyCrouch", CROUCH_KEY),
             ("KeyProne", PRONE_KEY),
             ("KeyThrow", THROW_KEY))
# Shells a killed wanderer leaves behind. Two per kill against five spent per
# magazine means the shotgun runs down unless most shots land, which is the
# point of giving it a reserve at all.
AMMO_DROP_SHELLS = 2
AMMO_PICKUP_RADIUS = 200.0   # cm; walked into, not pressed for
AMMO_PICKUP_LIFT = 40.0      # cm above the corpse, so it is not inside the mesh
AMMO_PICKUP_LIFETIME = 120.0 # s before an uncollected drop tidies itself away
AMMO_SPIN_DEG_PER_S = 90.0

# --- the three found weapons -------------------------------------------------
# The shotgun and pistol are the starting loadout and are spawned into the
# player's hands at BeginPlay. These three are not: the only way to get one is
# to kill something that happens to be carrying it, which is what makes the
# 10% a reason to keep fighting rather than a number in a table.
#
# The balance across all five is deliberately one axis: damage per second is
# roughly flat, and what differs is how it is delivered. The SMG spends nine
# rounds to kill a 100 HP wanderer in under a second; the sniper spends one and
# then makes you wait 1.6 s for the next. The shotgun sits between them and
# only at close range, because eight pellets in a 5 degree cone stop all
# landing on one target past about 15 m.
SMG_MAGAZINE, SMG_RESERVE = 30, 90
SMG_FIRE_INTERVAL, SMG_RELOAD_SECONDS = 0.09, 1.9
RIFLE_MAGAZINE, RIFLE_RESERVE = 30, 90
RIFLE_FIRE_INTERVAL, RIFLE_RELOAD_SECONDS = 0.14, 2.1
SNIPER_MAGAZINE, SNIPER_RESERVE = 5, 15
SNIPER_FIRE_INTERVAL, SNIPER_RELOAD_SECONDS = 1.60, 2.6

# --- how loud each gun is ----------------------------------------------------
# ShotVolume: how far, in cm, a wanderer with ordinary ears (hearing_scale 1.0)
# hears this weapon fired, all round. Down the barrel it carries
# COMBAT.shot_noise_cone_range_scale (1.6x) further, inside 30 degrees of the
# aim line only. A wendigo (hearing_scale 1.4) hears every figure 1.4x further.
# Measured against Lvl_Forest_200m's ten real spawn points and patrol circles
# (the pack starts 75-78 m from the player start), wanderers that hear one shot
# fired all-round from the player start, on average:
#
#   Sniper   150 m  (240 m ahead)  10 of 10; from a corner, 7 for sure + 3 maybe
#   Rifle     90 m  (144 m ahead)  ~9.9 of 10 -- the pack sits just inside it
#   Shotgun   85 m  (136 m ahead)  ~8.7 of 10
#   SMG       50 m   (80 m ahead)  ~0.6 of 10: local unless aimed at someone
#   Pistol    35 m   (56 m ahead)  0 of 10: only what is already close
#
# So from the start, rifle and shotgun wake nearly as much as the sniper; the
# gap between them opens up away from the centre, where the sniper still
# reaches 7-10 and the rifle and shotgun 3-6. Shrink RIFLE/SHOTGUN below ~75 m
# if the middle tier should leave part of the starting pack asleep.
SHOT_VOLUME_CM = {
    "Sniper": 15000.0,
    "Rifle": 9000.0,
    "Shotgun": 8500.0,
    "SMG": 5000.0,
    "Pistol": 3500.0,
}

# Which of the five hold the trigger down. The SMG and the assault rifle do;
# the shotgun, the pistol and the sniper are one shot per click.
#
# This is a property of the weapon and not of the input code, which is the
# whole reason it is expressible at all: the trigger is polled two ways every
# frame -- tapped and held -- and the weapon decides which of the two it
# answers to. Nothing branches on a weapon's name to find out.
#
# Note what automatic fire does NOT need: a timer, a "firing" state, or a
# repeating event. FireInterval and NextFireTime already gate the rate, and
# they were already being consulted on every frame the trigger was down. All
# the automatics change is whether a held button still counts as a pull.
AUTO_DISPLAYS = ("SMG", "Rifle")

# --- the gun drop: two seeded rolls and a loot table --------------------------
# One kill in ten leaves a gun. Two rolls, each on its own FRandomStream kept on
# the GameMode (combat/gun_drop.py):
#
#   the drop roll   RandomFloatFromStream < GUN_DROP_CHANCE -- does anything drop;
#   the pick roll   RandomIntegerFromStream into the loot table -- which gun.
#
# Separate streams, so the pick roll is only consumed by kills that drop: the
# rate is exactly GUN_DROP_CHANCE whatever the table holds, and re-weighting the
# table never moves which kills drop.
#
# Rolled on exactly the same arm as the shells, which means DamagedByPlayer
# guards it too: a wanderer the terrain swallowed has not been killed, and the
# safety net must not be a weapon dispenser.
GUN_DROP_CHANCE = 0.10
# The loot table: (weapon display name, weight). A weight is a number of
# tickets in BP_HealthComponent.DropClasses, so the pick roll is a uniform draw
# over tickets and a weapon's share of drops is weight / sum(weights). Per kill
# that is 5% SMG, 3% rifle, 2% sniper -- the sniper is the rarest because it is
# the one that changes how the forest plays. Only the order and the names here
# decide what can drop; the starting loadout is not in it on purpose.
GUN_LOOT_TABLE = (("SMG", 5), ("Rifle", 3), ("Sniper", 2))
# 0 seeds both streams from the engine's global RNG on the first kill of each
# session, so every session draws differently. Any other value makes the drop
# sequence reproducible (drop stream = seed, pick stream = seed + 1): kill N
# drops the same thing every run, which is what a probe or a bug report needs.
GUN_DROP_SEED = 0
GUN_DROP_FORWARD = 70.0   # cm; clear of the shells, which land on the corpse


# --- combat trace --------------------------------------------------------------
# Whether BP_ThirdPersonGameMode starts with the combat trace on (see
# COMBAT_TRACE_VAR in game_state.py). Leave it False: the trace is for
# troubleshooting, and a normal session should not write a line per punch.
# Turn it on for one session with `ke * CombatTraceOn` in the console, or make it
# the default by setting this True and re-running build_weapons_and_combat.py.
COMBAT_TRACE_DEFAULT = False
