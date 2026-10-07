"""uebp.nodes.shot -- the game's own shot library (C++, the Otherworld
module: Source/Otherworld/Public/OtherworldShotLibrary.h). The pellet's
trace, which on a server judges a remote shooter's shot against where every
character stood when it fired (lag compensation, task M22).
"""

SHOT_LIBRARY = "/Script/Otherworld.OtherworldShotLibrary"

# Shooter, Start, End, MaxRewindSeconds, ExtraRewindSeconds -> ReturnValue
# (stopped on something), OutHit, bBodyHit, BodyBone, BodyPoint. The pellet's
# one node: the Visibility trace and the struck character's body trace.
FN_SHOT_TRACE = SHOT_LIBRARY + ".ShotTrace"
# For the probes: the rewind a shooter gets, and what the history did.
FN_REWIND_SECONDS_FOR = SHOT_LIBRARY + ".RewindSecondsFor"
FN_HIT_HISTORY_SAMPLES = SHOT_LIBRARY + ".HitHistorySamples"
