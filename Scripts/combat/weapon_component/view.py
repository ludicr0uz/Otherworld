"""A client's half of the inventory's record (combat/record_vars.py): its
item actors are a picture of what the server says is carried, remade when a
record arrives. Never run with authority.

    upkeep, without authority, when ViewDirty:
        the record has rows (this machine's own player: only the owner is
        sent them) --> ViewRow(i, InvClass[i], InvSlot[i], InvLoaded[i],
                               InvReserve[i]) for each, ViewTrim(rows)
        it has none (another player's character, or an owner carrying
        nothing) --> HandClass set: ViewRow(0, HandClass, HAND, unknown ammo),
                                    ViewTrim(1)
                     HandClass none: ViewTrim(0)

    ViewRow(Index, Class, Slot, Loaded, Reserve)
        Inventory[Index] is an actor of Class --> kept
        otherwise --> what is there is destroyed, one of Class spawned in its
                      place (a local actor, never replicated), NeedsRefresh
        its Slot, and its Loaded and Reserve unless Loaded < 0
        a kept one whose Slot changed is HandledItem: it is heard
    what is worn, before the rows: view_worn.py (WornClass --> Worn)

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
    AMMO_UNKNOWN, HandClass, InvClass, InvLoaded, InvReserve, InvSlot, RECORD, ROW_PARAMS,
    TRIM_PARAMS, VIEW_ROW, VIEW_TRIM, ViewDirty, ViewItem)
from combat.shot_vars import AsksSent, AsksServed
from combat.slot_tuning import HAND, SLOT_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.slot_nodes import for_each, not_, op, valid
from combat.weapon_component.view_worn import author_view_worn
from Sound.sound_items import author_handled
from uebp.nodes.actor import FN_DESTROY, FN_GET_OWNER, FN_GET_TRANSFORM
from uebp.nodes.array import FN_ARR_GET, FN_ARR_LEN, FN_ARR_RESIZE, FN_ARR_SET, FN_ARR_VALID
from uebp.nodes.math import FN_AND, FN_EQ_CC, FN_EQ_II, FN_GE_II, FN_GREATER_II, FN_NEQ_II, FN_OR, FN_SELECT_II
from uebp.nodes.palette import NODE_SPAWN
from uebp.nodes.system import FN_IS_VALID_CLASS, FN_OBJECT_CLASS


def _at(g, var, index):
    n = g.call(FN_ARR_GET, TargetArray=g.get(var), Index=index)
    return _loose_pin(n, "Item", is_input=False)


def _length(g, var):
    return out(g.call(FN_ARR_LEN, TargetArray=g.get(var)))


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
    known, _unknown = g.branch(op(g, FN_GE_II, out(event, "Loaded"), 0), [flow])
    flow = g.iput(item, IV.Loaded, out(event, "Loaded"), [known])
    g.iput(item, IV.Reserve, out(event, "Reserve"), [flow])
    ed.add_comment_to_nodes(
        f"{VIEW_ROW} (view.py), a client's: the actor at Inventory[Index] is made to be "
        "the record's row. One of the right class is kept; anything else is destroyed "
        "and a local actor of the class spawned there. Then its slot and its rounds.",
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
    rows = _length(g, InvClass)
    own, other = g.branch(op(g, FN_GREATER_II, rows, 0), [flow])
    # Four arrays of one length: the server writes them in one frame.
    whole = None
    for var in RECORD[1:]:
        same = op(g, FN_EQ_II, _length(g, var), rows)
        whole = same if whole is None else op(g, FN_AND, whole, same)
    sound, torn = g.branch(whole, [own])
    cls, i, body, done = for_each(g, g.get(InvClass), [sound])
    # The rounds are taken only once the server has answered every shot and
    # reload this client asked for (shot_vars.py): until then the record is
    # older than the client's own count, and taking it would hand back rounds
    # already fired. AsksServed's own arrival raises ViewDirty, so the answer
    # to the last ask is always taken.
    settled = op(g, FN_GE_II, g.get(AsksServed), g.get(AsksSent))
    loaded = out(g.call(FN_SELECT_II, A=_at(g, InvLoaded, i), B=AMMO_UNKNOWN,
                        bPickA=settled))
    _call(g, VIEW_ROW, [body], Index=i, Class=cls, Slot=_at(g, InvSlot, i),
          Loaded=loaded, Reserve=_at(g, InvReserve, i))
    trimmed = _call(g, VIEW_TRIM, [done], Count=rows)

    armed, bare = g.branch(out(g.call(FN_IS_VALID_CLASS, Class=g.get(HandClass))), [other])
    one = _call(g, VIEW_ROW, [armed], Index=0, Class=g.get(HandClass), Slot=HAND,
                Loaded=AMMO_UNKNOWN, Reserve=AMMO_UNKNOWN)
    one = _call(g, VIEW_TRIM, [one], Count=1)
    none = _call(g, VIEW_TRIM, [bare], Count=0)
    tails = author_handled(g, [trimmed, one, none])
    ed.add_comment_to_nodes(
        "A client's inventory is a picture of the server's record (view.py): remade "
        "when one arrives (ViewDirty). Its own player's from the rows; another "
        "player's is the one item in their hand (HandClass).", g.made[:4])
    return tails + [clean, torn]
