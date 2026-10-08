"""uebp.nodes.inventory -- the game's own inventory library (C++, the
Otherworld module: Source/Otherworld/Public/OtherworldInventoryRecord.h).
What a player carries is written down as one record, by the server, at the
end of a frame that changed it (task A3a); these are how a graph says one
did. Nothing on a client.

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
# For the probes: the record as text, the times it was written, the times
# the audit found it stale, the audit's switch, and whether Push Model is on.
FN_DESCRIBE_INVENTORY_RECORD = INVENTORY_LIBRARY + ".DescribeInventoryRecord"
FN_INVENTORY_RECORD_WRITES = INVENTORY_LIBRARY + ".InventoryRecordWrites"
FN_INVENTORY_RECORD_STALE = INVENTORY_LIBRARY + ".InventoryRecordStale"
FN_SET_INVENTORY_RECORD_AUDIT = INVENTORY_LIBRARY + ".SetInventoryRecordAudit"
FN_IS_PUSH_MODEL_ON = INVENTORY_LIBRARY + ".IsPushModelOn"
