"""BP_ForestWanderer's own graph, named once: its two Multicast events, their
parameters, and its variables as a table (uebp/vars.py). Constants only;
npc/body_fx.py authors them and is how a controller's step calls them.

The parameters carry the names of the engine nodes they stand in for
(PlaySoundAtLocation's Sound and Location, PlaySlotAnimationAsDynamicMontage's
Asset and SlotNodeName), so a check that finds a step's voice or its clip by
those pins reads the same on the call as it did on the node.
"""

from npc.paths import NPC_BP_PATH
from uebp.vars import FLOAT, INT, NAME, VECTOR, Var, obj

NPC_CLASS_PATH = f"{NPC_BP_PATH}.{NPC_BP_PATH.rsplit('/', 1)[-1]}_C"

# A growl, a roar, a snarl, the thud of a blow: heard on every machine.
VOICE_EVENT = "Multicast_Voice"
VOICE_PARAMS = (("Sound", obj("/Script/Engine.SoundBase")), ("Location", VECTOR))
# The swing and the roar: played into the body's slot on every machine.
CLIP_EVENT = "Multicast_Clip"
CLIP_PARAMS = (("Asset", obj("/Script/Engine.AnimSequenceBase")), ("SlotNodeName", NAME),
               ("BlendInTime", FLOAT), ("BlendOutTime", FLOAT))
# What a verifier sees on a controller's cast to the body (BEL.get_node_title).
BODY_CAST_TITLE = "Cast To BP_ForestWanderer"
FN_MULTICAST_VOICE = f"{NPC_CLASS_PATH}:{VOICE_EVENT}"
FN_MULTICAST_CLIP = f"{NPC_CLASS_PATH}:{CLIP_EVENT}"

# How many of each this machine's copy of the body has played: what a probe
# on a client reads to know the server's word arrived. Not replicated.
VoicesPlayed = Var("VoicesPlayed", INT)
ClipsPlayed = Var("ClipsPlayed", INT)
TABLE = (VoicesPlayed, ClipsPlayed)
