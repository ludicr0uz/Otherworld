"""The monsters' sounds: the zombie's growl, the wendigo's roar, the thud of a
wanderer's blow on the player, and the roar's own attenuation curve.

SOUNDS is the area's rows of the sound table and BINDINGS where each is played
from: every creature's AI controller holds its voice as Voices and the blow
as HitSounds (arrays of takes, one drawn per play: Sound/play.py). When they
play is the tree's: the voice on a timer (npc/stats.py; who keeps quiet on
patrol is forest_generator/npc_voice.py), the roar at the hunt (npc/roar.py,
npc/stalk.py, npc/ward_roar.py), the thud where a swing lands (npc/melee.py).

To give a creature another voice, change its row of VOICES and run
Scripts/build_sound.py: no other build is needed.
"""

from forest_generator.npc_placement import NPC_VARIANTS
from npc.monster_tuning import monster_specs
from npc.paths import AI_BP_PATH, HIT_SOUNDS_VAR, VOICES_VAR
from Sound.sound_def import (
    ATT_CREATURE, AUDIBLE_LIMIT_CM, AttenuationProfile, Binding, Sound, takes)
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
ZOMBIE_GROWL = Sound("zombie_growl", "zombie growl", takes("zombie_growl"), ATT_CREATURE)
WENDIGO_ROAR = Sound("wendigo_roar", "wendigo roar", takes("wendigo_roar"), ATT_ROAR)
SOUNDS = (ZOMBIE_GROWL, WENDIGO_ROAR)

# Each creature's voice (NPC_VARIANTS' key). One with no row is mute.
VOICES = {"Zombie": ZOMBIE_GROWL, "Wendigo": WENDIGO_ROAR}
# A wanderer's blow on the player is the fist's thud (sound_weapons.py).
HIT_SOUNDS = MELEE_HIT.paths


def voices_of(key):
    """The creature's voice takes, as asset paths; () for a mute one."""
    return VOICES[key].paths if key in VOICES else ()


BINDINGS = (Binding(AI_BP_PATH, HIT_SOUNDS_VAR, MELEE_HIT),) + tuple(
    Binding(v.ai_blueprint, HIT_SOUNDS_VAR, MELEE_HIT) for v in NPC_VARIANTS
) + tuple(
    Binding(v.ai_blueprint, VOICES_VAR, VOICES[v.key]) for v in NPC_VARIANTS if v.key in VOICES)
