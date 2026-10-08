"""The weapon component's part in the inventory's record
(combat/record_vars.py says what it is): the test of authority every graph
that asks the server shares, and the RepNotify that raises ViewDirty.

The record is not written here, nor held: the C++ component beside this one
on the character holds it and writes it on a frame something marked
(combat/dirty.py: every node that changes what is carried is followed by
MarkInventoryDirty), and its own RepNotify raises ViewDirty on a client. The
variables that mirrored it for the old view went with task A3b. rep_dirty is
what is left for a variable of this component whose arrival the view must
answer: AsksServed (shot.py).
"""

import unreal

from uebp import net
from uebp.g import _G
from uebp.graph import BEL, out
from uebp.layout import arrange
from combat.record_vars import RETIRED_VARS, ViewDirty
from uebp.nodes.actor import FN_GET_OWNER, FN_HAS_AUTHORITY


def authority(g):
    """Pure: this machine owns the component's owner (the server, and single
    player)."""
    return out(g.call(FN_HAS_AUTHORITY, self=out(g.call(FN_GET_OWNER))))


def rep_dirty(bp, var, condition):
    """``var`` is a RepNotify whose arrival raises ViewDirty (shot.py's
    AsksServed)."""
    ed = net.rep_notify(bp, var, condition)
    stale = [n for n in ed.list_all_nodes()
             if not isinstance(n, unreal.K2Node_FunctionEntry)]
    if stale:
        ed.remove_nodes(stale)
    g = _G(ed)
    g.put(ViewDirty, "true", [ed.find_graph_entry_pin()])
    ed.add_comment_to_nodes(
        "The record changed: the Tick makes this machine's item actors its picture "
        "again (view.py). Blueprint runs this where the server sets the variable "
        "too, and the server never reads ViewDirty.", g.made)
    arrange(ed)


def retire_mirror(bp, ed):
    """The variables that mirrored the record, and each one's OnRep graph,
    taken off a component built before task A3b."""
    for name in RETIRED_VARS:
        ed.remove_member_variable(name)
        BEL.remove_function_graph(bp, f"OnRep_{name}")
    left = [n for n in RETIRED_VARS if BEL.find_graph(bp, f"OnRep_{n}")]
    if left:
        raise RuntimeError(f"the retired record's OnRep graphs are still there: {left}")
