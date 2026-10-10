"""The inventory's record: what a player carries, as plain data (tasks M18,
A3a, A3b). Constants only. The record itself is C++
(Source/Otherworld/Public/OtherworldInventoryRecord.h): one struct, a row per
carried item (its class, slot code, rounds loaded and held, whether it burns
or is hot) and a class per worn slot, held by a component on the character
(RECORD_COMPONENT, which combat/install.py adds) and sent whole to the owning
client. Everyone else is told what the hand holds: the component's HandClass,
HandLit and HandHot; and what is worn, for the garments drawn on the body:
WornClasses. No Blueprint variable holds a copy of any of it.

The server's item actors are still what its graphs work on (Inventory, Worn,
each item's Slot, Loaded, Reserve, Lit and Hot: CARRIED_ARRAYS, ITEM_STATE).
A node that changes one of those is a change site, and combat/dirty.py puts
the mark behind each; the component writes the record once, after the actors
ticked, on a frame something marked. Nothing writes it every Tick.

Classes, ints and flags, nothing that points into a running world (how long
a fire or a heat has left is the server's item's own clock, and is not
written down): so it is also what a save holds, as bytes with a version
first (the struct's ToBytes and FromBytes; probes/probe_record_bytes.py).

A client holds no inventory of its own: its item actors are made from the
record (weapon_component/view.py, which reads it through the library's
InventoryRow, WornRow and HandRow: uebp/nodes/inventory.py), on the frame
after one arrives (the component's RepNotify raises ViewDirty here, by the
name in RECORD_VIEW).
"""

from uebp.vars import BOOL, INT, Var, cls, obj
from combat import item_vars as IV
from combat.heat_tuning import HOT_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.slot_tuning import HAND as HAND_SLOT, SLOT_ITEMS_VAR, SLOT_VAR
from combat.torch_tuning import LIT_VAR
from combat.wear_tuning import WORN_VAR
from combat.weapon_component import vars as WV

ITEM_CLASS = cls(ITEM_CLASS_PATH)

# What the record is read from: the weapon component's two arrays of item
# actors, and five variables of each item. A node that writes one is a change
# site (combat/dirty.py marks it; verify/record.py checks every one is).
CARRIED_ARRAYS = (str(WV.Inventory), WORN_VAR)
ITEM_STATE = (SLOT_VAR, str(IV.Loaded), str(IV.Reserve), LIT_VAR, HOT_VAR)

# The component that holds the record, on the character, the names it reads
# by and the one it raises on a client when a record arrives: properties of
# its template, written by combat/install.py (the C++ defaults are the same
# names).
RECORD_COMPONENT = "InventoryRecord"
RECORD_COMPONENT_CLASS = "/Script/Otherworld.OtherworldInventoryRecordComponent"
RECORD_SOURCE = {
    "InventoryVar": str(WV.Inventory), "WornVar": WORN_VAR, "SlotItemsVar": SLOT_ITEMS_VAR,
    "ItemSlotVar": SLOT_VAR, "ItemLoadedVar": str(IV.Loaded), "ItemReserveVar": str(IV.Reserve),
    "ItemLitVar": LIT_VAR, "ItemHotVar": HOT_VAR,
}
RECORD_HAND_SLOT = ("HandSlot", HAND_SLOT)
# A client's: a record arrived and the item actors are not yet its picture
# (true from the start: the first record may arrive before BeginPlay), and
# the row's actor while ViewRow works on it.
ViewDirty = Var("ViewDirty", BOOL, True)
ViewItem = Var("ViewItem", obj(ITEM_CLASS_PATH))
RECORD_VIEW = {"ViewDirtyVar": str(ViewDirty)}

# What mirrored the record on the weapon component until task A3b: six
# arrays, a row per item (its class, slot, rounds loaded and held, lit, hot),
# the worn slots' classes and the hand's three. The build takes each, and its
# OnRep graph, off a component built before; verify/record.py fails on a
# builder that names one of the arrays again (so they are not spelt here).
RETIRED_ARRAYS = tuple("Inv" + column for column in (
    "Class", "Slot", "Loaded", "Reserve", "Lit", "Hot"))
RETIRED_VARS = RETIRED_ARRAYS + ("WornClass", "HandClass", "HandLit", "HandHot")

# A probe's hand on the asks, read where the keys are (slot_moves.py): the
# slot a number key would ask for, and the move a drag on the HUD would.
# Python cannot send a Blueprint Server event itself (a call from Python runs
# the event on the machine it is made on), so a client's probe writes these
# and the Tick's own graph asks.
NO_ASK = -1
SlotForced = Var("SlotForced", INT, NO_ASK)
MoveForcedFrom = Var("MoveForcedFrom", INT, NO_ASK)
MoveForcedTo = Var("MoveForcedTo", INT, NO_ASK)
# ...and the slot a drag out of the inventory, or the drop key, would set
# down (drop_request.py).
DropForced = Var("DropForced", INT, NO_ASK)
# ...the worn slot the I panel would take off, and where to (TakeOffForcedTo:
# a slot code, or UNPLACED for the bag), and the slot whose garment a drag
# onto the worn grid would wear (wear.py).
TakeOffForced = Var("TakeOffForced", INT, NO_ASK)
TakeOffForcedTo = Var("TakeOffForcedTo", INT, NO_ASK)
WearForced = Var("WearForced", INT, NO_ASK)
FORCED = (SlotForced, MoveForcedFrom, MoveForcedTo, DropForced, TakeOffForced,
          TakeOffForcedTo, WearForced)
TABLE = (ViewDirty, ViewItem) + FORCED

# The view's two events (view.py). A row with Loaded below 0 leaves the
# actor's rounds alone: another player's hand, whose ammo this machine is
# not told.
VIEW_ROW = "ViewRow"
VIEW_TRIM = "ViewTrim"
ROW_PARAMS = (("Index", INT), ("Class", ITEM_CLASS), ("Slot", INT), ("Loaded", INT),
              ("Reserve", INT), ("Lit", BOOL), ("Hot", BOOL))
TRIM_PARAMS = (("Count", INT),)
AMMO_UNKNOWN = -1
# ...and the worn garments' one (view_worn.py): Worn[Slot] made an actor of
# Class, or emptied.
VIEW_WORN = "ViewWorn"
WORN_PARAMS = (("Slot", INT), ("Class", ITEM_CLASS))
