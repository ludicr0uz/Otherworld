"""Asset paths, variable names and the few constants the NPC graphs share.
Constants only -- no Blueprint authoring, no graph helpers.
"""


# ─── Configuration ───────────────────────────────────────────────────────────

NPC_DIR = "/Game/Forest/NPC"
AI_BP_PATH = f"{NPC_DIR}/BP_ForestWandererAI"
NPC_BP_PATH = f"{NPC_DIR}/BP_ForestWanderer"

MESH_RELATIVE_Z_CM = -89.0
MESH_RELATIVE_YAW_DEG = 270.0

# Where the player's health lives.  Built by build_weapons_and_combat.py; if it
# is absent (a project where the weapons have never been built) the melee half
# of the chase loop is skipped and the NPC just runs at the player.
HEALTH_BP_PATH = "/Game/Weapons/BP_HealthComponent"
HEALTH_CLASS_PATH = f"{HEALTH_BP_PATH}.BP_HealthComponent_C"

# The slot the attack animation is played into.  build_weapons_and_combat.py
# splices a layered blend per bone (spine_01) into ABP_Unarmed, which makes
# DefaultSlot upper-body only -- so the NPC swings its arms while the legs keep
# running.  Without that patch the montage is full body and the swing also stops
# the legs; it still reads as an attack, so this is not a hard dependency.
MELEE_SLOT = "DefaultSlot"


# Where the creature voices and the impact sounds are imported to, by
# combat.audio.import_sounds().
VOICES_VAR = "Voices"
HIT_SOUNDS_VAR = "HitSounds"
STATS_APPLIED_VAR = "StatsApplied"
# The TuneHealth last written onto the pawn (npc/stats.py): a change re-applies it.
APPLIED_HEALTH_VAR = "AppliedHealth"
NEXT_VOICE_VAR = "NextVoiceTime"
HIT_SOUNDS = tuple(f"/Game/Audio/A_MeleeHit_{i:02d}" for i in (1, 2, 3))

# This creature's six flinches, carried on the CONTROLLER and copied onto the
# pawn's health component at possession -- the same route, and for the same
# reason, as its health: an AnimSequence belongs to one skeleton, the variants
# are three different skeletons, and a child Blueprint's override of an
# inherited component's defaults lives in an InheritableComponentHandler the
# Python API cannot reach.  Without this every wanderer would flinch with
# BP_ForestWanderer's mesh's clips, i.e. the wendigos would not flinch at all.
REACTIONS_VAR = "HitReactions"
# On BP_HealthComponent, written by whoever did the damage: a unit vector from
# the victim toward the source.  The wanderers' punch is the only melee in the
# game and this is the only place it is written; build_weapons_and_combat.py
# writes it off the impact normal for a bullet.  See _author_hit_reaction there
# for what reads it.
LAST_HIT_FROM_VAR = "LastHitFrom"
# Per controller: what the swing being landed deals, set by the player's guard
# check (npc/block.py) just before the Health write reads it.
HIT_DAMAGE_VAR = "HitDamage"

# ── Patrol and agro (npc/agro.py, patrol.py, senses.py) ─────────────────────
#
# Per controller, so every wanderer keeps its own state. Aggro is the switch:
# false is patrolling, true is the chase-and-swing loop, and nothing sets it
# back. AggroReason is which sense flipped it ("hurt", "sight", "touch",
# "sound"), kept for the log line and for anything later that wants to react
# differently to being heard than to being seen.
AGGRO_VAR = "Aggro"
AGGRO_REASON_VAR = "AggroReason"
# Taken once, on the first heartbeat with a pawn: the centre of the patrol
# circle, and this wanderer's own run speed -- per creature and per instance
# (gait variance), so it is read off the pawn rather than recomputed.
PATROL_READY_VAR = "PatrolReady"
PATROL_HOME_VAR = "PatrolHome"
RUN_SPEED_VAR = "RunSpeed"
PATROL_TARGET_VAR = "PatrolTarget"
NEXT_PATROL_VAR = "NextPatrolTime"
MOVEMENT_CLASS_PATH = "/Script/Engine.CharacterMovementComponent"
CHARACTER_CLASS_PATH = "/Script/Engine.Character"
# Whose StaticMesh a tree's cell is read through (npc/stalk_cover.py).
STATIC_MESH_COMP_CLASS_PATH = "/Script/Engine.StaticMeshComponent"

