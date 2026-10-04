"""The monsters' sounds: the zombie's growls (on patrol, as it goes aggro, as
it swings), the wendigo's roar, the thud of a wanderer's blow on the player,
the wanderers' footsteps, and the roar's own attenuation curve.

SOUNDS is the area's rows of the sound table and BINDINGS where each is played
from. Every creature's AI controller holds four arrays of takes, one drawn per
play (Sound/play.py); an empty one is silence:

    Voices        its voice on a timer (npc/stats.py; who keeps quiet on
                  patrol, and who on the hunt, is forest_generator/npc_voice.py),
                  and the wendigo's roars (npc/roar.py, stalk.py, ward_roar.py)
    AggroVoices   the once, as it notices the player (npc/agro.py)
    AttackVoices  as a swing starts (npc/melee.py)
    HitSounds     the thud where a swing lands (npc/melee.py)

and the wanderers' footsteps are the Sounds of BP_ForestWanderer's own
FootstepComponent (the component is the player's too: combat/footsteps.py).

To give a creature another voice, change its row of VOICES (or AGGRO_VOICES,
ATTACK_VOICES) and run Scripts/build_sound.py: no other build is needed.
"""

from forest_generator.npc_placement import NPC_VARIANTS
from npc.monster_tuning import monster_specs
from npc.paths import (
    AGGRO_VOICES_VAR, AI_BP_PATH, ATTACK_VOICES_VAR, HIT_SOUNDS_VAR, NPC_BP_PATH, VOICES_VAR)
from Sound.sound_def import (
    ATT_FOOTSTEP, ATT_VOICE, AUDIBLE_LIMIT_CM, AttenuationProfile, Binding, Sound, takes)
from Sound.sound_weapons import MELEE_HIT

# A wendigo roars as it goes aggro, so the roar has to reach a player it has
# only just seen: it carries this many times the wendigo's aggro range (its
# sight, monster_tuning.csv's vision_range_cm: 35 m, so 61 m), and never past
# the 100 m ceiling. Sized from the tuned range when the build runs, so a range
# saved from the MONSTER SETTINGS tab moves the roar with the next weapons build.
ROAR_REACH_X_AGGRO = 1.75
ROAR_CREATURE = "Wendigo"


def roar_reach_cm():
    """How far the wendigo's roar is heard, in cm."""
    return min(ROAR_REACH_X_AGGRO * monster_specs(ROAR_CREATURE)["vision_range_cm"],
               AUDIBLE_LIMIT_CM)


# THE ROAR IS HEARD FAR OFF, so it has a curve of its own. On the natural (dB)
# curve every other sound uses, a wendigo that saw the player from 35 m roared
# at about -34 dB: the loudest thing in the forest, and barely there. The
# curve is steep by design -- it reaches -60 dB at the edge, and is half way
# there in dB at half the distance -- which suits a noise heard close and is
# wrong for one whose whole purpose is to arrive from far away.
#
# So the roar is at full volume out to ROAR_FULL_CM and falls in a straight
# line from there to silence at its reach: at 35 m that is about half, -6 dB.
# Close up it is no louder than the recording (a multiplier never passes 1),
# so a wendigo that turns on the player at arm's length does not deafen them.
ROAR_FULL_CM = 1000.0
ATT_ROAR = AttenuationProfile("A_Att_WendigoRoar", ROAR_FULL_CM,
                              roar_reach_cm() - ROAR_FULL_CM, linear=True)

# Several takes per creature and the controller draws one at random, because a
# pack of ten on a 4-9 s timer playing the same buffer is audibly one sound.
#
# THE ZOMBIE'S GROWLS are one set of takes (the selection's zombie_growl,
# A_ZombieGrowl_01 and on), dealt out by number, counted from 1 as the audition
# page and the asset names do: these as it swings, this one as it goes aggro,
# and every other one on patrol, on the timer.
ZOMBIE_ATTACK_TAKES = (1, 2, 4)
ZOMBIE_AGGRO_TAKES = (10,)
_GROWLS = takes("zombie_growl")


def _growls(numbers):
    return tuple(_GROWLS[n - 1] for n in numbers)


# The growls carry further than the zombie sees (ATT_VOICE: 50 m), and the one
# it gives as it goes aggro as far as the wendigo's roar does, on the roar's
# own curve: a zombie that had noticed the player was not heard to.
ZOMBIE_GROWL = Sound("zombie_growl", "zombie growl", _growls(
    n for n in range(1, len(_GROWLS) + 1)
    if n not in ZOMBIE_ATTACK_TAKES + ZOMBIE_AGGRO_TAKES), ATT_VOICE)
ZOMBIE_ATTACK = Sound("zombie_attack_growl", "zombie attack", _growls(ZOMBIE_ATTACK_TAKES),
                      ATT_VOICE)
ZOMBIE_AGGRO = Sound("zombie_aggro_growl", "zombie aggro", _growls(ZOMBIE_AGGRO_TAKES),
                     ATT_ROAR)
WENDIGO_ROAR = Sound("wendigo_roar", "wendigo roar", takes("wendigo_roar"), ATT_ROAR)
# A wanderer's footfall: takes of its own (heavier than the player's leaves)
# and a volume of its own, so a pack running up is heard over one's own feet.
MONSTER_FOOTSTEPS = Sound("monster_footsteps", "monster footsteps",
                          takes("footsteps_monster"), ATT_FOOTSTEP)
SOUNDS = (ZOMBIE_GROWL, WENDIGO_ROAR, ZOMBIE_ATTACK, ZOMBIE_AGGRO, MONSTER_FOOTSTEPS)

# Each creature's voices (NPC_VARIANTS' key), by the controller variable that
# plays them. One with no row in a table is mute there: the wendigo roars as
# it goes aggro in a step of its own, and swings in silence.
VOICES = {"Zombie": ZOMBIE_GROWL, "Wendigo": WENDIGO_ROAR}
AGGRO_VOICES = {"Zombie": ZOMBIE_AGGRO}
ATTACK_VOICES = {"Zombie": ZOMBIE_ATTACK}
_BY_VAR = ((VOICES_VAR, VOICES), (AGGRO_VOICES_VAR, AGGRO_VOICES),
           (ATTACK_VOICES_VAR, ATTACK_VOICES))
# A wanderer's blow on the player is the fist's thud (sound_weapons.py).
HIT_SOUNDS = MELEE_HIT.paths
# The footstep component as BP_ForestWanderer wears it (combat/install.py),
# and the variable of it that holds the takes (combat/footstep_vars.py).
FOOTSTEP_COMPONENT = "FootstepComponent"
FOOTSTEP_SOUNDS_VAR = "Sounds"


def voices_of(key):
    """The creature's voice takes, as asset paths; () for a mute one."""
    return VOICES[key].paths if key in VOICES else ()


BINDINGS = (Binding(AI_BP_PATH, HIT_SOUNDS_VAR, MELEE_HIT),) + tuple(
    Binding(v.ai_blueprint, HIT_SOUNDS_VAR, MELEE_HIT) for v in NPC_VARIANTS
) + tuple(
    Binding(v.ai_blueprint, var, table[v.key])
    for var, table in _BY_VAR for v in NPC_VARIANTS if v.key in table
) + (Binding(NPC_BP_PATH, FOOTSTEP_SOUNDS_VAR, MONSTER_FOOTSTEPS,
             component=FOOTSTEP_COMPONENT),)
