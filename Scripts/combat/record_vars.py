"""The inventory's record: what a player carries, as plain data (tasks M18,
A3a). Constants only. The record itself is C++
(Source/Otherworld/Public/OtherworldInventoryRecord.h): one struct, a row per
carried item and a class per worn slot, held by a component on the character
(RECORD_COMPONENT, which combat/install.py adds) and sent whole to the owning
client.

The server's item actors are still what its graphs work on (Inventory, Worn,
each item's Slot, Loaded, Reserve, Lit and Hot: CARRIED_ARRAYS, ITEM_STATE).
A node that changes one of those is a change site, and combat/dirty.py puts
the mark behind each; the component writes the record once, after the actors
ticked, on a frame something marked. Nothing writes it every Tick.

Until the client's view reads the struct (task A3b), the component also
writes these variables of the weapon component from it, in the same frame,
and they still replicate, for weapon_component/view.py:

    InvClass[i]     the item's class
    InvSlot[i]      its slot code (slot_tuning.py: the hand, a weapon slot, a
                    bag slot)
    InvLoaded[i]    the rounds in it
    InvReserve[i]   the rounds held for it
    InvLit[i]       it is burning (a stick lit at a fire: task M25)
    InvHot[i]       it is hot (a blade heated at one)
    WornClass[slot] the class of the garment worn there, or none (a row per
                    worn slot, wear_tuning.WEAR_SLOTS' index; as long as the
                    server's Worn, which the first wear into a slot grows)

Classes, ints and flags, nothing that points into a running world (how long
a fire or a heat has left is the server's item's own clock, and is not
written down). They go to the owning client alone. Everyone else is told what
the hand holds: its class (HandClass) and whether it burns or glows (HandLit,
HandHot).

A client holds no inventory of its own: its item actors are made from the
record (view.py), on the frame after one of these arrives (each is a
RepNotify that raises ViewDirty).
"""

from uebp.vars import BOOL, INT, Var, array, cls, obj
from combat import item_vars as IV
from combat.heat_tuning import HOT_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.slot_tuning import HAND as HAND_SLOT, SLOT_ITEMS_VAR, SLOT_VAR
from combat.torch_tuning import LIT_VAR
from combat.wear_tuning import WORN_VAR
from combat.weapon_component import vars as WV

ITEM_CLASS = cls(ITEM_CLASS_PATH)

# Replicated to the owner. One row per carried item.
InvClass = Var("InvClass", array(ITEM_CLASS))
InvSlot = Var("InvSlot", array(INT))
InvLoaded = Var("InvLoaded", array(INT))
InvReserve = Var("InvReserve", array(INT))
InvLit = Var("InvLit", array(BOOL))
InvHot = Var("InvHot", array(BOOL))
RECORD = (InvClass, InvSlot, InvLoaded, InvReserve, InvLit, InvHot)
# Replicated to the owner too: a row per worn slot, the garment's class or none.
WornClass = Var("WornClass", array(ITEM_CLASS))
# Replicated to everyone but the owner: what the hand holds, or none.
HandClass = Var("HandClass", ITEM_CLASS)
HandLit = Var("HandLit", BOOL, False)
HandHot = Var("HandHot", BOOL, False)
HAND = (HandClass, HandLit, HandHot)
REPLICATED = RECORD + (WornClass,) + HAND

# What the record is read from: the weapon component's two arrays of item
# actors, and five variables of each item. A node that writes one is a change
# site (combat/dirty.py marks it; verify/record.py checks every one is).
CARRIED_ARRAYS = (str(WV.Inventory), WORN_VAR)
ITEM_STATE = (SLOT_VAR, str(IV.Loaded), str(IV.Reserve), LIT_VAR, HOT_VAR)

# The component that holds the record, on the character, and the names it
# reads by and mirrors to: properties of its template, written by
# combat/install.py (the C++ defaults are the same names).
RECORD_COMPONENT = "InventoryRecord"
RECORD_COMPONENT_CLASS = "/Script/Otherworld.OtherworldInventoryRecordComponent"
RECORD_SOURCE = {
    "InventoryVar": str(WV.Inventory), "WornVar": WORN_VAR, "SlotItemsVar": SLOT_ITEMS_VAR,
    "ItemSlotVar": SLOT_VAR, "ItemLoadedVar": str(IV.Loaded), "ItemReserveVar": str(IV.Reserve),
    "ItemLitVar": LIT_VAR, "ItemHotVar": HOT_VAR,
}
RECORD_HAND_SLOT = ("HandSlot", HAND_SLOT)
RECORD_MIRROR = {
    "MirrorClassVar": str(InvClass), "MirrorSlotVar": str(InvSlot),
    "MirrorLoadedVar": str(InvLoaded), "MirrorReserveVar": str(InvReserve),
    "MirrorLitVar": str(InvLit), "MirrorHotVar": str(InvHot), "MirrorWornVar": str(WornClass),
    "MirrorHandClassVar": str(HandClass), "MirrorHandLitVar": str(HandLit),
    "MirrorHandHotVar": str(HandHot),
}

# A client's: a record arrived and the item actors are not yet its picture
# (true from the start: the first record may arrive before BeginPlay), and
# the row's actor while ViewRow works on it.
ViewDirty = Var("ViewDirty", BOOL, True)
ViewItem = Var("ViewItem", obj(ITEM_CLASS_PATH))

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
TABLE = REPLICATED + (ViewDirty, ViewItem) + FORCED

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
