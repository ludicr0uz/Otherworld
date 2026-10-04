"""Play one of several sounds: the random pick the voice and the melee
impact both go through.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from uebp.nodes.array import FN_ARR_GET, FN_ARR_LEN
from uebp.nodes.math import FN_GREATER_II, FN_RAND_INT, FN_SUB_II
from uebp.nodes.system import FN_PLAY_SOUND


# ─── Playing one of several sounds ──────────────────────────────────────────

def _author_random_sound(ed, var_name, at_pin, exec_in):
    """Play a random element of the ``var_name`` sound array at ``at_pin``.

    Returns ``(nodes, then_pin)``.  The array is guarded on its own length:
    RandomIntegerInRange(0, -1) against an empty array feeds Array_Get an index
    into nothing, which is an access-none at runtime rather than silence.  That
    matters here because the arrays are filled from /Game/Audio, which a
    checkout that has never run Scripts/Sound/make_creature_sounds.py does not have
    -- an unvoiced monster is a fine outcome, a spammed error log is not.

    One sound is drawn per call rather than cycling, and there are three of
    each: a pack of ten retriggering a single buffer on a shared timer reads
    as one machine, which is the same lockstep problem gait_scale_for_index
    solves for the legs.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    table = keep(ed.add_get_member_variable_node(var_name))
    table_out = out(table, var_name)

    count = keep(_node(ed, FN_ARR_LEN))
    _connect(table_out, _pin(count, "TargetArray"))
    stocked = keep(_node(ed, FN_GREATER_II))
    _connect(out(count), _pin(stocked, "A"))
    _set(stocked, "B", 0)

    have = keep(ed.add_branch_node())
    _connect(out(stocked), _pin(have, "Condition"))
    _connect(exec_in, _pin(have, "execute"))

    # RandomIntegerInRange is inclusive at both ends, so the top is length - 1.
    top = keep(_node(ed, FN_SUB_II))
    _connect(out(count), _pin(top, "A"))
    _set(top, "B", 1)
    which = keep(_node(ed, FN_RAND_INT))
    _set(which, "Min", 0)
    _connect(out(top), _pin(which, "Max"))
    pick = keep(_node(ed, FN_ARR_GET))
    _connect(table_out, _pin(pick, "TargetArray"))
    _connect(out(which), _pin(pick, "Index"))

    play = keep(_node(ed, FN_PLAY_SOUND))
    _connect(out(pick, "Item"), _pin(play, "Sound"))
    _connect(at_pin, _pin(play, "Location"))
    _connect(then(have), _pin(play, "execute"))

    # A join node so the caller has ONE exec to carry on from whether or not
    # there was a sound to play. Without it the empty-array path dangles and
    # the chase loop ends the first time a wanderer tries to speak.
    join = keep(ed.add_branch_node())
    _set(join, "Condition", True)
    _connect(then(play), _pin(join, "execute"))
    _connect(else_(have), _pin(join, "execute"))
    return made, then(join)
