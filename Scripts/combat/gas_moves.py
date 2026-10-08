"""Which of the Game Animation Sample's extra moves the player has (task G5):
each switch of gas_moves_tuning.py, and the motion-matching body under it.
The builders and the verifiers ask here, never the constants alone: on the
mannequin fallback (no sample, or GAS_LOCOMOTION off) all three are off.
"""

from combat.gas_moves_tuning import GAS_CROUCH, GAS_SLIDE, GAS_TRAVERSAL
from combat.skin import player_skin


def crouch_on():
    """The crouch is the sample's crouch set, not the layers' two clips."""
    return bool(GAS_CROUCH and player_skin().gas)


def slide_on():
    """The crouch key in a sprint slides."""
    return bool(GAS_SLIDE and player_skin().gas)


def traversal_on():
    """The jump key in front of a traversable block climbs it."""
    return bool(GAS_TRAVERSAL and player_skin().gas)