# ── Between two swings (npc/strafe.py) ───────────────────────────────────────
#
# Picked once per swing, by the first Chase step after it: how far round the
# player the wanderer steps (degrees, signed: left or right) and how far from
# them it ends up. STRAFE_FOR_VAR is the NextAttackTime the pick was made
# for, which is how the step tells a new swing from the one it already has.
STRAFE_YAW_VAR = "StrafeYaw"
STRAFE_DIST_VAR = "StrafeDist"
STRAFE_FOR_VAR = "StrafeFor"

# ── The wendigo's hunt (npc/stalk.py, stalk_cover.py) ───────────────────────
#
# Per controller, on the creatures of forest_generator/npc_stalk.NPC_STALK_ROAR
# only. The hunt runs roar -> legs -> charge, and never back:
#   STALK_ROAR_UNTIL_VAR   when the roar ends; 0 until it has roared
#   STALK_ORIGIN_VAR       where the player stood when it roared
#   STALK_SIDE_VAR         +1 or -1: which way round the player, for now
#   STALK_TURN_AT_VAR      when the side is next turned about (at a leg's pick)
#   STALK_COVER_VAR        where this leg ends
#   STALK_HIDDEN_VAR       ...which is behind a tree (false: in the open)
#   STALK_LEG_UNTIL_VAR    running: when the leg is given up; arrived: when
#                          the wait behind the trunk ends. 0: pick a leg
#   STALK_ARRIVED_VAR      it has reached this leg's spot
#   STALK_LEGS_VAR         legs picked so far (the probe counts them)
#   STALK_CHARGING_VAR     close enough, or the player has run off: the Stalk
#                          step fails from now on
#   STALK_IGNORE_VAR       what the sweep for a tree ignores (ground, own pawn)
#   ENRAGED_VAR            the player has hurt it: no hunt, the charge, for good
STALK_ROAR_UNTIL_VAR = "StalkRoarUntil"
STALK_ORIGIN_VAR = "StalkOrigin"
STALK_SIDE_VAR = "StalkSide"
STALK_TURN_AT_VAR = "StalkTurnAt"
STALK_COVER_VAR = "StalkCover"
STALK_HIDDEN_VAR = "StalkHidden"
STALK_LEG_UNTIL_VAR = "StalkLegUntil"
STALK_ARRIVED_VAR = "StalkArrived"
STALK_LEGS_VAR = "StalkLegs"
STALK_CHARGING_VAR = "StalkCharging"
STALK_IGNORE_VAR = "StalkIgnore"
ENRAGED_VAR = "Enraged"

# ── Held off by fire (npc/ward.py) ──────────────────────────────────────────
#
# Per controller, on the creatures of forest_generator/npc_ward.NPC_WARD_FEARS
# only. All game times, 0 until first written:
#   WARD_SINCE_VAR       when this hold began; 0: none is under way
#   WARD_LAST_VAR        the last pass that was held off (a hold broken for
#                        longer than the grace starts over)
#   WARD_SIDE_VAR        +1 or -1: which way round the player it circles
#   WARD_TURN_AT_VAR     when that is next turned about
#   WARD_FLEE_UNTIL_VAR  it runs away until then
#   WARD_FLEE_GOAL_VAR   where the pass's run-away order points
#   WARD_ROAR_AT_VAR     when this hold's first roar is due; 0 once given
#   WARD_ROAR_UNTIL_VAR  it stands roaring until then (npc/ward_roar.py)
WARD_SINCE_VAR = "WardSince"
WARD_LAST_VAR = "WardLast"
WARD_SIDE_VAR = "WardSide"
WARD_TURN_AT_VAR = "WardTurnAt"
WARD_FLEE_UNTIL_VAR = "WardFleeUntil"
WARD_FLEE_GOAL_VAR = "WardFleeGoal"
WARD_ROAR_AT_VAR = "WardRoarAt"
WARD_ROAR_UNTIL_VAR = "WardRoarUntil"

