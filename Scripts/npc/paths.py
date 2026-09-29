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

INF = 1.0e9

# Where the creature voices and the impact sounds are imported to, by
# combat.audio.import_sounds().
VOICES_VAR = "Voices"
HIT_SOUNDS_VAR = "HitSounds"
STATS_APPLIED_VAR = "StatsApplied"
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
