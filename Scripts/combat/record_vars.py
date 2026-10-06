"""The inventory's record: what a player carries, as plain data (task M18).
Constants only; the graphs are weapon_component/record.py (the server writes
it) and view.py (a client makes its item actors from it).

The server's item actors are still what its graphs work on (Inventory, each
item's Slot, Loaded and Reserve). After the slots are placed, every Tick, the
server writes them down as four arrays of one length, a row per carried item,
in Inventory's order:

    InvClass[i]     the item's class
    InvSlot[i]      its slot code (slot_tuning.py: the hand, a weapon slot, a
                    bag slot)
    InvLoaded[i]    the rounds in it
    InvReserve[i]   the rounds held for it

Classes and ints, nothing that points into a running world: the save writes
the four arrays as they stand and a load is ``SpawnActor`` per row (the
character's save task reuses them). They replicate to the owning client
alone. Everyone else is told one thing, the class in the hand (HandClass).

A client holds no inventory of its own: its item actors are made from the
record (view.py), on the frame after one of these arrives (each is a
RepNotify that raises ViewDirty).
"""

from uebp.vars import BOOL, INT, Var, array, cls, obj
from combat.paths import ITEM_CLASS_PATH

ITEM_CLASS = cls(ITEM_CLASS_PATH)

# Replicated to the owner. One row per carried item.
InvClass = Var("InvClass", array(ITEM_CLASS))
InvSlot = Var("InvSlot", array(INT))
InvLoaded = Var("InvLoaded", array(INT))
InvReserve = Var("InvReserve", array(INT))
RECORD = (InvClass, InvSlot, InvLoaded, InvReserve)
# Replicated to everyone but the owner: what the hand holds, or none.
HandClass = Var("HandClass", ITEM_CLASS)
REPLICATED = RECORD + (HandClass,)

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
FORCED = (SlotForced, MoveForcedFrom, MoveForcedTo)
TABLE = REPLICATED + (ViewDirty, ViewItem) + FORCED

# The view's two events (view.py). A row with Loaded below 0 leaves the
# actor's rounds alone: another player's hand, whose ammo this machine is
# not told.
VIEW_ROW = "ViewRow"
VIEW_TRIM = "ViewTrim"
ROW_PARAMS = (("Index", INT), ("Class", ITEM_CLASS), ("Slot", INT), ("Loaded", INT),
              ("Reserve", INT))
TRIM_PARAMS = (("Count", INT),)
AMMO_UNKNOWN = -1
