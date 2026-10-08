"""A client's half of the inventory's record (combat/record_vars.py): its
item actors are a picture of what the server says is carried, remade when a
record arrives. Never run with authority.

The record is the C++ component's, one struct that arrives whole; the graph
reads it through the inventory library (uebp/nodes/inventory.py), a row at a
time, and keeps no copy. The component's RepNotify raises ViewDirty.

    upkeep, without authority, when ViewDirty:
        the record has rows (this machine's own player: only the owner is
        sent them) --> ViewRow(i, InventoryRow(owner, i)) for each,
                       ViewTrim(rows)
        it has none (another player's character, or an owner carrying
        nothing) --> HandRow(owner) has a class: ViewRow(0, that class, HAND,
                                    unknown ammo), ViewTrim(1)
                     none: ViewTrim(0)

    ViewRow(Index, Class, Slot, Loaded, Reserve)
        Inventory[Index] is an actor of Class --> kept
        otherwise --> what is there is destroyed, one of Class spawned in its
                      place (a local actor, never replicated), NeedsRefresh
        its Slot, and its Loaded and Reserve unless Loaded < 0
        a kept one whose Slot changed is HandledItem: it is heard
    what is worn, before the rows: view_worn.py (WornRow --> Worn)

    ViewTrim(Count)
        every actor of Inventory from Count on destroyed, Inventory cut to
        Count

Rows are matched by index, so an item that leaves the middle of the server's
Inventory respawns what follows it of another class: they are hidden actors
of a bag, and it is one frame's work. The slot sync and the equip, which run
on every copy after this, then place and show them exactly as the server's
own: nothing below the view knows whether its actors are the server's or a
picture.

The picture is remade only when a record arrives, so what a client changes
itself stays until the server next says otherwise: all an action that is not
yet the server's can have. A predicted one needs more. The owning client
spends its own shot's round and reloads its own copy at once (shot.py), and a
record that left the server before it answered those would hand the rounds
back for a moment: so a row's rounds are taken only while AsksServed has
caught up with AsksSent (shot_vars.py).
"""

from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from uebp.net import custom_event
from combat import item_vars as IV
from combat.paths import ITEM_CLASS_PATH
from combat.record_vars import (
    AMMO_UNKNOWN, ROW_PARAMS, TRIM_PARAMS, VIEW_ROW, VIEW_TRIM, ViewDirty, ViewItem)
from combat.heat_tuning import HOT_VAR
from combat.torch_tuning import LIT_VAR
from combat.shot_vars import AsksSent, AsksServed
from combat.slot_tuning import HAND, SLOT_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.slot_nodes import for_each, not_, op, valid
from combat.weapon_component.view_worn import author_view_worn
from Sound.sound_items import author_handled
from uebp.nodes.actor import FN_DESTROY, FN_GET_OWNER, FN_GET_TRANSFORM
from uebp.nodes.array import FN_ARR_GET, FN_ARR_RESIZE, FN_ARR_SET, FN_ARR_VALID
from uebp.nodes.inventory import FN_HAND_ROW, FN_INVENTORY_ROW, FN_INVENTORY_ROW_COUNT
from uebp.nodes.palette import MACRO_FOR_LOOP, NODE_SPAWN
from uebp.nodes.math import (
    FN_AND, FN_EQ_CC, FN_EQ_II, FN_GE_II, FN_GREATER_II, FN_NEQ_II, FN_OR, FN_SELECT_II,
    FN_SUB_II)
from uebp.nodes.system import FN_IS_VALID_CLASS, FN_OBJECT_CLASS


def _at(g, var, index):
    n = g.call(FN_ARR_GET, TargetArray=g.get(var), Index=index)
    return _loose_pin(n, "Item", is_input=False)


def carrier(g):
    """Whose record: the component's owner, as the marks name it (dirty.py)."""
    return out(g.call(FN_GET_OWNER))


