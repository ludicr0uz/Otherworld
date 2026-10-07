"""What a dying player was carrying leaves them, on a server: the first thing
the dead gate's dead arm does, once per death.

    the dead arm --> [OwnerDead already?] --yes--> on
                       no --> [IsStandalone?] --yes--> on (nothing is shed)
                                no --> every item of Inventory, then of Worn:
                                         on the server: its class, DisplayName,
                                             Icon and SlotColor onto the body's
                                             Loot arrays (the owner's
                                             BP_HealthComponent)
                                         DestroyActor
                                       Inventory and Worn emptied, SlotItems
                                       all None, Held None,
                                       EquippedIndex -1 --> on

Standalone sheds nothing: its death is the end of that game (death.py: the
profile deleted, back to the title), exactly as before, and the mode table's
death row is the one place the two differ (serversupportsysdesign.md 4.8).

On a server the body becomes the corpse the loot window searches
(graphics_menu/loot_*.py), as a wanderer's does: a body holds classes, not
actors (loot/roll.py), so each item is recorded and then destroyed. The
record is the server's alone and replicates with the health component; the
destroy runs on every copy: each machine holds item actors of its own for
the character (a client's are a picture of the server's record, view.py), and
the dead gate stops the Tick that would remove a client's.

A class remembers no rounds: a looted gun is a fresh one, until a body's loot
is rows of the inventory's record (combat/record_vars.py; not yet: the take,
loot_take.py, is the server's since M23, and still of a class).
The server empties that record here too (record.py).

OwnerDead is read before the gate sets it, which makes this the frame the
owner was first found dead: no latch of its own.
"""

from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _pin, out, then
from combat import item_vars as IV
from combat.paths import HEALTH_CLASS_PATH, ITEM_CLASS_PATH
from combat.slot_tuning import SLOT_COUNT, SLOT_ITEMS_VAR
from combat.wear_tuning import WORN_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.record import author_empty_record
from loot.consts import LOOT_ICONS_VAR, LOOT_NAMES_VAR, LOOT_TINTS_VAR, LOOT_VAR
from uebp.nodes.actor import FN_DESTROY, FN_HAS_AUTHORITY
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_CLEAR, FN_ARR_RESIZE
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import FN_IS_STANDALONE, FN_IS_VALID, FN_OBJECT_CLASS

# The component's arrays of carried things: the bag, the hand and the weapon
# slots are all Inventory; a worn garment is out of it (wear_tuning.py).
CARRIED = (WV.Inventory, WORN_VAR)
EMPTY_HANDS = -1


def _author_shed_all(g, var, owner_out, as_health, exec_in):
    """Every item of one array onto the body (the server) and destroyed.
    Returns the loop's Completed pin."""
    loop = g.keep(g.ed.add_macro_node(MACRO_FOR_EACH))
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _connect(g.get(var), _loose_pin(loop, "Array"))
    _connect(exec_in, _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)
    # Worn has a None for every slot nothing is worn in.
    real, _ = g.branch(out(g.call(FN_IS_VALID, Object=item)),
                       [_loose_pin(loop, "LoopBody", is_input=False)])
    server, client = g.branch(out(g.call(FN_HAS_AUTHORITY, self=owner_out)), [real])
    flow = server
    for body_var, value in ((LOOT_VAR, out(g.call(FN_OBJECT_CLASS, Object=item))),
                            (LOOT_NAMES_VAR, g.iget(item, IV.DisplayName)),
                            (LOOT_ICONS_VAR, g.iget(item, IV.Icon)),
                            (LOOT_TINTS_VAR, g.iget(item, IV.SlotColor))):
        add = g.call(FN_ARR_ADD, [flow],
                     TargetArray=g.iget(as_health, body_var, HEALTH_CLASS_PATH), NewItem=value)
        flow = then(add)
    g.call(FN_DESTROY, [flow, client], self=item)
    return _loose_pin(loop, "Completed", is_input=False)


def author_shed_gear(ed, owner_out, as_health, was_dead, exec_in):
    """See the module docstring. ``as_health``: the owner's health component,
    the dead gate's cast; ``was_dead``: OwnerDead, read before the gate sets
    it. Returns the exec pins to carry on from."""
    g = _G(ed, ITEM_CLASS_PATH)
    already, first = g.branch(was_dead, [exec_in])
    alone, shared = g.branch(out(g.call(FN_IS_STANDALONE)), [first])
    flow = shared
    for var in CARRIED:
        flow = _author_shed_all(g, var, owner_out, as_health, flow)
    for var in CARRIED:
        flow = then(g.call(FN_ARR_CLEAR, [flow], TargetArray=g.get(var)))
    # The slots keep their count: the HUD reads SlotItems[c] for every c.
    flow = then(g.call(FN_ARR_CLEAR, [flow], TargetArray=g.get(SLOT_ITEMS_VAR)))
    flow = then(g.call(FN_ARR_RESIZE, [flow], TargetArray=g.get(SLOT_ITEMS_VAR),
                       Size=SLOT_COUNT))
    flow = g.put(WV.Held, None, [flow])
    flow = g.put(WV.EquippedIndex, str(EMPTY_HANDS), [flow])
    # The record with them (record.py): the dead gate stops the upkeep that
    # writes it.
    emptied = author_empty_record(g, [flow])
    ed.add_comment_to_nodes(
        "A player found dead, on a server (never in standalone): what they carried and "
        "wore goes onto the body, as classes with their name, icon and tint (the "
        "server's record, which the loot window reads), and every copy destroys its own "
        "actors and empties its slots (shed.py).", g.made)
    return [already, alone, *emptied]
