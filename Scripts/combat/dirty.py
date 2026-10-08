"""The marks that have the inventory's record written (task A3a;
combat/record_vars.py says what the record is).

The server writes the record on a frame that changed what a player carries,
and a frame says so by calling MarkInventoryDirty (uebp/nodes/inventory.py).
Thirty-odd graphs change what is carried, in four styles of authoring, and one
that forgot the call would leave a client looking at an old inventory with
nothing logged. So no graph makes the call itself. A change site is found by
what it is:

    a Set of an item's Slot, Loaded, Reserve, Lit or Hot (ITEM_STATE)
    a node with an exec pin that writes Inventory or Worn (CARRIED_ARRAYS):
        Add, Remove, Set Array Elem, Clear, Resize, whatever takes the array
        as TargetArray

and mark_change_sites(ed), called once a graph is whole and before its
compile, splices the mark in behind each: the site's ``then`` runs the mark,
and the mark what the site ran. A graph authored later needs nothing but to be
followed by the same call, which every builder of a graph with a change site
already makes.

Whose record: in the weapon component's own graph (``own=CARRIER``) the
component's owner, the character. In an item's own graph (``own=ITEM``: the
stick burning out, the blade cooling) whoever carries the item. In anyone
else's graph (the HUD's cheat, the profile's load) the item the Set is aimed
at, or the weapon component whose array is written.

Marking is cheap and idempotent (a flag; any number of marks in a frame are
one write), and does nothing on a client, so the picture a client's view makes
of the record (view.py) is marked like anything else and nothing comes of it.

What the pass cannot see (a carried item destroyed and left in Inventory, a
value written by C++ or by Python) the audit can: with
Otherworld.InventoryRecord.Audit on, which probes/boot.py sets for every
probe, the component compares each unmarked record with the item actors every
frame and logs INVENTORY-RECORD-STALE where they differ.
"""

from uebp.g import _G
from uebp.graph import BEL, PIN, _connect, _pin, out, then
from combat.record_vars import CARRIED_ARRAYS, ITEM_STATE
from uebp.nodes.actor import FN_GET_OWNER
from uebp.nodes.inventory import FN_MARK_CARRIED_ITEM_DIRTY, FN_MARK_INVENTORY_DIRTY

# Whose graph this is (mark_change_sites' ``own``).
CARRIER, ITEM, OTHER = "carrier", "item", "other"

MARKS = ("MarkInventoryDirty", "MarkCarriedItemDirty")


def title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ")


def _is_exec(pin):
    return "exec" in str(PIN.get_pin_type_display_string(pin)).lower()


def _input(node, name):
    for p in BEL.list_input_pins(node):
        if str(PIN.get_pin_name(p)) == name:
            return p
    return None


def _sources(pin):
    return list(PIN.list_connected_pins(pin)) if pin else []


def _then(node):
    for p in BEL.list_output_pins(node):
        if _is_exec(p) and str(PIN.get_pin_name(p)) == "then":
            return p
    return None


def is_mark(node):
    return title(node).replace(" ", "") in MARKS


def item_state_set(node):
    """The ITEM_STATE variable this node sets, or None. A RepNotify
    variable's Set is titled ``Set with Notify <Var>``."""
    if "VariableSet" not in type(node).__name__:
        return None
    name = title(node)
    return next((v for v in ITEM_STATE if name.startswith("Set") and name.endswith(f" {v}")),
                None)


def carried_array_write(node):
    """The Get node of the CARRIED_ARRAYS variable this node writes, or None.
    A pure node (Length, Get, Contains) has no exec pin and writes nothing."""
    target = _input(node, "TargetArray")
    if not target or _then(node) is None:
        return None
    for q in _sources(target):
        feeder = PIN.get_owning_node(q)
        if title(feeder) in {f"Get {a}" for a in CARRIED_ARRAYS}:
            return feeder
    return None


def change_sites(nodes):
    """``(node, what, source)`` for every change site among ``nodes``: what
    it writes (a variable's name), and the pin the written object comes from
    (the item a Set is aimed at, the component an array is read off), or None
    when that is the graph's own self."""
    found = []
    for n in nodes:
        var = item_state_set(n)
        if var:
            aimed = _sources(_input(n, "self"))
            found.append((n, var, aimed[0] if aimed else None))
            continue
        get = carried_array_write(n)
        if get:
            held = _sources(_input(get, "self"))
            found.append((n, title(get)[len("Get "):], held[0] if held else None))
    return found


def marked(node):
    """The site's ``then`` runs a mark, and nothing else."""
    after = [PIN.get_owning_node(q) for q in _sources(_then(node))]
    return len(after) == 1 and is_mark(after[0])


def _splice(g, node, fn, **inputs):
    tail = _then(node)
    after = _sources(tail)
    PIN.break_pin_links(tail)
    mark = g.call(fn, [tail], **inputs)
    for q in after:
        _connect(then(mark), q)


def mark_change_sites(ed, own):
    """Put the mark behind every change site of ``ed``'s graph (see the module
    docstring). Returns what each site writes, for the log."""
    g = _G(ed)
    wrote = []
    for node, what, source in change_sites(list(ed.list_all_nodes())):
        if marked(node):
            continue
        is_item = what in ITEM_STATE
        if own == CARRIER:
            _splice(g, node, FN_MARK_INVENTORY_DIRTY, Carrier=out(g.call(FN_GET_OWNER)))
        elif is_item and source is not None:
            _splice(g, node, FN_MARK_CARRIED_ITEM_DIRTY, Item=source)
        elif is_item and own == ITEM:
            # Item unconnected: this graph's own actor.
            _splice(g, node, FN_MARK_CARRIED_ITEM_DIRTY)
        elif not is_item and source is not None:
            _splice(g, node, FN_MARK_INVENTORY_DIRTY, Carrier=source)
        else:
            # A variable of the same name on something that is not an item.
            continue
        wrote.append(what)
    if g.made:
        ed.add_comment_to_nodes(
            "What is carried changed here: the mark has the server write the "
            "inventory's record at the end of this frame (combat/dirty.py).", g.made[-1:])
    return wrote