def rows_loop(g, count, execs):
    """ForLoop over 0..count-1, ``count`` a pin: (index, body, completed)."""
    loop = g.ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    g.keep(loop)
    _set(loop, "FirstIndex", 0)
    _connect(op(g, FN_SUB_II, count, 1), _pin(loop, "LastIndex"))
    for e in execs:
        _connect(e, _pin(loop, "execute"))
    return (_loose_pin(loop, "Index", is_input=False),
            _loose_pin(loop, "LoopBody", is_input=False),
            _loose_pin(loop, "Completed", is_input=False))


def _call(g, name, execs, **params):
    """A call of one of this component's own events, by its bare name."""
    n = g.keep(_node(g.ed, name))
    for param, value in params.items():
        if isinstance(value, int):
            _set(n, param, value)
        else:
            _connect(value, _pin(n, param))
    for e in execs:
        _connect(e, _pin(n, "execute"))
    return then(n)


def _author_view_row(ed):
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(custom_event(ed, VIEW_ROW, ROW_PARAMS))
    index, want = out(event, "Index"), out(event, "Class")
    held = g.call(FN_ARR_VALID, TargetArray=g.get(WV.Inventory), IndexToTest=index)
    there, beyond = g.branch(out(held), [then(event)])
    cur = _at(g, WV.Inventory, index)
    alive, gone = g.branch(valid(g, cur), [there])
    same = out(g.call(FN_EQ_CC, A=out(g.call(FN_OBJECT_CLASS, Object=cur)), B=want))
    keep, replace = g.branch(same, [alive])
    kept = g.put(ViewItem, cur, [keep])
    # Heard, as a slot move is where the server serves it: the kept item
    # whose slot changed, the one that came to hand before any other.
    moved = op(g, FN_NEQ_II, g.iget(cur, SLOT_VAR), out(event, "Slot"))
    first = op(g, FN_OR, op(g, FN_EQ_II, out(event, "Slot"), HAND),
               not_(g, valid(g, g.get(WV.HandledItem))))
    heard, quiet = g.branch(op(g, FN_AND, moved, first), [kept])
    heard = g.put(WV.HandledItem, cur, [heard])

    destroyed = then(g.call(FN_DESTROY, [replace], self=cur))
    spawn = g.keep(_palette(ed, NODE_SPAWN))
    _connect(want, _pin(spawn, "Class"))
    where = g.call(FN_GET_TRANSFORM, self=out(g.call(FN_GET_OWNER)))
    _connect(out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    for e in (destroyed, gone, beyond):
        _connect(e, _pin(spawn, "execute"))
    put = g.call(FN_ARR_SET, [then(spawn)], TargetArray=g.get(WV.Inventory), Index=index,
                 Item=out(spawn))
    _set(put, "bSizeToFit", True)
    made = g.put(ViewItem, out(spawn), [then(put)])
    # Carried, so not a pick-up: a garment's class, like food's, is Dropped
    # until something takes it.
    made = g.iput(out(spawn), IV.Dropped, "false", [made])
    made = g.put(WV.NeedsRefresh, "true", [made])

    item = g.get(ViewItem)
    flow = g.iput(item, SLOT_VAR, out(event, "Slot"), [heard, quiet, made])
    # Burning or hot is the server's word (combat/fire_vars.py): this copy's
    # own Tick shows it, and puts nothing out.
    flow = g.iput(item, LIT_VAR, out(event, "Lit"), [flow])
    flow = g.iput(item, HOT_VAR, out(event, "Hot"), [flow])
    known, _unknown = g.branch(op(g, FN_GE_II, out(event, "Loaded"), 0), [flow])
    flow = g.iput(item, IV.Loaded, out(event, "Loaded"), [known])
    g.iput(item, IV.Reserve, out(event, "Reserve"), [flow])
    ed.add_comment_to_nodes(
        f"{VIEW_ROW} (view.py), a client's: the actor at Inventory[Index] is made to be "
        "the record's row. One of the right class is kept; anything else is destroyed "
        "and a local actor of the class spawned there. Then its slot, whether it "
        "burns or is hot, and its rounds.",
        g.made)


def _author_view_trim(ed):
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(custom_event(ed, VIEW_TRIM, TRIM_PARAMS))
    count = out(event, "Count")
    item, i, body, done = for_each(g, g.get(WV.Inventory), [then(event)])
    extra, _ = g.branch(op(g, FN_GE_II, i, count), [body])
    real, _ = g.branch(valid(g, item), [extra])
    g.call(FN_DESTROY, [real], self=item)
    g.call(FN_ARR_RESIZE, [done], TargetArray=g.get(WV.Inventory), Size=count)
    ed.add_comment_to_nodes(
        f"{VIEW_TRIM} (view.py), a client's: the record has Count rows, so every actor "
        "of Inventory past them is destroyed and Inventory cut to Count.", g.made)


def author_view_events(ed):
    """The two events. Before the Tick, which calls them by name."""
    _author_view_row(ed)
    _author_view_trim(ed)


def _author_view(ed, in_execs):
    """The picture remade when a record arrived (see the module docstring).
    Returns the exec tails."""
    g = _G(ed, ITEM_CLASS_PATH)
    dirty, clean = g.branch(g.get(ViewDirty), in_execs)
    flow = g.put(ViewDirty, "false", [dirty])
    # What is worn first (view_worn.py): the owner's alone, as the rows are.
    flow = author_view_worn(g, [flow])
    rows = out(g.call(FN_INVENTORY_ROW_COUNT, Carrier=carrier(g)))
    own, other = g.branch(op(g, FN_GREATER_II, rows, 0), [flow])
    i, body, done = rows_loop(g, rows, [own])
    # One record, so one length: no row can be half of one.
    row = g.call(FN_INVENTORY_ROW, Carrier=carrier(g), Index=i, Kind=ITEM_CLASS_PATH)
    # The rounds are taken only once the server has answered every shot and
    # reload this client asked for (shot_vars.py): until then the record is
    # older than the client's own count, and taking it would hand back rounds
    # already fired. AsksServed's own arrival raises ViewDirty, so the answer
    # to the last ask is always taken.
    settled = op(g, FN_GE_II, g.get(AsksServed), g.get(AsksSent))
    loaded = out(g.call(FN_SELECT_II, A=out(row, "Loaded"), B=AMMO_UNKNOWN, bPickA=settled))
    _call(g, VIEW_ROW, [body], Index=i, Class=out(row, "Class"), Slot=out(row, "Slot"),
          Loaded=loaded, Reserve=out(row, "Reserve"), Lit=out(row, "Lit"),
          Hot=out(row, "Hot"))
    trimmed = _call(g, VIEW_TRIM, [done], Count=rows)

    hand = g.call(FN_HAND_ROW, Carrier=carrier(g), Kind=ITEM_CLASS_PATH)
    held = out(hand, "Class")
    armed, bare = g.branch(out(g.call(FN_IS_VALID_CLASS, Class=held)), [other])
    one = _call(g, VIEW_ROW, [armed], Index=0, Class=held, Slot=HAND,
                Loaded=AMMO_UNKNOWN, Reserve=AMMO_UNKNOWN, Lit=out(hand, "Lit"),
                Hot=out(hand, "Hot"))
    one = _call(g, VIEW_TRIM, [one], Count=1)
    none = _call(g, VIEW_TRIM, [bare], Count=0)
    tails = author_handled(g, [trimmed, one, none])
    ed.add_comment_to_nodes(
        "A client's inventory is a picture of the server's record (view.py): remade "
        "when one arrives (ViewDirty), read off the record component row by row. Its "
        "own player's from the rows; another player's is the one item in their hand "
        "(HandRow).", g.made[:4])
    return tails + [clean]
