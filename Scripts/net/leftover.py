"""What a graph says when it leaves an actor in the world, and when one is
taken out of it (task M31): one node each, the server's list of leftovers
(uebp/nodes/leftover.py). The node does nothing in single player or on a
client, so a graph calls it wherever the thing comes to be left and asks no
question about the mode.
"""

from net.leftover_consts import Leftover
from uebp.g import _G
from uebp.graph import then
from uebp.nodes.leftover import FN_LEFT_IN_WORLD, FN_TAKEN_FROM_WORLD


def author_left(ed, row: Leftover, exec_ins, actor=None):
    """``actor`` (the graph's own actor, given none) is left in the world from
    here, by ``row``'s rule. Returns the exec pin after it."""
    g = _G(ed)
    noted = g.call(FN_LEFT_IN_WORLD, list(exec_ins), Kind=row.kind,
                   LifetimeSeconds=f"{row.lifetime_s:.1f}", Cap=row.cap,
                   **({"Actor": actor} if actor is not None else {}))
    return then(noted)


def author_taken(ed, exec_ins, actor=None):
    """``actor`` is taken out of the world: no rule applies to it while it is
    carried. Returns the exec pin after it."""
    g = _G(ed)
    taken = g.call(FN_TAKEN_FROM_WORLD, list(exec_ins),
                   **({"Actor": actor} if actor is not None else {}))
    return then(taken)
