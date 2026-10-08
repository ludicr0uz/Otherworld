"""uebp.nodes.inventory -- the game's own inventory library (C++, the
Otherworld module: Source/Otherworld/Public/OtherworldInventoryRecord.h).
What a player carries is written down as one record, by the server, at the
end of a frame that changed it (task A3a); these are how a graph says one
did. Nothing on a client. A client reads the record it was sent through the
view's three reads (task A3b), and a save its bytes.

A graph does not call them by hand: combat/dirty.py finds every node that
changes what is carried and puts the mark behind it.
"""

INVENTORY_LIBRARY = "/Script/Otherworld.OtherworldInventoryLibrary"

# Carrier (the character, or one of its components) -> its record is written
# at the end of this frame. The serve, the take, the drop, the throw, the
# shed, the wear, the reload, the shot, the consume: any change to Inventory,
# Worn or a carried item's Slot, Loaded, Reserve, Lit or Hot.
FN_MARK_INVENTORY_DIRTY = INVENTORY_LIBRARY + ".MarkInventoryDirty"
# Item -> whoever carries it is marked (nobody, for one lying in the world).
# Item unconnected is the graph's own actor: an item's own Tick (the stick
# burnt out, the blade cooled).
FN_MARK_CARRIED_ITEM_DIRTY = INVENTORY_LIBRARY + ".MarkCarriedItemDirty"
# The view's reads (combat/weapon_component/view.py), off the record as this
# machine holds it. Carrier as above; Kind is a class pin whose literal types
# the Class output (the class every carried item is a child of).
# Carrier -> the rows of its record (none on anyone's machine but its owner's).
FN_INVENTORY_ROW_COUNT = INVENTORY_LIBRARY + ".InventoryRowCount"
# Carrier, Index, Kind -> Class, Slot, Loaded, Reserve, Lit, Hot.
FN_INVENTORY_ROW = INVENTORY_LIBRARY + ".InventoryRow"
# Carrier -> its worn slots; Carrier, Slot, Kind -> Class (none: nothing worn).
FN_WORN_ROW_COUNT = INVENTORY_LIBRARY + ".WornRowCount"
FN_WORN_ROW = INVENTORY_LIBRARY + ".WornRow"
# Carrier, Kind -> Class, Lit, Hot: its hand, as everyone but its owner is told.
FN_HAND_ROW = INVENTORY_LIBRARY + ".HandRow"
# The save's (task M35) and the probes': a carrier's record, a record as the
# bytes a save holds (a version first) and back, that version, and as text.
FN_INVENTORY_RECORD_OF = INVENTORY_LIBRARY + ".InventoryRecordOf"
FN_INVENTORY_RECORD_TO_BYTES = INVENTORY_LIBRARY + ".InventoryRecordToBytes"
FN_INVENTORY_RECORD_FROM_BYTES = INVENTORY_LIBRARY + ".InventoryRecordFromBytes"
FN_INVENTORY_RECORD_SAVE_VERSION = INVENTORY_LIBRARY + ".InventoryRecordSaveVersion"
FN_DESCRIBE_RECORD = INVENTORY_LIBRARY + ".DescribeRecord"
# For the probes: the record as text, the times it was written, the times
# the audit found it stale, the audit's switch, and whether Push Model is on.
FN_DESCRIBE_INVENTORY_RECORD = INVENTORY_LIBRARY + ".DescribeInventoryRecord"
FN_INVENTORY_RECORD_WRITES = INVENTORY_LIBRARY + ".InventoryRecordWrites"
FN_INVENTORY_RECORD_STALE = INVENTORY_LIBRARY + ".InventoryRecordStale"
FN_SET_INVENTORY_RECORD_AUDIT = INVENTORY_LIBRARY + ".SetInventoryRecordAudit"
FN_IS_PUSH_MODEL_ON = INVENTORY_LIBRARY + ".IsPushModelOn"