# ── Drawn to a fire (npc/drawn.py) ───────────────────────────────────────────
#
# Per controller, on the creatures of forest_generator/npc_drawn.NPC_DRAWN_BY_FIRE
# only. Drawn is the state between patrol and hunt: it is what the last Drawn
# step found, and that step runs only while the wanderer is not aggro, so a
# reader wants "Drawn and not Aggro".
#   DRAWN_VAR      a fire within reach has it walking there (or standing by it)
#   DRAWN_TO_VAR   that fire: the target it moves towards
DRAWN_VAR = "Drawn"
DRAWN_TO_VAR = "DrawnTo"

# ── The corpse state (npc/corpse.py) ─────────────────────────────────────────
#
# The wanderer's third and last state, after patrol (Aggro false) and hunt
# (Aggro true). Set on the first heartbeat that finds the pawn's health
# component Dead, and nothing sets it back. A corpse's heartbeat stops there:
# no stats, no voice, no patrol, no chase, no swing, and no next Delay. The
# health component also destroys the controller when it dies (combat/death.py
# _author_corpse). This gate does not depend on that destroy having happened.
CORPSE_VAR = "Corpse"
CORPSE_LOG_PREFIX = "[NPC-CORPSE] #"

# ── Debug mode's sight cone (npc/sight_cone.py) ──────────────────────────────
#
# While the GameMode's DebugMode is on, every live wanderer draws the cone its
# sight sense tests (npc/senses.py): from the pawn, along its forward vector,
# TuneSightRange long and TuneSightHalfAngle either side. SIGHT_CONE_PATROL_COLOR
# while it patrols, SIGHT_CONE_AGGRO_COLOR once it hunts. SIGHT_CONE_STAMP_VAR
# is the game time of the last cone drawn, which is how a headless probe (no
# renderer) tells that the draw ran.
SIGHT_CONE_STAMP_VAR = "SightConeDrawnAt"
SIGHT_CONE_SIDES = 12
SIGHT_CONE_THICKNESS = 2.0
SIGHT_CONE_PATROL_COLOR = "(R=1.000000,G=0.850000,B=0.100000,A=1.000000)"
SIGHT_CONE_AGGRO_COLOR = "(R=1.000000,G=0.100000,B=0.050000,A=1.000000)"

# ── The behaviour tree (npc/tree.py, step_task.py, steps.py) ─────────────────
#
# The controller no longer loops on a Delay: on possession it runs a Behavior
# Tree, and the tree decides what happens in which order (corpse, hunt,
# notice, patrol). The work itself is still authored into the controller's
# event graph, one custom event per step (BT_<Step>), and one task Blueprint
# per controller calls the event its node's Step names, then finishes with
# the controller's StepResult. See npc/tree.py for the tree.
BB_PATH = f"{NPC_DIR}/BB_ForestWanderer"
# Blackboard keys, mirrored from the controller's own Aggro and AggroReason
# when a sense fires: the tree's Hunt branch is gated on BB_AGGRO_KEY.
BB_AGGRO_KEY = "Aggro"
BB_REASON_KEY = "AggroReason"
STEP_RESULT_VAR = "StepResult"      # on the controller, written by every step
STEP_VAR = "Step"                   # on the task, instance editable
STEP_EVENT_PREFIX = "BT_"

STEP_PULSE = "Pulse"          # possessed? corpse? stats, voice, patrol setup
STEP_WARD = "Ward"            # held off by fire: circle, or run; fails to attack
STEP_STALK = "Stalk"          # a stalker's roar and legs; fails once it charges
STEP_CHASE = "Chase"          # the move order at the player
STEP_SWING = "Swing"          # the melee check and swing
STEP_PRESENT = "PlayerPresent"
STEP_DRAWN = "Drawn"          # a fire in reach: walk to it; fails with none
STEP_STROLL = "Stroll"        # the patrol step
# One step per sense, in priority order: the tree's Senses selector tries
# them left to right, and the first that answers wins.
SENSE_STEPS = (("hurt", "Hurt"), ("sight", "Sight"), ("touch", "Touch"),
               ("sound", "Sound"))


def _stem(ai_path):
    return ai_path.rsplit("/", 1)[-1].removeprefix("BP_")


def tree_path(ai_path):
    """BT_ForestWandererAI[_<Creature>]: one tree per controller, because its
    task class casts to that controller."""
    return f"{NPC_DIR}/BT_{_stem(ai_path)}"


def step_task_path(ai_path):
    return f"{NPC_DIR}/BTT_{_stem(ai_path)}_Step"
