"""The server's half of the inventory's record (combat/record_vars.py says
what it is): written off the item actors each Tick, emptied at death, and
marked to replicate.

    upkeep, after the slot sync, with authority (so in single player too):
        InvClass, InvSlot, InvLoaded, InvReserve, InvLit, InvHot := a row
            per item of Inventory
        WornClass := a row per slot of Worn: the garment's class, or none
        HandClass := the class of SlotItems[HAND], written when it changes
        HandLit, HandHot := that item's Lit and Hot (false for empty hands),
            written when either changes

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
from combat.heat_tuning import HOT_VAR
from combat.record_vars import (
    HAND as HAND_VARS, HandClass, HandHot, HandLit, RECORD, REPLICATED, ViewDirty, WornClass)
from combat.torch_tuning import LIT_VAR
from combat.wear_tuning import WORN_VAR
from combat.slot_tuning import HAND, SLOT_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.slot_nodes import for_each, slot_at, valid
from uebp.nodes.actor import FN_GET_OWNER, FN_HAS_AUTHORITY
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_CLEAR
from uebp.nodes.math import FN_NE_CC, FN_NEQ_BB, FN_OR
from uebp.nodes.system import FN_OBJECT_CLASS

# What each column of a row is read from: the item's class, then its variables.
COLUMNS = (None, SLOT_VAR, IV.Loaded, IV.Reserve, LIT_VAR, HOT_VAR)


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


def _author_worn_record(g, execs):
    """WornClass := a row per slot of Worn (task M24). Returns Completed."""
    flow = then(g.call(FN_ARR_CLEAR, execs, TargetArray=g.get(WornClass)))
    item, _i, body, done = for_each(g, g.get(WORN_VAR), [flow])
    worn, bare = g.branch(valid(g, item), [body])
    g.call(FN_ARR_ADD, [worn], TargetArray=g.get(WornClass),
           NewItem=out(g.call(FN_OBJECT_CLASS, Object=item)))
    # NewItem left unconnected: no class, an empty slot.
    g.call(FN_ARR_ADD, [bare], TargetArray=g.get(WornClass))
    return done


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
    flow = then(g.call(FN_ARR_CLEAR, [flow], TargetArray=g.get(WornClass)))
    flow = g.put(HandClass, None, [flow])
    flow = g.put(HandLit, "false", [flow])
    return [g.put(HandHot, "false", [flow]), client]


def _author_hand_fire(g, execs):
    """HandLit, HandHot := the Lit and Hot of the item in hand (task M25),
    written when either changes. The item's flags are read behind IsValid.
    Returns the exec tails."""
    item = slot_at(g, HAND)
    armed, bare = g.branch(valid(g, item), execs)
    lit, hot = g.iget(item, LIT_VAR), g.iget(item, HOT_VAR)
    differs = out(g.call(FN_OR, A=out(g.call(FN_NEQ_BB, A=lit, B=g.get(HandLit))),
                         B=out(g.call(FN_NEQ_BB, A=hot, B=g.get(HandHot)))))
    changed, same = g.branch(differs, [armed])
    told = g.put(HandHot, hot, [g.put(HandLit, lit, [changed])])
    # Empty hands: neither.
    stale, clear = g.branch(out(g.call(FN_OR, A=g.get(HandLit), B=g.get(HandHot))), [bare])
    none = g.put(HandHot, "false", [g.put(HandLit, "false", [stale])])
    return [told, same, none, clear]


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
    done = _author_worn_record(g, [done])
    in_hand = out(g.call(FN_OBJECT_CLASS, Object=slot_at(g, HAND)))
    changed, same = g.branch(out(g.call(FN_NE_CC, A=in_hand, B=g.get(HandClass))), [done])
    told = g.put(HandClass, in_hand, [changed])
    tails = _author_hand_fire(g, [told, same])
    ed.add_comment_to_nodes(
        "The inventory's record (record.py), the server's: a row per carried item "
        "(class, slot, rounds loaded, rounds in reserve, burning, hot) and a class per worn slot, "
        "replicated to the owning client, and the class in hand and whether it burns or glows, "
        "replicated to everyone else. Plain data: the "
        "save writes it as it stands.", g.made[:4])
    return tails + [client]
