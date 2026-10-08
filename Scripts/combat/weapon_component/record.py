"""The weapon component's part in the inventory's record
(combat/record_vars.py says what it is): the variables the old view still
reads, marked to replicate, each a RepNotify that raises ViewDirty.

The record is no longer written here. The C++ component beside this one on
the character holds it and writes it, with these variables as its mirror, on
a frame something marked (combat/dirty.py: every node that changes what is
carried is followed by MarkInventoryDirty); the Tick's own rewrite, an Add per
column per item every frame, went with task A3a. The shed needs no clear of
its own either: it empties Inventory and Worn, which marks.

Task A3b takes these variables away, with the mirror.
"""

import unreal

from uebp import net
from uebp.g import _G
from uebp.graph import out
from uebp.layout import arrange
from combat.record_vars import HAND as HAND_VARS, REPLICATED, ViewDirty
from uebp.nodes.actor import FN_GET_OWNER, FN_HAS_AUTHORITY


def authority(g):
    """Pure: this machine owns the component's owner (the server, and single
    player)."""
    return out(g.call(FN_HAS_AUTHORITY, self=out(g.call(FN_GET_OWNER))))


def rep_dirty(bp, var, condition):
    """``var`` is a RepNotify whose arrival raises ViewDirty (shot.py's
    AsksServed is one too)."""
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


def replicate_record(bp):
    """Mark what travels and author each OnRep (ViewDirty := true). After
    every declare, which drops the flags, and before the compile."""
    for var in REPLICATED:
        condition = (unreal.LifetimeCondition.COND_SKIP_OWNER if var in HAND_VARS
                     else unreal.LifetimeCondition.COND_OWNER_ONLY)
        rep_dirty(bp, var, condition)
