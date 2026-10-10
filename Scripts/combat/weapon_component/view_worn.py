"""A client's worn garments: a picture of the worn slots the server sent
(combat/record_vars.py; read with WornRow, uebp/nodes/inventory.py), as its
bag is of the record's rows (view.py). Never run with authority, but for the one call per slot a loaded
profile makes of ViewWorn to wear what it saved (graphics_menu/profile_read.py).

The owner is sent the record, and WornRow reads its Worn. Everyone else is
sent the same classes beside HandClass (the record component's WornClasses,
skip-owner), and on their copy of the character WornRow reads those: so every
client's copy of a character has the garments in Worn, and each is drawn on
the body (wear_draw.py DrawWorn) by the machine that made it.

    the view, when a record arrived (view.py calls this while ViewDirty):
        ViewWorn(slot, WornRow(owner, slot)) for each slot of the record
        every actor of Worn past the rows destroyed, Worn cut to their count

    ViewWorn(Slot, Class)
        Worn[Slot] is an actor of Class --> kept
        otherwise --> what is there is taken off the body (DrawWorn off) and
                      destroyed; a Class: one spawned in its place (a local
                      actor, never replicated), hidden, not Dropped and
                      UNPLACED, as the server's worn garment is, and drawn
                      on the body (DrawWorn on); none: Worn[Slot] = None

The I panel reads Worn's actors (graphics_menu/wear_draw.py, inv_drag.py), so
with these it draws a client's worn slots as it draws single player's. The
shed empties Worn on every copy (shed.py), and the server's record with it,
so a dead player's picture is nothing; the dead gate stops this view, so
what the body was drawn in stays on the corpse.
"""

from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, out, then
from uebp.net import custom_event
from combat import item_vars as IV
from combat.paths import ITEM_CLASS_PATH
from combat.record_vars import VIEW_WORN, WORN_PARAMS
from combat.slot_tuning import SLOT_VAR, UNPLACED
from combat.wear_tuning import WORN_VAR
from combat.weapon_component.slot_nodes import for_each, op, valid
from combat.weapon_component.slot_moves import _ask
from combat.weapon_component.wear_draw import draw_worn
from uebp.nodes.actor import FN_DESTROY, FN_GET_OWNER, FN_GET_TRANSFORM, FN_SET_HIDDEN
from uebp.nodes.array import FN_ARR_GET, FN_ARR_RESIZE, FN_ARR_SET, FN_ARR_VALID
from uebp.nodes.inventory import FN_WORN_ROW, FN_WORN_ROW_COUNT
from uebp.nodes.math import FN_EQ_CC, FN_GE_II
from uebp.nodes.palette import NODE_SPAWN
from uebp.nodes.system import FN_IS_VALID_CLASS, FN_OBJECT_CLASS


def author_view_worn_event(ed):
    """ViewWorn (see the module docstring). Before the Tick, which calls it
    by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(custom_event(ed, VIEW_WORN, WORN_PARAMS))
    slot, want = out(event, "Slot"), out(event, "Class")
    inside = g.call(FN_ARR_VALID, TargetArray=g.get(WORN_VAR), IndexToTest=slot)
    there, beyond = g.branch(out(inside), [then(event)])
    cur = _loose_pin(g.call(FN_ARR_GET, TargetArray=g.get(WORN_VAR), Index=slot), "Item",
                     is_input=False)
    alive, gone = g.branch(valid(g, cur), [there])
    same = out(g.call(FN_EQ_CC, A=out(g.call(FN_OBJECT_CLASS, Object=cur)), B=want))
    _keep, replace = g.branch(same, [alive])
    destroyed = then(g.call(FN_DESTROY, [draw_worn(g, cur, False, [replace])], self=cur))

    worn, bare = g.branch(out(g.call(FN_IS_VALID_CLASS, Class=want)),
                          [destroyed, gone, beyond])
    spawn = g.keep(_palette(ed, NODE_SPAWN))
    _connect(want, _pin(spawn, "Class"))
    where = g.call(FN_GET_TRANSFORM, self=out(g.call(FN_GET_OWNER)))
    _connect(out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(worn, _pin(spawn, "execute"))
    put = g.call(FN_ARR_SET, [then(spawn)], TargetArray=g.get(WORN_VAR), Index=slot,
                 Item=out(spawn))
    _set(put, "bSizeToFit", True)
    hide = g.call(FN_SET_HIDDEN, [then(put)], self=out(spawn))
    _set(hide, "bNewHidden", True)
    flow = g.iput(out(spawn), IV.Dropped, "false", [then(hide)])
    flow = g.iput(out(spawn), SLOT_VAR, str(UNPLACED), [flow])
    draw_worn(g, out(spawn), True, [flow])
    # Item left unconnected: Worn[Slot] = None.
    off = g.call(FN_ARR_SET, [bare], TargetArray=g.get(WORN_VAR), Index=slot)
    _set(off, "bSizeToFit", True)
    ed.add_comment_to_nodes(
        f"{VIEW_WORN} (view_worn.py), a client's: Worn[Slot] is made to be the "
        "record's row for it. A garment of the right class is kept; anything else "
        "is taken off the body and destroyed, and a local actor of the class spawned "
        "there, hidden and not Dropped, and drawn on the body, or the slot emptied.",
        g.made)


def author_view_worn(g, execs):
    """The worn slots remade off the record (see the module docstring), in
    the view's dirty arm. Returns the exec tail."""
    # Here, not at the top: view.py imports this module.
    from combat.weapon_component.view import carrier, rows_loop
    rows = out(g.call(FN_WORN_ROW_COUNT, Carrier=carrier(g)))
    i, body, done = rows_loop(g, rows, execs)
    worn = g.call(FN_WORN_ROW, Carrier=carrier(g), Slot=i, Kind=ITEM_CLASS_PATH)
    _ask(g, VIEW_WORN, [body], Slot=i, Class=out(worn, "Class"))
    item, j, each, trimmed = for_each(g, g.get(WORN_VAR), [done])
    extra, _ = g.branch(op(g, FN_GE_II, j, rows), [each])
    real, _ = g.branch(valid(g, item), [extra])
    g.call(FN_DESTROY, [draw_worn(g, item, False, [real])], self=item)
    cut = g.call(FN_ARR_RESIZE, [trimmed], TargetArray=g.get(WORN_VAR), Size=rows)
    return then(cut)
