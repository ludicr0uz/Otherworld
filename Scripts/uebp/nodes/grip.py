"""uebp.nodes.grip -- the game's own grip library (C++, the Otherworld
module: Source/Otherworld/Public/OtherworldGripLibrary.h). Where a held item
sits under the grip socket, its Grip component and its row of the nudge table
together (H2), and the tuning tab's reads and writes of that row.
"""

GRIP_LIBRARY = "/Script/Otherworld.OtherworldGripLibrary"

# Item -> the transform the equip sets on it: inverse(Grip) * its nudge row.
FN_GRIP_SEAT = GRIP_LIBRARY + ".GripSeat"
# Pawn -> the item its weapon component holds, or null.
FN_HELD_ITEM_OF = GRIP_LIBRARY + ".HeldItemOf"
# Item, Table, First: the item's row into / out of six cells of a tab's table.
# The write seats the item anew and saves the file when the cells moved.
FN_READ_GRIP_CELLS = GRIP_LIBRARY + ".ReadGripCells"
FN_WRITE_GRIP_CELLS = GRIP_LIBRARY + ".WriteGripCells"
