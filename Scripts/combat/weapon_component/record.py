"""The server's half of the inventory's record (combat/record_vars.py says
what it is): written off the item actors each Tick, emptied at death, and
marked to replicate.

    upkeep, after the slot sync, with authority (so in single player too):
        InvClass, InvSlot, InvLoaded, InvReserve := a row per item of Inventory
        HandClass := the class of SlotItems[HAND], written when it changes

Written every Tick rather than at each change: thirty-odd graphs change what
is carried (a shot, a reload, a pick-up, a throw, a meal) and the record is
right after any of them, with no call to remember. Property replication
compares before it sends, so a record that did not change costs no traffic.

The dead gate stops the upkeep, so the shed (shed.py) empties the record
itself when the gear goes onto the body.
"""

import unreal

from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _pin, out, then
from uebp.layout import arrange
from combat import item_vars as IV
from combat.paths import ITEM_CLASS_PATH
from combat.record_vars import HandClass, RECORD, REPLICATED, ViewDirty
from combat.slot_tuning import HAND, SLOT_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.slot_nodes import for_each, slot_at, valid
from uebp.nodes.actor import FN_GET_OWNER, FN_HAS_AUTHORITY
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_CLEAR
from uebp.nodes.math import FN_NE_CC
from uebp.nodes.system import FN_OBJECT_CLASS

# What each column of a row is read from: the item's class, then its variables.
COLUMNS = (None, SLOT_VAR, IV.Loaded, IV.Reserve)


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
        condition = (unreal.LifetimeCondition.COND_SKIP_OWNER if var == HandClass
                     else unreal.LifetimeCondition.COND_OWNER_ONLY)
        rep_dirty(bp, var, condition)


def _author_clear(g, execs):
    flow = list(execs)
    for var in RECORD:
        flow = [then(g.call(FN_ARR_CLEAR, flow, TargetArray=g.get(var)))]
    return flow[0]


def author_empty_record(g, execs):
    """The shed's: with authority, no rows and nothing in hand. Returns the
    exec tails."""
    server, client = g.branch(authority(g), execs)
    flow = _author_clear(g, [server])
    return [g.put(HandClass, None, [flow]), client]


def _author_record(ed, in_execs):
    """Write the record (see the module docstring). Returns the exec tails."""
    g = _G(ed, ITEM_CLASS_PATH)
    server, client = g.branch(authority(g), in_execs)
    flow = _author_clear(g, [server])
    item, _i, body, done = for_each(g, g.get(WV.Inventory), [flow])
    row, _gone = g.branch(valid(g, item), [body])
    for var, column in zip(RECORD, COLUMNS):
        value = (g.iget(item, column) if column
                 else out(g.call(FN_OBJECT_CLASS, Object=item)))
        row = then(g.call(FN_ARR_ADD, [row], TargetArray=g.get(var), NewItem=value))
    # None for empty hands: GetObjectClass answers a null object with no class.
    in_hand = out(g.call(FN_OBJECT_CLASS, Object=slot_at(g, HAND)))
    changed, same = g.branch(out(g.call(FN_NE_CC, A=in_hand, B=g.get(HandClass))), [done])
    told = g.put(HandClass, in_hand, [changed])
    ed.add_comment_to_nodes(
        "The inventory's record (record.py), the server's: a row per carried item "
        "(class, slot, rounds loaded, rounds in reserve), replicated to the owning "
        "client, and the class in hand, replicated to everyone else. Plain data: the "
        "save writes it as it stands.", g.made[:4])
    return [told, same, client]
