"""Making a noise the wanderers can hear: the one fragment every noise-maker
calls to add a noise to the server's list.

WHY A LIST ON THE WORLD
-----------------------
The emitters (BP_WeaponComponent's shot, BP_FootstepComponent's step) and the
listeners (every wanderer's AI controller) are built by different builders and
share no reference to each other, so a noise is published on the world and
each patrolling wanderer asks for it on its own heartbeat (Scripts/npc/senses.py).
No event dispatch, no list of listeners, and a respawned wanderer hears the
next noise with nothing registering it.

It is a list (task M28: the native UOtherworldNoiseList, a world subsystem;
Source/Otherworld/Public/OtherworldNoise.h), one entry per maker, because the
single record it replaced kept only the loudest noise in the world: of two
players firing far apart, the wanderers near the quieter heard nothing. Each
entry holds the place, the reach, the time and who made it. Only a machine
with authority writes it (a client's call does nothing: only the wanderers'
AI reads it, and that runs on the server), and single player is that machine.

A maker's own entry is still guarded as the one record was: a new noise
replaces it only if it is STALE (older than COMBAT.noise_hold_s) or the new
noise is at least as LOUD. A footstep a fraction of a second after a gunshot
therefore cannot erase the gunshot before the pack has checked for it --
noise_hold_s outlasts one NPC heartbeat, which the verifier asserts. Loudness
is the larger of the two reaches, all-round and cone. An entry older than the
hold is dropped at the next write, so the list is the recent noises: at most
one per player.

What an entry holds is the noise's own reach, because how far a noise
carries belongs to what made it (a pistol, a sprint). The listener only scales
it (AgroSettings.hearing_scale in forest_generator/npc_agro.py).
"""

from combat.tuning import COMBAT
from uebp.graph import _connect, _node, _pin, _set, then
from uebp.nodes.noise import FN_MAKE_NOISE


def _author_make_noise(ed, exec_in, maker, location, reach,
                       direction=None, cone_reach=None, cone_cos=1.0):
    """Add a noise to the world's list. Returns ``(nodes, then_pin)``.

        exec_in -> MakeNoise(Maker, Location, Reach, Direction, ConeReach,
                             ConeCos, HoldSeconds = COMBAT.noise_hold_s) -> then

    ``maker`` (the pawn that made it), ``location``, ``reach`` and the
    optional ``direction``/``cone_reach`` are data pins; ``cone_cos`` is a
    literal. An all-round noise leaves ``cone_reach`` None, which leaves the
    cone's reach at 0 -- nothing is ever inside a cone that reaches nowhere.
    The authority test and the stale-or-louder guard are the node's own.
    """
    make = _node(ed, FN_MAKE_NOISE)
    _connect(exec_in, _pin(make, "execute"))
    _connect(maker, _pin(make, "Maker"))
    _connect(location, _pin(make, "Location"))
    _connect(reach, _pin(make, "Reach"))
    if cone_reach is not None:
        _connect(direction, _pin(make, "Direction"))
        _connect(cone_reach, _pin(make, "ConeReach"))
    _set(make, "ConeCos", cone_cos)
    _set(make, "HoldSeconds", COMBAT.noise_hold_s)
    return [make], then(make)
