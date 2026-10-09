"""BP_ForestWandererAI's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE, and each fragment its own group below, where it always has. The names
are npc/paths.py's; a fragment's graph still reads them from there.

Every row but the Tune* ones starts at zero, false or none, which is what a
declaration leaves and the right start for each (the fragments say why). The
Tune* defaults are the creature's, written by npc/tuned.write_tuned_defaults.
"""

from uebp.vars import BOOL, FLOAT, INT, NAME, STRING, VECTOR, Var, array, obj
from npc import paths as P
from npc.monster_tuning import MONSTER_STATS

_ACTOR = obj("/Script/Engine.Actor")

# Each NPC's swing timer. Zero is the right default -- it means "may attack
# immediately" -- which is just as well, since add_member_variable's own
# default-value argument silently does not apply (see CLAUDE.md).
NextAttackTime = Var("NextAttackTime", FLOAT)

TABLE = (NextAttackTime,)

# What the swing being landed deals, after the player's guard (npc/block.py).
HIT = (Var(P.HIT_DAMAGE_VAR, FLOAT),)

# npc/steps.py: what the step that just ran answered.
STEPS = (Var(P.STEP_RESULT_VAR, BOOL),)

# npc/agro.py: not aggro, not set up, a patrol point due immediately.
AGRO = (Var(P.AGGRO_VAR, BOOL), Var(P.PATROL_READY_VAR, BOOL),
        Var(P.AGGRO_REASON_VAR, STRING),
        Var(P.RUN_SPEED_VAR, FLOAT), Var(P.NEXT_PATROL_VAR, FLOAT),
        Var(P.PATROL_HOME_VAR, VECTOR), Var(P.PATROL_TARGET_VAR, VECTOR))

# npc/tuned.py: one float per MONSTER_STATS row.
TUNED = tuple(Var(var, FLOAT) for _col, var, *_rest in MONSTER_STATS)

# npc/stats.py: the stats applied once, the voice, the takes and the reactions.
STATS = (Var(P.STATS_APPLIED_VAR, BOOL), Var(P.NEXT_VOICE_VAR, FLOAT),
         Var(P.APPLIED_HEALTH_VAR, FLOAT),
         *(Var(name, array(obj("/Script/Engine.SoundBase"))) for name in P.SOUND_ARRAY_VARS),
         Var(P.REACTIONS_VAR, array(obj("/Script/Engine.AnimSequenceBase"))))

# npc/corpse.py, npc/sight_cone.py, npc/strafe.py, npc/drawn.py.
CORPSE = (Var(P.CORPSE_VAR, BOOL),)
SIGHT_CONE = (Var(P.SIGHT_CONE_STAMP_VAR, FLOAT),)
STRAFE = (Var(P.STRAFE_YAW_VAR, FLOAT), Var(P.STRAFE_DIST_VAR, FLOAT),
          Var(P.STRAFE_FOR_VAR, FLOAT))
DRAWN = (Var(P.DRAWN_VAR, BOOL), Var(P.DRAWN_TO_VAR, _ACTOR))

# npc/stalk.py, then npc/stalk_cover.py's leg.
STALK = (Var(P.STALK_ROAR_UNTIL_VAR, FLOAT), Var(P.STALK_SIDE_VAR, FLOAT),
         Var(P.STALK_TURN_AT_VAR, FLOAT), Var(P.STALK_CHARGING_VAR, BOOL),
         Var(P.ENRAGED_VAR, BOOL),
         # Where the player stood when it roared: the zero vector until then.
         Var(P.STALK_ORIGIN_VAR, VECTOR))
STALK_COVER = (Var(P.STALK_COVER_VAR, VECTOR), Var(P.STALK_HIDDEN_VAR, BOOL),
               Var(P.STALK_ARRIVED_VAR, BOOL), Var(P.STALK_LEG_UNTIL_VAR, FLOAT),
               Var(P.STALK_LEGS_VAR, INT), Var(P.STALK_IGNORE_VAR, array(_ACTOR)))

# npc/ward.py, then npc/ward_roar.py.
WARD = (Var(P.WARD_SINCE_VAR, FLOAT), Var(P.WARD_LAST_VAR, FLOAT),
        Var(P.WARD_SIDE_VAR, FLOAT), Var(P.WARD_TURN_AT_VAR, FLOAT),
        Var(P.WARD_FLEE_UNTIL_VAR, FLOAT), Var(P.WARD_FLEE_GOAL_VAR, VECTOR))
WARD_ROAR = (Var(P.WARD_ROAR_AT_VAR, FLOAT), Var(P.WARD_ROAR_UNTIL_VAR, FLOAT))

# The step task's one (a Blueprint of its own per creature: npc/step_task.py).
STEP_TASK = (Var(P.STEP_VAR, NAME),)
